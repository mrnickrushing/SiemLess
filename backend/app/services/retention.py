"""Tiered log retention service with cold storage and optional S3 archival."""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.event import SecurityEvent
from app.models.retention import ColdEvent, RetentionPolicy

logger = logging.getLogger(__name__)


class RetentionService:

    async def run_retention_cycle(self, db: AsyncSession) -> dict:
        """Move hot events to cold storage per retention policies."""
        result = await db.execute(
            select(RetentionPolicy).where(RetentionPolicy.enabled == True)  # noqa: E712
        )
        policies = result.scalars().all()

        moved_total = 0
        archived_total = 0

        for policy in policies:
            cutoff = datetime.now(timezone.utc) - timedelta(days=policy.hot_retention_days)

            # Query events to move
            query = select(SecurityEvent).where(SecurityEvent.timestamp < cutoff)
            if policy.log_type:
                query = query.where(SecurityEvent.log_type == policy.log_type)
            query = query.limit(5000)  # Batch limit

            events_result = await db.execute(query)
            events = events_result.scalars().all()

            if not events:
                continue

            moved_ids = []
            for event in events:
                event_data = {
                    "id": str(event.id),
                    "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                    "source_ip": event.source_ip,
                    "destination_ip": event.destination_ip,
                    "hostname": event.hostname,
                    "log_source": event.log_source,
                    "log_type": event.log_type,
                    "severity": event.severity,
                    "category": event.category,
                    "message": event.message,
                    "raw_log": event.raw_log,
                    "parsed_fields": event.parsed_fields,
                    "tags": event.tags,
                    "user": event.user,
                    "action": event.action,
                }
                cold = ColdEvent(
                    id=str(uuid.uuid4()),
                    original_id=str(event.id),
                    event_data=event_data,
                )
                db.add(cold)
                moved_ids.append(str(event.id))

            # Delete from hot storage
            for event in events:
                await db.delete(event)

            await db.flush()
            moved_total += len(moved_ids)

            # Optionally archive to S3
            if policy.archive_to_s3 and policy.s3_bucket:
                try:
                    archived = await self._archive_to_s3(
                        events=[e for e in events],
                        bucket=policy.s3_bucket,
                        prefix=policy.s3_prefix or "siemless/cold/",
                    )
                    archived_total += archived
                except Exception as exc:
                    logger.warning("S3 archival failed: %s", exc)

        await db.commit()
        return {"moved_to_cold": moved_total, "archived_to_s3": archived_total}

    async def _archive_to_s3(
        self, events: list, bucket: str, prefix: str
    ) -> int:
        """Serialize events to JSONL and upload to S3."""
        try:
            import boto3
            import asyncio

            jsonl = "\n".join(
                json.dumps({
                    "id": str(e.id),
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "severity": e.severity,
                    "log_type": e.log_type,
                    "message": e.message,
                })
                for e in events
            )

            timestamp_str = datetime.now(timezone.utc).strftime("%Y/%m/%d/%H%M%S")
            key = f"{prefix}{timestamp_str}-{uuid.uuid4().hex[:8]}.jsonl"

            loop = asyncio.get_event_loop()
            s3 = boto3.client("s3")
            await loop.run_in_executor(
                None,
                lambda: s3.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=jsonl.encode("utf-8"),
                    ContentType="application/x-ndjson",
                ),
            )
            logger.info("Archived %d events to s3://%s/%s", len(events), bucket, key)
            return len(events)
        except Exception as exc:
            logger.warning("S3 upload failed: %s", exc)
            return 0

    async def start_retention_loop(self) -> None:
        asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(3600 * 6)  # Every 6 hours
            try:
                async with AsyncSessionLocal() as db:
                    result = await self.run_retention_cycle(db)
                    logger.info("Retention cycle complete: %s", result)
            except Exception as exc:
                logger.error("Retention cycle failed: %s", exc)

    async def get_stats(self, db: AsyncSession) -> dict:
        """Return counts and oldest event date."""
        from sqlalchemy import func
        hot_count_result = await db.execute(
            select(func.count()).select_from(SecurityEvent)
        )
        cold_count_result = await db.execute(
            select(func.count()).select_from(ColdEvent)
        )
        oldest_result = await db.execute(
            select(func.min(SecurityEvent.timestamp)).select_from(SecurityEvent)
        )
        return {
            "hot_count": hot_count_result.scalar() or 0,
            "cold_count": cold_count_result.scalar() or 0,
            "oldest_event": (lambda v: v.isoformat() if v else None)(oldest_result.scalar()),
        }


retention_service = RetentionService()
