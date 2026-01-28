"""Unit tests for PikPak folder cycle detection.

Tests the cycle detection mechanism in _list_files_in_folder and
_list_all_file_ids_in_folder methods that prevents infinite recursion
when PikPak's path_to_id API returns incorrect folder IDs for non-existent paths.
"""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from module.downloader.client.pikpak_downloader import (
    MAX_FOLDER_DEPTH,
    PikPakDownloader,
)

# --- Fixtures ---


@pytest.fixture
def mock_pikpak_api():
    """Create a mock PikPakApi instance for cycle detection tests.

    Returns tuple of (MockClass, mock_instance) for configuring test behavior.
    """
    with patch("module.downloader.client.pikpak_downloader.PikPakApi") as MockApi:
        mock_instance = MagicMock()

        # Configure async methods
        mock_instance.login = AsyncMock()
        mock_instance.refresh_access_token = AsyncMock()
        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "folder_123", "name": "AutoBangumi"}]
        )
        mock_instance.file_list = AsyncMock(return_value={"files": []})

        # Configure synchronous attributes
        mock_instance.access_token = "test_access_token"
        mock_instance.refresh_token = "test_refresh_token"
        mock_instance.user_id = "test_user_123"
        mock_instance.encode_token = MagicMock()

        MockApi.return_value = mock_instance
        yield MockApi, mock_instance


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory for config files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def pikpak_downloader(mock_pikpak_api, temp_config_dir):
    """Create a PikPakDownloader instance with mocked dependencies."""
    MockApi, mock_instance = mock_pikpak_api

    # Patch file paths to use temp directory
    with (
        patch(
            "module.downloader.client.pikpak_downloader.TOKEN_FILE",
            os.path.join(temp_config_dir, "pikpak_token.json"),
        ),
        patch(
            "module.downloader.client.pikpak_downloader.HASH_MAP_FILE",
            os.path.join(temp_config_dir, "pikpak_hash_map.json"),
        ),
    ):
        downloader = PikPakDownloader("test@example.com", "password123")
        yield downloader


# --- Test Classes ---


