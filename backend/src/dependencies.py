"""FastAPI dependency injection functions.

This module provides dependency functions for:
- Database session management
- User authentication
- Downloader instances
- Configuration singleton
"""

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from module.api.middleware.auth import get_current_user as _get_current_user
from module.conf import Config, settings
from module.database.engine import get_db_session as _get_db_session
from module.services.downloader.factory import create_downloader
from module.services.downloader.interface import DownloaderProtocol


# Database session dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield async database session.
    
    Usage:
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async for session in _get_db_session():
        yield session


# Authentication dependency
async def get_current_user(token: str | None = None) -> str:
    """Get authenticated username from JWT token.
    
    Raises 401 if token is invalid or missing.
    
    Usage:
        @router.get("/example")
        async def example(username: str = Depends(get_current_user)):
            ...
    """
    # Re-export from middleware for convenience
    return await _get_current_user(token)


# Downloader singleton (lazy-initialized)
_downloader_instance: DownloaderProtocol | None = None


def get_downloader() -> DownloaderProtocol:
    """Get downloader instance (singleton).
    
    Lazily creates downloader on first call using current config.
    
    Usage:
        @router.get("/example")
        async def example(downloader: DownloaderProtocol = Depends(get_downloader)):
            ...
    """
    global _downloader_instance
    if _downloader_instance is None:
        _downloader_instance = create_downloader(settings)
    return _downloader_instance


def reset_downloader() -> None:
    """Reset downloader singleton (used after config updates)."""
    global _downloader_instance
    _downloader_instance = None


# Config singleton dependency
def get_settings() -> Config:
    """Get configuration singleton.
    
    Usage:
        @router.get("/example")
        async def example(config: Config = Depends(get_settings)):
            ...
    """
    return settings
