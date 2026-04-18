"""Tests for renamer service."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.domain.models.torrent import Torrent, TorrentState
from module.domain.value_objects import EpisodeFile, EpisodeType, SubtitleFile
from module.services.renamer import RenamerService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _add_series(session, *, title: str, season: int = 1, root_path: str | None = None) -> Series:
    s = Series(
        canonical_title=title,
        normalized_title=title.lower().replace(" ", "_"),
        season=season,
        root_path=root_path or f"/data/Bangumi/{title}/Season {season}",
    )
    session.add(s)
    await session.flush()
    return s


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
        self, db_session, mock_downloader, mock_parser
    ):
        """Test rename_all successfully renames unrenamed torrents."""
        series = await _add_series(
            db_session, title="Test Bangumi",
            root_path="/data/Bangumi/Test Bangumi/Season 1",
        )
        bangumi = Bangumi(
            series_id=series.id,
            group_name="Group",
        )
        db_session.add(bangumi)
        await db_session.flush()

        torrent = Torrent(
            bangumi_id=bangumi.id,
            name="[Group] Title - 01",
            url="https://example.com/torrent",
            hash="abc123",
            state=TorrentState.COMPLETED,
            downloaded=True,
            renamed_at=None,
        )
        db_session.add(torrent)
        await db_session.flush()

        service = RenamerService(db_session, rename_method="advance")
        result = await service.rename_all(mock_downloader)

        assert len(result) == 1
        assert result[0]["torrent_id"] == torrent.id
        assert result[0]["file_count"] == 1

        await db_session.refresh(torrent)
        assert torrent.renamed_at is not None
        assert torrent.renamed_file_count == 1
        assert torrent.downloaded is True

    @pytest.mark.asyncio
    async def test_rename_all_no_unrenamed(self, db_session, mock_downloader):
        """Test rename_all when no unrenamed torrents exist."""
        service = RenamerService(db_session, rename_method="advance")
        result = await service.rename_all(mock_downloader)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_rename_all_compensation_on_failure(
        self, db_session, mock_parser
    ):
        """Test compensation restores COMPLETED state on rename failure."""
        series = await _add_series(
            db_session, title="Test Bangumi",
            root_path="/data/Bangumi/Test/Season 1",
        )
        bangumi = Bangumi(series_id=series.id, group_name="Group")
        db_session.add(bangumi)
        await db_session.flush()

        torrent = Torrent(
            bangumi_id=bangumi.id,
            name="[Group] Title - 01",
            url="https://example.com/torrent",
            hash="abc123",
            state=TorrentState.COMPLETED,
            downloaded=True,
            renamed_at=None,
        )
        db_session.add(torrent)
        await db_session.flush()

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

        service = RenamerService(db_session, rename_method="advance")
        result = await service.rename_all(mock_downloader)

        assert len(result) == 0

        await db_session.refresh(torrent)
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
        self, db_session, mock_downloader, mock_parser
    ):
        """Test rename_bangumi for specific bangumi."""
        series = await _add_series(
            db_session, title="Test Bangumi",
            root_path="/data/Bangumi/Test Bangumi/Season 1",
        )
        bangumi = Bangumi(series_id=series.id, group_name="Group")
        db_session.add(bangumi)
        await db_session.flush()

        torrent = Torrent(
            bangumi_id=bangumi.id,
            name="[Group] Title - 01",
            url="https://example.com/torrent",
            hash="abc123",
            state=TorrentState.COMPLETED,
            renamed_at=None,
        )
        db_session.add(torrent)
        await db_session.flush()

        service = RenamerService(db_session, rename_method="advance")
        result = await service.rename_bangumi(
            mock_downloader, bangumi.id, retrigger=False
        )

        assert len(result) == 1
        assert result[0]["torrent_id"] == torrent.id

    @pytest.mark.asyncio
    async def test_rename_bangumi_with_retrigger(
        self, db_session, mock_downloader, mock_parser
    ):
        """Test rename_bangumi with retrigger clears rename status first."""
        series = await _add_series(
            db_session, title="Test Bangumi",
            root_path="/data/Bangumi/Test/Season 1",
        )
        bangumi = Bangumi(series_id=series.id, group_name="Group")
        db_session.add(bangumi)
        await db_session.flush()

        torrent = Torrent(
            bangumi_id=bangumi.id,
            name="[Group] Title - 01",
            url="https://example.com/torrent",
            hash="abc123",
            state=TorrentState.RENAMED,
            renamed_at=datetime.now(),
            renamed_file_count=1,
        )
        db_session.add(torrent)
        await db_session.flush()

        service = RenamerService(db_session, rename_method="advance")
        result = await service.rename_bangumi(
            mock_downloader, bangumi.id, retrigger=True
        )

        await db_session.refresh(torrent)
        assert torrent.renamed_at is not None  # Re-renamed
        assert torrent.renamed_file_count == 1

    @pytest.mark.asyncio
    async def test_rename_bangumi_moves_torrents_if_path_changed(
        self, db_session, mock_downloader, mock_parser
    ):
        """Test rename_bangumi moves torrents when save_path changes."""
        # root_path is the base directory (without Season N).
        # save_path property appends "Season {series.season}" automatically.
        series = await _add_series(
            db_session, title="New Title", season=2,
            root_path="/data/Bangumi/New Title",
        )
        bangumi = Bangumi(series_id=series.id, group_name="Group")
        db_session.add(bangumi)
        await db_session.flush()

        torrent = Torrent(
            bangumi_id=bangumi.id,
            name="[Group] Title - 01",
            url="https://example.com/torrent",
            hash="abc123",
            state=TorrentState.COMPLETED,
            renamed_at=None,
        )
        db_session.add(torrent)
        await db_session.flush()

        service = RenamerService(db_session, rename_method="advance")
        await service.rename_bangumi(mock_downloader, bangumi.id, retrigger=False)

        mock_downloader.move_torrent.assert_called_once()
        call_args = mock_downloader.move_torrent.call_args[0]
        assert "abc123" in call_args[0]
        assert call_args[1] == "/data/Bangumi/New Title/Season 2"


class TestSubtitleRenameNaming:
    @pytest.fixture
    def mock_parser(self):
        with patch("module.services.renamer.TitleParser") as MockParser:
            parser = MockParser.return_value
            parser.torrent_parser.return_value = SubtitleFile(
                media_path="[Collection] Folder Name/sub1.ass",
                group=None,
                title="Parsed Subtitle",
                season=1,
                episode=1,
                version=None,
                language="zh",
                suffix=".ass",
                is_movie=False,
                episode_type=None,
            )
            yield parser

    @pytest.mark.asyncio
    async def test_rename_subtitles_no_torrent_name_kwarg(
        self, db_session, mock_parser
    ):
        series = await _add_series(
            db_session, title="Test Bangumi",
            root_path="/data/Bangumi/Test/Season 1",
        )
        bangumi = Bangumi(series_id=series.id, group_name="Group")
        db_session.add(bangumi)
        await db_session.flush()

        torrent_info = Mock(
            hash="abc123",
            name="[Collection] Folder Name",
            save_path="/data/Bangumi/Test/Season 1",
            files=[Mock(name="[Collection] Folder Name/sub1.ass")],
        )

        downloader = AsyncMock()
        downloader.torrents_rename_file = AsyncMock(return_value=True)

        service = RenamerService(db_session, rename_method="advance")
        await service._rename_subtitles(
            torrent_info,
            ["[Collection] Folder Name/sub1.ass"],
            bangumi,
            downloader,
        )

        mock_parser.torrent_parser.assert_called_once()
        call_kwargs = mock_parser.torrent_parser.call_args[1]
        assert "torrent_name" not in call_kwargs
        assert call_kwargs["torrent_path"] == "[Collection] Folder Name/sub1.ass"
        assert call_kwargs["season"] == 1
        assert call_kwargs["file_type"] == "subtitle"


class TestRenameAllMediaZero:
    @pytest.fixture
    def mock_downloader(self):
        downloader = AsyncMock()
        downloader.torrents_info.return_value = [
            Mock(
                hash="abc123",
                name="[Group] Subtitles Only",
                save_path="/data/Bangumi/Test/Season 1",
                files=[Mock(name="sub1.ass"), Mock(name="sub2.ass")],
            )
        ]
        downloader.torrents_rename_file = AsyncMock(return_value=True)
        return downloader

    @pytest.fixture
    def mock_parser(self):
        with patch("module.services.renamer.TitleParser") as MockParser:
            parser = MockParser.return_value
            parser.torrent_parser.return_value = SubtitleFile(
                media_path="sub1.ass",
                group=None,
                title="Parsed Sub",
                season=1,
                episode=1,
                version=None,
                language="zh",
                suffix=".ass",
                is_movie=False,
                episode_type=None,
            )
            yield parser

    @pytest.mark.asyncio
    async def test_rename_all_media_zero_with_subtitles(
        self, db_session, mock_downloader, mock_parser
    ):
        series = await _add_series(
            db_session, title="Test Bangumi",
            root_path="/data/Bangumi/Test/Season 1",
        )
        bangumi = Bangumi(series_id=series.id, group_name="Group")
        db_session.add(bangumi)
        await db_session.flush()

        torrent = Torrent(
            bangumi_id=bangumi.id,
            name="[Group] Subtitles Only",
            url="https://example.com/torrent",
            hash="abc123",
            state=TorrentState.COMPLETED,
            downloaded=True,
            renamed_at=None,
        )
        db_session.add(torrent)
        await db_session.flush()

        service = RenamerService(db_session, rename_method="advance")
        with patch.object(service, "_classify_files", return_value=([], ["sub1.ass"])):
            with patch.object(service, "_rename_subtitles", new_callable=AsyncMock):
                result = await service.rename_all(mock_downloader)

        assert len(result) == 1
        assert result[0]["torrent_id"] == torrent.id
        assert result[0]["file_count"] == 0

        await db_session.refresh(torrent)
        assert torrent.renamed_at is not None
        assert torrent.renamed_file_count == 0

    @pytest.mark.asyncio
    async def test_rename_all_media_zero_no_subtitles(
        self, db_session, mock_downloader
    ):
        mock_downloader.torrents_info.return_value = [
            Mock(
                hash="abc123",
                name="[Group] Empty Torrent",
                save_path="/data/Bangumi/Test/Season 1",
                files=[],
            )
        ]

        series = await _add_series(
            db_session, title="Test Bangumi",
            root_path="/data/Bangumi/Test/Season 1",
        )
        bangumi = Bangumi(series_id=series.id, group_name="Group")
        db_session.add(bangumi)
        await db_session.flush()

        torrent = Torrent(
            bangumi_id=bangumi.id,
            name="[Group] Empty Torrent",
            url="https://example.com/torrent",
            hash="abc123",
            state=TorrentState.COMPLETED,
            downloaded=True,
            renamed_at=None,
        )
        db_session.add(torrent)
        await db_session.flush()

        service = RenamerService(db_session, rename_method="advance")
        result = await service.rename_all(mock_downloader)

        assert len(result) == 1
        assert result[0]["torrent_id"] == torrent.id
        assert result[0]["file_count"] == 0

        await db_session.refresh(torrent)
        assert torrent.renamed_at is not None
        assert torrent.renamed_file_count == 0
