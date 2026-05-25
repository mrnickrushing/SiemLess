import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    JSON,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Network fields
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True, index=True)
    destination_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    source_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    destination_port: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Source identification
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    log_source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="api"
    )  # syslog, file, api
    log_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="generic"
    )  # ssh, apache, nginx, windows, firewall, generic

    # Classification
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="low"
    )  # low, medium, high, critical
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, default="system"
    )  # authentication, network, system, application, threat

    # Content
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Metadata
    tags: Mapped[list | None] = mapped_column(ARRAY(String), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    process: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # allow, deny, failed, success

    __table_args__ = (
        Index("ix_security_events_timestamp_severity", "timestamp", "severity"),
        Index("ix_security_events_log_type_category", "log_type", "category"),
        Index("ix_security_events_source_ip_timestamp", "source_ip", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<SecurityEvent id={self.id} severity={self.severity} type={self.log_type}>"
