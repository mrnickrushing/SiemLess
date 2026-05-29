"""Cloud connector manager — polls enabled connectors on a schedule."""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.connector import CloudConnector

logger = logging.getLogger(__name__)


class ConnectorManager:
    _task: asyncio.Task | None = None

    async def start(self) -> None:
        """
        Start the connector manager's background polling task.
        
        Creates and stores an asyncio Task that runs the manager's internal polling loop by assigning it to self._task.
        """
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Connector manager started")

    async def stop(self) -> None:
        """
        Stop the background polling task if it is currently running.
        
        If a background task exists and is not completed, cancels it; does nothing if there is no task or it is already done. The method does not wait for the task's cancellation to complete.
        """
        if self._task and not self._task.done():
            self._task.cancel()

    async def poll_connector(self, connector_id: str) -> dict:
        """
        Trigger an immediate poll for the connector identified by connector_id and persist the results.
        
        Parameters:
            connector_id (str): Identifier of the CloudConnector to poll.
        
        Returns:
            dict: A mapping with key `events_ingested` containing the number of events ingested.
        
        Raises:
            ValueError: If no connector with the given `connector_id` exists.
        """
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(CloudConnector).where(CloudConnector.id == connector_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise ValueError(f"Connector {connector_id} not found")
            count = await self._poll_one(db, row)
            await db.commit()
            return {"events_ingested": count}

    async def _poll_loop(self) -> None:
        """
        Run an indefinite background loop that periodically polls enabled CloudConnector records and updates their database state.
        
        Every 60 seconds the loop queries enabled connectors and, for each connector whose last_polled_at is absent or older than its poll_interval_seconds, performs a connector poll, then:
        - sets `last_polled_at` to the current UTC time on success,
        - increments `events_ingested_total` by the number of events returned (treating a missing total as 0),
        - clears `last_error` on success,
        - on poll failure stores the exception message truncated to 500 characters in `last_error` and logs a warning.
        
        After processing the batch of connectors the loop commits the transaction. Any exception raised outside per-connector polling is logged as an error. This method does not return; it runs until the surrounding task is cancelled.
        """
        while True:
            await asyncio.sleep(60)  # Check every minute
            try:
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(CloudConnector).where(CloudConnector.enabled == True)  # noqa: E712
                    )
                    connectors = result.scalars().all()
                    for row in connectors:
                        now = datetime.now(timezone.utc)
                        last = row.last_polled_at
                        if last is None or (now - last).total_seconds() >= row.poll_interval_seconds:
                            try:
                                count = await self._poll_one(db, row)
                                row.last_polled_at = now
                                row.events_ingested_total = (row.events_ingested_total or 0) + count
                                row.last_error = None
                            except Exception as exc:
                                row.last_error = str(exc)[:500]
                                logger.warning("Connector %s poll failed: %s", row.name, exc)
                    await db.commit()
            except Exception as exc:
                logger.error("Connector manager poll loop error: %s", exc)

    async def _poll_one(self, db, row: CloudConnector) -> int:
        """
        Poll a single CloudConnector record and return how many events were ingested.
        
        Parameters:
            db: Async SQLAlchemy session used by the connector during polling.
            row (CloudConnector): Database row describing the connector (its type, config, and last_polled_at).
        
        Returns:
            int: The number of events ingested by the connector.
        """
        connector = self._get_connector(row)
        return await connector.poll(db, since=row.last_polled_at)

    def _get_connector(self, row: CloudConnector):
        """
        Instantiates a connector implementation configured from the given CloudConnector row.
        
        Parameters:
            row (CloudConnector): Database row containing connector metadata; `row.connector_type` selects the implementation and `row.config` supplies its configuration.
        
        Returns:
            An instance of the connector implementation corresponding to `row.connector_type`.
        
        Raises:
            ValueError: If `row.connector_type` is not one of the supported connector types.
        """
        config = row.config or {}
        if row.connector_type == "aws_cloudtrail":
            from app.services.connectors.aws_cloudtrail import AWSCloudTrailConnector
            return AWSCloudTrailConnector(config)
        elif row.connector_type == "azure_activity":
            from app.services.connectors.azure_activity import AzureActivityConnector
            return AzureActivityConnector(config)
        elif row.connector_type == "gcp_logging":
            from app.services.connectors.gcp_logging import GCPLoggingConnector
            return GCPLoggingConnector(config)
        else:
            raise ValueError(f"Unknown connector type: {row.connector_type}")


connector_manager = ConnectorManager()
