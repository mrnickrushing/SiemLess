"""
Shared event storage utility — normalises, enriches, and persists a single
security event, then triggers the correlation engine.

Extracted from ingest.py so that multiple ingestion paths (HTTP API, Kafka,
syslog, cloud connectors) all share identical enrichment and correlation logic.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.event import SecurityEvent
from app.models.rule import CorrelationRule
from app.models.watchlist import WatchlistEntry
from app.services.alerting import alert_service
from app.services.correlation import correlation_engine
from app.services.threat_intel import threat_intel_service

logger = logging.getLogger(__name__)


async def _enrich_from_watchlist(db: AsyncSession, event_dict: dict) -> dict:
    """Add watchlist tags to events whose source_ip or user appears in the watchlist."""
    try:
        candidates: list[tuple[str, str]] = []
        if event_dict.get("source_ip"):
            candidates.append(("ip", event_dict["source_ip"]))
        if event_dict.get("user"):
            candidates.append(("user", event_dict["user"]))

        if not candidates:
            return event_dict

        conditions = [
            (WatchlistEntry.entry_type == t) & (WatchlistEntry.value == v)
            for t, v in candidates
        ]
        result = await db.execute(
            select(WatchlistEntry).where(or_(*conditions))
        )
        matches = result.scalars().all()
        if matches:
            existing_tags: list[str] = list(event_dict.get("tags") or [])
            new_tags = {"watchlist-match"}
            for m in matches:
                new_tags.add(f"watchlist:{m.entry_type}:{m.value}")
                for t in (m.tags or []):
                    new_tags.add(t)
            event_dict["tags"] = existing_tags + [t for t in new_tags if t not in existing_tags]
    except Exception as exc:
        logger.debug("Watchlist enrichment error: %s", exc)
    return event_dict


async def _safe_send_alert(alert, rule) -> None:
    """Wrapper so background alert tasks log exceptions instead of silently dying."""
    try:
        await alert_service.send_alert(alert, rule)
    except Exception as exc:
        logger.error("Background alert dispatch failed for alert %s: %s", alert.id, exc)


async def store_event(
    db: AsyncSession,
    event_data,
    log_source: str = "api",
) -> SecurityEvent:
    """
    Persist a single event and run correlation.

    ``event_data`` may be either a ``SecurityEventCreate`` Pydantic schema
    instance or a plain ``dict`` (for connectors / Kafka that build the dict
    themselves).
    """
    now = datetime.now(timezone.utc)

    # Accept both Pydantic models and raw dicts
    if hasattr(event_data, "model_dump"):
        event_dict = event_data.model_dump()
    else:
        event_dict = dict(event_data)

    event_dict = await threat_intel_service.enrich_event(db, event_dict)
    event_dict = await _enrich_from_watchlist(db, event_dict)

    # Normalise timestamp
    ts = event_dict.get("timestamp")
    if ts is None:
        ts = now
    elif isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            ts = now

    event = SecurityEvent(
        id=uuid.uuid4(),
        timestamp=ts,
        received_at=now,
        source_ip=event_dict.get("source_ip"),
        destination_ip=event_dict.get("destination_ip"),
        source_port=event_dict.get("source_port"),
        destination_port=event_dict.get("destination_port"),
        hostname=event_dict.get("hostname"),
        log_source=event_dict.get("log_source") or log_source,
        log_type=event_dict.get("log_type", "generic"),
        severity=event_dict.get("severity", "low"),
        category=event_dict.get("category", "system"),
        message=event_dict.get("message"),
        raw_log=event_dict.get("raw_log"),
        parsed_fields=event_dict.get("parsed_fields"),
        tags=event_dict.get("tags"),
        country=event_dict.get("country"),
        user=event_dict.get("user"),
        process=event_dict.get("process"),
        action=event_dict.get("action"),
    )

    # Compute and assign risk score
    try:
        from app.services.risk_aggregation import risk_aggregation_service
        event.risk_score = risk_aggregation_service.compute_event_risk_score(event)
    except Exception as exc:
        logger.debug("Risk score computation failed: %s", exc)

    # Compute and assign normalized fields
    try:
        from app.services.normalizer import normalize_to_ecs
        event.normalized_fields = normalize_to_ecs(event_dict, event.parsed_fields or {})
    except Exception as exc:
        logger.debug("ECS normalization failed: %s", exc)

    db.add(event)
    await db.flush()

    # Auto-populate asset inventory if enabled
    try:
        from app.config import settings as _settings
        if getattr(_settings, "ASSET_DISCOVERY_ENABLED", True):
            from app.services.asset_discovery import asset_discovery_service
            await asset_discovery_service.upsert_from_event(db, event)
    except Exception as exc:
        logger.debug("Asset discovery failed: %s", exc)

    # UEBA anomaly detection (non-blocking background task)
    try:
        from app.config import settings as _settings
        if getattr(_settings, "UEBA_ENABLED", False):
            from app.database import AsyncSessionLocal
            from app.services.anomaly_detector import anomaly_detector

            async def _run_ueba():
                async with AsyncSessionLocal() as _db:
                    await anomaly_detector.evaluate_event(_db, event)

            asyncio.create_task(_run_ueba())
    except Exception as exc:
        logger.debug("UEBA task creation failed: %s", exc)

    # Run correlation engine
    triggered_alerts = []
    try:
        triggered_alerts = await correlation_engine.evaluate_event(db, event)
    except Exception as exc:
        logger.warning("Correlation error for event %s: %s", event.id, exc)

    # Commit everything (event + any new/updated alerts) before dispatching
    # background tasks that open their own sessions to look up these rows.
    await db.commit()

    # Dispatch alert notifications and playbook evaluations post-commit so
    # the rows are visible to the new sessions opened by these tasks.
    for alert in triggered_alerts:
        try:
            rule_result = await db.execute(
                select(CorrelationRule).where(CorrelationRule.id == alert.rule_id)
            )
            rule = rule_result.scalar_one_or_none()
            asyncio.create_task(_safe_send_alert(alert, rule))
        except Exception as exc:
            logger.warning("Alert notification dispatch failed: %s", exc)

        try:
            from app.services.playbook_engine import playbook_engine

            alert_id = str(alert.id)

            async def _run_playbooks(aid: str = alert_id) -> None:
                async with AsyncSessionLocal() as _db:
                    alert_result = await _db.execute(
                        select(Alert).where(Alert.id == aid)
                    )
                    _alert = alert_result.scalar_one_or_none()
                    if _alert:
                        await playbook_engine.evaluate_alert(_db, _alert)

            asyncio.create_task(_run_playbooks())
        except Exception as exc:
            logger.debug("Playbook evaluation task creation failed: %s", exc)

    return event
