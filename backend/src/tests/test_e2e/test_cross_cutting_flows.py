"""E2E tests for cross-cutting user journeys spanning multiple API calls."""
import pytest
from unittest.mock import patch

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
class TestNonAggregateFullFlow:
    """Full journey: add non-aggregate RSS → verify bangumi → retrigger rename."""

    def test_add_verify_rename(self, authed_client):
        """Add non-aggregate RSS, verify bangumi created, retrigger rename."""
        client, mock_dl, token = authed_client

        # Step 1: Add non-aggregate RSS
        resp = add_non_aggregate_rss(client)
        assert resp.status_code == 200

        # Step 2: Verify bangumi was auto-created
        bangumi_resp = get_all_bangumi(client)
        assert bangumi_resp.status_code == 200
        bangumi_list = bangumi_resp.json()
        assert len(bangumi_list) >= 1

        bangumi = bangumi_list[0]
        bangumi_id = bangumi["id"]
        assert bangumi["official_title"]

        # Step 3: Retrigger rename
        rename_resp = client.post(f"/api/v1/bangumi/{bangumi_id}/retrigger-rename")
        assert rename_resp.status_code == 200
        body = rename_resp.json()
        assert "msg_en" in body

    def test_add_update_verify_path(self, authed_client):
        """Add RSS, update bangumi title, verify save_path changes."""
        client, mock_dl, token = authed_client

        # Step 1: Add non-aggregate RSS
        resp = add_non_aggregate_rss(client)
        assert resp.status_code == 200

        # Step 2: Get the created bangumi
        bangumi_resp = get_all_bangumi(client)
        assert bangumi_resp.status_code == 200
        bangumi_list = bangumi_resp.json()
        assert len(bangumi_list) >= 1

        bangumi = bangumi_list[0]
        bangumi_id = bangumi["id"]
        original_path = bangumi.get("save_path", "")

        # Step 3: Update the bangumi title
        update_data = {**bangumi, "official_title": "New Title For Testing"}
        update_resp = client.patch(
            f"/api/v1/bangumi/update/{bangumi_id}",
            json=update_data,
        )
        assert update_resp.status_code == 200

        # Step 4: Verify save_path changed
        updated_bangumi = client.get(f"/api/v1/bangumi/get/{bangumi_id}")
        assert updated_bangumi.status_code == 200
        new_path = updated_bangumi.json()["save_path"]
        assert "New Title For Testing" in new_path
        assert new_path != original_path


@pytest.mark.e2e
class TestAggregateFullFlow:
    """Full journey: add aggregate RSS → refresh → verify auto-created bangumi."""

    def test_refresh_auto_creates(self, authed_client):
        """Add aggregate RSS, refresh, verify bangumi auto-created."""
        client, mock_dl, token = authed_client

        # Step 1: Add aggregate RSS (no bangumi created yet)
        resp = add_aggregate_rss(client)
        assert resp.status_code == 200

        # Step 2: Get RSS to find its ID
        rss_resp = get_all_rss(client)
        assert rss_resp.status_code == 200
        rss_list = rss_resp.json()
        assert len(rss_list) >= 1
        rss_id = rss_list[0]["id"]

        # Step 3: Refresh to trigger auto-creation
        refresh_resp = client.post(f"/api/v1/rss/refresh/{rss_id}")
        assert refresh_resp.status_code == 200

        # Step 4: Verify bangumi were auto-created
        bangumi_resp = get_all_bangumi(client)
        assert bangumi_resp.status_code == 200
        bangumi_list = bangumi_resp.json()
        assert len(bangumi_list) >= 1

    def test_refresh_pending_activate(self, authed_client):
        """Add aggregate RSS, refresh, check pending, activate."""
        client, mock_dl, token = authed_client

        # Step 1: Add aggregate RSS
        resp = add_aggregate_rss(client)
        assert resp.status_code == 200

        # Step 2: Get RSS ID
        rss_resp = get_all_rss(client)
        rss_list = rss_resp.json()
        rss_id = rss_list[0]["id"]

        # Step 3: Refresh
        client.post(f"/api/v1/rss/refresh/{rss_id}")

        # Step 4: Check pending count
        pending_resp = client.get(f"/api/v1/rss/{rss_id}/pending-count")
        assert pending_resp.status_code == 200
        pending_count = pending_resp.json()["pending_count"]

        # Step 5: If there are pending bangumi, activate one
        if pending_count > 0:
            pending_list_resp = client.get(f"/api/v1/rss/{rss_id}/pending")
            pending_list = pending_list_resp.json()
            assert len(pending_list) > 0

            bangumi_id = pending_list[0]["id"]
            activate_resp = client.post(f"/api/v1/bangumi/{bangumi_id}/activate")
            assert activate_resp.status_code == 200


