"""UEBA baseline computation service."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.event import SecurityEvent
from app.models.ueba import UserBehaviorProfile

logger = logging.getLogger(__name__)


class BaselineService:

    async def compute_baseline(
        self, db: AsyncSession, username: str
    ) -> UserBehaviorProfile:
        """Compute or update the behavioral baseline for a user over the last 30 days."""
        since = datetime.now(timezone.utc) - timedelta(days=30)

        result = await db.execute(
            select(SecurityEvent).where(
                SecurityEvent.user == username,
                SecurityEvent.timestamp >= since,
            )
        )
        events = result.scalars().all()

        if not events:
            # Upsert empty profile
            profile = await self._get_or_create_profile(db, username)
            profile.baseline_computed_at = datetime.now(timezone.utc)
            await db.flush()
            return profile

        # Compute baseline hours
        login_hours = sorted(set(e.timestamp.hour for e in events if e.timestamp))

        # Compute baseline source IPs
        source_ips = list({e.source_ip for e in events if e.source_ip})

        # Compute average events per hour
        total_hours = 30 * 24
        avg_rate = len(events) / total_hours

        profile = await self._get_or_create_profile(db, username)
        profile.baseline_login_hours = login_hours
        profile.baseline_source_ips = source_ips
        profile.baseline_event_rate_per_hour = avg_rate
        profile.baseline_computed_at = datetime.now(timezone.utc)
        await db.flush()
        return profile

    async def _get_or_create_profile(
        self, db: AsyncSession, username: str
    ) -> UserBehaviorProfile:
        result = await db.execute(
            select(UserBehaviorProfile).where(UserBehaviorProfile.username == username)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            import uuid
            profile = UserBehaviorProfile(
                id=str(uuid.uuid4()),
                username=username,
            )
            db.add(profile)
        return profile

    async def run_nightly_update(self, db: AsyncSession) -> int:
        """Recompute baselines for all active users. Returns count updated."""
        since = datetime.now(timezone.utc) - timedelta(days=30)
        distinct_users = await db.execute(
            select(SecurityEvent.user).where(
                SecurityEvent.timestamp >= since,
                SecurityEvent.user.isnot(None),
            ).distinct()
        )
        usernames = [row[0] for row in distinct_users if row[0]]
        for username in usernames:
            try:
                await self.compute_baseline(db, username)
            except Exception as exc:
                logger.warning("Baseline computation failed for %s: %s", username, exc)
        await db.commit()
        logger.info("Updated baselines for %d users", len(usernames))
        return len(usernames)

    async def start_baseline_loop(self) -> None:
        asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(86400)  # 24 hours
            try:
                async with AsyncSessionLocal() as db:
                    await self.run_nightly_update(db)
            except Exception as exc:
                logger.error("Nightly baseline update failed: %s", exc)


baseline_service = BaselineService()
