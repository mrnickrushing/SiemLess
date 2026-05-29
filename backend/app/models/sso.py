"""SSO/OIDC provider configuration model."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SSOConfig(Base):
    __tablename__ = "sso_configs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    provider_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    client_id: Mapped[str] = mapped_column(String(500), nullable=False)
    client_secret: Mapped[str] = mapped_column(String(500), nullable=False)
    authorization_endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    token_endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    userinfo_endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    jwks_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scopes: Mapped[str] = mapped_column(
        String(500), nullable=False, default="openid email profile"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<SSOConfig provider={self.provider_name!r} enabled={self.enabled}>"
