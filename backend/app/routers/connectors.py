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
    """
    List all cloud connectors.
    
    Each returned connector dictionary includes keys: `id`, `name`, `connector_type`, `config`
    (with sensitive values masked), `enabled`, `last_polled_at`, `last_error`,
    `poll_interval_seconds`, `events_ingested_total`, and `created_at`.
    
    Returns:
        connectors (list[dict]): List of connector dictionaries where values for config keys
        containing "key", "secret", "password", or "token" (case-insensitive) are replaced with `"****"`.
    """
    result = await db.execute(select(CloudConnector))
    connectors = result.scalars().all()
    return [_row_to_dict(c) for c in connectors]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create connector")
async def create_connector(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    """
    Create a new cloud connector record after validating its type and return its public representation.
    
    Parameters:
        payload (dict): Input fields for the connector. Expected keys:
            - "connector_type" (str): Required; must be one of CONNECTOR_TYPES.
            - "name" (str): Optional; defaults to the connector_type.
            - "config" (dict): Optional configuration object.
            - "enabled" (bool): Optional; defaults to True.
            - "poll_interval_seconds" (int): Optional; defaults to 300.
    
    Returns:
        dict: Public representation of the created connector with sensitive configuration values masked.
    
    Raises:
        HTTPException: 400 if "connector_type" is missing or not one of CONNECTOR_TYPES.
    """
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
    """
    Retrieve a cloud connector by its ID.
    
    Returns:
        dict: A dictionary representation of the connector with sensitive config values masked.
    
    Raises:
        HTTPException: 404 if the connector with the given ID does not exist.
    """
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
    """
    Update allowed fields of an existing cloud connector and return its updated representation.
    
    Parameters:
        payload (dict): Dictionary containing one or more of the updatable fields:
            - "name" (str)
            - "config" (dict)
            - "enabled" (bool)
            - "poll_interval_seconds" (int)
    
    Returns:
        dict: The updated connector object suitable for API responses, containing
        keys such as `id`, `name`, `connector_type`, `config` (sensitive values masked),
        `enabled`, `last_polled_at` (ISO string or `None`), `last_error`,
        `poll_interval_seconds`, `events_ingested_total`, and `created_at` (ISO string).
    
    Raises:
        HTTPException: 404 if no connector with the given `connector_id` exists.
    """
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
    """
    Delete a cloud connector by its identifier.
    
    Parameters:
        connector_id (str): The UUID of the connector to remove.
    
    Raises:
        HTTPException: 404 if no connector with the given id exists.
    """
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
    """
    Trigger an immediate poll for the specified connector and return the poll result.
    
    Parameters:
        connector_id (str): ID of the connector to poll.
    
    Returns:
        dict: Result produced by the connector polling operation.
    
    Raises:
        HTTPException: 404 if the connector is not found or invalid.
        HTTPException: 502 for other polling failures.
    """
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
    """
    Return a status summary for the specified cloud connector.
    
    Parameters:
        connector_id (str): UUID string of the connector to fetch.
    
    Returns:
        status (dict): Mapping with keys:
            - `id`: connector id string
            - `name`: connector name
            - `enabled`: whether the connector is enabled
            - `last_polled_at`: ISO 8601 timestamp string of last poll or `None`
            - `last_error`: last error message or `None`
            - `events_ingested_total`: total number of events ingested
    
    Raises:
        HTTPException: 404 if the connector does not exist.
    """
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
    """
    Convert a CloudConnector ORM instance into a JSON-serializable dict suitable for API responses, masking sensitive values in the connector config.
    
    Config masking replaces any config value whose key contains (case-insensitive) "key", "secret", "password", or "token" with "****".
    
    Parameters:
        c (CloudConnector): ORM model instance to convert.
    
    Returns:
        dict: A dictionary with the connector's public fields:
            - id
            - name
            - connector_type
            - config (with sensitive values masked)
            - enabled
            - last_polled_at (ISO 8601 string or None)
            - last_error
            - poll_interval_seconds
            - events_ingested_total
            - created_at (ISO 8601 string)
    """
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
        "events_ingested": c.events_ingested_total,
        "created_at": c.created_at.isoformat(),
    }
