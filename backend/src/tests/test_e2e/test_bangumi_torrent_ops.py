"""E2E tests for bangumi torrent operations."""

import pytest

from tests.test_e2e.conftest import (
    add_non_aggregate_rss,
    get_all_bangumi,
)


# ---------------------------------------------------------------------------
# TORRENT STATUS
# ---------------------------------------------------------------------------
@pytest.mark.e2e
class TestTorrentStatus:
    """Tests for GET /bangumi/torrent/{id}."""

    def test_with_online_match(self, authed_client):
        """Torrents in DB report status based on downloader state."""
        client, mock_dl, token = authed_client
        add_non_aggregate_rss(client)

        bangumis = get_all_bangumi(client).json()
        assert len(bangumis) >= 1
        bangumi_id = bangumis[0]["id"]

        resp = client.get(f"/api/v1/bangumi/torrent/{bangumi_id}")
        assert resp.status_code == 200
        statuses = resp.json()

        if statuses:
            for s in statuses:
                assert s["status"] == "missing"
                assert s["progress"] == 0

    def test_missing_in_downloader(self, authed_client):
        """Torrents in DB but not in downloader show status='missing'."""
        client, mock_dl, token = authed_client
        add_non_aggregate_rss(client)

        bangumis = get_all_bangumi(client).json()
        bangumi_id = bangumis[0]["id"]

        # Make sure downloader returns no matching torrents
        mock_dl.torrents_info.return_value = []

        resp = client.get(f"/api/v1/bangumi/torrent/{bangumi_id}")
        assert resp.status_code == 200
        statuses = resp.json()
        for s in statuses:
            assert s["status"] == "missing"

    def test_empty(self, authed_client):
        """No torrents for a bangumi returns empty list."""
        client, mock_dl, token = authed_client

        # Create bangumi but don't download any torrents
        # Use a fresh bangumi with no torrent records
        resp = client.get("/api/v1/bangumi/torrent/99999")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# RE-DOWNLOAD
# ---------------------------------------------------------------------------
@pytest.mark.e2e
class TestReDownload:
    """Tests for POST /bangumi/torrent/download?torrent_id=X."""

    def test_success(self, authed_client):
        """Re-download a torrent that exists in DB succeeds with mock downloader."""
        client, mock_dl, token = authed_client
        add_non_aggregate_rss(client)

        bangumis = get_all_bangumi(client).json()
        bangumi_id = bangumis[0]["id"]

        statuses = client.get(f"/api/v1/bangumi/torrent/{bangumi_id}").json()

        if statuses:
            torrent_id = statuses[0]["id"]

            resp = client.post(f"/api/v1/bangumi/torrent/download?torrent_id={torrent_id}")
            assert resp.status_code == 200
            mock_dl.add_torrents.assert_called()
        else:
            pytest.skip("No torrent records created by RSS")

    def test_torrent_not_found(self, authed_client):
        """torrent_id=999 returns 404."""
        client, mock_dl, token = authed_client
        resp = client.post("/api/v1/bangumi/torrent/download?torrent_id=999")
        assert resp.status_code == 404

    def test_no_bangumi_match(self, authed_client):
        """Torrent record cascade-deleted with bangumi returns 404."""
        client, mock_dl, token = authed_client
        add_non_aggregate_rss(client)

        bangumis = get_all_bangumi(client).json()
        bangumi_id = bangumis[0]["id"]

        statuses = client.get(f"/api/v1/bangumi/torrent/{bangumi_id}").json()

        if statuses:
            torrent_id = statuses[0]["id"]

            client.delete("/api/v1/bangumi/reset/all")

            resp = client.post(f"/api/v1/bangumi/torrent/download?torrent_id={torrent_id}")
            assert resp.status_code == 404
        else:
            pytest.skip("No torrent records created by RSS")

    def test_issue10_path_drift(self, authed_client):
        """Re-download after title change uses updated save_path."""
        client, mock_dl, token = authed_client
        add_non_aggregate_rss(client)

        bangumis = get_all_bangumi(client).json()
        bangumi_id = bangumis[0]["id"]

        original = client.get(f"/api/v1/bangumi/get/{bangumi_id}").json()
        original_save_path = original.get("save_path")

        statuses = client.get(f"/api/v1/bangumi/torrent/{bangumi_id}").json()

        if not statuses:
            pytest.skip("No torrent records created by RSS")
            return

        torrent_id = statuses[0]["id"]

        payload = {
            "rss_id": original.get("rss_id"),
            "official_title": "Path Drift Test Title",
            "year": original.get("year"),
            "title_raw": original["title_raw"],
            "season": original["season"],
            "season_raw": original.get("season_raw"),
            "group_name": original.get("group_name", "Unknown"),
            "dpi": original.get("dpi"),
            "source": original.get("source"),
            "subtitle": original.get("subtitle"),
            "eps_collect": original.get("eps_collect", False),
            "offset": original.get("offset", 0),
            "filter": original.get("filter", ""),
            "rss_link": original.get("rss_link", ""),
            "poster_link": original.get("poster_link"),
            "added": original.get("added", False),
            "rule_name": original.get("rule_name"),
            "save_path": original.get("save_path"),
            "deleted": original.get("deleted", False),
        }
        client.patch(f"/api/v1/bangumi/update/{bangumi_id}", json=payload)

        updated = client.get(f"/api/v1/bangumi/get/{bangumi_id}").json()
        new_save_path = updated.get("save_path")
        assert new_save_path != original_save_path, (
            "save_path should change after title update"
        )

        resp = client.post(f"/api/v1/bangumi/torrent/download?torrent_id={torrent_id}")
        assert resp.status_code == 200
        mock_dl.add_torrents.assert_called()
        assert "Path Drift Test Title" in mock_dl.add_torrents.call_args.kwargs["save_path"]


# ---------------------------------------------------------------------------
# REFRESH POSTER BY ID
# ---------------------------------------------------------------------------
@pytest.mark.e2e
class TestRefreshPosterById:
    """Tests for GET /bangumi/refresh/poster/{id}."""

    def test_single_poster_refresh(self, authed_client):
        """GET /bangumi/refresh/poster/{id} succeeds."""
        client, mock_dl, token = authed_client
        add_non_aggregate_rss(client)

        bangumi_id = get_all_bangumi(client).json()[0]["id"]

        resp = client.post(f"/api/v1/bangumi/refresh/poster/{bangumi_id}")
        assert resp.status_code == 200
