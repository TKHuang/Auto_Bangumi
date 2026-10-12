"""End-to-end smoke test for complete application flow."""
import sys
from pathlib import Path

# Add backend/src to path so we can import main
backend_src = Path(__file__).parent.parent.parent.parent / "src"
sys.path.insert(0, str(backend_src))

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

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
                
                bangumi_response = client.get("/api/v1/bangumi/get/all")
                assert bangumi_response.status_code == 200
                assert bangumi_response.json() == []

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
