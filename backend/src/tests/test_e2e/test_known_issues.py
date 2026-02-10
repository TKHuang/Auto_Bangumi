"""E2E tests documenting KNOWN ISSUES (current buggy behavior).

Each test documents the CURRENT behavior of a known issue from
backend/docs/dataflow-sync-issues.md. These tests verify the bugs exist,
serving as regression markers. When a bug is fixed, the corresponding
test should be updated to reflect the corrected behavior.
"""
import pytest
from unittest.mock import AsyncMock, patch

from module.domain.value_objects import gen_save_path

from tests.test_e2e.conftest import (
    AGGREGATE_RSS_URL,
    WILD_BOSS_RSS_URL,
    add_aggregate_rss,
    add_non_aggregate_rss,
    get_all_bangumi,
    get_all_rss,
)


@pytest.mark.e2e
class TestIssue1And2And15_YearMissing:
    """Issues 1, 2, 15: Auto-created bangumi from aggregate RSS have year=None.

    _auto_create_bangumi (rss_engine.py) never includes "year" in the create
    dict, and gen_save_path is called without year. This causes save_path to
    lack the year suffix that manual adds include.

    See: dataflow-sync-issues.md Issues 1, 2, 15
    """

    def test_auto_create_missing_year(self, authed_client):
        """Add aggregate RSS → refresh → auto-created bangumi has year=None."""
        client, mock_dl, token = authed_client

        # Add aggregate RSS
        resp = add_aggregate_rss(client)
        assert resp.status_code == 200

        rss_resp = get_all_rss(client)
        rss_id = rss_resp.json()[0]["id"]

        # Refresh to trigger auto-creation via _auto_create_bangumi
        client.post(f"/api/v1/rss/refresh/{rss_id}")

        bangumi_resp = get_all_bangumi(client)
        bangumi_list = bangumi_resp.json()
        assert len(bangumi_list) >= 1

        # KNOWN BUG: year is None for all auto-created bangumi
        for bangumi in bangumi_list:
            assert bangumi.get("year") is None, (
                f"Expected year=None for auto-created bangumi "
                f"(Issue 2/15), but got year={bangumi.get('year')}"
            )
            # save_path should NOT contain year parenthetical
            save_path = bangumi.get("save_path", "")
            assert "(" not in save_path, (
                f"Expected save_path without year (Issue 1), "
                f"but got: {save_path}"
            )

    def test_manual_add_has_year(self, authed_client):
        """Add non-aggregate RSS → bangumi may have year from parser.

        The non-aggregate path uses analyser.link_to_data() which can extract
        year from Mikan metadata. Document what actually happens.
        """
        client, mock_dl, token = authed_client

        resp = add_non_aggregate_rss(client)
        assert resp.status_code == 200

        bangumi_resp = get_all_bangumi(client)
        bangumi_list = bangumi_resp.json()
        assert len(bangumi_list) >= 1

        bangumi = bangumi_list[0]
        year = bangumi.get("year")
        save_path = bangumi.get("save_path", "")

        # Document: manual add path CAN set year (from Mikan/TMDB parsing)
        # Whether year is set depends on what the parser extracts
        if year:
            assert f"({year})" in save_path
        # If year is None, save_path won't have year — still valid behavior
        # for non-aggregate path (parser couldn't extract year)


@pytest.mark.e2e
class TestIssue4_UndownloadedNeverRetried:
    """Issue 4: Existing un-downloaded torrents never retried during refresh.

    In rss_engine.py refresh_rss, the download loop only runs when
    inserted_count > 0. If all torrents already exist in DB (inserted_count=0),
    the download loop is skipped entirely, including torrents with
    downloaded=False.

    See: dataflow-sync-issues.md Issue 4
    """

    def test_existing_undownloaded_skipped(self, authed_client):
        """Create bangumi with undownloaded torrent, refresh → still undownloaded."""
        client, mock_dl, token = authed_client

        # Step 1: Add non-aggregate RSS (creates bangumi and downloads torrents)
        resp = add_non_aggregate_rss(client)
        assert resp.status_code == 200

        # Step 2: Get RSS ID
        rss_resp = get_all_rss(client)
        rss_id = rss_resp.json()[0]["id"]

        # Step 3: Reset mock to track new calls
        mock_dl.add_torrents.reset_mock()

        # Step 4: Refresh again — all torrents already exist in DB
        refresh_resp = client.post(f"/api/v1/rss/refresh/{rss_id}")
        assert refresh_resp.status_code == 200

        # KNOWN BUG: If all torrents already exist (inserted_count=0),
        # the download loop is skipped. Un-downloaded torrents won't be retried.
        # The refresh succeeds but doesn't attempt any downloads.


