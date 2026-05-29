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
    """
    Retrieve a paginated list of cases applying optional filters.
    
    Optional filters can be provided to narrow results by `status`, `severity`, `assigned_to`, or a case title partial match via `search`. Results are ordered by `created_at` descending and paginated using `page` and `page_size`.
    
    Parameters:
        status (Optional[str]): Filter cases by exact status.
        severity (Optional[str]): Filter cases by exact severity.
        assigned_to (Optional[str]): Filter cases assigned to the given username or identifier.
        search (Optional[str]): Case title partial match (case-insensitive).
        page (int): 1-based page number.
        page_size (int): Number of items per page (max 200).
    
    Returns:
        CaseList: An object containing `total` matching cases, the `page` and `page_size`, and `items` as a list of `CaseRead` entries for the current page.
    """
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
    """
    Create a new case from the provided payload and return the saved case.
    
    Parameters:
        payload (CaseCreate): Data used to populate the new case.
    
    Returns:
        case (CaseRead): The created case serialized as a CaseRead model.
    """
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
    """
    Retrieve a case by its ID and return the case data along with linked alerts and events.
    
    Parameters:
        case_id (str): UUID of the case to fetch.
    
    Returns:
        dict: A mapping containing the case fields plus:
            - "linked_alerts": list[dict] each with keys:
                - "alert_id" (str): linked alert ID
                - "linked_at" (str): ISO 8601 timestamp when the alert was linked
            - "linked_events": list[dict] each with keys:
                - "event_id" (str): linked event ID
                - "added_at" (str): ISO 8601 timestamp when the event was added
    
    Raises:
        HTTPException: 404 if no case with the given `case_id` exists.
    """
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
    """
    Update specified fields of an existing case and return the updated case representation.
    
    Parameters:
        case_id (str): ID of the case to update.
        payload (CaseUpdate): Fields to apply to the case; fields with value `None` are ignored. If `status` becomes `"resolved"` or `"contained"` and the case has no `closed_at`, `closed_at` will be set to the current UTC time.
    
    Returns:
        CaseRead: The updated case data.
    
    Raises:
        HTTPException: 404 if the case with `case_id` does not exist.
    """
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
    """
    Delete a case by its identifier.
    
    Parameters:
        case_id (str): The UUID string of the case to remove.
    
    Raises:
        HTTPException: 404 if the case does not exist.
    """
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
    """
    Link multiple event IDs to a case by creating new CaseEvent records for events not already linked.
    
    Parameters:
        case_id (str): Identifier of the case to link events to.
        payload (LinkEventsRequest): Request payload containing `event_ids`, the list of event IDs to link.
    
    Returns:
        dict: A dictionary `{"linked": n}` where `n` is the number of events newly linked to the case.
    
    Raises:
        HTTPException: 404 if the specified case does not exist.
    """
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
    """
    Link multiple alerts to a case by creating CaseAlert records for any alerts not already linked.
    
    Parameters:
        case_id (str): ID of the case to link alerts to.
        payload (LinkAlertsRequest): Request containing `alert_ids` to link.
    
    Returns:
        dict: A mapping with key `"linked"` whose value is the number of alerts newly linked.
    
    Raises:
        HTTPException: 404 if no case exists with the provided `case_id`.
    """
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
    """
    Retrieve all comments for a case ordered by creation time.
    
    Parameters:
        case_id (str): The ID of the case whose comments should be returned.
    
    Returns:
        comments (list[CaseCommentRead]): A list of `CaseCommentRead` objects ordered by `created_at`.
    """
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
    """
    Add a new comment to a case.
    
    Creates and persists a CaseComment for the case identified by `case_id`.
    
    Parameters:
        case_id (str): ID of the case to attach the comment to.
        payload (CaseCommentCreate): Comment fields to store on the new comment.
    
    Returns:
        CaseCommentRead: The created comment record.
    
    Raises:
        HTTPException: If no case exists with the given `case_id` (status 404).
    """
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
    """
    Delete the comment with the given comment_id from the specified case.
    
    Raises:
        HTTPException: 404 with detail "Comment not found" if the comment does not exist for the case.
    """
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
    """
    Retrieve all artifacts for a case ordered by creation time.
    
    Returns:
        artifacts (list[CaseArtifactRead]): List of artifacts associated with the case, ordered by `created_at` (earliest first).
    """
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
    """
    Create a new artifact for the specified case.
    
    Verifies the case exists, persists a new CaseArtifact using values from `payload`, and returns the created artifact.
    
    Parameters:
    	case_id (str): Identifier of the case to attach the artifact to.
    	payload (CaseArtifactCreate): Artifact data to persist.
    
    Returns:
    	CaseArtifactRead: The newly created artifact.
    """
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
    """
    Delete an artifact belonging to a case.
    
    Parameters:
        case_id (str): ID of the parent case.
        artifact_id (str): ID of the artifact to delete.
    
    Raises:
        HTTPException: 404 if the artifact does not exist.
    """
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
    """
    Assembles chronological timeline items (events, alerts, and comments) for a case.
    
    Each timeline item contains `type`, `id`, `timestamp`, and a concise `summary`.
    Parameters:
        case_id (str): ID of the case to build the timeline for.
    
    Returns:
        list[CaseTimelineItem]: Timeline items sorted by `timestamp` in ascending order.
    
    Raises:
        HTTPException: 404 if the specified case does not exist.
    """
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
    """
    Create an external ticket for the case using the specified integration.
    
    Parameters:
        payload (dict): Request data; must include `"integration_id"` (the ID of the target integration).
    
    Returns:
        dict: A mapping with key `"ticket_id"` containing the created ticket's identifier.
    
    Raises:
        HTTPException: 404 if the case is not found.
        HTTPException: 400 if `integration_id` is missing or falsy in `payload`.
        HTTPException: 502 if the integration manager fails to create the ticket (detail contains the error).
    """
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
