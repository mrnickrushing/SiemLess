"""Asset inventory and network scanner models."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    ip_addresses: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    os_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    os_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    criticality: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    cve_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<Asset hostname={self.hostname!r} criticality={self.criticality}>"


class AssetSoftware(Base):
    __tablename__ = "asset_software"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cpe: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    last_scanned: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<AssetSoftware name={self.name!r} version={self.version!r}>"


class AssetVulnerability(Base):
    __tablename__ = "asset_vulnerabilities"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cve_id: Mapped[str] = mapped_column(String(50), nullable=False)
    cvss_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<AssetVulnerability cve={self.cve_id!r} severity={self.severity}>"


class NetworkScan(Base):
    __tablename__ = "network_scans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    target_cidr: Mapped[str] = mapped_column(String(64), nullable=False)
    ports: Mapped[list] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    hosts_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hosts_scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hosts_up: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    open_ports: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    options: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class NetworkScanHost(Base):
    __tablename__ = "network_scan_hosts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id: Mapped[str] = mapped_column(String(36), ForeignKey("network_scans.id", ondelete="CASCADE"), nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    hostname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="down")
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    open_ports: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    services: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    mac_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    os_guess: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    asset_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
