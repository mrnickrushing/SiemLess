import logging
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.config import settings
from app.deps import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Brute-force protection
# In-memory store: tracks failed login attempts per username.
# State resets on process restart — acceptable for single-process deployments.
# For multi-process/multi-node setups, replace with a Redis-backed counter.
# ---------------------------------------------------------------------------
_LOGIN_FAILURE_WINDOW = 300   # seconds to look back when counting failures
_LOGIN_MAX_FAILURES = 5       # max failures before lockout (reduced from 10)
_LOGIN_LOCKOUT_DURATION = 900 # seconds to lock out after exceeding threshold
_failed_attempts: dict[str, list[float]] = defaultdict(list)
_lockout_until: dict[str, float] = {}  # username -> monotonic unlock time


def _check_rate_limit(username: str, client_ip: str) -> None:
    """
    Raise 429 if:
      - The username is currently locked out, OR
      - The username has hit _LOGIN_MAX_FAILURES within _LOGIN_FAILURE_WINDOW
    On lockout threshold breach, set a hard lockout for _LOGIN_LOCKOUT_DURATION.
    """
    now = time.monotonic()

    # Hard lockout check
    unlock_at = _lockout_until.get(username, 0)
    if now < unlock_at:
        retry_after = int(unlock_at - now)
        logger.warning(
            "Login blocked (lockout active) for user '%s' from %s — %ds remaining",
            username,
            client_ip,
            retry_after,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    # Sliding window check
    cutoff = now - _LOGIN_FAILURE_WINDOW
    recent = [t for t in _failed_attempts[username] if t >= cutoff]
    if len(recent) >= _LOGIN_MAX_FAILURES:
        _lockout_until[username] = now + _LOGIN_LOCKOUT_DURATION
        _failed_attempts[username] = []  # reset window after lockout
        logger.warning(
            "Login lockout triggered for user '%s' from %s — locked for %ds",
            username,
            client_ip,
            _LOGIN_LOCKOUT_DURATION,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Account locked for {_LOGIN_LOCKOUT_DURATION // 60} minutes.",
            headers={"Retry-After": str(_LOGIN_LOCKOUT_DURATION)},
        )


def _record_failure(username: str) -> None:
    """Record a failed attempt timestamp for the sliding window."""
    now = time.monotonic()
    cutoff = now - _LOGIN_FAILURE_WINDOW
    recent = [t for t in _failed_attempts[username] if t >= cutoff]
    recent.append(now)
    _failed_attempts[username] = recent


def _clear_rate_limit(username: str) -> None:
    """Clear all failure state on successful login."""
    _failed_attempts.pop(username, None)
    _lockout_until.pop(username, None)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    username: str


@router.post("/login", response_model=LoginResponse, summary="Obtain session cookie")
async def login(body: LoginRequest, request: Request, response: Response) -> LoginResponse:
    if settings.ADMIN_PASSWORD is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: ADMIN_PASSWORD not set",
        )

    client_ip = request.client.host if request.client else "unknown"

    # Rate-limit check BEFORE credential evaluation to prevent timing oracle
    _check_rate_limit(body.username, client_ip)

    if (
        body.username != settings.ADMIN_USERNAME
        or body.password != settings.ADMIN_PASSWORD
    ):
        _record_failure(body.username)
        logger.warning(
            "Failed login for user '%s' from %s",
            body.username,
            client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    _clear_rate_limit(body.username)
    token = create_access_token(body.username)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    logger.info("Successful login for user '%s' from %s", body.username, client_ip)
    return LoginResponse(username=body.username)


@router.post("/logout", summary="Clear session cookie")
async def logout(response: Response) -> dict:
    response.delete_cookie(key="access_token", path="/", samesite="lax")
    return {"detail": "Logged out"}


@router.get("/me", summary="Current user info")
async def me(username: str = Depends(get_current_user)) -> dict:
    return {"username": username}
