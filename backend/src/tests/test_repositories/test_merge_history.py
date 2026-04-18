"""BangumiMergeHistoryRepository tests."""
import json

import pytest
import pytest_asyncio

from module.domain.models.bangumi import Bangumi
from module.repositories.merge_history import BangumiMergeHistoryRepository


@pytest_asyncio.fixture
async def winner_loser(db_session):
    """Create two real bangumi rows to reference as winner/loser."""
    from module.domain.models.series import Series
    s1 = Series(canonical_title="W", normalized_title="w", season=1, root_path="/dl/W")
    s2 = Series(canonical_title="L", normalized_title="l", season=1, root_path="/dl/L")
    db_session.add_all([s1, s2])
    await db_session.flush()
    w = Bangumi(series_id=s1.id, group_name="G1")
    l = Bangumi(series_id=s2.id, group_name="G2")
    db_session.add_all([w, l])
    await db_session.flush()
    await db_session.commit()
    return w, l


@pytest_asyncio.fixture
async def merge_repo(db_session):
    return BangumiMergeHistoryRepository(db_session)


@pytest.mark.integration
class TestMergeHistoryCreate:
    async def test_create(self, merge_repo, db_session, winner_loser):
        w, l = winner_loser
        h = await merge_repo.create(
            winner_id=w.id, loser_id=l.id,
            loser_snapshot={"id": l.id, "official_title": "L"},
            moved_torrent_ids=[10, 11],
            dropped_torrents=[],
            merge_reason="mikan_id_match",
            merged_by="auto_migration",
        )
        await db_session.commit()
        assert h.id is not None
        assert h.undone_at is None
        assert json.loads(h.loser_snapshot)["official_title"] == "L"
        assert json.loads(h.moved_torrent_ids) == [10, 11]


@pytest.mark.integration
class TestMergeHistoryBlacklist:
    async def test_is_blacklisted_after_merge(self, merge_repo, db_session, winner_loser):
        w, l = winner_loser
        await merge_repo.create(
            winner_id=w.id, loser_id=l.id,
            loser_snapshot={}, moved_torrent_ids=[], dropped_torrents=[],
            merge_reason="mikan_id_match", merged_by="auto",
        )
        await db_session.commit()

        # Direction does not matter
        assert await merge_repo.is_pair_blacklisted(w.id, l.id) is True
        assert await merge_repo.is_pair_blacklisted(l.id, w.id) is True

    async def test_blacklist_survives_undone(self, merge_repo, db_session, winner_loser):
        w, l = winner_loser
        h = await merge_repo.create(
            winner_id=w.id, loser_id=l.id,
            loser_snapshot={}, moved_torrent_ids=[], dropped_torrents=[],
            merge_reason="mikan_id_match", merged_by="auto",
        )
        await db_session.commit()

        await merge_repo.mark_undone(h.id, actor="user:admin")
        await db_session.commit()

        # Still blacklisted per spec §11.4
        assert await merge_repo.is_pair_blacklisted(w.id, l.id) is True

    async def test_not_blacklisted_when_no_history(self, merge_repo):
        assert await merge_repo.is_pair_blacklisted(999, 1000) is False


@pytest.mark.integration
class TestMergeHistoryMarkUndone:
    async def test_mark_undone(self, merge_repo, db_session, winner_loser):
        w, l = winner_loser
        h = await merge_repo.create(
            winner_id=w.id, loser_id=l.id,
            loser_snapshot={}, moved_torrent_ids=[], dropped_torrents=[],
            merge_reason="manual_confirm", merged_by="user:x",
        )
        await db_session.commit()

        await merge_repo.mark_undone(h.id, actor="user:admin")
        await db_session.commit()

        reloaded = await merge_repo.get_by_id(h.id)
        assert reloaded.undone_at is not None
        assert reloaded.undone_by == "user:admin"

    async def test_mark_undone_twice_raises(self, merge_repo, db_session, winner_loser):
        w, l = winner_loser
        h = await merge_repo.create(
            winner_id=w.id, loser_id=l.id,
            loser_snapshot={}, moved_torrent_ids=[], dropped_torrents=[],
            merge_reason="manual_confirm", merged_by="user:x",
        )
        await db_session.commit()

        await merge_repo.mark_undone(h.id, actor="user:admin")
        await db_session.commit()

        with pytest.raises(ValueError):
            await merge_repo.mark_undone(h.id, actor="user:admin")


@pytest.mark.integration
class TestMergeHistoryList:
    async def test_list_all(self, merge_repo, db_session, winner_loser):
        w, l = winner_loser
        await merge_repo.create(
            winner_id=w.id, loser_id=l.id,
            loser_snapshot={}, moved_torrent_ids=[], dropped_torrents=[],
            merge_reason="mikan_id_match", merged_by="auto",
        )
        await db_session.commit()
        assert len(await merge_repo.list_all()) >= 1

    async def test_list_active_only(self, merge_repo, db_session, winner_loser):
        w, l = winner_loser
        h1 = await merge_repo.create(
            winner_id=w.id, loser_id=l.id,
            loser_snapshot={}, moved_torrent_ids=[], dropped_torrents=[],
            merge_reason="mikan_id_match", merged_by="auto",
        )
        await db_session.commit()
        await merge_repo.mark_undone(h1.id, actor="user:admin")
        await db_session.commit()

        active = await merge_repo.list_all(active_only=True)
        assert all(r.undone_at is None for r in active)
        assert h1.id not in [r.id for r in active]
