"""Tests for renamer service."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from module.domain.models.bangumi import Bangumi
from module.domain.models.torrent import Torrent, TorrentState
from module.domain.value_objects import EpisodeFile, EpisodeType, SubtitleFile
from module.services.renamer import RenamerService


class TestGenerateRenamePath:
    """Test generate_rename_path static method with all rename methods."""

    def test_regular_episode_pn_method(self):
        """Test regular episode with 'pn' method uses parsed title."""
        ep = EpisodeFile(
            media_path="[Group] Title - 01.mkv",
            title="Parsed Title",
            season=1,
            episode=1,
            suffix=".mkv",
            is_movie=False,
        )
        result = RenamerService.generate_rename_path(ep, "Official Title", "pn")
        assert result == "Parsed Title S01E01.mkv"

    def test_regular_episode_advance_method(self):
        """Test regular episode with 'advance' method uses bangumi name."""
        ep = EpisodeFile(
            media_path="[Group] Title - 01.mkv",
            title="Parsed Title",
            season=1,
            episode=1,
            suffix=".mkv",
            is_movie=False,
        )
        result = RenamerService.generate_rename_path(ep, "Official Title", "advance")
        assert result == "Official Title S01E01.mkv"

    def test_regular_episode_none_method(self):
        """Test 'none' method returns original path unchanged."""
        ep = EpisodeFile(
            media_path="[Group] Title - 01.mkv",
            title="Parsed Title",
            season=1,
            episode=1,
            suffix=".mkv",
            is_movie=False,
        )
        result = RenamerService.generate_rename_path(ep, "Official Title", "none")
        assert result == "[Group] Title - 01.mkv"

    def test_regular_episode_normal_method_deprecated(self):
        """Test 'normal' method returns original path (deprecated)."""
        ep = EpisodeFile(
            media_path="[Group] Title - 01.mkv",
            title="Parsed Title",
            season=1,
            episode=1,
            suffix=".mkv",
            is_movie=False,
        )
        result = RenamerService.generate_rename_path(ep, "Official Title", "normal")
        assert result == "[Group] Title - 01.mkv"

    def test_episode_with_version(self):
        """Test episode with version suffix (v2)."""
        ep = EpisodeFile(
            media_path="[Group] Title - 01v2.mkv",
            title="Parsed Title",
            season=1,
            episode=1,
            version=2,
            suffix=".mkv",
            is_movie=False,
        )
        result = RenamerService.generate_rename_path(ep, "Official Title", "advance")
        assert result == "Official Title S01E01v2.mkv"

    def test_episode_double_digit(self):
        """Test double-digit episode and season numbers."""
        ep = EpisodeFile(
            media_path="[Group] Title - 12.mkv",
            title="Parsed Title",
            season=10,
            episode=12,
            suffix=".mkv",
            is_movie=False,
        )
        result = RenamerService.generate_rename_path(ep, "Official Title", "pn")
        assert result == "Parsed Title S10E12.mkv"

    def test_special_episode_oad(self):
        """Test OAD special episode type."""
        ep = EpisodeFile(
            media_path="[Group] Title OAD 01.mkv",
            title="Parsed Title",
            season=1,
            episode=1,
            episode_type=EpisodeType.OAD,
            suffix=".mkv",
            is_movie=False,
        )
        result = RenamerService.generate_rename_path(ep, "Official Title", "advance")
        assert result == "Official Title OAD 01.mkv"

    def test_special_episode_ova(self):
        """Test OVA special episode type."""
        ep = EpisodeFile(
            media_path="[Group] Title OVA 02.mkv",
            title="Parsed Title",
            season=1,
            episode=2,
            episode_type=EpisodeType.OVA,
            suffix=".mkv",
            is_movie=False,
        )
        result = RenamerService.generate_rename_path(ep, "Official Title", "pn")
        assert result == "Parsed Title OVA 02.mkv"

    def test_special_episode_sp(self):
        """Test SP special episode type."""
        ep = EpisodeFile(
            media_path="[Group] Title SP 01.mkv",
            title="Parsed Title",
            season=1,
            episode=1,
            episode_type=EpisodeType.SP,
            suffix=".mkv",
            is_movie=False,
        )
        result = RenamerService.generate_rename_path(ep, "Official Title", "advance")
        assert result == "Official Title SP 01.mkv"

    def test_movie_pn_method(self):
        """Test movie with 'pn' method."""
        ep = EpisodeFile(
            media_path="[Group] Movie Title.mkv",
            title="Movie Title",
            season=1,
            episode=None,
            suffix=".mkv",
            is_movie=True,
        )
        result = RenamerService.generate_rename_path(ep, "Official Movie", "pn")
        assert result == "Movie Title.mkv"

    def test_movie_advance_method(self):
        """Test movie with 'advance' method."""
        ep = EpisodeFile(
            media_path="[Group] Movie Title.mkv",
            title="Movie Title",
            season=1,
            episode=None,
            suffix=".mkv",
            is_movie=True,
        )
        result = RenamerService.generate_rename_path(ep, "Official Movie", "advance")
        assert result == "Official Movie.mkv"

    def test_movie_none_method(self):
        """Test movie with 'none' method."""
        ep = EpisodeFile(
            media_path="[Group] Movie Title.mkv",
            title="Movie Title",
            season=1,
            episode=None,
            suffix=".mkv",
            is_movie=True,
        )
        result = RenamerService.generate_rename_path(ep, "Official Movie", "none")
        assert result == "[Group] Movie Title.mkv"

    def test_no_episode_number_single_file(self):
        """Test file without episode number (treated as single-file)."""
        ep = EpisodeFile(
            media_path="[Group] Title.mkv",
            title="Title",
            season=1,
            episode=None,
            suffix=".mkv",
            is_movie=False,
        )
        result = RenamerService.generate_rename_path(ep, "Official Title", "advance")
        assert result == "Official Title.mkv"

    def test_subtitle_pn_method(self):
        """Test subtitle file with 'pn' method."""
        sub = SubtitleFile(
            media_path="[Group] Title - 01.ass",
            title="Parsed Title",
            season=1,
            episode=1,
            language="zh",
            suffix=".ass",
            is_movie=False,
        )
        result = RenamerService.generate_rename_path(
            sub, "Official Title", "subtitle_pn"
        )
        assert result == "Parsed Title S01E01.zh.ass"

    def test_subtitle_advance_method(self):
        """Test subtitle file with 'advance' method."""
        sub = SubtitleFile(
            media_path="[Group] Title - 01.ass",
            title="Parsed Title",
            season=1,
            episode=1,
            language="zh-tw",
            suffix=".ass",
            is_movie=False,
        )
        result = RenamerService.generate_rename_path(
            sub, "Official Title", "subtitle_advance"
        )
        assert result == "Official Title S01E01.zh-tw.ass"

    def test_subtitle_none_method(self):
        """Test subtitle with 'none' method."""
        sub = SubtitleFile(
            media_path="[Group] Title - 01.ass",
            title="Parsed Title",
            season=1,
            episode=1,
            language="zh",
            suffix=".ass",
            is_movie=False,
        )
        result = RenamerService.generate_rename_path(
            sub, "Official Title", "subtitle_none"
        )
        assert result == "[Group] Title - 01.ass"

    def test_subtitle_movie(self):
        """Test subtitle for movie."""
        sub = SubtitleFile(
            media_path="[Group] Movie.ass",
            title="Movie Title",
            season=1,
            episode=None,
            language="zh",
            suffix=".ass",
            is_movie=True,
        )
        result = RenamerService.generate_rename_path(
            sub, "Official Movie", "subtitle_advance"
        )
        assert result == "Official Movie.zh.ass"


class TestRenameAll:
    """Test rename_all method with state transitions."""

    @pytest.fixture
    def mock_downloader(self):
        """Mock downloader protocol."""
        downloader = AsyncMock()
        downloader.torrents_info.return_value = [
            Mock(
                hash="abc123",
                name="[Group] Title - 01",
                save_path="/data/Bangumi/Title/Season 1",
                files=[Mock(name="[Group] Title - 01.mkv")],
            )
        ]
        downloader.torrents_rename_file = AsyncMock(return_value=True)
        return downloader

    @pytest.fixture
    def mock_parser(self):
        """Mock title parser."""
        with patch("module.services.renamer.TitleParser") as MockParser:
            parser = MockParser.return_value
            parser.torrent_parser.return_value = EpisodeFile(
                media_path="[Group] Title - 01.mkv",
                title="Parsed Title",
                season=1,
                episode=1,
                suffix=".mkv",
                is_movie=False,
            )
            yield parser

    @pytest.mark.asyncio
    async def test_rename_all_success(
        self, async_session, mock_downloader, mock_parser
    ):
        """Test rename_all successfully renames unrenamed torrents."""
        # Create test data
        bangumi = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test",
            season=1,
            group_name="Group",
            save_path="/data/Bangumi/Test Bangumi/Season 1",
        )
        async_session.add(bangumi)
        await async_session.flush()

        torrent = Torrent(
            bangumi_id=bangumi.id,
            name="[Group] Title - 01",
            url="https://example.com/torrent",
            hash="abc123",
            state=TorrentState.COMPLETED,
            downloaded=True,
            renamed_at=None,
        )
        async_session.add(torrent)
        await async_session.flush()

        # Execute rename_all
        service = RenamerService(async_session, rename_method="advance")
        result = await service.rename_all(mock_downloader)

        # Verify results
        assert len(result) == 1
        assert result[0]["torrent_id"] == torrent.id
        assert result[0]["file_count"] == 1

        # Verify torrent was marked renamed
        await async_session.refresh(torrent)
        assert torrent.renamed_at is not None
        assert torrent.renamed_file_count == 1
        assert torrent.downloaded is True

    @pytest.mark.asyncio
    async def test_rename_all_no_unrenamed(self, async_session, mock_downloader):
        """Test rename_all when no unrenamed torrents exist."""
        service = RenamerService(async_session, rename_method="advance")
        result = await service.rename_all(mock_downloader)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_rename_all_compensation_on_failure(
        self, async_session, mock_parser
    ):
        """Test compensation restores COMPLETED state on rename failure."""
        # Create test data
        bangumi = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test",
            season=1,
            group_name="Group",
            save_path="/data/Bangumi/Test/Season 1",
        )
        async_session.add(bangumi)
        await async_session.flush()

        torrent = Torrent(
            bangumi_id=bangumi.id,
            name="[Group] Title - 01",
            url="https://example.com/torrent",
            hash="abc123",
            state=TorrentState.COMPLETED,
            downloaded=True,
            renamed_at=None,
        )
        async_session.add(torrent)
        await async_session.flush()

        # Mock downloader to fail rename
        mock_downloader = AsyncMock()
        mock_downloader.torrents_info.return_value = [
            Mock(
                hash="abc123",
                name="[Group] Title - 01",
                save_path="/data/Bangumi/Test/Season 1",
                files=[Mock(name="[Group] Title - 01.mkv")],
            )
        ]
        mock_downloader.torrents_rename_file = AsyncMock(return_value=False)

        # Execute rename_all
        service = RenamerService(async_session, rename_method="advance")
        result = await service.rename_all(mock_downloader)

        # Verify no successful renames
        assert len(result) == 0

        await async_session.refresh(torrent)
        assert torrent.renamed_at is None


class TestRenameBangumi:
    """Test rename_bangumi method with retrigger logic."""

    @pytest.fixture
    def mock_downloader(self):
        """Mock downloader protocol."""
        downloader = AsyncMock()
        downloader.torrents_info.return_value = [
            Mock(
                hash="abc123",
                name="[Group] Title - 01",
                save_path="/data/Bangumi/Old Title/Season 1",
                files=[Mock(name="[Group] Title - 01.mkv")],
            )
        ]
        downloader.torrents_rename_file = AsyncMock(return_value=True)
        downloader.move_torrent = AsyncMock(return_value=True)
        return downloader

    @pytest.fixture
    def mock_parser(self):
        """Mock title parser."""
        with patch("module.services.renamer.TitleParser") as MockParser:
            parser = MockParser.return_value
            parser.torrent_parser.return_value = EpisodeFile(
                media_path="[Group] Title - 01.mkv",
                title="Parsed Title",
                season=1,
                episode=1,
                suffix=".mkv",
                is_movie=False,
            )
            yield parser

    @pytest.mark.asyncio
    async def test_rename_bangumi_basic(
        self, async_session, mock_downloader, mock_parser
    ):
        """Test rename_bangumi for specific bangumi."""
        # Create test data
        bangumi = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test",
            season=1,
            group_name="Group",
            save_path="/data/Bangumi/Test Bangumi/Season 1",
        )
        async_session.add(bangumi)
        await async_session.flush()

        torrent = Torrent(
            bangumi_id=bangumi.id,
            name="[Group] Title - 01",
            url="https://example.com/torrent",
            hash="abc123",
            state=TorrentState.COMPLETED,
            renamed_at=None,
        )
        async_session.add(torrent)
        await async_session.flush()

        # Execute rename_bangumi
        service = RenamerService(async_session, rename_method="advance")
        result = await service.rename_bangumi(
            mock_downloader, bangumi.id, retrigger=False
        )

        # Verify results
        assert len(result) == 1
        assert result[0]["torrent_id"] == torrent.id

    @pytest.mark.asyncio
    async def test_rename_bangumi_with_retrigger(
        self, async_session, mock_downloader, mock_parser
    ):
        """Test rename_bangumi with retrigger clears rename status first."""
        # Create test data
        bangumi = Bangumi(
            official_title="Test Bangumi",
            title_raw="Test",
            season=1,
            group_name="Group",
            save_path="/data/Bangumi/Test/Season 1",
        )
        async_session.add(bangumi)
        await async_session.flush()

        # Torrent already renamed
        torrent = Torrent(
            bangumi_id=bangumi.id,
            name="[Group] Title - 01",
            url="https://example.com/torrent",
            hash="abc123",
            state=TorrentState.RENAMED,
            renamed_at=datetime.now(),
            renamed_file_count=1,
        )
        async_session.add(torrent)
        await async_session.flush()

        # Execute rename_bangumi with retrigger
        service = RenamerService(async_session, rename_method="advance")
        result = await service.rename_bangumi(
            mock_downloader, bangumi.id, retrigger=True
        )

        # Verify rename status was cleared
        await async_session.refresh(torrent)
        assert torrent.renamed_at is not None  # Re-renamed
        assert torrent.renamed_file_count == 1

    @pytest.mark.asyncio
    async def test_rename_bangumi_moves_torrents_if_path_changed(
        self, async_session, mock_downloader, mock_parser
    ):
        """Test rename_bangumi moves torrents when save_path changes."""
        # Create test data
        bangumi = Bangumi(
            official_title="New Title",
            title_raw="Test",
            season=2,  # Season changed
            group_name="Group",
            save_path="/data/Bangumi/New Title/Season 2",
        )
        async_session.add(bangumi)
        await async_session.flush()

        torrent = Torrent(
            bangumi_id=bangumi.id,
            name="[Group] Title - 01",
            url="https://example.com/torrent",
            hash="abc123",
            state=TorrentState.COMPLETED,
            renamed_at=None,
        )
        async_session.add(torrent)
        await async_session.flush()

        # Execute rename_bangumi
        service = RenamerService(async_session, rename_method="advance")
        await service.rename_bangumi(mock_downloader, bangumi.id, retrigger=False)

        # Verify move_torrent was called
        mock_downloader.move_torrent.assert_called_once()
        call_args = mock_downloader.move_torrent.call_args[0]
        assert "abc123" in call_args[0]
        assert call_args[1] == "/data/Bangumi/New Title/Season 2"
