"""Case management router."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.case import Case, CaseAlert, CaseArtifact, CaseComment, CaseEvent
from app.schemas.case import (
    CaseArtifactCreate,
    CaseArtifactRead,
    CaseCommentCreate,
    CaseCommentRead,
    CaseCreate,
    CaseList,
    CaseRead,
    CaseTimelineItem,
    CaseUpdate,
    LinkAlertsRequest,
    LinkEventsRequest,
)

router = APIRouter(prefix="/cases", tags=["cases"])
logger = logging.getLogger(__name__)


@router.get("", response_model=CaseList, summary="List cases")
async def list_cases(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> CaseList:
    query = select(Case)
    count_query = select(func.count()).select_from(Case)

    if status:
        query = query.where(Case.status == status)
        count_query = count_query.where(Case.status == status)
    if severity:
        query = query.where(Case.severity == severity)
        count_query = count_query.where(Case.severity == severity)
    if assigned_to:
        query = query.where(Case.assigned_to == assigned_to)
        count_query = count_query.where(Case.assigned_to == assigned_to)
    if search:
        like = f"%{search}%"
        query = query.where(Case.title.ilike(like))
        count_query = count_query.where(Case.title.ilike(like))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.order_by(Case.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    cases = result.scalars().all()

    return CaseList(
        total=total,
        page=page,
        page_size=page_size,
        items=[CaseRead.model_validate(c) for c in cases],
    )


@router.post("", response_model=CaseRead, status_code=status.HTTP_201_CREATED, summary="Create case")
async def create_case(
    payload: CaseCreate,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_user),
) -> CaseRead:
    case = Case(
        id=str(uuid.uuid4()),
        created_by=username,
        **payload.model_dump(),
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return CaseRead.model_validate(case)


@router.get("/{case_id}", response_model=dict, summary="Get case with linked data")
async def get_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    # Fetch linked alerts
    alerts_result = await db.execute(
        select(CaseAlert).where(CaseAlert.case_id == case_id)
    )
    linked_alerts = [{"alert_id": a.alert_id, "linked_at": a.linked_at.isoformat()} for a in alerts_result.scalars()]

    # Fetch linked events
    events_result = await db.execute(
        select(CaseEvent).where(CaseEvent.case_id == case_id)
    )
    linked_events = [{"event_id": e.event_id, "added_at": e.added_at.isoformat()} for e in events_result.scalars()]

    return {
        **CaseRead.model_validate(case).model_dump(),
        "linked_alerts": linked_alerts,
        "linked_events": linked_events,
    }


@router.patch("/{case_id}", response_model=CaseRead, summary="Update case")
async def update_case(
    case_id: str,
    payload: CaseUpdate,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> CaseRead:
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(case, field, value)

    if payload.status in ("resolved", "contained") and case.closed_at is None:
        case.closed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(case)
    return CaseRead.model_validate(case)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete case")
async def delete_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> None:
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    await db.delete(case)
    await db.commit()


@router.post("/{case_id}/events", status_code=status.HTTP_201_CREATED, summary="Link events to case")
async def link_events(
    case_id: str,
    payload: LinkEventsRequest,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_user),
) -> dict:
    result = await db.execute(select(Case).where(Case.id == case_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")

    linked = 0
    for event_id in payload.event_ids:
        existing = await db.execute(
            select(CaseEvent).where(CaseEvent.case_id == case_id, CaseEvent.event_id == event_id)
        )
        if existing.scalar_one_or_none() is None:
            db.add(CaseEvent(
                id=str(uuid.uuid4()),
                case_id=case_id,
                event_id=event_id,
                added_by=username,
            ))
            linked += 1
    await db.commit()
    return {"linked": linked}


@router.post("/{case_id}/alerts", status_code=status.HTTP_201_CREATED, summary="Link alerts to case")
async def link_alerts(
    case_id: str,
    payload: LinkAlertsRequest,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    result = await db.execute(select(Case).where(Case.id == case_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")

    linked = 0
    for alert_id in payload.alert_ids:
        existing = await db.execute(
            select(CaseAlert).where(CaseAlert.case_id == case_id, CaseAlert.alert_id == alert_id)
        )
        if existing.scalar_one_or_none() is None:
            db.add(CaseAlert(
                id=str(uuid.uuid4()),
                case_id=case_id,
                alert_id=alert_id,
            ))
            linked += 1
    await db.commit()
    return {"linked": linked}


@router.get("/{case_id}/comments", response_model=list[CaseCommentRead], summary="List comments")
async def list_comments(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> list[CaseCommentRead]:
    result = await db.execute(
        select(CaseComment).where(CaseComment.case_id == case_id).order_by(CaseComment.created_at)
    )
    return [CaseCommentRead.model_validate(c) for c in result.scalars()]


@router.post("/{case_id}/comments", response_model=CaseCommentRead, status_code=status.HTTP_201_CREATED)
async def add_comment(
    case_id: str,
    payload: CaseCommentCreate,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> CaseCommentRead:
    result = await db.execute(select(Case).where(Case.id == case_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")

    comment = CaseComment(id=str(uuid.uuid4()), case_id=case_id, **payload.model_dump())
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return CaseCommentRead.model_validate(comment)


@router.delete("/{case_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    case_id: str,
    comment_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(CaseComment).where(CaseComment.id == comment_id, CaseComment.case_id == case_id)
    )
    comment = result.scalar_one_or_none()
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    await db.delete(comment)
    await db.commit()


@router.get("/{case_id}/artifacts", response_model=list[CaseArtifactRead], summary="List artifacts")
async def list_artifacts(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> list[CaseArtifactRead]:
    result = await db.execute(
        select(CaseArtifact).where(CaseArtifact.case_id == case_id).order_by(CaseArtifact.created_at)
    )
    return [CaseArtifactRead.model_validate(a) for a in result.scalars()]


@router.post("/{case_id}/artifacts", response_model=CaseArtifactRead, status_code=status.HTTP_201_CREATED)
async def add_artifact(
    case_id: str,
    payload: CaseArtifactCreate,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> CaseArtifactRead:
    result = await db.execute(select(Case).where(Case.id == case_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")

    artifact = CaseArtifact(id=str(uuid.uuid4()), case_id=case_id, **payload.model_dump())
    db.add(artifact)
    await db.commit()
    await db.refresh(artifact)
    return CaseArtifactRead.model_validate(artifact)


@router.delete("/{case_id}/artifacts/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_artifact(
    case_id: str,
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(CaseArtifact).where(
            CaseArtifact.id == artifact_id, CaseArtifact.case_id == case_id
        )
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    await db.delete(artifact)
    await db.commit()


@router.get("/{case_id}/timeline", response_model=list[CaseTimelineItem], summary="Case timeline")
async def get_timeline(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> list[CaseTimelineItem]:
    result = await db.execute(select(Case).where(Case.id == case_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")

    items: list[CaseTimelineItem] = []

    # Linked events
    events_result = await db.execute(
        select(CaseEvent).where(CaseEvent.case_id == case_id)
    )
    for e in events_result.scalars():
        items.append(CaseTimelineItem(
            type="event",
            id=e.event_id,
            timestamp=e.added_at,
            summary=f"Event {e.event_id[:8]}… linked by {e.added_by}",
        ))

    # Linked alerts
    alerts_result = await db.execute(
        select(CaseAlert).where(CaseAlert.case_id == case_id)
    )
    for a in alerts_result.scalars():
        items.append(CaseTimelineItem(
            type="alert",
            id=a.alert_id,
            timestamp=a.linked_at,
            summary=f"Alert {a.alert_id[:8]}… linked",
        ))

    # Comments
    comments_result = await db.execute(
        select(CaseComment).where(CaseComment.case_id == case_id)
    )
    for c in comments_result.scalars():
        items.append(CaseTimelineItem(
            type="comment",
            id=c.id,
            timestamp=c.created_at,
            summary=f"{c.author}: {c.body[:80]}",
        ))

    items.sort(key=lambda x: x.timestamp)
    return items


@router.post("/{case_id}/create-ticket", summary="Create Jira/ServiceNow ticket from case")
async def create_ticket_from_case(
    case_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    """Create a ticket in Jira or ServiceNow for this case."""
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    integration_id = payload.get("integration_id")
    if not integration_id:
        raise HTTPException(status_code=400, detail="integration_id is required")

    try:
        from app.services.integrations.manager import integration_manager
        ticket_id = await integration_manager.create_ticket(
            db=db,
            integration_id=integration_id,
            title=f"[SiemLess Case] {case.title}",
            description=case.description or f"Case {case.id} - {case.severity} severity",
            priority=case.severity.capitalize(),
        )
        return {"ticket_id": ticket_id}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
