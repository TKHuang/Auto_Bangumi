"""Comprehensive tests for the Rename System.

Tests cover:
- Pure functions: gen_save_path, gen_rename_path, generate_rename_commands
- Orchestrator functions: rename_bangumi, rename_all
- Idempotency: already renamed torrents produce no commands
- Error handling: missing bangumi, parse errors, DB failures
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from zen_bangumi.domain.commands.base import RenameFile
from zen_bangumi.domain.models.bangumi import Bangumi
from zen_bangumi.domain.models.torrent import Torrent
from zen_bangumi.domain.parser.models import EpisodeType, ParsedBangumi
from zen_bangumi.effects.result import EffectResult, EffectStatus
from zen_bangumi.services.renamer import (
    RenameResult,
    gen_save_path,
    gen_rename_path,
    generate_rename_commands,
    rename_bangumi,
    rename_all,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_bangumi_with_year() -> Bangumi:
    """Bangumi with year information."""
    bangumi = Bangumi(
        id=1,
        official_title="Frieren: Beyond Journey's End",
        year="2023",
        title_raw="Frieren",
        season=1,
        season_raw="1",
        group_name="Lilith-Raws",
    )
    return bangumi


@pytest.fixture
def sample_bangumi_without_year() -> Bangumi:
    """Bangumi without year information."""
    bangumi = Bangumi(
        id=2,
        official_title="Test Anime",
        year=None,
        title_raw="Test",
        season=2,
        season_raw="2",
        group_name="SubGroup",
    )
    return bangumi


@pytest.fixture
def sample_torrent_unrenamed() -> Torrent:
    """Unrenamed torrent."""
    return Torrent(
        id=1,
        bangumi_id=1,
        name="[Lilith-Raws] Frieren - 01 [Baha][WEB-DL][1080p][AVC AAC][CHT][MP4].mp4",
        url="https://example.com/torrent1",
        downloaded=True,
        renamed_at=None,
    )


@pytest.fixture
def sample_torrent_renamed() -> Torrent:
    """Already renamed torrent."""
    return Torrent(
        id=2,
        bangumi_id=1,
        name="Frieren S01E02.mp4",
        url="https://example.com/torrent2",
        downloaded=True,
        renamed_at=datetime(2024, 1, 1, 12, 0, 0),
    )


@pytest.fixture
def sample_torrent_special_episode() -> Torrent:
    """Torrent with special episode (OVA)."""
    return Torrent(
        id=3,
        bangumi_id=1,
        name="[Lilith-Raws] Frieren OVA 01 [Baha][WEB-DL][1080p][AVC AAC][CHT][MP4].mp4",
        url="https://example.com/torrent3",
        downloaded=True,
        renamed_at=None,
    )


@pytest.fixture
def sample_torrent_version_suffix() -> Torrent:
    """Torrent with version suffix (v2)."""
    return Torrent(
        id=4,
        bangumi_id=1,
        name="[Lilith-Raws] Frieren - 03v2 [Baha][WEB-DL][1080p][AVC AAC][CHT][MP4].mp4",
        url="https://example.com/torrent4",
        downloaded=True,
        renamed_at=None,
    )


@pytest.fixture
def sample_torrent_float_episode() -> Torrent:
    """Torrent with float episode number (12.5)."""
    return Torrent(
        id=5,
        bangumi_id=1,
        name="[Lilith-Raws] Frieren - 12.5 [Baha][WEB-DL][1080p][AVC AAC][CHT][MP4].mp4",
        url="https://example.com/torrent5",
        downloaded=True,
        renamed_at=None,
    )


@pytest.fixture
def mock_bangumi_repo() -> AsyncMock:
    """Mock BangumiRepository."""
    return AsyncMock()


@pytest.fixture
def mock_torrent_repo() -> AsyncMock:
    """Mock TorrentRepository."""
    return AsyncMock()


@pytest.fixture
def mock_interpreter() -> AsyncMock:
    """Mock EffectInterpreter."""
    return AsyncMock()


# ============================================================================
# Tests for gen_save_path (Pure Function)
# ============================================================================


class TestGenSavePath:
    """Tests for gen_save_path pure function."""

    def test_gen_save_path_with_year(self, sample_bangumi_with_year):
        """Should generate path with year in folder name."""
        result = gen_save_path(sample_bangumi_with_year, "/downloads/Bangumi")
        
        assert result == "/downloads/Bangumi/Frieren: Beyond Journey's End (2023)/Season 1"

    def test_gen_save_path_without_year(self, sample_bangumi_without_year):
        """Should generate path without year in folder name."""
        result = gen_save_path(sample_bangumi_without_year, "/downloads/Bangumi")
        
        assert result == "/downloads/Bangumi/Test Anime/Season 2"

    def test_gen_save_path_custom_base_path(self, sample_bangumi_with_year):
        """Should use custom base path."""
        result = gen_save_path(sample_bangumi_with_year, "/media/anime")
        
        assert result == "/media/anime/Frieren: Beyond Journey's End (2023)/Season 1"

    def test_gen_save_path_season_zero(self, sample_bangumi_with_year):
        """Should handle season 0 (specials)."""
        sample_bangumi_with_year.season = 0
        result = gen_save_path(sample_bangumi_with_year, "/downloads/Bangumi")
        
        assert "Season 0" in result

    def test_gen_save_path_season_double_digit(self, sample_bangumi_with_year):
        """Should handle double-digit seasons."""
        sample_bangumi_with_year.season = 12
        result = gen_save_path(sample_bangumi_with_year, "/downloads/Bangumi")
        
        assert "Season 12" in result


# ============================================================================
# Tests for gen_rename_path (Pure Function)
# ============================================================================


class TestGenRenamePath:
    """Tests for gen_rename_path pure function."""

    def test_gen_rename_path_regular_episode(self, sample_bangumi_with_year):
        """Should generate regular episode filename."""
        result = gen_rename_path(
            bangumi=sample_bangumi_with_year,
            episode=1,
            extension=".mp4",
        )
        
        assert result == "Frieren: Beyond Journey's End S01E01.mp4"

    def test_gen_rename_path_double_digit_episode(self, sample_bangumi_with_year):
        """Should zero-pad episode numbers."""
        result = gen_rename_path(
            bangumi=sample_bangumi_with_year,
            episode=12,
            extension=".mp4",
        )
        
        assert result == "Frieren: Beyond Journey's End S01E12.mp4"

    def test_gen_rename_path_with_version(self, sample_bangumi_with_year):
        """Should include version suffix."""
        result = gen_rename_path(
            bangumi=sample_bangumi_with_year,
            episode=5,
            extension=".mp4",
            version=2,
        )
        
        assert result == "Frieren: Beyond Journey's End S01E05v2.mp4"

    def test_gen_rename_path_ova_episode(self, sample_bangumi_with_year):
        """Should format OVA episodes correctly."""
        result = gen_rename_path(
            bangumi=sample_bangumi_with_year,
            episode=1,
            extension=".mp4",
            episode_type="OVA",
        )
        
        assert result == "Frieren: Beyond Journey's End OVA 01.mp4"

    def test_gen_rename_path_oad_episode(self, sample_bangumi_with_year):
        """Should format OAD episodes correctly."""
        result = gen_rename_path(
            bangumi=sample_bangumi_with_year,
            episode=2,
            extension=".mp4",
            episode_type="OAD",
        )
        
        assert result == "Frieren: Beyond Journey's End OAD 02.mp4"

    def test_gen_rename_path_sp_episode(self, sample_bangumi_with_year):
        """Should format SP (special) episodes correctly."""
        result = gen_rename_path(
            bangumi=sample_bangumi_with_year,
            episode=1,
            extension=".mp4",
            episode_type="SP",
        )
        
        assert result == "Frieren: Beyond Journey's End SP 01.mp4"

    def test_gen_rename_path_float_episode(self, sample_bangumi_with_year):
        """Should handle float episode numbers (e.g., 12.5)."""
        result = gen_rename_path(
            bangumi=sample_bangumi_with_year,
            episode=12.5,
            extension=".mp4",
        )
        
        assert result == "Frieren: Beyond Journey's End S01E0125.mp4"

    def test_gen_rename_path_float_whole_number(self, sample_bangumi_with_year):
        """Should convert float to int if it's a whole number."""
        result = gen_rename_path(
            bangumi=sample_bangumi_with_year,
            episode=5.0,
            extension=".mp4",
        )
        
        assert result == "Frieren: Beyond Journey's End S01E05.mp4"

    def test_gen_rename_path_special_with_version(self, sample_bangumi_with_year):
        """Should include version suffix with special episodes."""
        result = gen_rename_path(
            bangumi=sample_bangumi_with_year,
            episode=1,
            extension=".mp4",
            version=2,
            episode_type="OVA",
        )
        
        assert result == "Frieren: Beyond Journey's End OVA 01v2.mp4"

    def test_gen_rename_path_different_extension(self, sample_bangumi_with_year):
        """Should handle different file extensions."""
        result = gen_rename_path(
            bangumi=sample_bangumi_with_year,
            episode=1,
            extension=".mkv",
        )
        
        assert result == "Frieren: Beyond Journey's End S01E01.mkv"

    def test_gen_rename_path_season_double_digit(self, sample_bangumi_with_year):
        """Should zero-pad season numbers."""
        sample_bangumi_with_year.season = 12
        result = gen_rename_path(
            bangumi=sample_bangumi_with_year,
            episode=1,
            extension=".mp4",
        )
        
        assert result == "Frieren: Beyond Journey's End S12E01.mp4"


