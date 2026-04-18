"""Auto-merge duplicate bangumi rows produced by the legacy identity scheme.

Usage (from backend/):
  uv run python -m scripts.migrate_duplicates --dry-run
  uv run python -m scripts.migrate_duplicates --execute

Run AFTER scripts/backfill_series.py has linked every bangumi to a Series.
Duplicate detection is purely DB-driven: same (series_id, mikan_subgroup_id)
on undeleted rows, OR same (series_id, rss_id) when mikan_subgroup_id IS NULL.

Winner rules (spec §11.1, applied in order):
  1. added=True ranks above added=False
  2. Higher torrent_count
  3. Newer updated_at

Pairs already present in bangumi_merge_history are skipped (spec §11.4).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from module.database.engine import AsyncSessionLocal
from module.domain.models.bangumi import Bangumi
from module.domain.models.torrent import Torrent
from module.repositories.merge_history import BangumiMergeHistoryRepository
from module.services.bangumi_merge import BangumiMergeService

logger = logging.getLogger(__name__)


@dataclass
class MergePlan:
    winner_id: int
    loser_id: int
    series_id: int
    mikan_subgroup_id: Optional[int]
    reason: str  # 'mikan_id_match' or 'fallback_key_match'


async def find_duplicate_groups(session: AsyncSession) -> list[list[Bangumi]]:
    """Return groups of >= 2 bangumi rows sharing the same identity key."""
    # Mikan-identity duplicates: (series_id, mikan_subgroup_id) both non-null.
    mikan_stmt = (
        select(Bangumi.series_id, Bangumi.mikan_subgroup_id)
        .where(
            Bangumi.deleted == False,  # noqa: E712
            Bangumi.series_id.is_not(None),
            Bangumi.mikan_subgroup_id.is_not(None),
        )
        .group_by(Bangumi.series_id, Bangumi.mikan_subgroup_id)
        .having(func.count("*") > 1)
    )
    mikan_keys = (await session.execute(mikan_stmt)).all()

    # Fallback-identity duplicates: (series_id, rss_id) where mikan_subgroup_id IS NULL.
    fallback_stmt = (
        select(Bangumi.series_id, Bangumi.rss_id)
        .where(
            Bangumi.deleted == False,  # noqa: E712
            Bangumi.series_id.is_not(None),
            Bangumi.mikan_subgroup_id.is_(None),
            Bangumi.rss_id.is_not(None),
        )
        .group_by(Bangumi.series_id, Bangumi.rss_id)
        .having(func.count("*") > 1)
    )
    fallback_keys = (await session.execute(fallback_stmt)).all()

    groups: list[list[Bangumi]] = []

    for series_id, sub_id in mikan_keys:
        rows = (
            await session.execute(
                select(Bangumi).where(
                    Bangumi.series_id == series_id,
                    Bangumi.mikan_subgroup_id == sub_id,
                    Bangumi.deleted == False,  # noqa: E712
                )
            )
        ).scalars().all()
        groups.append(list(rows))

    for series_id, rss_id in fallback_keys:
        rows = (
            await session.execute(
                select(Bangumi).where(
                    Bangumi.series_id == series_id,
                    Bangumi.rss_id == rss_id,
                    Bangumi.mikan_subgroup_id.is_(None),
                    Bangumi.deleted == False,  # noqa: E712
                )
            )
        ).scalars().all()
        groups.append(list(rows))

    return groups


async def _torrent_count(session: AsyncSession, bangumi_id: int) -> int:
    stmt = select(func.count(Torrent.id)).where(Torrent.bangumi_id == bangumi_id)
    return int((await session.execute(stmt)).scalar() or 0)


async def pick_winner(session: AsyncSession, group: list[Bangumi]) -> int:
    """Return the bangumi_id that should keep its torrents (winner).

    Winner rules applied in order:
      1. added=True ranks above added=False  (lower sort-key = wins)
      2. More torrents ranks higher
      3. Newer updated_at ranks higher
    """
    counts = {b.id: await _torrent_count(session, b.id) for b in group}

    def _sort_key(b: Bangumi) -> tuple:
        return (
            0 if b.added else 1,                                          # added=True first
            -counts.get(b.id, 0),                                         # more torrents first
            -(b.updated_at.timestamp() if b.updated_at else 0),           # newer first
            b.id,                                                         # deterministic tiebreaker (lower id wins)
        )

    winner = min(group, key=_sort_key)
    return winner.id


async def plan_merges(session: AsyncSession) -> list[MergePlan]:
    """Build merge plans for all duplicate groups, skipping blacklisted pairs."""
    history_repo = BangumiMergeHistoryRepository(session)
    plans: list[MergePlan] = []

    for group in await find_duplicate_groups(session):
        if len(group) < 2:
            continue

        winner_id = await pick_winner(session, group)

        for row in group:
            if row.id == winner_id:
                continue

            if await history_repo.is_pair_blacklisted(winner_id, row.id):
                logger.info(
                    "skip pair (winner=%d, loser=%d) — already in history",
                    winner_id,
                    row.id,
                )
                continue

            reason = (
                "mikan_id_match"
                if row.mikan_subgroup_id is not None
                else "fallback_key_match"
            )
            plans.append(
                MergePlan(
                    winner_id=winner_id,
                    loser_id=row.id,
                    series_id=row.series_id,
                    mikan_subgroup_id=row.mikan_subgroup_id,
                    reason=reason,
                )
            )

    return plans


async def execute_merges(
    session: AsyncSession,
    plans: list[MergePlan],
) -> int:
    """Call BangumiMergeService for each plan then commit.

    Returns the number of merges executed.
    """
    svc = BangumiMergeService(session)
    n = 0
    for p in plans:
        await svc.merge(
            winner_id=p.winner_id,
            loser_id=p.loser_id,
            merge_reason=p.reason,
            merged_by="auto_migration",
        )
        n += 1
    await session.commit()
    return n


async def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Detect and merge duplicate bangumi rows post-backfill."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="print planned merges and exit without writing",
    )
    group.add_argument(
        "--execute",
        action="store_true",
        help="perform the merges and write history",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    async with AsyncSessionLocal() as session:
        plans = await plan_merges(session)

        if not plans:
            logger.info("No duplicates to merge.")
            return 0

        logger.info("Planned merges (%d):", len(plans))
        for p in plans:
            logger.info(
                "  series=%d sub=%s reason=%s  winner=%d  loser=%d",
                p.series_id,
                p.mikan_subgroup_id,
                p.reason,
                p.winner_id,
                p.loser_id,
            )

        if args.dry_run:
            return 0

        n = await execute_merges(session, plans)
        logger.info("Executed %d merges.", n)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
