"""Shared test fixtures for parser tests.

This module provides common fixtures used across all parser test files.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from module.parser.analyser.bangumi_parser import BangumiParser

# --- Parser Fixtures ---


@pytest.fixture
def parser() -> BangumiParser:
    """Create a BangumiParser instance for tests.

    Returns a fresh instance for each test to ensure clean state.
    Scope is 'function' (default) for test isolation.
    """
    return BangumiParser()


# --- Test Data Fixtures ---


@pytest.fixture
def sample_torrent_names() -> dict[str, list[str]]:
    """Common sample torrent names organized by category.

    Returns a dictionary mapping category names to lists of sample torrent titles.
    """
    return {
        "simple": [
            "[Group] Title - 01 [1080p]",
            "[SubGroup] Anime Name - 12 [720P][HEVC]",
            "[Fansub] Show Title - 05 [1080P][AVC AAC]",
        ],
        "chinese_groups": [
            "[喵萌奶茶屋] 动漫名称 - 01 [1080p][简日双语]",
            "[幻樱字幕组] 番剧标题 - 05 [BIG5_MP4][1920X1080]",
            "[织梦字幕组] 新番名 - 03 [1080P][AVC][简日双语]",
        ],
        "multi_group": [
            "[喵萌奶茶屋&LoliHouse] Title - 01 [1080p]",
            "[SweetSub&LoliHouse] Anime - 01 [WebRip 1080p HEVC-10bit AAC]",
            "[百冬练习组&LoliHouse] Show - 01 [WebRip 1080p HEVC-10bit AAC]",
        ],
        "fullwidth_brackets": [
            "【动漫国字幕组】★01月新番[标题][01][1080P][繁体][MP4]",
            "【幻樱字幕组】【4月新番】【动漫标题】【01】【GB_MP4】【1920X1080】",
            "【极影字幕社】★4月新番 动漫名 Title 第01话 GB 720P MP4",
        ],
        "with_season": [
            "[Group] Title S02 - 01 [1080p]",
            "[Group] Anime 第二季 - 05 [720P]",
            "[Group] Show Season 2 - 12 [1080p]",
        ],
        "with_slash_titles": [
            "[Group] 中文名 / English Name - 01 [1080p]",
            "[LoliHouse] 日文名 / Romaji / English - 01 [WebRip 1080p HEVC-10bit AAC]",
            "[ANi] Chinese / English Title - 03 [1080P][Baha][WEB-DL][AAC AVC][CHT][MP4]",
        ],
    }


@pytest.fixture
def sample_codec_strings() -> dict[str, list[str]]:
    """Sample codec strings for testing codec detection.

    Returns a dictionary mapping codec categories to lists of test strings.
    """
    return {
        "hevc": ["HEVC", "hevc", "H.265", "H265", "x265", "X265", "HEVC-10bit"],
        "avc": ["AVC", "avc", "H.264", "H264", "x264", "X264", "AVC-8bit"],
        "audio": ["AAC", "FLAC", "AC3", "DTS", "EAC3", "OPUS", "DTS-HD"],
    }


@pytest.fixture
def sample_resolution_strings() -> dict[str, list[tuple[str, str]]]:
    """Sample resolution strings for testing resolution extraction.

    Returns a dictionary mapping resolution categories to lists of
    (input_string, expected_resolution) tuples.
    """
    return {
        "standard": [
            ("1080p", "1080P"),
            ("1080P", "1080P"),
            ("720p", "720P"),
            ("720P", "720P"),
            ("2160p", "2160P"),
            ("480p", "480P"),
        ],
        "dimension": [
            ("1920x1080", "1080P"),
            ("1920X1080", "1080P"),
            ("1280x720", "720P"),
            ("1280X720", "720P"),
            ("3840x2160", "2160P"),
        ],
        "alias": [
            ("4K", "2160P"),
            ("4k", "2160P"),
            ("UHD", "2160P"),
            ("FHD", "1080P"),
            ("HD", "720P"),
        ],
    }


@pytest.fixture
def sample_subtitle_strings() -> dict[str, list[str]]:
    """Sample subtitle type strings for testing subtitle detection.

    Returns a dictionary mapping subtitle categories to lists of test strings.
    """
    return {
        "chs": ["简体", "简中", "CHS", "GB", "简体中文", "简日双语", "简繁内封字幕"],
        "cht": ["繁体", "繁中", "CHT", "BIG5", "繁體", "繁體中文"],
        "jp": ["日语", "JP", "日文", "日本語"],
        "en": ["英语", "EN", "ENG", "English"],
        "combined": ["CHS_JP", "GB_JP", "简繁日内封字幕", "简繁内封字幕"],
    }


@pytest.fixture
def sample_source_strings() -> dict[str, list[str]]:
    """Sample source type strings for testing source detection.

    Returns a dictionary mapping source categories to lists of test strings.
    """
    return {
        "web": ["WEB-DL", "WebRip", "WebDL", "WEBDL", "WEB"],
        "bluray": ["BDRip", "BluRay", "Blu-ray", "BD", "BDRemux"],
        "tv": ["HDTV", "TVRip", "HDTVRIP"],
        "dvd": ["DVDRip", "DVD", "DVDR"],
        "streaming": ["Baha", "CR", "B-Global", "ABEMA", "Bilibili", "AT-X"],
    }


@pytest.fixture
def edge_case_titles() -> dict[str, Any]:
    """Load edge case titles from JSON fixture file.

    Returns the parsed JSON data from edge_case_titles.json.
    """
    fixture_path = Path(__file__).parent / "fixtures" / "edge_case_titles.json"
    if fixture_path.exists():
        with open(fixture_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"test_cases": []}


@pytest.fixture
def sample_season_strings() -> dict[str, list[tuple[str, int]]]:
    """Sample season strings for testing season extraction.

    Returns a dictionary mapping season format categories to lists of
    (input_string, expected_season) tuples.
    """
    return {
        "s_format": [
            ("S01", 1),
            ("S02", 2),
            ("S2", 2),
            ("s01", 1),
            ("S10", 10),
        ],
        "season_format": [
            ("Season 1", 1),
            ("Season 2", 2),
            ("Season 10", 10),
            ("season 1", 1),
        ],
        "chinese_season": [
            ("第一季", 1),
            ("第二季", 2),
            ("第三季", 3),
        ],
        "ordinal": [
            ("1st Season", 1),
            ("2nd Season", 2),
            ("3rd Season", 3),
        ],
    }


# --- Path Fixtures ---


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory.

    Returns the Path to backend/src/test/fixtures/.
    """
    return Path(__file__).parent / "fixtures"


