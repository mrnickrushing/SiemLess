"""SOAR Playbook models."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Playbook(Base):
    __tablename__ = "playbooks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # alert_severity/alert_rule/manual
    trigger_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    steps: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        """
        Provide a concise, unambiguous representation of the Playbook for debugging and logging.
        
        Returns:
            str: A string in the form "<Playbook name='...' enabled=...>" showing the playbook's name and enabled state.
        """
        return f"<Playbook name={self.name!r} enabled={self.enabled}>"


class PlaybookRun(Base):
    __tablename__ = "playbook_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    playbook_id: Mapped[str] = mapped_column(
        String(36), nullable=False, index=True
    )
    alert_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    triggered_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="running"
    )  # running/completed/failed
    step_results: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        """
        Provide a concise, debug-friendly string representation of the PlaybookRun instance.
        
        Returns:
            A string containing the model's class name and the instance's `id` and `status`, e.g. "<PlaybookRun id=... status=...>".
        """
        return f"<PlaybookRun id={self.id} status={self.status}>"
