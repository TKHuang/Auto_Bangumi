"""Search service for torrent providers.

Provides async search functionality with SSE streaming support.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator

from module.conf import SEARCH_CONFIG
from module.models import Bangumi, RSSItem
from module.network import RequestContent
from module.domain.parser.title_parser import TitleParser
from module.rss import RSSAnalyser
from module.searcher.provider import search_url

logger = logging.getLogger(__name__)

SEARCH_KEY = [
    "group_name",
    "official_title",
]


def get_providers() -> list[str]:
    """Get list of available search provider names.
    
    Returns:
        List of provider names (e.g., ['mikan', 'nyaa', 'dmhy'])
    """
    return list(SEARCH_CONFIG.keys())


async def search(
    keywords: list[str],
    provider: str = "mikan",
    limit: int = 5,
) -> AsyncGenerator[str, None]:
    if provider not in SEARCH_CONFIG:
        raise ValueError(f"Provider '{provider}' is not supported")

    rss_item = search_url(provider, keywords)

    def _fetch_and_parse():
        with RequestContent() as req:
            torrents = req.get_torrents(rss_item.url)

        parser = RSSAnalyser()
        results = []
        exist_list = []

        for torrent in torrents:
            if len(results) >= limit:
                break

            bangumi = parser.raw_parser(raw=torrent.name)
            if not bangumi:
                continue

            bangumi = parser.torrent_to_data(torrent=torrent, rss=rss_item)
            if not bangumi:
                continue

            special_link = _build_special_url(bangumi, provider).url
            if special_link in exist_list:
                continue

            bangumi.rss_link = special_link
            exist_list.append(special_link)
            results.append(bangumi)

        return results

    parsed_results = await asyncio.to_thread(_fetch_and_parse)

    for bangumi in parsed_results:
        yield json.dumps(bangumi.model_dump(), separators=(",", ":"))


def _build_special_url(bangumi: Bangumi, provider: str) -> RSSItem:
    """Build provider-specific RSS URL for a bangumi.
    
    Args:
        bangumi: Bangumi object with metadata
        provider: Search provider name
        
    Returns:
        RSSItem with provider-specific URL
    """
    keywords = [getattr(bangumi, key) for key in SEARCH_KEY if getattr(bangumi, key)]
    return search_url(provider, keywords)
