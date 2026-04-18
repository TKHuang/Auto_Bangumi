import pytest

from module.domain.models import Torrent, TorrentState
from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.repositories.torrent import TorrentRepository


async def _create_series_and_bangumi(session) -> int:
    """Create a minimal Series + Bangumi row and return bangumi.id."""
    s = Series(
        canonical_title="Test", normalized_title="test", season=1,
        root_path="/test", pending_review=False,
    )
    session.add(s)
    await session.flush()
    b = Bangumi(group_name="G", rss_link="", series_id=s.id, active=True)
    session.add(b)
    await session.flush()
    return b.id


@pytest.mark.anyio
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

    async def test_get_unrenamed_returns_completed_without_renamed_at(self, async_session):
        repo = TorrentRepository(async_session)

        async with async_session.begin():
            bangumi_id = await _create_series_and_bangumi(async_session)
            await repo.create({
                "name": "Unrenamed",
                "url": "https://example.com/t1",
                "hash": "hash1",
                "bangumi_id": bangumi_id,
                "state": TorrentState.COMPLETED,
                "downloaded": True,
                "renamed_at": None,
            })
            t2 = await repo.create({
                "name": "Renamed",
                "url": "https://example.com/t2",
                "hash": "hash2",
                "bangumi_id": bangumi_id,
                "state": TorrentState.COMPLETED,
                "downloaded": True,
            })
            await repo.mark_renamed(t2.id, 1)

        async with async_session.begin():
            unrenamed = await repo.get_unrenamed()

        assert len(unrenamed) == 1
        assert unrenamed[0].name == "Unrenamed"

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
        assert t1_cleared.pikpak_cloud_path == "/path1"
        
        assert t2_unchanged.renamed_at is not None
        assert t2_unchanged.renamed_file_count == 3

    async def test_get_by_id_returns_torrent(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            torrent = await repo.create({
                "name": "Test Torrent",
                "url": "https://example.com/t1",
                "hash": "hash1",
                "bangumi_id": 1,
            })
            torrent_id = torrent.id
        
        async with async_session.begin():
            found = await repo.get_by_id(torrent_id)
        
        assert found is not None
        assert found.id == torrent_id
        assert found.name == "Test Torrent"

    async def test_get_by_id_returns_none_for_nonexistent(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            found = await repo.get_by_id(99999)
        
        assert found is None

    async def test_get_all_returns_all_torrents(self, async_session):
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
                "bangumi_id": 2,
            })
            await repo.create({
                "name": "Torrent 3",
                "url": "https://example.com/t3",
                "hash": "hash3",
                "bangumi_id": 1,
            })
        
        async with async_session.begin():
            all_torrents = await repo.get_all()
        
        assert len(all_torrents) == 3

    async def test_get_by_bangumi_with_homepage_returns_torrent_with_homepage(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "No Homepage",
                "url": "https://example.com/t1",
                "hash": "hash1",
                "bangumi_id": 1,
                "homepage": None,
            })
            await repo.create({
                "name": "Empty Homepage",
                "url": "https://example.com/t2",
                "hash": "hash2",
                "bangumi_id": 1,
                "homepage": "",
            })
            await repo.create({
                "name": "With Homepage",
                "url": "https://example.com/t3",
                "hash": "hash3",
                "bangumi_id": 1,
                "homepage": "https://mikan.me/Home/Episode/123",
            })
        
        async with async_session.begin():
            found = await repo.get_by_bangumi_with_homepage(1)
        
        assert found is not None
        assert found.name == "With Homepage"
        assert found.homepage == "https://mikan.me/Home/Episode/123"

    async def test_get_by_bangumi_with_homepage_returns_none_if_no_homepage(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "No Homepage",
                "url": "https://example.com/t1",
                "hash": "hash1",
                "bangumi_id": 1,
                "homepage": None,
            })
        
        async with async_session.begin():
            found = await repo.get_by_bangumi_with_homepage(1)
        
        assert found is None

    async def test_get_unrenamed_hashes_returns_set_of_hashes(self, async_session):
        repo = TorrentRepository(async_session)

        async with async_session.begin():
            bangumi_id = await _create_series_and_bangumi(async_session)
            await repo.create({
                "name": "Unrenamed 1",
                "url": "https://example.com/t1",
                "hash": "HASH1",
                "bangumi_id": bangumi_id,
                "renamed_at": None,
            })
            await repo.create({
                "name": "Unrenamed 2",
                "url": "https://example.com/t2",
                "hash": "HASH2",
                "bangumi_id": bangumi_id,
                "renamed_at": None,
            })
            t3 = await repo.create({
                "name": "Renamed",
                "url": "https://example.com/t3",
                "hash": "HASH3",
                "bangumi_id": bangumi_id,
            })
            await repo.mark_renamed(t3.id, 1)

        async with async_session.begin():
            hashes = await repo.get_unrenamed_hashes()

        assert len(hashes) == 2
        assert "hash1" in hashes
        assert "hash2" in hashes
        assert "hash3" not in hashes

    async def test_get_unrenamed_hashes_excludes_null_hashes(self, async_session):
        repo = TorrentRepository(async_session)

        async with async_session.begin():
            bangumi_id = await _create_series_and_bangumi(async_session)
            await repo.create({
                "name": "No Hash",
                "url": "https://example.com/t1",
                "hash": None,
                "bangumi_id": bangumi_id,
            })
            await repo.create({
                "name": "Has Hash",
                "url": "https://example.com/t2",
                "hash": "hash1",
                "bangumi_id": bangumi_id,
            })
        
        async with async_session.begin():
            hashes = await repo.get_unrenamed_hashes()
        
        assert len(hashes) == 1
        assert "hash1" in hashes

    async def test_mark_downloaded_by_hash_marks_torrent_downloaded(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "Test Torrent",
                "url": "https://example.com/t1",
                "hash": "hash1",
                "bangumi_id": 1,
                "downloaded": False,
            })
            rowcount = await repo.mark_downloaded_by_hash("hash1", 1)
        
        async with async_session.begin():
            torrent = await repo.get_by_hash("hash1")
        
        assert rowcount == 1
        assert torrent.downloaded is True

    async def test_mark_downloaded_by_hash_with_save_path(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "Test Torrent",
                "url": "https://example.com/t1",
                "hash": "hash1",
                "bangumi_id": 1,
                "downloaded": False,
            })
            rowcount = await repo.mark_downloaded_by_hash("hash1", 1, "/cloud/path")
        
        async with async_session.begin():
            torrent = await repo.get_by_hash("hash1")
        
        assert rowcount == 1
        assert torrent.downloaded is True
        assert torrent.pikpak_cloud_path == "/cloud/path"

    async def test_mark_downloaded_by_hash_respects_bangumi_id(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "Bangumi 1",
                "url": "https://example.com/t1",
                "hash": "shared_hash",
                "bangumi_id": 1,
                "downloaded": False,
            })
            await repo.create({
                "name": "Bangumi 2",
                "url": "https://example.com/t2",
                "hash": "shared_hash",
                "bangumi_id": 2,
                "downloaded": False,
            })
            rowcount = await repo.mark_downloaded_by_hash("shared_hash", 1)
        
        async with async_session.begin():
            t1 = await repo.get_by_bangumi(1)
            t2 = await repo.get_by_bangumi(2)
        
        assert rowcount == 1
        assert t1[0].downloaded is True
        assert t2[0].downloaded is False

    async def test_delete_by_bangumi_deletes_torrents(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "Bangumi 1 Torrent 1",
                "url": "https://example.com/t1",
                "hash": "hash1",
                "bangumi_id": 1,
            })
            await repo.create({
                "name": "Bangumi 1 Torrent 2",
                "url": "https://example.com/t2",
                "hash": "hash2",
                "bangumi_id": 1,
            })
            await repo.create({
                "name": "Bangumi 2 Torrent",
                "url": "https://example.com/t3",
                "hash": "hash3",
                "bangumi_id": 2,
            })
            
            await repo.delete_by_bangumi(1)
        
        async with async_session.begin():
            bangumi1_torrents = await repo.get_by_bangumi(1)
            bangumi2_torrents = await repo.get_by_bangumi(2)
        
        assert len(bangumi1_torrents) == 0
        assert len(bangumi2_torrents) == 1

    async def test_delete_by_rss_deletes_torrents(self, async_session):
        repo = TorrentRepository(async_session)
        
        async with async_session.begin():
            await repo.create({
                "name": "RSS 1 Torrent 1",
                "url": "https://example.com/t1",
                "hash": "hash1",
                "rss_id": 1,
            })
            await repo.create({
                "name": "RSS 1 Torrent 2",
                "url": "https://example.com/t2",
                "hash": "hash2",
                "rss_id": 1,
            })
            await repo.create({
                "name": "RSS 2 Torrent",
                "url": "https://example.com/t3",
                "hash": "hash3",
                "rss_id": 2,
            })
            
            await repo.delete_by_rss(1)
        
        async with async_session.begin():
            rss1_torrents = await repo.get_by_rss(1)
            rss2_torrents = await repo.get_by_rss(2)
        
        assert len(rss1_torrents) == 0
        assert len(rss2_torrents) == 1

    # --- EXCLUDED state tests ---

    async def test_get_visible_by_bangumi_filters_excluded(self, async_session):
        repo = TorrentRepository(async_session)

        async with async_session.begin():
            await repo.create({
                "name": "Normal Torrent",
                "url": "https://example.com/t1",
                "hash": "hash_normal",
                "bangumi_id": 1,
            })
            await repo.create({
                "name": "",
                "url": "",
                "hash": "hash_excluded",
                "bangumi_id": 1,
                "downloaded": True,
                "state": TorrentState.EXCLUDED,
            })

        async with async_session.begin():
            all_torrents = await repo.get_by_bangumi(1)
            visible_torrents = await repo.get_visible_by_bangumi(1)

        assert len(all_torrents) == 2
        assert len(visible_torrents) == 1
        assert visible_torrents[0].hash == "hash_normal"

    async def test_get_visible_by_rss_filters_excluded(self, async_session):
        repo = TorrentRepository(async_session)

        async with async_session.begin():
            await repo.create({
                "name": "Normal Torrent",
                "url": "https://example.com/t1",
                "hash": "hash_normal",
                "rss_id": 1,
                "bangumi_id": 1,
            })
            await repo.create({
                "name": "",
                "url": "",
                "hash": "hash_excluded",
                "rss_id": 1,
                "bangumi_id": 2,
                "downloaded": True,
                "state": TorrentState.EXCLUDED,
            })

        async with async_session.begin():
            all_torrents = await repo.get_by_rss(1)
            visible_torrents = await repo.get_visible_by_rss(1)

        assert len(all_torrents) == 2
        assert len(visible_torrents) == 1
        assert visible_torrents[0].hash == "hash_normal"

    async def test_add_all_or_ignore_writes_excluded_state(self, async_session):
        repo = TorrentRepository(async_session)

        excluded = Torrent(
            name="",
            url="",
            hash="hash_excl",
            bangumi_id=1,
            downloaded=True,
            state=TorrentState.EXCLUDED,
        )

        async with async_session.begin():
            await repo.add_all_or_ignore([excluded])

        async with async_session.begin():
            torrent = await repo.get_by_hash("hash_excl")

        assert torrent is not None
        assert torrent.state == TorrentState.EXCLUDED
        assert torrent.downloaded is True
        assert torrent.name == ""

    async def test_get_unrenamed_excludes_excluded_state(self, async_session):
        repo = TorrentRepository(async_session)

        async with async_session.begin():
            bangumi_id = await _create_series_and_bangumi(async_session)
            await repo.create({
                "name": "Unrenamed Torrent",
                "url": "https://example.com/t1",
                "hash": "hash_unrenamed",
                "bangumi_id": bangumi_id,
                "downloaded": True,
            })
            await repo.create({
                "name": "",
                "url": "",
                "hash": "hash_excluded",
                "bangumi_id": bangumi_id,
                "downloaded": True,
                "state": TorrentState.EXCLUDED,
            })

        async with async_session.begin():
            unrenamed = await repo.get_unrenamed()
            unrenamed_hashes = await repo.get_unrenamed_hashes()

        assert len(unrenamed) == 1
        assert unrenamed[0].hash == "hash_unrenamed"
        assert "hash_excluded" not in unrenamed_hashes
        assert "hash_unrenamed" in unrenamed_hashes

    async def test_clear_rename_status_skips_excluded(self, async_session):
        repo = TorrentRepository(async_session)
        from datetime import datetime, timezone

        async with async_session.begin():
            await repo.create({
                "name": "Normal Torrent",
                "url": "https://example.com/t1",
                "hash": "hash_normal",
                "bangumi_id": 1,
                "renamed_at": datetime.now(timezone.utc),
                "renamed_file_count": 3,
            })
            await repo.create({
                "name": "",
                "url": "",
                "hash": "hash_excluded",
                "bangumi_id": 1,
                "downloaded": True,
                "state": TorrentState.EXCLUDED,
            })

        async with async_session.begin():
            await repo.clear_rename_status(1)

        async with async_session.begin():
            normal = await repo.get_by_hash("hash_normal")
            excluded = await repo.get_by_hash("hash_excluded")

        assert normal.renamed_at is None
        assert excluded.state == TorrentState.EXCLUDED

    async def test_dedup_still_works_with_excluded(self, async_session):
        repo = TorrentRepository(async_session)

        excluded = Torrent(
            name="", url="", hash="hash_dedup", bangumi_id=1,
            downloaded=True, state=TorrentState.EXCLUDED,
        )
        normal = Torrent(
            name="Normal", url="https://example.com", hash="hash_dedup", bangumi_id=1,
        )

        async with async_session.begin():
            count1 = await repo.add_all_or_ignore([excluded])

        async with async_session.begin():
            count2 = await repo.add_all_or_ignore([normal])

        assert count1 == 1
        assert count2 == 0  # conflict: same hash+bangumi_id, skipped

        async with async_session.begin():
            torrent = await repo.get_by_hash("hash_dedup")

        assert torrent.state == TorrentState.EXCLUDED  # original stays

    async def test_delete_all_removes_all_torrents(self, async_session):
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
                "bangumi_id": 2,
            })

            await repo.delete_all()

        async with async_session.begin():
            all_torrents = await repo.get_all()

        assert len(all_torrents) == 0


@pytest.mark.integration
async def test_backfill_mikan_ids_persists_both(db_session):
    from module.repositories.torrent import TorrentRepository
    from module.domain.models.torrent import Torrent

    repo = TorrentRepository(db_session)
    t = Torrent(name="x", url="https://e.com", hash="abc", bangumi_id=None, rss_id=None)
    db_session.add(t)
    await db_session.flush()

    await repo.backfill_mikan_ids(t.id, mikan_bangumi_id=3906, mikan_subgroup_id=370)
    await db_session.refresh(t)
    assert t.mikan_bangumi_id == 3906
    assert t.mikan_subgroup_id == 370
