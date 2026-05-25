"""
Events router: CRUD operations and real-time SSE streaming.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import SecurityEvent
from app.schemas.event import SecurityEventList, SecurityEventRead

router = APIRouter(prefix="/events", tags=["events"])
logger = logging.getLogger(__name__)

# SSE subscriber registry: maps request id → asyncio.Queue
_sse_subscribers: dict[str, asyncio.Queue] = {}


def publish_event_to_sse(event: SecurityEvent) -> None:
    """Push a newly ingested event to all SSE subscribers."""
    if not _sse_subscribers:
        return
    try:
        payload = {
            "id": str(event.id),
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "severity": event.severity,
            "log_type": event.log_type,
            "source_ip": event.source_ip,
            "hostname": event.hostname,
            "message": (event.message or "")[:200],
        }
        for q in list(_sse_subscribers.values()):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass
    except Exception as exc:
        logger.debug("SSE publish error: %s", exc)


@router.get(
    "",
    response_model=SecurityEventList,
    summary="List security events with filters",
)
async def list_events(
    start_time: Optional[datetime] = Query(None, description="Filter events after this UTC datetime"),
    end_time: Optional[datetime] = Query(None, description="Filter events before this UTC datetime"),
    severity: Optional[str] = Query(None, description="Filter by severity (low/medium/high/critical)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    log_type: Optional[str] = Query(None, description="Filter by log type"),
    log_source: Optional[str] = Query(None, description="Filter by log source"),
    source_ip: Optional[str] = Query(None, description="Filter by source IP"),
    hostname: Optional[str] = Query(None, description="Filter by hostname"),
    user: Optional[str] = Query(None, description="Filter by username"),
    action: Optional[str] = Query(None, description="Filter by action"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> SecurityEventList:
    query = select(SecurityEvent)
    count_query = select(func.count()).select_from(SecurityEvent)

    filters = []
    if start_time:
        filters.append(SecurityEvent.timestamp >= start_time)
    if end_time:
        filters.append(SecurityEvent.timestamp <= end_time)
    if severity:
        filters.append(SecurityEvent.severity == severity)
    if category:
        filters.append(SecurityEvent.category == category)
    if log_type:
        filters.append(SecurityEvent.log_type == log_type)
    if log_source:
        filters.append(SecurityEvent.log_source == log_source)
    if source_ip:
        filters.append(SecurityEvent.source_ip == source_ip)
    if hostname:
        filters.append(SecurityEvent.hostname.ilike(f"%{hostname}%"))
    if user:
        filters.append(SecurityEvent.user.ilike(f"%{user}%"))
    if action:
        filters.append(SecurityEvent.action == action)
    if tag:
        filters.append(SecurityEvent.tags.any(tag))  # type: ignore[attr-defined]

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.order_by(SecurityEvent.timestamp.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return SecurityEventList(total=total, page=page, page_size=page_size, items=items)  # type: ignore[arg-type]


@router.get(
    "/stream",
    summary="SSE endpoint for real-time event streaming",
    response_class=StreamingResponse,
)
async def stream_events(request: Request) -> StreamingResponse:
    """Server-Sent Events endpoint. Connect to receive live event notifications."""
    subscriber_id = str(id(request))
    queue: asyncio.Queue = asyncio.Queue(maxsize=500)
    _sse_subscribers[subscriber_id] = queue

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            yield "data: {\"type\":\"connected\",\"message\":\"SSE stream established\"}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=20.0)
                    data = json.dumps({"type": "event", "data": payload})
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _sse_subscribers.pop(subscriber_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/categories", summary="Distinct event categories")
async def get_categories(db: AsyncSession = Depends(get_db)) -> list[str]:
    result = await db.execute(
        select(SecurityEvent.category).distinct().where(SecurityEvent.category.isnot(None)).order_by(SecurityEvent.category)
    )
    return [row[0] for row in result.all()]


@router.get("/log-types", summary="Distinct log types")
async def get_log_types(db: AsyncSession = Depends(get_db)) -> list[str]:
    result = await db.execute(
        select(SecurityEvent.log_type).distinct().where(SecurityEvent.log_type.isnot(None)).order_by(SecurityEvent.log_type)
    )
    return [row[0] for row in result.all()]


@router.get(
    "/{event_id}",
    response_model=SecurityEventRead,
    summary="Get a single security event by ID",
)
async def get_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SecurityEvent:
    result = await db.execute(select(SecurityEvent).where(SecurityEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a security event",
)
async def delete_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(SecurityEvent).where(SecurityEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    await db.delete(event)
    await db.commit()
