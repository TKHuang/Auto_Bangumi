"""Async adapters for sync search and RSS analysis operations.

Provides thin async wrappers around SearchTorrent and RSSAnalyser
using asyncio.to_thread for non-blocking execution.
"""

import asyncio
from typing import Any, Optional

from module.models import Bangumi, RSSItem, Torrent
from module.rss import RSSAnalyser
from module.searcher import SearchTorrent


class AsyncSearchAdapter:
    """Async wrapper around sync SearchTorrent."""

    @staticmethod
    async def search_season(data: Bangumi, site: str = "mikan") -> list[Torrent]:
        """Search for torrents matching a bangumi season.
        
        Args:
            data: Bangumi object with metadata
            site: Search provider (default: 'mikan')
            
        Returns:
            List of matching Torrent objects
        """
        def _sync():
            with SearchTorrent() as st:
                return st.search_season(data, site)
        return await asyncio.to_thread(_sync)

    @staticmethod
    async def get_torrents(url: str, filter_pattern: str = "") -> list[Torrent]:
        """Get torrents from RSS URL with optional filtering.
        
        Args:
            url: RSS URL to fetch torrents from
            filter_pattern: Regex pattern to filter torrents
            
        Returns:
            List of Torrent objects
        """
        def _sync():
            with SearchTorrent() as st:
                return st.get_torrents(url, filter_pattern)
        return await asyncio.to_thread(_sync)


class AsyncRSSAnalyserAdapter:
    """Async wrapper around sync RSSAnalyser."""

    def __init__(self):
        """Initialize with a fresh RSSAnalyser instance."""
        self._analyser = RSSAnalyser()

    async def link_to_data(
        self,
        rss: RSSItem,
        official_title: Optional[str] = None,
        season: Optional[int] = None,
        group_name: Optional[str] = None,
    ) -> Bangumi:
        """Convert an RSS link to a Bangumi object.
        
        Args:
            rss: RSSItem to parse
            official_title: Optional manual title override
            season: Optional manual season override
            group_name: Optional manual group name override
            
        Returns:
            Bangumi object or ResponseModel with error details
        """
        return await asyncio.to_thread(
            self._analyser.link_to_data, rss, official_title, season, group_name
        )

    async def torrents_to_data(
        self, torrents: list[Torrent], rss: RSSItem, full_parse: bool = True
    ) -> list[Bangumi]:
        """Convert multiple torrents to Bangumi objects.
        
        Args:
            torrents: List of Torrent objects to parse
            rss: RSSItem containing parser configuration
            full_parse: If True, parse all torrents. If False, return first match.
            
        Returns:
            List of Bangumi objects
        """
        return await asyncio.to_thread(
            self._analyser.torrents_to_data, torrents, rss, full_parse
        )

    async def get_rss_torrents(
        self, url: str, full_parse: bool = False, apply_filter: bool = True
    ) -> list[Torrent]:
        """Fetch and parse torrents from RSS URL.
        
        Args:
            url: RSS URL to fetch from
            full_parse: If True, fetch all torrents. If False, filter out batch releases.
            apply_filter: If True, apply global filter patterns.
            
        Returns:
            List of Torrent objects
        """
        return await asyncio.to_thread(
            self._analyser.get_rss_torrents, url, full_parse, apply_filter
        )

    async def analyse_torrents(
        self, rss: RSSItem, _filter: Optional[str] = None, title_raw: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Analyse torrents from RSS with optional filtering.
        
        Args:
            rss: RSS item to fetch torrents from
            _filter: Regex pattern to exclude torrents
            title_raw: If provided, only include torrents matching this title_raw
            
        Returns:
            List of torrent analysis dictionaries
        """
        return await asyncio.to_thread(
            self._analyser.analyse_torrents, rss, _filter, title_raw
        )
