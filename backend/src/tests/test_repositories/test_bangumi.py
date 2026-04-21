"""BangumiRepository tests (post-0008: series_id required, legacy cols dropped)."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models import Bangumi
from module.domain.models.series import Series
from module.repositories.bangumi import BangumiRepository
from module.repositories.exceptions import ConcurrentModificationError


# ---------------------------------------------------------------------------
# Shared helpers: all helpers flush within the caller's transaction context
# ---------------------------------------------------------------------------

async def _add_series(session: AsyncSession, *, suffix: str = "") -> Series:
    """Add a Series to session (no flush — caller owns the transaction)."""
    s = Series(
        canonical_title=f"Test Anime{suffix}",
        normalized_title=f"test_anime{suffix}",
        season=1,
        root_path=f"/downloads/Test{suffix}",
    )
    session.add(s)
    await session.flush()
    return s


@pytest.mark.asyncio
class TestBangumiRepository:
    async def test_create_bangumi_success(self, db_session):
        repo = BangumiRepository(db_session)

        series = await _add_series(db_session)
        bangumi = await repo.create({
            "series_id": series.id,
            "group_name": "TestGroup",
        })

        assert bangumi.id is not None
        assert bangumi.group_name == "TestGroup"
        assert bangumi.version == 1

    async def test_create_bangumi_normalises_empty_group_name(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        bangumi = await repo.create({
            "series_id": series.id,
            "group_name": "",
        })

        assert bangumi.group_name == "Unknown"

    async def test_create_bangumi_allows_different_groups_same_series(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        b1 = await repo.create({"series_id": series.id, "group_name": "GroupA", "mikan_subgroup_id": 1})
        b2 = await repo.create({"series_id": series.id, "group_name": "GroupB", "mikan_subgroup_id": 2})

        assert b1.id != b2.id
        assert b1.group_name == "GroupA"
        assert b2.group_name == "GroupB"

    async def test_get_by_id_returns_bangumi(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        created = await repo.create({"series_id": series.id, "group_name": "G"})
        found = await repo.get_by_id(created.id)

        assert found is not None
        assert found.id == created.id

    async def test_get_by_id_returns_none_when_not_found(self, db_session):
        repo = BangumiRepository(db_session)
        found = await repo.get_by_id(99999)
        assert found is None

    async def test_get_all_returns_all_bangumi(self, db_session):
        repo = BangumiRepository(db_session)
        s1 = await _add_series(db_session, suffix="1")
        s2 = await _add_series(db_session, suffix="2")

        await repo.create({"series_id": s1.id, "group_name": "Group1"})
        await repo.create({"series_id": s2.id, "group_name": "Group2"})
        all_bangumi = await repo.get_all()

        assert len(all_bangumi) == 2

    async def test_get_all_excludes_deleted_by_default(self, db_session):
        repo = BangumiRepository(db_session)
        s1 = await _add_series(db_session, suffix="1")
        s2 = await _add_series(db_session, suffix="2")

        b1 = await repo.create({"series_id": s1.id, "group_name": "Group1"})
        await repo.create({"series_id": s2.id, "group_name": "Group2"})
        await repo.soft_delete(b1.id)

        all_bangumi = await repo.get_all(include_deleted=False)

        assert len(all_bangumi) == 1
        assert all_bangumi[0].group_name == "Group2"

    async def test_get_all_includes_deleted_when_requested(self, db_session):
        repo = BangumiRepository(db_session)
        s1 = await _add_series(db_session, suffix="1")
        s2 = await _add_series(db_session, suffix="2")

        b1 = await repo.create({"series_id": s1.id, "group_name": "Group1"})
        await repo.create({"series_id": s2.id, "group_name": "Group2"})
        await repo.soft_delete(b1.id)

        all_bangumi = await repo.get_all(include_deleted=True)
        assert len(all_bangumi) == 2

    async def test_update_bangumi_success(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        bangumi = await repo.create({"series_id": series.id, "group_name": "G"})
        initial_version = bangumi.version

        updated = await repo.update(
            bangumi.id,
            {"group_name": "UpdatedGroup"},
            expected_version=initial_version,
        )

        assert updated.group_name == "UpdatedGroup"
        assert updated.version == initial_version + 1

    async def test_update_bangumi_version_conflict_raises_error(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        bangumi = await repo.create({"series_id": series.id, "group_name": "G"})
        await repo.update(bangumi.id, {"group_name": "Updated"}, bangumi.version)

        with pytest.raises(ConcurrentModificationError):
            await repo.update(bangumi.id, {"group_name": "Updated Again"}, expected_version=1)

    async def test_soft_delete_sets_deleted_flag(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        bangumi = await repo.create({"series_id": series.id, "group_name": "G"})
        await repo.soft_delete(bangumi.id)
        found = await repo.get_by_id(bangumi.id)

        assert found is not None
        assert found.deleted is True

    async def test_get_active_returns_only_active_bangumi(self, db_session):
        repo = BangumiRepository(db_session)
        s1 = await _add_series(db_session, suffix="1")
        s2 = await _add_series(db_session, suffix="2")
        s3 = await _add_series(db_session, suffix="3")

        await repo.create({"series_id": s1.id, "group_name": "Group1", "pending_review": False, "deleted": False})
        b2 = await repo.create({"series_id": s2.id, "group_name": "Group2"})
        await repo.create({"series_id": s3.id, "group_name": "Group3", "pending_review": True})
        await repo.soft_delete(b2.id)

        active = await repo.get_active()

        assert len(active) == 1
        assert active[0].group_name == "Group1"

    async def test_get_pending_review_returns_pending_bangumi(self, db_session):
        repo = BangumiRepository(db_session)
        s1 = await _add_series(db_session, suffix="1")
        s2 = await _add_series(db_session, suffix="2")

        await repo.create({"series_id": s1.id, "group_name": "Group1", "pending_review": False})
        await repo.create({"series_id": s2.id, "group_name": "Group2", "pending_review": True})

        pending = await repo.get_pending_review()

        assert len(pending) == 1
        assert pending[0].group_name == "Group2"

    async def test_get_pending_review_filters_by_rss_id(self, db_session):
        repo = BangumiRepository(db_session)
        s1 = await _add_series(db_session, suffix="1")
        s2 = await _add_series(db_session, suffix="2")

        await repo.create({"series_id": s1.id, "group_name": "Group1", "pending_review": True, "rss_id": 1})
        await repo.create({"series_id": s2.id, "group_name": "Group2", "pending_review": True, "rss_id": 2})

        pending = await repo.get_pending_review(rss_id=1)

        assert len(pending) == 1
        assert pending[0].group_name == "Group1"

    async def test_get_by_rss_returns_bangumi_for_rss(self, db_session):
        repo = BangumiRepository(db_session)
        s1 = await _add_series(db_session, suffix="1")
        s2 = await _add_series(db_session, suffix="2")

        await repo.create({"series_id": s1.id, "group_name": "Group1", "rss_id": 1})
        await repo.create({"series_id": s2.id, "group_name": "Group2", "rss_id": 2})

        rss1_bangumi = await repo.get_by_rss(1)

        assert len(rss1_bangumi) == 1
        assert rss1_bangumi[0].group_name == "Group1"

    async def test_enable_sets_pending_review_false(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        bangumi = await repo.create({"series_id": series.id, "group_name": "G", "pending_review": True})
        await repo.enable(bangumi.id)
        found = await repo.get_by_id(bangumi.id)

        assert found.pending_review is False

    async def test_disable_sets_pending_review_true(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        bangumi = await repo.create({"series_id": series.id, "group_name": "G", "pending_review": False})
        await repo.disable(bangumi.id)
        found = await repo.get_by_id(bangumi.id)

        assert found.pending_review is True

    async def test_reset_all_resets_added_and_eps_collect(self, db_session):
        repo = BangumiRepository(db_session)
        s1 = await _add_series(db_session, suffix="1")
        s2 = await _add_series(db_session, suffix="2")

        await repo.create({"series_id": s1.id, "group_name": "Group1", "added": True, "eps_collect": True})
        await repo.create({"series_id": s2.id, "group_name": "Group2", "added": True, "eps_collect": True})
        await repo.reset_all()

        all_bangumi = await repo.get_all()

        for bangumi in all_bangumi:
            assert bangumi.added is False
            assert bangumi.eps_collect is False

    async def test_find_by_any_rss_link_returns_bangumi(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        await repo.create({
            "series_id": series.id,
            "group_name": "Group1",
            "rss_link": "https://example.com/rss/anime1",
        })

        found = await repo.find_by_any_rss_link(["https://example.com/rss/anime1"])

        assert found is not None
        assert found.group_name == "Group1"

    async def test_find_by_any_rss_link_returns_first_match(self, db_session):
        repo = BangumiRepository(db_session)
        s1 = await _add_series(db_session, suffix="1")
        s2 = await _add_series(db_session, suffix="2")

        await repo.create({"series_id": s1.id, "group_name": "Group1", "rss_link": "https://example.com/rss/anime1"})
        await repo.create({"series_id": s2.id, "group_name": "Group2", "rss_link": "https://example.com/rss/anime2"})

        found = await repo.find_by_any_rss_link([
            "https://example.com/rss/anime1",
            "https://example.com/rss/anime2",
        ])

        assert found is not None
        assert found.group_name == "Group1"

    async def test_find_by_any_rss_link_skips_empty_links(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        await repo.create({
            "series_id": series.id,
            "group_name": "Group1",
            "rss_link": "https://example.com/rss/anime1",
        })

        found = await repo.find_by_any_rss_link(["", "https://example.com/rss/anime1"])

        assert found is not None
        assert found.group_name == "Group1"

    async def test_match_poster_returns_poster_link(self, db_session):
        """match_poster joins to series.poster_url via the @property shim."""
        repo = BangumiRepository(db_session)
        series = Series(
            canonical_title="Test Anime",
            normalized_title="test_anime",
            season=1,
            root_path="/downloads/Test",
            poster_url="https://example.com/poster.jpg",
        )
        db_session.add(series)
        await db_session.flush()

        await repo.create({"series_id": series.id, "group_name": "G"})

        poster = await repo.match_poster("[Group] Test Anime - 01")

        assert poster == "https://example.com/poster.jpg"

    async def test_match_poster_returns_empty_when_not_found(self, db_session):
        repo = BangumiRepository(db_session)
        poster = await repo.match_poster("Non-existent Anime")
        assert poster == ""

    async def test_match_torrent_returns_bangumi(self, db_session):
        """match_torrent joins to series.canonical_title."""
        repo = BangumiRepository(db_session)
        series = Series(
            canonical_title="Test Anime",
            normalized_title="test_anime",
            season=1,
            root_path="/downloads/Test",
        )
        db_session.add(series)
        await db_session.flush()

        await repo.create({"series_id": series.id, "group_name": "Group1"})

        found = await repo.match_torrent("[Group] Test Anime - 01 [1080p]")

        assert found is not None
        assert found.group_name == "Group1"

    async def test_match_torrent_excludes_deleted(self, db_session):
        repo = BangumiRepository(db_session)
        series = Series(
            canonical_title="Test Anime",
            normalized_title="test_anime",
            season=1,
            root_path="/downloads/Test",
        )
        db_session.add(series)
        await db_session.flush()

        bangumi = await repo.create({"series_id": series.id, "group_name": "G"})
        await repo.soft_delete(bangumi.id)

        found = await repo.match_torrent("[Group] Test Anime - 01 [1080p]")

        assert found is None

    async def test_match_torrent_excludes_pending_review(self, db_session):
        repo = BangumiRepository(db_session)
        series = Series(
            canonical_title="Test Anime",
            normalized_title="test_anime",
            season=1,
            root_path="/downloads/Test",
        )
        db_session.add(series)
        await db_session.flush()

        await repo.create({"series_id": series.id, "group_name": "G", "pending_review": True})

        found = await repo.match_torrent("[Group] Test Anime - 01 [1080p]")

        assert found is None

    async def test_count_pending_by_rss_id_returns_count(self, db_session):
        repo = BangumiRepository(db_session)
        s1 = await _add_series(db_session, suffix="1")
        s2 = await _add_series(db_session, suffix="2")
        s3 = await _add_series(db_session, suffix="3")

        await repo.create({"series_id": s1.id, "group_name": "Group1", "rss_id": 1, "pending_review": True})
        await repo.create({"series_id": s2.id, "group_name": "Group2", "rss_id": 1, "pending_review": True})
        await repo.create({"series_id": s3.id, "group_name": "Group3", "rss_id": 1, "pending_review": False})

        count = await repo.count_pending_by_rss_id(1)

        assert count == 2

    async def test_count_active_by_rss_id_returns_count(self, db_session):
        repo = BangumiRepository(db_session)
        s1 = await _add_series(db_session, suffix="1")
        s2 = await _add_series(db_session, suffix="2")
        s3 = await _add_series(db_session, suffix="3")

        await repo.create({"series_id": s1.id, "group_name": "Group1", "rss_id": 1, "pending_review": False})
        await repo.create({"series_id": s2.id, "group_name": "Group2", "rss_id": 1, "pending_review": False})
        await repo.create({"series_id": s3.id, "group_name": "Group3", "rss_id": 1, "pending_review": True})

        count = await repo.count_active_by_rss_id(1)

        assert count == 2

    async def test_activate_pending_activates_bangumi(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        bangumi = await repo.create({
            "series_id": series.id,
            "group_name": "G",
            "pending_review": True,
            "global_filter_matches": "some_filter",
        })
        success, message = await repo.activate_pending(bangumi.id)

        assert success is True
        assert message == "Bangumi activated successfully"

        found = await repo.get_by_id(bangumi.id)

        assert found.pending_review is False
        assert found.global_filter_matches is None

    async def test_activate_pending_with_filter_value(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        bangumi = await repo.create({
            "series_id": series.id,
            "group_name": "G",
            "pending_review": True,
            "filter": "old_filter",
        })
        success, message = await repo.activate_pending(bangumi.id, filter_value="new_filter")

        assert success is True

        found = await repo.get_by_id(bangumi.id)
        assert found.filter == "new_filter"

    async def test_activate_pending_returns_false_when_not_found(self, db_session):
        repo = BangumiRepository(db_session)
        success, message = await repo.activate_pending(99999)
        assert success is False
        assert message == "Bangumi not found"

    async def test_activate_pending_returns_false_when_not_pending(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        bangumi = await repo.create({"series_id": series.id, "group_name": "G", "pending_review": False})
        success, message = await repo.activate_pending(bangumi.id)

        assert success is False
        assert message == "Bangumi is not pending review"

    async def test_update_pending_review_sets_pending_true(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        bangumi = await repo.create({"series_id": series.id, "group_name": "G", "pending_review": False})
        success = await repo.update_pending_review(bangumi.id, pending=True, global_filter_matches="test_filter")

        assert success is True

        found = await repo.get_by_id(bangumi.id)
        assert found.pending_review is True
        assert found.global_filter_matches == "test_filter"

    async def test_update_pending_review_sets_pending_false(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        bangumi = await repo.create({
            "series_id": series.id,
            "group_name": "G",
            "pending_review": True,
            "global_filter_matches": "test_filter",
        })
        success = await repo.update_pending_review(bangumi.id, pending=False)

        assert success is True

        found = await repo.get_by_id(bangumi.id)
        assert found.pending_review is False
        assert found.global_filter_matches is None

    async def test_update_pending_review_returns_false_when_not_found(self, db_session):
        repo = BangumiRepository(db_session)
        success = await repo.update_pending_review(99999, pending=True)
        assert success is False

    async def test_delete_one_deletes_bangumi(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        bangumi = await repo.create({"series_id": series.id, "group_name": "G"})
        result = await repo.delete_one(bangumi.id)

        assert result is True

        found = await repo.get_by_id(bangumi.id)
        assert found is None

    async def test_delete_one_returns_false_when_not_found(self, db_session):
        repo = BangumiRepository(db_session)
        result = await repo.delete_one(99999)
        assert result is False

    async def test_delete_many_deletes_multiple_bangumi(self, db_session):
        repo = BangumiRepository(db_session)
        s1 = await _add_series(db_session, suffix="1")
        s2 = await _add_series(db_session, suffix="2")
        s3 = await _add_series(db_session, suffix="3")

        b1 = await repo.create({"series_id": s1.id, "group_name": "Group1"})
        b2 = await repo.create({"series_id": s2.id, "group_name": "Group2"})
        await repo.create({"series_id": s3.id, "group_name": "Group3"})
        count = await repo.delete_many([b1.id, b2.id])

        assert count == 2

        all_bangumi = await repo.get_all(include_deleted=True)

        assert len(all_bangumi) == 1
        assert all_bangumi[0].group_name == "Group3"

    async def test_delete_many_returns_zero_for_empty_list(self, db_session):
        repo = BangumiRepository(db_session)
        count = await repo.delete_many([])
        assert count == 0

    async def test_disable_many_soft_deletes_multiple_bangumi(self, db_session):
        repo = BangumiRepository(db_session)
        s1 = await _add_series(db_session, suffix="1")
        s2 = await _add_series(db_session, suffix="2")

        b1 = await repo.create({"series_id": s1.id, "group_name": "Group1"})
        b2 = await repo.create({"series_id": s2.id, "group_name": "Group2"})
        count = await repo.disable_many([b1.id, b2.id])

        assert count == 2

        all_bangumi = await repo.get_all(include_deleted=True)
        assert len(all_bangumi) == 2
        assert all(b.deleted is True for b in all_bangumi)

    async def test_disable_many_returns_zero_for_empty_list(self, db_session):
        repo = BangumiRepository(db_session)
        count = await repo.disable_many([])
        assert count == 0

    async def test_delete_all_deletes_all_bangumi(self, db_session):
        repo = BangumiRepository(db_session)
        s1 = await _add_series(db_session, suffix="1")
        s2 = await _add_series(db_session, suffix="2")

        await repo.create({"series_id": s1.id, "group_name": "Group1"})
        await repo.create({"series_id": s2.id, "group_name": "Group2"})
        await repo.delete_all()

        all_bangumi = await repo.get_all(include_deleted=True)
        assert len(all_bangumi) == 0

    async def test_backfill_rss_id_updates_bangumi(self, db_session):
        repo = BangumiRepository(db_session)
        s1 = await _add_series(db_session, suffix="1")
        s2 = await _add_series(db_session, suffix="2")
        s3 = await _add_series(db_session, suffix="3")

        b1 = await repo.create({
            "series_id": s1.id, "group_name": "Group1",
            "rss_link": "https://example.com/rss/feed1",
        })
        b2 = await repo.create({
            "series_id": s2.id, "group_name": "Group2",
            "rss_link": "https://example.com/rss/feed1",
        })
        await repo.create({
            "series_id": s3.id, "group_name": "Group3",
            "rss_link": "https://other.com/rss/feed2",
        })
        count = await repo.backfill_rss_id(1, "https://example.com/rss/feed1")

        assert count == 2

        found1 = await repo.get_by_id(b1.id)
        found2 = await repo.get_by_id(b2.id)

        assert found1.rss_id == 1
        assert found2.rss_id == 1

    async def test_backfill_rss_id_skips_already_set(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        await repo.create({
            "series_id": series.id,
            "group_name": "Group1",
            "rss_link": "https://example.com/rss/feed1",
            "rss_id": 2,
        })
        count = await repo.backfill_rss_id(1, "https://example.com/rss/feed1")

        assert count == 0

    async def test_update_simple_updates_bangumi(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        bangumi = await repo.create({"series_id": series.id, "group_name": "G"})
        success = await repo.update_simple(bangumi.id, {"group_name": "Updated"})

        assert success is True

        found = await repo.get_by_id(bangumi.id)
        assert found.group_name == "Updated"

    async def test_update_simple_returns_false_when_not_found(self, db_session):
        repo = BangumiRepository(db_session)
        success = await repo.update_simple(99999, {"group_name": "Updated"})
        assert success is False

    async def test_update_simple_ignores_id_and_version(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)

        bangumi = await repo.create({"series_id": series.id, "group_name": "G"})
        original_id = bangumi.id
        await repo.update_simple(bangumi.id, {"id": 99999, "version": 99999, "group_name": "Updated"})

        found = await repo.get_by_id(original_id)
        assert found.id == original_id
        assert found.group_name == "Updated"

    async def test_get_by_mikan_bangumi_url_returns_match(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)
        url = "https://mikanani.me/Home/Bangumi/3901#1243"

        bangumi = await repo.create({
            "series_id": series.id,
            "group_name": "G",
            "mikan_subgroup_id": 1243,
            "mikan_bangumi_url": url,
        })

        found = await repo.get_by_mikan_bangumi_url(url)
        assert found is not None
        assert found.id == bangumi.id

    async def test_get_by_mikan_bangumi_url_ignores_deleted(self, db_session):
        repo = BangumiRepository(db_session)
        series = await _add_series(db_session)
        url = "https://mikanani.me/Home/Bangumi/4000#7"

        bangumi = await repo.create({
            "series_id": series.id,
            "group_name": "G",
            "mikan_subgroup_id": 7,
            "mikan_bangumi_url": url,
        })
        await repo.soft_delete(bangumi.id)

        assert await repo.get_by_mikan_bangumi_url(url) is None

    async def test_get_by_mikan_bangumi_url_returns_none_on_empty_or_missing(
        self, db_session
    ):
        repo = BangumiRepository(db_session)
        assert await repo.get_by_mikan_bangumi_url("") is None
        assert await repo.get_by_mikan_bangumi_url(
            "https://mikanani.me/Home/Bangumi/99999#99999"
        ) is None
