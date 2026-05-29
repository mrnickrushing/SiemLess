"""Threat feed connector router."""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.threat_feed import ThreatFeedConnector
from app.services.feed_connectors.manager import feed_manager

router = APIRouter(prefix="/threat-feeds", tags=["threat-feeds"])
logger = logging.getLogger(__name__)

FEED_TYPES = ["misp", "opencti", "taxii"]


@router.get("", summary="List threat feed connectors")
async def list_feeds(
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> list:
    """
    List all threat feed connectors.
    
    Returns:
        A list of dictionaries, each representing a ThreatFeedConnector with keys including
        `id`, `name`, `feed_type`, `url`, `api_key` (redacted as `"****"` when present), `last_pulled_at`,
        `pull_interval_hours`, `enabled`, `indicator_count`, `last_error`, and `created_at`.
    """
    result = await db.execute(select(ThreatFeedConnector))
    return [_feed_to_dict(f) for f in result.scalars()]


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create feed connector")
async def create_feed(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    """
    Create and persist a new ThreatFeedConnector from the provided payload.
    
    Parameters:
        payload (dict): Incoming data for the new connector. Expected keys:
            - "feed_type" (str, optional): Type of feed; must be one of ["misp", "opencti", "taxii"].
            - "name" (str, optional): Connector name; defaults to the feed_type.
            - "url" (str): Connector URL (required).
            - "api_key" (str, optional): API key for the feed.
            - "pull_interval_hours" (int, optional): Interval in hours between pulls; defaults to 24.
            - "enabled" (bool, optional): Whether the connector is enabled; defaults to True.
    
    Returns:
        dict: Serialized representation of the created connector, including:
            - id, name, feed_type, url
            - api_key (redacted as "****" when present, otherwise None)
            - last_pulled_at (ISO string or None), pull_interval_hours, enabled
            - indicator_count, last_error, created_at (ISO string)
    
    Raises:
        HTTPException: 400 if "feed_type" is not one of the allowed types.
    """
    feed_type = payload.get("feed_type", "")
    if feed_type not in FEED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported feed type. Valid: {FEED_TYPES}")

    feed = ThreatFeedConnector(
        id=str(uuid.uuid4()),
        name=payload.get("name", feed_type),
        feed_type=feed_type,
        url=payload["url"],
        api_key=payload.get("api_key"),
        pull_interval_hours=payload.get("pull_interval_hours", 24),
        enabled=payload.get("enabled", True),
    )
    db.add(feed)
    await db.commit()
    await db.refresh(feed)
    return _feed_to_dict(feed)


@router.patch("/{feed_id}", summary="Update feed connector")
async def update_feed(
    feed_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    """
    Update fields of an existing threat feed connector identified by `feed_id`.
    
    Parameters:
        feed_id (str): Identifier of the target feed connector.
        payload (dict): Mapping of fields to update. Supported keys: `"name"`, `"url"`, `"api_key"`, `"pull_interval_hours"`, and `"enabled"`.
    
    Returns:
        dict: Dictionary representation of the updated feed connector.
    
    Raises:
        HTTPException: with status code 404 if no feed with `feed_id` exists.
    """
    result = await db.execute(select(ThreatFeedConnector).where(ThreatFeedConnector.id == feed_id))
    feed = result.scalar_one_or_none()
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found")
    for field in ("name", "url", "api_key", "pull_interval_hours", "enabled"):
        if field in payload:
            setattr(feed, field, payload[field])
    await db.commit()
    await db.refresh(feed)
    return _feed_to_dict(feed)


@router.delete("/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feed(
    feed_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> None:
    """
    Delete the threat feed connector identified by `feed_id`.
    
    Parameters:
        feed_id (str): The UUID of the feed connector to remove.
    
    Raises:
        HTTPException: Status 404 if no feed with the given id exists.
    """
    result = await db.execute(select(ThreatFeedConnector).where(ThreatFeedConnector.id == feed_id))
    feed = result.scalar_one_or_none()
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed not found")
    await db.delete(feed)
    await db.commit()


@router.post("/{feed_id}/pull-now", status_code=status.HTTP_202_ACCEPTED, summary="Trigger immediate pull")
async def pull_now(
    feed_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    """
    Trigger an immediate pull for the threat feed connector identified by `feed_id`.
    
    Parameters:
        feed_id (str): Identifier of the ThreatFeedConnector to pull now.
    
    Returns:
        dict: Result of the pull operation.
    
    Raises:
        HTTPException: 404 if the specified feed connector was not found or a ValueError occurred.
        HTTPException: 502 for other errors encountered while performing the pull.
    """
    try:
        result = await feed_manager.pull_now(feed_id)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


def _feed_to_dict(f: ThreatFeedConnector) -> dict:
    """
    Serialize a ThreatFeedConnector into a dictionary suitable for API responses.
    
    Parameters:
        f (ThreatFeedConnector): ORM instance representing a threat feed connector.
    
    Returns:
        dict: A mapping with the connector's fields:
            - id: Connector UUID string.
            - name: Connector name.
            - feed_type: One of the supported feed types.
            - url: Feed URL.
            - api_key: Redacted API key as `"****"` if present, otherwise `None`.
            - last_pulled_at: ISO 8601 string of last pull timestamp or `None`.
            - pull_interval_hours: Pull interval in hours.
            - enabled: Boolean indicating whether the connector is enabled.
            - indicator_count: Number of imported indicators.
            - last_error: Last error message, if any.
            - created_at: ISO 8601 string of the creation timestamp.
    """
    return {
        "id": f.id,
        "name": f.name,
        "feed_type": f.feed_type,
        "url": f.url,
        "api_key": "****" if f.api_key else None,
        "last_pulled_at": f.last_pulled_at.isoformat() if f.last_pulled_at else None,
        "pull_interval_hours": f.pull_interval_hours,
        "enabled": f.enabled,
        "indicator_count": f.indicator_count,
        "last_error": f.last_error,
        "created_at": f.created_at.isoformat(),
    }
