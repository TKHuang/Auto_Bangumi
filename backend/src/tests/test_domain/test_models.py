"""Tests for domain models (post-0008: Bangumi uses series_id, legacy cols dropped)."""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, select, event
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
from module.domain.models.series import Series


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")
    # Enable FK enforcement for SQLite
    @event.listens_for(engine, "connect")
    def set_fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


def _make_series(session: Session, suffix: str = "") -> Series:
    s = Series(
        canonical_title=f"Test Bangumi{suffix}",
        normalized_title=f"test_bangumi{suffix}",
        season=1,
        root_path=f"/downloads/Test{suffix}",
    )
    session.add(s)
    session.flush()
    return s


class TestBase:
    def test_all_models_create_tables_successfully(self, engine):
        tables = Base.metadata.tables.keys()
        assert "bangumi" in tables
        assert "torrent" in tables
        assert "rssitem" in tables
        assert "user" in tables


class TestTimestampMixin:
    def test_created_at_auto_set(self, session):
        s = _make_series(session)
        bangumi = Bangumi(series_id=s.id, group_name="TestGroup")
        session.add(bangumi)
        session.commit()
        session.refresh(bangumi)

        assert bangumi.created_at is not None
        assert isinstance(bangumi.created_at, datetime)

    def test_updated_at_auto_set(self, session):
        s = _make_series(session)
        bangumi = Bangumi(series_id=s.id, group_name="TestGroup")
        session.add(bangumi)
        session.commit()
        session.refresh(bangumi)

        assert bangumi.updated_at is not None
        assert isinstance(bangumi.updated_at, datetime)

    def test_updated_at_changes_on_update(self, session):
        s = _make_series(session)
        bangumi = Bangumi(series_id=s.id, group_name="TestGroup")
        session.add(bangumi)
        session.commit()
        session.refresh(bangumi)

        original_updated_at = bangumi.updated_at

        bangumi.group_name = "UpdatedGroup"
        session.commit()
        session.refresh(bangumi)

        assert bangumi.updated_at > original_updated_at


class TestVersionMixin:
    def test_version_starts_at_one(self, session):
        s = _make_series(session)
        bangumi = Bangumi(series_id=s.id, group_name="TestGroup")
        session.add(bangumi)
        session.commit()
        session.refresh(bangumi)

        assert bangumi.version == 1

    def test_version_increments_on_update(self, session):
        s = _make_series(session)
        bangumi = Bangumi(series_id=s.id, group_name="TestGroup")
        session.add(bangumi)
        session.commit()
        session.refresh(bangumi)

        assert bangumi.version == 1

        bangumi.group_name = "UpdatedGroup"
        session.commit()
        session.refresh(bangumi)

        assert bangumi.version == 2

        bangumi.eps_collect = True
        session.commit()
        session.refresh(bangumi)

        assert bangumi.version == 3


class TestBangumi:
    def test_bangumi_partial_unique_blocks_dup_subgroup(self, session):
        """Two active bangumi with same series_id + mikan_subgroup_id must be rejected."""
        s = _make_series(session)
        b1 = Bangumi(series_id=s.id, group_name="G1", mikan_subgroup_id=7, deleted=False)
        session.add(b1)
        session.commit()

        b2 = Bangumi(series_id=s.id, group_name="G2", mikan_subgroup_id=7, deleted=False)
        session.add(b2)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_bangumi_partial_unique_allows_deleted_duplicate(self, session):
        """Deleted rows do NOT occupy the unique slot."""
        s = _make_series(session)
        b1 = Bangumi(series_id=s.id, group_name="G1", mikan_subgroup_id=7, deleted=True)
        session.add(b1)
        session.commit()

        b2 = Bangumi(series_id=s.id, group_name="G2", mikan_subgroup_id=7, deleted=False)
        session.add(b2)
        session.commit()

        assert b1.id != b2.id

    def test_bangumi_defaults(self, session):
        s = _make_series(session)
        bangumi = Bangumi(series_id=s.id)
        session.add(bangumi)
        session.commit()
        session.refresh(bangumi)

        assert bangumi.group_name == "Unknown"
        assert bangumi.eps_collect is False
        assert bangumi.offset == 0
        assert bangumi.filter == "720,\\d+-\\d+"
        assert bangumi.rss_link == ""
        assert bangumi.added is False
        assert bangumi.deleted is False
        assert bangumi.pending_review is False
        assert bangumi.active is True

    def test_bangumi_property_shims_delegate_to_series(self, session):
        """@property accessors return series values when series is loaded."""
        s = Series(
            canonical_title="Shim Anime",
            normalized_title="shim_anime",
            season=2,
            year=2024,
            root_path="/downloads/Shim",
            poster_url="https://example.com/poster.jpg",
        )
        session.add(s)
        session.flush()

        b = Bangumi(series_id=s.id, group_name="G")
        session.add(b)
        session.commit()

        # Load with series relationship
        loaded = session.execute(select(Bangumi).where(Bangumi.id == b.id)).scalar_one()
        session.refresh(loaded, ["series"])

        assert loaded.official_title == "Shim Anime"
        assert loaded.season == 2
        assert loaded.year == 2024
        assert loaded.poster_link == "https://example.com/poster.jpg"
        # save_path = root_path / "Season {season}" (post-0008 shim behaviour)
        assert loaded.save_path == "/downloads/Shim/Season 2"

    def test_bangumi_save_path_prefers_path_override(self, session):
        s = _make_series(session)
        b = Bangumi(series_id=s.id, group_name="G", path_override="/custom/path")
        session.add(b)
        session.commit()
        session.refresh(b, ["series"])

        assert b.save_path == "/custom/path"


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
        s = _make_series(session)
        bangumi = Bangumi(series_id=s.id, group_name="TestGroup")
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
        s1 = _make_series(session, "1")
        s2 = _make_series(session, "2")
        bangumi1 = Bangumi(series_id=s1.id, group_name="G1", mikan_subgroup_id=1)
        bangumi2 = Bangumi(series_id=s2.id, group_name="G2", mikan_subgroup_id=2)
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
        s = _make_series(session)
        bangumi = Bangumi(series_id=s.id, group_name="TestGroup")
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
        torrent = Torrent(name="Test Torrent")
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
