"""Unit tests for PikPak stale path detection.

Tests the path validation mechanism in _list_files_in_folder that prevents
listing files from wrong folders when stored paths become stale due to
user actions in the PikPak UI (moving/renaming folders).
"""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from module.downloader.client.pikpak_downloader import PikPakDownloader

# --- Fixtures ---


@pytest.fixture
def mock_pikpak_api():
    """Create a mock PikPakApi instance for path validation tests.

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
class TestStalePathDetection:
    """Tests for stale path detection in _list_files_in_folder."""

    def test_stale_path_returns_empty_list(self, pikpak_downloader, mock_pikpak_api):
        """Test that partial path resolution returns empty list.

        Simulates the bug where a folder was moved/renamed and path_to_id
        only resolves part of the path (e.g., /Bangumi instead of
        /Bangumi/Title/Season 4).
        """
        _, mock_instance = mock_pikpak_api

        # The bug: path_to_id only resolves to /Bangumi when we requested
        # /Bangumi/Title/Season 4 (because Title/Season 4 was moved/deleted)
        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "bangumi_id", "name": "Bangumi"}]
        )

        # This would return hundreds of files if we didn't validate
        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "Anime1", "kind": "drive#folder", "id": "a1"},
                    {"name": "Anime2", "kind": "drive#folder", "id": "a2"},
                    {"name": "video.mp4", "kind": "drive#file", "id": "v1"},
                ]
            }
        )

        # Request a path that should have 3 components
        files = pikpak_downloader._list_files_in_folder(
            "/Bangumi/Title/Season 4"
        )

        # Should return empty because path validation detected mismatch
        assert files == []
        # file_list should NOT have been called (fail fast)
        mock_instance.file_list.assert_not_called()

    def test_valid_path_returns_files(self, pikpak_downloader, mock_pikpak_api):
        """Test that full path resolution works normally."""
        _, mock_instance = mock_pikpak_api

        # path_to_id returns the complete path components
        mock_instance.path_to_id = AsyncMock(
            return_value=[
                {"id": "bangumi_id", "name": "Bangumi"},
                {"id": "title_id", "name": "Title"},
                {"id": "season_id", "name": "Season 4"},
            ]
        )

        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "episode01.mkv", "kind": "drive#file", "id": "e1"},
                    {"name": "episode02.mkv", "kind": "drive#file", "id": "e2"},
                ]
            }
        )

        files = pikpak_downloader._list_files_in_folder("/Bangumi/Title/Season 4")

        # Should return the files since path fully resolved
        assert len(files) == 2
        assert files[0].name == "episode01.mkv"
        assert files[1].name == "episode02.mkv"
        # file_list should have been called
        mock_instance.file_list.assert_called_once_with(parent_id="season_id")

    def test_missing_folder_returns_empty_list(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that completely missing folder returns empty list."""
        _, mock_instance = mock_pikpak_api

        # path_to_id returns empty/None for non-existent path
        mock_instance.path_to_id = AsyncMock(return_value=None)

        files = pikpak_downloader._list_files_in_folder("/NonExistent/Path")

        assert files == []
        mock_instance.file_list.assert_not_called()

    def test_stale_path_logs_warning(
        self, pikpak_downloader, mock_pikpak_api, caplog
    ):
        """Test that stale path detection logs a warning message."""
        _, mock_instance = mock_pikpak_api

        # Simulate partial resolution
        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "bangumi_id", "name": "Bangumi"}]
        )

        import logging

        with caplog.at_level(logging.WARNING):
            pikpak_downloader._list_files_in_folder("/Bangumi/Title/Season 4")

        # Check that warning was logged
        assert any("Stale path detected" in record.message for record in caplog.records)
        assert any("/Bangumi/Title/Season 4" in record.message for record in caplog.records)

    def test_single_component_path_works(self, pikpak_downloader, mock_pikpak_api):
        """Test that single-component paths work correctly."""
        _, mock_instance = mock_pikpak_api

        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "bangumi_id", "name": "Bangumi"}]
        )

        mock_instance.file_list = AsyncMock(
            return_value={
                "files": [
                    {"name": "file.mkv", "kind": "drive#file", "id": "f1"},
                ]
            }
        )

        files = pikpak_downloader._list_files_in_folder("/Bangumi")

        assert len(files) == 1
        assert files[0].name == "file.mkv"

    def test_path_without_leading_slash_validated(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that paths without leading slash are still validated correctly."""
        _, mock_instance = mock_pikpak_api

        # Partial resolution
        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "bangumi_id", "name": "Bangumi"}]
        )

        # Path without leading slash
        files = pikpak_downloader._list_files_in_folder("Bangumi/Title/Season 4")

        # Should still detect mismatch
        assert files == []

    def test_intermediate_path_mismatch_detected(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test that intermediate path component mismatches are detected."""
        _, mock_instance = mock_pikpak_api

        # Returns a different intermediate component (Renamed vs Title)
        mock_instance.path_to_id = AsyncMock(
            return_value=[
                {"id": "bangumi_id", "name": "Bangumi"},
                {"id": "renamed_id", "name": "Renamed"},  # Different from Title
                {"id": "season_id", "name": "Season 4"},
            ]
        )

        files = pikpak_downloader._list_files_in_folder("/Bangumi/Title/Season 4")

        # Should detect mismatch even though same number of components
        assert files == []


@pytest.mark.unit
class TestPathValidationEdgeCases:
    """Edge case tests for path validation."""

    def test_empty_path_info_returns_empty(self, pikpak_downloader, mock_pikpak_api):
        """Test that empty path_info returns empty list."""
        _, mock_instance = mock_pikpak_api

        mock_instance.path_to_id = AsyncMock(return_value=[])

        files = pikpak_downloader._list_files_in_folder("/Any/Path")

        assert files == []

    def test_path_info_with_missing_name_field(
        self, pikpak_downloader, mock_pikpak_api
    ):
        """Test handling when path_info entry has no 'name' field."""
        _, mock_instance = mock_pikpak_api

        # Entry without name field
        mock_instance.path_to_id = AsyncMock(
            return_value=[{"id": "folder_id"}]  # No "name" key
        )

        files = pikpak_downloader._list_files_in_folder("/Bangumi")

        # Should detect mismatch (empty name vs "Bangumi")
        assert files == []

    def test_special_characters_in_path(self, pikpak_downloader, mock_pikpak_api):
        """Test that special characters in paths are handled correctly."""
        _, mock_instance = mock_pikpak_api

        special_name = "Anime [2024] (BD)"
        mock_instance.path_to_id = AsyncMock(
            return_value=[
                {"id": "bangumi_id", "name": "Bangumi"},
                {"id": "special_id", "name": special_name},
            ]
        )

        mock_instance.file_list = AsyncMock(
            return_value={"files": [{"name": "ep01.mkv", "kind": "drive#file", "id": "f1"}]}
        )

        files = pikpak_downloader._list_files_in_folder(f"/Bangumi/{special_name}")

        assert len(files) == 1
        assert files[0].name == "ep01.mkv"
