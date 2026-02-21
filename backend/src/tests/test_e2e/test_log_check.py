"""E2E tests for log and downloader check API endpoints."""
import pytest
from unittest.mock import patch


@pytest.mark.e2e
class TestLog:
    """GET /api/v1/log and /api/v1/log/clear"""

    def test_get_log(self, authed_client):
        """GET /api/v1/log returns text (200 or 404 if log file doesn't exist)."""
        client, mock_dl, token = authed_client

        resp = client.get("/api/v1/log")
        # 200 if log file exists, 404 if it doesn't
        assert resp.status_code in (200, 404)

        if resp.status_code == 200:
            # Response should be plain text
            assert "text/plain" in resp.headers.get("content-type", "")

    def test_clear_log(self, authed_client):
        """GET /api/v1/log/clear clears the log file."""
        client, mock_dl, token = authed_client

        resp = client.delete("/api/v1/log/clear")
        # 200 if log file was cleared, 406 if log file not found
        assert resp.status_code in (200, 404)

        if resp.status_code == 200:
            body = resp.json()
            assert "msg_en" in body

    @patch("module.api.middleware.auth.VERSION", "3.0.0")
    def test_requires_auth(self, e2e_client):
        """GET /api/v1/log without auth → 401."""
        client, mock_dl = e2e_client

        resp = client.get("/api/v1/log")
        assert resp.status_code == 401


@pytest.mark.e2e
class TestCheckDownloader:
    """GET /api/v1/check/downloader"""

    def test_check_success(self, authed_client):
        """GET /api/v1/check/downloader → True (mock_dl returns True)."""
        client, mock_dl, token = authed_client

        # mock_dl.check_host and .auth already return True (from conftest)
        resp = client.get("/api/v1/check/downloader")
        assert resp.status_code == 200
        assert resp.json() is True

    def test_check_failure(self, authed_client):
        """Mock check_host to return False → response is False."""
        client, mock_dl, token = authed_client

        mock_dl.check_host.return_value = False

        resp = client.get("/api/v1/check/downloader")
        assert resp.status_code == 200
        assert resp.json() is False

        mock_dl.check_host.return_value = True

    @patch("module.api.middleware.auth.VERSION", "3.0.0")
    def test_requires_auth(self, e2e_client):
        """GET /api/v1/check/downloader without auth → 401."""
        client, mock_dl = e2e_client

        resp = client.get("/api/v1/check/downloader")
        assert resp.status_code == 401