# ============================================================================
# Tests for generate_rename_commands (Pure Function)
# ============================================================================


class TestGenerateRenameCommands:
    """Tests for generate_rename_commands pure function."""

    @patch("zen_bangumi.services.renamer.BangumiParser")
    def test_generate_rename_commands_single_torrent(
        self,
        mock_parser_class,
        sample_bangumi_with_year,
        sample_torrent_unrenamed,
    ):
        """Should generate rename command for unrenamed torrent."""
        # Mock parser
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        mock_parser.raw_parse.return_value = ParsedBangumi(
            raw=sample_torrent_unrenamed.name,
            episode=1,
        )
        
        commands = generate_rename_commands(
            bangumi=sample_bangumi_with_year,
            torrents=[sample_torrent_unrenamed],
            downloader_type="qbittorrent",
        )
        
        assert len(commands) == 1
        assert isinstance(commands[0], RenameFile)
        assert "Frieren: Beyond Journey's End S01E01" in commands[0].target_path

    @patch("zen_bangumi.services.renamer.BangumiParser")
    def test_generate_rename_commands_skip_renamed(
        self,
        mock_parser_class,
        sample_bangumi_with_year,
        sample_torrent_renamed,
    ):
        """Should skip already renamed torrents (idempotent)."""
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        
        commands = generate_rename_commands(
            bangumi=sample_bangumi_with_year,
            torrents=[sample_torrent_renamed],
            downloader_type="qbittorrent",
        )
        
        assert len(commands) == 0
        mock_parser.raw_parse.assert_not_called()

    @patch("zen_bangumi.services.renamer.BangumiParser")
    def test_generate_rename_commands_mixed_renamed_unrenamed(
        self,
        mock_parser_class,
        sample_bangumi_with_year,
        sample_torrent_unrenamed,
        sample_torrent_renamed,
    ):
        """Should process only unrenamed torrents."""
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        mock_parser.raw_parse.return_value = ParsedBangumi(
            raw=sample_torrent_unrenamed.name,
            episode=1,
        )
        
        commands = generate_rename_commands(
            bangumi=sample_bangumi_with_year,
            torrents=[sample_torrent_unrenamed, sample_torrent_renamed],
            downloader_type="qbittorrent",
        )
        
        assert len(commands) == 1

    @patch("zen_bangumi.services.renamer.BangumiParser")
    def test_generate_rename_commands_with_version(
        self,
        mock_parser_class,
        sample_bangumi_with_year,
        sample_torrent_version_suffix,
    ):
        """Should include version suffix in generated commands."""
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        mock_parser.raw_parse.return_value = ParsedBangumi(
            raw=sample_torrent_version_suffix.name,
            episode=3,
            version=2,
        )
        
        commands = generate_rename_commands(
            bangumi=sample_bangumi_with_year,
            torrents=[sample_torrent_version_suffix],
            downloader_type="qbittorrent",
        )
        
        assert len(commands) == 1
        assert "v2" in commands[0].target_path

    @patch("zen_bangumi.services.renamer.BangumiParser")
    def test_generate_rename_commands_with_special_episode(
        self,
        mock_parser_class,
        sample_bangumi_with_year,
        sample_torrent_special_episode,
    ):
        """Should handle special episodes (OVA, OAD, SP)."""
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        mock_parser.raw_parse.return_value = ParsedBangumi(
            raw=sample_torrent_special_episode.name,
            episode=1,
            episode_type=EpisodeType.OVA,
        )
        
        commands = generate_rename_commands(
            bangumi=sample_bangumi_with_year,
            torrents=[sample_torrent_special_episode],
            downloader_type="qbittorrent",
        )
        
        assert len(commands) == 1
        assert "OVA" in commands[0].target_path

    @patch("zen_bangumi.services.renamer.BangumiParser")
    def test_generate_rename_commands_with_float_episode(
        self,
        mock_parser_class,
        sample_bangumi_with_year,
        sample_torrent_float_episode,
    ):
        """Should handle float episode numbers."""
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        mock_parser.raw_parse.return_value = ParsedBangumi(
            raw=sample_torrent_float_episode.name,
            episode=12.5,
        )
        
        commands = generate_rename_commands(
            bangumi=sample_bangumi_with_year,
            torrents=[sample_torrent_float_episode],
            downloader_type="qbittorrent",
        )
        
        assert len(commands) == 1

    @patch("zen_bangumi.services.renamer.BangumiParser")
    def test_generate_rename_commands_parse_error_skipped(
        self,
        mock_parser_class,
        sample_bangumi_with_year,
        sample_torrent_unrenamed,
    ):
        """Should skip torrents that fail to parse."""
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        mock_parser.raw_parse.side_effect = Exception("Parse error")
        
        commands = generate_rename_commands(
            bangumi=sample_bangumi_with_year,
            torrents=[sample_torrent_unrenamed],
            downloader_type="qbittorrent",
        )
        
        assert len(commands) == 0

    @patch("zen_bangumi.services.renamer.BangumiParser")
    def test_generate_rename_commands_no_episode_skipped(
        self,
        mock_parser_class,
        sample_bangumi_with_year,
        sample_torrent_unrenamed,
    ):
        """Should skip torrents with no episode number."""
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        mock_parser.raw_parse.return_value = ParsedBangumi(
            raw=sample_torrent_unrenamed.name,
            episode=None,
        )
        
        commands = generate_rename_commands(
            bangumi=sample_bangumi_with_year,
            torrents=[sample_torrent_unrenamed],
            downloader_type="qbittorrent",
        )
        
        assert len(commands) == 0

    @patch("zen_bangumi.services.renamer.BangumiParser")
    def test_generate_rename_commands_pikpak_downloader(
        self,
        mock_parser_class,
        sample_bangumi_with_year,
        sample_torrent_unrenamed,
    ):
        """Should set correct downloader_type in command."""
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        mock_parser.raw_parse.return_value = ParsedBangumi(
            raw=sample_torrent_unrenamed.name,
            episode=1,
        )
        
        commands = generate_rename_commands(
            bangumi=sample_bangumi_with_year,
            torrents=[sample_torrent_unrenamed],
            downloader_type="pikpak",
        )
        
        assert len(commands) == 1
        assert commands[0].downloader_type == "pikpak"

    @patch("zen_bangumi.services.renamer.BangumiParser")
    def test_generate_rename_commands_custom_base_path(
        self,
        mock_parser_class,
        sample_bangumi_with_year,
        sample_torrent_unrenamed,
    ):
        """Should use custom base path in generated commands."""
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        mock_parser.raw_parse.return_value = ParsedBangumi(
            raw=sample_torrent_unrenamed.name,
            episode=1,
        )
        
        commands = generate_rename_commands(
            bangumi=sample_bangumi_with_year,
            torrents=[sample_torrent_unrenamed],
            downloader_type="qbittorrent",
            base_path="/media/anime",
        )
        
        assert len(commands) == 1
        assert "/media/anime" in commands[0].target_path


