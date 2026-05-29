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
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Connector manager started")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()

    async def poll_connector(self, connector_id: str) -> dict:
        """Immediately poll a specific connector."""
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
        connector = self._get_connector(row)
        return await connector.poll(db, since=row.last_polled_at)

    def _get_connector(self, row: CloudConnector):
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
