from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config import settings
from app.deps import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


@router.post("/login", response_model=TokenResponse, summary="Obtain access token")
async def login(body: LoginRequest) -> TokenResponse:
    if (
        body.username != settings.ADMIN_USERNAME
        or body.password != settings.ADMIN_PASSWORD
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(body.username)
    return TokenResponse(access_token=token, username=body.username)


@router.get("/me", summary="Current user info")
async def me(username: str = Depends(get_current_user)) -> dict:
    return {"username": username}
