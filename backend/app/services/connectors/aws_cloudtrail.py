"""AWS CloudTrail connector."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class AWSCloudTrailConnector(BaseConnector):

    async def poll(self, db: AsyncSession, since: Optional[datetime] = None) -> int:
        try:
            import boto3
        except ImportError:
            logger.warning("boto3 not installed — AWS CloudTrail connector disabled")
            return 0

        from app.services.event_store import store_event

        loop = asyncio.get_event_loop()
        client = boto3.client(
            "cloudtrail",
            region_name=self.config.get("region", "us-east-1"),
            aws_access_key_id=self.config.get("access_key"),
            aws_secret_access_key=self.config.get("secret_key"),
        )

        start_time = since or (datetime.now(timezone.utc) - timedelta(minutes=10))

        try:
            response = await loop.run_in_executor(
                None,
                lambda: client.lookup_events(
                    StartTime=start_time,
                    MaxResults=100,
                ),
            )
        except Exception as exc:
            logger.error("CloudTrail lookup_events failed: %s", exc)
            raise

        events = response.get("Events", [])
        count = 0
        for evt in events:
            try:
                await store_event(db, {
                    "raw_log": str(evt),
                    "source": "aws_cloudtrail",
                    "log_source": "aws_cloudtrail",
                    "log_type": "cloudtrail",
                    "category": "system",
                    "severity": "low",
                    "timestamp": evt.get("EventTime"),
                    "hostname": evt.get("Username", "aws"),
                    "source_ip": evt.get("SourceIPAddress"),
                    "message": evt.get("EventName", "CloudTrail event"),
                    "user": evt.get("Username"),
                })
                count += 1
            except Exception as exc:
                logger.debug("CloudTrail event storage failed: %s", exc)

        return count
