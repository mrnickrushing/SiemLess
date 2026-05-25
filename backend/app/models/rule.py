import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CorrelationRule(Base):
    __tablename__ = "correlation_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Classification
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="system")

    # Rule logic
    condition: Mapped[dict] = mapped_column(JSON, nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    time_window: Mapped[int] = mapped_column(Integer, nullable=False, default=300)  # seconds

    # MITRE ATT&CK mapping
    mitre_tactic: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mitre_technique: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_triggered: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Statistics
    trigger_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Alert templates
    alert_title_template: Mapped[str] = mapped_column(
        String(500), nullable=False, default="{rule_name} triggered"
    )
    alert_description_template: Mapped[str] = mapped_column(
        Text, nullable=False, default="Rule {rule_name} triggered {count} times in {window} seconds."
    )

    # Tags
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<CorrelationRule id={self.id} name={self.name!r} enabled={self.enabled}>"
