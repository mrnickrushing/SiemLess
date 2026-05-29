"""GCP Cloud Logging connector."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class GCPLoggingConnector(BaseConnector):

    async def poll(self, db: AsyncSession, since: Optional[datetime] = None) -> int:
        try:
            from google.cloud import logging as gcp_logging
        except ImportError:
            logger.warning("google-cloud-logging not installed — GCP connector disabled")
            return 0

        from app.services.event_store import store_event

        project_id = self.config.get("project_id", "")
        loop = asyncio.get_event_loop()

        start_time = since or (datetime.now(timezone.utc) - timedelta(minutes=10))
        filter_str = f'timestamp >= "{start_time.isoformat()}"'

        count = 0
        try:
            gcp_client = gcp_logging.Client(project=project_id)
            entries = await loop.run_in_executor(
                None,
                lambda: list(gcp_client.list_entries(filter_=filter_str, max_results=100)),
            )
            for entry in entries:
                try:
                    await store_event(db, {
                        "raw_log": str(entry.payload),
                        "log_source": "gcp_logging",
                        "log_type": "gcp",
                        "category": "system",
                        "severity": (entry.severity or "DEFAULT").lower(),
                        "timestamp": entry.timestamp,
                        "message": str(entry.payload)[:500],
                        "hostname": entry.resource.labels.get("instance_id") if entry.resource else None,
                    })
                    count += 1
                except Exception as exc:
                    logger.debug("GCP event storage failed: %s", exc)
        except Exception as exc:
            logger.error("GCP logging polling failed: %s", exc)
            raise

        return count