# ============================================================================
# Tests for rename_bangumi (Orchestrator Function)
# ============================================================================


class TestRenameBangumi:
    """Tests for rename_bangumi orchestrator function."""

    @pytest.mark.asyncio
    @patch("zen_bangumi.services.renamer.generate_rename_commands")
    async def test_rename_bangumi_success(
        self,
        mock_gen_commands,
        sample_bangumi_with_year,
        sample_torrent_unrenamed,
        mock_bangumi_repo,
        mock_torrent_repo,
        mock_interpreter,
    ):
        """Should successfully rename bangumi torrents."""
        # Setup mocks
        mock_bangumi_repo.get_by_id.return_value = sample_bangumi_with_year
        mock_torrent_repo.get_unrenamed.return_value = [sample_torrent_unrenamed]
        
        rename_command = RenameFile(
            source_path="/downloads/Bangumi/Frieren: Beyond Journey's End (2023)/Season 01/[Lilith-Raws] Frieren - 01 [Baha][WEB-DL][1080p][AVC AAC][CHT][MP4].mp4",
            target_path="/downloads/Bangumi/Frieren: Beyond Journey's End (2023)/Season 01/Frieren: Beyond Journey's End S01E01.mp4",
            downloader_type="qbittorrent",
        )
        mock_gen_commands.return_value = [rename_command]
        
        effect_result = EffectResult(
            command=rename_command,
            status=EffectStatus.SUCCESS,
        )
        mock_interpreter.execute.return_value = [effect_result]
        
        # Execute
        result = await rename_bangumi(
            bangumi_id=1,
            bangumi_repo=mock_bangumi_repo,
            torrent_repo=mock_torrent_repo,
            interpreter=mock_interpreter,
        )
        
        # Verify
        assert result.bangumi_id == 1
        assert result.renamed_count == 1
        assert len(result.errors) == 0
        mock_torrent_repo.mark_renamed.assert_called_once()

    @pytest.mark.asyncio
    async def test_rename_bangumi_not_found(
        self,
        mock_bangumi_repo,
        mock_torrent_repo,
        mock_interpreter,
    ):
        """Should handle bangumi not found."""
        mock_bangumi_repo.get_by_id.return_value = None
        
        result = await rename_bangumi(
            bangumi_id=999,
            bangumi_repo=mock_bangumi_repo,
            torrent_repo=mock_torrent_repo,
            interpreter=mock_interpreter,
        )
        
        assert result.bangumi_id == 999
        assert result.renamed_count == 0
        assert len(result.errors) == 1
        assert "not found" in result.errors[0]

    @pytest.mark.asyncio
    @patch("zen_bangumi.services.renamer.generate_rename_commands")
    async def test_rename_bangumi_no_unrenamed_torrents(
        self,
        mock_gen_commands,
        sample_bangumi_with_year,
        mock_bangumi_repo,
        mock_torrent_repo,
        mock_interpreter,
    ):
        """Should handle case with no unrenamed torrents."""
        mock_bangumi_repo.get_by_id.return_value = sample_bangumi_with_year
        mock_torrent_repo.get_unrenamed.return_value = []
        
        result = await rename_bangumi(
            bangumi_id=1,
            bangumi_repo=mock_bangumi_repo,
            torrent_repo=mock_torrent_repo,
            interpreter=mock_interpreter,
        )
        
        assert result.bangumi_id == 1
        assert result.renamed_count == 0
        assert len(result.errors) == 0
        mock_gen_commands.assert_not_called()

    @pytest.mark.asyncio
    @patch("zen_bangumi.services.renamer.generate_rename_commands")
    async def test_rename_bangumi_no_commands_generated(
        self,
        mock_gen_commands,
        sample_bangumi_with_year,
        sample_torrent_unrenamed,
        mock_bangumi_repo,
        mock_torrent_repo,
        mock_interpreter,
    ):
        """Should handle case where no commands are generated."""
        mock_bangumi_repo.get_by_id.return_value = sample_bangumi_with_year
        mock_torrent_repo.get_unrenamed.return_value = [sample_torrent_unrenamed]
        mock_gen_commands.return_value = []
        
        result = await rename_bangumi(
            bangumi_id=1,
            bangumi_repo=mock_bangumi_repo,
            torrent_repo=mock_torrent_repo,
            interpreter=mock_interpreter,
        )
        
        assert result.bangumi_id == 1
        assert result.renamed_count == 0
        assert len(result.errors) == 0
        mock_interpreter.execute.assert_not_called()

    @pytest.mark.asyncio
    @patch("zen_bangumi.services.renamer.generate_rename_commands")
    async def test_rename_bangumi_partial_success(
        self,
        mock_gen_commands,
        sample_bangumi_with_year,
        sample_torrent_unrenamed,
        mock_bangumi_repo,
        mock_torrent_repo,
        mock_interpreter,
    ):
        """Should handle partial success (some commands fail)."""
        mock_bangumi_repo.get_by_id.return_value = sample_bangumi_with_year
        mock_torrent_repo.get_unrenamed.return_value = [sample_torrent_unrenamed]
        
        rename_command = RenameFile(
            source_path="/path/source.mp4",
            target_path="/path/target.mp4",
            downloader_type="qbittorrent",
        )
        mock_gen_commands.return_value = [rename_command]
        
        effect_result = EffectResult(
            command=rename_command,
            status=EffectStatus.FAILED,
            error="Permission denied",
        )
        mock_interpreter.execute.return_value = [effect_result]
        
        result = await rename_bangumi(
            bangumi_id=1,
            bangumi_repo=mock_bangumi_repo,
            torrent_repo=mock_torrent_repo,
            interpreter=mock_interpreter,
        )
        
        assert result.bangumi_id == 1
        assert result.renamed_count == 0
        assert len(result.errors) == 1
        assert "Permission denied" in result.errors[0]

    @pytest.mark.asyncio
    async def test_rename_bangumi_exception_handling(
        self,
        mock_bangumi_repo,
        mock_torrent_repo,
        mock_interpreter,
    ):
        """Should handle unexpected exceptions."""
        mock_bangumi_repo.get_by_id.side_effect = Exception("Database error")
        
        result = await rename_bangumi(
            bangumi_id=1,
            bangumi_repo=mock_bangumi_repo,
            torrent_repo=mock_torrent_repo,
            interpreter=mock_interpreter,
        )
        
        assert result.bangumi_id == 1
        assert result.renamed_count == 0
        assert len(result.errors) == 1
        assert "Database error" in result.errors[0]

    @pytest.mark.asyncio
    @patch("zen_bangumi.services.renamer.generate_rename_commands")
    async def test_rename_bangumi_marks_renamed_in_db(
        self,
        mock_gen_commands,
        sample_bangumi_with_year,
        sample_torrent_unrenamed,
        mock_bangumi_repo,
        mock_torrent_repo,
        mock_interpreter,
    ):
        """Should mark torrents as renamed in database after success."""
        mock_bangumi_repo.get_by_id.return_value = sample_bangumi_with_year
        mock_torrent_repo.get_unrenamed.return_value = [sample_torrent_unrenamed]
        
        rename_command = RenameFile(
            source_path="/downloads/Bangumi/Frieren: Beyond Journey's End (2023)/Season 01/[Lilith-Raws] Frieren - 01 [Baha][WEB-DL][1080p][AVC AAC][CHT][MP4].mp4",
            target_path="/downloads/Bangumi/Frieren: Beyond Journey's End (2023)/Season 01/Frieren: Beyond Journey's End S01E01.mp4",
            downloader_type="qbittorrent",
        )
        mock_gen_commands.return_value = [rename_command]
        
        effect_result = EffectResult(
            command=rename_command,
            status=EffectStatus.SUCCESS,
        )
        mock_interpreter.execute.return_value = [effect_result]
        
        await rename_bangumi(
            bangumi_id=1,
            bangumi_repo=mock_bangumi_repo,
            torrent_repo=mock_torrent_repo,
            interpreter=mock_interpreter,
            downloader_type="qbittorrent",
        )
        
        # Verify mark_renamed was called with correct parameters
        mock_torrent_repo.mark_renamed.assert_called_once()
        call_args = mock_torrent_repo.mark_renamed.call_args
        assert call_args.kwargs["torrent_id"] == sample_torrent_unrenamed.id
        assert call_args.kwargs["file_count"] == 1
        assert call_args.kwargs["cloud_path"] is None

    @pytest.mark.asyncio
    @patch("zen_bangumi.services.renamer.generate_rename_commands")
    async def test_rename_bangumi_pikpak_cloud_path(
        self,
        mock_gen_commands,
        sample_bangumi_with_year,
        sample_torrent_unrenamed,
        mock_bangumi_repo,
        mock_torrent_repo,
        mock_interpreter,
    ):
        """Should set cloud_path for PikPak downloader."""
        mock_bangumi_repo.get_by_id.return_value = sample_bangumi_with_year
        mock_torrent_repo.get_unrenamed.return_value = [sample_torrent_unrenamed]
        
        rename_command = RenameFile(
            source_path=f"/cloud/{sample_torrent_unrenamed.name}",
            target_path="/cloud/target.mp4",
            downloader_type="pikpak",
        )
        mock_gen_commands.return_value = [rename_command]
        
        effect_result = EffectResult(
            command=rename_command,
            status=EffectStatus.SUCCESS,
        )
        mock_interpreter.execute.return_value = [effect_result]
        
        await rename_bangumi(
            bangumi_id=1,
            bangumi_repo=mock_bangumi_repo,
            torrent_repo=mock_torrent_repo,
            interpreter=mock_interpreter,
            downloader_type="pikpak",
        )
        
        mock_torrent_repo.mark_renamed.assert_called_once()
        call_args = mock_torrent_repo.mark_renamed.call_args
        assert call_args.kwargs["cloud_path"] == "/cloud/target.mp4"


