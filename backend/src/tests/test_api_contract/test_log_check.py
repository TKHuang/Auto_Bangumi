import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends

from module.api.v1.log import router as log_router
from module.api.v1.check import router as check_router
from module.conf import LOG_PATH


@pytest.fixture
def app():
    app = FastAPI()
    
    async def mock_get_current_user():
        return "testuser"
    
    app.dependency_overrides[__import__("module.api.middleware.auth", fromlist=["get_current_user"]).get_current_user] = mock_get_current_user
    
    app.include_router(log_router)
    app.include_router(check_router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestLogEndpoints:
    def test_get_log_returns_string(self, client, tmp_path):
        log_file = tmp_path / "log.txt"
        log_file.write_text("line1\nline2\nline3\n")
        
        with patch("module.api.v1.log.LOG_PATH", log_file):
            response = client.get("/log")
            assert response.status_code == 200
            assert "text/plain" in response.headers.get("content-type", "")
            assert "line1" in response.text
            assert "line2" in response.text
            assert "line3" in response.text

    def test_get_log_last_100_lines(self, client, tmp_path):
        log_file = tmp_path / "log.txt"
        lines = [f"line{i}\n" for i in range(150)]
        log_file.write_text("".join(lines))
        
        with patch("module.api.v1.log.LOG_PATH", log_file):
            response = client.get("/log")
            assert response.status_code == 200
            assert "line50" in response.text
            assert "line149" in response.text
            assert "line0" not in response.text

    def test_get_log_file_not_found(self, client, tmp_path):
        nonexistent = tmp_path / "nonexistent.txt"
        
        with patch("module.api.v1.log.LOG_PATH", nonexistent):
            response = client.get("/log")
            assert response.status_code == 404
            assert "Log file not found" in response.text

    def test_clear_log_success(self, client, tmp_path):
        log_file = tmp_path / "log.txt"
        log_file.write_text("some log content")
        
        with patch("module.api.v1.log.LOG_PATH", log_file):
            response = client.get("/log/clear")
            assert response.status_code == 200
            assert response.json() == {
                "msg_en": "Log cleared successfully.",
                "msg_zh": "日志清除成功。"
            }
            assert log_file.read_text() == ""

    def test_clear_log_file_not_found(self, client, tmp_path):
        nonexistent = tmp_path / "nonexistent.txt"
        
        with patch("module.api.v1.log.LOG_PATH", nonexistent):
            response = client.get("/log/clear")
            assert response.status_code == 406
            assert response.json() == {
                "msg_en": "Log file not found.",
                "msg_zh": "日志文件未找到。"
            }


class TestCheckEndpoints:
    def test_check_downloader_success(self, client):
        mock_downloader = AsyncMock()
        mock_downloader.check_host = AsyncMock(return_value=True)
        mock_downloader.auth = AsyncMock(return_value=True)
        
        with patch("module.api.v1.check.create_downloader") as mock_factory:
            mock_factory.return_value = mock_downloader
            response = client.get("/check/downloader")
            assert response.status_code == 200
            assert response.json() is True

    def test_check_downloader_host_unreachable(self, client):
        mock_downloader = AsyncMock()
        mock_downloader.check_host = AsyncMock(return_value=False)
        
        with patch("module.api.v1.check.create_downloader") as mock_factory:
            mock_factory.return_value = mock_downloader
            response = client.get("/check/downloader")
            assert response.status_code == 200
            assert response.json() is False

    def test_check_downloader_auth_failed(self, client):
        mock_downloader = AsyncMock()
        mock_downloader.check_host = AsyncMock(return_value=True)
        mock_downloader.auth = AsyncMock(return_value=False)
        
        with patch("module.api.v1.check.create_downloader") as mock_factory:
            mock_factory.return_value = mock_downloader
            response = client.get("/check/downloader")
            assert response.status_code == 200
            assert response.json() is False

    def test_check_downloader_exception(self, client):
        with patch("module.api.v1.check.create_downloader") as mock_factory:
            mock_factory.side_effect = Exception("Connection error")
            response = client.get("/check/downloader")
            assert response.status_code == 200
            assert response.json() is False
