"""
OIDC / SSO authentication router.

Endpoints:
  GET  /auth/oidc/providers            — public list of enabled providers
  GET  /auth/oidc/{provider}/login     — PKCE redirect to IdP
  GET  /auth/oidc/{provider}/callback  — exchange code, issue JWT cookie
  GET  /auth/oidc/configs              — admin: list all configs
  POST /auth/oidc/configs              — admin: create config
  PUT  /auth/oidc/configs/{id}         — admin: update config
  DELETE /auth/oidc/configs/{id}       — admin: delete config
"""
import base64
import hashlib
import logging
import os
import secrets
import urllib.parse
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import RedirectResponse
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import create_access_token, get_current_user
from app.models.sso import SSOConfig
from app.schemas.sso import SSOConfigCreate, SSOConfigRead, SSOConfigUpdate, SSOProviderPublic
from app.services.redis_client import get_redis

router = APIRouter(prefix="/auth/oidc", tags=["sso"])
logger = logging.getLogger(__name__)

_PKCE_TTL = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_provider(db: AsyncSession, provider_name: str) -> SSOConfig:
    """
    Retrieve an enabled SSO provider configuration by provider name.
    
    Parameters:
        db (AsyncSession): Database session used to query SSO configurations.
        provider_name (str): The provider_name identifier to look up.
    
    Returns:
        SSOConfig: The matching enabled SSOConfig instance.
    
    Raises:
        HTTPException: 404 if no enabled configuration with the given provider_name exists.
    """
    result = await db.execute(
        select(SSOConfig).where(
            SSOConfig.provider_name == provider_name,
            SSOConfig.enabled == True,  # noqa: E712
        )
    )
    cfg = result.scalar_one_or_none()
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"SSO provider '{provider_name}' not found or disabled")
    return cfg


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@router.get("/providers", response_model=list[SSOProviderPublic], summary="List enabled SSO providers")
async def list_providers(db: AsyncSession = Depends(get_db)) -> list[SSOProviderPublic]:
    """
    Return publicly discoverable OIDC providers that are enabled.
    
    Returns:
        list[SSOProviderPublic]: A list of provider descriptors, each containing `provider_name`, `scopes`, and a `login_url` to initiate OIDC login.
    """
    result = await db.execute(select(SSOConfig).where(SSOConfig.enabled == True))  # noqa: E712
    providers = result.scalars().all()
    return [
        SSOProviderPublic(
            provider_name=p.provider_name,
            scopes=p.scopes,
            login_url=f"/api/v1/auth/oidc/{p.provider_name}/login",  # relative — browser navigates here
        )
        for p in providers
    ]


