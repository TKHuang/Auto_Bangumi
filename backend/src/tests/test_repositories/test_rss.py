import pytest

from module.domain.models import RSSItem
from module.repositories.rss import RSSRepository


@pytest.mark.asyncio
class TestRSSRepository:
    async def test_create_rss_success(self, async_session):
        repo = RSSRepository(async_session)
        
        data = {
            "name": "Test RSS",
            "url": "https://mikanani.me/RSS/MyBangumi",
            "enabled": True,
            "aggregate": False,
            "parser": "mikan",
        }
        
        async with async_session.begin():
            rss = await repo.create(data)
        
        assert rss.id is not None
        assert rss.name == "Test RSS"
        assert rss.enabled is True

    async def test_get_by_id_returns_rss(self, async_session):
        repo = RSSRepository(async_session)
        
        data = {
            "name": "Test RSS",
            "url": "https://mikanani.me/RSS/MyBangumi",
        }
        
        async with async_session.begin():
            created = await repo.create(data)
        
        async with async_session.begin():
            found = await repo.get_by_id(created.id)
        
        assert found is not None
        assert found.id == created.id

    async def test_get_all_returns_all_rss(self, async_session):
        repo = RSSRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "RSS 1",
                "url": "https://example.com/rss1",
            })
            await repo.create({
                "name": "RSS 2",
                "url": "https://example.com/rss2",
            })
        
        async with async_session.begin():
            all_rss = await repo.get_all()
        
        assert len(all_rss) == 2

    async def test_get_enabled_returns_only_enabled(self, async_session):
        repo = RSSRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "Enabled RSS",
                "url": "https://example.com/rss1",
                "enabled": True,
            })
            await repo.create({
                "name": "Disabled RSS",
                "url": "https://example.com/rss2",
                "enabled": False,
            })
        
        async with async_session.begin():
            enabled = await repo.get_enabled()
        
        assert len(enabled) == 1
        assert enabled[0].name == "Enabled RSS"

    async def test_update_rss_success(self, async_session):
        repo = RSSRepository(async_session)
        
        data = {
            "name": "Test RSS",
            "url": "https://example.com/rss1",
        }
        
        async with async_session.begin():
            rss = await repo.create(data)
            await repo.update(rss.id, {"name": "Updated RSS"})
        
        async with async_session.begin():
            updated = await repo.get_by_id(rss.id)
        
        assert updated.name == "Updated RSS"

    async def test_update_status_updates_fields(self, async_session):
        repo = RSSRepository(async_session)
        
        data = {
            "name": "Test RSS",
            "url": "https://example.com/rss1",
        }
        
        async with async_session.begin():
            rss = await repo.create(data)
            await repo.update_status(rss.id, "success", None)
        
        async with async_session.begin():
            updated = await repo.get_by_id(rss.id)
        
        assert updated.last_status == "success"
        assert updated.last_error is None
        assert updated.last_update is not None

    async def test_update_status_with_error(self, async_session):
        repo = RSSRepository(async_session)
        
        data = {
            "name": "Test RSS",
            "url": "https://example.com/rss1",
        }
        
        async with async_session.begin():
            rss = await repo.create(data)
            await repo.update_status(rss.id, "error", "Connection timeout")
        
        async with async_session.begin():
            updated = await repo.get_by_id(rss.id)
        
        assert updated.last_status == "error"
        assert updated.last_error == "Connection timeout"

    async def test_delete_rss_removes_from_db(self, async_session):
        repo = RSSRepository(async_session)
        
        data = {
            "name": "Test RSS",
            "url": "https://example.com/rss1",
        }
        
        async with async_session.begin():
            rss = await repo.create(data)
            await repo.delete(rss.id)
        
        async with async_session.begin():
            found = await repo.get_by_id(rss.id)
        
        assert found is None

    async def test_get_by_url_returns_rss(self, async_session):
        repo = RSSRepository(async_session)
        
        data = {
            "name": "Test RSS",
            "url": "https://mikanani.me/RSS/Unique",
        }
        
        async with async_session.begin():
            await repo.create(data)
        
        async with async_session.begin():
            found = await repo.get_by_url("https://mikanani.me/RSS/Unique")
        
        assert found is not None
        assert found.url == "https://mikanani.me/RSS/Unique"

    async def test_get_by_url_returns_none_when_not_found(self, async_session):
        repo = RSSRepository(async_session)
        
        async with async_session.begin():
            found = await repo.get_by_url("https://nonexistent.com/rss")
        
        assert found is None

    async def test_enable_sets_enabled_to_true(self, async_session):
        repo = RSSRepository(async_session)
        
        data = {
            "name": "Test RSS",
            "url": "https://example.com/rss1",
            "enabled": False,
        }
        
        async with async_session.begin():
            rss = await repo.create(data)
            result = await repo.enable(rss.id)
        
        async with async_session.begin():
            updated = await repo.get_by_id(rss.id)
        
        assert result is True
        assert updated.enabled is True

    async def test_enable_returns_false_when_rss_not_found(self, async_session):
        repo = RSSRepository(async_session)
        
        async with async_session.begin():
            result = await repo.enable(99999)
        
        assert result is False

    async def test_disable_sets_enabled_to_false(self, async_session):
        repo = RSSRepository(async_session)
        
        data = {
            "name": "Test RSS",
            "url": "https://example.com/rss1",
            "enabled": True,
        }
        
        async with async_session.begin():
            rss = await repo.create(data)
            result = await repo.disable(rss.id)
        
        async with async_session.begin():
            updated = await repo.get_by_id(rss.id)
        
        assert result is True
        assert updated.enabled is False

    async def test_disable_returns_false_when_rss_not_found(self, async_session):
        repo = RSSRepository(async_session)
        
        async with async_session.begin():
            result = await repo.disable(99999)
        
        assert result is False

    async def test_get_aggregate_returns_only_enabled_aggregate_rss(self, async_session):
        repo = RSSRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "Enabled Aggregate",
                "url": "https://example.com/aggregate1",
                "enabled": True,
                "aggregate": True,
            })
            await repo.create({
                "name": "Disabled Aggregate",
                "url": "https://example.com/aggregate2",
                "enabled": False,
                "aggregate": True,
            })
            await repo.create({
                "name": "Enabled Non-Aggregate",
                "url": "https://example.com/normal",
                "enabled": True,
                "aggregate": False,
            })
        
        async with async_session.begin():
            aggregates = await repo.get_aggregate()
        
        assert len(aggregates) == 1
        assert aggregates[0].name == "Enabled Aggregate"

    async def test_cascade_delete_removes_rss_and_related_data(self, async_session):
        from module.domain.models.bangumi import Bangumi
        from module.domain.models.series import Series
        from module.domain.models.torrent import Torrent

        repo = RSSRepository(async_session)

        async with async_session.begin():
            rss = await repo.create({
                "name": "Test RSS",
                "url": "https://example.com/rss1",
            })

            series = Series(
                canonical_title="Test Bangumi",
                normalized_title="test_bangumi",
                season=1,
                root_path="/downloads/Test",
            )
            async_session.add(series)
            await async_session.flush()

            bangumi = Bangumi(
                series_id=series.id,
                group_name="Group",
                rss_id=rss.id,
                rss_link=rss.url,
            )
            async_session.add(bangumi)
            await async_session.flush()
            
            torrent = Torrent(
                name="Test Torrent",
                bangumi_id=bangumi.id,
                rss_id=rss.id,
            )
            async_session.add(torrent)
            await async_session.flush()
            
            result = await repo.cascade_delete(rss.id)
        
        assert result is True
        
        async with async_session.begin():
            found_rss = await repo.get_by_id(rss.id)
            assert found_rss is None

    async def test_cascade_delete_returns_false_when_rss_not_found(self, async_session):
        repo = RSSRepository(async_session)

        async with async_session.begin():
            result = await repo.cascade_delete(99999)

        assert result is False

    async def test_collect_cascade_hashes_includes_direct_and_bangumi_children(
        self, async_session
    ):
        from module.domain.models.bangumi import Bangumi
        from module.domain.models.series import Series
        from module.domain.models.torrent import Torrent

        repo = RSSRepository(async_session)

        async with async_session.begin():
            rss = await repo.create({
                "name": "Feed",
                "url": "https://example.com/feed",
            })
            series = Series(
                canonical_title="S",
                normalized_title="s",
                season=1,
                root_path="/downloads/S",
            )
            async_session.add(series)
            await async_session.flush()

            linked = Bangumi(
                series_id=series.id,
                group_name="G",
                rss_id=rss.id,
                rss_link=rss.url,
            )
            fallback = Bangumi(
                series_id=series.id,
                group_name="G2",
                rss_id=None,
                rss_link=rss.url,
            )
            async_session.add_all([linked, fallback])
            await async_session.flush()

            async_session.add_all([
                Torrent(name="direct", hash="h_direct", rss_id=rss.id),
                Torrent(name="via_bangumi", hash="h_linked", bangumi_id=linked.id),
                Torrent(name="via_fallback", hash="h_fallback", bangumi_id=fallback.id),
                Torrent(name="dup", hash="h_direct", bangumi_id=linked.id),
                Torrent(name="excluded_empty", hash="", rss_id=rss.id),
                Torrent(name="null_hash", hash=None, rss_id=rss.id),
            ])
            await async_session.flush()

            hashes = await repo.collect_cascade_hashes(rss.id)

        assert set(hashes) == {"h_direct", "h_linked", "h_fallback"}
        assert len(hashes) == 3

    async def test_collect_cascade_hashes_unknown_rss_returns_empty(
        self, async_session
    ):
        repo = RSSRepository(async_session)
        async with async_session.begin():
            hashes = await repo.collect_cascade_hashes(99999)
        assert hashes == []

    async def test_set_status_updates_last_status(self, async_session):
        repo = RSSRepository(async_session)
        
        data = {
            "name": "Test RSS",
            "url": "https://example.com/rss1",
        }
        
        async with async_session.begin():
            rss = await repo.create(data)
            result = await repo.set_status(rss.id, "processing")
        
        async with async_session.begin():
            updated = await repo.get_by_id(rss.id)
        
        assert result is True
        assert updated.last_status == "processing"

    async def test_set_status_returns_false_when_rss_not_found(self, async_session):
        repo = RSSRepository(async_session)

        async with async_session.begin():
            result = await repo.set_status(99999, "processing")

        assert result is False

    async def test_cascade_delete_garbage_collects_orphan_series(
        self, async_session
    ):
        from sqlalchemy import func, select

        from module.domain.models import Bangumi
        from module.domain.models.series import Series

        repo = RSSRepository(async_session)

        async with async_session.begin():
            rss = RSSItem(name="feed", url="https://x/y", parser="mikan")
            series = Series(
                canonical_title="T",
                normalized_title="t",
                season=1,
                root_path="/r",
            )
            async_session.add_all([rss, series])
            await async_session.flush()

            async_session.add(
                Bangumi(series_id=series.id, rss_id=rss.id, group_name="G")
            )

        async with async_session.begin():
            assert await repo.cascade_delete(rss.id) is True

        async with async_session.begin():
            total = await async_session.execute(
                select(func.count()).select_from(Series)
            )
            assert total.scalar_one() == 0

    async def test_cascade_delete_keeps_series_with_surviving_bangumi(
        self, async_session
    ):
        from sqlalchemy import select

        from module.domain.models import Bangumi
        from module.domain.models.series import Series

        repo = RSSRepository(async_session)

        async with async_session.begin():
            rss_a = RSSItem(name="a", url="https://x/a", parser="mikan")
            rss_b = RSSItem(name="b", url="https://x/b", parser="mikan")
            series = Series(
                canonical_title="T",
                normalized_title="t",
                season=1,
                root_path="/r",
            )
            async_session.add_all([rss_a, rss_b, series])
            await async_session.flush()

            async_session.add_all([
                Bangumi(series_id=series.id, rss_id=rss_a.id, group_name="A"),
                Bangumi(series_id=series.id, rss_id=rss_b.id, group_name="B"),
            ])

        async with async_session.begin():
            assert await repo.cascade_delete(rss_a.id) is True

        async with async_session.begin():
            survivor = (
                await async_session.execute(
                    select(Series).where(Series.id == series.id)
                )
            ).scalar_one_or_none()
            assert survivor is not None
