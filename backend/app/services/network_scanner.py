"""Defensive asset discovery service for owned internal networks.

The scanner is intentionally conservative:
- private and loopback ranges only
- limited host and port counts
- bounded concurrency and timeouts
- TCP connect checks only
- results are stored and linked to assets
"""
import asyncio
import ipaddress
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.asset import Asset, NetworkScan, NetworkScanHost

DEFAULT_PORTS = [22, 53, 80, 135, 139, 443, 445, 3389, 5432, 6379, 8000, 8080, 8443]
MAX_HOSTS = 1024
MAX_PORTS = 200
MAX_CONCURRENCY = 128
CONNECT_TIMEOUT = 1.0

SERVICE_NAMES: dict[int, str] = {
    21: "ftp",
    22: "ssh",
    25: "smtp",
    53: "dns",
    80: "http",
    110: "pop3",
    135: "msrpc",
    139: "netbios",
    143: "imap",
    389: "ldap",
    443: "https",
    445: "smb",
    465: "smtps",
    587: "submission",
    993: "imaps",
    995: "pop3s",
    1433: "mssql",
    3306: "mysql",
    3389: "rdp",
    5432: "postgresql",
    5900: "vnc",
    6379: "redis",
    8000: "http-alt",
    8080: "http-alt",
    8443: "https-alt",
    9200: "elasticsearch",
    9300: "elasticsearch",
}


@dataclass
class HostResult:
    ip_address: str
    hostname: str | None
    status: str
    latency_ms: float | None
    open_ports: list[int]
    services: list[dict]
    error: str | None = None


def parse_ports(raw_ports: Iterable[int] | str | None) -> list[int]:
    if raw_ports is None or raw_ports == "":
        return DEFAULT_PORTS.copy()
    ports: set[int] = set()
    if isinstance(raw_ports, str):
        chunks = [part.strip() for part in raw_ports.split(",") if part.strip()]
        for chunk in chunks:
            if "-" in chunk:
                start, end = chunk.split("-", 1)
                ports.update(range(int(start), int(end) + 1))
            else:
                ports.add(int(chunk))
    else:
        ports = {int(p) for p in raw_ports}
    valid = sorted(p for p in ports if 1 <= p <= 65535)
    if len(valid) > MAX_PORTS:
        raise ValueError(f"Too many ports. Maximum is {MAX_PORTS}.")
    if not valid:
        raise ValueError("At least one valid port is required.")
    return valid


def parse_targets(cidr: str) -> list[str]:
    network = ipaddress.ip_network(cidr, strict=False)
    if not (network.is_private or network.is_loopback or network.is_link_local):
        raise ValueError("Only private, loopback, or link local ranges are allowed.")
    hosts = [str(ip) for ip in network.hosts()]
    if network.num_addresses == 1:
        hosts = [str(network.network_address)]
    if len(hosts) > MAX_HOSTS:
        raise ValueError(f"Target range has {len(hosts)} hosts. Maximum is {MAX_HOSTS}.")
    if not hosts:
        raise ValueError("No scan targets found in range.")
    return hosts


async def _reverse_dns(ip_address: str) -> str | None:
    try:
        return await asyncio.to_thread(lambda: socket.gethostbyaddr(ip_address)[0])
    except Exception:
        return None


async def _check_port(ip_address: str, port: int, timeout: float) -> bool:
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip_address, port), timeout=timeout)
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def scan_host(ip_address: str, ports: list[int], timeout: float, semaphore: asyncio.Semaphore) -> HostResult:
    started = time.perf_counter()
    open_ports: list[int] = []
    services: list[dict] = []

    async def probe(port: int) -> None:
        async with semaphore:
            if await _check_port(ip_address, port, timeout):
                open_ports.append(port)
                services.append({"port": port, "protocol": "tcp", "service": SERVICE_NAMES.get(port, "unknown")})

    await asyncio.gather(*(probe(port) for port in ports))
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    hostname = await _reverse_dns(ip_address) if open_ports else None
    return HostResult(
        ip_address=ip_address,
        hostname=hostname,
        status="up" if open_ports else "down",
        latency_ms=latency_ms if open_ports else None,
        open_ports=sorted(open_ports),
        services=sorted(services, key=lambda item: item["port"]),
    )


