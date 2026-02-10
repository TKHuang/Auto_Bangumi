"""Tests for Season Collector Service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from module.domain.models.bangumi import Bangumi
from module.domain.models.rss import RSSItem
from module.domain.models.torrent import Torrent, TorrentState
from module.domain.value_objects import ResponseModel
from module.services.collector import SeasonCollectorService
from module.services.downloader.interface import TorrentInfo, TorrentFile


@pytest.fixture
def mock_downloader():
    downloader = AsyncMock()
    downloader.add_torrents = AsyncMock(return_value=True)
    downloader.torrents_delete = AsyncMock(return_value=True)
    downloader.torrents_info = AsyncMock(return_value=[])
    downloader.auth = AsyncMock(return_value=True)
    return downloader


@pytest.fixture
def sample_bangumi():
    return Bangumi(
        id=1,
        official_title="Test Anime",
        title_raw="Test Anime",
        season=1,
        group_name="TestGroup",
        rss_link="https://example.com/rss",
        rss_id=1,
        poster_link="",
        filter="",
        added=False,
        deleted=False,
        eps_collect=False,
        offset=0,
        pending_review=False,
    )


@pytest.fixture
def sample_rss():
    return RSSItem(
        id=1,
        name="Test RSS",
        url="https://example.com/rss",
        aggregate=False,
        parser="mikan",
        enabled=True,
    )


@pytest.fixture
def sample_legacy_torrent():
    class LegacyTorrent:
        def __init__(self, name, url, homepage, hash):
            self.name = name
            self.url = url
            self.homepage = homepage
            self.hash = hash

    return LegacyTorrent(
        name="[TestGroup] Test Anime - 01 [1080p]",
        url="https://example.com/torrent1.torrent",
        homepage="https://example.com/episode/1",
        hash="hash1",
    )


class TestCollectSeason:

    @pytest.mark.asyncio
    async def test_collect_season_success(
        self, async_session, mock_downloader, sample_bangumi
    ):
        from module.repositories.bangumi import BangumiRepository
        from module.repositories.torrent import TorrentRepository

        bangumi_repo = BangumiRepository(async_session)
        torrent_repo = TorrentRepository(async_session)

        created = await bangumi_repo.create({
            "official_title": sample_bangumi.official_title,
            "title_raw": sample_bangumi.title_raw,
            "season": sample_bangumi.season,
            "group_name": sample_bangumi.group_name,
            "rss_link": sample_bangumi.rss_link,
            "rss_id": sample_bangumi.rss_id,
            "poster_link": "",
            "filter": "",
            "eps_collect": False,
            "offset": 0,
            "added": False,
            "deleted": False,
            "pending_review": False,
        })
        await async_session.commit()

        class LegacyTorrent:
            def __init__(self, name, url, homepage, hash):
                self.name = name
                self.url = url
                self.homepage = homepage
                self.hash = hash

        legacy_torrents = [
            LegacyTorrent(
                name="[TestGroup] Test Anime - 01 [1080p]",
                url="https://example.com/torrent1.torrent",
                homepage="https://example.com/episode/1",
                hash="hash1",
            ),
            LegacyTorrent(
                name="[TestGroup] Test Anime - 02 [1080p]",
                url="https://example.com/torrent2.torrent",
                homepage="https://example.com/episode/2",
                hash="hash2",
            ),
        ]

        def mock_fetch():
            return legacy_torrents

        with patch("asyncio.to_thread", return_value=mock_fetch()):
            result = await SeasonCollectorService.collect_season(
                async_session, mock_downloader, created, link=None
            )

        assert result.status is True
        assert result.status_code == 200
        assert "completed" in result.msg_en.lower()

        updated = await bangumi_repo.get_by_id(created.id)
        assert updated.eps_collect is True

        torrents = await torrent_repo.get_by_bangumi(created.id)
        assert len(torrents) == 2

    @pytest.mark.asyncio
    async def test_collect_season_no_new_torrents(
        self, async_session, mock_downloader, sample_bangumi
    ):
        from module.repositories.bangumi import BangumiRepository

        bangumi_repo = BangumiRepository(async_session)

        created = await bangumi_repo.create({
            "official_title": sample_bangumi.official_title,
            "title_raw": sample_bangumi.title_raw,
            "season": sample_bangumi.season,
            "group_name": sample_bangumi.group_name,
            "rss_link": sample_bangumi.rss_link,
            "rss_id": sample_bangumi.rss_id,
            "poster_link": "",
            "filter": "",
            "eps_collect": False,
            "offset": 0,
            "added": False,
            "deleted": False,
            "pending_review": False,
        })
        await async_session.commit()

        def mock_fetch():
            return []

        with patch("asyncio.to_thread", return_value=mock_fetch()):
            result = await SeasonCollectorService.collect_season(
                async_session, mock_downloader, created, link=None
            )

        assert result.status is False
        assert result.status_code == 404
        assert "no new episodes" in result.msg_en.lower()

    @pytest.mark.asyncio
    async def test_collect_season_already_in_downloader(
        self, async_session, mock_downloader, sample_bangumi
    ):
        from module.repositories.bangumi import BangumiRepository
        from module.repositories.torrent import TorrentRepository

        bangumi_repo = BangumiRepository(async_session)
        torrent_repo = TorrentRepository(async_session)

        created = await bangumi_repo.create({
            "official_title": sample_bangumi.official_title,
            "title_raw": sample_bangumi.title_raw,
            "season": sample_bangumi.season,
            "group_name": sample_bangumi.group_name,
            "rss_link": sample_bangumi.rss_link,
            "rss_id": sample_bangumi.rss_id,
            "poster_link": "",
            "filter": "",
            "eps_collect": False,
            "offset": 0,
            "added": False,
            "deleted": False,
            "pending_review": False,
        })
        await async_session.commit()

        class LegacyTorrent:
            def __init__(self, name, url, homepage, hash):
                self.name = name
                self.url = url
                self.homepage = homepage
                self.hash = hash

        legacy_torrents = [
            LegacyTorrent(
                name="[TestGroup] Test Anime - 01 [1080p]",
                url="https://example.com/torrent1.torrent",
                homepage="https://example.com/episode/1",
                hash="hash1",
            ),
        ]

        mock_downloader.torrents_info = AsyncMock(
            return_value=[
                TorrentInfo(
                    hash="hash1",
                    name="[TestGroup] Test Anime - 01 [1080p]",
                    state="completed",
                    progress=1.0,
                    save_path="/downloads",
                    size=1000000,
                    files=[],
                )
            ]
        )

        def mock_fetch():
            return legacy_torrents

        with patch("asyncio.to_thread", return_value=mock_fetch()):
            result = await SeasonCollectorService.collect_season(
                async_session, mock_downloader, created, link=None
            )

        assert result.status is True
        assert result.status_code == 200
        assert "already in download client" in result.msg_en.lower()

        updated = await bangumi_repo.get_by_id(created.id)
        assert updated.eps_collect is True

        torrents = await torrent_repo.get_by_bangumi(created.id)
        assert len(torrents) == 1
        assert torrents[0].downloaded is True


class TestSubscribeSeason:

    @pytest.mark.asyncio
    async def test_subscribe_season_success(self, async_session, mock_downloader):
        from module.repositories.bangumi import BangumiRepository
        from module.repositories.rss import RSSRepository

        bangumi_repo = BangumiRepository(async_session)
        rss_repo = RSSRepository(async_session)

        rss = await rss_repo.create({
            "name": "Test RSS",
            "url": "https://example.com/rss",
            "aggregate": False,
            "parser": "mikan",
            "enabled": True,
        })
        await async_session.commit()

        new_bangumi = Bangumi(
            official_title="New Anime",
            title_raw="New Anime",
            season=1,
            season_raw="S1",
            group_name="TestGroup",
            rss_link=rss.url,
            rss_id=rss.id,
            poster_link="",
            filter="",
            dpi="1080P",
            source="WEB-DL",
            subtitle="CHS",
            offset=0,
        )

        with patch("module.services.rss_engine.RSSEngine.download_bangumi") as mock_dl:
            mock_dl.return_value = {
                "status": True,
                "message": "Downloaded 2 torrents",
                "count": 2,
            }

            result = await SeasonCollectorService.subscribe_season(
                async_session, mock_downloader, new_bangumi, parser="mikan"
            )

        assert isinstance(result, ResponseModel)
        assert result.status is True

        all_bangumi = await bangumi_repo.get_all()
        assert len(all_bangumi) == 1
        assert all_bangumi[0].official_title == "New Anime"
        assert all_bangumi[0].added is True
        assert all_bangumi[0].eps_collect is True

    @pytest.mark.asyncio
    async def test_subscribe_season_duplicate_from_different_rss(
        self, async_session, mock_downloader
    ):
        from module.repositories.bangumi import BangumiRepository
        from module.repositories.rss import RSSRepository

        bangumi_repo = BangumiRepository(async_session)
        rss_repo = RSSRepository(async_session)

        rss1 = await rss_repo.create({
            "name": "RSS 1",
            "url": "https://example.com/rss1",
            "aggregate": False,
            "parser": "mikan",
            "enabled": True,
        })

        rss2 = await rss_repo.create({
            "name": "RSS 2",
            "url": "https://example.com/rss2",
            "aggregate": False,
            "parser": "mikan",
            "enabled": True,
        })
        await async_session.commit()

        existing = await bangumi_repo.create({
            "official_title": "Test Anime",
            "title_raw": "Test Anime",
            "season": 1,
            "group_name": "TestGroup",
            "rss_link": rss1.url,
            "rss_id": rss1.id,
            "poster_link": "",
            "filter": "",
            "eps_collect": False,
            "offset": 0,
            "added": True,
            "deleted": False,
            "pending_review": False,
        })
        await async_session.commit()

        new_bangumi = Bangumi(
            official_title="Test Anime",
            title_raw="Test Anime",
            season=1,
            season_raw="S1",
            group_name="TestGroup",
            rss_link=rss2.url,
            rss_id=rss2.id,
            poster_link="",
            filter="",
            dpi="1080P",
            source="WEB-DL",
            subtitle="CHS",
            offset=0,
        )

        with pytest.raises(ValueError, match="already subscribed"):
            await SeasonCollectorService.subscribe_season(
                async_session, mock_downloader, new_bangumi, parser="mikan"
            )

    @pytest.mark.asyncio
    async def test_subscribe_season_recreate_same_rss(
        self, async_session, mock_downloader
    ):
        from module.repositories.bangumi import BangumiRepository
        from module.repositories.rss import RSSRepository
        from module.repositories.torrent import TorrentRepository

        bangumi_repo = BangumiRepository(async_session)
        rss_repo = RSSRepository(async_session)
        torrent_repo = TorrentRepository(async_session)

        rss = await rss_repo.create({
            "name": "Test RSS",
            "url": "https://example.com/rss",
            "aggregate": False,
            "parser": "mikan",
            "enabled": True,
        })
        await async_session.commit()

        existing = await bangumi_repo.create({
            "official_title": "Test Anime",
            "title_raw": "Test Anime",
            "season": 1,
            "group_name": "TestGroup",
            "rss_link": rss.url,
            "rss_id": rss.id,
            "poster_link": "",
            "filter": "",
            "eps_collect": False,
            "offset": 0,
            "added": True,
            "deleted": False,
            "pending_review": False,
        })

        torrent = await torrent_repo.create({
            "name": "[TestGroup] Test Anime - 01 [1080p]",
            "url": "https://example.com/torrent1.torrent",
            "hash": "hash1",
            "bangumi_id": existing.id,
            "rss_id": rss.id,
            "downloaded": True,
            "state": TorrentState.PENDING,
        })
        await async_session.commit()

        new_bangumi = Bangumi(
            official_title="Test Anime Updated",
            title_raw="Test Anime Updated",
            season=1,
            season_raw="S1",
            group_name="TestGroup",
            rss_link=rss.url,
            rss_id=rss.id,
            poster_link="",
            filter="",
            dpi="1080P",
            source="WEB-DL",
            subtitle="CHS",
            offset=0,
        )

        with patch("module.services.rss_engine.RSSEngine.download_bangumi") as mock_dl:
            mock_dl.return_value = {
                "status": True,
                "message": "Downloaded 1 torrent",
                "count": 1,
            }

            result = await SeasonCollectorService.subscribe_season(
                async_session,
                mock_downloader,
                new_bangumi,
                parser="mikan",
                delete_files=False,
            )

        assert isinstance(result, ResponseModel)
        assert result.status is True

        all_bangumi = await bangumi_repo.get_by_rss(rss.id)
        assert len(all_bangumi) == 1
        assert all_bangumi[0].official_title == "Test Anime Updated"

        assert mock_downloader.torrents_delete.called


class TestSubscribeBatch:

    @pytest.mark.asyncio
    async def test_subscribe_batch_success(self, async_session, mock_downloader):
        from module.repositories.bangumi import BangumiRepository
        from module.repositories.rss import RSSRepository

        bangumi_repo = BangumiRepository(async_session)
        rss_repo = RSSRepository(async_session)

        rss = await rss_repo.create({
            "name": "Test RSS",
            "url": "https://example.com/rss",
            "aggregate": True,
            "parser": "mikan",
            "enabled": True,
        })
        await async_session.commit()

        bangumi_list = [
            Bangumi(
                official_title="Anime 1",
                title_raw="Anime 1",
                season=1,
                season_raw="S1",
                group_name="TestGroup",
                rss_link=rss.url,
                poster_link="",
                filter="",
                dpi="1080P",
                source="WEB-DL",
                subtitle="CHS",
                offset=0,
            ),
            Bangumi(
                official_title="Anime 2",
                title_raw="Anime 2",
                season=1,
                season_raw="S1",
                group_name="TestGroup",
                rss_link=rss.url,
                poster_link="",
                filter="",
                dpi="1080P",
                source="WEB-DL",
                subtitle="CHS",
                offset=0,
            ),
        ]

        with patch("module.services.rss_engine.RSSEngine.download_bangumi") as mock_dl:
            mock_dl.return_value = {
                "status": True,
                "message": "Downloaded torrents",
                "count": 1,
            }

            result = await SeasonCollectorService.subscribe_batch(
                async_session, mock_downloader, bangumi_list, rss.id, parser="mikan"
            )

        assert result.status is True
        assert result.status_code == 200
        assert "successfully subscribed 2" in result.msg_en.lower()

        all_bangumi = await bangumi_repo.get_by_rss(rss.id)
        assert len(all_bangumi) == 2

    @pytest.mark.asyncio
    async def test_subscribe_batch_empty_list(self, async_session, mock_downloader):
        result = await SeasonCollectorService.subscribe_batch(
            async_session, mock_downloader, [], 1, parser="mikan"
        )

        assert result.status is False
        assert result.status_code == 400
        assert "no bangumi provided" in result.msg_en.lower()

    @pytest.mark.asyncio
    async def test_subscribe_batch_partial_failure(self, async_session, mock_downloader):
        from module.repositories.bangumi import BangumiRepository
        from module.repositories.rss import RSSRepository

        bangumi_repo = BangumiRepository(async_session)
        rss_repo = RSSRepository(async_session)

        rss = await rss_repo.create({
            "name": "Test RSS",
            "url": "https://example.com/rss",
            "aggregate": True,
            "parser": "mikan",
            "enabled": True,
        })
        await async_session.commit()

        bangumi_list = [
            Bangumi(
                official_title="Anime 1",
                title_raw="Anime 1",
                season=1,
                season_raw="S1",
                group_name="TestGroup",
                rss_link=rss.url,
                poster_link="",
                filter="",
                dpi="1080P",
                source="WEB-DL",
                subtitle="CHS",
                offset=0,
            ),
        ]

        with patch("module.services.rss_engine.RSSEngine.download_bangumi") as mock_dl:
            mock_dl.return_value = {
                "status": True,
                "message": "Downloaded torrents",
                "count": 1,
            }

            result = await SeasonCollectorService.subscribe_batch(
                async_session, mock_downloader, bangumi_list, rss.id, parser="mikan"
            )

        assert result.status is True
        assert result.status_code == 200

        all_bangumi = await bangumi_repo.get_by_rss(rss.id)
        assert len(all_bangumi) == 1
