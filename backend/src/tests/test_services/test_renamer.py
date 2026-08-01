"""Tests for renamer service."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.domain.models.torrent import RenameStatus, Torrent, TorrentState
from module.domain.value_objects import EpisodeFile, EpisodeType, SubtitleFile
from module.services.downloader.interface import RenameOutcome, TorrentFile, TorrentInfo
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


MULTI_VERSION_TORRENTS = [
    pytest.param(
        {
            "episode": 1,
            "hash": "9feaaa14189495fd55cb38f6c4fffc21a7b3239c",
            "root": (
                "[TV版&无修版] 令和妖神斑小姐 - EP01 "
                "[简／繁] (1080p H.264 AAC SRTx2)"
            ),
            "tv_name": "【7月】令和妖神斑小姐 01【TV Ver.】.mp4",
            "tv_size": 752_680_718,
            "padding_size": 196_850,
            "alternate_name": (
                "【7月】令和妖神斑小姐 01"
                "【在令和时代这样没问题吗！？Ver.】.mp4"
            ),
            "alternate_size": 1_448_320_983,
        },
        id="ep01",
    ),
    pytest.param(
        {
            "episode": 2,
            "hash": "dc0492333d459197efaff3a5d68939313cc300bd",
            "root": (
                "[TV版&无修版] 令和妖神斑小姐 - EP02 "
                "[简／繁] (1080p H.264 AAC SRTx2)"
            ),
            "tv_name": "【7月】令和的斑小姐 02【TV Ver.】.mp4",
            "tv_size": 752_676_167,
            "padding_size": 201_401,
            "alternate_name": (
                "【7月】令和的斑小姐 02"
                "【在令和时代这样没问题吗！？Ver.】.mp4"
            ),
            "alternate_size": 1_447_003_404,
        },
        id="ep02",
    ),
    pytest.param(
        {
            "episode": 4,
            "hash": "4fcca833aafa0e7d006ed9f76d3f5f2c676c3d41",
            "root": (
                "[TV版&无修版] 令和的斑小姐 - EP04 "
                "[简／繁] (1080p H.264 AAC SRTx2)"
            ),
            "tv_name": "【7月】令和的斑小姐 04【TV Ver.】.mp4",
            "tv_size": 752_481_599,
            "padding_size": 395_969,
            "alternate_name": (
                "【7月】令和的斑小姐 04"
                "【在令和时代这样没问题吗！？Ver.】.mp4"
            ),
            "alternate_size": 1_448_396_864,
        },
        id="ep04",
    ),
    pytest.param(
        {
            "episode": 5,
            "hash": "58e0ed2ee7005e95391e09c270942d7fbd5ce096",
            "root": (
                "[TV版&无修版] 令和的斑小姐 - EP05 "
                "[简／繁] (1080p H.264 AAC SRTx2)"
            ),
            "tv_name": "【7月】令和的斑小姐 05【TV Ver.】.mp4",
            "tv_size": 752_545_587,
            "padding_size": 331_981,
            "alternate_name": (
                "【7月】令和的斑小姐 05"
                "【在令和时代这样没问题吗！？Ver.】.mp4"
            ),
            "alternate_size": 1_449_416_253,
        },
        id="ep05",
    ),
]


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

    def test_regular_episode_advance_method_sanitizes_illegal_chars(self):
        """Test advance rename sanitizes PikPak-illegal chars in target filename."""
        ep = EpisodeFile(
            media_path="[Group] Title - 01.mp4",
            title="Parsed Title",
            season=1,
            episode=1,
            suffix=".mp4",
            is_movie=False,
        )
        result = RenamerService.generate_rename_path(
            ep, "没有辣妹会对阿宅温柔!?", "advance"
        )
        assert result == "没有辣妹会对阿宅温柔!？ S01E01.mp4"

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
        downloader.torrents_rename_file = AsyncMock(return_value=RenameOutcome.OK)
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
    async def test_rename_all_does_not_add_edition_to_single_media_file(
        self, db_session
    ):
        """A terminal source label alone does not change normal naming."""
        series = await _add_series(db_session, title="Test Bangumi")
        bangumi = Bangumi(series_id=series.id, group_name="Group")
        db_session.add(bangumi)
        await db_session.flush()
        torrent = Torrent(
            bangumi_id=bangumi.id,
            name="[Group] Title - EP04【TV Ver.】",
            url="https://example.com/single.torrent",
            hash="single04",
            state=TorrentState.COMPLETED,
            downloaded=True,
            renamed_at=None,
        )
        db_session.add(torrent)
        await db_session.flush()

        source_path = "[Group] Title - EP04【TV Ver.】.mp4"
        downloader = AsyncMock()
        downloader.torrents_info.return_value = [
            TorrentInfo(
                hash="single04",
                name="[Group] Title - EP04【TV Ver.】",
                state="completed",
                progress=1.0,
                save_path="Bangumi/Test Bangumi/Season 1",
                size=100,
                files=[TorrentFile(name=source_path, size=100, path=source_path)],
            )
        ]
        downloader.torrents_rename_file.return_value = RenameOutcome.OK

        await RenamerService(db_session, rename_method="advance").rename_all(
            downloader
        )

        downloader.torrents_rename_file.assert_awaited_once_with(
            "single04",
            source_path,
            "Test Bangumi S01E04.mp4",
        )

    @pytest.mark.asyncio
    async def test_rename_all_uses_plain_name_for_real_ep03_single_file(
        self, db_session
    ):
        """The real EP03 single-file metainfo remains an ordinary episode."""
        torrent_hash = "fe5b3207710966052e1e2a73c33e8af103f92414"
        source_path = "【7月】令和的斑小姐 03.mp4"
        series = await _add_series(db_session, title="令和的斑小姐")
        bangumi = Bangumi(series_id=series.id, group_name="Nix-Raws")
        db_session.add(bangumi)
        await db_session.flush()
        torrent = Torrent(
            bangumi_id=bangumi.id,
            name=(
                "令和的斑小姐 - EP03 [简／繁] "
                "(1080p H.264 AAC SRTx2)"
            ),
            url="https://example.com/ep03.torrent",
            hash=torrent_hash,
            state=TorrentState.COMPLETED,
            downloaded=True,
            renamed_at=None,
        )
        db_session.add(torrent)
        await db_session.flush()

        downloader = AsyncMock()
        downloader.torrents_info.return_value = [
            TorrentInfo(
                hash=torrent_hash,
                name=source_path,
                state="completed",
                progress=1.0,
                save_path="Bangumi/令和的斑小姐/Season 1",
                size=1_448_499_020,
                files=[
                    TorrentFile(
                        name=source_path,
                        size=1_448_499_020,
                        path=source_path,
                    )
                ],
            )
        ]
        downloader.torrents_rename_file.return_value = RenameOutcome.OK

        await RenamerService(db_session, rename_method="advance").rename_all(
            downloader
        )

        downloader.torrents_rename_file.assert_awaited_once_with(
            torrent_hash,
            source_path,
            "令和的斑小姐 S01E03.mp4",
        )

    @pytest.mark.asyncio
    async def test_rename_all_keeps_normal_multi_episode_collection_names(
        self, db_session
    ):
        """Unique episode targets in a collection keep the legacy names."""
        series = await _add_series(db_session, title="Test Bangumi")
        bangumi = Bangumi(series_id=series.id, group_name="Group")
        db_session.add(bangumi)
        await db_session.flush()
        torrent = Torrent(
            bangumi_id=bangumi.id,
            name="[Group] Test Bangumi [01-02]",
            url="https://example.com/collection.torrent",
            hash="collection0102",
            state=TorrentState.COMPLETED,
            downloaded=True,
            renamed_at=None,
        )
        db_session.add(torrent)
        await db_session.flush()

        source_paths = [
            "[Group] Test Bangumi [01-02]/[Group] Test Bangumi - 01.mkv",
            "[Group] Test Bangumi [01-02]/[Group] Test Bangumi - 02.mkv",
        ]
        downloader = AsyncMock()
        downloader.torrents_info.return_value = [
            TorrentInfo(
                hash="collection0102",
                name="[Group] Test Bangumi [01-02]",
                state="completed",
                progress=1.0,
                save_path="Bangumi/Test Bangumi/Season 1",
                size=200,
                files=[
                    TorrentFile(name=path, size=100, path=path)
                    for path in source_paths
                ],
            )
        ]
        downloader.torrents_rename_file.return_value = RenameOutcome.OK

        await RenamerService(db_session, rename_method="advance").rename_all(
            downloader
        )

        assert [
            call.args[2]
            for call in downloader.torrents_rename_file.await_args_list
        ] == [
            "Test Bangumi S01E01.mkv",
            "Test Bangumi S01E02.mkv",
        ]

    @pytest.mark.asyncio
    async def test_rename_all_leaves_ambiguous_collection_unchanged(
        self, db_session
    ):
        """Same-target files without distinct labels remain a conflict."""
        series = await _add_series(db_session, title="Test Bangumi")
        bangumi = Bangumi(series_id=series.id, group_name="Group")
        db_session.add(bangumi)
        await db_session.flush()
        torrent = Torrent(
            bangumi_id=bangumi.id,
            name="[Group] Test Bangumi - EP04",
            url="https://example.com/ambiguous.torrent",
            hash="ambiguous04",
            state=TorrentState.COMPLETED,
            downloaded=True,
            renamed_at=None,
        )
        db_session.add(torrent)
        await db_session.flush()

        source_files = {
            "[Group] Test Bangumi - EP04/source-a.mp4": 100,
            "[Group] Test Bangumi - EP04/source-b.mp4": 200,
        }

        class FakeCloudDownloader:
            def __init__(self):
                self.files = dict(source_files)

            async def torrents_info(self, **_kwargs):
                return [
                    TorrentInfo(
                        hash="ambiguous04",
                        name="[Group] Test Bangumi - EP04",
                        state="completed",
                        progress=1.0,
                        save_path="Bangumi/Test Bangumi/Season 1",
                        size=300,
                        files=[
                            TorrentFile(name=path, size=size, path=path)
                            for path, size in self.files.items()
                        ],
                    )
                ]

            async def torrents_rename_file(self, _hash, old_path, new_path):
                self.files[new_path] = self.files.pop(old_path)
                return RenameOutcome.OK

        downloader = FakeCloudDownloader()

        result = await RenamerService(
            db_session, rename_method="advance"
        ).rename_all(downloader)

        assert downloader.files == source_files
        assert result == [
            {
                "torrent_id": torrent.id,
                "file_count": 0,
                "conflict": "Test Bangumi.mp4",
            }
        ]
        await db_session.refresh(torrent)
        assert torrent.rename_status == RenameStatus.CONFLICT

    @pytest.mark.parametrize("case", MULTI_VERSION_TORRENTS)
    @pytest.mark.asyncio
    async def test_rename_all_preserves_source_labels_for_same_episode_versions(
        self, db_session, case
    ):
        """Real two-version torrent metainfo keeps both source labels."""
        torrent_hash = case["hash"]
        root_name = case["root"]
        tv_path = f'{root_name}/{case["tv_name"]}'
        alternate_path = f'{root_name}/{case["alternate_name"]}'
        padding_path = f"{root_name}/_____padding_file_0_____"

        series = await _add_series(
            db_session,
            title="令和的斑小姐",
            root_path="Bangumi/令和的斑小姐",
        )
        bangumi = Bangumi(series_id=series.id, group_name="Nix-Raws")
        db_session.add(bangumi)
        await db_session.flush()
        torrent = Torrent(
            bangumi_id=bangumi.id,
            name=root_name,
            url=f'https://example.com/ep{case["episode"]:02d}.torrent',
            hash=torrent_hash,
            state=TorrentState.COMPLETED,
            downloaded=True,
            renamed_at=None,
        )
        db_session.add(torrent)
        await db_session.flush()

        class FakeCloudDownloader:
            def __init__(self):
                self.files = {
                    tv_path: case["tv_size"],
                    padding_path: case["padding_size"],
                    alternate_path: case["alternate_size"],
                }

            async def torrents_info(self, **_kwargs):
                return [
                    TorrentInfo(
                        hash=torrent_hash,
                        name=root_name,
                        state="completed",
                        progress=1.0,
                        save_path="Bangumi/令和的斑小姐/Season 1",
                        size=sum(self.files.values()),
                        files=[
                            TorrentFile(name=path, size=size, path=path)
                            for path, size in self.files.items()
                        ],
                    )
                ]

            async def torrents_rename_file(self, _hash, old_path, new_path):
                if old_path not in self.files or new_path in self.files:
                    return RenameOutcome.CONFLICT
                self.files[new_path] = self.files.pop(old_path)
                return RenameOutcome.OK

        downloader = FakeCloudDownloader()
        service = RenamerService(db_session, rename_method="advance")

        result = await service.rename_all(downloader)

        expected_media = {
            f'令和的斑小姐 S01E{case["episode"]:02d} - TV Ver.mp4': case[
                "tv_size"
            ],
            (
                f'令和的斑小姐 S01E{case["episode"]:02d} - '
                "在令和时代这样没问题吗！？Ver.mp4"
            ): case["alternate_size"],
        }
        assert {
            path: size
            for path, size in downloader.files.items()
            if path.lower().endswith(".mp4")
        } == expected_media
        assert result == [{"torrent_id": torrent.id, "file_count": 2}]

        await db_session.refresh(torrent)
        assert torrent.rename_status == RenameStatus.DONE
        assert torrent.renamed_file_count == 2

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
        mock_downloader.torrents_rename_file = AsyncMock(return_value=RenameOutcome.ERROR)

        service = RenamerService(db_session, rename_method="advance")
        result = await service.rename_all(mock_downloader)

        assert len(result) == 0

        await db_session.refresh(torrent)
        assert torrent.renamed_at is None

    @pytest.mark.asyncio
    async def test_rename_all_records_subtitle_conflict(
        self, db_session
    ):
        series = await _add_series(
            db_session,
            title="Test Bangumi",
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
            downloaded=True,
            renamed_at=None,
        )
        db_session.add(torrent)
        await db_session.flush()

        downloader = AsyncMock()
        downloader.torrents_info.return_value = [
            Mock(
                hash="abc123",
                name="[Group] Title - 01",
                save_path="/data/Bangumi/Test Bangumi/Season 1",
                files=[
                    SimpleNamespace(name="[Group] Title - 01.mkv"),
                    SimpleNamespace(name="[Group] Title - 01.ass"),
                ],
            )
        ]
        downloader.torrents_rename_file = AsyncMock(
            side_effect=[RenameOutcome.OK, RenameOutcome.CONFLICT]
        )

        def parse_side_effect(**kwargs):
            if kwargs.get("file_type") == "subtitle":
                return SubtitleFile(
                    media_path="[Group] Title - 01.ass",
                    group=None,
                    title="Parsed Title",
                    season=1,
                    episode=1,
                    language="zh",
                    suffix=".ass",
                    is_movie=False,
                    episode_type=None,
                )
            return EpisodeFile(
                media_path="[Group] Title - 01.mkv",
                title="Parsed Title",
                season=1,
                episode=1,
                suffix=".mkv",
                is_movie=False,
            )

        with patch("module.services.renamer.TitleParser") as MockParser:
            MockParser.return_value.torrent_parser.side_effect = parse_side_effect
            service = RenamerService(db_session, rename_method="advance")
            result = await service.rename_all(downloader)

        assert result == [{
            "torrent_id": torrent.id,
            "file_count": 0,
            "conflict": "Test Bangumi S01E01.zh.ass",
        }]

        await db_session.refresh(torrent)
        assert torrent.renamed_at is None
        assert torrent.rename_status == RenameStatus.CONFLICT
        assert torrent.rename_conflict_target == "Test Bangumi S01E01.zh.ass"


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
        downloader.torrents_rename_file = AsyncMock(return_value=RenameOutcome.OK)
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
        await service.rename_bangumi(
            mock_downloader, bangumi.id, retrigger=True
        )

        await db_session.refresh(torrent)
        assert torrent.renamed_at is not None  # Re-renamed
        assert torrent.renamed_file_count == 1

    @pytest.mark.asyncio
    async def test_rename_bangumi_retrigger_keeps_failed_torrent_retryable(
        self, db_session, mock_downloader, mock_parser
    ):
        series = await _add_series(
            db_session,
            title="Test Bangumi",
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

        mock_downloader.torrents_rename_file.return_value = RenameOutcome.ERROR

        service = RenamerService(db_session, rename_method="advance")
        result = await service.rename_bangumi(
            mock_downloader, bangumi.id, retrigger=True
        )

        assert result == []

        await db_session.refresh(torrent)
        assert torrent.renamed_at is None
        assert torrent.renamed_file_count is None

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
        downloader.torrents_rename_file = AsyncMock(return_value=RenameOutcome.OK)

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
        downloader.torrents_rename_file = AsyncMock(return_value=RenameOutcome.OK)
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
            with patch.object(
                service,
                "_rename_subtitles",
                new_callable=AsyncMock,
                return_value=(RenameOutcome.OK, None),
            ):
                result = await service.rename_all(mock_downloader)

        assert result == []

        await db_session.refresh(torrent)
        assert torrent.renamed_at is None
        assert torrent.renamed_file_count is None

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

        assert result == []

        await db_session.refresh(torrent)
        assert torrent.renamed_at is None
        assert torrent.renamed_file_count is None
