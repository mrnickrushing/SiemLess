"""Network scanner API router for defensive internal asset discovery."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.asset import NetworkScan, NetworkScanHost
from app.services.network_scanner import network_scanner_service

router = APIRouter(prefix="/network-scanner", tags=["network-scanner"])


@router.post("/scans", status_code=status.HTTP_202_ACCEPTED, summary="Start network scan")
async def start_scan(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_user),
) -> dict:
    target_cidr = str(payload.get("target_cidr", "")).strip()
    if not target_cidr:
        raise HTTPException(status_code=400, detail="target_cidr is required")
    ports = payload.get("ports")
    try:
        scan = await network_scanner_service.create_scan(db, target_cidr, ports, username)
        network_scanner_service.start_background_scan(scan.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _scan_to_dict(scan)


@router.get("/scans", summary="List network scans")
async def list_scans(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    query = select(NetworkScan)
    count_query = select(func.count()).select_from(NetworkScan)
    if status_filter:
        query = query.where(NetworkScan.status == status_filter)
        count_query = count_query.where(NetworkScan.status == status_filter)

    total = (await db.execute(count_query)).scalar() or 0
    pages = max(1, (total + page_size - 1) // page_size)
    result = await db.execute(
        query.order_by(NetworkScan.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "items": [_scan_to_dict(scan) for scan in result.scalars().all()],
        "active_scan_ids": network_scanner_service.active_scan_ids(),
    }


@router.get("/scans/{scan_id}", summary="Get network scan")
async def get_scan(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> dict:
    scan = await db.get(NetworkScan, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    hosts = await db.execute(
        select(NetworkScanHost)
        .where(NetworkScanHost.scan_id == scan_id)
        .order_by(NetworkScanHost.status.desc(), NetworkScanHost.ip_address.asc())
    )
    return {
        **_scan_to_dict(scan),
        "hosts": [_host_to_dict(host) for host in hosts.scalars().all()],
    }


@router.get("/scans/{scan_id}/hosts", summary="List network scan hosts")
async def list_scan_hosts(
    scan_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> list[dict]:
    query = select(NetworkScanHost).where(NetworkScanHost.scan_id == scan_id)
    if status_filter:
        query = query.where(NetworkScanHost.status == status_filter)
    result = await db.execute(query.order_by(NetworkScanHost.ip_address.asc()))
    return [_host_to_dict(host) for host in result.scalars().all()]


def _scan_to_dict(scan: NetworkScan) -> dict:
    return {
        "id": scan.id,
        "target_cidr": scan.target_cidr,
        "ports": scan.ports,
        "status": scan.status,
        "created_by": scan.created_by,
        "created_at": scan.created_at.isoformat() if scan.created_at else None,
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "finished_at": scan.finished_at.isoformat() if scan.finished_at else None,
        "hosts_total": scan.hosts_total,
        "hosts_scanned": scan.hosts_scanned,
        "hosts_up": scan.hosts_up,
        "open_ports": scan.open_ports,
        "error": scan.error,
        "options": scan.options,
    }


def _host_to_dict(host: NetworkScanHost) -> dict:
    return {
        "id": host.id,
        "scan_id": host.scan_id,
        "ip_address": host.ip_address,
        "hostname": host.hostname,
        "status": host.status,
        "latency_ms": host.latency_ms,
        "open_ports": host.open_ports or [],
        "services": host.services or [],
        "mac_address": host.mac_address,
        "os_guess": host.os_guess,
        "asset_id": host.asset_id,
        "scanned_at": host.scanned_at.isoformat() if host.scanned_at else None,
        "error": host.error,
    }
