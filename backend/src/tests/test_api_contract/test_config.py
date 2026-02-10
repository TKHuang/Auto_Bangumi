"""Tests for config API endpoints."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from module.api.v1.config import router
from module.conf.models import Config, Program, Downloader, RSSParser, BangumiManage, Log, Proxy, Notification, ExperimentalOpenAI
from fastapi import FastAPI


@pytest.fixture
def app():
    """Create FastAPI app with config router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_config():
    """Create mock config object."""
    return Config(
        program=Program(rss_time=900, rename_time=60, webui_port=7892),
        downloader=Downloader(
            type="qbittorrent",
            host_="172.17.0.1:8080",
            username_="admin",
            password_="adminadmin",
            path="/downloads/Bangumi",
            ssl=False,
        ),
        rss_parser=RSSParser(
            enable=True,
            filter=["720", r"\d+-\d"],
            language="zh",
        ),
        bangumi_manage=BangumiManage(
            enable=True,
            eps_complete=False,
            eps_complete_from_source=True,
            rename_method="pn",
            group_tag=False,
            remove_bad_torrent=False,
        ),
        log=Log(debug_enable=False),
        proxy=Proxy(
            enable=False,
            type="http",
            host="",
            port=0,
            username_="",
            password_="",
        ),
        notification=Notification(
            enable=False,
            type="telegram",
            token_="",
            chat_id_="",
        ),
        experimental_openai=ExperimentalOpenAI(
            enable=False,
            api_key="",
            api_base="https://api.openai.com/v1",
            api_type="openai",
            api_version="2023-05-15",
            model="gpt-3.5-turbo",
            deployment_id="",
        ),
    )


