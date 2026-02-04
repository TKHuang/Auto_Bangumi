import pytest
from datetime import datetime, timezone

from zen_bangumi.domain.models.torrent import Torrent
from zen_bangumi.repositories.torrent import TorrentRepository


@pytest.mark.asyncio
async def test_create_torrent(test_session):
    repo = TorrentRepository(test_session)
    data = {
        "name": "Test Torrent",
        "url": "https://example.com/torrent1",
        "hash": "abc123def456",
        "bangumi_id": 1,
    }
    torrent = await repo.create(data)
    
    assert torrent.id is not None
    assert torrent.name == "Test Torrent"
    assert torrent.hash == "abc123def456"
    assert torrent.bangumi_id == 1


@pytest.mark.asyncio
async def test_create_torrent_with_duplicate_hash_returns_existing(test_session):
    repo = TorrentRepository(test_session)
    
    data1 = {
        "name": "Torrent 1",
        "url": "https://example.com/torrent1",
        "hash": "duplicate_hash",
    }
    first = await repo.create(data1)
    
    data2 = {
        "name": "Torrent 2",
        "url": "https://example.com/torrent2",
        "hash": "duplicate_hash",
    }
    second = await repo.create(data2)
    
    assert first.id == second.id
    assert second.name == "Torrent 1"


@pytest.mark.asyncio
async def test_get_by_hash(test_session):
    repo = TorrentRepository(test_session)
    
    data = {
        "name": "Test Torrent",
        "url": "https://example.com/torrent1",
        "hash": "unique_hash",
    }
    created = await repo.create(data)
    
    retrieved = await repo.get_by_hash("unique_hash")
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.hash == "unique_hash"


@pytest.mark.asyncio
async def test_get_unrenamed(test_session):
    repo = TorrentRepository(test_session)
    
    renamed = await repo.create({
        "name": "Renamed Torrent",
        "url": "https://example.com/torrent1",
        "hash": "hash1",
        "bangumi_id": 1,
        "renamed_at": datetime.now(timezone.utc),
    })
    
    unrenamed = await repo.create({
        "name": "Unrenamed Torrent",
        "url": "https://example.com/torrent2",
        "hash": "hash2",
        "bangumi_id": 1,
    })
    
    unrenamed_list = await repo.get_unrenamed(1)
    unrenamed_ids = [t.id for t in unrenamed_list]
    
    assert unrenamed.id in unrenamed_ids
    assert renamed.id not in unrenamed_ids


@pytest.mark.asyncio
async def test_mark_renamed(test_session):
    repo = TorrentRepository(test_session)
    
    torrent = await repo.create({
        "name": "Test Torrent",
        "url": "https://example.com/torrent1",
        "hash": "hash1",
        "bangumi_id": 1,
    })
    
    assert torrent.renamed_at is None
    
    updated = await repo.mark_renamed(torrent.id, file_count=3, cloud_path="/path/to/files")
    
    assert updated.renamed_at is not None
    assert updated.renamed_file_count == 3
    assert updated.pikpak_cloud_path == "/path/to/files"


@pytest.mark.asyncio
async def test_mark_renamed_without_cloud_path(test_session):
    repo = TorrentRepository(test_session)
    
    torrent = await repo.create({
        "name": "Test Torrent",
        "url": "https://example.com/torrent1",
        "hash": "hash1",
        "bangumi_id": 1,
    })
    
    updated = await repo.mark_renamed(torrent.id, file_count=5)
    
    assert updated.renamed_at is not None
    assert updated.renamed_file_count == 5
    assert updated.pikpak_cloud_path is None


@pytest.mark.asyncio
async def test_get_by_bangumi(test_session):
    repo = TorrentRepository(test_session)
    
    torrent1 = await repo.create({
        "name": "Torrent 1",
        "url": "https://example.com/torrent1",
        "hash": "hash1",
        "bangumi_id": 1,
    })
    
    torrent2 = await repo.create({
        "name": "Torrent 2",
        "url": "https://example.com/torrent2",
        "hash": "hash2",
        "bangumi_id": 1,
    })
    
    torrent3 = await repo.create({
        "name": "Torrent 3",
        "url": "https://example.com/torrent3",
        "hash": "hash3",
        "bangumi_id": 2,
    })
    
    bangumi1_torrents = await repo.get_by_bangumi(1)
    bangumi1_ids = [t.id for t in bangumi1_torrents]
    
    assert len(bangumi1_torrents) == 2
    assert torrent1.id in bangumi1_ids
    assert torrent2.id in bangumi1_ids
    assert torrent3.id not in bangumi1_ids


@pytest.mark.asyncio
async def test_create_torrent_without_hash(test_session):
    repo = TorrentRepository(test_session)
    
    data = {
        "name": "Test Torrent",
        "url": "https://example.com/torrent1",
        "bangumi_id": 1,
    }
    torrent = await repo.create(data)
    
    assert torrent.id is not None
    assert torrent.hash is None
