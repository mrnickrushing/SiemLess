import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ThreatIndicator(Base):
    __tablename__ = "threat_indicators"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Indicator identity
    indicator_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )  # ip, domain, hash_md5, hash_sha256, url, email
    value: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)

    # Confidence and severity
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=50)  # 0-100
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")

    # Source tracking
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="manual"
    )  # manual, abuseipdb, virustotal, internal

    # Metadata
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Description and raw data
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_threat_indicators_type_value", "indicator_type", "value", unique=True),
    )

    def __repr__(self) -> str:
        return f"<ThreatIndicator type={self.indicator_type} value={self.value!r} severity={self.severity}>"