class TestGetConfig:
    """Tests for GET /config/get endpoint."""

    def test_get_config_without_auth(self, client):
        """Test GET /config/get without authentication returns 401."""
        with patch("module.api.middleware.auth.VERSION", "3.0.0"):
            response = client.get("/config/get")
            assert response.status_code == 401

    def test_get_config_with_auth(self, client, mock_config):
        """Test GET /config/get with valid token returns full config."""
        with patch("module.api.middleware.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = {"sub": "testuser"}
            
            with patch("module.api.v1.config.settings", mock_config):
                response = client.get("/config/get", cookies={"token": "valid_token"})
                
                assert response.status_code == 200
                data = response.json()
                
                # Verify all config sections present
                assert "program" in data
                assert "downloader" in data
                assert "rss_parser" in data
                assert "bangumi_manage" in data
                assert "log" in data
                assert "proxy" in data
                assert "notification" in data
                assert "experimental_openai" in data
                
                # Verify program section
                assert data["program"]["rss_time"] == 900
                assert data["program"]["rename_time"] == 60
                assert data["program"]["webui_port"] == 7892
                
                # Verify downloader section (with aliases)
                assert data["downloader"]["type"] == "qbittorrent"
                assert data["downloader"]["host"] == "172.17.0.1:8080"
                assert data["downloader"]["username"] == "admin"
                assert data["downloader"]["password"] == "adminadmin"
                assert data["downloader"]["path"] == "/downloads/Bangumi"
                assert data["downloader"]["ssl"] is False

    def test_get_config_invalid_token(self, client):
        """Test GET /config/get with invalid token returns 401."""
        with patch("module.api.middleware.auth.VERSION", "3.0.0"):
            with patch("module.api.middleware.auth.decode_access_token") as mock_decode:
                mock_decode.side_effect = Exception("Invalid token")
                
                response = client.get("/config/get", cookies={"token": "invalid_token"})
                assert response.status_code == 401


class TestUpdateConfig:
    """Tests for PATCH /config/update endpoint."""

    def test_update_config_without_auth(self, client, mock_config):
        """Test PATCH /config/update without authentication returns 401."""
        with patch("module.api.middleware.auth.VERSION", "3.0.0"):
            response = client.patch("/config/update", json=mock_config.model_dump(by_alias=True))
            assert response.status_code == 401

    def test_update_config_success(self, client, mock_config):
        """Test PATCH /config/update with valid token saves config."""
        with patch("module.api.middleware.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = {"sub": "testuser"}
            
            mock_settings = MagicMock()
            mock_settings.save = MagicMock()
            mock_settings.load = MagicMock()
            
            with patch("module.api.v1.config.settings", mock_settings):
                response = client.patch(
                    "/config/update",
                    json=mock_config.model_dump(by_alias=True),
                    cookies={"token": "valid_token"},
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["msg_en"] == "Update config successfully."
                assert data["msg_zh"] == "更新配置成功。"
                
                # Verify save and load were called
                mock_settings.save.assert_called_once()
                mock_settings.load.assert_called_once()

    def test_update_config_save_failure(self, client, mock_config):
        """Test PATCH /config/update handles save failure gracefully."""
        with patch("module.api.middleware.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = {"sub": "testuser"}
            
            mock_settings = MagicMock()
            mock_settings.save = MagicMock(side_effect=Exception("Save failed"))
            
            with patch("module.api.v1.config.settings", mock_settings):
                response = client.patch(
                    "/config/update",
                    json=mock_config.model_dump(by_alias=True),
                    cookies={"token": "valid_token"},
                )
                
                assert response.status_code == 500
                data = response.json()
                assert data["msg_en"] == "Update config failed."
                assert data["msg_zh"] == "更新配置失败。"

    def test_update_config_partial_update(self, client, mock_config):
        """Test PATCH /config/update with partial config changes."""
        with patch("module.api.middleware.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = {"sub": "testuser"}
            
            mock_settings = MagicMock()
            mock_settings.save = MagicMock()
            mock_settings.load = MagicMock()
            
            # Modify only program section
            updated_config = mock_config.model_dump(by_alias=True)
            updated_config["program"]["rss_time"] = 1800
            
            with patch("module.api.v1.config.settings", mock_settings):
                response = client.patch(
                    "/config/update",
                    json=updated_config,
                    cookies={"token": "valid_token"},
                )
                
                assert response.status_code == 200
                
                # Verify save was called with updated config
                call_args = mock_settings.save.call_args
                assert call_args is not None
                saved_config = call_args.kwargs.get("config_dict")
                assert saved_config["program"]["rss_time"] == 1800

    def test_update_config_invalid_token(self, client, mock_config):
        """Test PATCH /config/update with invalid token returns 401."""
        with patch("module.api.middleware.auth.VERSION", "3.0.0"):
            with patch("module.api.middleware.auth.decode_access_token") as mock_decode:
                mock_decode.side_effect = Exception("Invalid token")
                
                response = client.patch(
                    "/config/update",
                    json=mock_config.model_dump(by_alias=True),
                    cookies={"token": "invalid_token"},
                )
                assert response.status_code == 401

    def test_update_config_uses_by_alias(self, client, mock_config):
        """Test PATCH /config/update uses by_alias=True for serialization."""
        with patch("module.api.middleware.auth.decode_access_token") as mock_decode:
            mock_decode.return_value = {"sub": "testuser"}
            
            mock_settings = MagicMock()
            mock_settings.save = MagicMock()
            mock_settings.load = MagicMock()
            
            with patch("module.api.v1.config.settings", mock_settings):
                response = client.patch(
                    "/config/update",
                    json=mock_config.model_dump(by_alias=True),
                    cookies={"token": "valid_token"},
                )
                
                assert response.status_code == 200
                
                # Verify save was called with by_alias=True format
                call_args = mock_settings.save.call_args
                saved_config = call_args.kwargs.get("config_dict")
                
                # Check that aliases are used (e.g., "host" not "host_")
                assert "host" in saved_config["downloader"]
                assert "username" in saved_config["downloader"]
                assert "password" in saved_config["downloader"]
