"""Auth API endpoints."""
import os
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from module.api.middleware.auth import get_current_user
from module.database.engine import get_db_session
from module.repositories.user import UserRepository
from module.security.jwt import create_access_token
from module.security.password import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db_session),
):
    """Login with username and password.
    
    Returns access_token, token_type, and expire timestamp.
    Sets HTTP-only cookie with token.
    """
    repo = UserRepository(session)
    user = await repo.get_by_username(form_data.username)

    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_access_token(
        username=form_data.username,
        expires_delta=timedelta(days=1),
    )

    expire_timestamp = int((timedelta(days=1).total_seconds()))

    response = JSONResponse(
        status_code=200,
        content={
            "access_token": token,
            "token_type": "bearer",
            "expire": expire_timestamp,
        },
    )
    _set_auth_cookie(response, token)
    return response


def _set_auth_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        max_age=86400,
        samesite="lax",
        secure=os.getenv("AB_SECURE_COOKIES", "").lower() in ("1", "true", "yes"),
    )


@router.get("/refresh_token")
async def refresh_token(
    current_user: str = Depends(get_current_user),
):
    token = create_access_token(
        username=current_user,
        expires_delta=timedelta(days=1),
    )

    expire_timestamp = int((timedelta(days=1).total_seconds()))

    response = JSONResponse(
        status_code=200,
        content={
            "access_token": token,
            "token_type": "bearer",
            "expire": expire_timestamp,
        },
    )
    _set_auth_cookie(response, token)
    return response


@router.get("/logout")
async def logout(
    current_user: str = Depends(get_current_user),
):
    response = JSONResponse(
        status_code=200,
        content={
            "msg_en": "Logout successfully.",
            "msg_zh": "登出成功。",
        },
    )
    response.delete_cookie(key="token")
    return response


@router.post("/update")
async def update_password(
    password_update: dict,
    current_user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    if "password" not in password_update:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="password field required",
        )

    new_password = password_update["password"]
    if not new_password or len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="password must be at least 8 characters",
        )

    repo = UserRepository(session)

    async with session.begin():
        password_hash = hash_password(new_password)
        user = await repo.get_by_username(current_user)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        await repo.update_password(user.id, password_hash)

    token = create_access_token(
        username=current_user,
        expires_delta=timedelta(days=1),
    )

    expire_timestamp = int((timedelta(days=1).total_seconds()))

    response = JSONResponse(
        status_code=200,
        content={
            "access_token": token,
            "token_type": "bearer",
            "expire": expire_timestamp,
            "message": "update success",
        },
    )
    _set_auth_cookie(response, token)
    return response
