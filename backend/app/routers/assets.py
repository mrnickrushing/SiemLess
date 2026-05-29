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
    import asyncio
    from app.database import AsyncSessionLocal

    async def _run():
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
    result = await db.execute(
        select(AssetVulnerability)
        .where(AssetVulnerability.asset_id == asset_id)
        .order_by(AssetVulnerability.cvss_score.desc().nullslast())
    )
    return [_vuln_to_dict(v) for v in result.scalars()]


def _asset_to_dict(a: Asset) -> dict:
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
    return {
        "id": s.id,
        "asset_id": s.asset_id,
        "name": s.name,
        "version": s.version,
        "cpe": s.cpe,
        "last_scanned": s.last_scanned.isoformat() if s.last_scanned else None,
    }


def _vuln_to_dict(v: AssetVulnerability) -> dict:
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
