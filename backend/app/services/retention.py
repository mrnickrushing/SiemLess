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
        """
        Apply enabled retention policies to move aged SecurityEvent rows into ColdEvent records and optionally archive them to S3.
        
        Processes each enabled RetentionPolicy by selecting hot events older than the policy's hot_retention_days (batch-limited), creating corresponding ColdEvent entries, deleting the original hot events, and, if configured, uploading the moved events to S3. S3 failures are logged and do not abort the overall cycle. The function commits the transaction before returning aggregated counts.
        
        Parameters:
            db (AsyncSession): Active database session used for selecting, inserting, deleting, and committing changes.
        
        Returns:
            dict: Summary counts with keys:
                - "moved_to_cold": number of events moved into cold storage.
                - "archived_to_s3": number of events successfully archived to S3.
        """
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
        """
        Serialize a list of security events into NDJSON and upload the payload to the specified S3 bucket.
        
        Parameters:
            events (list): Iterable of event objects to archive; each object must expose `id`, `timestamp`, `severity`, `log_type`, and `message` attributes. Records are written one JSON object per line.
            bucket (str): Target S3 bucket name.
            prefix (str): Key prefix to prepend to the generated object key; a timestamp and short UUID are appended to form the final key.
        
        Returns:
            int: Number of events uploaded on success, or `0` if the upload failed.
        """
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
        """
        Start the background retention loop.
        
        Schedules the service's retention loop (self._loop) as an asyncio background task so retention cycles run periodically without blocking the caller.
        """
        asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        """
        Continuously runs retention cycles on a six-hour schedule.
        
        Sleeps six hours between iterations, opens a new async database session for each cycle, invokes run_retention_cycle(db), and logs completion. Any exception raised during a cycle is logged and the loop continues.
        """
        while True:
            await asyncio.sleep(3600 * 6)  # Every 6 hours
            try:
                async with AsyncSessionLocal() as db:
                    result = await self.run_retention_cycle(db)
                    logger.info("Retention cycle complete: %s", result)
            except Exception as exc:
                logger.error("Retention cycle failed: %s", exc)

    async def get_stats(self, db: AsyncSession) -> dict:
        """
        Return counts of hot and cold events and the timestamp of the oldest hot event.
        
        Returns:
            dict: {
                "hot_count": int - number of SecurityEvent rows (0 if none),
                "cold_count": int - number of ColdEvent rows (0 if none),
                "oldest_event": str | None - ISO 8601 string of the oldest SecurityEvent.timestamp, or None if no hot events
            }
        """
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
