"""Threat feed connector manager — manages polling schedule."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.threat_feed import ThreatFeedConnector

logger = logging.getLogger(__name__)


class FeedManager:
    _task: asyncio.Task | None = None

    async def start(self) -> None:
        """
        Start the background polling task that periodically pulls enabled threat feeds.
        
        Schedules the manager's polling loop as an asyncio Task and stores it on the instance.
        """
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Threat feed manager started")

    async def stop(self) -> None:
        """
        Stop the background polling task if it is currently running.
        
        If a polling task exists and has not completed, cancel it. This method does not wait for the task to finish or handle its cancellation outcome.
        """
        if self._task and not self._task.done():
            self._task.cancel()

    async def pull_now(self, feed_id: str) -> dict:
        """
        Trigger an immediate pull of the specified threat feed.
        
        Parameters:
        	feed_id (str): UUID or identifier of the ThreatFeedConnector to pull.
        
        Returns:
        	result (dict): Mapping with key `"indicators_added"` set to the number of indicators added.
        
        Raises:
        	ValueError: If no feed with the given `feed_id` exists.
        """
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ThreatFeedConnector).where(ThreatFeedConnector.id == feed_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise ValueError(f"Feed {feed_id} not found")
            count = await self._pull_one(db, row)
            await db.commit()
            return {"indicators_added": count}

    async def _poll_loop(self) -> None:
        """
        Background loop that periodically polls enabled threat feeds and updates their stored metadata.
        
        On each iteration it waits one hour, loads all enabled ThreatFeedConnector records, and for each feed
        whose configured pull interval has elapsed (or that has never been pulled) performs a pull via
        _self._pull_one_. On successful pulls it sets `last_pulled_at` to the current UTC time, increments
        `indicator_count` (treating `None` as zero), and clears `last_error`. If a per-feed pull raises an
        exception, `last_error` is set to the exception text truncated to 500 characters and a warning is logged.
        All changes are committed after processing the batch of feeds. Unhandled errors from the outer loop
        are logged and the loop continues.
        """
        while True:
            await asyncio.sleep(3600)  # Check every hour
            try:
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(ThreatFeedConnector).where(
                            ThreatFeedConnector.enabled == True  # noqa: E712
                        )
                    )
                    feeds = result.scalars().all()
                    for feed in feeds:
                        now = datetime.now(timezone.utc)
                        last = feed.last_pulled_at
                        interval = timedelta(hours=feed.pull_interval_hours)
                        if last is None or (now - last) >= interval:
                            try:
                                count = await self._pull_one(db, feed)
                                feed.last_pulled_at = now
                                feed.indicator_count = (feed.indicator_count or 0) + count
                                feed.last_error = None
                            except Exception as exc:
                                feed.last_error = str(exc)[:500]
                                logger.warning("Feed %s pull failed: %s", feed.name, exc)
                    await db.commit()
            except Exception as exc:
                logger.error("Feed manager poll loop error: %s", exc)

    async def _pull_one(self, db, row: ThreatFeedConnector) -> int:
        """
        Pulls indicators for a single feed connector and returns the number added.
        
        Parameters:
            db (AsyncSession): Async database session passed to the connector's pull method.
            row (ThreatFeedConnector): Feed record whose configuration is used; `row.last_pulled_at` is provided as the `since` argument.
        
        Returns:
            int: Number of indicators added by the pull.
        """
        connector = self._get_connector(row)
        return await connector.pull(db, since=row.last_pulled_at)

    def _get_connector(self, row: ThreatFeedConnector):
        """
        Return a connector instance appropriate for the given threat feed record.
        
        Parameters:
            row (ThreatFeedConnector): Database model instance describing the feed (contains feed_type, url, api_key).
        
        Returns:
            connector: An instance of the feed-specific connector class corresponding to `row.feed_type`.
        
        Raises:
            ValueError: If `row.feed_type` is not a recognized connector type.
        """
        if row.feed_type == "misp":
            from app.services.feed_connectors.misp import MISPFeedConnector
            return MISPFeedConnector(row.url, row.api_key)
        elif row.feed_type == "opencti":
            from app.services.feed_connectors.opencti import OpenCTIFeedConnector
            return OpenCTIFeedConnector(row.url, row.api_key)
        else:
            raise ValueError(f"Unknown feed type: {row.feed_type}")


feed_manager = FeedManager()
