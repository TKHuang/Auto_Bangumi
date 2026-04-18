"""Tests for scripts/migrate_duplicates.py.

Post-0008: the partial UNIQUE indexes prevent duplicate (series_id, mikan_subgroup_id)
rows from being created, so find_duplicate_groups/plan_merges always return empty on
a live DB. Tests here verify:
  - find_duplicate_groups returns [] on a clean post-0008 DB
  - pick_winner logic using distinct-identity test rows
  - execute_merges via direct MergePlan construction (no duplicates needed)
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.migrate_duplicates import (  # noqa: E402
    MergePlan,
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


async def _seed_series(db_session, mikan_id, suffix="") -> Series:
    s = Series(
        canonical_title=f"X{suffix}", normalized_title=f"x{mikan_id}{suffix}",
        season=1, root_path=f"/p/X{mikan_id}{suffix}", pending_review=False,
        mikan_bangumi_id=mikan_id,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.mark.integration
async def test_find_duplicate_groups_returns_empty_on_clean_db(db_session):
    """Post-0008: no duplicates can exist, so result is always empty."""
    s = await _seed_series(db_session, 100)
    a = Bangumi(group_name=_grp(), rss_link="", series_id=s.id, mikan_subgroup_id=1)
    b = Bangumi(group_name=_grp(), rss_link="", series_id=s.id, mikan_subgroup_id=2)
    db_session.add_all([a, b])
    await db_session.flush()

    groups = await find_duplicate_groups(db_session)
    assert groups == []


@pytest.mark.integration
async def test_pick_winner_prefers_added_then_torrent_count(db_session):
    """pick_winner logic works on distinct-identity bangumi rows."""
    s1 = await _seed_series(db_session, 200, "a")
    s2 = await _seed_series(db_session, 201, "b")
    a = Bangumi(group_name=_grp(), rss_link="", series_id=s1.id, mikan_subgroup_id=1, added=False)
    b = Bangumi(group_name=_grp(), rss_link="", series_id=s2.id, mikan_subgroup_id=1, added=True)
    db_session.add_all([a, b])
    await db_session.flush()

    winner_id = await pick_winner(db_session, [a, b])
    assert winner_id == b.id


@pytest.mark.integration
async def test_pick_winner_breaks_tie_on_torrent_count(db_session):
    """When both rows have added=False, more torrents wins."""
    s1 = await _seed_series(db_session, 300, "a")
    s2 = await _seed_series(db_session, 301, "b")
    a = Bangumi(group_name=_grp(), rss_link="", series_id=s1.id, mikan_subgroup_id=1, added=False)
    b = Bangumi(group_name=_grp(), rss_link="", series_id=s2.id, mikan_subgroup_id=1, added=False)
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
async def test_plan_merges_returns_empty_on_clean_db(db_session):
    """Post-0008: no duplicates -> plan_merges always returns empty list."""
    s = await _seed_series(db_session, 400)
    a = Bangumi(group_name=_grp(), rss_link="", series_id=s.id, mikan_subgroup_id=1, added=True)
    db_session.add(a)
    await db_session.flush()

    plans = await plan_merges(db_session)
    assert plans == []


@pytest.mark.integration
async def test_execute_merges_writes_history_and_soft_deletes(db_session):
    """execute_merges works when called with explicit MergePlans."""
    s = await _seed_series(db_session, 500)
    winner = Bangumi(group_name=_grp(), rss_link="", series_id=s.id, mikan_subgroup_id=7, added=True)
    loser = Bangumi(group_name=_grp(), rss_link="", series_id=s.id, mikan_subgroup_id=8, added=False)
    db_session.add_all([winner, loser])
    await db_session.flush()

    # Construct plans directly (bypassing find_duplicate_groups)
    plans = [
        MergePlan(
            winner_id=winner.id,
            loser_id=loser.id,
            series_id=s.id,
            mikan_subgroup_id=None,
            reason="mikan_id_match",
        )
    ]

    n = await execute_merges(db_session, plans)
    assert n == 1
    await db_session.refresh(loser)
    assert loser.deleted is True
    histories = await BangumiMergeHistoryRepository(db_session).list_all()
    assert len(histories) == 1
    assert histories[0].winner_bangumi_id == winner.id
    assert histories[0].loser_bangumi_id == loser.id
    assert histories[0].merge_reason == "mikan_id_match"