@pytest.mark.unit
class TestCycleDetectionInListFiles:
    """Tests for cycle detection in _list_files_in_folder."""

    def test_detects_circular_folder_reference(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that _list_files_in_folder detects circular folder references.

        Simulates the bug where path_to_id returns the same folder ID for
        different paths (e.g., /Bangumi and /Bangumi/NonExistent both return
        the same ID), which would cause infinite recursion without cycle detection.
        """
        _, mock_instance = mock_pikpak_api

        # The bug: path_to_id returns the SAME folder ID for any path
        # This happens when a path doesn't exist - API returns parent folder
        same_folder_id = "VOjvA_T3c2Pq2I6F-WfdyOhzo2"
        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": same_folder_id, "name": "Bangumi"}]
        )

        # Folder contains a subfolder, which would trigger recursion
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "Subfolder", "kind": "drive#folder", "id": "sub1"},
                ]
            }
        )

        # Without cycle detection, this would recurse infinitely
        # With cycle detection, it should return empty after detecting the cycle
        files = pikpak_downloader._list_files_in_folder("/Bangumi/NonExistent/Path")

        # Should return empty list (cycle detected on second iteration)
        assert files == []

        # path_to_id should have been called at most twice:
        # 1. For the initial path /Bangumi/NonExistent/Path
        # 2. For the subfolder path (before cycle detected)
        assert mock_instance.path_to_id.call_count <= 2

    def test_visited_ids_prevents_revisit(self, pikpak_downloader, mock_pikpak_api):
        """Test that visited folder IDs are tracked and prevent revisits."""
        _, mock_instance = mock_pikpak_api

        # Setup: folder A contains folder B, folder B "contains" folder A (cycle)
        folder_a_id = "folder_a_id"
        folder_b_id = "folder_b_id"

        call_count = [0]

        def path_to_id_side_effect(path, create=False):
            call_count[0] += 1
            if "FolderB" in path:
                return [{"id": folder_b_id, "name": "FolderB"}]
            return [{"id": folder_a_id, "name": "FolderA"}]

        mock_instance.path_to_id = AsyncMock(side_effect=path_to_id_side_effect)

        def file_list_side_effect(parent_id):
            if parent_id == folder_a_id:
                return {
                    "files": [
                        {"name": "FolderB", "kind": "drive#folder", "id": folder_b_id}
                    ]
                }
            elif parent_id == folder_b_id:
                # This creates a cycle back to folder_a
                return {
                    "files": [
                        {"name": "FolderA", "kind": "drive#folder", "id": folder_a_id}
                    ]
                }
            return {"files": []}

        mock_instance.file_list = AsyncMock(side_effect=file_list_side_effect)

        # Should not hang due to cycle detection
        files = pikpak_downloader._list_files_in_folder("/FolderA")

        # Cycle is broken - no infinite recursion
        assert isinstance(files, list)
        # Should have limited calls (not infinite)
        assert call_count[0] <= 4

    def test_returns_files_before_cycle(self, pikpak_downloader, mock_pikpak_api):
        """Test that files found before hitting a cycle are still returned."""
        _, mock_instance = mock_pikpak_api

        folder_id = "same_folder_id"
        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": folder_id, "name": "Folder"}]
        )

        first_call = [True]

        def file_list_side_effect(parent_id):
            if first_call[0]:
                first_call[0] = False
                return {
                    "files": [
                        {"name": "video.mkv", "kind": "drive#file", "id": "file1"},
                        {"name": "Subfolder", "kind": "drive#folder", "id": "sub1"},
                    ]
                }
            # Subsequent calls return empty (cycle would be detected anyway)
            return {"files": []}

        mock_instance.file_list = AsyncMock(side_effect=file_list_side_effect)

        files = pikpak_downloader._list_files_in_folder("/Folder")

        # Should return the file found in the first iteration
        assert len(files) == 1
        assert files[0].name == "video.mkv"


@pytest.mark.unit
class TestMaxFolderDepth:
    """Tests for MAX_FOLDER_DEPTH limit in folder traversal."""

    def test_max_depth_constant_exists(self):
        """Test that MAX_FOLDER_DEPTH constant is defined and reasonable."""
        assert isinstance(MAX_FOLDER_DEPTH, int)
        assert MAX_FOLDER_DEPTH > 0
        assert MAX_FOLDER_DEPTH == 20  # Current implementation value

    def test_stops_at_max_depth(self, pikpak_downloader, mock_pikpak_api):
        """Test that _list_files_in_folder stops at MAX_FOLDER_DEPTH.

        Creates a deep folder structure that would exceed MAX_FOLDER_DEPTH
        if not limited, verifying the depth check works correctly.
        """
        _, mock_instance = mock_pikpak_api

        folder_counter = [0]

        def path_to_id_side_effect(path, create=False):
            folder_counter[0] += 1
            # Return unique folder ID for each path
            return [{"id": f"folder_{folder_counter[0]}", "name": f"Level{folder_counter[0]}"}]

        mock_instance.path_to_id = AsyncMock(side_effect=path_to_id_side_effect)

        # Each folder contains one subfolder, creating infinite depth
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "DeepFolder", "kind": "drive#folder", "id": "deep"},
                ]
            }
        )

        _files = pikpak_downloader._list_files_in_folder("/Start")

        # Should have stopped at MAX_FOLDER_DEPTH, not gone infinite
        # Allow some buffer for the implementation
        # Note: _files is intentionally unused - we're testing the depth limit
        assert folder_counter[0] <= MAX_FOLDER_DEPTH + 2

    def test_depth_parameter_increments(self, pikpak_downloader, mock_pikpak_api):
        """Test that _depth parameter is properly incremented during recursion."""
        _, mock_instance = mock_pikpak_api

        depths_seen = []

        # Store original method
        original_method = pikpak_downloader._list_files_in_folder

        def tracking_wrapper(folder_path, _visited_ids=None, _depth=0):
            depths_seen.append(_depth)
            if _depth >= 3:  # Stop after a few levels to avoid long test
                return []
            return original_method(folder_path, _visited_ids, _depth)

        # Patch method to track depth
        pikpak_downloader._list_files_in_folder = tracking_wrapper

        # Setup for 3 levels of nesting
        # Must return full path components to pass path validation
        def path_to_id_side_effect(path, create=False):
            # Parse the path and return matching components
            parts = path.strip("/").split("/")
            return [{"id": f"folder_{i}", "name": part} for i, part in enumerate(parts)]

        mock_instance.path_to_id = AsyncMock(side_effect=path_to_id_side_effect)
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "SubFolder", "kind": "drive#folder", "id": "sub"},
                ]
            }
        )

        pikpak_downloader._list_files_in_folder("/Root")

        # Should have seen increasing depth values
        assert 0 in depths_seen
        assert 1 in depths_seen
        assert 2 in depths_seen


@pytest.mark.unit
class TestCycleDetectionInListAllFileIds:
    """Tests for cycle detection in _list_all_file_ids_in_folder."""

    def test_detects_circular_folder_reference(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that _list_all_file_ids_in_folder detects circular folder references."""
        _, mock_instance = mock_pikpak_api

        # Same folder ID returned for all paths (simulating the bug)
        same_folder_id = "circular_folder_id"
        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": same_folder_id, "name": "Circular"}]
        )

        # Folder contains a subfolder
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "Loop", "kind": "drive#folder", "id": "loop_sub"},
                ]
            }
        )

        # Should not hang
        file_ids = pikpak_downloader._list_all_file_ids_in_folder("/Circular/Path")

        # Should return empty (no files, just folders in cycle)
        assert file_ids == []
        # Should have limited calls
        assert mock_instance.path_to_id.call_count <= 2

    def test_stops_at_max_depth(self, pikpak_downloader, mock_pikpak_api):
        """Test that _list_all_file_ids_in_folder stops at MAX_FOLDER_DEPTH."""
        _, mock_instance = mock_pikpak_api

        folder_counter = [0]

        def path_to_id_side_effect(path, create=False):
            folder_counter[0] += 1
            return [{"id": f"folder_{folder_counter[0]}", "name": f"Level{folder_counter[0]}"}]

        mock_instance.path_to_id = AsyncMock(side_effect=path_to_id_side_effect)

        # Each folder contains one subfolder
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "Deep", "kind": "drive#folder", "id": "deep_sub"},
                ]
            }
        )

        _file_ids = pikpak_downloader._list_all_file_ids_in_folder("/Deep/Start")

        # Should have stopped at MAX_FOLDER_DEPTH
        # Note: _file_ids is intentionally unused - we're testing the depth limit
        assert folder_counter[0] <= MAX_FOLDER_DEPTH + 2

    def test_collects_files_before_cycle(self, pikpak_downloader, mock_pikpak_api):
        """Test that file IDs found before hitting a cycle are still returned."""
        _, mock_instance = mock_pikpak_api

        folder_id = "same_folder"
        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": folder_id, "name": "Folder"}]
        )

        first_call = [True]

        def file_list_side_effect(parent_id):
            if first_call[0]:
                first_call[0] = False
                return {
                    "files": [
                        {"name": "video.mkv", "kind": "drive#file", "id": "file_123"},
                        {"name": "Subfolder", "kind": "drive#folder", "id": "sub"},
                    ]
                }
            return {"files": []}

        mock_instance.file_list = AsyncMock(side_effect=file_list_side_effect)

        file_ids = pikpak_downloader._list_all_file_ids_in_folder("/Folder")

        # Should return the file ID found before cycle
        assert "file_123" in file_ids
        assert len(file_ids) == 1

    def test_does_not_include_folder_ids(self, pikpak_downloader, mock_pikpak_api):
        """Test that folder IDs are not included in the result, only file IDs."""
        _, mock_instance = mock_pikpak_api

        # Use different IDs for each folder to avoid cycle detection
        call_count = [0]

        def path_to_id_side_effect(path, create=False):
            call_count[0] += 1
            return [{"id": f"folder_{call_count[0]}", "name": "Folder"}]

        mock_instance.path_to_id = AsyncMock(side_effect=path_to_id_side_effect)

        # Return mix of files and folders
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "video.mkv", "kind": "drive#file", "id": "file_id"},
                    {"name": "subfolder", "kind": "drive#folder", "id": "folder_id"},
                ]
            }
        )

        # Limit recursion for test
        original_method = pikpak_downloader._list_all_file_ids_in_folder

        def limited_recursion(path, _visited_ids=None, _depth=0):
            if _depth > 0:
                return []
            return original_method(path, _visited_ids, _depth)

        pikpak_downloader._list_all_file_ids_in_folder = limited_recursion

        file_ids = pikpak_downloader._list_all_file_ids_in_folder("/Test")

        # Should only contain file ID, not folder ID
        assert "file_id" in file_ids
        assert "folder_id" not in file_ids


