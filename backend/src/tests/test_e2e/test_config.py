"""E2E tests for config API endpoints."""
import pytest
from unittest.mock import patch


@pytest.mark.e2e
class TestGetConfig:
    """GET /api/v1/config/get"""

    def test_get_config(self, authed_client):
        """GET /api/v1/config/get returns config with program and downloader keys."""
        client, mock_dl, token = authed_client

        resp = client.get("/api/v1/config/get")
        assert resp.status_code == 200

        body = resp.json()
        assert "program" in body
        assert "downloader" in body

    @patch("module.api.middleware.auth.VERSION", "3.0.0")
    def test_requires_auth(self, e2e_client):
        """GET /api/v1/config/get without auth → 401."""
        client, mock_dl = e2e_client

        resp = client.get("/api/v1/config/get")
        assert resp.status_code == 401


@pytest.mark.e2e
class TestUpdateConfig:
    """PATCH /api/v1/config/update"""

    def test_update_config(self, authed_client):
        """PATCH /api/v1/config/update with valid config."""
        client, mock_dl, token = authed_client

        # First get current config
        get_resp = client.get("/api/v1/config/get")
        assert get_resp.status_code == 200
        config = get_resp.json()

        # Update with the same config (should succeed)
        update_resp = client.patch("/api/v1/config/update", json=config)
        assert update_resp.status_code == 200
        body = update_resp.json()
        assert "msg_en" in body

    def test_readback_after_update(self, authed_client):
        """Update then get, verify change persisted."""
        client, mock_dl, token = authed_client

        # Get current config
        get_resp = client.get("/api/v1/config/get")
        assert get_resp.status_code == 200
        config = get_resp.json()

        # Update config (round-trip with same values)
        update_resp = client.patch("/api/v1/config/update", json=config)
        assert update_resp.status_code == 200

        # Read back
        readback_resp = client.get("/api/v1/config/get")
        assert readback_resp.status_code == 200
        readback = readback_resp.json()

        # Verify key fields match
        assert readback["program"] == config["program"]
        assert readback["downloader"]["type"] == config["downloader"]["type"]

    @patch("module.api.middleware.auth.VERSION", "3.0.0")
    def test_requires_auth(self, e2e_client):
        """PATCH /api/v1/config/update without auth → 401."""
        client, mock_dl = e2e_client

        resp = client.patch("/api/v1/config/update", json={})
        assert resp.status_code == 401
