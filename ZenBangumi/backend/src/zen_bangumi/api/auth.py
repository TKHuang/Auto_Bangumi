from datetime import timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from zen_bangumi.api.middleware.auth import get_current_user
from zen_bangumi.api.models import (
    LoginRequest,
    LoginResponse,
    MessageResponse,
    UpdatePasswordRequest,
)
from zen_bangumi.domain.models.user import User
from zen_bangumi.services.auth import create_access_token, decode_access_token
from zen_bangumi.services.user import authenticate, update_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

COOKIE_MAX_AGE = 86400


def get_session(request: Request) -> AsyncSession:
    return request.state.db


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    user = await authenticate(body.username, body.password, session)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    
    token = create_access_token(user.id, timedelta(seconds=COOKIE_MAX_AGE))
    
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
    )
    
    return LoginResponse(message="Login successful", username=user.username)


@router.post("/logout", response_model=MessageResponse, status_code=status.HTTP_200_OK)
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    return MessageResponse(message="Logout successful")


@router.post("/refresh", response_model=MessageResponse, status_code=status.HTTP_200_OK)
async def refresh(
    response: Response,
    access_token: str | None = Cookie(None),
):
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - missing token",
        )
    
    try:
        payload = decode_access_token(access_token)
        user_id = payload["user_id"]
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}",
        )
    
    new_token = create_access_token(user_id, timedelta(seconds=COOKIE_MAX_AGE))
    
    response.set_cookie(
        key="access_token",
        value=new_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
    )
    
    return MessageResponse(message="Token refreshed successfully")


@router.put("/update", response_model=MessageResponse, status_code=status.HTTP_200_OK)
async def update_user_password(
    body: UpdatePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        await update_password(
            current_user.id,
            body.old_password,
            body.new_password,
            session,
        )
        await session.commit()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    
    return MessageResponse(message="Password updated successfully")
