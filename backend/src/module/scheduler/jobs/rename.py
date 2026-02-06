"""Rename scheduled job.

Periodically renames completed torrents at configured interval.
Uses asyncio.Lock to prevent concurrent rename operations.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from module.conf import settings
from module.database import get_db_session
from module.services.downloader import create_downloader
from module.services.renamer import RenamerService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Global lock to prevent concurrent rename operations
_rename_lock = asyncio.Lock()


async def rename_job() -> None:
    """Rename all completed torrents.

    Registered with scheduler at settings.program.rename_time interval (default 60s).
    Calls renamer.rename_all() with error handling.
    Uses asyncio.Lock to prevent concurrent renames.
    Errors are logged but don't crash the scheduler.
    """
    # Acquire lock to prevent concurrent renames
    if _rename_lock.locked():
        logger.debug("Rename job already running, skipping this cycle")
        return

    async with _rename_lock:
        try:
            # Get database session
            async_session_gen = get_db_session()
            session: AsyncSession = await async_session_gen.__anext__()

            try:
                # Create renamer service
                rename_method = settings.bangumi_manage.rename_method
                renamer = RenamerService(session, rename_method=rename_method)

                # Create downloader client with session
                downloader = create_downloader(settings, session=session)

                # Rename all completed torrents
                await renamer.rename_all(downloader)

                logger.info("Rename job completed successfully")

            finally:
                # Clean up session
                await session.close()

        except Exception as e:
            logger.exception(f"Error in rename job: {e}")
            # Don't re-raise - let scheduler continue
