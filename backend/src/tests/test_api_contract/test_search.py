"""Tests for search API endpoints."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from module.api.middleware.auth import get_current_user
from module.api.v1.search import router


@pytest.fixture
def app():
    """FastAPI test app."""
    app = FastAPI()
    
    async def mock_get_current_user():
        return "test_user"
    
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def client(app):
    """FastAPI test client."""
    return TestClient(app)


class TestSearchBangumi:
    """Tests for GET /search/bangumi endpoint."""

    @pytest.mark.parametrize(
        "query,expected_keywords,expected_provider",
        [
            ("site=mikan&keywords=test", ["test"], "mikan"),
            ("site=nyaa&keywords=test anime 2024", ["test", "anime", "2024"], "nyaa"),
            ("keywords=test", ["test"], "mikan"),
        ],
        ids=["basic", "multiple_keywords", "default_provider"],
    )
    def test_search_bangumi_success(self, client, query, expected_keywords, expected_provider):
        """Test successful bangumi search with SSE streaming."""
        async def mock_search_generator(*args, **kwargs):
            yield json.dumps({"name": "Test Anime", "season": 1})

        with patch("module.api.v1.search.search") as mock_search:
            mock_search.return_value = mock_search_generator()

            response = client.get(f"/api/v1/search/bangumi?{query}")

            assert response.status_code == 200
            mock_search.assert_called_once_with(
                keywords=expected_keywords,
                provider=expected_provider,
            )

    @pytest.mark.parametrize(
        "query",
        [
            "site=mikan",
            "site=mikan&keywords=",
            "site=mikan&keywords=   ",
        ],
        ids=["missing_keywords", "empty_keywords", "whitespace_keywords"],
    )
    def test_search_bangumi_rejects_blank_keywords(self, client, query):
        """Missing, empty, or whitespace-only keywords are a 400."""
        response = client.get(f"/api/v1/search/bangumi?{query}")

        assert response.status_code == 400
        assert "keywords" in response.json()["detail"].lower()

    def test_search_bangumi_too_many_keywords(self, client):
        """Test search with more than 10 keywords."""
        keywords = " ".join(f"word{i}" for i in range(11))
        response = client.get(f"/api/v1/search/bangumi?keywords={keywords}")
        assert response.status_code == 400
        assert "too many" in response.json()["detail"].lower()

    def test_search_bangumi_invalid_provider(self, client):
        """Test search with unsupported provider."""
        with patch("module.api.v1.search.search") as mock_search:
            mock_search.side_effect = ValueError("Provider 'invalid' is not supported")
            
            response = client.get(
                "/api/v1/search/bangumi?site=invalid&keywords=test",
            )
            
            assert response.status_code == 400
            assert "not supported" in response.json()["detail"]

    def test_search_bangumi_sse_content_type(self, client):
        """Test that search returns SSE content type."""
        async def mock_search_generator(*args, **kwargs):
            yield json.dumps({"name": "Test Anime", "season": 1})

        with patch("module.api.v1.search.search") as mock_search:
            mock_search.return_value = mock_search_generator()
            
            response = client.get(
                "/api/v1/search/bangumi?site=mikan&keywords=test",
            )
            
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
