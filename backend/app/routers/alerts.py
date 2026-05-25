"""
Alerts router: CRUD for alerts and related event lookup.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.alert import Alert
from app.models.event import SecurityEvent
from app.schemas.alert import AlertCreate, AlertList, AlertRead, AlertUpdate
from app.schemas.event import SecurityEventList

router = APIRouter(prefix="/alerts", tags=["alerts"])
logger = logging.getLogger(__name__)


@router.get("", response_model=AlertList, summary="List alerts with filters")
async def list_alerts(
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = Query(None),
    rule_id: Optional[UUID] = Query(None),
    assigned_to: Optional[str] = Query(None),
    mitre_tactic: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=settings.MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
) -> AlertList:
    query = select(Alert)
    count_query = select(func.count()).select_from(Alert)

    filters = []
    if status_filter:
        filters.append(Alert.status == status_filter)
    if severity:
        filters.append(Alert.severity == severity)
    if rule_id:
        filters.append(Alert.rule_id == rule_id)
    if assigned_to:
        filters.append(Alert.assigned_to == assigned_to)
    if mitre_tactic:
        filters.append(Alert.mitre_tactic.ilike(f"%{mitre_tactic}%"))
    if start_time:
        filters.append(Alert.created_at >= start_time)
    if end_time:
        filters.append(Alert.created_at <= end_time)

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.order_by(Alert.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return AlertList(total=total, page=page, page_size=page_size, items=items)  # type: ignore[arg-type]


@router.post(
    "",
    response_model=AlertRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new alert manually",
)
async def create_alert(
    alert_data: AlertCreate,
    db: AsyncSession = Depends(get_db),
) -> Alert:
    import uuid
    alert = Alert(
        id=uuid.uuid4(),
        title=alert_data.title,
        description=alert_data.description,
        severity=alert_data.severity,
        status=alert_data.status,
        rule_id=alert_data.rule_id,
        event_ids=alert_data.event_ids,
        source_ips=alert_data.source_ips,
        affected_users=alert_data.affected_users,
        mitre_tactic=alert_data.mitre_tactic,
        mitre_technique=alert_data.mitre_technique,
        notes=alert_data.notes,
        assigned_to=alert_data.assigned_to,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.get("/{alert_id}", response_model=AlertRead, summary="Get a single alert")
async def get_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Alert:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


@router.patch("/{alert_id}", response_model=AlertRead, summary="Update alert status, notes, or assignment")
async def update_alert(
    alert_id: UUID,
    update_data: AlertUpdate,
    db: AsyncSession = Depends(get_db),
) -> Alert:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    update_dict = update_data.model_dump(exclude_unset=True)

    for field, value in update_dict.items():
        setattr(alert, field, value)

    # Auto-set resolved_at when status becomes resolved or false_positive
    if update_data.status in ("resolved", "false_positive") and not alert.resolved_at:
        alert.resolved_at = datetime.now(timezone.utc)

    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.delete(
    "/{alert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an alert",
)
async def delete_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    await db.delete(alert)
    await db.commit()


@router.get(
    "/{alert_id}/events",
    response_model=SecurityEventList,
    summary="Get events related to an alert",
)
async def get_alert_events(
    alert_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=settings.MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
) -> SecurityEventList:
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    event_ids = alert.event_ids or []
    if not event_ids:
        return SecurityEventList(total=0, page=page, page_size=page_size, items=[])

    # Convert string UUIDs
    try:
        import uuid as uuid_mod
        parsed_ids = [uuid_mod.UUID(eid) if isinstance(eid, str) else eid for eid in event_ids]
    except ValueError:
        parsed_ids = []

    if not parsed_ids:
        return SecurityEventList(total=0, page=page, page_size=page_size, items=[])

    total = len(parsed_ids)
    offset = (page - 1) * page_size
    page_ids = parsed_ids[offset : offset + page_size]

    events_result = await db.execute(
        select(SecurityEvent).where(SecurityEvent.id.in_(page_ids))
    )
    items = list(events_result.scalars().all())

    return SecurityEventList(total=total, page=page, page_size=page_size, items=items)  # type: ignore[arg-type]
