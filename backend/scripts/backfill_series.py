"""One-shot script: link every existing bangumi + torrent to a Series.

Usage (from backend/):
  uv run python -m scripts.backfill_series           # default DB
  AB_ALEMBIC_DB_URL=sqlite+aiosqlite:///path uv run python -m scripts.backfill_series

Idempotent. Re-runs only touch rows where series_id IS NULL or
mikan_*_id IS NULL.

Phases (per spec §13.2):
  3. Link bangumi -> series (get_or_create via IdentityResolver).
  4. Backfill torrent.mikan_bangumi_id / mikan_subgroup_id from bangumi.
  5. Backfill bangumi.mikan_subgroup_id (covered by step 3 since rss_link
     carries the subgroupid for Mikan rows).
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from module.database.engine import AsyncSessionLocal
from module.domain.models.bangumi import Bangumi
from module.domain.models.torrent import Torrent
from module.domain.text.normalize import normalize_title
from module.mikan.parser import MikanRef, extract_mikan_ids_from_rss
from module.repositories.series import SeriesRepository
from module.services.identity_resolver import IdentityResolver


logger = logging.getLogger(__name__)


async def backfill_one_bangumi(session: AsyncSession, bangumi: Bangumi) -> bool:
    """Resolve a Series for `bangumi` and link via series_id /
    mikan_subgroup_id. No-op when already linked. Returns True iff a new
    Series link was written."""
    if bangumi.series_id is not None:
        return False

    mikan_bangumi_id, mikan_subgroup_id = extract_mikan_ids_from_rss(
        bangumi.rss_link
    )

    mikan_ref: Optional[MikanRef] = None
    if mikan_bangumi_id is not None:
        # MikanRef.mikan_subgroup_id is non-Optional in the dataclass; pass 0
        # as a placeholder when subgroupid is missing from the RSS URL. The
        # Series identity downstream only reads mikan_bangumi_id from this
        # ref, so the placeholder is inert. (Future Mikan consumers must
        # not interpret this field without checking for the URL having a
        # real subgroupid.)
        mikan_ref = MikanRef(
            mikan_bangumi_id=mikan_bangumi_id,
            mikan_subgroup_id=mikan_subgroup_id or 0,
            canonical_title=bangumi.official_title,
            poster_url=bangumi.poster_link,
        )

    raw_title = bangumi.official_title or bangumi.title_raw or "Untitled"
    norm, cour = normalize_title(raw_title)

    resolver = IdentityResolver(SeriesRepository(session))
    resolved = await resolver.resolve(
        mikan_ref=mikan_ref,
        normalized_title=norm,
        season=bangumi.season,
        cour_part=cour,
        raw_title_for_root=raw_title,
    )

    bangumi.series_id = resolved.series.id
    bangumi.mikan_subgroup_id = mikan_subgroup_id
    if bangumi.observed_groups is None:
        bangumi.observed_groups = json.dumps([bangumi.group_name or "Unknown"])
    await session.flush()
    return True


async def backfill_torrents_for_bangumi(
    session: AsyncSession, bangumi: Bangumi
) -> int:
    """Propagate bangumi's resolved Mikan IDs onto its torrents that haven't
    been backfilled yet. Returns the number of rows updated."""
    if bangumi.series_id is None:
        return 0

    series = await SeriesRepository(session).get_by_id(bangumi.series_id)
    if series is None:
        return 0
    mikan_bid = series.mikan_bangumi_id
    mikan_sid = bangumi.mikan_subgroup_id

    if mikan_bid is None and mikan_sid is None:
        return 0

    stmt = (
        update(Torrent)
        .where(
            Torrent.bangumi_id == bangumi.id,
            Torrent.mikan_bangumi_id.is_(None),
        )
        .values(mikan_bangumi_id=mikan_bid, mikan_subgroup_id=mikan_sid)
    )
    result = await session.execute(stmt)
    await session.flush()
    return result.rowcount


async def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    async with AsyncSessionLocal() as session:
        all_bangumi = (
            await session.execute(select(Bangumi).where(Bangumi.deleted == False))
        ).scalars().all()
        logger.info("Backfilling %d bangumi rows", len(all_bangumi))

        linked_count = 0
        torrent_count = 0
        for bangumi in all_bangumi:
            if await backfill_one_bangumi(session, bangumi):
                linked_count += 1
            torrent_count += await backfill_torrents_for_bangumi(session, bangumi)

        await session.commit()
        logger.info(
            "Backfill complete: %d bangumi newly linked (of %d total), "
            "%d torrents updated",
            linked_count,
            len(all_bangumi),
            torrent_count,
        )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