@pytest.mark.unit
class TestVisitedIdsParameter:
    """Tests for the _visited_ids parameter behavior."""

    def test_visited_ids_starts_as_none(self, pikpak_downloader, mock_pikpak_api):
        """Test that _visited_ids defaults to None and is initialized internally."""
        _, mock_instance = mock_pikpak_api

        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "folder_1", "name": "Test"}]
        )
        mock_instance.file_list = AsyncMock(return_value={"files": []})

        # Calling without _visited_ids should work
        result = pikpak_downloader._list_files_in_folder("/Test")
        assert isinstance(result, list)

    def test_visited_ids_shared_across_recursion(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that _visited_ids set is shared and updated across recursive calls."""
        _, mock_instance = mock_pikpak_api

        folder_a_id = "folder_a"
        folder_b_id = "folder_b"

        def path_to_id_side_effect(path, create=False):
            # Return full path components to pass path validation
            parts = path.strip("/").split("/")
            result = []
            for part in parts:
                if part == "A":
                    result.append({"id": folder_a_id, "name": "A"})
                elif part == "B":
                    result.append({"id": folder_b_id, "name": "B"})
            return result

        mock_instance.path_to_id = AsyncMock(side_effect=path_to_id_side_effect)

        call_count = {"A": 0, "B": 0}

        def file_list_side_effect(parent_id):
            if parent_id == folder_a_id:
                call_count["A"] += 1
                if call_count["A"] == 1:
                    return {
                        "files": [
                            {"name": "B", "kind": "drive#folder", "id": folder_b_id}
                        ]
                    }
            elif parent_id == folder_b_id:
                call_count["B"] += 1
                if call_count["B"] == 1:
                    # Try to recurse back to A - should be blocked by visited_ids
                    return {
                        "files": [
                            {"name": "A", "kind": "drive#folder", "id": folder_a_id}
                        ]
                    }
            return {"files": []}

        mock_instance.file_list = AsyncMock(side_effect=file_list_side_effect)

        _result = pikpak_downloader._list_files_in_folder("/A")

        # Each folder should only be visited once
        # Note: _result is intentionally unused - we're testing call counts
        assert call_count["A"] == 1
        assert call_count["B"] == 1


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases in cycle detection."""

    def test_empty_folder_returns_empty_list(self, pikpak_downloader, mock_pikpak_api):
        """Test that an empty folder returns an empty list."""
        _, mock_instance = mock_pikpak_api

        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "empty_folder", "name": "Empty"}]
        )
        mock_instance.file_list = AsyncMock(return_value={"files": []})

        result = pikpak_downloader._list_files_in_folder("/Empty")

        assert result == []

    def test_nonexistent_folder_returns_empty_list(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that a non-existent folder returns an empty list."""
        _, mock_instance = mock_pikpak_api

        # path_to_id returns empty for non-existent path
        mock_instance.path_to_id = AsyncMock(return_value=[])

        result = pikpak_downloader._list_files_in_folder("/NonExistent")

        assert result == []

    def test_path_to_id_returns_no_id(self, pikpak_downloader, mock_pikpak_api):
        """Test handling when path_to_id returns entry without 'id' field."""
        _, mock_instance = mock_pikpak_api

        # Returns entry without id
        mock_instance.path_to_id = AsyncMock(
            return_value=[{"name": "NoId"}]  # Missing 'id'
        )

        result = pikpak_downloader._list_files_in_folder("/NoId")

        assert result == []

    def test_api_exception_returns_empty_list(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that API exceptions are caught and return empty list."""
        _, mock_instance = mock_pikpak_api

        mock_instance.path_to_id = AsyncMock(
            side_effect=Exception("API Error")
        )

        result = pikpak_downloader._list_files_in_folder("/Error")

        assert result == []

    def test_path_normalization_with_leading_slash(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that paths are normalized to start with /."""
        _, mock_instance = mock_pikpak_api

        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "folder", "name": "Test"}]
        )
        mock_instance.file_list = AsyncMock(return_value={"files": []})

        # Path without leading slash should still work
        result = pikpak_downloader._list_files_in_folder("NoSlash/Path")

        assert result == []
        # Verify path was normalized (path_to_id should receive path with /)
        call_args = mock_instance.path_to_id.call_args
        called_path = call_args[0][0] if call_args[0] else call_args.kwargs.get("path")
        assert called_path.startswith("/")


@pytest.mark.unit
def test_list_files_handles_pikpak_fuzzy_path_matching(pikpak_downloader, mock_pikpak_api):
    """
    Test handling of PikPak's fuzzy path matching bug.

    When a path doesn't exist, PikPak returns the closest parent folder.
    With path validation, this is now detected as a stale path and returns
    empty list immediately (fail-fast) instead of listing the wrong folder.
    """
    _, mock_instance = mock_pikpak_api
    bangumi_folder_id = "VOjvA_T3c2Pq2I6F-WfdyOhzo2"

    # Simulate: any path under /Bangumi returns only the Bangumi folder
    # (fuzzy matching - DeletedFolder/Season1 doesn't exist)
    mock_instance.path_to_id = AsyncMock(return_value=[
        {"id": bangumi_folder_id, "name": "Bangumi"}
    ])

    # Bangumi folder contains multiple anime folders plus a file
    mock_instance.file_list = AsyncMock(return_value={
        "files": [
            {"name": "Anime1", "kind": "drive#folder", "id": "a1"},
            {"name": "Anime2", "kind": "drive#folder", "id": "a2"},
            {"name": "video.mp4", "kind": "drive#file", "id": "v1"},
        ]
    })

    # Request non-existent path - should detect stale path and return empty
    files = pikpak_downloader._list_files_in_folder("/Bangumi/DeletedFolder/Season1")

    # With path validation, stale paths return empty immediately (fail-fast)
    # This prevents listing hundreds of files from the wrong folder
    assert files == []
    # file_list should NOT have been called (we fail before listing)
    mock_instance.file_list.assert_not_called()


@pytest.mark.unit
def test_validate_hash_map_removes_stale_entries(pikpak_downloader, mock_pikpak_api):
    """Test that validate_hash_map removes entries pointing to non-existent folders."""
    _, mock_instance = mock_pikpak_api

    # Setup hash map with mix of valid and stale entries
    pikpak_downloader._hash_map = {
        "hash1": "/Bangumi/ValidAnime/Season1",  # exists
        "hash2": "/Bangumi/DeletedAnime/Season1",  # deleted
        "hash3": "/Bangumi/AnotherValid/Season2",  # exists
    }

    # Mock path_to_id: return None for deleted paths
    async def mock_path_to_id(path, create=False):
        if "Deleted" in path:
            return None  # folder doesn't exist
        return [{"id": "valid_id", "name": "folder"}]

    mock_instance.path_to_id = AsyncMock(side_effect=mock_path_to_id)
    pikpak_downloader._save_hash_map = MagicMock()

    # Run validation
    removed = pikpak_downloader.validate_hash_map()

    # Should remove stale entry
    assert "hash2" in removed
    assert "hash2" not in pikpak_downloader._hash_map
    assert "hash1" in pikpak_downloader._hash_map
    assert "hash3" in pikpak_downloader._hash_map
    pikpak_downloader._save_hash_map.assert_called_once()