@router.get("/{provider}/login", summary="Redirect to OIDC authorization endpoint")
async def oidc_login(
    provider: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """
    Initiates an OIDC authorization request by redirecting the client to the provider's authorization endpoint.
    
    Generates PKCE `state`, `code_verifier`, and `code_challenge`, stores the `state` mapping to `{"verifier", "redirect_uri"}` in Redis with a TTL of 300 seconds (Redis failures are logged and do not stop the flow), then constructs the provider authorization URL with required query parameters and returns a 302 redirect to it.
    
    Parameters:
        provider (str): Name of the configured OIDC provider to use (used to load the enabled provider configuration and to build the canonical callback URI).
    
    Returns:
        RedirectResponse: A 302 redirect to the provider's authorization endpoint containing `response_type=code`, client credentials, `redirect_uri`, `scope`, `state`, and PKCE parameters (`code_challenge` and `code_challenge_method=S256`).
    """
    cfg = await _get_provider(db, provider)

    # Generate PKCE state and code_verifier
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    # RFC 7636 S256: BASE64URL(SHA256(code_verifier)) — no padding
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    # Construct an absolute callback URI — OIDC providers require a full URL
    # that matches the registered redirect URI exactly (scheme + host + path).
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    canonical_callback = f"{base}/api/v1/auth/oidc/{provider}/callback"

    # Store state → (code_verifier, redirect_uri) in Redis with TTL
    try:
        import json as _json
        redis = await get_redis()
        await redis.setex(
            f"oidc:state:{state}",
            _PKCE_TTL,
            _json.dumps({"verifier": code_verifier, "redirect_uri": canonical_callback}),
        )
    except Exception as exc:
        logger.warning("Redis unavailable for PKCE state storage: %s", exc)

    callback_uri = canonical_callback

    params = {
        "response_type": "code",
        "client_id": cfg.client_id,
        "redirect_uri": callback_uri,
        "scope": cfg.scopes,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    authorization_url = cfg.authorization_endpoint + "?" + urllib.parse.urlencode(params)
    return RedirectResponse(url=authorization_url, status_code=302)


@router.get("/{provider}/callback", summary="OIDC callback — exchange code for tokens")
async def oidc_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    response: Response = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """
    Handle the OIDC provider callback: exchange the authorization code for tokens, extract a username from the ID token or userinfo endpoint, issue an application JWT as an HTTP-only cookie, and redirect the client to "/".
    
    Parameters:
        provider (str): Registered provider name used to load provider configuration.
        code (str): Authorization code returned by the IdP.
        state (str): PKCE/state value used to retrieve the stored code verifier and original redirect URI.
        response (Response | None): Optional FastAPI Response (unused; present for dependency injection compatibility).
    
    Returns:
        RedirectResponse: A 302 redirect to "/" with an `access_token` HTTP-only cookie set for the authenticated user.
    
    Raises:
        HTTPException: 502 if token exchange with the IdP fails; 401 if a username cannot be extracted from tokens/userinfo.
    """
    cfg = await _get_provider(db, provider)

    # Retrieve code_verifier and stored redirect_uri from Redis
    code_verifier = None
    _base = settings.PUBLIC_BASE_URL.rstrip("/")
    callback_uri = f"{_base}/api/v1/auth/oidc/{provider}/callback"
    try:
        import json as _json
        redis = await get_redis()
        stored = await redis.get(f"oidc:state:{state}")
        if stored:
            raw = stored.decode() if isinstance(stored, bytes) else stored
            try:
                pkce_data = _json.loads(raw)
                code_verifier = pkce_data.get("verifier")
                callback_uri = pkce_data.get("redirect_uri", callback_uri)
            except Exception:
                code_verifier = raw  # legacy plain-string fallback
            await redis.delete(f"oidc:state:{state}")
    except Exception as exc:
        logger.warning("Redis lookup for OIDC state failed: %s", exc)

    # Exchange code for tokens — redirect_uri must exactly match what was sent to IdP
    token_payload: dict = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": callback_uri,
        "client_id": cfg.client_id,
        "client_secret": cfg.client_secret,
    }
    if code_verifier:
        token_payload["code_verifier"] = code_verifier

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            cfg.token_endpoint,
            data=token_payload,
            headers={"Accept": "application/json"},
        )
    if token_resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Token exchange failed: {token_resp.text[:200]}",
        )
    token_data = token_resp.json()
    id_token = token_data.get("id_token")
    access_token_ext = token_data.get("access_token")

    # Extract user info from id_token or userinfo endpoint
    username: Optional[str] = None
    email: Optional[str] = None

    if id_token and cfg.jwks_uri:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                jwks_resp = await client.get(cfg.jwks_uri)
            jwks = jwks_resp.json()
            claims = jwt.decode(
                id_token,
                jwks,
                algorithms=["RS256", "ES256"],
                options={"verify_aud": False},
            )
            username = claims.get("preferred_username") or claims.get("sub")
            email = claims.get("email")
        except JWTError as exc:
            logger.warning("ID token validation failed: %s", exc)

    # Fall back to userinfo endpoint
    if not username and access_token_ext:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                userinfo_resp = await client.get(
                    cfg.userinfo_endpoint,
                    headers={"Authorization": f"Bearer {access_token_ext}"},
                )
            userinfo = userinfo_resp.json()
            username = userinfo.get("preferred_username") or userinfo.get("sub") or userinfo.get("email")
            email = userinfo.get("email")
        except Exception as exc:
            logger.warning("Userinfo fetch failed: %s", exc)

    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not extract username from OIDC tokens",
        )

    # Issue SiemLess JWT cookie
    siemless_token = create_access_token(subject=username)
    redirect = RedirectResponse(url="/", status_code=302)
    redirect.set_cookie(
        key="access_token",
        value=siemless_token,
        httponly=True,
        samesite="lax",
        secure=False,  # Set True in production behind HTTPS
        max_age=3600,
    )
    logger.info("OIDC login successful: user=%s provider=%s", username, provider)
    return redirect


