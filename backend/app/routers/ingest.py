"""
Ingest router: accepts events via JSON, batch, raw log string, or file upload.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import SecurityEvent
from app.schemas.event import BatchIngest, RawLogIngest, SecurityEventCreate, SecurityEventRead
from app.services.event_store import store_event
from app.services.log_parser import LogParser

router = APIRouter(prefix="/ingest", tags=["ingest"])
logger = logging.getLogger(__name__)

_parser = LogParser()


# Keep a thin local alias for backward-compat in case anything imports _store_event
async def _store_event(db: AsyncSession, event_data: SecurityEventCreate, log_source: str = "api") -> SecurityEvent:
    """
    Store a normalized security event and return the persisted event record.
    
    Parameters:
        event_data (SecurityEventCreate): Normalized security event payload to persist.
        log_source (str): Identifier of the event's origin (defaults to "api").
    
    Returns:
        SecurityEvent: The persisted security event with database-populated fields (for example, identifiers and timestamps).
    """
    return await store_event(db, event_data, log_source)


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
