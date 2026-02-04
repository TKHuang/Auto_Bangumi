import pytest

from zen_bangumi.repositories.rss import RSSRepository
from zen_bangumi.repositories.bangumi import BangumiRepository
from zen_bangumi.repositories.torrent import TorrentRepository


@pytest.mark.asyncio
async def test_create_rss_item(test_session):
    repo = RSSRepository(test_session)
    
    rss = await repo.create(
        url="https://example.com/rss",
        name="Test RSS",
        enabled=True,
        aggregate=False
    )
    
    assert rss.id is not None
    assert rss.url == "https://example.com/rss"
    assert rss.name == "Test RSS"
    assert rss.enabled is True
    assert rss.aggregate is False


@pytest.mark.asyncio
async def test_get_all(test_session):
    repo = RSSRepository(test_session)
    
    await repo.create("https://example.com/rss1", "RSS 1")
    await repo.create("https://example.com/rss2", "RSS 2")
    
    all_rss = await repo.get_all()
    assert len(all_rss) == 2


@pytest.mark.asyncio
async def test_get_enabled(test_session):
    repo = RSSRepository(test_session)
    
    enabled = await repo.create("https://example.com/rss1", "RSS 1", enabled=True)
    disabled = await repo.create("https://example.com/rss2", "RSS 2", enabled=False)
    
    enabled_list = await repo.get_enabled()
    enabled_ids = [r.id for r in enabled_list]
    
    assert enabled.id in enabled_ids
    assert disabled.id not in enabled_ids


@pytest.mark.asyncio
async def test_update_rss_item(test_session):
    repo = RSSRepository(test_session)
    
    rss = await repo.create("https://example.com/rss", "Original Name")
    
    updated = await repo.update(rss.id, {"name": "Updated Name", "enabled": False})
    
    assert updated.name == "Updated Name"
    assert updated.enabled is False
    assert updated.url == "https://example.com/rss"


@pytest.mark.asyncio
async def test_delete_rss_cascades_to_bangumi_and_torrents(test_session):
    rss_repo = RSSRepository(test_session)
    bangumi_repo = BangumiRepository(test_session)
    torrent_repo = TorrentRepository(test_session)
    
    rss = await rss_repo.create("https://example.com/rss", "Test RSS")
    
    bangumi = await bangumi_repo.create({
        "official_title": "Test Bangumi",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "Test Raw",
        "rss_id": rss.id,
    })
    
    torrent = await torrent_repo.create({
        "name": "Test Torrent",
        "url": "https://example.com/torrent",
        "hash": "hash123",
        "rss_id": rss.id,
        "bangumi_id": bangumi.id,
    })
    
    await rss_repo.delete(rss.id)
    
    assert await bangumi_repo.get_by_id(bangumi.id) is None
    assert await torrent_repo.get_by_hash("hash123") is None


@pytest.mark.asyncio
async def test_delete_nonexistent_rss_raises_error(test_session):
    repo = RSSRepository(test_session)
    
    with pytest.raises(ValueError, match="not found"):
        await repo.delete(9999)
