"""Poster service: refresh a bangumi poster from Mikan, then TMDB."""

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from module.conf.config import settings
from module.domain.bangumi_view import effective_season, effective_title
from module.domain.parser.title_parser import TitleParser
from module.repositories import BangumiRepository, RSSRepository, TorrentRepository

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
        self.rss_repo = RSSRepository(session)
        self.torrent_repo = TorrentRepository(session)

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
        tmdb_info = await asyncio.to_thread(tmdb_parser, official_title, language)

        if not tmdb_info or not tmdb_info.poster_link:
            logger.warning(f"No poster found on TMDB for: {official_title}")
            return None

        logger.debug(f"TMDB found poster: {tmdb_info.poster_link}")
        return tmdb_info.poster_link

    async def refresh_poster(self, bangumi_id: int) -> dict[str, Any]:
        """Refresh poster for a specific bangumi.

        Tries the Mikan episode page of the bangumi's newest torrent first
        (Mikan RSS only), then TMDB. Saves the first poster found.

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

        _title = effective_title(bangumi)
        _season = effective_season(bangumi)
        try:
            poster_link = await self._fetch_mikan_poster(bangumi, _title)
            if not poster_link:
                poster_link = await self.fetch_poster(_title, _season)
            if poster_link:
                await self.bangumi_repo.update_simple(
                    bangumi.id, {"poster_link": poster_link}
                )
                logger.info(f"Updated poster for {_title}: {poster_link}")
                return {
                    "success": True,
                    "poster_link": poster_link,
                    "message": f"Poster updated for {_title}",
                }
            else:
                logger.warning(f"No poster found for {_title}")
                return {
                    "success": False,
                    "poster_link": None,
                    "message": f"No poster found for {_title}",
                }
        except Exception as e:
            logger.error(f"Error refreshing poster for {bangumi_id}: {e}")
            return {
                "success": False,
                "poster_link": None,
                "message": f"Error: {str(e)}",
            }

    async def _fetch_mikan_poster(self, bangumi, title: str) -> str | None:
        if not bangumi.rss_id:
            return None
        rss = await self.rss_repo.get_by_id(bangumi.rss_id)
        if not rss or rss.parser != "mikan":
            return None
        torrent = await self.torrent_repo.get_by_bangumi_with_homepage(bangumi.id)
        if not torrent or not torrent.homepage:
            return None
        try:
            result = await asyncio.to_thread(
                TitleParser().mikan_parser_with_rss, torrent.homepage
            )
        except Exception as e:
            logger.warning(f"[Poster] Mikan parser failed for {title}: {e}")
            return None
        return result.poster_link or None
