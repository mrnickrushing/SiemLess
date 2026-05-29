"""UEBA anomaly detection service."""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import SecurityEvent
from app.models.ueba import UEBAAnomaly, UserBehaviorProfile

logger = logging.getLogger(__name__)


class AnomalyDetector:

    async def evaluate_event(
        self, db: AsyncSession, event: SecurityEvent
    ) -> Optional[UEBAAnomaly]:
        if not event.user:
            return None

        profile = await self._get_profile(db, event.user)
        if not profile or not profile.baseline_computed_at:
            return None  # No baseline yet

        score = 0.0
        anomaly_type: Optional[str] = None
        details: dict = {}

        # Check 1: Unusual hour
        if event.timestamp:
            event_hour = event.timestamp.hour
            baseline_hours = profile.baseline_login_hours or []
            if baseline_hours and event_hour not in baseline_hours:
                score += 40.0
                anomaly_type = "unusual_hour"
                details["hour"] = event_hour
                details["baseline_hours"] = baseline_hours

        # Check 2: New source IP
        if event.source_ip and profile.baseline_source_ips:
            if event.source_ip not in profile.baseline_source_ips:
                score += 30.0
                anomaly_type = anomaly_type or "new_source_ip"
                details["source_ip"] = event.source_ip
                details["known_ips"] = profile.baseline_source_ips[:10]

        # Check 3: Impossible travel — same user from different IP in last 60 min
        if event.source_ip:
            recent_events = await self._get_recent_user_events(db, event.user, minutes=60)
            for prev in recent_events:
                if (
                    prev.source_ip
                    and prev.source_ip != event.source_ip
                    and str(prev.id) != str(event.id)
                ):
                    score += 60.0
                    anomaly_type = "impossible_travel"
                    details["ip_a"] = prev.source_ip
                    details["ip_b"] = event.source_ip
                    if event.timestamp and prev.timestamp:
                        details["time_delta_minutes"] = round(
                            abs((event.timestamp - prev.timestamp).total_seconds()) / 60, 1
                        )
                    break

        try:
            from app.config import settings
            threshold = getattr(settings, "UEBA_ANOMALY_THRESHOLD", 60.0)
        except Exception:
            threshold = 60.0

        if score < threshold:
            return None

        anomaly = UEBAAnomaly(
            id=str(uuid.uuid4()),
            username=event.user,
            event_id=str(event.id),
            anomaly_type=anomaly_type or "composite",
            score=score,
            details=details,
        )
        db.add(anomaly)

        # Update last_evaluated_at on profile
        if profile:
            profile.last_evaluated_at = datetime.now(timezone.utc)

        try:
            await db.commit()
        except Exception as exc:
            logger.warning("Failed to persist UEBA anomaly: %s", exc)
            await db.rollback()

        return anomaly

    async def _get_profile(
        self, db: AsyncSession, username: str
    ) -> Optional[UserBehaviorProfile]:
        result = await db.execute(
            select(UserBehaviorProfile).where(UserBehaviorProfile.username == username)
        )
        return result.scalar_one_or_none()

    async def _get_recent_user_events(
        self, db: AsyncSession, username: str, minutes: int = 60
    ) -> list[SecurityEvent]:
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        result = await db.execute(
            select(SecurityEvent).where(
                SecurityEvent.user == username,
                SecurityEvent.timestamp >= since,
            ).limit(20)
        )
        return list(result.scalars())


anomaly_detector = AnomalyDetector()
