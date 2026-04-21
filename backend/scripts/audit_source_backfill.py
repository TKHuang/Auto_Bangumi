"""Audit and optionally backfill existing bangumi from source RSS feeds.

Usage (from backend/):
  uv run python -m scripts.audit_source_backfill --dry-run
  uv run python -m scripts.audit_source_backfill --execute

Only bangumi whose primary rss_link is a season-specific Mikan feed are
considered safe for automatic backfill. Legacy / aggregate RSS rows are
reported separately and skipped during execute mode.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from typing import Any

from module.conf import settings
from module.conf.const import MIKAN_SEASON_RSS_PATTERN
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from module.domain.models.bangumi import Bangumi
from module.domain.models.torrent import Torrent
from module.network import RequestContent
from module.repositories.bangumi import BangumiRepository
from module.repositories.torrent import TorrentRepository
from module.services.downloader.factory import create_downloader
from module.services.rss_engine import RSSEngine

logger = logging.getLogger(__name__)
DEFAULT_DB_URL = "sqlite+aiosqlite:///data/bangumi.db"


def _is_mikan_season_rss(rss_link: str) -> bool:
    if not rss_link:
        return False
    first_rss_link = rss_link.split(",")[0]
    return bool(MIKAN_SEASON_RSS_PATTERN.search(first_rss_link))


def classify_bangumi_source(
    bangumi_rows: list[Bangumi],
) -> tuple[list[Bangumi], list[Bangumi]]:
    safe: list[Bangumi] = []
    legacy: list[Bangumi] = []
    for bangumi in bangumi_rows:
        if _is_mikan_season_rss(bangumi.rss_link):
            safe.append(bangumi)
        else:
            legacy.append(bangumi)
    return safe, legacy


def filter_bangumi_rows(
    bangumi_rows: list[Bangumi],
    requested_ids: set[int] | None,
) -> list[Bangumi]:
    if not requested_ids:
        return bangumi_rows
    return [bangumi for bangumi in bangumi_rows if bangumi.id in requested_ids]


async def fetch_source_torrents(bangumi: Bangumi) -> list[Torrent]:
    def _fetch() -> list[Torrent]:
        with RequestContent() as req:
            legacy_torrents = req.get_torrents(bangumi.rss_link, _filter="")
            return [
                Torrent(
                    name=t.name,
                    url=t.url,
                    homepage=t.homepage,
                    hash=t.hash,
                )
                for t in legacy_torrents
            ]

    all_torrents = await asyncio.to_thread(_fetch)
    if not all_torrents:
        return []

    canonical = bangumi.series.canonical_title if bangumi.series is not None else ""
    title_matched = [
        torrent
        for torrent in all_torrents
        if canonical and canonical in torrent.name
    ]
    if not title_matched:
        title_matched = all_torrents

    if not bangumi.filter:
        return title_matched

    filter_re = bangumi.filter.replace(",", "|")
    filtered_torrents = [
        torrent
        for torrent in title_matched
        if not re.search(filter_re, torrent.name, re.IGNORECASE)
    ]
    return filtered_torrents


async def audit_bangumi_source_coverage(
    session,
    bangumi: Bangumi,
) -> dict[str, Any]:
    bangumi_repo = BangumiRepository(session)
    torrent_repo = TorrentRepository(session)
    loaded_bangumi = await bangumi_repo.get_by_id(bangumi.id)
    if loaded_bangumi is not None:
        bangumi = loaded_bangumi
    source_torrents = await fetch_source_torrents(bangumi)
    existing_torrents = await torrent_repo.get_by_bangumi(bangumi.id)

    existing_hashes = {
        torrent.hash.lower()
        for torrent in existing_torrents
        if torrent.hash
    }
    source_hashes = [
        torrent.hash.lower()
        for torrent in source_torrents
        if torrent.hash
    ]
    missing_hashes = sorted(
        source_hash
        for source_hash in source_hashes
        if source_hash not in existing_hashes
    )

    return {
        "bangumi_id": bangumi.id,
        "title": bangumi.series.canonical_title if bangumi.series is not None else "",
        "rss_link": bangumi.rss_link,
        "source_count": len(source_torrents),
        "existing_count": len(existing_hashes),
        "missing_hashes": missing_hashes,
    }


async def execute_source_backfill(
    session,
    bangumi_rows: list[Bangumi],
    *,
    execute: bool,
) -> dict[str, Any]:
    safe_rows, legacy_rows = classify_bangumi_source(bangumi_rows)
    downloader = create_downloader(settings, session) if execute else None

    results: list[dict[str, Any]] = []
    executed = 0

    for bangumi in safe_rows:
        audit = await audit_bangumi_source_coverage(session, bangumi)
        results.append(audit)
        if execute and audit["missing_hashes"]:
            result = await RSSEngine.download_bangumi(session, downloader, bangumi.id)
            if isinstance(result, dict) and result.get("status"):
                executed += 1

    return {
        "safe_total": len(safe_rows),
        "legacy_total": len(legacy_rows),
        "audits": results,
        "executed": executed,
    }


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit existing bangumi for missing source episodes."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Audit only (default).")
    mode.add_argument("--execute", action="store_true", help="Backfill safe bangumi.")
    parser.add_argument(
        "--db-url",
        default=DEFAULT_DB_URL,
        help="SQLite/SQLAlchemy URL for the target DB.",
    )
    parser.add_argument(
        "--bangumi-id",
        action="append",
        dest="bangumi_ids",
        type=int,
        help="Limit audit/backfill to one or more bangumi ids.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    engine = create_async_engine(args.db_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        bangumi_rows = await BangumiRepository(session).get_active(enabled_only=True)
        bangumi_rows = filter_bangumi_rows(
            bangumi_rows,
            set(args.bangumi_ids or []),
        )
        report = await execute_source_backfill(
            session,
            bangumi_rows,
            execute=args.execute,
        )

        missing = [row for row in report["audits"] if row["missing_hashes"]]
        payload = {
            "safe_total": report["safe_total"],
            "legacy_total": report["legacy_total"],
            "missing_total": len(missing),
            "executed": report["executed"],
            "missing": missing,
        }
        logger.info(json.dumps(payload, ensure_ascii=False, indent=2))
    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
