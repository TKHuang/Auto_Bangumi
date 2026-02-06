import pytest
from sqlalchemy.exc import IntegrityError

from module.domain.models import Bangumi
from module.repositories.bangumi import BangumiRepository
from module.repositories.exceptions import ConcurrentModificationError


@pytest.mark.asyncio
class TestBangumiRepository:
    async def test_create_bangumi_success(self, async_session):
        repo = BangumiRepository(async_session)
        
        data = {
            "official_title": "Test Anime",
            "title_raw": "[Group] Test Anime",
            "season": 1,
            "group_name": "TestGroup",
        }
        
        async with async_session.begin():
            bangumi = await repo.create(data)
        
        assert bangumi.id is not None
        assert bangumi.official_title == "Test Anime"
        assert bangumi.season == 1
        assert bangumi.group_name == "TestGroup"
        assert bangumi.version == 1

    async def test_create_bangumi_composite_key_duplicate_raises_error(self, async_session):
        repo = BangumiRepository(async_session)
        
        data = {
            "official_title": "Test Anime",
            "title_raw": "[Group] Test Anime",
            "season": 1,
            "group_name": "TestGroup",
        }
        
        async with async_session.begin():
            await repo.create(data)
        
        async with async_session.begin():
            with pytest.raises(ValueError, match="already exists"):
                await repo.create(data)

    async def test_create_bangumi_allows_different_season(self, async_session):
        repo = BangumiRepository(async_session)
        
        data1 = {
            "official_title": "Test Anime",
            "title_raw": "[Group] Test Anime",
            "season": 1,
            "group_name": "TestGroup",
        }
        data2 = {
            "official_title": "Test Anime",
            "title_raw": "[Group] Test Anime S2",
            "season": 2,
            "group_name": "TestGroup",
        }
        
        async with async_session.begin():
            bangumi1 = await repo.create(data1)
            bangumi2 = await repo.create(data2)
        
        assert bangumi1.id != bangumi2.id
        assert bangumi1.season == 1
        assert bangumi2.season == 2

    async def test_create_bangumi_allows_different_group(self, async_session):
        repo = BangumiRepository(async_session)
        
        data1 = {
            "official_title": "Test Anime",
            "title_raw": "[GroupA] Test Anime",
            "season": 1,
            "group_name": "GroupA",
        }
        data2 = {
            "official_title": "Test Anime",
            "title_raw": "[GroupB] Test Anime",
            "season": 1,
            "group_name": "GroupB",
        }
        
        async with async_session.begin():
            bangumi1 = await repo.create(data1)
            bangumi2 = await repo.create(data2)
        
        assert bangumi1.id != bangumi2.id
        assert bangumi1.group_name == "GroupA"
        assert bangumi2.group_name == "GroupB"

    async def test_get_by_id_returns_bangumi(self, async_session):
        repo = BangumiRepository(async_session)
        
        data = {
            "official_title": "Test Anime",
            "title_raw": "[Group] Test Anime",
            "season": 1,
            "group_name": "TestGroup",
        }
        
        async with async_session.begin():
            created = await repo.create(data)
        
        async with async_session.begin():
            found = await repo.get_by_id(created.id)
        
        assert found is not None
        assert found.id == created.id
        assert found.official_title == "Test Anime"

    async def test_get_by_id_returns_none_when_not_found(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            found = await repo.get_by_id(99999)
        
        assert found is None

    async def test_get_by_composite_key_returns_bangumi(self, async_session):
        repo = BangumiRepository(async_session)
        
        data = {
            "official_title": "Test Anime",
            "title_raw": "[Group] Test Anime",
            "season": 1,
            "group_name": "TestGroup",
        }
        
        async with async_session.begin():
            await repo.create(data)
        
        async with async_session.begin():
            found = await repo.get_by_composite_key("Test Anime", 1, "TestGroup")
        
        assert found is not None
        assert found.official_title == "Test Anime"
        assert found.season == 1
        assert found.group_name == "TestGroup"

    async def test_get_by_composite_key_returns_none_when_deleted(self, async_session):
        repo = BangumiRepository(async_session)
        
        data = {
            "official_title": "Test Anime",
            "title_raw": "[Group] Test Anime",
            "season": 1,
            "group_name": "TestGroup",
        }
        
        async with async_session.begin():
            bangumi = await repo.create(data)
            await repo.soft_delete(bangumi.id)
        
        async with async_session.begin():
            found = await repo.get_by_composite_key("Test Anime", 1, "TestGroup")
        
        assert found is None

    async def test_get_all_returns_all_bangumi(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "Anime 1",
                "title_raw": "Anime 1",
                "season": 1,
                "group_name": "Group1",
            })
            await repo.create({
                "official_title": "Anime 2",
                "title_raw": "Anime 2",
                "season": 1,
                "group_name": "Group2",
            })
        
        async with async_session.begin():
            all_bangumi = await repo.get_all()
        
        assert len(all_bangumi) == 2

    async def test_get_all_excludes_deleted_by_default(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            b1 = await repo.create({
                "official_title": "Anime 1",
                "title_raw": "Anime 1",
                "season": 1,
                "group_name": "Group1",
            })
            await repo.create({
                "official_title": "Anime 2",
                "title_raw": "Anime 2",
                "season": 1,
                "group_name": "Group2",
            })
            await repo.soft_delete(b1.id)
        
        async with async_session.begin():
            all_bangumi = await repo.get_all(include_deleted=False)
        
        assert len(all_bangumi) == 1
        assert all_bangumi[0].official_title == "Anime 2"

    async def test_get_all_includes_deleted_when_requested(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            b1 = await repo.create({
                "official_title": "Anime 1",
                "title_raw": "Anime 1",
                "season": 1,
                "group_name": "Group1",
            })
            await repo.create({
                "official_title": "Anime 2",
                "title_raw": "Anime 2",
                "season": 1,
                "group_name": "Group2",
            })
            await repo.soft_delete(b1.id)
        
        async with async_session.begin():
            all_bangumi = await repo.get_all(include_deleted=True)
        
        assert len(all_bangumi) == 2

    async def test_update_bangumi_success(self, async_session):
        repo = BangumiRepository(async_session)
        
        data = {
            "official_title": "Test Anime",
            "title_raw": "[Group] Test Anime",
            "season": 1,
            "group_name": "TestGroup",
        }
        
        async with async_session.begin():
            bangumi = await repo.create(data)
            initial_version = bangumi.version
        
        async with async_session.begin():
            updated = await repo.update(
                bangumi.id,
                {"official_title": "Updated Anime"},
                expected_version=initial_version
            )
        
        assert updated.official_title == "Updated Anime"
        assert updated.version == initial_version + 1

    async def test_update_bangumi_version_conflict_raises_error(self, async_session):
        repo = BangumiRepository(async_session)
        
        data = {
            "official_title": "Test Anime",
            "title_raw": "[Group] Test Anime",
            "season": 1,
            "group_name": "TestGroup",
        }
        
        async with async_session.begin():
            bangumi = await repo.create(data)
            await repo.update(bangumi.id, {"official_title": "Updated Once"}, bangumi.version)
        
        async with async_session.begin():
            with pytest.raises(ConcurrentModificationError):
                await repo.update(bangumi.id, {"official_title": "Updated Twice"}, expected_version=1)

    async def test_soft_delete_sets_deleted_flag(self, async_session):
        repo = BangumiRepository(async_session)
        
        data = {
            "official_title": "Test Anime",
            "title_raw": "[Group] Test Anime",
            "season": 1,
            "group_name": "TestGroup",
        }
        
        async with async_session.begin():
            bangumi = await repo.create(data)
            await repo.soft_delete(bangumi.id)
        
        async with async_session.begin():
            found = await repo.get_by_id(bangumi.id)
        
        assert found is not None
        assert found.deleted is True

    async def test_get_active_returns_only_active_bangumi(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "Active Anime",
                "title_raw": "Active Anime",
                "season": 1,
                "group_name": "Group1",
                "pending_review": False,
                "deleted": False,
            })
            b2 = await repo.create({
                "official_title": "Deleted Anime",
                "title_raw": "Deleted Anime",
                "season": 1,
                "group_name": "Group2",
            })
            await repo.create({
                "official_title": "Pending Anime",
                "title_raw": "Pending Anime",
                "season": 1,
                "group_name": "Group3",
                "pending_review": True,
            })
            await repo.soft_delete(b2.id)
        
        async with async_session.begin():
            active = await repo.get_active()
        
        assert len(active) == 1
        assert active[0].official_title == "Active Anime"

    async def test_get_pending_review_returns_pending_bangumi(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "Active Anime",
                "title_raw": "Active Anime",
                "season": 1,
                "group_name": "Group1",
                "pending_review": False,
            })
            await repo.create({
                "official_title": "Pending Anime",
                "title_raw": "Pending Anime",
                "season": 1,
                "group_name": "Group2",
                "pending_review": True,
            })
        
        async with async_session.begin():
            pending = await repo.get_pending_review()
        
        assert len(pending) == 1
        assert pending[0].official_title == "Pending Anime"

    async def test_get_pending_review_filters_by_rss_id(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "Pending RSS 1",
                "title_raw": "Pending RSS 1",
                "season": 1,
                "group_name": "Group1",
                "pending_review": True,
                "rss_id": 1,
            })
            await repo.create({
                "official_title": "Pending RSS 2",
                "title_raw": "Pending RSS 2",
                "season": 1,
                "group_name": "Group2",
                "pending_review": True,
                "rss_id": 2,
            })
        
        async with async_session.begin():
            pending = await repo.get_pending_review(rss_id=1)
        
        assert len(pending) == 1
        assert pending[0].official_title == "Pending RSS 1"

    async def test_get_by_rss_returns_bangumi_for_rss(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "RSS 1 Anime",
                "title_raw": "RSS 1 Anime",
                "season": 1,
                "group_name": "Group1",
                "rss_id": 1,
            })
            await repo.create({
                "official_title": "RSS 2 Anime",
                "title_raw": "RSS 2 Anime",
                "season": 1,
                "group_name": "Group2",
                "rss_id": 2,
            })
        
        async with async_session.begin():
            rss1_bangumi = await repo.get_by_rss(1)
        
        assert len(rss1_bangumi) == 1
        assert rss1_bangumi[0].official_title == "RSS 1 Anime"

    async def test_enable_sets_pending_review_false(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            bangumi = await repo.create({
                "official_title": "Test Anime",
                "title_raw": "Test Anime",
                "season": 1,
                "group_name": "Group1",
                "pending_review": True,
            })
            await repo.enable(bangumi.id)
        
        async with async_session.begin():
            found = await repo.get_by_id(bangumi.id)
        
        assert found.pending_review is False

    async def test_disable_sets_pending_review_true(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            bangumi = await repo.create({
                "official_title": "Test Anime",
                "title_raw": "Test Anime",
                "season": 1,
                "group_name": "Group1",
                "pending_review": False,
            })
            await repo.disable(bangumi.id)
        
        async with async_session.begin():
            found = await repo.get_by_id(bangumi.id)
        
        assert found.pending_review is True

    async def test_reset_all_resets_added_and_eps_collect(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "Anime 1",
                "title_raw": "Anime 1",
                "season": 1,
                "group_name": "Group1",
                "added": True,
                "eps_collect": True,
            })
            await repo.create({
                "official_title": "Anime 2",
                "title_raw": "Anime 2",
                "season": 1,
                "group_name": "Group2",
                "added": True,
                "eps_collect": True,
            })
            await repo.reset_all()
        
        async with async_session.begin():
            all_bangumi = await repo.get_all()
        
        for bangumi in all_bangumi:
            assert bangumi.added is False
            assert bangumi.eps_collect is False

    async def test_find_by_official_title_returns_bangumi(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "Test Anime",
                "title_raw": "Test Anime",
                "season": 1,
                "group_name": "Group1",
            })
        
        async with async_session.begin():
            found = await repo.find_by_official_title("Test Anime")
        
        assert found is not None
        assert found.official_title == "Test Anime"

    async def test_find_by_official_title_returns_none_when_deleted(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            bangumi = await repo.create({
                "official_title": "Test Anime",
                "title_raw": "Test Anime",
                "season": 1,
                "group_name": "Group1",
            })
            await repo.soft_delete(bangumi.id)
        
        async with async_session.begin():
            found = await repo.find_by_official_title("Test Anime")
        
        assert found is None

    async def test_find_by_any_rss_link_returns_bangumi(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "Test Anime",
                "title_raw": "Test Anime",
                "season": 1,
                "group_name": "Group1",
                "rss_link": "https://example.com/rss/anime1",
            })
        
        async with async_session.begin():
            found = await repo.find_by_any_rss_link(["https://example.com/rss/anime1"])
        
        assert found is not None
        assert found.official_title == "Test Anime"

    async def test_find_by_any_rss_link_returns_first_match(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "Anime 1",
                "title_raw": "Anime 1",
                "season": 1,
                "group_name": "Group1",
                "rss_link": "https://example.com/rss/anime1",
            })
            await repo.create({
                "official_title": "Anime 2",
                "title_raw": "Anime 2",
                "season": 1,
                "group_name": "Group2",
                "rss_link": "https://example.com/rss/anime2",
            })
        
        async with async_session.begin():
            found = await repo.find_by_any_rss_link([
                "https://example.com/rss/anime1",
                "https://example.com/rss/anime2"
            ])
        
        assert found is not None
        assert found.official_title == "Anime 1"

    async def test_find_by_any_rss_link_skips_empty_links(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "Test Anime",
                "title_raw": "Test Anime",
                "season": 1,
                "group_name": "Group1",
                "rss_link": "https://example.com/rss/anime1",
            })
        
        async with async_session.begin():
            found = await repo.find_by_any_rss_link(["", "https://example.com/rss/anime1"])
        
        assert found is not None
        assert found.official_title == "Test Anime"

    async def test_match_poster_returns_poster_link(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "Test Anime",
                "title_raw": "Test Anime",
                "season": 1,
                "group_name": "Group1",
                "poster_link": "https://example.com/poster.jpg",
            })
        
        async with async_session.begin():
            poster = await repo.match_poster("[Group] Test Anime - 01")
        
        assert poster == "https://example.com/poster.jpg"

    async def test_match_poster_returns_empty_when_not_found(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            poster = await repo.match_poster("Non-existent Anime")
        
        assert poster == ""

    async def test_match_torrent_returns_bangumi(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "Test Anime",
                "title_raw": "[Group] Test Anime",
                "season": 1,
                "group_name": "Group1",
            })
        
        async with async_session.begin():
            found = await repo.match_torrent("[Group] Test Anime - 01 [1080p]")
        
        assert found is not None
        assert found.official_title == "Test Anime"

    async def test_match_torrent_excludes_deleted(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            bangumi = await repo.create({
                "official_title": "Test Anime",
                "title_raw": "[Group] Test Anime",
                "season": 1,
                "group_name": "Group1",
            })
            await repo.soft_delete(bangumi.id)
        
        async with async_session.begin():
            found = await repo.match_torrent("[Group] Test Anime - 01 [1080p]")
        
        assert found is None

    async def test_match_torrent_excludes_pending_review(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "Test Anime",
                "title_raw": "[Group] Test Anime",
                "season": 1,
                "group_name": "Group1",
                "pending_review": True,
            })
        
        async with async_session.begin():
            found = await repo.match_torrent("[Group] Test Anime - 01 [1080p]")
        
        assert found is None

    async def test_count_pending_by_rss_id_returns_count(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "Pending 1",
                "title_raw": "Pending 1",
                "season": 1,
                "group_name": "Group1",
                "rss_id": 1,
                "pending_review": True,
            })
            await repo.create({
                "official_title": "Pending 2",
                "title_raw": "Pending 2",
                "season": 1,
                "group_name": "Group2",
                "rss_id": 1,
                "pending_review": True,
            })
            await repo.create({
                "official_title": "Active",
                "title_raw": "Active",
                "season": 1,
                "group_name": "Group3",
                "rss_id": 1,
                "pending_review": False,
            })
        
        async with async_session.begin():
            count = await repo.count_pending_by_rss_id(1)
        
        assert count == 2

    async def test_count_active_by_rss_id_returns_count(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "Active 1",
                "title_raw": "Active 1",
                "season": 1,
                "group_name": "Group1",
                "rss_id": 1,
                "pending_review": False,
            })
            await repo.create({
                "official_title": "Active 2",
                "title_raw": "Active 2",
                "season": 1,
                "group_name": "Group2",
                "rss_id": 1,
                "pending_review": False,
            })
            await repo.create({
                "official_title": "Pending",
                "title_raw": "Pending",
                "season": 1,
                "group_name": "Group3",
                "rss_id": 1,
                "pending_review": True,
            })
        
        async with async_session.begin():
            count = await repo.count_active_by_rss_id(1)
        
        assert count == 2

    async def test_activate_pending_activates_bangumi(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            bangumi = await repo.create({
                "official_title": "Test Anime",
                "title_raw": "Test Anime",
                "season": 1,
                "group_name": "Group1",
                "pending_review": True,
                "global_filter_matches": "some_filter",
            })
            success, message = await repo.activate_pending(bangumi.id)
        
        assert success is True
        assert message == "Bangumi activated successfully"
        
        async with async_session.begin():
            found = await repo.get_by_id(bangumi.id)
        
        assert found.pending_review is False
        assert found.global_filter_matches is None

    async def test_activate_pending_with_filter_value(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            bangumi = await repo.create({
                "official_title": "Test Anime",
                "title_raw": "Test Anime",
                "season": 1,
                "group_name": "Group1",
                "pending_review": True,
                "filter": "old_filter",
            })
            success, message = await repo.activate_pending(bangumi.id, filter_value="new_filter")
        
        assert success is True
        
        async with async_session.begin():
            found = await repo.get_by_id(bangumi.id)
        
        assert found.filter == "new_filter"

    async def test_activate_pending_returns_false_when_not_found(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            success, message = await repo.activate_pending(99999)
        
        assert success is False
        assert message == "Bangumi not found"

    async def test_activate_pending_returns_false_when_not_pending(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            bangumi = await repo.create({
                "official_title": "Test Anime",
                "title_raw": "Test Anime",
                "season": 1,
                "group_name": "Group1",
                "pending_review": False,
            })
            success, message = await repo.activate_pending(bangumi.id)
        
        assert success is False
        assert message == "Bangumi is not pending review"

    async def test_update_pending_review_sets_pending_true(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            bangumi = await repo.create({
                "official_title": "Test Anime",
                "title_raw": "Test Anime",
                "season": 1,
                "group_name": "Group1",
                "pending_review": False,
            })
            success = await repo.update_pending_review(
                bangumi.id, 
                pending=True, 
                global_filter_matches="test_filter"
            )
        
        assert success is True
        
        async with async_session.begin():
            found = await repo.get_by_id(bangumi.id)
        
        assert found.pending_review is True
        assert found.global_filter_matches == "test_filter"

    async def test_update_pending_review_sets_pending_false(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            bangumi = await repo.create({
                "official_title": "Test Anime",
                "title_raw": "Test Anime",
                "season": 1,
                "group_name": "Group1",
                "pending_review": True,
                "global_filter_matches": "test_filter",
            })
            success = await repo.update_pending_review(bangumi.id, pending=False)
        
        assert success is True
        
        async with async_session.begin():
            found = await repo.get_by_id(bangumi.id)
        
        assert found.pending_review is False
        assert found.global_filter_matches is None

    async def test_update_pending_review_returns_false_when_not_found(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            success = await repo.update_pending_review(99999, pending=True)
        
        assert success is False

    async def test_delete_one_deletes_bangumi(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            bangumi = await repo.create({
                "official_title": "Test Anime",
                "title_raw": "Test Anime",
                "season": 1,
                "group_name": "Group1",
            })
            result = await repo.delete_one(bangumi.id)
        
        assert result is True
        
        async with async_session.begin():
            found = await repo.get_by_id(bangumi.id)
        
        assert found is None

    async def test_delete_one_returns_false_when_not_found(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            result = await repo.delete_one(99999)
        
        assert result is False

    async def test_delete_many_deletes_multiple_bangumi(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            b1 = await repo.create({
                "official_title": "Anime 1",
                "title_raw": "Anime 1",
                "season": 1,
                "group_name": "Group1",
            })
            b2 = await repo.create({
                "official_title": "Anime 2",
                "title_raw": "Anime 2",
                "season": 1,
                "group_name": "Group2",
            })
            await repo.create({
                "official_title": "Anime 3",
                "title_raw": "Anime 3",
                "season": 1,
                "group_name": "Group3",
            })
            count = await repo.delete_many([b1.id, b2.id])
        
        assert count == 2
        
        async with async_session.begin():
            all_bangumi = await repo.get_all(include_deleted=True)
        
        assert len(all_bangumi) == 1
        assert all_bangumi[0].official_title == "Anime 3"

    async def test_delete_many_returns_zero_for_empty_list(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            count = await repo.delete_many([])
        
        assert count == 0

    async def test_disable_many_soft_deletes_multiple_bangumi(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            b1 = await repo.create({
                "official_title": "Anime 1",
                "title_raw": "Anime 1",
                "season": 1,
                "group_name": "Group1",
            })
            b2 = await repo.create({
                "official_title": "Anime 2",
                "title_raw": "Anime 2",
                "season": 1,
                "group_name": "Group2",
            })
            count = await repo.disable_many([b1.id, b2.id])
        
        assert count == 2
        
        async with async_session.begin():
            all_bangumi = await repo.get_all(include_deleted=True)
        
        assert len(all_bangumi) == 2
        assert all(b.deleted is True for b in all_bangumi)

    async def test_disable_many_returns_zero_for_empty_list(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            count = await repo.disable_many([])
        
        assert count == 0

    async def test_delete_all_deletes_all_bangumi(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "Anime 1",
                "title_raw": "Anime 1",
                "season": 1,
                "group_name": "Group1",
            })
            await repo.create({
                "official_title": "Anime 2",
                "title_raw": "Anime 2",
                "season": 1,
                "group_name": "Group2",
            })
            await repo.delete_all()
        
        async with async_session.begin():
            all_bangumi = await repo.get_all(include_deleted=True)
        
        assert len(all_bangumi) == 0

    async def test_backfill_rss_id_updates_bangumi(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            b1 = await repo.create({
                "official_title": "Anime 1",
                "title_raw": "Anime 1",
                "season": 1,
                "group_name": "Group1",
                "rss_link": "https://example.com/rss/feed1",
            })
            b2 = await repo.create({
                "official_title": "Anime 2",
                "title_raw": "Anime 2",
                "season": 1,
                "group_name": "Group2",
                "rss_link": "https://example.com/rss/feed1",
            })
            await repo.create({
                "official_title": "Anime 3",
                "title_raw": "Anime 3",
                "season": 1,
                "group_name": "Group3",
                "rss_link": "https://other.com/rss/feed2",
            })
            count = await repo.backfill_rss_id(1, "https://example.com/rss/feed1")
        
        assert count == 2
        
        async with async_session.begin():
            found1 = await repo.get_by_id(b1.id)
            found2 = await repo.get_by_id(b2.id)
        
        assert found1.rss_id == 1
        assert found2.rss_id == 1

    async def test_backfill_rss_id_skips_already_set(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "official_title": "Anime 1",
                "title_raw": "Anime 1",
                "season": 1,
                "group_name": "Group1",
                "rss_link": "https://example.com/rss/feed1",
                "rss_id": 2,
            })
            count = await repo.backfill_rss_id(1, "https://example.com/rss/feed1")
        
        assert count == 0

    async def test_update_simple_updates_bangumi(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            bangumi = await repo.create({
                "official_title": "Test Anime",
                "title_raw": "Test Anime",
                "season": 1,
                "group_name": "Group1",
            })
            success = await repo.update_simple(bangumi.id, {"official_title": "Updated Anime"})
        
        assert success is True
        
        async with async_session.begin():
            found = await repo.get_by_id(bangumi.id)
        
        assert found.official_title == "Updated Anime"

    async def test_update_simple_returns_false_when_not_found(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            success = await repo.update_simple(99999, {"official_title": "Updated"})
        
        assert success is False

    async def test_update_simple_ignores_id_and_version(self, async_session):
        repo = BangumiRepository(async_session)
        
        async with async_session.begin():
            bangumi = await repo.create({
                "official_title": "Test Anime",
                "title_raw": "Test Anime",
                "season": 1,
                "group_name": "Group1",
            })
            original_id = bangumi.id
            await repo.update_simple(
                bangumi.id, 
                {"id": 99999, "version": 99999, "official_title": "Updated"}
            )
        
        async with async_session.begin():
            found = await repo.get_by_id(original_id)
        
        assert found.id == original_id
        assert found.official_title == "Updated"
