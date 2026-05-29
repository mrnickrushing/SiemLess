"""UEBA (User and Entity Behavior Analytics) models."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserBehaviorProfile(Base):
    __tablename__ = "user_behavior_profiles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    baseline_login_hours: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    baseline_source_ips: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    baseline_event_rate_per_hour: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    baseline_computed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_evaluated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        """
        Provide an unambiguous string representation of the UserBehaviorProfile including the username.
        
        Returns:
            A string formatted as "<UserBehaviorProfile username='...'>" where the username is shown as its repr.
        """
        return f"<UserBehaviorProfile username={self.username!r}>"


class UEBAAnomaly(Base):
    __tablename__ = "ueba_anomalies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    username: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    anomaly_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # unusual_hour/new_source_ip/rate_spike/impossible_travel/composite
    score: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    alert_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        """
        Provide a concise developer-facing string representation of the UEBAAnomaly.
        
        Returns:
            str: A string containing the class name and the anomaly's `username`, `anomaly_type`, and `score`.
        """
        return f"<UEBAAnomaly username={self.username!r} type={self.anomaly_type} score={self.score}>"
