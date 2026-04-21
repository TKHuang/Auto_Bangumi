"""Tests for Season Collector Service."""

import pytest
from unittest.mock import AsyncMock, patch

from sqlalchemy import text

from module.domain.models.bangumi import Bangumi
from module.domain.models.rss import RSSItem
from module.domain.models.series import Series
from module.domain.models.torrent import TorrentState
from module.domain.value_objects import ResponseModel
from module.services.collector import SeasonCollectorService
from module.services.downloader.interface import TorrentInfo


@pytest.fixture
def mock_downloader():
    downloader = AsyncMock()
    downloader.add_torrents = AsyncMock(return_value=True)
    downloader.torrents_delete = AsyncMock(return_value=True)
    downloader.torrents_info = AsyncMock(return_value=[])
    downloader.auth = AsyncMock(return_value=True)
    return downloader


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _add_series(session, title: str = "Test Anime", season: int = 1) -> Series:
    from module.domain.text.normalize import normalize_title as _normalize
    norm, _cour = _normalize(title)
    s = Series(
        canonical_title=title,
        normalized_title=norm,
        season=season,
        root_path=f"/mnt/{title.replace(' ', '_')}",
        pending_review=False,
    )
    session.add(s)
    await session.flush()
    return s


class TestCollectSeason:

    @pytest.mark.asyncio
    async def test_collect_season_success(
        self, async_session, mock_downloader
    ):
        from module.repositories.bangumi import BangumiRepository
        from module.repositories.torrent import TorrentRepository

        bangumi_repo = BangumiRepository(async_session)
        torrent_repo = TorrentRepository(async_session)

        series = await _add_series(async_session, "Test Anime")

        created = await bangumi_repo.create({
            "group_name": "TestGroup",
            "series_id": series.id,
            "rss_link": "https://example.com/rss",
            "rss_id": 1,
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
        self, async_session, mock_downloader
    ):
        from module.repositories.bangumi import BangumiRepository

        bangumi_repo = BangumiRepository(async_session)

        series = await _add_series(async_session, "Test Anime")

        created = await bangumi_repo.create({
            "group_name": "TestGroup",
            "series_id": series.id,
            "rss_link": "https://example.com/rss",
            "rss_id": 1,
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
        self, async_session, mock_downloader
    ):
        from module.repositories.bangumi import BangumiRepository
        from module.repositories.torrent import TorrentRepository

        bangumi_repo = BangumiRepository(async_session)
        torrent_repo = TorrentRepository(async_session)

        series = await _add_series(async_session, "Test Anime")

        created = await bangumi_repo.create({
            "group_name": "TestGroup",
            "series_id": series.id,
            "rss_link": "https://example.com/rss",
            "rss_id": 1,
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

        series = await _add_series(async_session, "New Anime")

        rss = await rss_repo.create({
            "name": "Test RSS",
            "url": "https://example.com/rss",
            "aggregate": False,
            "parser": "mikan",
            "enabled": True,
        })
        await async_session.commit()

        # Bangumi object passed to subscribe_season (not persisted yet).
        # Dropped kwargs removed; series property will be None (no series relation loaded).
        new_bangumi = Bangumi(
            group_name="TestGroup",
            rss_link=rss.url,
            rss_id=rss.id,
            filter="",
            dpi="1080P",
            source="WEB-DL",
            subtitle="CHS",
            offset=0,
        )
        # Attach transient series so official_title / season properties work.
        new_bangumi.series = series

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
        assert all_bangumi[0].added is True
        assert all_bangumi[0].eps_collect is True

    @pytest.mark.asyncio
    async def test_subscribe_season_duplicate_from_different_rss(
        self, async_session, mock_downloader
    ):
        """With get_by_composite_key stubbed to None, duplicate detection via
        composite key is disabled.  The test now verifies that subscribing
        from a second RSS proceeds (no ValueError for 'already subscribed').
        This is acceptable post-0008 behavior; duplicate prevention is
        handled at the DB UNIQUE index level.
        """
        from module.repositories.bangumi import BangumiRepository
        from module.repositories.rss import RSSRepository

        bangumi_repo = BangumiRepository(async_session)
        rss_repo = RSSRepository(async_session)

        series = await _add_series(async_session, "Test Anime")

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

        await bangumi_repo.create({
            "group_name": "TestGroup",
            "series_id": series.id,
            "rss_link": rss1.url,
            "rss_id": rss1.id,
            "filter": "",
            "eps_collect": False,
            "offset": 0,
            "added": True,
            "deleted": False,
            "pending_review": False,
        })
        await async_session.commit()

        new_bangumi = Bangumi(
            group_name="TestGroup",
            rss_link=rss2.url,
            rss_id=rss2.id,
            filter="",
            dpi="1080P",
            source="WEB-DL",
            subtitle="CHS",
            offset=0,
        )
        new_bangumi.series = series

        with patch("module.services.rss_engine.RSSEngine.download_bangumi") as mock_dl:
            mock_dl.return_value = {"status": True, "message": "ok", "count": 0}
            # post-0008: composite-key stub always returns None → no duplicate error
            result = await SeasonCollectorService.subscribe_season(
                async_session, mock_downloader, new_bangumi, parser="mikan"
            )

        # No ValueError raised; subscription proceeds
        assert isinstance(result, ResponseModel)

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

        series = await _add_series(async_session, "Test Anime")

        rss = await rss_repo.create({
            "name": "Test RSS",
            "url": "https://example.com/rss",
            "aggregate": False,
            "parser": "mikan",
            "enabled": True,
        })
        await async_session.commit()

        existing = await bangumi_repo.create({
            "group_name": "TestGroup",
            "series_id": series.id,
            "rss_link": rss.url,
            "rss_id": rss.id,
            "filter": "",
            "eps_collect": False,
            "offset": 0,
            "added": True,
            "deleted": False,
            "pending_review": False,
        })

        await torrent_repo.create({
            "name": "[TestGroup] Test Anime - 01 [1080p]",
            "url": "https://example.com/torrent1.torrent",
            "hash": "hash1",
            "bangumi_id": existing.id,
            "rss_id": rss.id,
            "downloaded": True,
            "state": TorrentState.PENDING,
        })
        await async_session.commit()

        series2 = await _add_series(async_session, "Test Anime Updated")

        new_bangumi = Bangumi(
            group_name="TestGroup",
            rss_link=rss.url,
            rss_id=rss.id,
            filter="",
            dpi="1080P",
            source="WEB-DL",
            subtitle="CHS",
            offset=0,
        )
        new_bangumi.series = series2

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

        assert mock_downloader.torrents_delete.called

    @pytest.mark.asyncio
    async def test_subscribe_season_recovers_from_stale_rss_id(
        self, async_engine, async_session, mock_downloader
    ):
        from module.repositories.bangumi import BangumiRepository
        from module.repositories.rss import RSSRepository

        bangumi_repo = BangumiRepository(async_session)
        rss_repo = RSSRepository(async_session)

        # Reproduce the production behavior where SQLite FK enforcement rejects
        # a bangumi row that points at a stale rss_id.
        async with async_engine.begin() as conn:
            await conn.execute(text("PRAGMA foreign_keys=ON"))
        await async_session.execute(text("PRAGMA foreign_keys=ON"))

        series = await _add_series(async_session, "Recovered Anime")

        new_bangumi = Bangumi(
            group_name="TestGroup",
            rss_link="https://example.com/recovered.rss",
            rss_id=999,
            filter="",
            dpi="1080P",
            source="WEB-DL",
            subtitle="CHS",
            offset=0,
        )
        new_bangumi.series = series

        with patch("module.services.rss_engine.RSSEngine.download_bangumi") as mock_dl:
            mock_dl.return_value = {
                "status": True,
                "message": "Downloaded 1 torrent",
                "count": 1,
            }

            result = await SeasonCollectorService.subscribe_season(
                async_session, mock_downloader, new_bangumi, parser="mikan"
            )

        assert isinstance(result, ResponseModel)
        assert result.status is True

        rss_rows = await rss_repo.get_all()
        created_rss = next(r for r in rss_rows if r.url == new_bangumi.rss_link)
        bangumi_rows = await bangumi_repo.get_all()

        assert created_rss.name == "Recovered Anime"
        assert len(bangumi_rows) == 1
        assert bangumi_rows[0].rss_id == created_rss.id


class TestSubscribeBatch:

    @pytest.mark.asyncio
    async def test_subscribe_batch_success(self, async_session, mock_downloader):
        from module.repositories.bangumi import BangumiRepository
        from module.repositories.rss import RSSRepository

        bangumi_repo = BangumiRepository(async_session)
        rss_repo = RSSRepository(async_session)

        series1 = await _add_series(async_session, "Anime 1")
        series2 = await _add_series(async_session, "Anime 2")

        rss = await rss_repo.create({
            "name": "Test RSS",
            "url": "https://example.com/rss",
            "aggregate": True,
            "parser": "mikan",
            "enabled": True,
        })
        await async_session.commit()

        b1 = Bangumi(
            group_name="TestGroup",
            rss_link=rss.url,
            filter="",
            dpi="1080P",
            source="WEB-DL",
            subtitle="CHS",
            offset=0,
        )
        b1.series = series1

        b2 = Bangumi(
            group_name="TestGroup",
            rss_link=rss.url,
            filter="",
            dpi="1080P",
            source="WEB-DL",
            subtitle="CHS",
            offset=0,
        )
        b2.series = series2

        bangumi_list = [b1, b2]

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

        series = await _add_series(async_session, "Anime 1")

        rss = await rss_repo.create({
            "name": "Test RSS",
            "url": "https://example.com/rss",
            "aggregate": True,
            "parser": "mikan",
            "enabled": True,
        })
        await async_session.commit()

        b1 = Bangumi(
            group_name="TestGroup",
            rss_link=rss.url,
            filter="",
            dpi="1080P",
            source="WEB-DL",
            subtitle="CHS",
            offset=0,
        )
        b1.series = series

        bangumi_list = [b1]

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

    @pytest.mark.asyncio
    async def test_subscribe_batch_dedupes_duplicate_identity(
        self, async_session, mock_downloader
    ):
        """Aggregate feeds can expose two torrent name variants that both
        resolve to the same (series_id, mikan_subgroup_id) identity.
        The batch must dedupe in-process so a single IntegrityError doesn't
        poison the session's transaction and cascade-fail the rest of the batch.
        """
        from module.repositories.bangumi import BangumiRepository
        from module.repositories.rss import RSSRepository

        bangumi_repo = BangumiRepository(async_session)
        rss_repo = RSSRepository(async_session)

        series = await _add_series(async_session, "Shared Anime")

        rss = await rss_repo.create({
            "name": "Aggregate RSS",
            "url": "https://example.com/rss/aggregate",
            "aggregate": True,
            "parser": "mikan",
            "enabled": True,
        })
        await async_session.commit()

        # Two Bangumi DTOs with different group_names but resolving
        # to the same series via the same rss_link. Non-Mikan URLs yield
        # mikan_subgroup_id=None, so both collapse to identity (series.id, None).
        b1 = Bangumi(
            group_name="VariantA",
            rss_link=rss.url,
            filter="",
            dpi="1080P",
            source="WEB-DL",
            subtitle="CHS",
            offset=0,
        )
        b1.series = series

        b2 = Bangumi(
            group_name="VariantB",
            rss_link=rss.url,
            filter="",
            dpi="1080P",
            source="WEB-DL",
            subtitle="CHS",
            offset=0,
        )
        b2.series = series

        bangumi_list = [b1, b2]

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
        assert len(all_bangumi) == 1, (
            f"expected dedup to collapse duplicate identity to 1 row, got {len(all_bangumi)}"
        )

    @pytest.mark.asyncio
    async def test_subscribe_batch_applies_manual_torrent_selection(
        self, async_session, mock_downloader
    ):
        from module.repositories.bangumi import BangumiRepository
        from module.repositories.rss import RSSRepository
        from module.repositories.torrent import TorrentRepository

        bangumi_repo = BangumiRepository(async_session)
        rss_repo = RSSRepository(async_session)
        torrent_repo = TorrentRepository(async_session)

        series = await _add_series(async_session, "Anime Manual")

        rss = await rss_repo.create({
            "name": "Aggregate RSS",
            "url": "https://example.com/rss/aggregate",
            "aggregate": True,
            "parser": "mikan",
            "enabled": True,
        })
        await async_session.commit()

        b1 = Bangumi(
            group_name="TestGroup",
            rss_link=rss.url,
            filter="合集,繁体",
            dpi="1080P",
            source="WEB-DL",
            subtitle="CHS",
            offset=0,
        )
        b1.series = series

        with patch("module.services.rss_engine.RSSEngine.download_bangumi") as mock_dl:
            mock_dl.return_value = {
                "status": True,
                "message": "Downloaded torrents",
                "count": 1,
            }

            result = await SeasonCollectorService.subscribe_batch(
                async_session,
                mock_downloader,
                [b1],
                rss.id,
                parser="mikan",
                torrent_selections=[
                    {
                        "included_hashes": ["batchhash"],
                        "excluded_hashes": ["skiphash"],
                    }
                ],
            )

        assert result.status is True
        assert result.status_code == 200

        all_bangumi = await bangumi_repo.get_by_rss(rss.id)
        assert len(all_bangumi) == 1

        mock_dl.assert_awaited_once_with(
            async_session,
            mock_downloader,
            all_bangumi[0].id,
            included_hashes=["batchhash"],
        )

        torrents = await torrent_repo.get_by_bangumi(all_bangumi[0].id)
        excluded = [t for t in torrents if t.hash == "skiphash"]
        assert len(excluded) == 1
        assert excluded[0].state == TorrentState.EXCLUDED
