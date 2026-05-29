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
from app.services.rbac import rbac_service

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


async def _require_admin(
    db: AsyncSession = Depends(get_db),
    username: str = Depends(get_current_user),
) -> str:
    """Reject non-admin authenticated users from admin endpoints.

    Returns:
        username (str): The authenticated admin's username.

    Raises:
        HTTPException: 403 if the user does not have the admin role.
    """
    if not await rbac_service.has_role(db, username, "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return username


@router.get("/users", summary="List org users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(_require_admin),
) -> list:
    """
    List all organization users.
    
    Returns:
        A list of dictionaries for each user with keys `id`, `org_id`, `username`, `email`, `role`, and `created_at` (ISO-8601 string).
    """
    result = await db.execute(select(OrgUser))
    return [_user_to_dict(u) for u in result.scalars()]


@router.post("/users", status_code=status.HTTP_201_CREATED, summary="Create org user")
async def create_user(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(_require_admin),
) -> dict:
    """
    Create a new OrgUser from the given payload and persist it to the database.
    
    Parameters:
        payload (dict): Payload containing user data. Required key: `"username"`.
            Optional keys:
            - `"org_id"` (str): Organization id; defaults to `"default"`.
            - `"email"` (str | None): User email.
            - `"role"` (str): User role; defaults to `"analyst"`.
    
    Returns:
        dict: Serialized user object containing `id`, `org_id`, `username`, `email`, `role`, and `created_at` (ISO-8601 string).
    """
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
    """
    Update an existing OrgUser's role and/or email.
    
    Parameters:
        username (str): Username of the OrgUser to update.
        payload (dict): Keys to update. Recognized keys:
            - "role": new role for the user.
            - "email": new email address for the user.
    
    Returns:
        dict: Serialized user containing `id`, `org_id`, `username`, `email`, `role`, and `created_at` (ISO-8601 string).
    
    Raises:
        HTTPException: 404 if no user exists with the given username.
    """
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
    """
    Delete the OrgUser with the given username from the database.
    
    Raises:
        HTTPException: 404 with detail "User not found" if no user exists with the provided username.
    """
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
    """
    Create a new API token for a user and return its metadata along with the raw token (shown once).
    
    Parameters:
        payload (dict): Optional keys:
            - "username" (str): Username to associate the token with; defaults to the requesting admin's username.
            - "description" (str): Human-readable description for the token.
        db (AsyncSession): Database session (dependency-injected).
        req_username (str): Requesting admin's username (dependency-injected).
    
    Returns:
        dict: A mapping containing the token record fields (`id`, `username`, `description`, `expires_at`, `created_at`) plus
        `raw_token` — the plain token value returned only on creation.
    """
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
    """
    List all stored API tokens.
    
    Returns:
        list: A list of token dictionaries with keys `id`, `username`, `description`, `expires_at` (ISO-8601 string or `None`), and `created_at` (ISO-8601 string).
    """
    result = await db.execute(select(APIToken))
    return [_token_to_dict(t) for t in result.scalars()]


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(
    token_id: str,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(_require_admin),
) -> None:
    """
    Revoke (delete) an API token identified by its ID.
    
    Parameters:
        token_id (str): The `APIToken.id` value of the token to remove.
    
    Raises:
        HTTPException: 404 error with detail "Token not found" if no token exists with the given ID.
    """
    result = await db.execute(select(APIToken).where(APIToken.id == token_id))
    token = result.scalar_one_or_none()
    if token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    await db.delete(token)
    await db.commit()


def _user_to_dict(u: OrgUser) -> dict:
    """
    Serialize an OrgUser into a JSON-serializable dictionary.
    
    Parameters:
        u (OrgUser): The OrgUser instance to serialize.
    
    Returns:
        dict: Dictionary containing the user's `id`, `org_id`, `username`, `email`, `role`, and `created_at` as an ISO-8601 string.
    """
    return {
        "id": u.id,
        "org_id": u.org_id,
        "username": u.username,
        "email": u.email,
        "role": u.role,
        "created_at": u.created_at.isoformat(),
    }


def _token_to_dict(t: APIToken) -> dict:
    """
    Serialize an APIToken model into a JSON-serializable dictionary.
    
    Parameters:
        t (APIToken): The API token model instance to serialize.
    
    Returns:
        dict: Dictionary with keys:
            - `id` (str): Token UUID.
            - `username` (str): Associated username.
            - `description` (str | None): Optional description.
            - `expires_at` (str | None): ISO-8601 timestamp if set, otherwise `None`.
            - `created_at` (str): ISO-8601 creation timestamp.
    """
    return {
        "id": t.id,
        "username": t.username,
        "description": t.description,
        "expires_at": t.expires_at.isoformat() if t.expires_at else None,
        "created_at": t.created_at.isoformat(),
    }
