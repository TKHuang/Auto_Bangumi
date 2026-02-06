"""RSS refresh scheduled job.

Periodically refreshes all enabled RSS feeds at configured interval.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ...conf import settings
from ...database import get_db_session
from ...services.downloader import create_downloader
from ...services.rss_engine import RSSEngine

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def rss_refresh_job() -> None:
    """Refresh all enabled RSS feeds.

    Registered with scheduler at settings.program.rss_time interval (default 900s).
    Calls rss_engine.refresh_all_rss() with error handling.
    Errors are logged but don't crash the scheduler.
    """
    try:
        # Get database session
        async_session_gen = get_db_session()
        session: AsyncSession = await async_session_gen.__anext__()

        try:
            # Create downloader client with session
            downloader = create_downloader(settings, session=session)

            # Refresh all RSS feeds
            await RSSEngine.refresh_all_rss(session, downloader)

            logger.info("RSS refresh job completed successfully")

        finally:
            # Clean up session
            await session.close()

    except Exception as e:
        logger.exception(f"Error in RSS refresh job: {e}")
        # Don't re-raise - let scheduler continue
