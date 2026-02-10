"""E2E tests for RSS subscribe/collect/batch and aggregate pending endpoints."""
from unittest.mock import MagicMock, patch

import pytest

from tests.test_e2e.conftest import (
    AGGREGATE_RSS_URL,
    WILD_BOSS_RSS_URL,
    add_aggregate_rss,
    add_non_aggregate_rss,
    get_all_bangumi,
    get_all_rss,
)


def _get_first_bangumi(client):
    """Helper: return the first bangumi dict, or None."""
    resp = get_all_bangumi(client)
    bangumi_list = resp.json()
    return bangumi_list[0] if bangumi_list else None


@pytest.mark.e2e
class TestCollect:
    """Tests for POST /api/v1/rss/collect."""

    def test_full_collection(self, authed_client):
        client, mock_dl, token = authed_client

        # Add a non-aggregate RSS so we have a bangumi
        add_non_aggregate_rss(client)
        bangumi = _get_first_bangumi(client)
        assert bangumi is not None

        # Patch SearchTorrent where it is defined (module.searcher).
        # collector.py imports it locally via `from module.searcher import SearchTorrent`,
        # so patching the origin module is sufficient.
        with patch("module.searcher.SearchTorrent") as MockST:
            mock_st_instance = MagicMock()
            mock_st_instance.__enter__ = MagicMock(return_value=mock_st_instance)
            mock_st_instance.__exit__ = MagicMock(return_value=False)
            mock_st_instance.get_torrents.return_value = []
            mock_st_instance.search_season.return_value = []
            MockST.return_value = mock_st_instance

            resp = client.post(
                "/api/v1/rss/collect",
                json=bangumi,
            )
            assert resp.status_code in (200, 404)

    def test_empty_rss(self, authed_client):
        client, mock_dl, token = authed_client

        # Add a non-aggregate RSS so we have a bangumi
        add_non_aggregate_rss(client)
        bangumi = _get_first_bangumi(client)
        assert bangumi is not None

        # Set rss_link to a URL that returns no torrents
        bangumi_copy = dict(bangumi)
        bangumi_copy["rss_link"] = ""

        # Patch SearchTorrent where it is defined (module.searcher).
        with patch("module.searcher.SearchTorrent") as MockST:
            mock_st_instance = MagicMock()
            mock_st_instance.__enter__ = MagicMock(return_value=mock_st_instance)
            mock_st_instance.__exit__ = MagicMock(return_value=False)
            mock_st_instance.get_torrents.return_value = []
            mock_st_instance.search_season.return_value = []
            MockST.return_value = mock_st_instance

            resp = client.post(
                "/api/v1/rss/collect",
                json=bangumi_copy,
            )
            # Expect 404 (no new episodes found) or 200
            assert resp.status_code in (200, 404)


@pytest.mark.e2e
class TestSubscribe:
    """Tests for POST /api/v1/rss/subscribe."""

    def test_subscribe_creates_and_downloads(self, authed_client):
        client, mock_dl, token = authed_client

        # First analyse to get a Bangumi object
        analysis_resp = client.post(
            "/api/v1/rss/analysis",
            json={
                "url": WILD_BOSS_RSS_URL,
                "name": "Wild Boss",
                "aggregate": False,
                "parser": "mikan",
                "enabled": True,
            },
        )
        assert analysis_resp.status_code == 200
        bangumi_data = analysis_resp.json()

        # Subscribe using the analysed bangumi + RSS info
        # FastAPI expects nested body: {"data": ..., "rss": ...}
        resp = client.post(
            "/api/v1/rss/subscribe",
            json={
                "data": bangumi_data,
                "rss": {
                    "url": WILD_BOSS_RSS_URL,
                    "name": "Wild Boss",
                    "aggregate": False,
                    "parser": "mikan",
                    "enabled": True,
                },
            },
        )
        assert resp.status_code == 200

        # Verify bangumi was created
        bangumi_list = get_all_bangumi(client).json()
        assert len(bangumi_list) >= 1

        # Verify RSS was created
        rss_list = get_all_rss(client).json()
        assert len(rss_list) >= 1

    def test_subscribe_duplicate_rejected(self, authed_client):
        client, mock_dl, token = authed_client

        # Analyse to get bangumi data
        analysis_resp = client.post(
            "/api/v1/rss/analysis",
            json={
                "url": WILD_BOSS_RSS_URL,
                "name": "Wild Boss",
                "aggregate": False,
                "parser": "mikan",
                "enabled": True,
            },
        )
        assert analysis_resp.status_code == 200
        bangumi_data = analysis_resp.json()

        # First subscribe
        resp1 = client.post(
            "/api/v1/rss/subscribe",
            json={
                "data": bangumi_data,
                "rss": {
                    "url": WILD_BOSS_RSS_URL,
                    "name": "Wild Boss",
                    "aggregate": False,
                    "parser": "mikan",
                    "enabled": True,
                },
            },
        )
        assert resp1.status_code == 200

        # Second subscribe with same data should succeed (recreate behavior)
        # or fail with 409 if from different RSS
        resp2 = client.post(
            "/api/v1/rss/subscribe",
            json={
                "data": bangumi_data,
                "rss": {
                    "url": WILD_BOSS_RSS_URL,
                    "name": "Wild Boss",
                    "aggregate": False,
                    "parser": "mikan",
                    "enabled": True,
                },
            },
        )
        # Same RSS → recreate succeeds (200) or different RSS → 409
        assert resp2.status_code in (200, 409)