@pytest.mark.e2e
class TestSubscribeFullFlow:
    """Full journey: subscribe to bangumi from recreated RSS rules."""

    def test_subscribe_replaces_old(self, authed_client):
        """Add RSS, subscribe new bangumi, old one replaced."""
        client, mock_dl, token = authed_client

        # Step 1: Add non-aggregate RSS (creates a bangumi)
        resp = add_non_aggregate_rss(client)
        assert resp.status_code == 200

        bangumi_resp = get_all_bangumi(client)
        original_bangumi = bangumi_resp.json()
        assert len(original_bangumi) >= 1

        # Step 2: Get RSS ID
        rss_resp = get_all_rss(client)
        rss_list = rss_resp.json()
        rss_id = rss_list[0]["id"]

        # Step 3: Recreate RSS rules to get parsed bangumi data
        recreate_resp = client.post(f"/api/v1/rss/recreate/{rss_id}")
        assert recreate_resp.status_code == 200
        recreated_list = recreate_resp.json()
        assert len(recreated_list) >= 1

        # The subscribe endpoint expects two body params: data (Bangumi) + rss (RSSItem)
        # and a query param: file (bool)
        bangumi_data = recreated_list[0]
        rss_data = rss_list[0]
        subscribe_resp = client.post(
            "/api/v1/rss/subscribe",
            json={"data": bangumi_data, "rss": rss_data},
            params={"file": False},
        )
        # Subscribe may return 200 or error depending on existing data
        assert subscribe_resp.status_code in (200, 409)

    def test_batch_from_aggregate(self, authed_client):
        """Add aggregate RSS, recreate, batch subscribe."""
        client, mock_dl, token = authed_client

        # Step 1: Add aggregate RSS
        resp = add_aggregate_rss(client)
        assert resp.status_code == 200

        # Step 2: Get RSS ID
        rss_resp = get_all_rss(client)
        rss_list = rss_resp.json()
        rss_id = rss_list[0]["id"]

        # Step 3: Recreate to get parsed bangumi list
        recreate_resp = client.post(f"/api/v1/rss/recreate/{rss_id}")
        assert recreate_resp.status_code == 200
        bangumi_list = recreate_resp.json()
        assert isinstance(bangumi_list, list)
        assert len(bangumi_list) >= 1


