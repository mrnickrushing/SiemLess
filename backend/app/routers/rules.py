"""
Rules router: CRUD for correlation rules and rule testing.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import SecurityEvent
from app.models.rule import CorrelationRule
from app.schemas.rule import (
    CorrelationRuleCreate,
    CorrelationRuleList,
    CorrelationRuleRead,
    CorrelationRuleUpdate,
)
from app.services.correlation import correlation_engine

router = APIRouter(prefix="/rules", tags=["rules"])
logger = logging.getLogger(__name__)


@router.get("", response_model=CorrelationRuleList, summary="List all correlation rules")
async def list_rules(
    enabled: Optional[bool] = Query(None),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> CorrelationRuleList:
    query = select(CorrelationRule)
    filters = []
    if enabled is not None:
        filters.append(CorrelationRule.enabled == enabled)
    if category:
        filters.append(CorrelationRule.category == category)
    if severity:
        filters.append(CorrelationRule.severity == severity)
    if filters:
        query = query.where(*filters)

    query = query.order_by(CorrelationRule.created_at.desc())
    result = await db.execute(query)
    items = list(result.scalars().all())

    total_result = await db.execute(select(func.count()).select_from(CorrelationRule))
    total = total_result.scalar() or 0

    return CorrelationRuleList(total=total, items=items)  # type: ignore[arg-type]


@router.post(
    "",
    response_model=CorrelationRuleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new correlation rule",
)
async def create_rule(
    rule_data: CorrelationRuleCreate,
    db: AsyncSession = Depends(get_db),
) -> CorrelationRule:
    import uuid

    # Check name uniqueness
    existing = await db.execute(
        select(CorrelationRule).where(CorrelationRule.name == rule_data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Rule with name '{rule_data.name}' already exists",
        )

    rule = CorrelationRule(id=uuid.uuid4(), **rule_data.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    # Reload rules in correlation engine
    await correlation_engine.load_rules(db)

    return rule


@router.get("/{rule_id}", response_model=CorrelationRuleRead, summary="Get a single rule")
async def get_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> CorrelationRule:
    result = await db.execute(select(CorrelationRule).where(CorrelationRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    return rule


@router.put("/{rule_id}", response_model=CorrelationRuleRead, summary="Update a rule")
async def update_rule(
    rule_id: UUID,
    update_data: CorrelationRuleUpdate,
    db: AsyncSession = Depends(get_db),
) -> CorrelationRule:
    result = await db.execute(select(CorrelationRule).where(CorrelationRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    # Check new name uniqueness if changing name
    update_dict = update_data.model_dump(exclude_unset=True)
    if "name" in update_dict and update_dict["name"] != rule.name:
        existing = await db.execute(
            select(CorrelationRule).where(CorrelationRule.name == update_dict["name"])
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Rule with name '{update_dict['name']}' already exists",
            )

    for field, value in update_dict.items():
        setattr(rule, field, value)

    rule.updated_at = datetime.now(timezone.utc)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    # Reload rules in correlation engine
    await correlation_engine.load_rules(db)

    return rule


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a rule",
)
async def delete_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(CorrelationRule).where(CorrelationRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
    await correlation_engine.load_rules(db)


@router.patch("/{rule_id}/toggle", response_model=CorrelationRuleRead, summary="Enable or disable a rule")
async def toggle_rule(
    rule_id: UUID,
    body: CorrelationRuleUpdate,
    db: AsyncSession = Depends(get_db),
) -> CorrelationRule:
    result = await db.execute(select(CorrelationRule).where(CorrelationRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    if body.enabled is not None:
        rule.enabled = body.enabled
        rule.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(rule)
    await correlation_engine.load_rules(db)
    return rule


@router.post(
    "/{rule_id}/test",
    summary="Test a rule against recent events",
)
async def test_rule(
    rule_id: UUID,
    hours: int = Query(1, ge=1, le=168, description="How many hours of history to test against"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Test a rule against the last N hours of events.
    Returns which events would have matched and the threshold evaluation.
    """
    result = await db.execute(select(CorrelationRule).where(CorrelationRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    events_result = await db.execute(
        select(SecurityEvent)
        .where(SecurityEvent.timestamp >= since)
        .order_by(SecurityEvent.timestamp.desc())
        .limit(5000)
    )
    events = list(events_result.scalars().all())

    matched_events = []
    for event in events:
        if correlation_engine._matches_condition(event, rule.condition):
            matched_events.append({
                "id": str(event.id),
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "source_ip": event.source_ip,
                "severity": event.severity,
                "log_type": event.log_type,
                "message": (event.message or "")[:200],
            })

    # Group by group_by field
    group_by = rule.condition.get("group_by", "source_ip")
    groups: dict[str, list] = {}
    for ev_dict in matched_events:
        gval = ev_dict.get(group_by) or "__all__"
        groups.setdefault(str(gval), []).append(ev_dict)

    would_trigger = {
        k: {"count": len(v), "would_alert": len(v) >= rule.threshold, "events": v[:5]}
        for k, v in groups.items()
    }

    return {
        "rule_id": str(rule_id),
        "rule_name": rule.name,
        "hours_tested": hours,
        "total_events_scanned": len(events),
        "matching_events": len(matched_events),
        "threshold": rule.threshold,
        "time_window": rule.time_window,
        "group_by": group_by,
        "groups": would_trigger,
        "alert_would_fire": any(g["would_alert"] for g in would_trigger.values()),
    }