# --- Database Fixtures ---


@pytest.fixture
def in_memory_engine():
    """Create a SQLite in-memory engine with StaticPool.

    Returns an engine configured for testing with a fresh in-memory
    database that persists for the duration of the test.
    """
    from sqlalchemy.pool import StaticPool
    from sqlmodel import create_engine

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine


@pytest.fixture
def test_database(in_memory_engine):
    """Provide a fresh Database instance using in_memory_engine.

    Creates all tables and returns a Database instance connected to
    the in-memory engine. The database is empty and ready for tests.
    """
    from module.database import Database

    db = Database(engine=in_memory_engine)
    db.create_table()
    yield db
    db.close()


@pytest.fixture
def seeded_database(in_memory_engine):
    """Provide a Database pre-populated with sample test data.

    Pre-populates with:
    - RSSItem: id=1 (non-aggregate), id=2 (aggregate)
    - Bangumi: id=1 (linked to RSSItem id=1)
    - Torrent: id=1 (linked to Bangumi id=1)
    """
    from module.database import Database
    from module.models.bangumi import Bangumi
    from module.models.rss import RSSItem
    from module.models.torrent import Torrent

    db = Database(engine=in_memory_engine)
    db.create_table()

    # Add sample RSSItems
    rss1 = RSSItem(
        id=1,
        name="Test Non-Aggregate RSS",
        url="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
        aggregate=False,
        parser="mikan",
        enabled=True,
    )
    rss2 = RSSItem(
        id=2,
        name="Test Aggregate RSS",
        url="https://mikanani.me/RSS/MyBangumi?token=test123",
        aggregate=True,
        parser="mikan",
        enabled=True,
    )
    db.add(rss1)
    db.add(rss2)

    # Add sample Bangumi
    bangumi1 = Bangumi(
        id=1,
        rss_id=1,
        official_title="Test Anime",
        title_raw="[TestGroup] Test Anime",
        season=1,
        group_name="TestGroup",
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
        added=True,
    )
    db.add(bangumi1)

    # Add sample Torrent
    torrent1 = Torrent(
        id=1,
        bangumi_id=1,
        rss_id=1,
        name="[TestGroup] Test Anime - 01 [1080p].mkv",
        url="https://example.com/torrent/1.torrent",
        downloaded=True,
        hash="abc123def456",
    )
    db.add(torrent1)

    db.commit()
    yield db
    db.close()


