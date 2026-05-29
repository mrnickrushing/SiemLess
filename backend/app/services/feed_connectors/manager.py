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
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Threat feed manager started")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()

    async def pull_now(self, feed_id: str) -> dict:
        """Immediately pull a specific threat feed."""
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
        connector = self._get_connector(row)
        return await connector.pull(db, since=row.last_pulled_at)

    def _get_connector(self, row: ThreatFeedConnector):
        if row.feed_type == "misp":
            from app.services.feed_connectors.misp import MISPFeedConnector
            return MISPFeedConnector(row.url, row.api_key)
        elif row.feed_type == "opencti":
            from app.services.feed_connectors.opencti import OpenCTIFeedConnector
            return OpenCTIFeedConnector(row.url, row.api_key)
        else:
            raise ValueError(f"Unknown feed type: {row.feed_type}")


feed_manager = FeedManager()
