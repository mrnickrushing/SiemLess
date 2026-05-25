from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.config import settings
from app.deps import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    username: str


@router.post("/login", response_model=LoginResponse, summary="Obtain session cookie")
async def login(body: LoginRequest, response: Response) -> LoginResponse:
    if settings.ADMIN_PASSWORD is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: ADMIN_PASSWORD not set",
        )
    if (
        body.username != settings.ADMIN_USERNAME
        or body.password != settings.ADMIN_PASSWORD
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
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
