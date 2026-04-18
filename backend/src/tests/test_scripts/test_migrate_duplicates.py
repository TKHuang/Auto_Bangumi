"""Tests for scripts/migrate_duplicates.py."""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.migrate_duplicates import (  # noqa: E402
    find_duplicate_groups,
    pick_winner,
    plan_merges,
    execute_merges,
)

from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.domain.models.torrent import Torrent
from module.repositories.merge_history import BangumiMergeHistoryRepository


_grp_counter = 0


def _grp() -> str:
    global _grp_counter
    _grp_counter += 1
    return f"DUPGRP{_grp_counter}"


async def _seed_series(db_session, mikan_id) -> Series:
    s = Series(
        canonical_title="X", normalized_title=f"x{mikan_id}", season=1,
        root_path=f"/p/X{mikan_id}", pending_review=False,
        mikan_bangumi_id=mikan_id,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.mark.integration
async def test_find_duplicate_groups_picks_shared_subgroup(db_session):
    s = await _seed_series(db_session, 100)
    a = Bangumi(
        official_title="A", title_raw="A", season=1, group_name=_grp(),
        rss_link="", series_id=s.id, mikan_subgroup_id=1,
    )
    b = Bangumi(
        official_title="A", title_raw="A", season=1, group_name=_grp(),
        rss_link="", series_id=s.id, mikan_subgroup_id=1,
    )
    c = Bangumi(
        official_title="A", title_raw="A", season=1, group_name=_grp(),
        rss_link="", series_id=s.id, mikan_subgroup_id=2,  # different sub → not a dup
    )
    db_session.add_all([a, b, c])
    await db_session.flush()

    groups = await find_duplicate_groups(db_session)
    assert len(groups) == 1
    assert {row.id for row in groups[0]} == {a.id, b.id}


@pytest.mark.integration
async def test_pick_winner_prefers_added_then_torrent_count(db_session):
    s = await _seed_series(db_session, 200)
    a = Bangumi(
        official_title="A", title_raw="A", season=1, group_name=_grp(),
        rss_link="", series_id=s.id, mikan_subgroup_id=1, added=False,
    )
    b = Bangumi(
        official_title="A", title_raw="A", season=1, group_name=_grp(),
        rss_link="", series_id=s.id, mikan_subgroup_id=1, added=True,
    )
    db_session.add_all([a, b])
    await db_session.flush()

    winner_id = await pick_winner(db_session, [a, b])
    assert winner_id == b.id


@pytest.mark.integration
async def test_pick_winner_breaks_tie_on_torrent_count(db_session):
    s = await _seed_series(db_session, 300)
    a = Bangumi(
        official_title="A", title_raw="A", season=1, group_name=_grp(),
        rss_link="", series_id=s.id, mikan_subgroup_id=1, added=False,
    )
    b = Bangumi(
        official_title="A", title_raw="A", season=1, group_name=_grp(),
        rss_link="", series_id=s.id, mikan_subgroup_id=1, added=False,
    )
    db_session.add_all([a, b])
    await db_session.flush()
    db_session.add_all([
        Torrent(name="t1", url="u", hash="h1", bangumi_id=b.id),
        Torrent(name="t2", url="u", hash="h2", bangumi_id=b.id),
    ])
    await db_session.flush()
    winner_id = await pick_winner(db_session, [a, b])
    assert winner_id == b.id


@pytest.mark.integration
async def test_plan_merges_skips_blacklisted_pairs(db_session):
    s = await _seed_series(db_session, 400)
    a = Bangumi(
        official_title="A", title_raw="A", season=1, group_name=_grp(),
        rss_link="", series_id=s.id, mikan_subgroup_id=1, added=True,
    )
    b = Bangumi(
        official_title="A", title_raw="A", season=1, group_name=_grp(),
        rss_link="", series_id=s.id, mikan_subgroup_id=1, added=False,
    )
    db_session.add_all([a, b])
    await db_session.flush()

    await BangumiMergeHistoryRepository(db_session).create(
        winner_id=a.id, loser_id=b.id,
        loser_snapshot={}, moved_torrent_ids=[], dropped_torrents=[],
        merge_reason="prior", merged_by="auto_migration",
    )

    plans = await plan_merges(db_session)
    assert plans == []


@pytest.mark.integration
async def test_execute_merges_writes_history_and_soft_deletes(db_session):
    s = await _seed_series(db_session, 500)
    winner = Bangumi(
        official_title="W", title_raw="W", season=1, group_name=_grp(),
        rss_link="", series_id=s.id, mikan_subgroup_id=7, added=True,
    )
    loser = Bangumi(
        official_title="L", title_raw="L", season=1, group_name=_grp(),
        rss_link="", series_id=s.id, mikan_subgroup_id=7, added=False,
    )
    db_session.add_all([winner, loser])
    await db_session.flush()

    plans = await plan_merges(db_session)
    assert len(plans) == 1

    n = await execute_merges(db_session, plans)
    assert n == 1
    await db_session.refresh(loser)
    assert loser.deleted is True
    histories = await BangumiMergeHistoryRepository(db_session).list_all()
    assert len(histories) == 1
    assert histories[0].winner_bangumi_id == winner.id
    assert histories[0].loser_bangumi_id == loser.id
    assert histories[0].merge_reason == "mikan_id_match"
