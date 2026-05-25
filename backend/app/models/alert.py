import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Alert details
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="medium"
    )  # low, medium, high, critical
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="open"
    )  # open, investigating, resolved, false_positive

    # Relationship to rule
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("correlation_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Associated data
    event_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list of UUID strings
    source_ips: Mapped[list | None] = mapped_column(JSON, nullable=True)
    affected_users: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # MITRE ATT&CK mapping
    mitre_tactic: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mitre_technique: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Investigation
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<Alert id={self.id} title={self.title!r} severity={self.severity} status={self.status}>"
