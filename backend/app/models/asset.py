"""Asset inventory models."""
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
        """
        Return a concise, debug-friendly representation of the Asset.
        
        Returns:
            str: String containing the asset's hostname and criticality, e.g. "<Asset hostname='host' criticality=high>".
        """
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
        """
        Provide a concise string representation of the AssetSoftware instance.
        
        Returns:
            repr_str (str): String in the format "<AssetSoftware name='...' version='...'>".
        """
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
        """
        Produce a concise string representation of the vulnerability for debugging and logging.
        
        Returns:
            str: A string containing the CVE identifier and severity in the form
                 "<AssetVulnerability cve='CVE-ID' severity=SEVERITY>".
        """
        return f"<AssetVulnerability cve={self.cve_id!r} severity={self.severity}>"
