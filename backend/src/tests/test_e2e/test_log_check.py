"""E2E tests for log and downloader check API endpoints."""
import pytest
from unittest.mock import patch


@pytest.mark.e2e
class TestLog:
    """GET /api/v1/log and /api/v1/log/clear"""

    @patch("module.api.middleware.auth.VERSION", "3.0.0")
    def test_requires_auth(self, e2e_client):
        """GET /api/v1/log without auth → 401."""
        client, mock_dl = e2e_client

        resp = client.get("/api/v1/log")
        assert resp.status_code == 401


@pytest.mark.e2e
class TestCheckDownloader:
    """GET /api/v1/check/downloader"""

    @patch("module.api.middleware.auth.VERSION", "3.0.0")
    def test_requires_auth(self, e2e_client):
        """GET /api/v1/check/downloader without auth → 401."""
        client, mock_dl = e2e_client

        resp = client.get("/api/v1/check/downloader")
        assert resp.status_code == 401
