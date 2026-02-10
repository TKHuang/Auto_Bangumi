"""E2E tests for search API endpoints.

Note: The search endpoint uses SSE (EventSourceResponse). With TestClient,
we may not receive full SSE events, so we verify the response starts correctly.
"""
import pytest
from unittest.mock import patch


@pytest.mark.e2e
class TestSearchProvider:
    """GET /api/v1/search/provider"""

    def test_get_provider_list(self, authed_client):
        """GET /api/v1/search/provider returns list of strings."""
        client, mock_dl, token = authed_client

        resp = client.get("/api/v1/search/provider")
        assert resp.status_code == 200

        body = resp.json()
        assert isinstance(body, list)
        assert len(body) >= 1
        # Each provider should be a string
        for provider in body:
            assert isinstance(provider, str)
        # mikan should be available as default provider
        assert "mikan" in body


@pytest.mark.e2e
class TestSearchBangumi:
    """GET /api/v1/search/bangumi"""

    def test_search_returns_response(self, authed_client):
        """GET /api/v1/search/bangumi?keywords=test&site=mikan returns 200."""
        client, mock_dl, token = authed_client

        resp = client.get(
            "/api/v1/search/bangumi",
            params={"keywords": "test", "site": "mikan"},
        )
        # SSE endpoint returns 200 with streaming content
        assert resp.status_code == 200

    def test_empty_keywords(self, authed_client):
        """GET /api/v1/search/bangumi?keywords= → 400."""
        client, mock_dl, token = authed_client

        resp = client.get(
            "/api/v1/search/bangumi",
            params={"keywords": "", "site": "mikan"},
        )
        assert resp.status_code == 400

    def test_unsupported_provider(self, authed_client):
        """GET /api/v1/search/bangumi?keywords=test&site=fakeprovider → 200.

        The search endpoint wraps search() in an EventSourceResponse. Since
        search() is an async generator, the ValueError for unsupported
        providers is only raised during streaming (iteration), not during
        response construction. The endpoint therefore returns 200 with an
        SSE stream rather than catching the ValueError synchronously.
        """
        client, mock_dl, token = authed_client

        resp = client.get(
            "/api/v1/search/bangumi",
            params={"keywords": "test", "site": "fakeprovider"},
        )
        assert resp.status_code == 200

    @patch("module.api.middleware.auth.VERSION", "3.0.0")
    def test_requires_auth(self, e2e_client):
        """GET /api/v1/search/bangumi without auth → 401."""
        client, mock_dl = e2e_client

        resp = client.get(
            "/api/v1/search/bangumi",
            params={"keywords": "test", "site": "mikan"},
        )
        assert resp.status_code == 401