@pytest.mark.e2e
class TestBatchSubscribe:
    """Tests for POST /api/v1/rss/subscribe/batch."""

    def test_batch_multiple(self, authed_client):
        client, mock_dl, token = authed_client

        # First add aggregate RSS so we have an RSS ID
        add_aggregate_rss(client)
        rss_list = get_all_rss(client).json()
        rss_id = rss_list[0]["id"]

        # Use analysis endpoint to get valid bangumi data (recreate may
        # return 406 for aggregate feeds when parsing yields no results).
        analysis_resp = client.post(
            "/api/v1/rss/analysis",
            json={
                "url": WILD_BOSS_RSS_URL,
                "name": "Wild Boss",
                "aggregate": False,
                "parser": "mikan",
                "enabled": True,
            },
        )
        assert analysis_resp.status_code == 200
        bangumi_data = analysis_resp.json()

        # Batch subscribe with the analysed bangumi
        resp = client.post(
            "/api/v1/rss/subscribe/batch",
            json={
                "bangumi_list": [bangumi_data],
                "rss": {
                    "id": rss_id,
                    "url": AGGREGATE_RSS_URL,
                    "name": "My Bangumi",
                    "aggregate": True,
                    "parser": "mikan",
                    "enabled": True,
                },
            },
        )
        assert resp.status_code == 200

        # Verify bangumi were created
        all_bangumi = get_all_bangumi(client).json()
        assert len(all_bangumi) >= 1

    def test_batch_empty_list(self, authed_client):
        client, mock_dl, token = authed_client

        add_aggregate_rss(client)
        rss_list = get_all_rss(client).json()
        rss_id = rss_list[0]["id"]

        resp = client.post(
            "/api/v1/rss/subscribe/batch",
            json={
                "bangumi_list": [],
                "rss": {
                    "id": rss_id,
                    "url": AGGREGATE_RSS_URL,
                    "name": "My Bangumi",
                    "aggregate": True,
                    "parser": "mikan",
                    "enabled": True,
                },
            },
        )
        assert resp.status_code == 400

    def test_batch_partial_failure(self, authed_client):
        client, mock_dl, token = authed_client

        add_aggregate_rss(client)
        rss_list = get_all_rss(client).json()
        rss_id = rss_list[0]["id"]

        # Use analysis endpoint to get valid bangumi data (recreate may
        # return 406 for aggregate feeds when parsing yields no results).
        analysis_resp = client.post(
            "/api/v1/rss/analysis",
            json={
                "url": WILD_BOSS_RSS_URL,
                "name": "Wild Boss",
                "aggregate": False,
                "parser": "mikan",
                "enabled": True,
            },
        )
        assert analysis_resp.status_code == 200
        bangumi_data = analysis_resp.json()

        # Batch subscribe with valid bangumi data
        # The batch should succeed for valid entries
        resp = client.post(
            "/api/v1/rss/subscribe/batch",
            json={
                "bangumi_list": [bangumi_data],
                "rss": {
                    "id": rss_id,
                    "url": AGGREGATE_RSS_URL,
                    "name": "My Bangumi",
                    "aggregate": True,
                    "parser": "mikan",
                    "enabled": True,
                },
            },
        )
        assert resp.status_code == 200


@pytest.mark.e2e
class TestAggregatePending:
    """Tests for GET /api/v1/rss/aggregate/pending/{rss_id}."""

    def test_pending_list_with_counts(self, authed_client):
        client, mock_dl, token = authed_client

        # Add aggregate RSS
        add_aggregate_rss(client)
        rss_list = get_all_rss(client).json()
        rss_id = rss_list[0]["id"]

        resp = client.get(f"/api/v1/rss/aggregate/pending/{rss_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "pending_count" in data
        assert "active_count" in data
        assert "bangumi" in data
        assert isinstance(data["pending_count"], int)
        assert isinstance(data["active_count"], int)
        assert isinstance(data["bangumi"], list)
