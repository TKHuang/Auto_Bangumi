import pytest

from zen_bangumi.domain.models.bangumi import Bangumi
from zen_bangumi.repositories.bangumi import BangumiRepository
from zen_bangumi.repositories.exceptions import ConcurrentModificationError


@pytest.mark.asyncio
async def test_create_bangumi(test_session):
    repo = BangumiRepository(test_session)
    data = {
        "official_title": "Test Bangumi",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "Test Raw Title",
    }
    bangumi = await repo.create(data)
    
    assert bangumi.id is not None
    assert bangumi.official_title == "Test Bangumi"
    assert bangumi.season == 1
    assert bangumi.group_name == "TestGroup"
    assert bangumi.version == 1


@pytest.mark.asyncio
async def test_create_bangumi_with_empty_group_name_defaults_to_unknown(test_session):
    repo = BangumiRepository(test_session)
    data = {
        "official_title": "Test Bangumi",
        "season": 1,
        "group_name": "",
        "title_raw": "Test Raw Title",
    }
    bangumi = await repo.create(data)
    
    assert bangumi.group_name == "Unknown"


@pytest.mark.asyncio
async def test_create_duplicate_composite_key_raises_error(test_session):
    repo = BangumiRepository(test_session)
    data = {
        "official_title": "Test Bangumi",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "Test Raw Title",
    }
    await repo.create(data)
    
    with pytest.raises(ValueError, match="already exists"):
        await repo.create(data)


@pytest.mark.asyncio
async def test_get_by_id(test_session):
    repo = BangumiRepository(test_session)
    data = {
        "official_title": "Test Bangumi",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "Test Raw Title",
    }
    created = await repo.create(data)
    
    retrieved = await repo.get_by_id(created.id)
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.official_title == "Test Bangumi"


@pytest.mark.asyncio
async def test_get_by_composite_key(test_session):
    repo = BangumiRepository(test_session)
    data = {
        "official_title": "Test Bangumi",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "Test Raw Title",
    }
    await repo.create(data)
    
    retrieved = await repo.get_by_composite_key("Test Bangumi", 1, "TestGroup")
    assert retrieved is not None
    assert retrieved.official_title == "Test Bangumi"
    assert retrieved.season == 1
    assert retrieved.group_name == "TestGroup"


@pytest.mark.asyncio
async def test_update_with_correct_version(test_session):
    repo = BangumiRepository(test_session)
    data = {
        "official_title": "Test Bangumi",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "Test Raw Title",
    }
    created = await repo.create(data)
    
    updated = await repo.update(
        created.id,
        {"offset": 5},
        expected_version=1
    )
    
    assert updated.offset == 5
    assert updated.version == 2


@pytest.mark.asyncio
async def test_update_with_wrong_version_raises_concurrent_modification_error(test_session):
    repo = BangumiRepository(test_session)
    data = {
        "official_title": "Test Bangumi",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "Test Raw Title",
    }
    created = await repo.create(data)
    
    with pytest.raises(ConcurrentModificationError) as exc_info:
        await repo.update(created.id, {"offset": 5}, expected_version=999)
    
    assert exc_info.value.entity_type == "Bangumi"
    assert exc_info.value.entity_id == created.id
    assert exc_info.value.expected_version == 999


@pytest.mark.asyncio
async def test_delete_soft_deletes_bangumi(test_session):
    repo = BangumiRepository(test_session)
    data = {
        "official_title": "Test Bangumi",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "Test Raw Title",
    }
    created = await repo.create(data)
    
    await repo.delete(created.id)
    
    retrieved = await repo.get_by_id(created.id)
    assert retrieved is not None
    assert retrieved.deleted is True


@pytest.mark.asyncio
async def test_get_active_excludes_deleted_and_pending(test_session):
    repo = BangumiRepository(test_session)
    
    active = await repo.create({
        "official_title": "Active Bangumi",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "Active Raw",
        "pending_review": False,
    })
    
    deleted = await repo.create({
        "official_title": "Deleted Bangumi",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "Deleted Raw",
    })
    await repo.delete(deleted.id)
    
    pending = await repo.create({
        "official_title": "Pending Bangumi",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "Pending Raw",
        "pending_review": True,
    })
    
    active_list = await repo.get_active()
    active_ids = [b.id for b in active_list]
    
    assert active.id in active_ids
    assert deleted.id not in active_ids
    assert pending.id not in active_ids


@pytest.mark.asyncio
async def test_get_pending_review(test_session):
    repo = BangumiRepository(test_session)
    
    active = await repo.create({
        "official_title": "Active Bangumi",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "Active Raw",
        "pending_review": False,
    })
    
    pending = await repo.create({
        "official_title": "Pending Bangumi",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "Pending Raw",
        "pending_review": True,
    })
    
    pending_list = await repo.get_pending_review()
    pending_ids = [b.id for b in pending_list]
    
    assert pending.id in pending_ids
    assert active.id not in pending_ids


@pytest.mark.asyncio
async def test_match_torrent_finds_matching_bangumi(test_session):
    repo = BangumiRepository(test_session)
    
    bangumi = await repo.create({
        "official_title": "Test Bangumi",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "[TestGroup] Test Bangumi",
        "pending_review": False,
    })
    
    parsed_info = {
        "name": "[TestGroup] Test Bangumi - 01 [1080p].mkv"
    }
    
    matched = await repo.match_torrent(parsed_info)
    assert matched is not None
    assert matched.id == bangumi.id


@pytest.mark.asyncio
async def test_match_torrent_returns_none_for_pending_bangumi(test_session):
    repo = BangumiRepository(test_session)
    
    await repo.create({
        "official_title": "Pending Bangumi",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "[TestGroup] Pending",
        "pending_review": True,
    })
    
    parsed_info = {
        "name": "[TestGroup] Pending - 01 [1080p].mkv"
    }
    
    matched = await repo.match_torrent(parsed_info)
    assert matched is None


@pytest.mark.asyncio
async def test_get_all_with_filters(test_session):
    repo = BangumiRepository(test_session)
    
    await repo.create({
        "official_title": "Bangumi A",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "A",
        "rss_id": 1,
    })
    
    await repo.create({
        "official_title": "Bangumi B",
        "season": 1,
        "group_name": "TestGroup",
        "title_raw": "B",
        "rss_id": 2,
    })
    
    filtered = await repo.get_all(filters={"rss_id": 1})
    assert len(filtered) == 1
    assert filtered[0].official_title == "Bangumi A"
