"""Admin router — user/role management and API tokens."""
import hashlib
import logging
import secrets
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.rbac import APIToken, OrgUser

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


def _require_admin(username: str = Depends(get_current_user)) -> str:
    """Simple admin check — extend with RBAC if needed."""
    return username


@router.get("/users", summary="List org users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(_require_admin),
) -> list:
    result = await db.execute(select(OrgUser))
    return [_user_to_dict(u) for u in result.scalars()]


@router.post("/users", status_code=status.HTTP_201_CREATED, summary="Create org user")
async def create_user(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(_require_admin),
) -> dict:
    user = OrgUser(
        id=str(uuid.uuid4()),
        org_id=payload.get("org_id", "default"),
        username=payload["username"],
        email=payload.get("email"),
        role=payload.get("role", "analyst"),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _user_to_dict(user)


@router.patch("/users/{username}", summary="Update user role")
async def update_user(
    username: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _req_username: str = Depends(_require_admin),
) -> dict:
    result = await db.execute(select(OrgUser).where(OrgUser.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if "role" in payload:
        user.role = payload["role"]
    if "email" in payload:
        user.email = payload["email"]
    await db.commit()
    await db.refresh(user)
    return _user_to_dict(user)


@router.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    username: str,
    db: AsyncSession = Depends(get_db),
    _req_username: str = Depends(_require_admin),
) -> None:
    result = await db.execute(select(OrgUser).where(OrgUser.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()


@router.post("/tokens", status_code=status.HTTP_201_CREATED, summary="Issue API token")
async def create_token(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    req_username: str = Depends(_require_admin),
) -> dict:
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    token = APIToken(
        id=str(uuid.uuid4()),
        username=payload.get("username", req_username),
        token_hash=token_hash,
        description=payload.get("description"),
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    # Return raw token only once
    return {
        **_token_to_dict(token),
        "raw_token": raw_token,  # Only shown once
    }


@router.get("/tokens", summary="List API tokens")
async def list_tokens(
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(_require_admin),
) -> list:
    result = await db.execute(select(APIToken))
    return [_token_to_dict(t) for t in result.scalars()]


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(
    token_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(_require_admin),
) -> None:
    result = await db.execute(select(APIToken).where(APIToken.id == token_id))
    token = result.scalar_one_or_none()
    if token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    await db.delete(token)
    await db.commit()


def _user_to_dict(u: OrgUser) -> dict:
    return {
        "id": u.id,
        "org_id": u.org_id,
        "username": u.username,
        "email": u.email,
        "role": u.role,
        "created_at": u.created_at.isoformat(),
    }


def _token_to_dict(t: APIToken) -> dict:
    return {
        "id": t.id,
        "username": t.username,
        "description": t.description,
        "expires_at": t.expires_at.isoformat() if t.expires_at else None,
        "created_at": t.created_at.isoformat(),
    }
