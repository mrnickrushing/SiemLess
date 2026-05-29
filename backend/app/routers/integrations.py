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
    """
    List configured integrations and serialize each to a safe dictionary.
    
    Returns:
        integrations (list): A list of integration dictionaries where sensitive configuration values are replaced with "****" and `created_at` is an ISO 8601 string.
    """
    result = await db.execute(select(IntegrationConfig))
    return [_integration_to_dict(i) for i in result.scalars()]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create integration")
async def create_integration(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    """
    Create a new IntegrationConfig record from the provided payload.
    
    Creates and persists an integration using values from `payload` and returns its serialized representation with sensitive configuration values masked.
    
    Parameters:
        payload (dict): Integration attributes. Recognized keys:
            - "integration_type" (str): Required; must be one of INTEGRATION_TYPES.
            - "name" (str): Optional; defaults to the integration_type.
            - "config" (dict): Optional; defaults to {}.
            - "enabled" (bool): Optional; defaults to True.
    
    Returns:
        dict: The created integration as a dictionary with sensitive config values replaced by "****" and `created_at` formatted as an ISO 8601 string.
    
    Raises:
        HTTPException: If `integration_type` is not in INTEGRATION_TYPES (status 400).
    """
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
    """
    Update fields of an existing IntegrationConfig and return its serialized representation.
    
    Parameters:
        integration_id (str): Identifier of the integration to update.
        payload (dict): Mapping containing any of the keys `"name"`, `"config"`, or `"enabled"` whose values will replace the corresponding fields on the integration.
    
    Returns:
        dict: Serialized integration with sensitive configuration values masked and `created_at` formatted as an ISO 8601 string.
    
    Raises:
        HTTPException: 404 if no integration with `integration_id` exists.
    """
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
    """
    Delete the IntegrationConfig record with the given ID.
    
    Parameters:
        integration_id (str): The UUID string of the integration to remove.
    
    Raises:
        HTTPException: 404 if no integration with the given ID exists.
    """
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
    """
    Test the connection for a specific integration.
    
    Parameters:
        integration_id (str): ID of the integration configuration to test.
    
    Returns:
        result (dict): A dictionary with key `"success"` set to `True` if the connection succeeded, `False` otherwise.
    
    Raises:
        HTTPException: Raised with status code 404 when the integration cannot be found or is invalid.
    """
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
    """
    Create a ticket using the specified integration and return the created ticket's identifier.
    
    Parameters:
        integration_id (str): Identifier of the integration to use for ticket creation.
        payload (dict): Request data; may include:
            - alert_id: Optional alert identifier used in the default title.
            - title: Ticket title (defaults to "SiemLess Alert {alert_id}").
            - description: Ticket description (defaults to empty string).
            - priority: Ticket priority (defaults to "Medium").
    
    Returns:
        dict: A dictionary with the created ticket id: `{"ticket_id": <ticket_id>}`.
    
    Raises:
        HTTPException: 404 if the integration or referenced resource is not found (mapped from ValueError).
        HTTPException: 502 for other errors encountered while creating the ticket.
    """
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
    """
    Serialize an IntegrationConfig into a dictionary with sensitive configuration values masked.
    
    Parameters:
        i (IntegrationConfig): The integration model instance to serialize.
    
    Returns:
        dict: A dictionary containing `id`, `name`, `integration_type`, `config`, `enabled`, and
        `created_at` (ISO 8601 string). In `config`, values for keys containing `key`, `secret`,
        `password`, or `token` (case-insensitive) are replaced with `"****"`.
    """
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
