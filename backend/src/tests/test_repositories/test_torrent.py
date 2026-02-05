import pytest

from module.domain.models import Torrent, TorrentState
from module.repositories.torrent import TorrentRepository


@pytest.mark.asyncio
class TestTorrentRepository:
    async def test_create_torrent_success(self, async_session):
        repo = TorrentRepository(async_session)
        
        data = {
            "name": "Test Torrent",
            "url": "https://example.com/torrent",
            "hash": "abc123",
            "bangumi_id": 1,
            "state": TorrentState.PENDING,
        }
        
        async with async_session.begin():
            torrent = await repo.create(data)
        
        assert torrent.id is not None
        assert torrent.name == "Test Torrent"
        assert torrent.hash == "abc123"
        assert torrent.bangumi_id == 1

    async def test_create_torrent_composite_unique_hash_bangumi(self, async_session):
        repo = TorrentRepository(async_session)
        
        data1 = {
            "name": "Torrent 1",
            "url": "https://example.com/torrent1",
            "hash": "abc123",
            "bangumi_id": 1,
        }
        data2 = {
            "name": "Torrent 2",
            "url": "https://example.com/torrent2",
            "hash": "abc123",
            "bangumi_id": 1,
        }
        
        async with async_session.begin():
            await repo.create(data1)
        
        async with async_session.begin():
            with pytest.raises(Exception):
                await repo.create(data2)

    async def test_create_torrent_same_hash_different_bangumi_allowed(self, async_session):
        repo = TorrentRepository(async_session)
        
        data1 = {
            "name": "Torrent 1",
            "url": "https://example.com/torrent1",
            "hash": "abc123",
            "bangumi_id": 1,
        }
        data2 = {
            "name": "Torrent 2",
            "url": "https://example.com/torrent2",
            "hash": "abc123",
            "bangumi_id": 2,
        }
        
        async with async_session.begin():
            t1 = await repo.create(data1)
            t2 = await repo.create(data2)
        
        assert t1.id != t2.id
        assert t1.hash == t2.hash
        assert t1.bangumi_id != t2.bangumi_id

    async def test_create_torrent_null_hash_always_new(self, async_session):
        repo = TorrentRepository(async_session)
        
        data1 = {
            "name": "Torrent 1",
            "url": "https://example.com/torrent1",
            "hash": None,
            "bangumi_id": 1,
        }
        data2 = {
            "name": "Torrent 2",
            "url": "https://example.com/torrent2",
            "hash": None,
            "bangumi_id": 1,
        }
        
        async with async_session.begin():
            t1 = await repo.create(data1)
            t2 = await repo.create(data2)
        
        assert t1.id != t2.id
        assert t1.hash is None
        assert t2.hash is None
        assert t1.bangumi_id == t2.bangumi_id

    async def test_get_by_bangumi_returns_torrents(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "Torrent 1",
                "url": "https://example.com/t1",
                "hash": "hash1",
                "bangumi_id": 1,
            })
            await repo.create({
                "name": "Torrent 2",
                "url": "https://example.com/t2",
                "hash": "hash2",
                "bangumi_id": 1,
            })
            await repo.create({
                "name": "Torrent 3",
                "url": "https://example.com/t3",
                "hash": "hash3",
                "bangumi_id": 2,
            })
        
        async with async_session.begin():
            torrents = await repo.get_by_bangumi(1)
        
        assert len(torrents) == 2

    async def test_get_by_hash_returns_torrent(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "Torrent 1",
                "url": "https://example.com/t1",
                "hash": "abc123",
                "bangumi_id": 1,
            })
        
        async with async_session.begin():
            found = await repo.get_by_hash("abc123")
        
        assert found is not None
        assert found.hash == "abc123"

    async def test_get_by_rss_returns_torrents(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "Torrent 1",
                "url": "https://example.com/t1",
                "hash": "hash1",
                "rss_id": 1,
            })
            await repo.create({
                "name": "Torrent 2",
                "url": "https://example.com/t2",
                "hash": "hash2",
                "rss_id": 2,
            })
        
        async with async_session.begin():
            torrents = await repo.get_by_rss(1)
        
        assert len(torrents) == 1
        assert torrents[0].name == "Torrent 1"

    async def test_get_by_state_returns_torrents(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "Pending",
                "url": "https://example.com/t1",
                "hash": "hash1",
                "state": TorrentState.PENDING,
            })
            await repo.create({
                "name": "Completed",
                "url": "https://example.com/t2",
                "hash": "hash2",
                "state": TorrentState.COMPLETED,
            })
        
        async with async_session.begin():
            completed = await repo.get_by_state(TorrentState.COMPLETED)
        
        assert len(completed) == 1
        assert completed[0].name == "Completed"

    async def test_get_unrenamed_returns_completed_without_renamed_at(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "Unrenamed",
                "url": "https://example.com/t1",
                "hash": "hash1",
                "state": TorrentState.COMPLETED,
                "renamed_at": None,
            })
            t2 = await repo.create({
                "name": "Renamed",
                "url": "https://example.com/t2",
                "hash": "hash2",
                "state": TorrentState.COMPLETED,
            })
            await repo.mark_renamed(t2.id, 1)
        
        async with async_session.begin():
            unrenamed = await repo.get_unrenamed()
        
        assert len(unrenamed) == 1
        assert unrenamed[0].name == "Unrenamed"

    async def test_update_state_changes_state(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            torrent = await repo.create({
                "name": "Test",
                "url": "https://example.com/t1",
                "hash": "hash1",
                "state": TorrentState.PENDING,
            })
            await repo.update_state(torrent.id, TorrentState.DOWNLOADING)
        
        async with async_session.begin():
            updated = await repo.get_by_hash("hash1")
        
        assert updated.state == TorrentState.DOWNLOADING

    async def test_mark_renamed_sets_fields(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            torrent = await repo.create({
                "name": "Test",
                "url": "https://example.com/t1",
                "hash": "hash1",
                "state": TorrentState.COMPLETED,
            })
            await repo.mark_renamed(torrent.id, 3, "/cloud/path")
        
        async with async_session.begin():
            updated = await repo.get_by_hash("hash1")
        
        assert updated.renamed_at is not None
        assert updated.renamed_file_count == 3
        assert updated.pikpak_cloud_path == "/cloud/path"

    async def test_check_new_by_hash_returns_new_torrents(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "Existing",
                "url": "https://example.com/t1",
                "hash": "existing_hash",
                "bangumi_id": 1,
            })
        
        hashes = ["existing_hash", "new_hash1", "new_hash2"]
        
        async with async_session.begin():
            new_hashes = await repo.check_new_by_hash(hashes, bangumi_id=1)
        
        assert "existing_hash" not in new_hashes
        assert "new_hash1" in new_hashes
        assert "new_hash2" in new_hashes

    async def test_check_new_by_hash_same_hash_different_bangumi_is_new(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "Bangumi 1",
                "url": "https://example.com/t1",
                "hash": "shared_hash",
                "bangumi_id": 1,
            })
        
        hashes = ["shared_hash"]
        
        async with async_session.begin():
            new_for_bangumi2 = await repo.check_new_by_hash(hashes, bangumi_id=2)
        
        assert "shared_hash" in new_for_bangumi2

    async def test_check_new_by_hash_null_hash_always_new(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "Existing NULL",
                "url": "https://example.com/t1",
                "hash": None,
                "bangumi_id": 1,
            })
        
        hashes = [None, "hash1"]
        
        async with async_session.begin():
            new_hashes = await repo.check_new_by_hash(hashes, bangumi_id=1)
        
        assert None in new_hashes
        assert "hash1" in new_hashes

    async def test_clear_rename_status_clears_fields(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            t1 = await repo.create({
                "name": "Bangumi 1 Torrent",
                "url": "https://example.com/t1",
                "hash": "hash1",
                "bangumi_id": 1,
            })
            t2 = await repo.create({
                "name": "Bangumi 2 Torrent",
                "url": "https://example.com/t2",
                "hash": "hash2",
                "bangumi_id": 2,
            })
            await repo.mark_renamed(t1.id, 2, "/path1")
            await repo.mark_renamed(t2.id, 3, "/path2")
            
            await repo.clear_rename_status(bangumi_id=1)
        
        async with async_session.begin():
            t1_cleared = await repo.get_by_hash("hash1")
            t2_unchanged = await repo.get_by_hash("hash2")
        
        assert t1_cleared.renamed_at is None
        assert t1_cleared.renamed_file_count is None
        assert t1_cleared.pikpak_cloud_path is None
        
        assert t2_unchanged.renamed_at is not None
        assert t2_unchanged.renamed_file_count == 3
