import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

_bearer = HTTPBearer(auto_error=False)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(
        {"sub": subject, "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _try_decode_jwt(token: str) -> Optional[str]:
    """Return username from a valid JWT, or None if it is not a JWT."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub") or None
    except JWTError:
        return None


async def _lookup_api_token(token: str) -> Optional[str]:
    """Return the username associated with a raw API token, or None."""
    from app.database import AsyncSessionLocal
    from app.models.rbac import APIToken

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(APIToken).where(APIToken.token_hash == token_hash)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            if row.expires_at and row.expires_at < datetime.now(timezone.utc):
                return None
            return row.username
    except Exception:
        return None


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> str:
    """Authenticate via JWT (cookie or Bearer header) or a hashed API token."""
    raw_token: Optional[str] = None

    if credentials:
        raw_token = credentials.credentials
    else:
        raw_token = request.cookies.get("access_token")

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Try JWT first (fast path — no DB hit)
    username = _try_decode_jwt(raw_token)
    if username:
        return username

    # Fall back to API token lookup (DB hit, but only when JWT decode fails)
    username = await _lookup_api_token(raw_token)
    if username:
        return username

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
