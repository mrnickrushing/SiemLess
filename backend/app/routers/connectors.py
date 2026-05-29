"""Cloud connector router."""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.connector import CloudConnector

router = APIRouter(prefix="/connectors", tags=["connectors"])
logger = logging.getLogger(__name__)

CONNECTOR_TYPES = ["aws_cloudtrail", "azure_activity", "gcp_logging"]


@router.get("", summary="List cloud connectors")
async def list_connectors(
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> list:
    result = await db.execute(select(CloudConnector))
    connectors = result.scalars().all()
    return [_row_to_dict(c) for c in connectors]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create connector")
async def create_connector(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    connector_type = payload.get("connector_type", "")
    if connector_type not in CONNECTOR_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported type. Valid: {CONNECTOR_TYPES}")

    connector = CloudConnector(
        id=str(uuid.uuid4()),
        name=payload.get("name", connector_type),
        connector_type=connector_type,
        config=payload.get("config", {}),
        enabled=payload.get("enabled", True),
        poll_interval_seconds=payload.get("poll_interval_seconds", 300),
    )
    db.add(connector)
    await db.commit()
    await db.refresh(connector)
    return _row_to_dict(connector)


@router.get("/{connector_id}", summary="Get connector")
async def get_connector(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    result = await db.execute(select(CloudConnector).where(CloudConnector.id == connector_id))
    connector = result.scalar_one_or_none()
    if connector is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    return _row_to_dict(connector)


@router.patch("/{connector_id}", summary="Update connector")
async def update_connector(
    connector_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    result = await db.execute(select(CloudConnector).where(CloudConnector.id == connector_id))
    connector = result.scalar_one_or_none()
    if connector is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    for field in ("name", "config", "enabled", "poll_interval_seconds"):
        if field in payload:
            setattr(connector, field, payload[field])
    await db.commit()
    await db.refresh(connector)
    return _row_to_dict(connector)


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> None:
    result = await db.execute(select(CloudConnector).where(CloudConnector.id == connector_id))
    connector = result.scalar_one_or_none()
    if connector is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    await db.delete(connector)
    await db.commit()


@router.post("/{connector_id}/poll-now", summary="Trigger immediate poll")
async def poll_now(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    from app.services.connectors.manager import connector_manager
    try:
        result = await connector_manager.poll_connector(connector_id)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/{connector_id}/status", summary="Get connector status")
async def get_connector_status(
    connector_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    result = await db.execute(select(CloudConnector).where(CloudConnector.id == connector_id))
    connector = result.scalar_one_or_none()
    if connector is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    return {
        "id": connector.id,
        "name": connector.name,
        "enabled": connector.enabled,
        "last_polled_at": connector.last_polled_at.isoformat() if connector.last_polled_at else None,
        "last_error": connector.last_error,
        "events_ingested_total": connector.events_ingested_total,
    }


def _row_to_dict(c: CloudConnector) -> dict:
    # Mask config credentials
    safe_config = {}
    if c.config:
        for k, v in c.config.items():
            if any(s in k.lower() for s in ("key", "secret", "password", "token")):
                safe_config[k] = "****"
            else:
                safe_config[k] = v

    return {
        "id": c.id,
        "name": c.name,
        "connector_type": c.connector_type,
        "config": safe_config,
        "enabled": c.enabled,
        "last_polled_at": c.last_polled_at.isoformat() if c.last_polled_at else None,
        "last_error": c.last_error,
        "poll_interval_seconds": c.poll_interval_seconds,
        "events_ingested_total": c.events_ingested_total,
        "created_at": c.created_at.isoformat(),
    }
