"""
Ingest router: accepts events via JSON, batch, raw log string, or file upload.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select

from app.database import get_db
from app.models.event import SecurityEvent
from app.models.rule import CorrelationRule
from app.models.watchlist import WatchlistEntry
from app.schemas.event import BatchIngest, RawLogIngest, SecurityEventCreate, SecurityEventRead
from app.services.alerting import alert_service
from app.services.correlation import correlation_engine
from app.services.log_parser import LogParser
from app.services.threat_intel import threat_intel_service

router = APIRouter(prefix="/ingest", tags=["ingest"])
logger = logging.getLogger(__name__)

_parser = LogParser()


async def _safe_send_alert(alert, rule) -> None:
    """Wrapper so background alert tasks log exceptions instead of silently dying."""
    try:
        await alert_service.send_alert(alert, rule)
    except Exception as exc:
        logger.error("Background alert dispatch failed for alert %s: %s", alert.id, exc)


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


async def _store_event(db: AsyncSession, event_data: SecurityEventCreate, log_source: str = "api") -> SecurityEvent:
    """Persist a single event and run correlation."""
    now = datetime.now(timezone.utc)

    event_dict = event_data.model_dump()
    event_dict = await threat_intel_service.enrich_event(db, event_dict)
    event_dict = await _enrich_from_watchlist(db, event_dict)

    event = SecurityEvent(
        id=uuid.uuid4(),
        timestamp=event_dict.get("timestamp") or now,
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

    db.add(event)
    await db.flush()

    # Run correlation engine; dispatch alert notifications as a background task
    # using _safe_send_alert so any notification failures are logged, not swallowed.
    # Alert notification tasks fire after the outer db.commit() in the calling route,
    # which is the correct ordering — events are visible in the DB before notifications fire.
    try:
        alerts = await correlation_engine.evaluate_event(db, event)
        for alert in alerts:
            rule_result = await db.execute(
                select(CorrelationRule).where(CorrelationRule.id == alert.rule_id)
            )
            rule = rule_result.scalar_one_or_none()
            asyncio.create_task(_safe_send_alert(alert, rule))
    except Exception as exc:
        logger.warning("Correlation error for event %s: %s", event.id, exc)

    return event


@router.post(
    "/event",
    response_model=SecurityEventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a single structured event",
)
async def ingest_event(
    event_data: SecurityEventCreate,
    db: AsyncSession = Depends(get_db),
) -> SecurityEvent:
    """Ingest a single pre-parsed security event."""
    event = await _store_event(db, event_data)
    await db.commit()
    await db.refresh(event)
    return event


@router.post(
    "/batch",
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a batch of structured events (max 1000)",
)
async def ingest_batch(
    batch: BatchIngest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Ingest up to 1000 security events in a single request."""
    if len(batch.events) > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum batch size is 1000 events",
        )

    stored = 0
    errors = 0
    for event_data in batch.events:
        try:
            await _store_event(db, event_data)
            stored += 1
        except Exception as exc:
            logger.warning("Failed to store batch event: %s", exc)
            errors += 1

    await db.commit()
    return {"stored": stored, "errors": errors, "total": len(batch.events)}


@router.post(
    "/raw",
    response_model=SecurityEventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a raw log line",
)
async def ingest_raw(
    payload: RawLogIngest,
    db: AsyncSession = Depends(get_db),
) -> SecurityEvent:
    """
    Ingest a raw log string. The parser auto-detects format (syslog, JSON, CEF)
    and normalises it before storage.
    """
    parsed = _parser.parse(payload.raw_log, log_source=payload.log_source)
    if payload.hint and not parsed.get("log_type"):
        parsed["log_type"] = payload.hint

    event_schema = _parser.normalize(parsed)
    event = await _store_event(db, event_schema, log_source=payload.log_source)
    await db.commit()
    await db.refresh(event)
    return event


@router.post(
    "/file",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a log file for bulk ingestion",
)
async def ingest_file(
    file: UploadFile = File(...),
    log_source: str = Form(default="file"),
    log_type_hint: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Upload a plain-text log file (one log entry per line).
    Lines are parsed and stored in batches of 200.
    The response always reflects actual lines processed at the time of return;
    if the request is cancelled mid-flight the caller will receive an incomplete
    response — this is surfaced via the 'stored' + 'errors' counts.
    """
    if file.content_type and not (
        file.content_type.startswith("text/")
        or file.content_type in ("application/octet-stream", "application/json")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only text files are supported",
        )

    MAX_SIZE = 50 * 1024 * 1024  # 50 MB
    content = await file.read(MAX_SIZE + 1)
    if len(content) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 50 MB limit",
        )

    lines = content.decode("utf-8", errors="replace").splitlines()
    stored = 0
    errors = 0
    batch_size = 200

    for i in range(0, len(lines), batch_size):
        chunk = lines[i : i + batch_size]
        for line in chunk:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = _parser.parse(line, log_source=log_source)
                if log_type_hint and not parsed.get("log_type"):
                    parsed["log_type"] = log_type_hint
                event_schema = _parser.normalize(parsed)
                await _store_event(db, event_schema, log_source=log_source)
                stored += 1
            except Exception as exc:
                logger.debug("Error parsing line: %s | %s", line[:80], exc)
                errors += 1

        # Commit each batch. Alert notification tasks (created inside _store_event
        # via asyncio.create_task) may begin executing after this commit, which is
        # the correct ordering — events are visible in the DB before notifications fire.
        await db.commit()

    return {
        "filename": file.filename,
        "total_lines": len(lines),
        "stored": stored,
        "errors": errors,
    }
