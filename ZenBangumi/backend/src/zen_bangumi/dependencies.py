"""FastAPI dependencies for dependency injection."""

from fastapi import Request

from zen_bangumi.api.middleware.auth import get_current_user as _get_current_user
from zen_bangumi.config.loader import ConfigLoader, ZenBangumiConfig
from zen_bangumi.domain.models.user import User


async def get_session(request: Request):
    """Get database session from request state.
    
    The session is injected by DBSessionMiddleware during request lifecycle.
    """
    return request.state.db


async def get_config() -> ZenBangumiConfig:
    """Get global application configuration."""
    return ConfigLoader.load()


async def get_current_user(request: Request) -> User:
    """Get authenticated user from JWT token in cookie.
    
    Delegates to auth middleware's get_current_user which:
    - Extracts JWT from HTTP-only cookie
    - Validates and decodes token
    - Fetches user from database
    
    Raises HTTPException(401) if not authenticated or token invalid.
    """
    return await _get_current_user(request)
