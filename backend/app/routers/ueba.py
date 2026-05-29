"""UEBA router."""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.ueba import UEBAAnomaly, UserBehaviorProfile

router = APIRouter(prefix="/ueba", tags=["ueba"])
logger = logging.getLogger(__name__)


@router.get("/profiles", summary="List user behavior profiles")
async def list_profiles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    from sqlalchemy import func

    total_result = await db.execute(select(func.count()).select_from(UserBehaviorProfile))
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    result = await db.execute(
        select(UserBehaviorProfile).offset(offset).limit(page_size)
    )
    profiles = result.scalars().all()
    return {
        "total": total,
        "items": [
            {
                "id": p.id,
                "username": p.username,
                "baseline_login_hours": p.baseline_login_hours,
                "baseline_source_ips": p.baseline_source_ips,
                "baseline_event_rate_per_hour": p.baseline_event_rate_per_hour,
                "baseline_computed_at": p.baseline_computed_at.isoformat() if p.baseline_computed_at else None,
                "last_evaluated_at": p.last_evaluated_at.isoformat() if p.last_evaluated_at else None,
            }
            for p in profiles
        ],
    }


@router.get("/profiles/{username}", summary="Get user behavior profile")
async def get_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    from fastapi import HTTPException

    result = await db.execute(
        select(UserBehaviorProfile).where(UserBehaviorProfile.username == username)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {
        "id": profile.id,
        "username": profile.username,
        "baseline_login_hours": profile.baseline_login_hours,
        "baseline_source_ips": profile.baseline_source_ips,
        "baseline_event_rate_per_hour": profile.baseline_event_rate_per_hour,
        "baseline_computed_at": profile.baseline_computed_at.isoformat() if profile.baseline_computed_at else None,
        "last_evaluated_at": profile.last_evaluated_at.isoformat() if profile.last_evaluated_at else None,
    }


@router.get("/anomalies", summary="List UEBA anomalies")
async def list_anomalies(
    username: Optional[str] = Query(None),
    anomaly_type: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    from sqlalchemy import func

    query = select(UEBAAnomaly)
    count_query = select(func.count()).select_from(UEBAAnomaly)

    if username:
        query = query.where(UEBAAnomaly.username == username)
        count_query = count_query.where(UEBAAnomaly.username == username)
    if anomaly_type:
        query = query.where(UEBAAnomaly.anomaly_type == anomaly_type)
        count_query = count_query.where(UEBAAnomaly.anomaly_type == anomaly_type)
    if min_score is not None:
        query = query.where(UEBAAnomaly.score >= min_score)
        count_query = count_query.where(UEBAAnomaly.score >= min_score)
    if start_time:
        query = query.where(UEBAAnomaly.created_at >= start_time)
        count_query = count_query.where(UEBAAnomaly.created_at >= start_time)
    if end_time:
        query = query.where(UEBAAnomaly.created_at <= end_time)
        count_query = count_query.where(UEBAAnomaly.created_at <= end_time)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    query = query.order_by(UEBAAnomaly.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    anomalies = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": a.id,
                "username": a.username,
                "event_id": a.event_id,
                "anomaly_type": a.anomaly_type,
                "score": a.score,
                "details": a.details,
                "alert_id": a.alert_id,
                "created_at": a.created_at.isoformat(),
            }
            for a in anomalies
        ],
    }


@router.post("/baseline/refresh", status_code=status.HTTP_202_ACCEPTED, summary="Trigger baseline refresh")
async def refresh_baselines(
    _username: str = Depends(get_current_user),
) -> dict:
    import asyncio
    from app.database import AsyncSessionLocal
    from app.services.baseline import baseline_service

    async def _run():
        async with AsyncSessionLocal() as db:
            count = await baseline_service.run_nightly_update(db)
            logger.info("Manual baseline refresh complete for %d users", count)

    asyncio.create_task(_run())
    return {"message": "Baseline refresh triggered in background"}
