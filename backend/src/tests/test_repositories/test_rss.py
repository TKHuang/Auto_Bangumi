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
