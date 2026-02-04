"""Mikan anime scraper adapter for searching and fetching RSS feeds."""

import logging
from collections.abc import AsyncIterator

import feedparser
import httpx
from pydantic import BaseModel

from ...domain.parser.mikan_parser import (
    MikanBangumiInfo,
    SearchResult,
    parse_bangumi_page,
    parse_search_results,
)

logger = logging.getLogger(__name__)


class TorrentInfo(BaseModel):
    """Torrent entry from RSS feed."""

    name: str
    url: str
    size: str | None = None
    date: str | None = None


class MikanAdapter:
    """Mikan anime site scraper for search and RSS feeds."""

    BASE_URL: str = "https://mikanani.me"
    SEARCH_URL: str = f"{BASE_URL}/Home/Search"

    def __init__(self, timeout: float = 10.0):
        self.timeout: float = timeout

    async def search(self, keyword: str) -> AsyncIterator[SearchResult]:
        """Search for anime on Mikan and yield results.

        Args:
            keyword: Search keyword (anime title)

        Yields:
            SearchResult objects
        """
        url = self.SEARCH_URL
        params = {"searchstr": keyword}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()

                html = response.text
                results = parse_search_results(html, self.BASE_URL)

                for result in results:
                    yield result

        except httpx.HTTPError as e:
            logger.error(f"Failed to search Mikan for '{keyword}': {e}")
            raise

    async def get_bangumi_info(self, mikan_id: str) -> MikanBangumiInfo:
        """Fetch detailed bangumi information.

        Args:
            mikan_id: Mikan bangumi ID

        Returns:
            MikanBangumiInfo with title, RSS URL, poster, etc.

        Raises:
            httpx.HTTPError: If request fails
            ValueError: If parsing fails
        """
        url = f"{self.BASE_URL}/Home/Bangumi/{mikan_id}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=self.timeout)
                response.raise_for_status()

                html = response.text
                info = parse_bangumi_page(html, self.BASE_URL)

                return info

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch bangumi info for ID '{mikan_id}': {e}")
            raise

    async def scrape_rss_page(self, url: str) -> list[TorrentInfo]:
        """Scrape RSS feed and extract torrent information.

        Args:
            url: RSS feed URL

        Returns:
            List of TorrentInfo objects

        Raises:
            httpx.HTTPError: If request fails
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=self.timeout)
                response.raise_for_status()

                xml_content = response.text

            feed = feedparser.parse(xml_content)  # type: ignore
            torrents: list[TorrentInfo] = []

            for entry in feed.entries:  # type: ignore
                name = str(entry.get("title", ""))  # type: ignore
                torrent_url = ""

                links = entry.get("links") or []  # type: ignore
                if links:  # type: ignore
                    for link in links:  # type: ignore
                        if link.get("type") == "application/x-bittorrent":  # type: ignore
                            torrent_url = str(link.get("href", ""))  # type: ignore
                            break

                if not torrent_url and "link" in entry:  # type: ignore
                    torrent_url = str(entry.link)  # type: ignore

                size: str | None = None
                if "torrent_contentlength" in entry:  # type: ignore
                    try:
                        size_bytes_raw = entry.torrent_contentlength  # type: ignore
                        size = self._format_size(int(str(size_bytes_raw)))  # type: ignore
                    except (ValueError, TypeError):
                        pass

                date_str = entry.get("published", None)  # type: ignore
                date: str | None = str(date_str) if date_str else None

                torrents.append(
                    TorrentInfo(
                        name=name,
                        url=torrent_url,
                        size=size,
                        date=date,
                    )
                )

            logger.debug(f"Scraped {len(torrents)} torrents from RSS feed")
            return torrents

        except httpx.HTTPError as e:
            logger.error(f"Failed to scrape RSS feed '{url}': {e}")
            raise

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format byte size to human-readable string.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted string (e.g., "1.5 GB")
        """
        size = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
