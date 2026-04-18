"""Tests for scripts/backfill_series.py."""
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
async def test_backfill_one_bangumi_creates_mikan_series(db_session):
    repo_s = SeriesRepository(db_session)

    b = Bangumi(
        official_title="Demo S2", title_raw="Demo S2", season=2,
        group_name=_grp(),
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=100&subgroupid=20",
    )
    db_session.add(b)
    await db_session.flush()

    await backfill_one_bangumi(db_session, b)
    await db_session.refresh(b)

    assert b.series_id is not None
    assert b.mikan_subgroup_id == 20
    series = await repo_s.get_by_id(b.series_id)
    assert series.mikan_bangumi_id == 100
    assert series.canonical_title == "Demo S2"


@pytest.mark.integration
async def test_backfill_one_bangumi_uses_fallback_for_non_mikan(db_session):
    repo_s = SeriesRepository(db_session)

    b = Bangumi(
        official_title="Nyaa Show",
        title_raw="Nyaa Show 第二季",
        season=2,
        group_name=_grp(),
        rss_link="https://nyaa.si/?page=rss",
    )
    db_session.add(b)
    await db_session.flush()

    await backfill_one_bangumi(db_session, b)
    await db_session.refresh(b)

    assert b.series_id is not None
    assert b.mikan_subgroup_id is None
    series = await repo_s.get_by_id(b.series_id)
    assert series.mikan_bangumi_id is None


@pytest.mark.integration
async def test_backfill_one_bangumi_is_idempotent(db_session):
    b = Bangumi(
        official_title="Idempotent", title_raw="Idempotent", season=1,
        group_name=_grp(),
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=200&subgroupid=11",
    )
    db_session.add(b)
    await db_session.flush()

    await backfill_one_bangumi(db_session, b)
    await db_session.refresh(b)
    first_series_id = b.series_id

    await backfill_one_bangumi(db_session, b)
    await db_session.refresh(b)
    assert b.series_id == first_series_id


@pytest.mark.integration
async def test_backfill_two_bangumi_share_series_when_mikan_id_matches(db_session):
    """Production case: rows 91 + 93 share bangumiId=3906/subgroupid=370."""
    b1 = Bangumi(
        official_title="Same", title_raw="Same A", season=1, group_name=_grp(),
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=3906&subgroupid=370",
    )
    b2 = Bangumi(
        official_title="Same", title_raw="Same B", season=1, group_name=_grp(),
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=3906&subgroupid=370",
    )
    db_session.add_all([b1, b2])
    await db_session.flush()

    await backfill_one_bangumi(db_session, b1)
    await backfill_one_bangumi(db_session, b2)
    await db_session.refresh(b1)
    await db_session.refresh(b2)

    assert b1.series_id == b2.series_id
    assert b1.mikan_subgroup_id == b2.mikan_subgroup_id == 370


@pytest.mark.integration
async def test_backfill_torrents_propagates_mikan_ids(db_session):
    b = Bangumi(
        official_title="X", title_raw="X", season=1, group_name=_grp(),
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=500&subgroupid=99",
    )
    db_session.add(b)
    await db_session.flush()
    await backfill_one_bangumi(db_session, b)

    t = Torrent(name="x", url="u", hash="h1", bangumi_id=b.id)
    db_session.add(t)
    await db_session.flush()

    n = await backfill_torrents_for_bangumi(db_session, b)
    await db_session.refresh(t)
    assert n == 1
    assert t.mikan_bangumi_id == 500
    assert t.mikan_subgroup_id == 99
