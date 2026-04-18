"""Atomic bangumi merge transaction (spec §11.2)."""
import json

import pytest

from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.domain.models.torrent import Torrent
from module.repositories.merge_history import BangumiMergeHistoryRepository
from module.services.bangumi_merge import BangumiMergeService


_grp_counter = 0


def _grp() -> str:
    global _grp_counter
    _grp_counter += 1
    return f"G{_grp_counter}"


async def _seed(db_session) -> tuple[Series, Bangumi, Bangumi]:
    s = Series(
        canonical_title="X", normalized_title="x", season=1,
        root_path="/p/X", pending_review=False, mikan_bangumi_id=42,
    )
    db_session.add(s)
    await db_session.flush()

    winner = Bangumi(
        official_title="X", title_raw="X", season=1, group_name=_grp(),
        rss_link="", series_id=s.id, mikan_subgroup_id=370, active=True,
        observed_groups=json.dumps(["LoliHouse"]),
    )
    loser = Bangumi(
        official_title="X", title_raw="X", season=1, group_name=_grp(),
        rss_link="", series_id=s.id, mikan_subgroup_id=370, active=True,
        observed_groups=json.dumps(["A&LoliHouse"]),
    )
    db_session.add_all([winner, loser])
    await db_session.flush()
    return s, winner, loser


@pytest.mark.integration
async def test_merge_moves_unique_torrents_to_winner(db_session):
    _, winner, loser = await _seed(db_session)
    t = Torrent(name="t1", url="u", hash="h-unique", bangumi_id=loser.id)
    db_session.add(t)
    await db_session.flush()

    svc = BangumiMergeService(db_session)
    history = await svc.merge(
        winner_id=winner.id, loser_id=loser.id,
        merge_reason="auto_migration", merged_by="auto_migration",
    )

    await db_session.refresh(t)
    assert t.bangumi_id == winner.id
    moved = json.loads(history.moved_torrent_ids)
    assert moved == [t.id]
    assert json.loads(history.dropped_torrents) == []


@pytest.mark.integration
async def test_merge_drops_torrents_that_would_violate_winner_unique(db_session):
    _, winner, loser = await _seed(db_session)
    db_session.add_all([
        Torrent(name="w", url="u", hash="h-conflict", bangumi_id=winner.id),
        Torrent(name="l", url="u", hash="h-conflict", bangumi_id=loser.id),
    ])
    await db_session.flush()

    svc = BangumiMergeService(db_session)
    history = await svc.merge(
        winner_id=winner.id, loser_id=loser.id,
        merge_reason="auto_migration", merged_by="auto_migration",
    )

    dropped = json.loads(history.dropped_torrents)
    assert len(dropped) == 1
    assert dropped[0]["hash"] == "h-conflict"
    assert dropped[0]["bangumi_id"] == loser.id


@pytest.mark.integration
async def test_merge_soft_deletes_loser_and_unions_observed_groups(db_session):
    _, winner, loser = await _seed(db_session)
    svc = BangumiMergeService(db_session)
    await svc.merge(
        winner_id=winner.id, loser_id=loser.id,
        merge_reason="auto_migration", merged_by="auto_migration",
    )
    await db_session.refresh(winner)
    await db_session.refresh(loser)
    assert loser.deleted is True
    assert loser.active is False
    assert set(json.loads(winner.observed_groups)) == {"LoliHouse", "A&LoliHouse"}


@pytest.mark.integration
async def test_merge_writes_full_history_row(db_session):
    _, winner, loser = await _seed(db_session)
    svc = BangumiMergeService(db_session)
    history = await svc.merge(
        winner_id=winner.id, loser_id=loser.id,
        merge_reason="mikan_id_match", merged_by="user:alice",
    )
    snap = json.loads(history.loser_snapshot)
    assert snap["id"] == loser.id
    assert snap["official_title"] == "X"
    assert history.merge_reason == "mikan_id_match"
    assert history.merged_by == "user:alice"
    assert history.winner_bangumi_id == winner.id


@pytest.mark.integration
async def test_merge_refuses_blacklisted_pair(db_session):
    _, winner, loser = await _seed(db_session)
    repo = BangumiMergeHistoryRepository(db_session)
    await repo.create(
        winner_id=winner.id, loser_id=loser.id,
        loser_snapshot={}, moved_torrent_ids=[], dropped_torrents=[],
        merge_reason="prior_merge", merged_by="auto_migration",
    )

    svc = BangumiMergeService(db_session)
    with pytest.raises(ValueError, match="blacklisted"):
        await svc.merge(
            winner_id=winner.id, loser_id=loser.id,
            merge_reason="auto_migration", merged_by="auto_migration",
        )


@pytest.mark.integration
async def test_merge_refuses_winner_equal_loser(db_session):
    _, winner, _ = await _seed(db_session)
    svc = BangumiMergeService(db_session)
    with pytest.raises(ValueError, match="must differ"):
        await svc.merge(
            winner_id=winner.id, loser_id=winner.id,
            merge_reason="auto_migration", merged_by="auto_migration",
        )
