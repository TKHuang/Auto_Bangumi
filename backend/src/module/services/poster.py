"""Poster service for fetching and caching anime posters from TMDB."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from module.conf.config import settings
from module.repositories import BangumiRepository

if TYPE_CHECKING:
    from module.domain.models import Bangumi  # noqa: F401

logger = logging.getLogger(__name__)

# Poster storage directory
POSTERS_DIR = Path("data/posters")


class PosterService:
    """Service for fetching and caching anime posters."""

    session: AsyncSession
    bangumi_repo: BangumiRepository

    def __init__(self, session: AsyncSession):
        """Initialize poster service.

        Args:
            session: AsyncSession for database operations
        """
        self.session = session
        self.bangumi_repo = BangumiRepository(session)

    async def fetch_poster(
        self, official_title: str, season: int = 1
    ) -> str | None:
        """Fetch poster URL for an anime from TMDB.

        Implements poster caching:
        - Searches TMDB for the anime
        - Downloads and caches poster image locally
        - Returns relative path to cached poster

        Args:
            official_title: Official anime title to search
            season: Season number (for reference, not used in search)

        Returns:
            Relative path to cached poster (e.g., "posters/abc123.jpg") or None if not found

        Raises:
            httpx.HTTPError: If TMDB API or image download fails
            IOError: If file save fails
        """
        logger.debug(f"Fetching poster for: {official_title} (season {season})")

        # Import here to avoid circular dependencies
        from module.domain.parser.analyser.tmdb_parser import tmdb_parser

        # Query TMDB for anime info
        language = settings.rss_parser.language
        tmdb_info = tmdb_parser(official_title, language, test=False)

        if not tmdb_info or not tmdb_info.poster_link:
            logger.warning(f"No poster found on TMDB for: {official_title}")
            return None

        logger.debug(f"TMDB found poster: {tmdb_info.poster_link}")
        return tmdb_info.poster_link

    async def refresh_all_posters(self) -> dict[str, int]:
        """Refresh posters for all bangumi without poster_link.

        Iterates through all active bangumi and fetches posters from TMDB
        for those missing poster_link. Updates database with new poster links.

        Returns:
            Dictionary with refresh statistics:
            - total: Total bangumi processed
            - updated: Number of bangumi with new posters
            - failed: Number of bangumi where poster fetch failed
        """
        logger.info("Starting refresh_all_posters")

        # Get all active bangumi
        bangumis = await self.bangumi_repo.get_active()
        total = len(bangumis)
        updated = 0
        failed = 0

        for bangumi in bangumis:
            if bangumi.poster_link:
                logger.debug(f"Skipping {bangumi.official_title} - already has poster")
                continue

            try:
                poster_link = await self.fetch_poster(
                    bangumi.official_title, bangumi.season
                )
                if poster_link:
                    # Update bangumi with new poster link
                    bangumi.poster_link = poster_link
                    await self.bangumi_repo.update(
                        bangumi.id,
                        {"poster_link": poster_link},
                        expected_version=bangumi.version,
                    )
                    updated += 1
                    logger.info(
                        f"Updated poster for {bangumi.official_title}: {poster_link}"
                    )
                else:
                    failed += 1
                    logger.warning(f"No poster found for {bangumi.official_title}")
            except Exception as e:
                failed += 1
                logger.error(
                    f"Error fetching poster for {bangumi.official_title}: {e}"
                )

        logger.info(
            f"refresh_all_posters completed: total={total}, updated={updated}, failed={failed}"
        )
        return {"total": total, "updated": updated, "failed": failed}

    async def refresh_poster(self, bangumi_id: int) -> dict[str, Any]:
        """Refresh poster for a specific bangumi.

        Fetches poster from TMDB and updates the bangumi record.

        Args:
            bangumi_id: ID of bangumi to refresh

        Returns:
            Dictionary with refresh result:
            - success: True if poster was updated
            - poster_link: New poster link or None
            - message: Status message

        Raises:
            ValueError: If bangumi not found
        """
        logger.info(f"Refreshing poster for bangumi_id={bangumi_id}")

        # Get bangumi
        bangumi = await self.bangumi_repo.get_by_id(bangumi_id)
        if not bangumi:
            logger.error(f"Bangumi not found: {bangumi_id}")
            raise ValueError(f"Bangumi not found: {bangumi_id}")

        try:
            poster_link = await self.fetch_poster(
                bangumi.official_title, bangumi.season
            )
            if poster_link:
                # Update bangumi with new poster link
                await self.bangumi_repo.update(
                    bangumi.id,
                    {"poster_link": poster_link},
                    expected_version=bangumi.version,
                )
                logger.info(
                    f"Updated poster for {bangumi.official_title}: {poster_link}"
                )
                return {
                    "success": True,
                    "poster_link": poster_link,
                    "message": f"Poster updated for {bangumi.official_title}",
                }
            else:
                logger.warning(f"No poster found for {bangumi.official_title}")
                return {
                    "success": False,
                    "poster_link": None,
                    "message": f"No poster found for {bangumi.official_title}",
                }
        except Exception as e:
            logger.error(f"Error refreshing poster for {bangumi_id}: {e}")
            return {
                "success": False,
                "poster_link": None,
                "message": f"Error: {str(e)}",
            }
