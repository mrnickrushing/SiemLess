"""Schemas for SSO/OIDC provider configuration."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SSOConfigCreate(BaseModel):
    provider_name: str
    client_id: str
    client_secret: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: Optional[str] = None
    scopes: str = "openid email profile"
    enabled: bool = True


class SSOConfigUpdate(BaseModel):
    provider_name: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    authorization_endpoint: Optional[str] = None
    token_endpoint: Optional[str] = None
    userinfo_endpoint: Optional[str] = None
    jwks_uri: Optional[str] = None
    scopes: Optional[str] = None
    enabled: Optional[bool] = None


class SSOConfigRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    provider_name: str
    client_id: str
    # client_secret is masked: only first 4 chars + ****
    client_secret_masked: Optional[str] = None
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: Optional[str] = None
    scopes: str
    enabled: bool
    created_at: datetime

    @classmethod
    def from_orm_masked(cls, obj: object) -> "SSOConfigRead":
        secret = getattr(obj, "client_secret", "") or ""
        masked = secret[:4] + "****" if len(secret) >= 4 else "****"
        return cls(
            id=obj.id,
            provider_name=obj.provider_name,
            client_id=obj.client_id,
            client_secret_masked=masked,
            authorization_endpoint=obj.authorization_endpoint,
            token_endpoint=obj.token_endpoint,
            userinfo_endpoint=obj.userinfo_endpoint,
            jwks_uri=obj.jwks_uri,
            scopes=obj.scopes,
            enabled=obj.enabled,
            created_at=obj.created_at,
        )


class SSOProviderPublic(BaseModel):
    """Public-facing provider info (no secrets)."""
    provider_name: str
    scopes: str
    login_url: str