class NetworkScannerService:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}

    def active_scan_ids(self) -> list[str]:
        return [scan_id for scan_id, task in self._tasks.items() if not task.done()]

    async def create_scan(self, db: AsyncSession, target_cidr: str, ports: Iterable[int] | str | None, username: str | None) -> NetworkScan:
        target_hosts = parse_targets(target_cidr)
        parsed_ports = parse_ports(ports)
        scan = NetworkScan(
            id=str(uuid.uuid4()),
            target_cidr=str(ipaddress.ip_network(target_cidr, strict=False)),
            ports=parsed_ports,
            status="queued",
            created_by=username,
            hosts_total=len(target_hosts),
            hosts_scanned=0,
            hosts_up=0,
            open_ports=0,
            options={"max_concurrency": MAX_CONCURRENCY, "timeout": CONNECT_TIMEOUT},
        )
        db.add(scan)
        await db.commit()
        await db.refresh(scan)
        return scan

    def start_background_scan(self, scan_id: str) -> None:
        if scan_id in self._tasks and not self._tasks[scan_id].done():
            return
        self._tasks[scan_id] = asyncio.create_task(self._run_scan(scan_id))

    async def _run_scan(self, scan_id: str) -> None:
        async with AsyncSessionLocal() as db:
            scan = await db.get(NetworkScan, scan_id)
            if scan is None:
                return
            try:
                scan.status = "running"
                scan.started_at = datetime.now(timezone.utc)
                await db.commit()

                hosts = parse_targets(scan.target_cidr)
                ports = parse_ports(scan.ports)
                semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

                for ip_address in hosts:
                    result = await scan_host(ip_address, ports, CONNECT_TIMEOUT, semaphore)
                    asset_id = None
                    if result.status == "up":
                        asset_id = await self._upsert_asset(db, result)
                    db.add(NetworkScanHost(
                        id=str(uuid.uuid4()),
                        scan_id=scan.id,
                        ip_address=result.ip_address,
                        hostname=result.hostname,
                        status=result.status,
                        latency_ms=result.latency_ms,
                        open_ports=result.open_ports,
                        services=result.services,
                        asset_id=asset_id,
                        scanned_at=datetime.now(timezone.utc),
                        error=result.error,
                    ))
                    scan.hosts_scanned += 1
                    if result.status == "up":
                        scan.hosts_up += 1
                        scan.open_ports += len(result.open_ports)
                    await db.commit()

                scan.status = "completed"
                scan.finished_at = datetime.now(timezone.utc)
                await db.commit()
            except Exception as exc:
                scan.status = "failed"
                scan.error = str(exc)
                scan.finished_at = datetime.now(timezone.utc)
                await db.commit()

    async def _upsert_asset(self, db: AsyncSession, result: HostResult) -> str:
        hostname = result.hostname or result.ip_address
        existing = await db.execute(select(Asset).where(Asset.hostname == hostname))
        asset = existing.scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if asset is None:
            asset = Asset(
                id=str(uuid.uuid4()),
                hostname=hostname,
                ip_addresses=[result.ip_address],
                asset_type="network",
                criticality="medium",
                tags=["network-scan"],
                first_seen=now,
                last_seen=now,
            )
            db.add(asset)
            await db.flush()
        else:
            ips = set(asset.ip_addresses or [])
            ips.add(result.ip_address)
            asset.ip_addresses = sorted(ips)
            asset.last_seen = now
            tags = set(asset.tags or []) if isinstance(asset.tags, list) else set()
            tags.add("network-scan")
            asset.tags = sorted(tags)
        return asset.id


network_scanner_service = NetworkScannerService()
