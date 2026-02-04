import sqlite3
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from zen_bangumi.database.engine import (
    AsyncSessionLocal,
    create_all_tables,
    drop_all_tables,
    engine,
)
from zen_bangumi.domain.models.bangumi import Bangumi
from zen_bangumi.domain.models.rss import RSSItem
from zen_bangumi.domain.models.torrent import Torrent
from zen_bangumi.domain.models.user import User


@pytest_asyncio.fixture
async def session():
    await create_all_tables()
    async with AsyncSessionLocal() as session:
        yield session
    await drop_all_tables()


@pytest.mark.asyncio
async def test_wal_mode_enabled():
    await create_all_tables()
    
    conn = sqlite3.connect("./data/zen_bangumi.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode")
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    assert result[0].upper() == "WAL"
    
    await drop_all_tables()


@pytest.mark.asyncio
async def test_create_bangumi_with_defaults(session):
    bangumi = Bangumi(
        official_title="Test Bangumi",
        title_raw="Test Raw Title",
        season=1,
        group_name="TestGroup"
    )
    session.add(bangumi)
    await session.commit()
    
    result = await session.execute(select(Bangumi))
    saved = result.scalar_one()
    
    assert saved.id is not None
    assert saved.official_title == "Test Bangumi"
    assert saved.title_raw == "Test Raw Title"
    assert saved.season == 1
    assert saved.group_name == "TestGroup"
    assert saved.eps_collect is False
    assert saved.offset == 0
    assert saved.filter == "720,\\d+-\\d+"
    assert saved.rss_link == ""
    assert saved.added is False
    assert saved.deleted is False
    assert saved.pending_review is False
    assert saved.version == 1


@pytest.mark.asyncio
async def test_bangumi_composite_unique_constraint(session):
    bangumi1 = Bangumi(
        official_title="Test Bangumi",
        title_raw="Test Raw",
        season=1,
        group_name="TestGroup"
    )
    session.add(bangumi1)
    await session.commit()
    
    bangumi2 = Bangumi(
        official_title="Test Bangumi",
        title_raw="Different Raw",
        season=1,
        group_name="TestGroup"
    )
    session.add(bangumi2)
    
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_bangumi_version_increments_on_update(session):
    bangumi = Bangumi(
        official_title="Test Bangumi",
        title_raw="Test Raw",
        season=1,
        group_name="TestGroup"
    )
    session.add(bangumi)
    await session.commit()
    
    assert bangumi.version == 1
    
    bangumi.offset = 5
    bangumi.version += 1
    await session.commit()
    
    result = await session.execute(select(Bangumi).where(Bangumi.id == bangumi.id))
    updated = result.scalar_one()
    assert updated.version == 2
    assert updated.offset == 5


@pytest.mark.asyncio
async def test_create_torrent_with_hash_uniqueness(session):
    torrent1 = Torrent(
        name="Test Torrent 1",
        url="https://example.com/torrent1",
        hash="abc123def456"
    )
    session.add(torrent1)
    await session.commit()
    
    torrent2 = Torrent(
        name="Test Torrent 2",
        url="https://example.com/torrent2",
        hash="abc123def456"
    )
    session.add(torrent2)
    
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_torrent_renamed_at_nullable(session):
    torrent = Torrent(
        name="Test Torrent",
        url="https://example.com/torrent"
    )
    session.add(torrent)
    await session.commit()
    
    result = await session.execute(select(Torrent))
    saved = result.scalar_one()
    
    assert saved.renamed_at is None
    assert saved.renamed_file_count is None
    assert saved.pikpak_cloud_path is None
    assert saved.downloaded is False
    
    saved.renamed_at = datetime.now(timezone.utc)
    saved.renamed_file_count = 12
    saved.pikpak_cloud_path = "/cloud/path"
    await session.commit()
    
    result = await session.execute(select(Torrent).where(Torrent.id == saved.id))
    updated = result.scalar_one()
    assert updated.renamed_at is not None
    assert updated.renamed_file_count == 12
    assert updated.pikpak_cloud_path == "/cloud/path"


@pytest.mark.asyncio
async def test_create_rss_item(session):
    rss = RSSItem(
        name="Mikan RSS",
        url="https://mikanani.me/RSS/MyBangumi",
        aggregate=False,
        parser="mikan"
    )
    session.add(rss)
    await session.commit()
    
    result = await session.execute(select(RSSItem))
    saved = result.scalar_one()
    
    assert saved.id is not None
    assert saved.name == "Mikan RSS"
    assert saved.url == "https://mikanani.me/RSS/MyBangumi"
    assert saved.aggregate is False
    assert saved.parser == "mikan"
    assert saved.enabled is True
    assert saved.last_update is None
    assert saved.last_status is None
    assert saved.last_error is None


@pytest.mark.asyncio
async def test_create_user_with_unique_username(session):
    user1 = User(
        username="testuser",
        password_hash="hashed_password_123",
        created_at=datetime.now(timezone.utc)
    )
    session.add(user1)
    await session.commit()
    
    result = await session.execute(select(User))
    saved = result.scalar_one()
    
    assert saved.id is not None
    assert saved.username == "testuser"
    assert saved.password_hash == "hashed_password_123"
    assert saved.created_at is not None
    
    user2 = User(
        username="testuser",
        password_hash="different_hash",
        created_at=datetime.now(timezone.utc)
    )
    session.add(user2)
    
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_bangumi_nullable_fields(session):
    bangumi = Bangumi(
        official_title="Minimal Bangumi",
        title_raw="Minimal Raw",
        season=1,
        group_name="Group"
    )
    session.add(bangumi)
    await session.commit()
    
    result = await session.execute(select(Bangumi))
    saved = result.scalar_one()
    
    assert saved.rss_id is None
    assert saved.year is None
    assert saved.season_raw is None
    assert saved.dpi is None
    assert saved.source is None
    assert saved.subtitle is None
    assert saved.poster_link is None
    assert saved.rule_name is None
    assert saved.save_path is None
    assert saved.global_filter_matches is None
