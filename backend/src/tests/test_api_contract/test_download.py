"""API contract tests for download endpoints (RSS analysis and collection)."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from module.api.v1.rss import router as rss_router
from module.domain.value_objects import ResponseModel
from module.models import Bangumi


@pytest.fixture
def app():
    """Create FastAPI app with rss router and auth bypass."""
    from module.api.middleware.auth import get_current_user
    from module.database.engine import get_db_session

    app = FastAPI()
    app.include_router(rss_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: "testuser"

    async def mock_get_session():
        yield AsyncMock()

    app.dependency_overrides[get_db_session] = mock_get_session
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def mock_bangumi():
    return Bangumi(
        id=1, official_title="Test Bangumi",
        title_raw="[Group] Test Bangumi - 01 [1080p]",
        season=1, season_raw="S01", group_name="Group",
        dpi="1080p", source="WEB-DL", subtitle="CHT",
        filter="1080p,WEB-DL", rss_link="https://example.com/rss",
        poster_link="https://example.com/poster.jpg", year="2024",
        added=False, deleted=False, eps_collect=False, offset=0,
        rule_name="Test Bangumi", save_path="/downloads/Bangumi/Test Bangumi",
        rss_id=1,
    )


class TestAnalysis:
    """Test POST /rss/analysis endpoint."""

    @pytest.mark.asyncio
    async def test_analysis_success(self, client, mock_bangumi):
        with patch("module.api.v1.rss.analyser") as mock_analyser:
            mock_analyser.link_to_data = AsyncMock(return_value=mock_bangumi)
            response = client.post("/api/v1/rss/analysis", json={
                "name": "Test RSS", "url": "https://example.com/rss.xml",
                "aggregate": False, "parser": "mikan",
            })
            assert response.status_code == 200
            data = response.json()
            assert data["official_title"] == "Test Bangumi"
            assert isinstance(data["filter"], str)
            assert isinstance(data["rss_link"], str)

    @pytest.mark.asyncio
    async def test_analysis_error(self, client):
        error_resp = ResponseModel(status=False, status_code=422, msg_en="Analysis failed.", msg_zh="解析失败。")
        with patch("module.api.v1.rss.analyser") as mock_analyser:
            mock_analyser.link_to_data = AsyncMock(return_value=error_resp)
            response = client.post("/api/v1/rss/analysis", json={
                "name": "Test RSS", "url": "https://example.com/rss.xml",
                "aggregate": False, "parser": "mikan",
            })
            assert response.status_code == 422


class TestAnalysisTorrents:
    """Test POST /rss/analysis/torrents endpoint."""

    @pytest.mark.asyncio
    async def test_analysis_torrents_success(self, client):
        mock_list = [
            {"name": "[Group] Test - 01 [1080p]", "url": "https://example.com/t1", "homepage": "https://example.com", "filter": True},
            {"name": "[Group] Test - 02 [1080p]", "url": "https://example.com/t2", "homepage": "https://example.com", "filter": True},
        ]
        with patch("module.api.v1.rss.analyser") as mock_analyser:
            mock_analyser.analyse_torrents = AsyncMock(return_value=mock_list)
            response = client.post("/api/v1/rss/analysis/torrents",
                json={"name": "Test RSS", "url": "https://example.com/rss.xml", "aggregate": False, "parser": "mikan"},
                params={"_filter": "1080p"},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["name"] == "[Group] Test - 01 [1080p]"

    @pytest.mark.asyncio
    async def test_analysis_torrents_with_title_raw(self, client):
        mock_list = [{"name": "[Group] Specific Title - 01 [1080p]", "url": "https://example.com/t1", "homepage": "https://example.com", "filter": True}]
        with patch("module.api.v1.rss.analyser") as mock_analyser:
            mock_analyser.analyse_torrents = AsyncMock(return_value=mock_list)
            response = client.post("/api/v1/rss/analysis/torrents",
                json={"name": "Test RSS", "url": "https://example.com/rss.xml", "aggregate": True, "parser": "mikan"},
                params={"_filter": "1080p", "title_raw": "Specific Title"},
            )
            assert response.status_code == 200
            assert isinstance(response.json(), list)


class TestCollection:
    """Test POST /rss/collect endpoint."""

    @pytest.mark.asyncio
    async def test_collection_success(self, client):
        resp = ResponseModel(status=True, status_code=200, msg_en="Collection completed successfully.", msg_zh="收集完成。")
        with patch("module.api.v1.rss.create_downloader") as mock_dl:
            mock_dl.return_value = AsyncMock()
            with patch("module.api.v1.rss.SeasonCollectorService") as mock_svc:
                mock_svc.collect_season = AsyncMock(return_value=resp)
                response = client.post("/api/v1/rss/collect", json={
                    "official_title": "Test Bangumi", "season": 1,
                    "filter": "1080p,WEB-DL", "rss_link": "https://example.com/rss",
                })
                assert response.status_code == 200
                assert "msg_en" in response.json()

    @pytest.mark.asyncio
    async def test_collection_error(self, client):
        resp = ResponseModel(status=False, status_code=404, msg_en="Collection failed.", msg_zh="收集失败。")
        with patch("module.api.v1.rss.create_downloader") as mock_dl:
            mock_dl.return_value = AsyncMock()
            with patch("module.api.v1.rss.SeasonCollectorService") as mock_svc:
                mock_svc.collect_season = AsyncMock(return_value=resp)
                response = client.post("/api/v1/rss/collect", json={
                    "official_title": "Test Bangumi", "season": 1,
                    "filter": "1080p", "rss_link": "https://example.com/rss",
                })
                assert response.status_code == 404


class TestSubscribe:
    """Test POST /rss/subscribe endpoint."""

    def _body(self, **kw):
        b = {
            "data": {"official_title": "Test Bangumi", "season": 1, "filter": "1080p", "rss_link": "https://example.com/rss"},
            "rss": {"id": 1, "name": "Test RSS", "url": "https://example.com/rss.xml", "aggregate": False, "parser": "mikan"},
        }
        b.update(kw)
        return b

    @pytest.mark.asyncio
    async def test_subscribe_success(self, client):
        resp = ResponseModel(status=True, status_code=200, msg_en="Subscribe successfully.", msg_zh="订阅成功。")
        with patch("module.api.v1.rss.create_downloader") as mock_dl:
            mock_dl.return_value = AsyncMock()
            with patch("module.api.v1.rss.SeasonCollectorService") as mock_svc:
                mock_svc.subscribe_season = AsyncMock(return_value=resp)
                response = client.post("/api/v1/rss/subscribe", json=self._body(), params={"file": False})
                assert response.status_code == 200
                assert "msg_en" in response.json()

    @pytest.mark.asyncio
    async def test_subscribe_with_delete_files(self, client):
        resp = ResponseModel(status=True, status_code=200, msg_en="Subscribe successfully.", msg_zh="订阅成功。")
        with patch("module.api.v1.rss.create_downloader") as mock_dl:
            mock_dl.return_value = AsyncMock()
            with patch("module.api.v1.rss.SeasonCollectorService") as mock_svc:
                mock_svc.subscribe_season = AsyncMock(return_value=resp)
                response = client.post("/api/v1/rss/subscribe", json=self._body(), params={"file": True})
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_subscribe_duplicate_error(self, client):
        with patch("module.api.v1.rss.create_downloader") as mock_dl:
            mock_dl.return_value = AsyncMock()
            with patch("module.api.v1.rss.SeasonCollectorService") as mock_svc:
                mock_svc.subscribe_season = AsyncMock(side_effect=ValueError("Already subscribed from another RSS"))
                response = client.post("/api/v1/rss/subscribe", json=self._body())
                assert response.status_code == 409
                assert "msg_en" in response.json()

    @pytest.mark.asyncio
    async def test_subscribe_forwards_manual_include_and_exclude_hashes(self, client):
        resp = ResponseModel(status=True, status_code=200, msg_en="Subscribe successfully.", msg_zh="订阅成功。")
        with patch("module.api.v1.rss.create_downloader") as mock_dl:
            mock_dl.return_value = AsyncMock()
            with patch("module.api.v1.rss.SeasonCollectorService") as mock_svc:
                mock_svc.subscribe_season = AsyncMock(return_value=resp)
                response = client.post(
                    "/api/v1/rss/subscribe",
                    json=self._body(
                        included_hashes=["keephash"],
                        excluded_hashes=["drophash"],
                    ),
                )
                assert response.status_code == 200
                _, kwargs = mock_svc.subscribe_season.await_args
                assert kwargs["included_hashes"] == ["keephash"]
                assert kwargs["excluded_hashes"] == ["drophash"]


class TestSubscribeBatch:
    """Test POST /rss/subscribe/batch endpoint."""

    def _body(self):
        return {
            "bangumi_list": [
                {"official_title": "Bangumi 1", "season": 1, "filter": "1080p", "rss_link": "https://example.com/rss1"},
                {"official_title": "Bangumi 2", "season": 2, "filter": "720p", "rss_link": "https://example.com/rss2"},
            ],
            "rss": {"id": 1, "name": "Test RSS", "url": "https://example.com/rss.xml", "aggregate": True, "parser": "mikan"},
        }

    @pytest.mark.asyncio
    async def test_subscribe_batch_success(self, client):
        resp = ResponseModel(status=True, status_code=200, msg_en="Batch subscribe successfully.", msg_zh="批量订阅成功。")
        with patch("module.api.v1.rss.create_downloader") as mock_dl:
            mock_dl.return_value = AsyncMock()
            with patch("module.api.v1.rss.SeasonCollectorService") as mock_svc:
                mock_svc.subscribe_batch = AsyncMock(return_value=resp)
                response = client.post("/api/v1/rss/subscribe/batch", json=self._body(), params={"file": False})
                assert response.status_code == 200
                assert "msg_en" in response.json()

    @pytest.mark.asyncio
    async def test_subscribe_batch_error(self, client):
        with patch("module.api.v1.rss.create_downloader") as mock_dl:
            mock_dl.return_value = AsyncMock()
            with patch("module.api.v1.rss.SeasonCollectorService") as mock_svc:
                mock_svc.subscribe_batch = AsyncMock(side_effect=Exception("Database error"))
                body = self._body()
                body["bangumi_list"] = body["bangumi_list"][:1]
                response = client.post("/api/v1/rss/subscribe/batch", json=body)
                assert response.status_code == 500
                assert "failed" in response.json()["msg_en"].lower()

    @pytest.mark.asyncio
    async def test_subscribe_batch_forwards_torrent_selections(self, client):
        resp = ResponseModel(status=True, status_code=200, msg_en="Batch subscribe successfully.", msg_zh="批量订阅成功。")
        with patch("module.api.v1.rss.create_downloader") as mock_dl:
            mock_dl.return_value = AsyncMock()
            with patch("module.api.v1.rss.SeasonCollectorService") as mock_svc:
                mock_svc.subscribe_batch = AsyncMock(return_value=resp)
                body = self._body()
                body["torrent_selections"] = [
                    {"included_hashes": ["keep1"], "excluded_hashes": ["drop1"]},
                    {"included_hashes": ["keep2"], "excluded_hashes": []},
                ]
                response = client.post("/api/v1/rss/subscribe/batch", json=body)
                assert response.status_code == 200
                _, kwargs = mock_svc.subscribe_batch.await_args
                assert kwargs["torrent_selections"] == body["torrent_selections"]
