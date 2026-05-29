"""Asset inventory router."""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.asset import Asset, AssetSoftware, AssetVulnerability
from app.models.event import SecurityEvent
from app.services.asset_discovery import asset_discovery_service

router = APIRouter(prefix="/assets", tags=["assets"])
logger = logging.getLogger(__name__)


@router.get("", summary="List assets")
async def list_assets(
    criticality: Optional[str] = Query(None),
    os_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    """
    Return a paginated list of assets, optionally filtered by criticality, OS type, or hostname.
    
    Supports filtering by `criticality` and `os_type`, and a case-insensitive partial match on `hostname`. Results are ordered by `last_seen` descending.
    
    Parameters:
        criticality (Optional[str]): Filter assets that have this criticality value.
        os_type (Optional[str]): Filter assets that have this operating system type.
        search (Optional[str]): Case-insensitive substring to match against asset hostnames.
        page (int): 1-based page number of results.
        page_size (int): Number of items per page (maximum 200).
    
    Returns:
        dict: A dictionary containing:
            - `total` (int): total number of matching assets
            - `page` (int): current page number
            - `page_size` (int): number of items per page
            - `items` (list): list of asset dictionaries
    """
    from sqlalchemy import func

    query = select(Asset)
    count_query = select(func.count()).select_from(Asset)

    if criticality:
        query = query.where(Asset.criticality == criticality)
        count_query = count_query.where(Asset.criticality == criticality)
    if os_type:
        query = query.where(Asset.os_type == os_type)
        count_query = count_query.where(Asset.os_type == os_type)
    if search:
        like = f"%{search}%"
        query = query.where(Asset.hostname.ilike(like))
        count_query = count_query.where(Asset.hostname.ilike(like))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    query = query.order_by(Asset.last_seen.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    assets = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_asset_to_dict(a) for a in assets],
    }