# ---------------------------------------------------------------------------
# Admin endpoints (require authentication)
# ---------------------------------------------------------------------------

@router.get("/configs", response_model=list[SSOConfigRead], summary="List SSO configs (admin)")
async def list_configs(
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_user),
) -> list[SSOConfigRead]:
    """
    List all stored SSO provider configurations with sensitive fields masked.
    
    Returns:
        configs (list[SSOConfigRead]): A list of read models for each SSO configuration; secret or sensitive fields are masked.
    """
    result = await db.execute(select(SSOConfig))
    configs = result.scalars().all()
    return [SSOConfigRead.from_orm_masked(c) for c in configs]


@router.post(
    "/configs",
    response_model=SSOConfigRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create SSO config (admin)",
)
async def create_config(
    payload: SSOConfigCreate,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_user),
) -> SSOConfigRead:
    """
    Create a new SSO provider configuration and persist it to the database.
    
    The new record is assigned a generated UUID for its `id`. Sensitive fields in the returned model are masked.
    
    Parameters:
        payload (SSOConfigCreate): Data for the new SSO configuration.
    
    Returns:
        SSOConfigRead: The created configuration record with sensitive fields masked.
    """
    import uuid as _uuid
    cfg = SSOConfig(
        id=str(_uuid.uuid4()),
        **payload.model_dump(),
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return SSOConfigRead.from_orm_masked(cfg)


@router.put("/configs/{config_id}", response_model=SSOConfigRead, summary="Update SSO config (admin)")
async def update_config(
    config_id: str,
    payload: SSOConfigUpdate,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_user),
) -> SSOConfigRead:
    """
    Update an existing SSO provider configuration with the values provided in `payload`.
    
    Parameters:
        config_id (str): UUID of the SSO configuration to update.
        payload (SSOConfigUpdate): Fields to update; only attributes with non-None values will be applied.
    
    Returns:
        SSOConfigRead: The updated configuration as a read model with sensitive fields masked.
    
    Raises:
        HTTPException: 404 if no configuration with `config_id` is found.
    """
    result = await db.execute(select(SSOConfig).where(SSOConfig.id == config_id))
    cfg = result.scalar_one_or_none()
    if cfg is None:
        raise HTTPException(status_code=404, detail="SSO config not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(cfg, field, value)

    await db.commit()
    await db.refresh(cfg)
    return SSOConfigRead.from_orm_masked(cfg)


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete SSO config (admin)")
async def delete_config(
    config_id: str,
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_user),
) -> None:
    """
    Delete an SSO provider configuration by its ID.
    
    Parameters:
        config_id (str): UUID string of the SSO configuration to remove.
    
    Raises:
        HTTPException: 404 if no SSO configuration with the given `config_id` exists.
    """
    result = await db.execute(select(SSOConfig).where(SSOConfig.id == config_id))
    cfg = result.scalar_one_or_none()
    if cfg is None:
        raise HTTPException(status_code=404, detail="SSO config not found")
    await db.delete(cfg)
    await db.commit()
