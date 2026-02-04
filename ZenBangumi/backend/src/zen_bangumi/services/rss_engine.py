"""RSS engine for feed parsing, torrent matching, and download orchestration."""

import hashlib
import logging
from dataclasses import dataclass
from typing import Optional

import feedparser
import httpx

from zen_bangumi.domain.commands.base import DownloadTorrent
from zen_bangumi.domain.models.bangumi import Bangumi
from zen_bangumi.domain.models.rss import RSSItem
from zen_bangumi.domain.models.torrent import Torrent
from zen_bangumi.domain.parser.bangumi_parser import BangumiParser
from zen_bangumi.repositories.bangumi import BangumiRepository
from zen_bangumi.repositories.rss import RSSRepository
from zen_bangumi.repositories.torrent import TorrentRepository

logger = logging.getLogger(__name__)


from dataclasses import field

@dataclass
class RefreshResult:
    """Result of RSS feed refresh operation."""

    new_bangumi: int = 0
    new_torrents: int = 0
    downloads_triggered: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class ProcessedFeed:
    """Result of processing RSS feed entries."""

    new_bangumi: list[Bangumi]
    new_torrents: list[Torrent]
    download_commands: list[DownloadTorrent]


def process_rss_feed(
    feed_entries: list[dict],
    rss_item: RSSItem,
    existing_bangumi: list[Bangumi],
    existing_torrents: list[Torrent],
) -> ProcessedFeed:
    """Process RSS feed entries into bangumi, torrents, and download commands.

    This is a pure function that doesn't perform any I/O.

    Args:
        feed_entries: Parsed RSS feed entries from feedparser
        rss_item: The RSS feed configuration
        existing_bangumi: List of existing bangumi in database
        existing_torrents: List of existing torrents in database

    Returns:
        ProcessedFeed containing new bangumi, torrents, and download commands
    """
    parser = BangumiParser()
    new_bangumi_list: list[Bangumi] = []
    new_torrents_list: list[Torrent] = []
    download_commands: list[DownloadTorrent] = []

    # Build hash set of existing torrent hashes for deduplication
    existing_hashes = {t.hash for t in existing_torrents if t.hash}

    for entry in feed_entries:
        # Extract torrent info from RSS entry
        title = entry.get("title", "")
        link = entry.get("link", "")
        
        if not title or not link:
            continue

        # Generate torrent hash from URL
        torrent_hash = hashlib.sha1(link.encode()).hexdigest()

        # Skip if torrent already exists
        if torrent_hash in existing_hashes:
            continue

        # Parse torrent title
        try:
            parsed = parser.parse(title)
        except Exception as e:
            logger.warning(f"Failed to parse torrent title: {title}, error: {e}")
            continue

        # Match against existing bangumi
        matched_bangumi = _match_bangumi(parsed, existing_bangumi)

        if matched_bangumi:
            # Link torrent to existing bangumi
            torrent = Torrent(
                bangumi_id=matched_bangumi.id,
                rss_id=rss_item.id,
                name=title,
                url=link,
                hash=torrent_hash,
                downloaded=False,
            )
            new_torrents_list.append(torrent)
        else:
            # Create new bangumi
            bangumi = Bangumi(
                rss_id=rss_item.id,
                official_title=parsed.title or title,
                title_raw=title,
                season=parsed.season,
                group_name=parsed.group or "Unknown",
                dpi=parsed.resolution,
                source=parsed.source,
                subtitle=parsed.subtitle.value if parsed.subtitle else None,
                pending_review=rss_item.aggregate,  # Aggregate RSS needs review
                filter="720,\\d+-\\d+",  # Default filter
                rss_link=rss_item.url,
            )
            new_bangumi_list.append(bangumi)

            # Create torrent linked to new bangumi (will be linked after bangumi is saved)
            torrent = Torrent(
                rss_id=rss_item.id,
                name=title,
                url=link,
                hash=torrent_hash,
                downloaded=False,
            )
            new_torrents_list.append(torrent)

        # Create download command (only if bangumi matched)
        if matched_bangumi:
            download_cmd = DownloadTorrent(
                torrent_url=link,
                save_path="/downloads/Bangumi",
                bangumi_id=matched_bangumi.id,
            )
            download_commands.append(download_cmd)

    return ProcessedFeed(
        new_bangumi=new_bangumi_list,
        new_torrents=new_torrents_list,
        download_commands=download_commands,
    )