@router.post("", status_code=status.HTTP_201_CREATED, summary="Create asset")
async def create_asset(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    """
    Create a new Asset record from the provided payload and return its serialized representation.
    
    Parameters:
        payload (dict): Asset attributes. Required key: `"hostname"`. Optional keys:
            - `ip_addresses` (list): list of IP address strings.
            - `os_type` (str)
            - `os_version` (str)
            - `asset_type` (str): defaults to `"unknown"` when omitted.
            - `criticality` (str): defaults to `"medium"` when omitted.
            - `tags` (list)
    
    Returns:
        dict: A dictionary representation of the created asset (fields include id, hostname, ip_addresses, os_type, os_version, asset_type, criticality, tags, first_seen, last_seen, and cve_count).
    """
    from datetime import datetime, timezone
    asset = Asset(
        id=str(uuid.uuid4()),
        hostname=payload["hostname"],
        ip_addresses=payload.get("ip_addresses", []),
        os_type=payload.get("os_type"),
        os_version=payload.get("os_version"),
        asset_type=payload.get("asset_type", "unknown"),
        criticality=payload.get("criticality", "medium"),
        tags=payload.get("tags"),
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return _asset_to_dict(asset)


@router.get("/{asset_id}", summary="Get asset with software and vulnerabilities")
async def get_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    """
    Fetches an asset by its ID and returns the asset data together with its installed software and vulnerabilities.
    
    Parameters:
        asset_id (str): UUID of the asset to retrieve.
    
    Returns:
        dict: Asset data merged with two keys:
            - "software": list of software dictionaries associated with the asset.
            - "vulnerabilities": list of vulnerability dictionaries associated with the asset, ordered by CVSS score descending with null scores last.
    
    Raises:
        HTTPException: 404 if the asset with the given ID does not exist.
    """
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    software_result = await db.execute(
        select(AssetSoftware).where(AssetSoftware.asset_id == asset_id)
    )
    software = software_result.scalars().all()

    vuln_result = await db.execute(
        select(AssetVulnerability).where(AssetVulnerability.asset_id == asset_id)
        .order_by(AssetVulnerability.cvss_score.desc().nullslast())
    )
    vulns = vuln_result.scalars().all()

    return {
        **_asset_to_dict(asset),
        "software": [_sw_to_dict(s) for s in software],
        "vulnerabilities": [_vuln_to_dict(v) for v in vulns],
    }


@router.patch("/{asset_id}", summary="Update asset")
async def update_asset(
    asset_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    """
    Update selectable fields of an existing asset.
    
    Parameters:
        asset_id (str): The UUID string identifying the asset to update.
        payload (dict): A mapping of fields to update. Supported keys: "criticality", "tags", "os_type", "os_version", "asset_type".
    
    Returns:
        dict: The updated asset serialized as a dictionary.
    
    Raises:
        HTTPException: Raised with status code 404 if no asset exists with the given `asset_id`.
    """
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    for field in ("criticality", "tags", "os_type", "os_version", "asset_type"):
        if field in payload:
            setattr(asset, field, payload[field])
    await db.commit()
    await db.refresh(asset)
    return _asset_to_dict(asset)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> None:
    """
    Delete the asset identified by asset_id from the database.
    
    Parameters:
        asset_id (str): Identifier of the asset to delete.
    
    Raises:
        HTTPException: status code 404 if the asset does not exist.
    """
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    await db.delete(asset)
    await db.commit()


@router.get("/{asset_id}/events", summary="Get recent events from this asset")
async def get_asset_events(
    asset_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    """
    Return recent security events for the specified asset's hostname with pagination.
    
    Parameters:
        asset_id (str): UUID of the asset whose events to retrieve.
        page (int): 1-based page number (must be >= 1).
        page_size (int): Number of events per page (1–100).
    
    Returns:
        dict: A mapping with:
            - "total" (int): Total number of matching events.
            - "items" (list[dict]): Paginated events, each containing:
                - "id" (str): Event identifier.
                - "timestamp" (str|None): ISO 8601 timestamp or `None` if missing.
                - "severity" (str): Event severity.
                - "category" (str): Event category.
                - "message" (str): Event message.
                - "source_ip" (str): Source IP address.
    
    Raises:
        HTTPException: 404 if the asset with `asset_id` does not exist.
    """
    from sqlalchemy import func

    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    count_result = await db.execute(
        select(func.count()).select_from(SecurityEvent).where(
            SecurityEvent.hostname == asset.hostname
        )
    )
    total = count_result.scalar() or 0
    offset = (page - 1) * page_size
    events_result = await db.execute(
        select(SecurityEvent)
        .where(SecurityEvent.hostname == asset.hostname)
        .order_by(SecurityEvent.timestamp.desc())
        .offset(offset)
        .limit(page_size)
    )
    events = events_result.scalars().all()

    return {
        "total": total,
        "items": [
            {
                "id": str(e.id),
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "severity": e.severity,
                "category": e.category,
                "message": e.message,
                "source_ip": e.source_ip,
            }
            for e in events
        ],
    }


@router.post("/{asset_id}/software", status_code=status.HTTP_201_CREATED, summary="Add software")
async def add_software(
    asset_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    """
    Add a software record to an existing asset.
    
    Parameters:
        asset_id (str): Identifier of the asset to attach the software to.
        payload (dict): Software attributes; must include `"name"` and may include `"version"` and `"cpe"`.
    
    Returns:
        dict: Serialized software record as returned by `_sw_to_dict`.
    
    Raises:
        HTTPException: 404 if the asset with `asset_id` does not exist.
    """
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    sw = AssetSoftware(
        id=str(uuid.uuid4()),
        asset_id=asset_id,
        name=payload["name"],
        version=payload.get("version"),
        cpe=payload.get("cpe"),
    )
    db.add(sw)
    await db.commit()
    await db.refresh(sw)
    return _sw_to_dict(sw)


@router.post("/{asset_id}/scan-cves", status_code=status.HTTP_202_ACCEPTED, summary="Trigger CVE enrichment")
async def scan_cves(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    """
    Trigger CVE enrichment for the given asset by scheduling a background task.
    
    Returns:
        result (dict): A dict with a `message` key confirming the CVE scan was scheduled.
    """
    import asyncio
    from app.database import AsyncSessionLocal

    async def _run():
        """
        Perform CVE enrichment for the surrounding `asset_id` and log how many new CVEs were added.
        
        This coroutine runs using its own database session, invokes the asset discovery service to enrich CVE data for the asset, and emits an informational log with the number of newly discovered CVEs.
        """
        async with AsyncSessionLocal() as _db:
            count = await asset_discovery_service.enrich_cves(_db, asset_id)
            logger.info("CVE scan for asset %s: %d new CVEs", asset_id, count)

    asyncio.create_task(_run())
    return {"message": "CVE scan triggered in background"}


@router.get("/{asset_id}/vulnerabilities", summary="List vulnerabilities")
async def list_vulnerabilities(
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> list:
    """
    List vulnerabilities for the given asset ordered by CVSS score (highest first, nulls last).
    
    Parameters:
        asset_id (str): Identifier of the asset whose vulnerabilities will be listed.
    
    Returns:
        list: A list of vulnerability dictionaries containing `id`, `asset_id`, `cve_id`, `cvss_score`, `description`, `severity`, and `published_at`/`fetched_at` timestamp fields (ISO-formatted strings or `None`).
    """
    result = await db.execute(
        select(AssetVulnerability)
        .where(AssetVulnerability.asset_id == asset_id)
        .order_by(AssetVulnerability.cvss_score.desc().nullslast())
    )
    return [_vuln_to_dict(v) for v in result.scalars()]


def _asset_to_dict(a: Asset) -> dict:
    """
    Serialize an Asset ORM instance into a JSON-ready dictionary.
    
    Parameters:
        a (Asset): Asset model instance to serialize.
    
    Returns:
        dict: Mapping containing asset fields:
            - `id`, `hostname`, `ip_addresses`, `os_type`, `os_version`, `asset_type`, `tags`, `criticality`, `cve_count`
            - `first_seen`, `last_seen` as ISO 8601 strings if present, otherwise `None`
    """
    return {
        "id": a.id,
        "hostname": a.hostname,
        "ip_addresses": a.ip_addresses,
        "os_type": a.os_type,
        "os_version": a.os_version,
        "asset_type": a.asset_type,
        "first_seen": a.first_seen.isoformat() if a.first_seen else None,
        "last_seen": a.last_seen.isoformat() if a.last_seen else None,
        "tags": a.tags,
        "criticality": a.criticality,
        "cve_count": a.cve_count,
    }


def _sw_to_dict(s: AssetSoftware) -> dict:
    """
    Serialize an AssetSoftware ORM object into a JSON-ready dictionary.
    
    Parameters:
        s (AssetSoftware): The asset software ORM instance to serialize.
    
    Returns:
        dict: Dictionary with keys:
            - `id`: software identifier (string)
            - `asset_id`: associated asset identifier (string)
            - `name`: software name
            - `version`: software version or `None`
            - `cpe`: CPE string or `None`
            - `last_scanned`: ISO 8601 timestamp string of last scan, or `None`
    """
    return {
        "id": s.id,
        "asset_id": s.asset_id,
        "name": s.name,
        "version": s.version,
        "cpe": s.cpe,
        "last_scanned": s.last_scanned.isoformat() if s.last_scanned else None,
    }


def _vuln_to_dict(v: AssetVulnerability) -> dict:
    """
    Serialize an AssetVulnerability ORM instance into a JSON-ready dictionary.
    
    Parameters:
        v (AssetVulnerability): The vulnerability ORM instance to serialize.
    
    Returns:
        dict: A dictionary with keys `id`, `asset_id`, `cve_id`, `cvss_score`, `description`, `severity`,
        `published_at`, and `fetched_at`. Timestamp fields are ISO 8601 strings when present, otherwise `None`.
    """
    return {
        "id": v.id,
        "asset_id": v.asset_id,
        "cve_id": v.cve_id,
        "cvss_score": v.cvss_score,
        "description": v.description,
        "severity": v.severity,
        "published_at": v.published_at.isoformat() if v.published_at else None,
        "fetched_at": v.fetched_at.isoformat() if v.fetched_at else None,
    }
