"""Tests for domain models."""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from module.domain.models import (
    Base,
    Bangumi,
    RSSItem,
    Torrent,
    TorrentState,
    User,
)


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


class TestBase:
    def test_all_models_create_tables_successfully(self, engine):
        tables = Base.metadata.tables.keys()
        assert "bangumi" in tables
        assert "torrent" in tables
        assert "rssitem" in tables
        assert "user" in tables


class TestTimestampMixin:
    def test_created_at_auto_set(self, session):
        bangumi = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test Raw",
            season=1,
            group_name="TestGroup",
        )
        session.add(bangumi)
        session.commit()
        session.refresh(bangumi)

        assert bangumi.created_at is not None
        assert isinstance(bangumi.created_at, datetime)

    def test_updated_at_auto_set(self, session):
        bangumi = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test Raw",
            season=1,
            group_name="TestGroup",
        )
        session.add(bangumi)
        session.commit()
        session.refresh(bangumi)

        assert bangumi.updated_at is not None
        assert isinstance(bangumi.updated_at, datetime)

    def test_updated_at_changes_on_update(self, session):
        bangumi = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test Raw",
            season=1,
            group_name="TestGroup",
        )
        session.add(bangumi)
        session.commit()
        session.refresh(bangumi)

        original_updated_at = bangumi.updated_at

        bangumi.official_title = "Updated Title"
        session.commit()
        session.refresh(bangumi)

        assert bangumi.updated_at > original_updated_at


class TestVersionMixin:
    def test_version_starts_at_one(self, session):
        bangumi = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test Raw",
            season=1,
            group_name="TestGroup",
        )
        session.add(bangumi)
        session.commit()
        session.refresh(bangumi)

        assert bangumi.version == 1

    def test_version_increments_on_update(self, session):
        bangumi = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test Raw",
            season=1,
            group_name="TestGroup",
        )
        session.add(bangumi)
        session.commit()
        session.refresh(bangumi)

        assert bangumi.version == 1

        bangumi.official_title = "Updated Title"
        session.commit()
        session.refresh(bangumi)

        assert bangumi.version == 2

        bangumi.season = 2
        session.commit()
        session.refresh(bangumi)

        assert bangumi.version == 3


class TestBangumi:
    def test_unique_constraint_official_title_season_group_name(self, session):
        bangumi1 = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test Raw",
            season=1,
            group_name="TestGroup",
        )
        session.add(bangumi1)
        session.commit()

        bangumi2 = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test Raw",
            season=1,
            group_name="TestGroup",
        )
        session.add(bangumi2)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_unique_constraint_allows_different_season(self, session):
        bangumi1 = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test Raw",
            season=1,
            group_name="TestGroup",
        )
        session.add(bangumi1)
        session.commit()

        bangumi2 = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test Raw",
            season=2,
            group_name="TestGroup",
        )
        session.add(bangumi2)
        session.commit()

        assert bangumi1.id != bangumi2.id

    def test_unique_constraint_allows_different_group(self, session):
        bangumi1 = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test Raw",
            season=1,
            group_name="TestGroup1",
        )
        session.add(bangumi1)
        session.commit()

        bangumi2 = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test Raw",
            season=1,
            group_name="TestGroup2",
        )
        session.add(bangumi2)
        session.commit()

        assert bangumi1.id != bangumi2.id

    def test_bangumi_defaults(self, session):
        bangumi = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test Raw",
        )
        session.add(bangumi)
        session.commit()
        session.refresh(bangumi)

        assert bangumi.season == 1
        assert bangumi.group_name == "Unknown"
        assert bangumi.eps_collect is False
        assert bangumi.offset == 0
        assert bangumi.filter == "720,\\d+-\\d+"
        assert bangumi.rss_link == ""
        assert bangumi.added is False
        assert bangumi.deleted is False
        assert bangumi.pending_review is False


