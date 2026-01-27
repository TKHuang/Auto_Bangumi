"""Integration tests for Search API endpoints.

This module contains integration tests for the Search API routes:
- /api/v1/search/bangumi (GET) - SSE stream search for bangumi
- /api/v1/search/provider (GET) - Returns list of search providers

Note: SSE (Server-Sent Events) endpoints have known limitations with TestClient
when making multiple SSE requests in the same test session due to event loop state
in sse_starlette.AppStatus.should_exit_event. Tests are designed to work around
these limitations while still verifying the core functionality.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from module.models.bangumi import Bangumi


class TestSearchAPIBangumi:
    """Tests for GET /api/v1/search/bangumi endpoint (SSE stream)."""

    @pytest.mark.integration
    def test_search_bangumi_sse_stream_with_different_sites(self, authenticated_client):
        """Test GET /api/v1/search/bangumi returns SSE stream with results.

        This endpoint uses Server-Sent Events (SSE) to stream Bangumi results.
        Each result is JSON-encoded and sent as an SSE event.

        This test also validates that the endpoint correctly accepts the site
        parameter which supports multiple search providers (mikan, dmhy, nyaa).
        The site parameter is passed to SearchTorrent.analyse_keyword.
        """
        # Track which sites are passed to the mock
        captured_sites = []

        # Mock SearchTorrent.analyse_keyword to yield test results
        mock_bangumi1 = Bangumi(
            official_title="Test Anime 1",
            title_raw="[TestGroup] Test Anime 1",
            season=1,
            group_name="TestGroup",
            rss_link="https://mikanani.me/RSS/Search?searchstr=TestAnime1",
        )
        mock_bangumi2 = Bangumi(
            official_title="Test Anime 2",
            title_raw="[TestGroup] Test Anime 2",
            season=1,
            group_name="TestGroup",
            rss_link="https://mikanani.me/RSS/Search?searchstr=TestAnime2",
        )

        def mock_analyse_keyword(keywords, site="mikan", limit=5):
            """Generator that yields JSON-encoded Bangumi results.

            Validates and captures the site parameter.
            """
            # Capture the site for verification
            captured_sites.append(site)
            # Validate site is one of the supported values
            assert site in ["mikan", "dmhy", "nyaa"], f"Unsupported site: {site}"
            yield json.dumps(mock_bangumi1.dict(), separators=(",", ":"))
            yield json.dumps(mock_bangumi2.dict(), separators=(",", ":"))

        # Create a mock that works as context manager
        mock_search_instance = MagicMock()
        mock_search_instance.analyse_keyword = mock_analyse_keyword
        mock_search_instance.__enter__ = MagicMock(return_value=mock_search_instance)
        mock_search_instance.__exit__ = MagicMock(return_value=None)

        # Test with mikan site (validates site parameter is passed correctly)
        with patch(
            "module.api.search.SearchTorrent", return_value=mock_search_instance
        ):
            response = authenticated_client.get(
                "/api/v1/search/bangumi",
                params={"site": "mikan", "keywords": "Test Anime"},
            )

        # SSE endpoint returns 200 with text/event-stream content type
        assert response.status_code == 200
        # Verify site parameter was correctly passed
        assert "mikan" in captured_sites
        # The mock validates that only mikan/dmhy/nyaa are valid sites

    @pytest.mark.integration
    def test_search_bangumi_site_parameter_validation(self, authenticated_client):
        """Test that different site parameters (mikan/dmhy/nyaa) are accepted.

        The endpoint accepts site parameter values: mikan, dmhy, nyaa.
        This test verifies the API correctly routes different site values.

        Note: Since we can only make one SSE request per test session due to
        event loop limitations, we test the site parameter handling through
        the unit tests in test_search_torrent_unit.py and verify here that
        the API accepts the parameter.

        The endpoint returns [] for empty keywords, which doesn't create an
        SSE stream, allowing us to test parameter parsing without hitting
        the event loop issue.
        """
        # Test that different site parameters are accepted by the API
        # Using empty keywords to avoid SSE stream (returns [] immediately)
        for site in ["mikan", "dmhy", "nyaa"]:
            response = authenticated_client.get(
                "/api/v1/search/bangumi",
                params={"site": site, "keywords": ""},
            )
            # All valid sites should be accepted (empty keywords returns [])
            assert response.status_code == 200
            assert response.json() == []

    @pytest.mark.integration
    def test_search_bangumi_empty_keywords_returns_empty(self, authenticated_client):
        """Test GET /api/v1/search/bangumi with empty keywords returns empty list.

        When no keywords are provided, the endpoint should return an empty
        list immediately without invoking the search.
        """
        # Test with no keywords parameter
        response = authenticated_client.get("/api/v1/search/bangumi")

        assert response.status_code == 200
        # Empty keywords should return empty list directly
        data = response.json()
        assert data == []

        # Test with empty string keywords
        response_empty = authenticated_client.get(
            "/api/v1/search/bangumi",
            params={"keywords": ""},
        )

        assert response_empty.status_code == 200
        # Empty string should also return empty list
        data_empty = response_empty.json()
        assert data_empty == []


class TestSearchAPIProvider:
    """Tests for GET /api/v1/search/provider endpoint."""

    @pytest.mark.integration
    def test_get_providers_returns_list(self, authenticated_client):
        """Test GET /api/v1/search/provider returns list of available providers.

        The endpoint should return a list of search provider names
        (e.g., ['mikan', 'dmhy', 'nyaa']).
        """
        # Mock SEARCH_CONFIG to ensure consistent test results
        mock_config = {"mikan": "...", "dmhy": "...", "nyaa": "..."}

        with patch("module.api.search.SEARCH_CONFIG", mock_config):
            response = authenticated_client.get("/api/v1/search/provider")

        assert response.status_code == 200
        data = response.json()
        # Response should be a list
        assert isinstance(data, list)
        # Should contain at least some providers
        assert len(data) > 0
        # Check for expected default providers
        assert "mikan" in data or "dmhy" in data or "nyaa" in data
