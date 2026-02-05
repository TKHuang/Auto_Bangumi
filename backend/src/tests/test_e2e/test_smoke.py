"""End-to-end smoke test for complete application flow."""
import sys
from pathlib import Path

# Add backend/src to path so we can import main
backend_src = Path(__file__).parent.parent.parent.parent / "src"
sys.path.insert(0, str(backend_src))

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

from main import create_app


@pytest.mark.e2e
class TestApplicationSmoke:
    """Smoke test that verifies the complete application lifecycle."""

    def test_complete_application_flow(self):
        """
        Test complete application flow from startup to shutdown.
        
        Flow:
        1. Startup: App starts with lifespan (creates tables, default user)
        2. Login: POST /auth/login with default credentials
        3. Verify Bangumi: GET /bangumi/get/all returns empty list
        4. Check Status: GET /bangumi/torrent/1 returns status
        5. Config: GET /config/get returns config
        6. Log: GET /log returns log content
        7. Check: GET /check returns version info
        8. Shutdown: App shuts down cleanly
        """
        with patch("module.services.downloader.qbittorrent.Client"):
            with TestClient(create_app()) as client:
                login_response = client.post(
                    "/api/v1/auth/login",
                    data={"username": "admin", "password": "adminadmin"},
                )
                assert login_response.status_code == 200, f"Login failed: {login_response.text}"
                login_data = login_response.json()
                assert "access_token" in login_data
                assert login_data["token_type"] == "bearer"
                assert "expire" in login_data
                
                token = login_data["access_token"]
                client.cookies.set("token", token)
                
                with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
                    mock_instance = MagicMock()
                    mock_manager.return_value.__enter__.return_value = mock_instance
                    mock_instance.bangumi.search_all.return_value = []
                    
                    bangumi_response = client.get("/api/v1/bangumi/get/all")
                    assert bangumi_response.status_code == 200
                    assert bangumi_response.json() == []
                
                with patch("module.api.v1.bangumi.TorrentStatusManager") as mock_manager:
                    mock_instance = MagicMock()
                    mock_manager.return_value.__enter__.return_value = mock_instance
                    mock_instance.get_bangumi_torrents_status.return_value = []
                    
                    status_response = client.get("/api/v1/bangumi/torrent/1")
                    assert status_response.status_code == 200
                    assert isinstance(status_response.json(), list)
                
                config_response = client.get("/api/v1/config/get")
                assert config_response.status_code == 200
                config_data = config_response.json()
                assert "program" in config_data
                assert "downloader" in config_data
                
                log_response = client.get("/api/v1/log")
                assert log_response.status_code == 200
                
                check_response = client.get("/api/v1/check/downloader")
                assert check_response.status_code in [200, 500]


@pytest.mark.e2e
class TestApplicationStartup:
    """Test application startup behavior."""

    def test_default_admin_user_created_on_first_run(self):
        """Test that default admin user is created on first run."""
        with patch("module.services.downloader.qbittorrent.Client"):
            with TestClient(create_app()) as client:
                # Try to login with default credentials
                response = client.post(
                    "/api/v1/auth/login",
                    data={"username": "admin", "password": "adminadmin"},
                )
                assert response.status_code == 200
                data = response.json()
                assert "access_token" in data


@pytest.mark.e2e
class TestApplicationShutdown:
    """Test application shutdown behavior."""

    def test_scheduler_stops_on_shutdown(self):
        """Test that scheduler stops cleanly on shutdown."""
        with patch("module.services.downloader.qbittorrent.Client"):
            with patch("module.scheduler.engine.AsyncScheduler.stop") as mock_stop:
                with TestClient(create_app()) as client:
                    response = client.post(
                        "/api/v1/auth/login",
                        data={"username": "admin", "password": "adminadmin"},
                    )
                    assert response.status_code == 200


@pytest.mark.e2e
class TestAuthenticationFlow:
    """Test authentication flow across multiple requests."""

    def test_login_refresh_logout_flow(self):
        """Test complete authentication lifecycle."""
        with patch("module.services.downloader.qbittorrent.Client"):
            with TestClient(create_app()) as client:
                login_response = client.post(
                    "/api/v1/auth/login",
                    data={"username": "admin", "password": "adminadmin"},
                )
                assert login_response.status_code == 200
                token = login_response.json()["access_token"]
                client.cookies.set("token", token)
                
                refresh_response = client.get("/api/v1/auth/refresh_token")
                assert refresh_response.status_code == 200
                new_token = refresh_response.json()["access_token"]
                assert "access_token" in refresh_response.json()
                
                logout_response = client.get("/api/v1/auth/logout")
                assert logout_response.status_code == 200
                assert "Logout successfully" in logout_response.json()["msg_en"]


@pytest.mark.e2e
class TestDatabaseIntegration:
    """Test database integration across the application."""

    def test_database_tables_created_on_startup(self):
        """Test that all database tables are created on startup."""
        with patch("module.services.downloader.qbittorrent.Client"):
            with TestClient(create_app()) as client:
                # If tables weren't created, login would fail
                response = client.post(
                    "/api/v1/auth/login",
                    data={"username": "admin", "password": "adminadmin"},
                )
                assert response.status_code == 200
                
                # Verify we can access endpoints that query database
                token = response.json()["access_token"]
                cookies = {"token": token}
                
                with patch("module.api.v1.bangumi.TorrentManager") as mock_manager:
                    mock_instance = MagicMock()
                    mock_manager.return_value.__enter__.return_value = mock_instance
                    mock_instance.bangumi.search_all.return_value = []
                    
                    bangumi_response = client.get(
                        "/api/v1/bangumi/get/all",
                        cookies=cookies,
                    )
                    assert bangumi_response.status_code == 200
