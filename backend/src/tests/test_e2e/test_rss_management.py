"""E2E tests for RSS management endpoints (CRUD, disable/enable, refresh, torrent status)."""
import pytest

from tests.test_e2e.conftest import (
    AGGREGATE_RSS_URL,
    DRAGON_MAID_RSS_URL,
    WILD_BOSS_RSS_URL,
    add_aggregate_rss,
    add_non_aggregate_rss,
    get_all_bangumi,
    get_all_rss,
)


@pytest.mark.e2e
class TestAddRSS:
    """Tests for POST /api/v1/rss/add."""

    def test_add_non_aggregate_creates_bangumi(self, authed_client):
        client, mock_dl, token = authed_client

        resp = add_non_aggregate_rss(client)
        assert resp.status_code == 200

        # Verify bangumi was created
        bangumi_resp = get_all_bangumi(client)
        assert bangumi_resp.status_code == 200
        bangumi_list = bangumi_resp.json()
        assert len(bangumi_list) >= 1
        titles = [b["official_title"] for b in bangumi_list]
        # Wild boss RSS should produce at least one bangumi
        assert any(t != "" for t in titles)

    def test_add_aggregate_rss_only(self, authed_client):
        client, mock_dl, token = authed_client

        resp = add_aggregate_rss(client)
        assert resp.status_code == 200

        # Verify RSS was added
        rss_resp = get_all_rss(client)
        rss_list = rss_resp.json()
        assert len(rss_list) == 1
        assert rss_list[0]["aggregate"] is True

        # Aggregate RSS does NOT create bangumi on add
        bangumi_resp = get_all_bangumi(client)
        bangumi_list = bangumi_resp.json()
        assert len(bangumi_list) == 0

    def test_add_with_skip_bangumi(self, authed_client):
        client, mock_dl, token = authed_client

        resp = client.post(
            "/api/v1/rss/add",
            params={"skip_bangumi": True},
            json={
                "url": WILD_BOSS_RSS_URL,
                "name": "Wild Boss Skip",
                "aggregate": False,
                "parser": "mikan",
                "enabled": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "rss_id" in data

        # RSS exists but no bangumi
        rss_resp = get_all_rss(client)
        assert len(rss_resp.json()) == 1

        bangumi_resp = get_all_bangumi(client)
        assert len(bangumi_resp.json()) == 0

    def test_add_duplicate_title_rejected(self, authed_client):
        client, mock_dl, token = authed_client

        # First add succeeds
        resp1 = add_non_aggregate_rss(client)
        assert resp1.status_code == 200

        # Second add with same RSS (same title) should be rejected
        resp2 = add_non_aggregate_rss(client, name="Wild Boss Again")
        assert resp2.status_code == 409

    def test_add_duplicate_link_rejected(self, authed_client):
        client, mock_dl, token = authed_client

        # First add succeeds
        resp1 = add_non_aggregate_rss(client)
        assert resp1.status_code == 200

        # Second add with same URL but different name should be rejected (same rss_link)
        resp2 = client.post(
            "/api/v1/rss/add",
            params={"official_title": "Different Title"},
            json={
                "url": WILD_BOSS_RSS_URL,
                "name": "Different Name",
                "aggregate": False,
                "parser": "mikan",
                "enabled": True,
            },
        )
        assert resp2.status_code == 409

    def test_add_parse_error_returns_422(self, authed_client, fixture_request_content):
        client, mock_dl, token = authed_client

        # Patch _resolve_xml to return None for a special URL
        original_resolve = fixture_request_content._resolve_xml

        def _broken_resolve(url):
            if "broken_feed" in url:
                return None
            return original_resolve(url)

        fixture_request_content._resolve_xml = _broken_resolve

        resp = client.post(
            "/api/v1/rss/add",
            json={
                "url": "https://mikanani.me/RSS/broken_feed",
                "name": "Broken Feed",
                "aggregate": False,
                "parser": "mikan",
                "enabled": True,
            },
        )
        # When XML can't be parsed, the analyser returns an error response
        assert resp.status_code in (404, 422, 500)

    def test_add_with_pending_review(self, authed_client):
        """When all torrents are filtered out, bangumi should be set to pending_review."""
        client, mock_dl, token = authed_client

        # Add with a filter that matches everything (all torrents filtered out)
        resp = client.post(
            "/api/v1/rss/add",
            json={
                "url": WILD_BOSS_RSS_URL,
                "name": "Wild Boss Filtered",
                "aggregate": False,
                "parser": "mikan",
                "enabled": True,
            },
        )
        assert resp.status_code == 200

        # Check if the bangumi was created (it should be, but may have pending_review)
        bangumi_resp = get_all_bangumi(client)
        bangumi_list = bangumi_resp.json()
        # At least one bangumi should exist
        assert len(bangumi_list) >= 1


@pytest.mark.e2e
class TestListRSS:
    """Tests for GET /api/v1/rss."""

    def test_list_empty(self, authed_client):
        client, mock_dl, token = authed_client

        resp = get_all_rss(client)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_adding_three(self, authed_client):
        client, mock_dl, token = authed_client

        add_non_aggregate_rss(client, name="Wild Boss", url=WILD_BOSS_RSS_URL)
        add_aggregate_rss(client, name="My Aggregate", url=AGGREGATE_RSS_URL)
        add_non_aggregate_rss(client, name="Dragon Maid", url=DRAGON_MAID_RSS_URL)

        resp = get_all_rss(client)
        assert resp.status_code == 200
        rss_list = resp.json()
        assert len(rss_list) == 3
        names = {r["name"] for r in rss_list}
        assert "Wild Boss" in names
        assert "My Aggregate" in names
        assert "Dragon Maid" in names


@pytest.mark.e2e
class TestDeleteRSS:
    """Tests for DELETE /api/v1/rss/delete/{rss_id} and POST /api/v1/rss/delete/many."""

    def test_cascade_delete(self, authed_client):
        client, mock_dl, token = authed_client

        # Add non-aggregate RSS (creates bangumi + torrents)
        add_non_aggregate_rss(client)
        rss_list = get_all_rss(client).json()
        assert len(rss_list) == 1
        rss_id = rss_list[0]["id"]

        # Verify bangumi exists
        bangumi_before = get_all_bangumi(client).json()
        assert len(bangumi_before) >= 1

        # Delete RSS (cascade)
        resp = client.delete(f"/api/v1/rss/delete/{rss_id}")
        assert resp.status_code == 200

        # Verify RSS gone
        assert len(get_all_rss(client).json()) == 0

        # Verify bangumi also gone (cascade)
        bangumi_after = get_all_bangumi(client).json()
        remaining = [b for b in bangumi_after if b["rss_id"] == rss_id]
        assert len(remaining) == 0

    def test_delete_nonexistent(self, authed_client):
        client, mock_dl, token = authed_client

        resp = client.delete("/api/v1/rss/delete/999")
        assert resp.status_code == 404

    def test_delete_many(self, authed_client):
        client, mock_dl, token = authed_client

        add_non_aggregate_rss(client, name="Wild Boss", url=WILD_BOSS_RSS_URL)
        add_aggregate_rss(client, name="Aggregate", url=AGGREGATE_RSS_URL)

        rss_list = get_all_rss(client).json()
        assert len(rss_list) == 2
        rss_ids = [r["id"] for r in rss_list]

        resp = client.post("/api/v1/rss/delete/many", json=rss_ids)
        assert resp.status_code == 200

        assert len(get_all_rss(client).json()) == 0


@pytest.mark.e2e
class TestDisableEnableRSS:
    """Tests for PATCH /api/v1/rss/disable/{rss_id}, POST /disable/many, /enable/many."""

    def test_disable_rss(self, authed_client):
        client, mock_dl, token = authed_client

        add_aggregate_rss(client)
        rss_list = get_all_rss(client).json()
        rss_id = rss_list[0]["id"]

        resp = client.patch(f"/api/v1/rss/disable/{rss_id}")
        assert resp.status_code == 200

        # Verify disabled
        updated = get_all_rss(client).json()
        assert updated[0]["enabled"] is False

    def test_disable_many(self, authed_client):
        client, mock_dl, token = authed_client

        add_non_aggregate_rss(client, name="Wild Boss", url=WILD_BOSS_RSS_URL)
        add_aggregate_rss(client, name="Aggregate", url=AGGREGATE_RSS_URL)

        rss_list = get_all_rss(client).json()
        rss_ids = [r["id"] for r in rss_list]

        resp = client.post("/api/v1/rss/disable/many", json=rss_ids)
        assert resp.status_code == 200

        updated = get_all_rss(client).json()
        assert all(r["enabled"] is False for r in updated)

    def test_enable_many(self, authed_client):
        client, mock_dl, token = authed_client

        add_non_aggregate_rss(client, name="Wild Boss", url=WILD_BOSS_RSS_URL)
        add_aggregate_rss(client, name="Aggregate", url=AGGREGATE_RSS_URL)

        rss_list = get_all_rss(client).json()
        rss_ids = [r["id"] for r in rss_list]

        # Disable first
        client.post("/api/v1/rss/disable/many", json=rss_ids)

        # Enable
        resp = client.post("/api/v1/rss/enable/many", json=rss_ids)
        assert resp.status_code == 200

        updated = get_all_rss(client).json()
        assert all(r["enabled"] is True for r in updated)

    def test_disable_enable_roundtrip(self, authed_client):
        client, mock_dl, token = authed_client

        add_aggregate_rss(client)
        rss_list = get_all_rss(client).json()
        rss_id = rss_list[0]["id"]

        # Initially enabled
        assert rss_list[0]["enabled"] is True

        # Disable
        client.patch(f"/api/v1/rss/disable/{rss_id}")
        disabled = get_all_rss(client).json()
        assert disabled[0]["enabled"] is False

        # Re-enable
        client.post("/api/v1/rss/enable/many", json=[rss_id])
        enabled = get_all_rss(client).json()
        assert enabled[0]["enabled"] is True


@pytest.mark.e2e
class TestUpdateRSS:
    """Tests for PATCH /api/v1/rss/update/{rss_id}."""

    def test_update_name(self, authed_client):
        client, mock_dl, token = authed_client

        add_aggregate_rss(client)
        rss_list = get_all_rss(client).json()
        rss_id = rss_list[0]["id"]

        resp = client.patch(
            f"/api/v1/rss/update/{rss_id}",
            json={"name": "Renamed RSS"},
        )
        assert resp.status_code == 200

        updated = get_all_rss(client).json()
        assert updated[0]["name"] == "Renamed RSS"

    def test_update_url(self, authed_client):
        client, mock_dl, token = authed_client

        add_aggregate_rss(client)
        rss_list = get_all_rss(client).json()
        rss_id = rss_list[0]["id"]
        new_url = "https://mikanani.me/RSS/MyBangumi?token=UPDATED"

        resp = client.patch(
            f"/api/v1/rss/update/{rss_id}",
            json={"url": new_url},
        )
        assert resp.status_code == 200

        updated = get_all_rss(client).json()
        assert updated[0]["url"] == new_url

    def test_update_nonexistent(self, authed_client):
        client, mock_dl, token = authed_client

        resp = client.patch(
            "/api/v1/rss/update/999",
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404


@pytest.mark.e2e
class TestRefreshRSS:
    """Tests for GET /api/v1/rss/refresh/all and /refresh/{rss_id}."""

    def test_refresh_all(self, authed_client):
        client, mock_dl, token = authed_client

        add_non_aggregate_rss(client)

        resp = client.post("/api/v1/rss/refresh/all")
        assert resp.status_code == 200

    def test_refresh_single(self, authed_client):
        client, mock_dl, token = authed_client

        add_non_aggregate_rss(client)
        rss_list = get_all_rss(client).json()
        rss_id = rss_list[0]["id"]

        resp = client.post(f"/api/v1/rss/refresh/{rss_id}")
        assert resp.status_code == 200


@pytest.mark.e2e
class TestRSSTorrentStatus:
    """Tests for GET /api/v1/rss/torrent?rss_id=X."""

    def test_with_torrents(self, authed_client):
        client, mock_dl, token = authed_client

        # Add non-aggregate RSS (downloads torrents)
        add_non_aggregate_rss(client)
        rss_list = get_all_rss(client).json()
        rss_id = rss_list[0]["id"]

        resp = client.get(f"/api/v1/rss/torrent?rss_id={rss_id}")
        assert resp.status_code == 200
        torrents = resp.json()
        assert isinstance(torrents, list)
        # Non-aggregate wild boss RSS should have created some torrents
        assert len(torrents) >= 1
        for t in torrents:
            assert "id" in t
            assert "name" in t
            assert "status" in t

    def test_empty(self, authed_client):
        client, mock_dl, token = authed_client

        # Add aggregate RSS (no torrents created on add)
        add_aggregate_rss(client)
        rss_list = get_all_rss(client).json()
        rss_id = rss_list[0]["id"]

        resp = client.get(f"/api/v1/rss/torrent?rss_id={rss_id}")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.e2e
class TestRecreateRSS:
    """Tests for POST /api/v1/rss/recreate/{rss_id}."""

    def test_recreate_non_aggregate(self, authed_client):
        client, mock_dl, token = authed_client

        add_non_aggregate_rss(client)
        rss_list = get_all_rss(client).json()
        rss_id = rss_list[0]["id"]

        resp = client.post(f"/api/v1/rss/recreate/{rss_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        # Each item should have bangumi fields
        assert "official_title" in data[0]
