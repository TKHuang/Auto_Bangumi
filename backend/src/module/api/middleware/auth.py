"""JWT authentication middleware."""
from typing import cast

from fastapi import Cookie, HTTPException, status

from module.security.jwt import decode_access_token


async def get_current_user(token: str | None = Cookie(None)) -> str:
    """Extract and validate JWT from cookie.
    
    Returns username if valid, raises 401 otherwise.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = decode_access_token(token)
        username = payload.get("sub")
        if not username or not isinstance(username, str):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        return cast(str, username)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