# ============================================================================
# Tests for rename_all (Orchestrator Function)
# ============================================================================


class TestRenameAll:
    """Tests for rename_all orchestrator function."""

    @pytest.mark.asyncio
    @patch("zen_bangumi.services.renamer.rename_bangumi")
    async def test_rename_all_multiple_bangumi(
        self,
        mock_rename_bangumi,
        sample_bangumi_with_year,
        sample_bangumi_without_year,
        mock_bangumi_repo,
        mock_torrent_repo,
        mock_interpreter,
    ):
        """Should process multiple bangumi sequentially."""
        mock_bangumi_repo.get_active.return_value = [
            sample_bangumi_with_year,
            sample_bangumi_without_year,
        ]
        
        result1 = RenameResult(bangumi_id=1, renamed_count=5)
        result2 = RenameResult(bangumi_id=2, renamed_count=3)
        mock_rename_bangumi.side_effect = [result1, result2]
        
        results = await rename_all(
            bangumi_repo=mock_bangumi_repo,
            torrent_repo=mock_torrent_repo,
            interpreter=mock_interpreter,
        )
        
        assert len(results) == 2
        assert results[1].renamed_count == 5
        assert results[2].renamed_count == 3
        assert mock_rename_bangumi.call_count == 2

    @pytest.mark.asyncio
    @patch("zen_bangumi.services.renamer.rename_bangumi")
    async def test_rename_all_no_active_bangumi(
        self,
        mock_rename_bangumi,
        mock_bangumi_repo,
        mock_torrent_repo,
        mock_interpreter,
    ):
        """Should handle case with no active bangumi."""
        mock_bangumi_repo.get_active.return_value = []
        
        results = await rename_all(
            bangumi_repo=mock_bangumi_repo,
            torrent_repo=mock_torrent_repo,
            interpreter=mock_interpreter,
        )
        
        assert len(results) == 0
        mock_rename_bangumi.assert_not_called()

    @pytest.mark.asyncio
    @patch("zen_bangumi.services.renamer.rename_bangumi")
    async def test_rename_all_with_errors(
        self,
        mock_rename_bangumi,
        sample_bangumi_with_year,
        sample_bangumi_without_year,
        mock_bangumi_repo,
        mock_torrent_repo,
        mock_interpreter,
    ):
        """Should collect errors from individual bangumi renames."""
        mock_bangumi_repo.get_active.return_value = [
            sample_bangumi_with_year,
            sample_bangumi_without_year,
        ]
        
        result1 = RenameResult(bangumi_id=1, renamed_count=5, errors=[])
        result2 = RenameResult(bangumi_id=2, renamed_count=0, errors=["Parse error"])
        mock_rename_bangumi.side_effect = [result1, result2]
        
        results = await rename_all(
            bangumi_repo=mock_bangumi_repo,
            torrent_repo=mock_torrent_repo,
            interpreter=mock_interpreter,
        )
        
        assert len(results) == 2
        assert len(results[1].errors) == 0
        assert len(results[2].errors) == 1

    @pytest.mark.asyncio
    @patch("zen_bangumi.services.renamer.rename_bangumi")
    async def test_rename_all_returns_dict_by_bangumi_id(
        self,
        mock_rename_bangumi,
        sample_bangumi_with_year,
        mock_bangumi_repo,
        mock_torrent_repo,
        mock_interpreter,
    ):
        """Should return results dict keyed by bangumi ID."""
        mock_bangumi_repo.get_active.return_value = [sample_bangumi_with_year]
        
        result = RenameResult(bangumi_id=1, renamed_count=5)
        mock_rename_bangumi.return_value = result
        
        results = await rename_all(
            bangumi_repo=mock_bangumi_repo,
            torrent_repo=mock_torrent_repo,
            interpreter=mock_interpreter,
        )
        
        assert 1 in results
        assert results[1].renamed_count == 5

    @pytest.mark.asyncio
    @patch("zen_bangumi.services.renamer.rename_bangumi")
    async def test_rename_all_custom_downloader_type(
        self,
        mock_rename_bangumi,
        sample_bangumi_with_year,
        mock_bangumi_repo,
        mock_torrent_repo,
        mock_interpreter,
    ):
        """Should pass custom downloader_type to rename_bangumi."""
        mock_bangumi_repo.get_active.return_value = [sample_bangumi_with_year]
        mock_rename_bangumi.return_value = RenameResult(bangumi_id=1)
        
        await rename_all(
            bangumi_repo=mock_bangumi_repo,
            torrent_repo=mock_torrent_repo,
            interpreter=mock_interpreter,
            downloader_type="pikpak",
        )
        
        # Verify downloader_type was passed
        call_args = mock_rename_bangumi.call_args
        assert call_args.kwargs["downloader_type"] == "pikpak"

    @pytest.mark.asyncio
    @patch("zen_bangumi.services.renamer.rename_bangumi")
    async def test_rename_all_custom_base_path(
        self,
        mock_rename_bangumi,
        sample_bangumi_with_year,
        mock_bangumi_repo,
        mock_torrent_repo,
        mock_interpreter,
    ):
        """Should pass custom base_path to rename_bangumi."""
        mock_bangumi_repo.get_active.return_value = [sample_bangumi_with_year]
        mock_rename_bangumi.return_value = RenameResult(bangumi_id=1)
        
        await rename_all(
            bangumi_repo=mock_bangumi_repo,
            torrent_repo=mock_torrent_repo,
            interpreter=mock_interpreter,
            base_path="/media/anime",
        )
        
        # Verify base_path was passed
        call_args = mock_rename_bangumi.call_args
        assert call_args.kwargs["base_path"] == "/media/anime"


