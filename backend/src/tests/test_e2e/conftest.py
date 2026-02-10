"""Shared E2E test fixtures for Auto_Bangumi backend.

Mock strategy: Only mock the network boundary (RequestContent) and downloader.
Everything else runs real: DB, auth, scheduler, repos, services, parsers.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import create_app
from module.database.engine import engine as _async_engine, sync_engine as _sync_engine, DB_PATH as _DB_PATH

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

# ---------------------------------------------------------------------------
# RSS fixture URLs (used for URL-based routing)
# ---------------------------------------------------------------------------
WILD_BOSS_RSS_URL = "https://mikanani.me/RSS/Bangumi?bangumiId=3738&subgroupid=583"
AGGREGATE_RSS_URL = "http://mikanani.me/RSS/MyBangumi?token=FAKE_TOKEN_FOR_TESTING_ONLY"
DRAGON_MAID_RSS_URL = "http://mikanani.me/RSS/Bangumi?bangumiId=3808&subgroupid=575"

WILD_BOSS_HOMEPAGE_PATTERN = "mikanani.me/Home/Episode/a1b2c3d4"
GENERIC_HOMEPAGE_PATTERN = "mikanani.me/Home/Episode/"


# ---------------------------------------------------------------------------
# MockRequestContent - routes URLs to fixture data
# ---------------------------------------------------------------------------
class MockRequestContent:
    """Mock network boundary that returns fixture data based on URL patterns."""

    def __init__(self):
        self._load_fixtures()

    def _load_fixtures(self):
        self._wild_boss_xml = (FIXTURES_DIR / "non_aggregate_rss_wild_boss.xml").read_text()
        self._aggregate_xml = (FIXTURES_DIR / "aggregate_rss.xml").read_text()
        self._dragon_maid_xml = (FIXTURES_DIR / "non_aggregate_rss1.xml").read_text()
        self._wild_boss_html = (FIXTURES_DIR / "episode_page_wild_boss.html").read_text()
        self._generic_html = (FIXTURES_DIR / "episode_page_generic.html").read_text()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def get_xml(self, url: str, retry: int = 3) -> ET.Element | None:
        xml_str = self._resolve_xml(url)
        if xml_str:
            return ET.fromstring(xml_str)
        return None

    def _resolve_xml(self, url: str) -> str | None:
        if "bangumiId=3738" in url:
            return self._wild_boss_xml
        if "bangumiId=3808" in url:
            return self._dragon_maid_xml
        if "MyBangumi" in url or "token=" in url:
            return self._aggregate_xml
        # Default: try aggregate for unknown URLs
        return self._aggregate_xml

    def get_html(self, url: str) -> str:
        if "a1b2c3d4" in url:
            return self._wild_boss_html
        return self._generic_html

    def get_content(self, url: str) -> bytes:
        # Fake image bytes (PNG header)
        return b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'

    def get_torrents(self, _url: str, _filter: str = None, limit: int = None, retry: int = 3):
        """Delegate to real get_torrents logic but with our fixture XML."""
        from module.conf import settings
        from module.models import Torrent
        from module.network.site import rss_parser

        soup = self.get_xml(_url, retry)
        if soup is not None:
            torrent_titles, torrent_urls, torrent_homepage = rss_parser(soup)
            torrents = []

            # Handle filter
            if _filter is None:
                actual_filter = "|".join(settings.rss_parser.filter)
            elif _filter == "":
                actual_filter = None
            else:
                actual_filter = _filter.replace(",", "|")

            for _title, torrent_url, homepage in zip(
                torrent_titles, torrent_urls, torrent_homepage
            ):
                if actual_filter is None or re.search(actual_filter, _title, re.IGNORECASE) is None:
                    _hash = None
                    if "Download/" in torrent_url:
                        match = re.search(r"Download/\d+/([A-Fa-f0-9]{40})\.torrent", torrent_url)
                        if match:
                            _hash = match.group(1).lower()
                    elif "magnet:?" in torrent_url:
                        match = re.search(r"btih:([A-Fa-f0-9]{40})", torrent_url)
                        if match:
                            _hash = match.group(1).lower()
                    torrents.append(
                        Torrent(name=_title, url=torrent_url, homepage=homepage, hash=_hash)
                    )
                if isinstance(limit, int) and len(torrents) >= limit:
                    break
            return torrents
        return []

    def get_torrents_with_filter(
        self, _url: str, _filter: str = None, title_raw: str = None, retry: int = 3
    ) -> list[dict]:
        """Delegate to real get_torrents_with_filter logic with fixture data."""
        from module.conf import settings
        from module.network.site import rss_parser

        soup = self.get_xml(_url, retry)
        if soup is not None:
            torrent_titles, torrent_urls, torrent_homepage = rss_parser(soup)
            torrents = []

            if _filter is None:
                actual_filter = "|".join(settings.rss_parser.filter)
            elif _filter == "":
                actual_filter = None
            else:
                actual_filter = _filter.replace(",", "|")

            raw_parser = None
            BangumiParsingError = None
            if title_raw:
                from module.models.bangumi import BangumiParsingError
                from module.domain.parser.title_parser import TitleParser
                raw_parser = TitleParser()

            for _title, torrent_url, homepage in zip(
                torrent_titles, torrent_urls, torrent_homepage
            ):
                if title_raw and raw_parser:
                    try:
                        parsed = raw_parser.raw_parser(_title)
                        if not parsed:
                            continue
                        if title_raw not in parsed.title_raw and parsed.title_raw not in title_raw:
                            continue
                    except BangumiParsingError:
                        continue

                filtered = False
                if actual_filter and re.search(actual_filter, _title, re.IGNORECASE):
                    filtered = True

                torrents.append({
                    "name": _title,
                    "url": torrent_url,
                    "homepage": homepage,
                    "filter": filtered,
                })
            return torrents
        return []

    def get_rss_title(self, _url: str) -> str | None:
        soup = self.get_xml(_url)
        if soup is not None:
            title_elem = soup.find("./channel/title")
            if title_elem is not None:
                title = title_elem.text
                if title and title.startswith("Mikan Project - "):
                    title = title[len("Mikan Project - "):]
                return title
        return None

    def get_url(self, _url: str, retry: int = 3):
        """Return a mock response object for get_url calls."""
        mock_resp = MagicMock()
        xml_str = self._resolve_xml(_url)
        if xml_str:
            mock_resp.text = xml_str
            mock_resp.content = xml_str.encode()
        else:
            mock_resp.text = self._generic_html
            mock_resp.content = self._generic_html.encode()
        mock_resp.status_code = 200
        return mock_resp

    def check_connection(self, _url: str) -> bool:
        return True

    def check_url(self, _url: str) -> bool:
        return True


# ---------------------------------------------------------------------------
# Mock downloader fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_downloader():
    """Create a fully-mocked DownloaderProtocol."""
    dl = AsyncMock()
    dl.auth.return_value = True
    dl.check_host.return_value = True
    dl.add_torrents.return_value = True
    dl.torrents_info.return_value = []
    dl.torrents_rename_file.return_value = True
    dl.torrents_delete.return_value = True
    dl.move_torrent.return_value = True
    dl.get_torrent_path.return_value = None
    return dl


# ---------------------------------------------------------------------------
# Mock RequestContent fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def fixture_request_content():
    """Create MockRequestContent instance."""
    return MockRequestContent()


def _fake_save_image(img_bytes, suffix):
    """Skip real file I/O, return a fake poster path."""
    return f"data/posters/fake_poster.{suffix}"


# ---------------------------------------------------------------------------
# DB isolation — dispose engine + delete DB file before each test
# ---------------------------------------------------------------------------
def _reset_database():
    """Dispose engine connections and remove the DB file for test isolation."""
    import gc

    # Force garbage collection to clean up any lingering connections
    gc.collect()

    # Dispose the underlying sync engines to drop all pooled connections.
    # AsyncEngine wraps a sync engine, so disposing it synchronously is safe here.
    _async_engine.sync_engine.dispose()
    _sync_engine.dispose()

    # Remove the DB file so each test starts with a fresh database
    if _DB_PATH.exists():
        _DB_PATH.unlink()


# ---------------------------------------------------------------------------
# E2E client fixture — full app with mocked network boundary + downloader
# ---------------------------------------------------------------------------
@pytest.fixture
def e2e_client(mock_downloader, fixture_request_content):
    """Full-app TestClient with mocked network and downloader.

    Yields (client, mock_downloader) tuple.
    Each test gets a fresh database (file deleted + engine disposed before startup).
    """
    _reset_database()

    # Build a mock class that returns our fixture instance when called.
    # This ensures both `RequestContent()` and `with RequestContent() as req:`
    # work correctly in all modules.
    mock_rc_class = MagicMock(return_value=fixture_request_content)

    async def _safe_stop(self):
        """Stop scheduler without triggering cancel-scope hang."""
        if not self._started or self._scheduler is None:
            return
        self._started = False
        self._scheduler = None
        self._exit_stack = None

    patches = [
        patch("module.services.downloader.qbittorrent.Client"),
        patch("module.services.downloader.factory.create_downloader", return_value=mock_downloader),
        # Patch RequestContent everywhere it's imported so all modules use the mock
        patch("module.network.request_contents.RequestContent", mock_rc_class),
        patch("module.network.RequestContent", mock_rc_class),
        patch("module.services.rss_engine.RequestContent", mock_rc_class),
        patch("module.rss.analyser.RequestContent", mock_rc_class),
        patch("module.domain.parser.analyser.mikan_parser.RequestContent", mock_rc_class),
        patch("module.domain.parser.analyser.mikan_parser.save_image", side_effect=_fake_save_image),
        patch("module.utils.save_image", side_effect=_fake_save_image),
        # Patch scheduler stop to prevent APScheduler cancel-scope hang
        patch("module.scheduler.engine.AsyncScheduler.stop", _safe_stop),
    ]

    for p in patches:
        p.start()

    try:
        app = create_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, mock_downloader
    finally:
        for p in reversed(patches):
            p.stop()


# ---------------------------------------------------------------------------
# Authenticated client fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def authed_client(e2e_client):
    """Logs in as admin/adminadmin, returns (client, mock_downloader, token).

    Cookie is already set on the client.
    """
    client, mock_dl = e2e_client

    resp = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "adminadmin"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    client.cookies.set("token", token)

    return client, mock_dl, token


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------
def add_non_aggregate_rss(client, name="Wild Boss", url=WILD_BOSS_RSS_URL):
    """Add a non-aggregate RSS via the API. Returns the response."""
    return client.post(
        "/api/v1/rss/add",
        json={
            "url": url,
            "name": name,
            "aggregate": False,
            "parser": "mikan",
            "enabled": True,
        },
    )


def add_aggregate_rss(client, name="My Bangumi", url=AGGREGATE_RSS_URL):
    """Add an aggregate RSS via the API. Returns the response."""
    return client.post(
        "/api/v1/rss/add",
        json={
            "url": url,
            "name": name,
            "aggregate": True,
            "parser": "mikan",
            "enabled": True,
        },
    )


def get_all_rss(client):
    """GET all RSS feeds."""
    return client.get("/api/v1/rss")


def get_all_bangumi(client):
    """GET all bangumi."""
    return client.get("/api/v1/bangumi/get/all")


def login(client, username="admin", password="adminadmin"):
    """Login and set cookie. Returns token."""
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    client.cookies.set("token", token)
    return token
