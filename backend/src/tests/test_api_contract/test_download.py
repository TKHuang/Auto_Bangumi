"""API contract tests for download endpoints (RSS analysis and collection)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from module.api.v1.rss import router as rss_router
from module.models import Bangumi, RSSItem, ResponseModel


@pytest.fixture
def app():
    """Create FastAPI app with rss router and auth bypass."""
    from module.api.middleware.auth import get_current_user
    
    app = FastAPI()
    app.include_router(rss_router, prefix="/api/v1")
    
    # Override auth dependency to bypass authentication
    async def mock_get_current_user():
        return "testuser"
    
    app.dependency_overrides[get_current_user] = mock_get_current_user
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_rss():
    """Create mock RSS item."""
    return RSSItem(
        id=1,
        name="Test RSS",
        url="https://example.com/rss.xml",
        aggregate=False,
        parser="mikan",
        enabled=True,
        last_update=None,
        last_status=None,
        last_error=None,
    )


@pytest.fixture
def mock_bangumi():
    """Create mock bangumi data."""
    return Bangumi(
        id=1,
        official_title="Test Bangumi",
        title_raw="[Group] Test Bangumi - 01 [1080p]",
        season=1,
        season_raw="S01",
        group_name="Group",
        dpi="1080p",
        source="WEB-DL",
        subtitle="CHT",
        filter="1080p,WEB-DL",
        rss_link="https://example.com/rss",
        poster_link="https://example.com/poster.jpg",
        year="2024",
        added=False,
        deleted=False,
        eps_collect=False,
        offset=0,
        rule_name="Test Bangumi",
        save_path="/downloads/Bangumi/Test Bangumi",
        rss_id=1,
    )


class TestAnalysis:
    """Test POST /rss/analysis endpoint."""

    @pytest.mark.asyncio
    async def test_analysis_success(self, client, mock_rss, mock_bangumi):
        """Test successful RSS analysis."""
        with patch("module.api.v1.rss.analyser") as mock_analyser:
            mock_analyser.link_to_data.return_value = mock_bangumi

            response = client.post(
                "/api/v1/rss/analysis",
                json={
                    "name": "Test RSS",
                    "url": "https://example.com/rss.xml",
                    "aggregate": False,
                    "parser": "mikan",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "official_title" in data
            assert data["official_title"] == "Test Bangumi"
            assert isinstance(data["filter"], str)
            assert isinstance(data["rss_link"], str)

    @pytest.mark.asyncio
    async def test_analysis_error(self, client, mock_rss):
        """Test RSS analysis with error response."""
        mock_error_response = ResponseModel(
            status=False,
            status_code=406,
            msg_en="Analysis failed.",
            msg_zh="解析失败。",
        )

        with patch("module.api.v1.rss.analyser") as mock_analyser:
            mock_analyser.link_to_data.return_value = mock_error_response

            response = client.post(
                "/api/v1/rss/analysis",
                json={
                    "name": "Test RSS",
                    "url": "https://example.com/rss.xml",
                    "aggregate": False,
                    "parser": "mikan",
                },
            )

            assert response.status_code == 406


class TestAnalysisTorrents:
    """Test POST /rss/analysis/torrents endpoint."""

    @pytest.mark.asyncio
    async def test_analysis_torrents_success(self, client, mock_rss):
        """Test successful torrent analysis."""
        mock_torrent_list = [
            {
                "name": "[Group] Test - 01 [1080p]",
                "url": "https://example.com/torrent1",
                "homepage": "https://example.com",
                "filter": True,
            },
            {
                "name": "[Group] Test - 02 [1080p]",
                "url": "https://example.com/torrent2",
                "homepage": "https://example.com",
                "filter": True,
            },
        ]

        with patch("module.api.v1.rss.analyser") as mock_analyser:
            mock_analyser.analyse_torrents.return_value = mock_torrent_list

            response = client.post(
                "/api/v1/rss/analysis/torrents",
                json={
                    "name": "Test RSS",
                    "url": "https://example.com/rss.xml",
                    "aggregate": False,
                    "parser": "mikan",
                },
                params={"_filter": "1080p"},
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]["name"] == "[Group] Test - 01 [1080p]"

    @pytest.mark.asyncio
    async def test_analysis_torrents_with_title_raw(self, client, mock_rss):
        """Test torrent analysis with title_raw filter."""
        mock_torrent_list = [
            {
                "name": "[Group] Specific Title - 01 [1080p]",
                "url": "https://example.com/torrent1",
                "homepage": "https://example.com",
                "filter": True,
            },
        ]

        with patch("module.api.v1.rss.analyser") as mock_analyser:
            mock_analyser.analyse_torrents.return_value = mock_torrent_list

            response = client.post(
                "/api/v1/rss/analysis/torrents",
                json={
                    "name": "Test RSS",
                    "url": "https://example.com/rss.xml",
                    "aggregate": True,
                    "parser": "mikan",
                },
                params={"_filter": "1080p", "title_raw": "Specific Title"},
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)


class TestCollection:
    """Test POST /rss/collect endpoint."""

    @pytest.mark.asyncio
    async def test_collection_success(self, client, mock_bangumi):
        """Test successful season collection."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Collection completed successfully.",
            msg_zh="收集完成。",
        )

        with patch("module.api.v1.rss.SeasonCollector") as mock_collector:
            mock_instance = MagicMock()
            mock_collector.return_value.__enter__.return_value = mock_instance
            mock_instance.collect_season.return_value = mock_response

            response = client.post(
                "/api/v1/rss/collect",
                json={
                    "official_title": "Test Bangumi",
                    "season": 1,
                    "filter": "1080p,WEB-DL",
                    "rss_link": "https://example.com/rss",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data

    @pytest.mark.asyncio
    async def test_collection_error(self, client):
        """Test collection with error."""
        mock_response = ResponseModel(
            status=False,
            status_code=406,
            msg_en="Collection failed.",
            msg_zh="收集失败。",
        )

        with patch("module.api.v1.rss.SeasonCollector") as mock_collector:
            mock_instance = MagicMock()
            mock_collector.return_value.__enter__.return_value = mock_instance
            mock_instance.collect_season.return_value = mock_response

            response = client.post(
                "/api/v1/rss/collect",
                json={
                    "official_title": "Test Bangumi",
                    "season": 1,
                    "filter": "1080p",
                    "rss_link": "https://example.com/rss",
                },
            )

            assert response.status_code == 406


class TestSubscribe:
    """Test POST /rss/subscribe endpoint."""

    @pytest.mark.asyncio
    async def test_subscribe_success(self, client, mock_bangumi, mock_rss):
        """Test successful subscription."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Subscribe successfully.",
            msg_zh="订阅成功。",
        )

        with patch("module.api.v1.rss.SeasonCollector") as mock_collector:
            mock_instance = MagicMock()
            mock_collector.return_value.__enter__.return_value = mock_instance
            mock_instance.subscribe_season.return_value = mock_response

            response = client.post(
                "/api/v1/rss/subscribe",
                json={
                    "data": {
                        "official_title": "Test Bangumi",
                        "season": 1,
                        "filter": "1080p",
                        "rss_link": "https://example.com/rss",
                    },
                    "rss": {
                        "id": 1,
                        "name": "Test RSS",
                        "url": "https://example.com/rss.xml",
                        "aggregate": False,
                        "parser": "mikan",
                    },
                },
                params={"file": False},
            )

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data

    @pytest.mark.asyncio
    async def test_subscribe_with_delete_files(self, client):
        """Test subscription with file deletion."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Subscribe successfully.",
            msg_zh="订阅成功。",
        )

        with patch("module.api.v1.rss.SeasonCollector") as mock_collector:
            mock_instance = MagicMock()
            mock_collector.return_value.__enter__.return_value = mock_instance
            mock_instance.subscribe_season.return_value = mock_response

            response = client.post(
                "/api/v1/rss/subscribe",
                json={
                    "data": {
                        "official_title": "Test Bangumi",
                        "season": 1,
                        "filter": "1080p",
                        "rss_link": "https://example.com/rss",
                    },
                    "rss": {
                        "id": 1,
                        "name": "Test RSS",
                        "url": "https://example.com/rss.xml",
                        "aggregate": False,
                        "parser": "mikan",
                    },
                },
                params={"file": True},
            )

            assert response.status_code == 200
            mock_instance.subscribe_season.assert_called_once()
            args, kwargs = mock_instance.subscribe_season.call_args
            assert kwargs.get("delete_files") is True

    @pytest.mark.asyncio
    async def test_subscribe_duplicate_error(self, client):
        """Test subscription when already subscribed."""
        with patch("module.api.v1.rss.SeasonCollector") as mock_collector:
            mock_instance = MagicMock()
            mock_collector.return_value.__enter__.return_value = mock_instance
            mock_instance.subscribe_season.side_effect = ValueError(
                "Already subscribed from another RSS"
            )

            response = client.post(
                "/api/v1/rss/subscribe",
                json={
                    "data": {
                        "official_title": "Test Bangumi",
                        "season": 1,
                        "filter": "1080p",
                        "rss_link": "https://example.com/rss",
                    },
                    "rss": {
                        "id": 1,
                        "name": "Test RSS",
                        "url": "https://example.com/rss.xml",
                        "aggregate": False,
                        "parser": "mikan",
                    },
                },
            )

            assert response.status_code == 409
            data = response.json()
            assert "msg_en" in data


class TestSubscribeBatch:
    """Test POST /rss/subscribe/batch endpoint."""

    @pytest.mark.asyncio
    async def test_subscribe_batch_success(self, client):
        """Test successful batch subscription."""
        mock_response = ResponseModel(
            status=True,
            status_code=200,
            msg_en="Batch subscribe successfully.",
            msg_zh="批量订阅成功。",
        )

        with patch("module.api.v1.rss.SeasonCollector") as mock_collector:
            mock_instance = MagicMock()
            mock_collector.return_value.__enter__.return_value = mock_instance
            mock_instance.subscribe_batch.return_value = mock_response

            response = client.post(
                "/api/v1/rss/subscribe/batch",
                json={
                    "bangumi_list": [
                        {
                            "official_title": "Bangumi 1",
                            "season": 1,
                            "filter": "1080p",
                            "rss_link": "https://example.com/rss1",
                        },
                        {
                            "official_title": "Bangumi 2",
                            "season": 2,
                            "filter": "720p",
                            "rss_link": "https://example.com/rss2",
                        },
                    ],
                    "rss": {
                        "id": 1,
                        "name": "Test RSS",
                        "url": "https://example.com/rss.xml",
                        "aggregate": True,
                        "parser": "mikan",
                    },
                },
                params={"file": False},
            )

            assert response.status_code == 200
            data = response.json()
            assert "msg_en" in data

    @pytest.mark.asyncio
    async def test_subscribe_batch_error(self, client):
        """Test batch subscription with error."""
        with patch("module.api.v1.rss.SeasonCollector") as mock_collector:
            mock_instance = MagicMock()
            mock_collector.return_value.__enter__.return_value = mock_instance
            mock_instance.subscribe_batch.side_effect = Exception("Database error")

            response = client.post(
                "/api/v1/rss/subscribe/batch",
                json={
                    "bangumi_list": [
                        {
                            "official_title": "Bangumi 1",
                            "season": 1,
                            "filter": "1080p",
                            "rss_link": "https://example.com/rss1",
                        },
                    ],
                    "rss": {
                        "id": 1,
                        "name": "Test RSS",
                        "url": "https://example.com/rss.xml",
                        "aggregate": True,
                        "parser": "mikan",
                    },
                },
            )

            assert response.status_code == 500
            data = response.json()
            assert "msg_en" in data
            assert "failed" in data["msg_en"].lower()
