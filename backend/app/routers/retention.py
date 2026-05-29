"""Retention policy router."""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.retention import RetentionPolicy
from app.services.retention import retention_service

router = APIRouter(prefix="/retention", tags=["retention"])
logger = logging.getLogger(__name__)


@router.get("/policies", summary="List retention policies")
async def list_policies(
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> list:
    result = await db.execute(select(RetentionPolicy))
    policies = result.scalars().all()
    return [_policy_to_dict(p) for p in policies]


@router.post("/policies", status_code=status.HTTP_201_CREATED, summary="Create retention policy")
async def create_policy(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    policy = RetentionPolicy(
        id=str(uuid.uuid4()),
        name=payload.get("name", "Default"),
        log_type=payload.get("log_type"),
        hot_retention_days=payload.get("hot_retention_days", 90),
        cold_retention_days=payload.get("cold_retention_days", 365),
        archive_to_s3=payload.get("archive_to_s3", False),
        s3_bucket=payload.get("s3_bucket"),
        s3_prefix=payload.get("s3_prefix"),
        enabled=payload.get("enabled", True),
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return _policy_to_dict(policy)


@router.patch("/policies/{policy_id}", summary="Update retention policy")
async def update_policy(
    policy_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    result = await db.execute(select(RetentionPolicy).where(RetentionPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    for field in ("name", "log_type", "hot_retention_days", "cold_retention_days",
                  "archive_to_s3", "s3_bucket", "s3_prefix", "enabled"):
        if field in payload:
            setattr(policy, field, payload[field])
    await db.commit()
    await db.refresh(policy)
    return _policy_to_dict(policy)


@router.delete("/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> None:
    result = await db.execute(select(RetentionPolicy).where(RetentionPolicy.id == policy_id))
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    await db.delete(policy)
    await db.commit()


@router.get("/stats", summary="Hot/cold event counts")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    return await retention_service.get_stats(db)


@router.post("/run-now", status_code=status.HTTP_202_ACCEPTED, summary="Trigger retention cycle")
async def run_now(
    _username: str = Depends(get_current_user),
) -> dict:
    import asyncio
    from app.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as db:
            result = await retention_service.run_retention_cycle(db)
            logger.info("Manual retention cycle: %s", result)

    asyncio.create_task(_run())
    return {"message": "Retention cycle triggered in background"}


def _policy_to_dict(p: RetentionPolicy) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "log_type": p.log_type,
        "hot_retention_days": p.hot_retention_days,
        "cold_retention_days": p.cold_retention_days,
        "archive_to_s3": p.archive_to_s3,
        "s3_bucket": p.s3_bucket,
        "s3_prefix": p.s3_prefix,
        "enabled": p.enabled,
        "created_at": p.created_at.isoformat(),
    }
