"""Search service for torrent providers.

Provides async search functionality with SSE streaming support.
"""

import json
import logging
from typing import AsyncGenerator

from module.conf import SEARCH_CONFIG
from module.models import Bangumi, RSSItem
from module.network import RequestContent
from module.parser import TitleParser
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
    """Search for bangumi torrents and stream results as SSE.
    
    Args:
        keywords: List of search keywords
        provider: Search provider name (default: 'mikan')
        limit: Maximum number of results to return (default: 5)
        
    Yields:
        JSON-encoded Bangumi objects as strings for SSE streaming
        
    Raises:
        ValueError: If provider is not supported
    """
    if provider not in SEARCH_CONFIG:
        raise ValueError(f"Provider '{provider}' is not supported")
    
    # Build RSS search URL
    rss_item = search_url(provider, keywords)
    
    # Fetch torrents from RSS
    with RequestContent() as req:
        torrents = req.get_torrents(rss_item.url)
    
    # Parse torrents to bangumi data
    parser = RSSAnalyser()
    exist_list = []
    
    for torrent in torrents:
        if len(exist_list) >= limit:
            break
            
        bangumi = parser.raw_parser(raw=torrent.name)
        if not bangumi:
            continue
            
        # Parse official title and metadata
        bangumi = parser.torrent_to_data(torrent=torrent, rss=rss_item)
        if not bangumi:
            continue
        
        # Generate special RSS link for this bangumi
        special_link = _build_special_url(bangumi, provider).url
        
        # Skip duplicates
        if special_link in exist_list:
            continue
            
        bangumi.rss_link = special_link
        exist_list.append(special_link)
        
        # Yield JSON for SSE streaming
        yield json.dumps(bangumi.dict(), separators=(",", ":"))


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
