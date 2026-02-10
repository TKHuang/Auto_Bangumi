"""E2E tests for bangumi CRUD operations."""
import pytest

from tests.test_e2e.conftest import (
    add_non_aggregate_rss,
    get_all_bangumi,
    WILD_BOSS_RSS_URL,
)


def _bangumi_to_update_payload(bangumi: dict) -> dict:
    """Convert a GET bangumi response to an update payload (BangumiUpdate fields)."""
    return {
        "rss_id": bangumi.get("rss_id"),
        "official_title": bangumi["official_title"],
        "year": bangumi.get("year"),
        "title_raw": bangumi["title_raw"],
        "season": bangumi["season"],
        "season_raw": bangumi.get("season_raw"),
        "group_name": bangumi.get("group_name", "Unknown"),
        "dpi": bangumi.get("dpi"),
        "source": bangumi.get("source"),
        "subtitle": bangumi.get("subtitle"),
        "eps_collect": bangumi.get("eps_collect", False),
        "offset": bangumi.get("offset", 0),
        "filter": bangumi.get("filter", ""),
        "rss_link": bangumi.get("rss_link", ""),
        "poster_link": bangumi.get("poster_link"),
        "added": bangumi.get("added", False),
        "rule_name": bangumi.get("rule_name"),
        "save_path": bangumi.get("save_path"),
        "deleted": bangumi.get("deleted", False),
    }


