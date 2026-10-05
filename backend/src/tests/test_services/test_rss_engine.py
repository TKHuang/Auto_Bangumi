"""Tests for RSS Engine Service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from module.domain.models.bangumi import Bangumi
from module.domain.models.rss import RSSItem
from module.domain.models.series import Series
from module.domain.models.torrent import Torrent, TorrentState
from module.services.rss_engine import RSSEngine


@pytest.fixture
def mock_downloader():
    """Mock downloader implementing DownloaderProtocol."""
    downloader = AsyncMock()
    downloader.add_torrents = AsyncMock(return_value=True)
    downloader.auth = AsyncMock(return_value=True)
    return downloader


@pytest.fixture
def sample_rss():
    """Sample RSS item."""
    return RSSItem(
        id=1,
        name="Test RSS",
        url="https://example.com/rss",
        aggregate=False,
        parser="mikan",
        enabled=True,
    )


@pytest.fixture
def sample_bangumi():
    """Sample bangumi (no dropped columns)."""
    return Bangumi(
        id=1,
        group_name="TestGroup",
        rss_link="https://example.com/rss",
        rss_id=1,
        filter="",
        added=False,
        deleted=False,
        eps_collect=True,
        offset=0,
        pending_review=False,
    )


@pytest.fixture
def sample_torrent():
    """Sample torrent."""
    return Torrent(
        id=1,
        name="[TestGroup] Test Anime - 01 [1080p]",
        url="https://example.com/torrent.torrent",
        homepage="https://example.com/episode/1",
        hash="a1b2c3d4e5f6",
        state=TorrentState.PENDING,
        bangumi_id=1,
        rss_id=1,
        downloaded=False,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _add_series(session, title: str = "Test Anime", season: int = 1) -> Series:
    s = Series(
        canonical_title=title,
        normalized_title=title.lower().replace(" ", "_"),
        season=season,
        root_path=f"/mnt/{title.replace(' ', '_')}",
        pending_review=False,
    )
    session.add(s)
    await session.flush()
    return s


class TestParseRSSFeed:
    """Test parse_rss_feed function."""

    @pytest.mark.asyncio
    async def test_parse_rss_feed_success(self):
        """Test successful RSS feed parsing."""
        url = "https://example.com/rss"

        # Mock RequestContent
        with patch("module.services.rss_engine.RequestContent") as mock_request:
            mock_instance = MagicMock()
            mock_request.return_value.__enter__.return_value = mock_instance

            # Mock get_torrents to return sample torrents
            mock_instance.get_torrents.return_value = [
                Torrent(
                    name="[TestGroup] Test Anime - 01 [1080p]",
                    url="https://example.com/torrent1.torrent",
                    homepage="https://example.com/episode/1",
                    hash="hash1",
                ),
                Torrent(
                    name="[TestGroup] Test Anime - 02 [1080p]",
                    url="https://example.com/torrent2.torrent",
                    homepage="https://example.com/episode/2",
                    hash="hash2",
                ),
            ]

            torrents = await RSSEngine.parse_rss_feed(url)

            assert len(torrents) == 2
            assert torrents[0].name == "[TestGroup] Test Anime - 01 [1080p]"
            assert torrents[1].name == "[TestGroup] Test Anime - 02 [1080p]"
            mock_instance.get_torrents.assert_called_once_with(url, _filter="")

    @pytest.mark.asyncio
    async def test_parse_rss_feed_empty(self):
        """Test RSS feed returns empty list."""
        url = "https://example.com/rss"

        with patch("module.services.rss_engine.RequestContent") as mock_request:
            mock_instance = MagicMock()
            mock_request.return_value.__enter__.return_value = mock_instance
            mock_instance.get_torrents.return_value = []

            torrents = await RSSEngine.parse_rss_feed(url)

            assert len(torrents) == 0


class TestCollectPendingCandidatesFromSource:
    """Test pending-review torrent collection from a source RSS."""

    @pytest.mark.asyncio
    async def test_mikan_identity_feed_keeps_source_title_aliases(
        self, async_session
    ):
        """One Mikan bangumi/subgroup feed keeps every release title alias."""
        from module.repositories import (
            BangumiRepository,
            RSSRepository,
            TorrentRepository,
        )

        source_url = (
            "https://mikanani.me/RSS/Bangumi?bangumiId=4003&subgroupid=202"
        )
        expected_hashes = {
            "9feaaa14189495fd55cb38f6c4fffc21a7b3239c",
            "dc0492333d459197efaff3a5d68939313cc300bd",
            "fe5b3207710966052e1e2a73c33e8af103f92414",
            "4fcca833aafa0e7d006ed9f76d3f5f2c676c3d41",
            "58e0ed2ee7005e95391e09c270942d7fbd5ce096",
        }
        source_torrents = [
            Torrent(
                name=(
                    "[TV版&无修版] 令和的斑小姐 - EP05 "
                    "[简／繁] (1080p H.264 AAC SRTx2)"
                ),
                url=(
                    "https://mikanani.me/Download/20260730/"
                    "58e0ed2ee7005e95391e09c270942d7fbd5ce096.torrent"
                ),
                hash="58e0ed2ee7005e95391e09c270942d7fbd5ce096",
            ),
            Torrent(
                name=(
                    "[TV版&无修版] 令和的斑小姐 - EP04 "
                    "[简／繁] (1080p H.264 AAC SRTx2)"
                ),
                url=(
                    "https://mikanani.me/Download/20260723/"
                    "4fcca833aafa0e7d006ed9f76d3f5f2c676c3d41.torrent"
                ),
                hash="4fcca833aafa0e7d006ed9f76d3f5f2c676c3d41",
            ),
            Torrent(
                name=(
                    "令和的斑小姐 - EP03 "
                    "[简／繁] (1080p H.264 AAC SRTx2)"
                ),
                url=(
                    "https://mikanani.me/Download/20260716/"
                    "fe5b3207710966052e1e2a73c33e8af103f92414.torrent"
                ),
                hash="fe5b3207710966052e1e2a73c33e8af103f92414",
            ),
            Torrent(
                name=(
                    "[TV版&无修版] 令和的斑小姐 - EP02 "
                    "[简／繁] (1080p H.264 AAC SRTx2)"
                ),
                url=(
                    "https://mikanani.me/Download/20260709/"
                    "dc0492333d459197efaff3a5d68939313cc300bd.torrent"
                ),
                hash="dc0492333d459197efaff3a5d68939313cc300bd",
            ),
            Torrent(
                name=(
                    "[TV版&无修版] 令和妖神斑小姐 - EP01 "
                    "[简／繁] (1080p H.264 AAC SRTx2)"
                ),
                url=(
                    "https://mikanani.me/Download/20260703/"
                    "9feaaa14189495fd55cb38f6c4fffc21a7b3239c.torrent"
                ),
                hash="9feaaa14189495fd55cb38f6c4fffc21a7b3239c",
            ),
        ]

        rss_repo = RSSRepository(async_session)
        bangumi_repo = BangumiRepository(async_session)
        torrent_repo = TorrentRepository(async_session)
        rss = await rss_repo.create({
            "name": "My Bangumi",
            "url": "https://example.com/aggregate.rss",
            "aggregate": True,
            "parser": "mikan",
            "enabled": True,
        })
        series = await _add_series(async_session, "令和的斑小姐")
        bangumi = await bangumi_repo.create({
            "series_id": series.id,
            "rss_id": rss.id,
            "rss_link": source_url,
            "group_name": "TV版&无修版",
            "filter": "简",
            "pending_review": True,
            "added": False,
        })
        await async_session.commit()

        with patch("module.services.rss_engine.RequestContent") as mock_request:
            mock_request.return_value.__enter__.return_value.get_torrents.return_value = (
                source_torrents
            )

            inserted = await RSSEngine.collect_pending_candidates_from_source(
                async_session, bangumi.id
            )

        torrents = await torrent_repo.get_by_rss(rss.id)
        assert inserted == 5
        assert {torrent.hash for torrent in torrents} == expected_hashes
        assert {torrent.mikan_bangumi_id for torrent in torrents} == {4003}
        assert {torrent.mikan_subgroup_id for torrent in torrents} == {202}

    @pytest.mark.parametrize(
        "source_url",
        [
            "https://example.com/source.rss",
            "https://mikanani.me/RSS/Bangumi?bangumiId=4003",
        ],
    )
    @pytest.mark.asyncio
    async def test_unscoped_feed_keeps_legacy_title_filter(
        self, async_session, source_url
    ):
        """Feeds without complete Mikan identity keep title-based scoping."""
        from module.repositories import (
            BangumiRepository,
            RSSRepository,
            TorrentRepository,
        )

        rss_repo = RSSRepository(async_session)
        bangumi_repo = BangumiRepository(async_session)
        torrent_repo = TorrentRepository(async_session)
        rss = await rss_repo.create({
            "name": "My Bangumi",
            "url": "https://example.com/aggregate.rss",
            "aggregate": True,
            "parser": "mikan",
            "enabled": True,
        })
        series = await _add_series(async_session, "Canonical Show")
        bangumi = await bangumi_repo.create({
            "series_id": series.id,
            "rss_id": rss.id,
            "rss_link": source_url,
            "group_name": "Group",
            "filter": "简",
            "pending_review": True,
            "added": False,
        })
        await async_session.commit()

        source_torrents = [
            Torrent(
                name="[Group] Canonical Show - 01 [简]",
                url="https://example.com/matching.torrent",
                hash="matching_hash",
            ),
            Torrent(
                name="[Group] Unrelated Show - 01 [简]",
                url="https://example.com/unrelated.torrent",
                hash="unrelated_hash",
            ),
        ]
        with patch("module.services.rss_engine.RequestContent") as mock_request:
            mock_request.return_value.__enter__.return_value.get_torrents.return_value = (
                source_torrents
            )

            inserted = await RSSEngine.collect_pending_candidates_from_source(
                async_session, bangumi.id
            )

        torrents = await torrent_repo.get_by_rss(rss.id)
        assert inserted == 1
        assert [torrent.hash for torrent in torrents] == ["matching_hash"]


class TestDownloadBangumi:
    """Test download_bangumi function (collection/backfill)."""

    @pytest.mark.asyncio
    async def test_download_bangumi_backfill(
        self, async_session, mock_downloader
    ):
        """Test downloading all episodes for a bangumi."""
        from module.repositories import BangumiRepository, TorrentRepository

        bangumi_repo = BangumiRepository(async_session)
        torrent_repo = TorrentRepository(async_session)

        series = await _add_series(async_session, "Test Anime")

        # Create bangumi
        bangumi = await bangumi_repo.create({
            "group_name": "TestGroup",
            "series_id": series.id,
            "rss_link": "https://example.com/rss",
            "filter": "",
        })
        await async_session.commit()

        # Mock RequestContent to return multiple episodes
        with patch("module.services.rss_engine.RequestContent") as mock_request:
            mock_instance = MagicMock()
            mock_request.return_value.__enter__.return_value = mock_instance

            mock_instance.get_torrents.return_value = [
                Torrent(
                    name="[TestGroup] Test Anime - 01 [1080p]",
                    url="https://example.com/torrent1.torrent",
                    hash="hash1",
                ),
                Torrent(
                    name="[TestGroup] Test Anime - 02 [1080p]",
                    url="https://example.com/torrent2.torrent",
                    hash="hash2",
                ),
                Torrent(
                    name="[TestGroup] Test Anime - 03 [1080p]",
                    url="https://example.com/torrent3.torrent",
                    hash="hash3",
                ),
            ]

            result = await RSSEngine.download_bangumi(
                async_session, mock_downloader, bangumi.id
            )

        await async_session.commit()

        assert result["status"] is True
        assert result["count"] == 3

        # Verify all torrents were created
        torrents = await torrent_repo.get_by_bangumi(bangumi.id)
        assert len(torrents) == 3

        refreshed = await bangumi_repo.get_by_id(bangumi.id)
        assert refreshed.eps_collect is True

        # Verify downloader was called
        mock_downloader.add_torrents.assert_called()

    @pytest.mark.asyncio
    async def test_download_bangumi_with_filter(
        self, async_session, mock_downloader
    ):
        """Test downloading bangumi with filter."""
        from module.repositories import BangumiRepository, TorrentRepository

        bangumi_repo = BangumiRepository(async_session)
        torrent_repo = TorrentRepository(async_session)

        series = await _add_series(async_session, "Test Anime")

        # Create bangumi with filter
        bangumi = await bangumi_repo.create({
            "group_name": "TestGroup",
            "series_id": series.id,
            "rss_link": "https://example.com/rss",
            "filter": "720p",  # Exclude 720p torrents
        })
        await async_session.commit()

        # Mock RequestContent
        with patch("module.services.rss_engine.RequestContent") as mock_request:
            mock_instance = MagicMock()
            mock_request.return_value.__enter__.return_value = mock_instance

            mock_instance.get_torrents.return_value = [
                Torrent(
                    name="[TestGroup] Test Anime - 01 [1080p]",
                    url="https://example.com/torrent1.torrent",
                    hash="hash1",
                ),
                Torrent(
                    name="[TestGroup] Test Anime - 02 [720p]",  # Should be filtered
                    url="https://example.com/torrent2.torrent",
                    hash="hash2",
                ),
            ]

            result = await RSSEngine.download_bangumi(
                async_session, mock_downloader, bangumi.id
            )

        await async_session.commit()

        # Only 1 torrent should pass filter
        assert result["count"] == 1

        torrents = await torrent_repo.get_by_bangumi(bangumi.id)
        assert len(torrents) == 1
        assert "1080p" in torrents[0].name

    @pytest.mark.asyncio
    async def test_download_bangumi_included_hashes_override_filter(
        self, async_session, mock_downloader
    ):
        """Manual keep selections must bypass the regex filter by hash."""
        from module.repositories import BangumiRepository, TorrentRepository

        bangumi_repo = BangumiRepository(async_session)
        torrent_repo = TorrentRepository(async_session)

        series = await _add_series(async_session, "Test Anime")

        bangumi = await bangumi_repo.create({
            "group_name": "TestGroup",
            "series_id": series.id,
            "rss_link": "https://example.com/rss",
            "filter": "合集,繁体",  # Would exclude the selected batch torrent
        })
        await async_session.commit()

        with patch("module.services.rss_engine.RequestContent") as mock_request:
            mock_instance = MagicMock()
            mock_request.return_value.__enter__.return_value = mock_instance

            mock_instance.get_torrents.return_value = [
                Torrent(
                    name="[TestGroup] Test Anime [01-12][1080p][繁体]",
                    url="https://example.com/batch.torrent",
                    hash="batchhash",
                ),
            ]

            result = await RSSEngine.download_bangumi(
                async_session,
                mock_downloader,
                bangumi.id,
                included_hashes=["batchhash"],
            )

        await async_session.commit()

        assert result["status"] is True
        assert result["count"] == 1

        torrents = await torrent_repo.get_by_bangumi(bangumi.id)
        assert len(torrents) == 1
        assert torrents[0].hash == "batchhash"
        mock_downloader.add_torrents.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_bangumi_downloads_existing_pending_keep_selection(
        self, async_session, mock_downloader
    ):
        """Manual keep should download an existing preview candidate row."""
        from module.repositories import BangumiRepository, TorrentRepository

        bangumi_repo = BangumiRepository(async_session)
        torrent_repo = TorrentRepository(async_session)

        series = await _add_series(async_session, "Test Anime")

        bangumi = await bangumi_repo.create({
            "group_name": "TestGroup",
            "series_id": series.id,
            "rss_link": "https://example.com/rss",
            "filter": "合集,繁体",
        })
        await torrent_repo.create({
            "bangumi_id": bangumi.id,
            "rss_id": 1,
            "name": "[TestGroup] Test Anime [01-12][1080p][繁体]",
            "url": "https://example.com/batch.torrent",
            "hash": "batchhash",
            "downloaded": False,
        })
        await async_session.commit()

        with patch("module.services.rss_engine.RequestContent") as mock_request:
            mock_instance = MagicMock()
            mock_request.return_value.__enter__.return_value = mock_instance

            mock_instance.get_torrents.return_value = [
                Torrent(
                    name="[TestGroup] Test Anime [01-12][1080p][繁体]",
                    url="https://example.com/batch.torrent",
                    hash="batchhash",
                ),
            ]

            result = await RSSEngine.download_bangumi(
                async_session,
                mock_downloader,
                bangumi.id,
                included_hashes=["batchhash"],
            )

        await async_session.commit()

        assert result["status"] is True
        assert result["count"] == 1

        torrents = await torrent_repo.get_by_bangumi(bangumi.id)
        assert len(torrents) == 1
        assert torrents[0].downloaded is True
        mock_downloader.add_torrents.assert_called_once()

    @pytest.mark.asyncio
    async def test_review_selection_keeps_new_items_and_exclusions(
        self, async_session, mock_downloader
    ):
        """Preview choices override filters, not exclusions or future RSS items."""
        from module.api.v1.bangumi import activate_pending_bangumi
        from module.api.v1.rss import get_pending_torrent_preview
        from module.conf import settings
        from module.repositories import BangumiRepository, TorrentRepository

        rss = RSSItem(name="Aggregate", url="https://example.com/aggregate", aggregate=True)
        async_session.add(rss)
        series = await _add_series(async_session)
        bangumi = await BangumiRepository(async_session).create({
            "series_id": series.id,
            "rss_id": rss.id,
            "rss_link": "https://example.com/source",
            "filter": "720P,合集",
            "pending_review": True,
        })
        feed = [
            {"name": "Test Anime - 01 [720p]", "url": "https://example.com/keep", "hash": "keep"},
            {"name": "Test Anime - 02 [1080p]", "url": "https://example.com/drop", "hash": "drop"},
        ]
        with patch.object(settings.bangumi_manage, "eps_complete", True), \
             patch.object(settings.bangumi_manage, "eps_complete_from_source", True), \
             patch("module.services.rss_engine.RequestContent") as request, \
             patch("module.api.v1.bangumi.create_downloader", return_value=mock_downloader):
            request.return_value.__enter__.return_value.get_torrents.side_effect = (
                lambda *args, **kwargs: [Torrent(**item) for item in feed]
            )
            preview = await get_pending_torrent_preview(
                rss.id, bangumi.id, _filter=None, session=async_session
            )
            assert {item["hash"]: item["filter"] for item in preview} == {
                "keep": True, "drop": False,
            }
            feed.extend([
                {"name": "Test Anime - 03 [1080p]", "url": "https://example.com/new", "hash": "new"},
                {"name": "Test Anime 合集", "url": "https://example.com/filtered", "hash": "filtered"},
            ])
            response = await activate_pending_bangumi(
                bangumi.id,
                filter=None,
                included_hashes=["KEEP", "drop"],
                excluded_hashes=["drop"],
                session=async_session,
            )
            assert response.status_code == 200
            assert mock_downloader.add_torrents.call_args.kwargs["urls"] == [
                "https://example.com/keep", "https://example.com/new",
            ]
            repeated = await RSSEngine.download_bangumi(
                async_session, mock_downloader, bangumi.id, included_hashes=["keep", "drop"]
            )
            assert repeated["status"] is True
            assert repeated["count"] == 0
            mock_downloader.add_torrents.assert_awaited_once()

        rows = await TorrentRepository(async_session).get_by_bangumi(bangumi.id)
        assert {row.hash for row in rows} == {"keep", "drop", "new"}
        assert all(row.downloaded for row in rows)
        assert next(row for row in rows if row.hash == "drop").state == TorrentState.EXCLUDED
        assert (await BangumiRepository(async_session).get_by_id(bangumi.id)).pending_review is False

    @pytest.mark.asyncio
    async def test_download_bangumi_mikan_feed_does_not_require_canonical_title(
        self, async_session, mock_downloader
    ):
        """Mikan season RSS already identifies the bangumi. Backfill must not
        drop episodes just because the release title uses an alias.
        """
        from module.repositories import BangumiRepository, TorrentRepository

        bangumi_repo = BangumiRepository(async_session)
        torrent_repo = TorrentRepository(async_session)

        series = await _add_series(async_session, "公鸡斗士")
        bangumi = await bangumi_repo.create({
            "group_name": "LoliHouse",
            "series_id": series.id,
            "rss_link": "https://mikanani.me/RSS/Bangumi?bangumiId=3886&subgroupid=370",
            "filter": "",
        })
        await async_session.commit()

        with patch("module.services.rss_engine.RequestContent") as mock_request:
            mock_instance = MagicMock()
            mock_request.return_value.__enter__.return_value = mock_instance
            mock_instance.get_torrents.return_value = [
                Torrent(
                    name=(
                        "[LoliHouse] 鸡斗士 / 怒火鸡头 / Rooster Fighter / "
                        "Niwatori Fighter - 06 [WebRip 1080p HEVC-10bit AAC][简繁内封字幕]"
                    ),
                    url="https://example.com/rooster06.torrent",
                    hash="rooster06",
                ),
                Torrent(
                    name=(
                        "[LoliHouse] 鸡斗士 / 怒火鸡头 / Rooster Fighter / "
                        "Niwatori Fighter - 05 [WebRip 1080p HEVC-10bit AAC][简繁内封字幕]"
                    ),
                    url="https://example.com/rooster05.torrent",
                    hash="rooster05",
                ),
            ]

            result = await RSSEngine.download_bangumi(
                async_session, mock_downloader, bangumi.id
            )

        assert result["status"] is True
        assert result["count"] == 2

        torrents = await torrent_repo.get_by_bangumi(bangumi.id)
        assert len(torrents) == 2
        assert {t.hash for t in torrents} == {"rooster05", "rooster06"}
        mock_downloader.add_torrents.assert_called_once()
