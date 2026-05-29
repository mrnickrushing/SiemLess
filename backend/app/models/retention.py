"""Log retention policy and cold storage models."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RetentionPolicy(Base):
    __tablename__ = "retention_policies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    log_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    hot_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    cold_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    archive_to_s3: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    s3_bucket: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    s3_prefix: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<RetentionPolicy name={self.name!r} hot={self.hot_retention_days}d>"


class ColdEvent(Base):
    __tablename__ = "cold_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    original_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    event_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    def __repr__(self) -> str:
        return f"<ColdEvent original_id={self.original_id!r}>"
