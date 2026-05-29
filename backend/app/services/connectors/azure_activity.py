"""Azure Activity Log connector."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class AzureActivityConnector(BaseConnector):

    async def poll(self, db: AsyncSession, since: Optional[datetime] = None) -> int:
        """
        Poll Azure Activity Logs and persist retrieved entries into the event store.
        
        When Azure SDK packages are not available, the connector is disabled and the method returns 0.
        Parameters:
            db (AsyncSession): Database session used to persist events into the application event store.
            since (Optional[datetime]): Earliest event timestamp to fetch; when omitted, defaults to 10 minutes before the current UTC time.
        
        Returns:
            int: Number of activity log entries successfully stored.
        
        Raises:
            Exception: Propagates exceptions raised while fetching activity logs from Azure.
        """
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.monitor import MonitorManagementClient
        except ImportError:
            logger.warning("azure packages not installed — Azure connector disabled")
            return 0

        from app.services.event_store import store_event

        credential = ClientSecretCredential(
            tenant_id=self.config.get("tenant_id", ""),
            client_id=self.config.get("client_id", ""),
            client_secret=self.config.get("client_secret", ""),
        )
        subscription_id = self.config.get("subscription_id", "")
        monitor_client = MonitorManagementClient(credential, subscription_id)

        start_time = since or (datetime.now(timezone.utc) - timedelta(minutes=10))
        filter_str = (
            f"eventTimestamp ge '{start_time.isoformat()}'"
        )

        loop = asyncio.get_event_loop()
        count = 0
        try:
            activity_logs = await loop.run_in_executor(
                None,
                lambda: list(monitor_client.activity_logs.list(filter=filter_str)),
            )
            for log in activity_logs[:100]:
                try:
                    await store_event(db, {
                        "raw_log": str(log),
                        "log_source": "azure_activity",
                        "log_type": "azure",
                        "category": "system",
                        "severity": "low",
                        "timestamp": getattr(log, "event_timestamp", None),
                        "message": getattr(log, "operation_name", {}).get("value", "Azure activity"),
                        "user": getattr(getattr(log, "caller", None), "", None),
                        "source_ip": getattr(log, "http_request", {}).get("client_ip_address"),
                    })
                    count += 1
                except Exception as exc:
                    logger.debug("Azure event storage failed: %s", exc)
        except Exception as exc:
            logger.error("Azure activity log polling failed: %s", exc)
            raise

        return count