def _match_bangumi(parsed, existing_bangumi: list[Bangumi]) -> Optional[Bangumi]:
    """Match parsed torrent against existing bangumi.

    Args:
        parsed: ParsedBangumi from parser
        existing_bangumi: List of existing bangumi

    Returns:
        Matched Bangumi or None
    """
    if not parsed.title:
        return None

    for bangumi in existing_bangumi:
        # Match by composite key: title, season, group
        if (
            bangumi.official_title == parsed.title
            and bangumi.season == parsed.season
            and bangumi.group_name == (parsed.group or "Unknown")
        ):
            return bangumi

    return None


async def refresh_rss(
    rss_id: int,
    rss_repo: RSSRepository,
    bangumi_repo: BangumiRepository,
    torrent_repo: TorrentRepository,
) -> RefreshResult:
    """Refresh a single RSS feed.

    Args:
        rss_id: ID of RSS feed to refresh
        rss_repo: RSS repository
        bangumi_repo: Bangumi repository
        torrent_repo: Torrent repository

    Returns:
        RefreshResult with statistics
    """
    result = RefreshResult()

    try:
        rss_items = await rss_repo.get_all()
        rss_item = next((r for r in rss_items if r.id == rss_id), None)
        
        if not rss_item:
            result.errors.append(f"RSS feed {rss_id} not found")
            return result

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(rss_item.url)
            response.raise_for_status()
            feed_content = response.text

        feed = feedparser.parse(feed_content)
        
        if not feed.entries:
            logger.warning(f"No entries found in RSS feed {rss_id}")
            return result

        existing_bangumi = await bangumi_repo.get_all()
        
        from zen_bangumi.domain.models.torrent import Torrent
        from sqlalchemy import select
        stmt = select(Torrent)
        torrent_result = await torrent_repo.session.execute(stmt)
        existing_torrents = list(torrent_result.scalars().all())

        processed = process_rss_feed(
            [dict(entry) for entry in feed.entries],  # type: ignore
            rss_item,
            existing_bangumi,
            existing_torrents,
        )

        for bangumi in processed.new_bangumi:
            bangumi_dict = {
                "rss_id": bangumi.rss_id,
                "official_title": bangumi.official_title,
                "title_raw": bangumi.title_raw,
                "season": bangumi.season,
                "group_name": bangumi.group_name,
                "dpi": bangumi.dpi,
                "source": bangumi.source,
                "subtitle": bangumi.subtitle,
                "pending_review": bangumi.pending_review,
                "filter": bangumi.filter,
                "rss_link": bangumi.rss_link,
            }
            await bangumi_repo.create(bangumi_dict)
            result.new_bangumi += 1

        for torrent in processed.new_torrents:
            torrent_dict = {
                "bangumi_id": torrent.bangumi_id,
                "rss_id": torrent.rss_id,
                "name": torrent.name,
                "url": torrent.url,
                "hash": torrent.hash,
                "downloaded": torrent.downloaded,
            }
            await torrent_repo.create(torrent_dict)
            result.new_torrents += 1

        result.downloads_triggered = len(processed.download_commands)
        
        logger.info(
            f"RSS refresh complete for feed {rss_id}: "
            f"{result.new_bangumi} bangumi, {result.new_torrents} torrents"
        )
        
    except Exception as e:
        logger.error(f"Error refreshing RSS feed {rss_id}: {e}")
        result.errors.append(str(e))

    return result


async def refresh_all_rss(
    rss_repo: RSSRepository,
    bangumi_repo: BangumiRepository,
    torrent_repo: TorrentRepository,
) -> dict[int, RefreshResult]:
    """Refresh all enabled RSS feeds sequentially.

    Args:
        rss_repo: RSS repository
        bangumi_repo: Bangumi repository
        torrent_repo: Torrent repository

    Returns:
        Dictionary mapping RSS ID to RefreshResult
    """
    results: dict[int, RefreshResult] = {}

    enabled_feeds = await rss_repo.get_enabled()
    
    for rss_item in enabled_feeds:
        result = await refresh_rss(
            rss_item.id,
            rss_repo,
            bangumi_repo,
            torrent_repo,
        )
        results[rss_item.id] = result

    logger.info(f"Batch RSS refresh complete: {len(results)} feeds processed")

    return results
