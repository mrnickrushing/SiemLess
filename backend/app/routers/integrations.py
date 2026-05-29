"""Integration configuration router (Jira, ServiceNow)."""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.integration import IntegrationConfig
from app.services.integrations.manager import integration_manager

router = APIRouter(prefix="/integrations", tags=["integrations"])
logger = logging.getLogger(__name__)

INTEGRATION_TYPES = ["jira", "servicenow", "generic"]


@router.get("", summary="List integrations")
async def list_integrations(
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> list:
    result = await db.execute(select(IntegrationConfig))
    return [_integration_to_dict(i) for i in result.scalars()]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create integration")
async def create_integration(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    integration_type = payload.get("integration_type", "")
    if integration_type not in INTEGRATION_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported type. Valid: {INTEGRATION_TYPES}")

    integration = IntegrationConfig(
        id=str(uuid.uuid4()),
        name=payload.get("name", integration_type),
        integration_type=integration_type,
        config=payload.get("config", {}),
        enabled=payload.get("enabled", True),
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)
    return _integration_to_dict(integration)


@router.patch("/{integration_id}", summary="Update integration")
async def update_integration(
    integration_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    result = await db.execute(select(IntegrationConfig).where(IntegrationConfig.id == integration_id))
    integration = result.scalar_one_or_none()
    if integration is None:
        raise HTTPException(status_code=404, detail="Integration not found")
    for field in ("name", "config", "enabled"):
        if field in payload:
            setattr(integration, field, payload[field])
    await db.commit()
    await db.refresh(integration)
    return _integration_to_dict(integration)


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> None:
    result = await db.execute(select(IntegrationConfig).where(IntegrationConfig.id == integration_id))
    integration = result.scalar_one_or_none()
    if integration is None:
        raise HTTPException(status_code=404, detail="Integration not found")
    await db.delete(integration)
    await db.commit()


@router.post("/{integration_id}/test", summary="Test integration connection")
async def test_connection(
    integration_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    try:
        success = await integration_manager.test_connection(db, integration_id)
        return {"success": success}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{integration_id}/create-ticket", summary="Create ticket from alert")
async def create_ticket(
    integration_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    alert_id = payload.get("alert_id")
    title = payload.get("title", f"SiemLess Alert {alert_id}")
    description = payload.get("description", "")
    priority = payload.get("priority", "Medium")

    try:
        ticket_id = await integration_manager.create_ticket(
            db=db,
            integration_id=integration_id,
            title=title,
            description=description,
            priority=priority,
        )
        return {"ticket_id": ticket_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


def _integration_to_dict(i: IntegrationConfig) -> dict:
    # Mask sensitive config fields
    safe_config = {}
    if i.config:
        for k, v in i.config.items():
            if any(s in k.lower() for s in ("key", "secret", "password", "token")):
                safe_config[k] = "****"
            else:
                safe_config[k] = v
    return {
        "id": i.id,
        "name": i.name,
        "integration_type": i.integration_type,
        "config": safe_config,
        "enabled": i.enabled,
        "created_at": i.created_at.isoformat(),
    }
