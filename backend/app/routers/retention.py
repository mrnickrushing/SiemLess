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
    """
    Retrieve all retention policies.
    
    Returns:
        list: A list of policy dictionaries. Each dictionary contains the keys
            `id`, `name`, `log_type`, `hot_retention_days`, `cold_retention_days`,
            `archive_to_s3`, `s3_bucket`, `s3_prefix`, `enabled`, and `created_at`
            (ISO 8601 string).
    """
    result = await db.execute(select(RetentionPolicy))
    policies = result.scalars().all()
    return [_policy_to_dict(p) for p in policies]


@router.post("/policies", status_code=status.HTTP_201_CREATED, summary="Create retention policy")
async def create_policy(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    """
    Create a new retention policy from the provided payload and persist it to the database.
    
    Parameters:
        payload (dict): Payload containing policy fields. Supported keys:
            - name (str): Policy name. Defaults to "Default".
            - log_type (str): Type of logs the policy applies to.
            - hot_retention_days (int): Days to keep hot storage. Defaults to 90.
            - cold_retention_days (int): Days to keep cold storage. Defaults to 365.
            - archive_to_s3 (bool): Whether to archive to S3. Defaults to False.
            - s3_bucket (str): S3 bucket name for archives.
            - s3_prefix (str): S3 key prefix for archives.
            - enabled (bool): Whether the policy is active. Defaults to True.
    
    Returns:
        dict: Serialized representation of the created RetentionPolicy, including its generated `id` and ISO-formatted `created_at`.
    """
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
    """
    Update fields of an existing retention policy identified by `policy_id`.
    
    Updates only the provided fields from the payload and returns the serialized policy dictionary.
    
    Parameters:
        policy_id (str): ID of the policy to update.
        payload (dict): Mapping of fields to update. Supported keys: `name`, `log_type`, `hot_retention_days`, `cold_retention_days`, `archive_to_s3`, `s3_bucket`, `s3_prefix`, `enabled`.
        db (AsyncSession): Database session (injected).
    
    Returns:
        dict: Serialized retention policy with updated values.
    
    Raises:
        HTTPException: `404` if no policy with `policy_id` exists.
    """
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
    """
    Delete a retention policy by its identifier.
    
    Parameters:
        policy_id (str): Identifier of the retention policy to remove.
    
    Raises:
        HTTPException: `404` if no policy with the given `policy_id` exists.
    """
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
    """
    Retrieve aggregated retention statistics for the system.
    
    Returns:
        dict: Aggregated retention statistics keyed by metric name.
    """
    return await retention_service.get_stats(db)


@router.post("/run-now", status_code=status.HTTP_202_ACCEPTED, summary="Trigger retention cycle")
async def run_now(
    _username: str = Depends(get_current_user),
) -> dict:
    """
    Trigger a retention cycle to run asynchronously in the background.
    
    Returns:
        dict: A message confirming the retention cycle was triggered and will run in the background.
    """
    import asyncio
    from app.database import AsyncSessionLocal

    async def _run():
        """
        Run a manual retention cycle using a fresh async database session and log the outcome.
        
        This coroutine creates a new AsyncSession, invokes the retention service to execute one retention cycle, and logs the result for auditing/troubleshooting purposes.
        """
        async with AsyncSessionLocal() as db:
            result = await retention_service.run_retention_cycle(db)
            logger.info("Manual retention cycle: %s", result)

    asyncio.create_task(_run())
    return {"message": "Retention cycle triggered in background"}


def _policy_to_dict(p: RetentionPolicy) -> dict:
    """
    Serialize a RetentionPolicy model instance into a dictionary suitable for JSON responses.
    
    Parameters:
        p (RetentionPolicy): The RetentionPolicy ORM instance to serialize.
    
    Returns:
        dict: A dictionary containing the policy's fields:
            - id: Policy UUID or identifier.
            - name: Policy name.
            - log_type: Type/category of logs the policy applies to.
            - hot_retention_days: Days to keep data in hot storage.
            - cold_retention_days: Days to keep data in cold storage.
            - archive_to_s3: `True` if archived to S3, `False` otherwise.
            - s3_bucket: S3 bucket name used for archives, or `None`.
            - s3_prefix: S3 key prefix used for archives, or `None`.
            - enabled: `True` if the policy is active, `False` otherwise.
            - created_at: ISO 8601 string of the policy creation timestamp.
    """
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
