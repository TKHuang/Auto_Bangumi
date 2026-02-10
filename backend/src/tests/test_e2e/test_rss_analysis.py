"""E2E tests for RSS analysis and pending endpoints."""
import pytest

from tests.test_e2e.conftest import (
    WILD_BOSS_RSS_URL,
    add_non_aggregate_rss,
    get_all_rss,
)


@pytest.mark.e2e
class TestRSSAnalysis:
    """Tests for POST /api/v1/rss/analysis."""

    def test_valid_analysis(self, authed_client):
        client, mock_dl, token = authed_client

        resp = client.post(
            "/api/v1/rss/analysis",
            json={
                "url": WILD_BOSS_RSS_URL,
                "name": "Wild Boss",
                "aggregate": False,
                "parser": "mikan",
                "enabled": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "official_title" in data
        assert "title_raw" in data
        assert "season" in data

    def test_analysis_error(self, authed_client, fixture_request_content):
        client, mock_dl, token = authed_client

        # Patch _resolve_xml to return None for this URL
        original_resolve = fixture_request_content._resolve_xml

        def _broken_resolve(url):
            if "bad_url" in url:
                return None
            return original_resolve(url)

        fixture_request_content._resolve_xml = _broken_resolve

        resp = client.post(
            "/api/v1/rss/analysis",
            json={
                "url": "https://mikanani.me/RSS/bad_url",
                "name": "Bad Feed",
                "aggregate": False,
                "parser": "mikan",
                "enabled": True,
            },
        )
        # Should return an error (406 from ResponseModel or 422/500)
        assert resp.status_code in (404, 422, 500)


@pytest.mark.e2e
class TestRSSAnalysisTorrents:
    """Tests for POST /api/v1/rss/analysis/torrents."""

    def test_with_filter(self, authed_client):
        client, mock_dl, token = authed_client

        resp = client.post(
            "/api/v1/rss/analysis/torrents",
            params={"_filter": "720"},
            json={
                "url": WILD_BOSS_RSS_URL,
                "name": "Wild Boss",
                "aggregate": False,
                "parser": "mikan",
                "enabled": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Each torrent dict should have a "filter" field
        for t in data:
            assert "name" in t
            assert "filter" in t

    def test_without_filter(self, authed_client):
        client, mock_dl, token = authed_client

        resp = client.post(
            "/api/v1/rss/analysis/torrents",
            json={
                "url": WILD_BOSS_RSS_URL,
                "name": "Wild Boss",
                "aggregate": False,
                "parser": "mikan",
                "enabled": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1


@pytest.mark.e2e
class TestPendingEndpoints:
    """Tests for GET /api/v1/rss/{rss_id}/pending-count and /pending."""

    def test_pending_count(self, authed_client):
        client, mock_dl, token = authed_client

        add_non_aggregate_rss(client)
        rss_list = get_all_rss(client).json()
        rss_id = rss_list[0]["id"]

        resp = client.get(f"/api/v1/rss/{rss_id}/pending-count")
        assert resp.status_code == 200
        data = resp.json()
        assert "pending_count" in data
        assert isinstance(data["pending_count"], int)

    def test_pending_list(self, authed_client):
        client, mock_dl, token = authed_client

        add_non_aggregate_rss(client)
        rss_list = get_all_rss(client).json()
        rss_id = rss_list[0]["id"]

        resp = client.get(f"/api/v1/rss/{rss_id}/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