# --- Mock Fixtures ---


@pytest.fixture
def mock_download_client():
    """Mock DownloadClient for unit tests.

    Provides a mock DownloadClient that:
    - Works as a context manager (__enter__/__exit__)
    - Returns expected default values for common methods

    The mock patches 'module.downloader.download_client.DownloadClient'
    so it intercepts all uses of the class.
    """
    from unittest.mock import MagicMock, patch

    mock_client = MagicMock()
    mock_client.add_torrent.return_value = True
    mock_client.delete_torrent.return_value = True
    mock_client.get_torrent_info.return_value = []
    mock_client.get_existing_hashes.return_value = set()
    mock_client.auth.return_value = True

    # Configure as context manager
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    with patch(
        "module.downloader.download_client.DownloadClient",
        return_value=mock_client,
    ) as mock_class:
        # Also make the class itself callable and return the mock
        mock_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_request_content():
    """Mock RequestContent for unit tests.

    Provides a mock RequestContent that:
    - Works as a context manager (__enter__/__exit__)
    - Returns expected default values for common methods

    The mock patches 'module.network.request_contents.RequestContent'
    so it intercepts all uses of the class.
    """
    from unittest.mock import MagicMock, patch

    mock_req = MagicMock()
    mock_req.get_torrents.return_value = []
    mock_req.get_rss_title.return_value = "Test Feed"

    # Configure as context manager
    mock_req.__enter__.return_value = mock_req
    mock_req.__exit__.return_value = None

    with patch(
        "module.network.request_contents.RequestContent",
        return_value=mock_req,
    ) as mock_class:
        # Also make the class itself callable and return the mock
        mock_class.return_value = mock_req
        yield mock_req


@pytest.fixture
def mock_mikan_parser():
    """Mock TitleParser.mikan_parser_with_rss for unit tests.

    Provides a mock that returns a MikanParserResult with default values.
    This patches the method directly on the TitleParser class.
    """
    from unittest.mock import MagicMock, patch

    from module.parser.analyser import MikanParserResult

    mock_result = MikanParserResult(
        poster_link="https://example.com/poster.jpg",
        official_title="Test Anime",
        season_rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=12345",
    )

    with patch(
        "module.parser.title_parser.TitleParser.mikan_parser_with_rss",
        return_value=mock_result,
    ) as mock_parser:
        yield mock_parser


@pytest.fixture
def mock_tmdb_parser():
    """Mock TitleParser.tmdb_parser for unit tests.

    Provides a mock that returns default TMDB parsed values:
    (title, season, year, poster_link).
    This patches the method directly on the TitleParser class.
    """
    from unittest.mock import patch

    # tmdb_parser returns (title, season, year, poster_link)
    mock_return = (
        "Test Anime Official",
        1,
        "2024",
        "https://example.com/tmdb_poster.jpg",
    )

    with patch(
        "module.parser.title_parser.TitleParser.tmdb_parser",
        return_value=mock_return,
    ) as mock_parser:
        yield mock_parser


# --- FastAPI TestClient Fixtures ---