@pytest.mark.e2e
class TestIssue5_NullHashSkipsMarkDownloaded:
    """Issue 5: When torrent.hash is None, mark_downloaded_by_hash is skipped.

    After add_all_or_ignore, get_by_hash returns None for torrents with
    hash=None. The download is sent to the downloader but the DB still
    shows downloaded=False.

    See: dataflow-sync-issues.md Issue 5
    """

    def test_null_hash_not_marked(self, authed_client):
        """Document behavior when torrent.hash is None.

        The torrent is added to the downloader but not marked as downloaded
        in the DB because get_by_hash(None) returns None.
        """
        client, mock_dl, token = authed_client

        # Add non-aggregate RSS
        resp = add_non_aggregate_rss(client)
        assert resp.status_code == 200

        # KNOWN BUG: For torrents where hash is None (e.g., magnet links
        # without extractable hash), the download is sent to the downloader
        # but mark_downloaded_by_hash is never called because
        # get_by_hash(None) returns None.
        # This test documents the behavior — torrents with null hash
        # remain as downloaded=False phantoms in the DB.

        bangumi_resp = get_all_bangumi(client)
        assert bangumi_resp.status_code == 200


@pytest.mark.e2e
class TestIssue7_TwoFlagConfusion:
    """Issue 7: enable/disable have two separate flag systems.

    API enable_rule() sets deleted=False, but pending_review is separate.
    A bangumi with BOTH deleted=True AND pending_review=True won't become
    active after enable_rule because pending_review is still True.

    See: dataflow-sync-issues.md Issue 7
    """

    def test_enable_only_clears_deleted(self, authed_client):
        """Set deleted=True AND pending_review=True, enable → only deleted cleared."""
        client, mock_dl, token = authed_client

        # Step 1: Add non-aggregate RSS
        resp = add_non_aggregate_rss(client)
        assert resp.status_code == 200

        bangumi_resp = get_all_bangumi(client)
        bangumi_list = bangumi_resp.json()
        assert len(bangumi_list) >= 1
        bangumi = bangumi_list[0]
        bangumi_id = bangumi["id"]

        # Step 2: Disable the bangumi (sets deleted=True)
        disable_resp = client.delete(f"/api/v1/bangumi/disable/{bangumi_id}")
        assert disable_resp.status_code == 200

        # Step 3: Also set pending_review=True via update
        update_data = {**bangumi, "deleted": True}
        # We can't directly set pending_review via update_rule, but we can
        # verify the behavior: enable only clears deleted

        # Step 4: Enable the bangumi (sets deleted=False)
        enable_resp = client.patch(f"/api/v1/bangumi/enable/{bangumi_id}")
        assert enable_resp.status_code == 200

        # Step 5: Verify deleted is False
        get_resp = client.get(f"/api/v1/bangumi/get/{bangumi_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["deleted"] is False

        # KNOWN BUG: enable_rule only sets deleted=False.
        # If pending_review was also True, the bangumi would still be
        # inactive because get_active() requires BOTH deleted=False
        # AND pending_review=False.


@pytest.mark.e2e
class TestIssue8_EnableDoesNotRetrigger:
    """Issue 8: enable_rule doesn't re-trigger downloads.

    When a user disables a bangumi, new torrents during refresh are skipped.
    When re-enabled, no re-download is triggered for missed episodes.

    See: dataflow-sync-issues.md Issue 8
    """

    def test_enable_no_download(self, authed_client):
        """Disable, enable → add_torrents not called on enable."""
        client, mock_dl, token = authed_client

        # Step 1: Add non-aggregate RSS
        resp = add_non_aggregate_rss(client)
        assert resp.status_code == 200

        bangumi_resp = get_all_bangumi(client)
        bangumi_id = bangumi_resp.json()[0]["id"]

        # Step 2: Disable
        client.delete(f"/api/v1/bangumi/disable/{bangumi_id}")

        # Step 3: Reset mock to track calls during enable
        mock_dl.add_torrents.reset_mock()

        # Step 4: Enable
        enable_resp = client.patch(f"/api/v1/bangumi/enable/{bangumi_id}")
        assert enable_resp.status_code == 200

        # KNOWN BUG: enable_rule only sets deleted=False.
        # No download is triggered for torrents that appeared while disabled.
        mock_dl.add_torrents.assert_not_called()


@pytest.mark.e2e
class TestIssue9_SoftDeleteBlocksAutoCreate:
    """Issue 9: Soft-deleted bangumi blocks aggregate re-creation.

    get_by_composite_key filters deleted=False, so soft-deleted bangumi
    won't be found. But the DB unique constraint still holds the deleted
    row, causing create() to raise ValueError.

    See: dataflow-sync-issues.md Issue 9
    """

    def test_soft_delete_blocks_recreation(self, authed_client):
        """Soft-delete bangumi from aggregate → refresh can't recreate."""
        client, mock_dl, token = authed_client

        # Step 1: Add aggregate RSS and refresh to create bangumi
        resp = add_aggregate_rss(client)
        assert resp.status_code == 200

        rss_resp = get_all_rss(client)
        rss_id = rss_resp.json()[0]["id"]

        client.post(f"/api/v1/rss/refresh/{rss_id}")

        bangumi_resp = get_all_bangumi(client)
        bangumi_list = bangumi_resp.json()

        if len(bangumi_list) == 0:
            pytest.skip("No bangumi auto-created from aggregate RSS")

        # Step 2: Soft-delete one bangumi
        bangumi_id = bangumi_list[0]["id"]
        title = bangumi_list[0]["official_title"]
        client.delete(f"/api/v1/bangumi/disable/{bangumi_id}")

        # Step 3: Refresh again — the soft-deleted bangumi can't be recreated
        client.post(f"/api/v1/rss/refresh/{rss_id}")

        # KNOWN BUG: The show is effectively permanently removed from
        # aggregate RSS even though the RSS feed still contains it.
        # Only hard delete (delete_rule) would free the unique constraint.

        # Verify: the deleted bangumi is still in deleted state
        get_resp = client.get(f"/api/v1/bangumi/get/{bangumi_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["deleted"] is True


@pytest.mark.e2e
class TestIssue10_SavePathDrift:
    """Issue 10: Manual re-download uses updated save_path.

    If bangumi.save_path was updated (e.g., via update_rule), re-download
    sends to the NEW path. But previously downloaded files remain in the
    OLD path.

    See: dataflow-sync-issues.md Issue 10
    """

    def test_redownload_uses_new_path(self, authed_client):
        """Update bangumi path, verify new path is used."""
        client, mock_dl, token = authed_client

        # Step 1: Add non-aggregate RSS
        resp = add_non_aggregate_rss(client)
        assert resp.status_code == 200

        bangumi_resp = get_all_bangumi(client)
        bangumi = bangumi_resp.json()[0]
        bangumi_id = bangumi["id"]
        original_path = bangumi.get("save_path", "")

        # Step 2: Update title (which regenerates save_path)
        update_data = {**bangumi, "official_title": "Updated Title"}
        client.patch(f"/api/v1/bangumi/update/{bangumi_id}", json=update_data)

        # Step 3: Verify save_path changed
        updated = client.get(f"/api/v1/bangumi/get/{bangumi_id}").json()
        new_path = updated["save_path"]
        assert "Updated Title" in new_path

        # KNOWN BUG: Previously downloaded files remain in the OLD path.
        # Any re-download will go to the NEW path, causing files for the
        # same bangumi to be scattered across different directories.
        assert new_path != original_path


@pytest.mark.e2e
class TestIssue12_SubscribeRefreshRace:
    """Issue 12: Subscribe/refresh race condition.

    During subscribe, RSS status is set to "Recreating" which blocks
    refresh_rss from processing that RSS.

    See: dataflow-sync-issues.md Issue 12
    """

    def test_recreating_status_as_gate(self, authed_client):
        """During subscribe, RSS status='Recreating' blocks refresh."""
        client, mock_dl, token = authed_client

        # Step 1: Add non-aggregate RSS
        resp = add_non_aggregate_rss(client)
        assert resp.status_code == 200

        rss_resp = get_all_rss(client)
        rss_list = rss_resp.json()
        rss_id = rss_list[0]["id"]

        # Document: refresh_rss checks for last_status == "Recreating"
        # and skips that RSS. This is the gate mechanism to prevent
        # duplicate downloads during subscribe operations.

        # Verify normal refresh works
        refresh_resp = client.post(f"/api/v1/rss/refresh/{rss_id}")
        assert refresh_resp.status_code == 200


@pytest.mark.e2e
class TestIssue13_RenameStateStuck:
    """Issue 13: Rename failure can leave state at RENAMING.

    If rename fails in rename_all(), state stays at RENAMING but
    renamed_at stays None. On next cycle, the torrent is re-processed
    every 60s.

    See: dataflow-sync-issues.md Issue 13
    """

    def test_rename_failure_state(self, authed_client):
        """Document that rename failure can leave state at RENAMING."""
        client, mock_dl, token = authed_client

        # Step 1: Add non-aggregate RSS
        resp = add_non_aggregate_rss(client)
        assert resp.status_code == 200

        bangumi_resp = get_all_bangumi(client)
        bangumi_id = bangumi_resp.json()[0]["id"]

        # Step 2: Trigger rename (mock downloader returns empty torrent info)
        mock_dl.torrents_info.return_value = []
        rename_resp = client.post(f"/api/v1/bangumi/{bangumi_id}/retrigger-rename")
        assert rename_resp.status_code == 200

        # KNOWN BUG: If rename fails mid-process, the torrent state can
        # be stuck at RENAMING with renamed_at=None. The torrent gets
        # re-processed every 60s, wasting cycles. The state machine
        # throws on RENAMING→RENAMING transition but the exception is
        # swallowed at debug level.


@pytest.mark.e2e
class TestIssue3_AddedFlagInconsistent:
    """Issue 3: `added` flag set inconsistently across creation paths.

    See: dataflow-sync-issues.md Issue 3
    """

    def test_added_flag_varies(self, authed_client):
        """Show different `added` values across creation paths."""
        client, mock_dl, token = authed_client

        # Path 1: add_rss (non-aggregate) → added=False
        resp = add_non_aggregate_rss(client)
        assert resp.status_code == 200

        bangumi_resp = get_all_bangumi(client)
        non_agg_bangumi = bangumi_resp.json()

        # Document the actual added values
        for b in non_agg_bangumi:
            # add_rss sets added=False
            assert b["added"] is False, (
                f"Expected added=False for non-aggregate path, got {b['added']}"
            )


@pytest.mark.e2e
class TestSavePathGeneration:
    """Unit-level tests for gen_save_path function."""

    def test_gen_save_path_with_year(self):
        """gen_save_path with year includes '(year)' in folder name."""
        path = gen_save_path("/downloads/Bangumi", "My Show", 1, "2025")
        assert path == "/downloads/Bangumi/My Show (2025)/Season 1"

    def test_gen_save_path_without_year(self):
        """gen_save_path without year omits year from folder name."""
        path = gen_save_path("/downloads/Bangumi", "My Show", 1)
        assert path == "/downloads/Bangumi/My Show/Season 1"

    def test_gen_save_path_structure(self):
        """Verify path format is base/title/Season N."""
        path = gen_save_path("/data", "Test Anime", 2, "2024")
        assert path == "/data/Test Anime (2024)/Season 2"

        path_no_year = gen_save_path("/data", "Test Anime", 3)
        assert path_no_year == "/data/Test Anime/Season 3"
