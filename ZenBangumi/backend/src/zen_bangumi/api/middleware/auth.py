"""FastAPI authentication middleware and dependencies."""

from fastapi import Cookie, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from zen_bangumi.domain.models.user import User
from zen_bangumi.services.auth import decode_access_token


async def get_current_user(
    request: Request,
    access_token: str | None = Cookie(None),
) -> User:
    """FastAPI dependency that extracts and validates JWT from HTTP-only cookie.
    
    Reads JWT token from "access_token" cookie, validates it, and returns the
    authenticated user from database.
    
    Args:
        request: FastAPI request object (provides db session)
        access_token: JWT token from HTTP-only cookie
        
    Returns:
        Authenticated User instance
        
    Raises:
        HTTPException: 401 if token is missing, invalid, or expired
    """
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
    
    session: AsyncSession = request.state.db
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    return user