# ============================================================================
# Integration Tests
# ============================================================================


class TestRenameIntegration:
    """Integration tests combining multiple functions."""

    def test_gen_save_path_and_gen_rename_path_integration(
        self,
        sample_bangumi_with_year,
    ):
        """Should generate consistent paths for save and rename."""
        save_path = gen_save_path(sample_bangumi_with_year)
        rename_path = gen_rename_path(
            bangumi=sample_bangumi_with_year,
            episode=1,
            extension=".mp4",
        )
        
        assert "Season 1" in save_path
        assert rename_path.endswith(".mp4")
        assert "/" not in rename_path

    @patch("zen_bangumi.services.renamer.BangumiParser")
    def test_generate_rename_commands_idempotency(
        self,
        mock_parser_class,
        sample_bangumi_with_year,
        sample_torrent_unrenamed,
        sample_torrent_renamed,
    ):
        """Should be idempotent - already renamed torrents produce no commands."""
        mock_parser = MagicMock()
        mock_parser_class.return_value = mock_parser
        mock_parser.raw_parse.return_value = ParsedBangumi(
            raw=sample_torrent_unrenamed.name,
            episode=1,
        )
        
        # First call with unrenamed torrent
        commands1 = generate_rename_commands(
            bangumi=sample_bangumi_with_year,
            torrents=[sample_torrent_unrenamed],
            downloader_type="qbittorrent",
        )
        
        # Mark torrent as renamed
        sample_torrent_unrenamed.renamed_at = datetime.now()
        
        # Second call with same torrent (now renamed)
        commands2 = generate_rename_commands(
            bangumi=sample_bangumi_with_year,
            torrents=[sample_torrent_unrenamed],
            downloader_type="qbittorrent",
        )
        
        assert len(commands1) == 1
        assert len(commands2) == 0
