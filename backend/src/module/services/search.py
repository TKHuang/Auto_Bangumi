"""Search service for torrent providers, streamed over SSE."""

import asyncio
import json
import logging
import re
from typing import AsyncGenerator, AsyncIterator
from urllib.parse import urlencode

from module.conf import SEARCH_CONFIG, settings
from module.domain.value_objects import BangumiParsingError
from module.mikan.parser import (
    MikanSearchHit,
    build_season_rss_url,
    parse_mikan_bangumi_subgroups,
    parse_mikan_search_page,
)
from module.models import Bangumi
from module.network import RequestContent
from module.rss import RSSAnalyser
from module.rss.analyser import _extract_season_from_title
from module.searcher import SearchTorrent
from module.searcher.provider import search_url
from module.utils.cache_image import save_image

logger = logging.getLogger(__name__)

# A broad keyword can match dozens of shows; each one costs a page fetch.
MAX_MIKAN_BANGUMI = 10


def get_providers() -> list[str]:
    return list(SEARCH_CONFIG.keys())


async def search(
    keywords: list[str],
    provider: str = "mikan",
) -> AsyncGenerator[str, None]:
    if provider not in SEARCH_CONFIG:
        raise ValueError(f"Provider '{provider}' is not supported")

    hits = _search_mikan(keywords) if provider == "mikan" else _search_torrents(keywords, provider)
    async for bangumi in hits:
        yield json.dumps(bangumi.model_dump(), separators=(",", ":"))


def _get_html(url: str) -> str:
    try:
        with RequestContent() as req:
            return req.get_html(url)
    except Exception as e:
        logger.warning("[Search] Cannot fetch %s: %s", url, e)
        return ""


def _mikan_hits(hit: MikanSearchHit) -> list[Bangumi]:
    base_url = settings.mikan.base_url.rstrip("/")
    subgroups = parse_mikan_bangumi_subgroups(_get_html(f"{base_url}/Home/Bangumi/{hit.bangumi_id}"))
    if not subgroups:
        return []

    poster_link = None
    if hit.poster_path:
        with RequestContent() as req:
            img = req.get_content(f"{base_url}{hit.poster_path}")
        if img:
            poster_link = save_image(img, hit.poster_path.rsplit(".", 1)[-1])

    title = re.sub(r"[/:.\\]", " ", hit.title)
    season = _extract_season_from_title(hit.title) or 1
    return [
        Bangumi(
            official_title=title,
            title_raw=hit.title,
            season=season,
            group_name=sub.name,
            poster_link=poster_link,
            rss_link=build_season_rss_url(hit.bangumi_id, sub.subgroup_id, base_url=base_url),
            filter=",".join(settings.rss_parser.filter),
        )
        for sub in subgroups
    ]


async def _search_mikan(keywords: list[str]) -> AsyncIterator[Bangumi]:
    base_url = settings.mikan.base_url.rstrip("/")
    url = f"{base_url}/Home/Search?{urlencode({'searchstr': ' '.join(keywords)})}"
    page = await asyncio.to_thread(_get_html, url)
    hits = parse_mikan_search_page(page)[:MAX_MIKAN_BANGUMI]

    slots = asyncio.Semaphore(max(1, settings.mikan.max_concurrent))

    async def fetch(hit: MikanSearchHit) -> list[Bangumi]:
        async with slots:
            return await asyncio.to_thread(_mikan_hits, hit)

    tasks = [asyncio.create_task(fetch(hit)) for hit in hits]
    try:
        for done in asyncio.as_completed(tasks):
            for bangumi in await done:
                yield bangumi
    finally:
        for task in tasks:
            task.cancel()


async def _search_torrents(keywords: list[str], provider: str) -> AsyncIterator[Bangumi]:
    rss_item = search_url(provider, keywords)

    def fetch():
        with RequestContent() as req:
            return req.get_torrents(rss_item.url)

    parser = RSSAnalyser()
    seen: set[tuple[str, str]] = set()
    for torrent in await asyncio.to_thread(fetch):
        try:
            bangumi = parser.raw_parser(raw=torrent.name)
        except BangumiParsingError:
            continue
        if not bangumi:
            continue
        key = (bangumi.group_name, bangumi.title_raw)
        if key in seen:
            continue
        seen.add(key)

        await asyncio.to_thread(parser.official_title_parser, bangumi, rss_item, torrent)
        bangumi.rss_link = SearchTorrent.special_url(bangumi, provider).url
        yield bangumi