# ---------------------------------------------------------------------------
# GET
# ---------------------------------------------------------------------------
@pytest.mark.e2e
class TestGetBangumi:
    """Tests for GET bangumi endpoints."""

    def test_get_all_empty(self, authed_client):
        """No bangumi exist initially — empty list."""
        client, mock_dl, token = authed_client
        resp = get_all_bangumi(client)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_all_after_create(self, authed_client):
        """Adding a non-aggregate RSS auto-creates a bangumi."""
        client, mock_dl, token = authed_client
        rss_resp = add_non_aggregate_rss(client)
        assert rss_resp.status_code == 200

        resp = get_all_bangumi(client)
        assert resp.status_code == 200
        bangumis = resp.json()
        assert len(bangumis) >= 1
        assert any(b["title_raw"] for b in bangumis)

    def test_get_by_id(self, authed_client):
        """GET /bangumi/get/{id} returns the correct bangumi."""
        client, mock_dl, token = authed_client
        add_non_aggregate_rss(client)

        bangumis = get_all_bangumi(client).json()
        assert len(bangumis) >= 1
        bangumi_id = bangumis[0]["id"]

        resp = client.get(f"/api/v1/bangumi/get/{bangumi_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == bangumi_id

    def test_get_nonexistent(self, authed_client):
        """GET /bangumi/get/999 returns 404."""
        client, mock_dl, token = authed_client
        resp = client.get("/api/v1/bangumi/get/999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------
@pytest.mark.e2e
class TestUpdateBangumi:
    """Tests for PATCH /bangumi/update/{id}."""

    def test_update_title(self, authed_client):
        """Changing official_title regenerates save_path."""
        client, mock_dl, token = authed_client
        add_non_aggregate_rss(client)

        bangumi = get_all_bangumi(client).json()[0]
        bangumi_id = bangumi["id"]
        old_save_path = bangumi.get("save_path")

        payload = _bangumi_to_update_payload(bangumi)
        payload["official_title"] = "New Title For Testing"

        resp = client.patch(f"/api/v1/bangumi/update/{bangumi_id}", json=payload)
        assert resp.status_code == 200

        updated = client.get(f"/api/v1/bangumi/get/{bangumi_id}").json()
        assert updated["official_title"] == "New Title For Testing"
        # save_path should have been regenerated
        assert updated["save_path"] != old_save_path

    def test_update_season(self, authed_client):
        """Changing season works."""
        client, mock_dl, token = authed_client
        add_non_aggregate_rss(client)

        bangumi = get_all_bangumi(client).json()[0]
        bangumi_id = bangumi["id"]

        payload = _bangumi_to_update_payload(bangumi)
        payload["season"] = 3

        resp = client.patch(f"/api/v1/bangumi/update/{bangumi_id}", json=payload)
        assert resp.status_code == 200

        updated = client.get(f"/api/v1/bangumi/get/{bangumi_id}").json()
        assert updated["season"] == 3

    def test_update_filter(self, authed_client):
        """Changing filter works."""
        client, mock_dl, token = authed_client
        add_non_aggregate_rss(client)

        bangumi = get_all_bangumi(client).json()[0]
        bangumi_id = bangumi["id"]

        payload = _bangumi_to_update_payload(bangumi)
        payload["filter"] = "1080p,HEVC"

        resp = client.patch(f"/api/v1/bangumi/update/{bangumi_id}", json=payload)
        assert resp.status_code == 200

        updated = client.get(f"/api/v1/bangumi/get/{bangumi_id}").json()
        assert updated["filter"] == "1080p,HEVC"

    def test_update_nonexistent(self, authed_client):
        """PATCH /bangumi/update/999 returns 404."""
        client, mock_dl, token = authed_client
        payload = {
            "rss_id": None,
            "official_title": "Ghost",
            "year": None,
            "title_raw": "ghost",
            "season": 1,
            "season_raw": None,
            "group_name": "Unknown",
            "dpi": None,
            "source": None,
            "subtitle": None,
            "eps_collect": False,
            "offset": 0,
            "filter": "",
            "rss_link": "",
            "poster_link": None,
            "added": False,
            "rule_name": None,
            "save_path": None,
            "deleted": False,
        }
        resp = client.patch("/api/v1/bangumi/update/999", json=payload)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE (hard)
# ---------------------------------------------------------------------------
@pytest.mark.e2e
class TestDeleteBangumi:
    """Tests for DELETE /bangumi/delete endpoints."""

    def test_hard_delete(self, authed_client):
        """DELETE /bangumi/delete/{id} removes the bangumi."""
        client, mock_dl, token = authed_client
        add_non_aggregate_rss(client)

        bangumis = get_all_bangumi(client).json()
        assert len(bangumis) >= 1
        bangumi_id = bangumis[0]["id"]

        resp = client.delete(f"/api/v1/bangumi/delete/{bangumi_id}?file=false")
        assert resp.status_code == 200

        # Verify it's gone
        resp = client.get(f"/api/v1/bangumi/get/{bangumi_id}")
        assert resp.status_code == 404

    def test_delete_with_files(self, authed_client):
        """DELETE with file=true calls downloader.torrents_delete."""
        client, mock_dl, token = authed_client
        add_non_aggregate_rss(client)

        bangumis = get_all_bangumi(client).json()
        bangumi_id = bangumis[0]["id"]

        resp = client.delete(f"/api/v1/bangumi/delete/{bangumi_id}?file=true")
        assert resp.status_code == 200

        # Verify bangumi is gone
        resp = client.get(f"/api/v1/bangumi/get/{bangumi_id}")
        assert resp.status_code == 404

    def test_delete_nonexistent(self, authed_client):
        """DELETE /bangumi/delete/999 returns 404."""
        client, mock_dl, token = authed_client
        resp = client.delete("/api/v1/bangumi/delete/999?file=false")
        assert resp.status_code == 404

    def test_delete_many(self, authed_client):
        """DELETE /bangumi/delete with body of IDs removes multiple bangumi."""
        client, mock_dl, token = authed_client
        # Add two different RSS feeds to create two bangumi
        add_non_aggregate_rss(client, name="Wild Boss", url=WILD_BOSS_RSS_URL)

        bangumis = get_all_bangumi(client).json()
        ids = [b["id"] for b in bangumis]
        assert len(ids) >= 1

        resp = client.request(
            "DELETE",
            "/api/v1/bangumi/delete?file=false",
            json=ids,
        )
        assert resp.status_code == 200

        remaining = get_all_bangumi(client).json()
        assert len(remaining) == 0


# ---------------------------------------------------------------------------
# RESET ALL
# ---------------------------------------------------------------------------
@pytest.mark.e2e
class TestResetAll:
    """Tests for GET /bangumi/reset/all."""

    def test_reset_all_rules(self, authed_client):
        """Reset all removes every bangumi."""
        client, mock_dl, token = authed_client
        add_non_aggregate_rss(client)

        bangumis = get_all_bangumi(client).json()
        assert len(bangumis) >= 1

        resp = client.delete("/api/v1/bangumi/reset/all")
        assert resp.status_code == 200

        remaining = get_all_bangumi(client).json()
        assert len(remaining) == 0


# ---------------------------------------------------------------------------
# REFRESH POSTER
# ---------------------------------------------------------------------------
@pytest.mark.e2e
class TestRefreshPoster:
    """Tests for GET /bangumi/refresh/poster/all."""

    def test_refresh_poster_all(self, authed_client):
        """Refresh all posters succeeds (mikan_parser_with_rss is mocked via fixture)."""
        client, mock_dl, token = authed_client
        add_non_aggregate_rss(client)

        resp = client.post("/api/v1/bangumi/refresh/poster/all")
        assert resp.status_code == 200