class TestTorrent:
    def test_torrent_state_enum_has_all_states(self):
        assert TorrentState.PENDING == "pending"
        assert TorrentState.QUEUED == "queued"
        assert TorrentState.DOWNLOADING == "downloading"
        assert TorrentState.COMPLETED == "completed"
        assert TorrentState.RENAMING == "renaming"
        assert TorrentState.RENAMED == "renamed"
        assert TorrentState.ERROR == "error"
        assert TorrentState.STALE == "stale"
        assert TorrentState.MISSING == "missing"

    def test_unique_constraint_hash_bangumi_id_rejects_duplicate(self, session):
        bangumi = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test Raw",
            season=1,
            group_name="TestGroup",
        )
        session.add(bangumi)
        session.commit()

        torrent1 = Torrent(
            name="Test Torrent",
            url="https://example.com/torrent1",
            hash="abc123",
            bangumi_id=bangumi.id,
        )
        session.add(torrent1)
        session.commit()

        torrent2 = Torrent(
            name="Test Torrent 2",
            url="https://example.com/torrent2",
            hash="abc123",
            bangumi_id=bangumi.id,
        )
        session.add(torrent2)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_unique_constraint_allows_same_hash_different_bangumi(self, session):
        bangumi1 = Bangumi(
            official_title="Test Bangumi 1",
            title_raw="Test Raw 1",
            season=1,
            group_name="TestGroup1",
        )
        bangumi2 = Bangumi(
            official_title="Test Bangumi 2",
            title_raw="Test Raw 2",
            season=1,
            group_name="TestGroup2",
        )
        session.add_all([bangumi1, bangumi2])
        session.commit()

        torrent1 = Torrent(
            name="Test Torrent 1",
            url="https://example.com/torrent1",
            hash="abc123",
            bangumi_id=bangumi1.id,
        )
        torrent2 = Torrent(
            name="Test Torrent 2",
            url="https://example.com/torrent2",
            hash="abc123",
            bangumi_id=bangumi2.id,
        )
        session.add_all([torrent1, torrent2])
        session.commit()

        assert torrent1.id != torrent2.id
        assert torrent1.hash == torrent2.hash

    def test_unique_constraint_allows_null_hash_pairs(self, session):
        bangumi = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test Raw",
            season=1,
            group_name="TestGroup",
        )
        session.add(bangumi)
        session.commit()

        torrent1 = Torrent(
            name="Test Torrent 1",
            url="https://example.com/torrent1",
            hash=None,
            bangumi_id=bangumi.id,
        )
        torrent2 = Torrent(
            name="Test Torrent 2",
            url="https://example.com/torrent2",
            hash=None,
            bangumi_id=bangumi.id,
        )
        session.add_all([torrent1, torrent2])
        session.commit()

        assert torrent1.id != torrent2.id
        assert torrent1.hash is None
        assert torrent2.hash is None

    def test_torrent_defaults(self, session):
        torrent = Torrent(
            name="Test Torrent",
        )
        session.add(torrent)
        session.commit()
        session.refresh(torrent)

        assert torrent.name == "Test Torrent"
        assert torrent.url == "https://example.com/torrent"
        assert torrent.state == TorrentState.PENDING
        assert torrent.downloaded is False


class TestRSSItem:
    def test_rss_item_defaults(self, session):
        rss = RSSItem(url="https://mikanani.me/RSS/MyBangumi")
        session.add(rss)
        session.commit()
        session.refresh(rss)

        assert rss.url == "https://mikanani.me/RSS/MyBangumi"
        assert rss.enabled is True
        assert rss.aggregate is False
        assert rss.parser == "mikan"


class TestUser:
    def test_user_unique_username(self, session):
        user1 = User(username="testuser", password="hashed_password")
        session.add(user1)
        session.commit()

        user2 = User(username="testuser", password="another_password")
        session.add(user2)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_user_allows_different_usernames(self, session):
        user1 = User(username="testuser1", password="hashed_password")
        user2 = User(username="testuser2", password="hashed_password")
        session.add_all([user1, user2])
        session.commit()

        assert user1.id != user2.id