@pytest.fixture
def test_client(in_memory_engine):
    """Create a FastAPI TestClient with in-memory database.

    This fixture:
    - Patches module.database.engine to use in-memory SQLite
    - Patches module.database.combine.e (the engine alias) to use in-memory SQLite
    - Patches DownloadClient to use mock (no real qBittorrent)
    - Patches RequestContent to use mock (no real HTTP requests)
    - Creates all database tables
    - Returns TestClient for making API requests

    Database state persists within a single test but resets between tests.
    """
    from unittest.mock import MagicMock, patch

    from fastapi.testclient import TestClient
    from sqlmodel import SQLModel

    # Import all models to ensure they are registered in SQLModel metadata
    from module.models.bangumi import Bangumi  # noqa: F401
    from module.models.rss import RSSItem  # noqa: F401
    from module.models.torrent import Torrent  # noqa: F401

    # Create all tables in the in-memory database
    # Use bind=in_memory_engine to ensure tables are created on THIS engine
    # This is necessary when running multiple tests because metadata might
    # have been bound to a different engine in previous tests
    SQLModel.metadata.create_all(bind=in_memory_engine)

    # Create mock for DownloadClient
    mock_client = MagicMock()
    mock_client.add_torrent.return_value = True
    mock_client.delete_torrent.return_value = True
    mock_client.get_torrent_info.return_value = []
    mock_client.get_existing_hashes.return_value = set()
    mock_client.auth.return_value = True
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None

    # Create mock for RequestContent
    mock_req = MagicMock()
    mock_req.get_torrents.return_value = []
    mock_req.get_rss_title.return_value = "Test Feed"
    mock_req.__enter__.return_value = mock_req
    mock_req.__exit__.return_value = None

    # We need to patch the RSSEngine.__init__ default to use our in_memory_engine
    # since Python evaluates default arguments at definition time, not call time.
    # We also need to patch all places where engine and external services are used.
    # Same for TorrentManager and TorrentStatusManager which inherit from Database.

    from module.manager.torrent import TorrentManager
    from module.manager.torrent_status import TorrentStatusManager
    from module.rss.engine import RSSEngine

    original_rss_init = RSSEngine.__init__
    original_tm_init = TorrentManager.__init__
    original_tsm_init = TorrentStatusManager.__init__

    def patched_rss_init(self, _engine=None):
        # Force use of in_memory_engine if no engine specified
        return original_rss_init(self, _engine or in_memory_engine)

    def patched_tm_init(self, engine=None):
        # Force use of in_memory_engine if no engine specified
        return original_tm_init(self, engine or in_memory_engine)

    def patched_tsm_init(self, engine=None):
        # Force use of in_memory_engine if no engine specified
        return original_tsm_init(self, engine or in_memory_engine)

    # Patch all engine references and external dependencies
    with (
        # Patch engine at all import locations
        patch("module.database.engine", in_memory_engine),
        patch("module.database.combine.e", in_memory_engine),
        patch("module.rss.engine.engine", in_memory_engine),
        # Patch class __init__ methods to force use of in_memory_engine
        patch.object(RSSEngine, "__init__", patched_rss_init),
        patch.object(TorrentManager, "__init__", patched_tm_init),
        patch.object(TorrentStatusManager, "__init__", patched_tsm_init),
        # Patch DownloadClient at definition and common import locations
        patch(
            "module.downloader.download_client.DownloadClient",
            return_value=mock_client,
        ),
        patch(
            "module.downloader.DownloadClient",
            return_value=mock_client,
        ),
        patch(
            "module.api.rss.DownloadClient",
            return_value=mock_client,
        ),
        patch(
            "module.manager.torrent.DownloadClient",
            return_value=mock_client,
        ),
        patch(
            "module.manager.torrent_status.DownloadClient",
            return_value=mock_client,
        ),
        # Patch RequestContent at definition and common import locations
        patch(
            "module.network.request_contents.RequestContent",
            return_value=mock_req,
        ),
        patch(
            "module.network.RequestContent",
            return_value=mock_req,
        ),
    ):
        # Import and create app inside the patch context
        from main import create_app

        app = create_app()
        client = TestClient(app)
        yield client


@pytest.fixture
def authenticated_client(test_client):
    """Create an authenticated TestClient with Authorization header.

    This fixture builds on test_client and adds:
    - Authorization: Bearer test_token header to all requests

    Use this fixture for testing protected API endpoints.
    """
    # In DEV_VERSION mode, authentication is bypassed
    # But we still need to set a cookie for proper auth flow
    test_client.cookies.set("token", "test_token")
    yield test_client
