"""Tests for scripts/backfill_series.py.

Post-0008: series_id is NOT NULL, so backfill_one_bangumi is a no-op for all
rows that already have series_id (which is all rows after the migration).
Tests here verify the idempotency contract and the torrent backfill logic.
The unit tests for extract_mikan_ids_from_rss remain unchanged.
"""
import sys
from pathlib import Path

import pytest

# Make scripts/ importable
BACKEND_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.backfill_series import (  # noqa: E402
    extract_mikan_ids_from_rss,
    backfill_one_bangumi,
    backfill_torrents_for_bangumi,
)

from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.domain.models.torrent import Torrent
from module.repositories.bangumi import BangumiRepository
from module.repositories.series import SeriesRepository
from module.repositories.torrent import TorrentRepository


_grp_counter = 0


def _grp() -> str:
    global _grp_counter
    _grp_counter += 1
    return f"BFGRP{_grp_counter}"


@pytest.mark.unit
@pytest.mark.parametrize("link, expected", [
    (
        "https://mikanani.me/RSS/Bangumi?bangumiId=3906&subgroupid=370",
        (3906, 370),
    ),
    (
        "http://mikanime.tv/RSS/Bangumi?bangumiId=42&subgroupid=7",
        (42, 7),
    ),
    (
        "https://mikanani.me/RSS/Bangumi?bangumiId=3906",
        (3906, None),
    ),
    (
        "https://nyaa.si/?page=rss",
        (None, None),
    ),
    ("", (None, None)),
    (None, (None, None)),
])
def test_extract_mikan_ids_from_rss(link, expected):
    assert extract_mikan_ids_from_rss(link) == expected


@pytest.mark.integration
async def test_backfill_one_bangumi_is_noop_when_series_id_set(db_session):
    """Post-0008: all bangumi have series_id; backfill_one_bangumi returns False."""
    s = Series(
        mikan_bangumi_id=100,
        canonical_title="Demo S2",
        normalized_title="demo_s2",
        season=2,
        root_path="/downloads/Demo",
    )
    db_session.add(s)
    await db_session.flush()

    b = Bangumi(
        group_name=_grp(),
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=100&subgroupid=20",
        series_id=s.id,
        mikan_subgroup_id=20,
    )
    db_session.add(b)
    await db_session.flush()

    result = await backfill_one_bangumi(db_session, b)
    assert result is False  # no-op: series_id already set


@pytest.mark.integration
async def test_backfill_torrents_propagates_mikan_ids(db_session):
    """backfill_torrents_for_bangumi propagates mikan IDs onto torrents."""
    s = Series(
        mikan_bangumi_id=500,
        canonical_title="X",
        normalized_title="x",
        season=1,
        root_path="/downloads/X",
    )
    db_session.add(s)
    await db_session.flush()

    b = Bangumi(
        group_name=_grp(),
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=500&subgroupid=99",
        series_id=s.id,
        mikan_subgroup_id=99,
    )
    db_session.add(b)
    await db_session.flush()

    t = Torrent(name="x", url="u", hash="h1", bangumi_id=b.id)
    db_session.add(t)
    await db_session.flush()

    n = await backfill_torrents_for_bangumi(db_session, b)
    await db_session.refresh(t)
    assert n == 1
    assert t.mikan_bangumi_id == 500
    assert t.mikan_subgroup_id == 99


@pytest.mark.integration
async def test_backfill_torrents_returns_zero_when_series_has_no_mikan_id(db_session):
    """Non-Mikan series: backfill_torrents is a no-op (no mikan IDs to propagate)."""
    s = Series(
        mikan_bangumi_id=None,
        canonical_title="Nyaa Show",
        normalized_title="nyaa_show",
        season=1,
        root_path="/downloads/Nyaa",
    )
    db_session.add(s)
    await db_session.flush()

    b = Bangumi(
        group_name=_grp(),
        rss_link="https://nyaa.si/?page=rss",
        series_id=s.id,
        mikan_subgroup_id=None,
    )
    db_session.add(b)
    await db_session.flush()

    t = Torrent(name="n", url="u", hash="h2", bangumi_id=b.id)
    db_session.add(t)
    await db_session.flush()

    n = await backfill_torrents_for_bangumi(db_session, b)
    assert n == 0