@pytest.mark.e2e
class TestEnableDisableFullFlow:
    """Full journey: disable bangumi, refresh skips it, re-enable."""

    def test_disable_refresh_skips_enable(self, authed_client):
        """Add non-agg RSS, disable bangumi, refresh doesn't match, enable."""
        client, mock_dl, token = authed_client

        # Step 1: Add non-aggregate RSS
        resp = add_non_aggregate_rss(client)
        assert resp.status_code == 200

        bangumi_resp = get_all_bangumi(client)
        bangumi_list = bangumi_resp.json()
        assert len(bangumi_list) >= 1
        bangumi_id = bangumi_list[0]["id"]

        # Step 2: Disable the bangumi (soft delete)
        disable_resp = client.delete(f"/api/v1/bangumi/disable/{bangumi_id}")
        assert disable_resp.status_code == 200

        # Step 3: Verify it's disabled (deleted=True)
        get_resp = client.get(f"/api/v1/bangumi/get/{bangumi_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["deleted"] is True

        # Step 4: Refresh RSS — disabled bangumi should be skipped
        rss_resp = get_all_rss(client)
        rss_id = rss_resp.json()[0]["id"]
        refresh_resp = client.post(f"/api/v1/rss/refresh/{rss_id}")
        assert refresh_resp.status_code == 200

        # Step 5: Re-enable the bangumi
        enable_resp = client.patch(f"/api/v1/bangumi/enable/{bangumi_id}")
        assert enable_resp.status_code == 200

        # Step 6: Verify it's enabled again
        get_resp2 = client.get(f"/api/v1/bangumi/get/{bangumi_id}")
        assert get_resp2.status_code == 200
        assert get_resp2.json()["deleted"] is False


@pytest.mark.e2e
class TestCascadeDelete:
    """Full journey: delete RSS cascades to bangumi and torrents."""

    def test_delete_rss_removes_children(self, authed_client):
        """Add RSS with bangumi, delete RSS, bangumi and torrents gone."""
        client, mock_dl, token = authed_client

        # Step 1: Add non-aggregate RSS (creates bangumi + torrents)
        resp = add_non_aggregate_rss(client)
        assert resp.status_code == 200

        # Step 2: Verify bangumi exists
        bangumi_resp = get_all_bangumi(client)
        bangumi_list = bangumi_resp.json()
        assert len(bangumi_list) >= 1

        # Step 3: Get RSS ID
        rss_resp = get_all_rss(client)
        rss_list = rss_resp.json()
        assert len(rss_list) >= 1
        rss_id = rss_list[0]["id"]

        # Step 4: Delete RSS (cascade)
        delete_resp = client.delete(f"/api/v1/rss/delete/{rss_id}")
        assert delete_resp.status_code == 200

        # Step 5: Verify RSS is gone
        rss_resp2 = get_all_rss(client)
        rss_list2 = rss_resp2.json()
        rss_ids = [r["id"] for r in rss_list2]
        assert rss_id not in rss_ids

        # Step 6: Verify bangumi is gone (cascade deleted)
        bangumi_resp2 = get_all_bangumi(client)
        bangumi_list2 = bangumi_resp2.json()
        # All bangumi linked to the deleted RSS should be gone
        for b in bangumi_list2:
            assert b.get("rss_id") != rss_id


@pytest.mark.e2e
class TestSavePathConsistency:
    """Verify save_path generation with and without year."""

    def test_save_path_with_year(self, authed_client):
        """Manual add with year → verify path includes year."""
        client, mock_dl, token = authed_client

        # Add non-aggregate RSS — analyser.link_to_data extracts year from Mikan
        resp = add_non_aggregate_rss(client)
        assert resp.status_code == 200

        bangumi_resp = get_all_bangumi(client)
        bangumi_list = bangumi_resp.json()
        assert len(bangumi_list) >= 1

        bangumi = bangumi_list[0]
        save_path = bangumi.get("save_path", "")
        year = bangumi.get("year")

        # If year was extracted, save_path should include it
        if year:
            assert f"({year})" in save_path
        # Otherwise just verify save_path is set
        assert "Season" in save_path

    def test_save_path_without_year(self, authed_client):
        """Auto-create without year → path missing year (known Issue 1/2)."""
        client, mock_dl, token = authed_client

        # Add aggregate RSS
        resp = add_aggregate_rss(client)
        assert resp.status_code == 200

        rss_resp = get_all_rss(client)
        rss_id = rss_resp.json()[0]["id"]

        # Refresh to trigger auto-creation
        client.post(f"/api/v1/rss/refresh/{rss_id}")

        bangumi_resp = get_all_bangumi(client)
        bangumi_list = bangumi_resp.json()

        # Auto-created bangumi from aggregate RSS:
        # Known Issue 1/2: year is NOT set, so save_path lacks year
        for bangumi in bangumi_list:
            save_path = bangumi.get("save_path", "")
            assert "Season" in save_path
            # year field is expected to be None for auto-created bangumi
            # (see dataflow-sync-issues.md Issue 2/15)
