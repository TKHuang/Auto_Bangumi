"""Rename scheduled job.

Periodically renames completed torrents at configured interval.
Uses asyncio.Lock to prevent concurrent rename operations.
"""

from __future__ import annotations

import asyncio
import logging

from module.conf import settings
from module.database.engine import AsyncSessionLocal
from module.services.downloader import create_downloader
from module.services.renamer import RenamerService

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
            # Use proper async context manager for session lifecycle.
            # The renamer passes cloud_paths to torrents_info, so the
            # downloader won't do DB queries during the rename cycle
            # (prevents session conflicts with concurrent scheduler jobs).
            async with AsyncSessionLocal() as session:
                rename_method = settings.bangumi_manage.rename_method
                renamer = RenamerService(session, rename_method=rename_method)

                downloader = create_downloader(settings, session=session)

                await renamer.rename_all(downloader)

                logger.info("Rename job completed successfully")

        except Exception as e:
            logger.exception(f"Error in rename job: {e}")
            # Don't re-raise - let scheduler continue
