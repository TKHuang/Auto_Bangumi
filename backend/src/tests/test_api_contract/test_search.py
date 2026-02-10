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


class TestSearchProvider:
    """Tests for GET /search/provider endpoint."""

    def test_search_provider_success(self, client):
        """Test successful provider list retrieval."""
        with patch("module.api.v1.search.get_providers") as mock_get:
            mock_get.return_value = ["mikan", "nyaa", "dmhy"]
            
            response = client.get("/api/v1/search/provider")
            
            assert response.status_code == 200
            assert response.json() == ["mikan", "nyaa", "dmhy"]
            mock_get.assert_called_once()

    def test_search_provider_empty_list(self, client):
        """Test provider list when no providers available."""
        with patch("module.api.v1.search.get_providers") as mock_get:
            mock_get.return_value = []
            
            response = client.get("/api/v1/search/provider")
            
            assert response.status_code == 200
            assert response.json() == []


class TestSearchBangumi:
    """Tests for GET /search/bangumi endpoint."""

    def test_search_bangumi_success(self, client):
        """Test successful bangumi search with SSE streaming."""
        async def mock_search_generator(*args, **kwargs):
            yield json.dumps({"name": "Test Anime 1", "season": 1})
            yield json.dumps({"name": "Test Anime 2", "season": 1})

        with patch("module.api.v1.search.search") as mock_search:
            mock_search.return_value = mock_search_generator()
            
            response = client.get(
                "/api/v1/search/bangumi?site=mikan&keywords=test",
            )
            
            assert response.status_code == 200
            mock_search.assert_called_once_with(
                keywords=["test"],
                provider="mikan",
                limit=5,
            )

    def test_search_bangumi_multiple_keywords(self, client):
        """Test search with multiple keywords."""
        async def mock_search_generator(*args, **kwargs):
            yield json.dumps({"name": "Test Anime", "season": 1})

        with patch("module.api.v1.search.search") as mock_search:
            mock_search.return_value = mock_search_generator()
            
            response = client.get(
                "/api/v1/search/bangumi?site=nyaa&keywords=test anime 2024",
            )
            
            assert response.status_code == 200
            mock_search.assert_called_once_with(
                keywords=["test", "anime", "2024"],
                provider="nyaa",
                limit=5,
            )

    def test_search_bangumi_default_provider(self, client):
        """Test search with default provider (mikan)."""
        async def mock_search_generator(*args, **kwargs):
            yield json.dumps({"name": "Test Anime", "season": 1})

        with patch("module.api.v1.search.search") as mock_search:
            mock_search.return_value = mock_search_generator()
            
            response = client.get(
                "/api/v1/search/bangumi?keywords=test",
            )
            
            assert response.status_code == 200
            mock_search.assert_called_once_with(
                keywords=["test"],
                provider="mikan",
                limit=5,
            )

    def test_search_bangumi_missing_keywords(self, client):
        """Test search without keywords parameter."""
        response = client.get(
            "/api/v1/search/bangumi?site=mikan",
        )
        
        assert response.status_code == 400
        assert "keywords" in response.json()["detail"].lower()

    def test_search_bangumi_empty_keywords(self, client):
        """Test search with empty keywords."""
        response = client.get(
            "/api/v1/search/bangumi?site=mikan&keywords=",
        )
        
        assert response.status_code == 400
        assert "keywords" in response.json()["detail"].lower()

    def test_search_bangumi_whitespace_keywords(self, client):
        """Test search with whitespace-only keywords."""
        response = client.get(
            "/api/v1/search/bangumi?site=mikan&keywords=   ",
        )
        
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
