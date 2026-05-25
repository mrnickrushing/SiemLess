import logging
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.config import settings
from app.deps import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# In-memory brute-force tracking: username -> list of failure timestamps
_LOGIN_FAILURE_WINDOW = 300   # seconds
_LOGIN_MAX_FAILURES = 10      # lockout threshold within window
_failed_attempts: dict[str, list[float]] = defaultdict(list)


def _check_and_record_failure(username: str) -> None:
    """Raise 429 if too many recent failures; otherwise record this failure."""
    now = time.monotonic()
    cutoff = now - _LOGIN_FAILURE_WINDOW
    attempts = [t for t in _failed_attempts[username] if t >= cutoff]
    if len(attempts) >= _LOGIN_MAX_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(_LOGIN_FAILURE_WINDOW)},
        )
    attempts.append(now)
    _failed_attempts[username] = attempts


def _clear_failures(username: str) -> None:
    _failed_attempts.pop(username, None)


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

    _check_and_record_failure(body.username)

    if (
        body.username != settings.ADMIN_USERNAME
        or body.password != settings.ADMIN_PASSWORD
    ):
        logger.warning(
            "Failed login attempt for user '%s' from %s",
            body.username,
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    _clear_failures(body.username)
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
    return LoginResponse(username=body.username)


@router.post("/logout", summary="Clear session cookie")
async def logout(response: Response) -> dict:
    response.delete_cookie(key="access_token", path="/", samesite="lax")
    return {"detail": "Logged out"}


@router.get("/me", summary="Current user info")
async def me(username: str = Depends(get_current_user)) -> dict:
    return {"username": username}
