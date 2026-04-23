"""Tests for RSS refresh scheduled job (pipeline-based)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from module.scheduler.jobs.rss_refresh import (
    _build_global_filter_pattern,
    _is_globally_filtered,
    _parse_torrent_title,
    _trigger_downloads,
    rss_refresh_job,
)
from module.services.pipeline.rss_pipeline import FeedItem, PipelineResult


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestBuildGlobalFilterPattern:
    def test_empty_filter_list_returns_none(self):
        with patch("module.scheduler.jobs.rss_refresh.settings") as mock_settings:
            mock_settings.rss_parser.filter = []
            result = _build_global_filter_pattern()
        assert result is None

    def test_single_literal_filter(self):
        with patch("module.scheduler.jobs.rss_refresh.settings") as mock_settings:
            mock_settings.rss_parser.filter = ["720"]
            result = _build_global_filter_pattern()
        assert result is not None
        assert "720" in result

    def test_multiple_filters_joined(self):
        with patch("module.scheduler.jobs.rss_refresh.settings") as mock_settings:
            mock_settings.rss_parser.filter = ["720", r"\d+-\d"]
            result = _build_global_filter_pattern()
        assert result is not None
        # Should contain both patterns
        assert "720" in result
        assert r"\d+-\d" in result


class TestIsGloballyFiltered:
    def test_no_pattern_never_filters(self):
        assert _is_globally_filtered("Some Anime [1080p]", None) is False

    def test_match_returns_true(self):
        assert _is_globally_filtered("Some Anime [720p]", "720") is True

    def test_no_match_returns_false(self):
        assert _is_globally_filtered("Some Anime [1080p]", "720") is False

    def test_case_insensitive(self):
        assert _is_globally_filtered("ANIME_720P.mkv", "720p") is True


# ---------------------------------------------------------------------------
# Integration tests for rss_refresh_job
# ---------------------------------------------------------------------------


class TestRssRefreshJob:
    @pytest.mark.asyncio
    async def test_job_iterates_enabled_rss_items(self):
        """Job should fetch and process each enabled RSS item."""
        mock_session = AsyncMock()
        mock_session_gen = AsyncMock()
        mock_session_gen.__anext__.return_value = mock_session

        mock_rss_item = MagicMock()
        mock_rss_item.id = 1
        mock_rss_item.name = "Test RSS"
        mock_rss_item.url = "https://mikanani.me/RSS/Bangumi?bangumiId=123"
        mock_rss_item.last_status = None

        mock_pipeline_result = PipelineResult(items_seen=0, items_resolved=0)
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.commit = AsyncMock()

        with (
            patch("module.scheduler.jobs.rss_refresh.get_db_session") as mock_get_db,
            patch("module.scheduler.jobs.rss_refresh.create_downloader"),
            patch("module.scheduler.jobs.rss_refresh.build_mikan_limiter_from_settings"),
            patch("module.scheduler.jobs.rss_refresh.MikanClient") as mock_mikan_cls,
            patch("module.scheduler.jobs.rss_refresh.MikanResolver"),
            patch("module.scheduler.jobs.rss_refresh.MikanEpisodeRefRepository"),
            patch("module.scheduler.jobs.rss_refresh.RSSRepository") as mock_rss_repo_cls,
            patch("module.scheduler.jobs.rss_refresh.RssPipeline") as mock_pipeline_cls,
            patch("module.scheduler.jobs.rss_refresh.RSSEngine.parse_rss_feed", return_value=[]),
            patch("module.scheduler.jobs.rss_refresh._build_global_filter_pattern", return_value=None),
        ):
            mock_get_db.return_value = mock_session_gen

            # Set up context manager for MikanClient
            mock_mikan_client = AsyncMock()
            mock_mikan_cls.return_value.__aenter__ = AsyncMock(return_value=mock_mikan_client)
            mock_mikan_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # Set up RSSRepository
            mock_rss_repo = AsyncMock()
            mock_rss_repo.get_enabled = AsyncMock(return_value=[mock_rss_item])
            mock_rss_repo.update_status = AsyncMock()
            mock_rss_repo_cls.return_value = mock_rss_repo

            # Set up pipeline
            mock_pipeline = AsyncMock()
            mock_pipeline.run_for_feed = AsyncMock(return_value=mock_pipeline_result)
            mock_pipeline_cls.return_value = mock_pipeline

            await rss_refresh_job()

        # Pipeline was called for the RSS item
        mock_pipeline.run_for_feed.assert_called_once_with(1, [])
        mock_rss_repo.update_status.assert_called_once_with(1, "Success", None)

    @pytest.mark.asyncio
    async def test_global_filter_drops_matching_torrents(self):
        """Torrents matching global filter still reach the pipeline with a flag."""
        from module.domain.models.torrent import Torrent as OrmTorrent

        mock_session = AsyncMock()
        mock_session_gen = AsyncMock()
        mock_session_gen.__anext__.return_value = mock_session

        mock_rss_item = MagicMock()
        mock_rss_item.id = 1
        mock_rss_item.name = "Test RSS"
        mock_rss_item.url = "https://mikanani.me/RSS/Bangumi?bangumiId=123"
        mock_rss_item.last_status = None

        # Two torrents: one is 720p (should be flagged), one is 1080p (should pass)
        torrent_720 = MagicMock(spec=OrmTorrent)
        torrent_720.name = "Anime S01E01 [720p].mkv"
        torrent_720.hash = "aaaa1111bbbb2222cccc3333dddd4444eeee5555"
        torrent_720.url = "https://example.com/720.torrent"
        torrent_720.homepage = "https://mikanani.me/Home/Episode/aaaa"

        torrent_1080 = MagicMock(spec=OrmTorrent)
        torrent_1080.name = "Anime S01E01 [1080p].mkv"
        torrent_1080.hash = "bbbb2222cccc3333dddd4444eeee5555ffff6666"
        torrent_1080.url = "https://example.com/1080.torrent"
        torrent_1080.homepage = "https://mikanani.me/Home/Episode/bbbb"

        captured_feed_items: list[list[FeedItem]] = []

        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.commit = AsyncMock()

        async def capture_run_for_feed(rss_id, items):
            captured_feed_items.append(list(items))
            return PipelineResult(items_seen=len(items))

        with (
            patch("module.scheduler.jobs.rss_refresh.get_db_session") as mock_get_db,
            patch("module.scheduler.jobs.rss_refresh.create_downloader"),
            patch("module.scheduler.jobs.rss_refresh.build_mikan_limiter_from_settings"),
            patch("module.scheduler.jobs.rss_refresh.MikanClient") as mock_mikan_cls,
            patch("module.scheduler.jobs.rss_refresh.MikanResolver"),
            patch("module.scheduler.jobs.rss_refresh.MikanEpisodeRefRepository"),
            patch("module.scheduler.jobs.rss_refresh.RSSRepository") as mock_rss_repo_cls,
            patch("module.scheduler.jobs.rss_refresh.RssPipeline") as mock_pipeline_cls,
            patch(
                "module.scheduler.jobs.rss_refresh.RSSEngine.parse_rss_feed",
                return_value=[torrent_720, torrent_1080],
            ),
            # Global filter pattern that matches "720"
            patch(
                "module.scheduler.jobs.rss_refresh._build_global_filter_pattern",
                return_value="720",
            ),
            patch(
                "module.scheduler.jobs.rss_refresh._parse_torrent_title",
                return_value=("Anime", 1, None, None),
            ),
        ):
            mock_get_db.return_value = mock_session_gen

            mock_mikan_client = AsyncMock()
            mock_mikan_cls.return_value.__aenter__ = AsyncMock(return_value=mock_mikan_client)
            mock_mikan_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_rss_repo = AsyncMock()
            mock_rss_repo.get_enabled = AsyncMock(return_value=[mock_rss_item])
            mock_rss_repo.update_status = AsyncMock()
            mock_rss_repo_cls.return_value = mock_rss_repo

            mock_pipeline = AsyncMock()
            mock_pipeline.run_for_feed = AsyncMock(side_effect=capture_run_for_feed)
            mock_pipeline_cls.return_value = mock_pipeline

            await rss_refresh_job()

        assert len(captured_feed_items) == 1
        items = captured_feed_items[0]
        assert len(items) == 2
        assert items[0].raw_name == "Anime S01E01 [720p].mkv"
        assert items[0].globally_filtered is True
        assert items[1].raw_name == "Anime S01E01 [1080p].mkv"
        assert items[1].globally_filtered is False

    @pytest.mark.asyncio
    async def test_fetch_error_is_caught_and_status_updated(self):
        """When RSS fetch fails, error status is set and job continues for other feeds."""
        mock_session = AsyncMock()
        mock_session_gen = AsyncMock()
        mock_session_gen.__anext__.return_value = mock_session

        mock_rss_item = MagicMock()
        mock_rss_item.id = 42
        mock_rss_item.name = "Failing RSS"
        mock_rss_item.url = "https://mikanani.me/bad-url"
        mock_rss_item.last_status = None

        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.commit = AsyncMock()

        with (
            patch("module.scheduler.jobs.rss_refresh.get_db_session") as mock_get_db,
            patch("module.scheduler.jobs.rss_refresh.create_downloader"),
            patch("module.scheduler.jobs.rss_refresh.build_mikan_limiter_from_settings"),
            patch("module.scheduler.jobs.rss_refresh.MikanClient") as mock_mikan_cls,
            patch("module.scheduler.jobs.rss_refresh.MikanResolver"),
            patch("module.scheduler.jobs.rss_refresh.MikanEpisodeRefRepository"),
            patch("module.scheduler.jobs.rss_refresh.RSSRepository") as mock_rss_repo_cls,
            patch("module.scheduler.jobs.rss_refresh.RssPipeline") as mock_pipeline_cls,
            patch(
                "module.scheduler.jobs.rss_refresh.RSSEngine.parse_rss_feed",
                side_effect=Exception("Network error"),
            ),
            patch(
                "module.scheduler.jobs.rss_refresh._build_global_filter_pattern",
                return_value=None,
            ),
        ):
            mock_get_db.return_value = mock_session_gen

            mock_mikan_client = AsyncMock()
            mock_mikan_cls.return_value.__aenter__ = AsyncMock(return_value=mock_mikan_client)
            mock_mikan_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_rss_repo = AsyncMock()
            mock_rss_repo.get_enabled = AsyncMock(return_value=[mock_rss_item])
            mock_rss_repo.update_status = AsyncMock()
            mock_rss_repo_cls.return_value = mock_rss_repo

            mock_pipeline = AsyncMock()
            mock_pipeline.run_for_feed = AsyncMock(return_value=PipelineResult())
            mock_pipeline_cls.return_value = mock_pipeline

            # Should not raise — errors are caught and logged
            await rss_refresh_job()

        # Error status should be set
        mock_rss_repo.update_status.assert_called_once_with(42, "Error", "Network error")
        # Pipeline should NOT have been called (fetch failed)
        mock_pipeline.run_for_feed.assert_not_called()

    @pytest.mark.asyncio
    async def test_skipped_locked_feed_does_not_report_success(self):
        """A skipped feed must keep its previous status because no work ran."""
        mock_session = AsyncMock()
        mock_session_gen = AsyncMock()
        mock_session_gen.__anext__.return_value = mock_session

        mock_rss_item = MagicMock()
        mock_rss_item.id = 1
        mock_rss_item.name = "Locked RSS"
        mock_rss_item.url = "https://mikanani.me/RSS/Bangumi?bangumiId=123"
        mock_rss_item.last_status = None

        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.commit = AsyncMock()

        with (
            patch("module.scheduler.jobs.rss_refresh.get_db_session") as mock_get_db,
            patch("module.scheduler.jobs.rss_refresh.create_downloader"),
            patch("module.scheduler.jobs.rss_refresh.build_mikan_limiter_from_settings"),
            patch("module.scheduler.jobs.rss_refresh.MikanClient") as mock_mikan_cls,
            patch("module.scheduler.jobs.rss_refresh.MikanResolver"),
            patch("module.scheduler.jobs.rss_refresh.MikanEpisodeRefRepository"),
            patch("module.scheduler.jobs.rss_refresh.RSSRepository") as mock_rss_repo_cls,
            patch("module.scheduler.jobs.rss_refresh.RssPipeline") as mock_pipeline_cls,
            patch("module.scheduler.jobs.rss_refresh.RSSEngine.parse_rss_feed", return_value=[]),
            patch("module.scheduler.jobs.rss_refresh._build_global_filter_pattern", return_value=None),
        ):
            mock_get_db.return_value = mock_session_gen

            mock_mikan_client = AsyncMock()
            mock_mikan_cls.return_value.__aenter__ = AsyncMock(return_value=mock_mikan_client)
            mock_mikan_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_rss_repo = AsyncMock()
            mock_rss_repo.get_enabled = AsyncMock(return_value=[mock_rss_item])
            mock_rss_repo.update_status = AsyncMock()
            mock_rss_repo_cls.return_value = mock_rss_repo

            mock_pipeline = AsyncMock()
            mock_pipeline.run_for_feed = AsyncMock(
                return_value=PipelineResult(skipped_locked=True)
            )
            mock_pipeline_cls.return_value = mock_pipeline

            await rss_refresh_job()

        mock_pipeline.run_for_feed.assert_called_once_with(1, [])
        mock_rss_repo.update_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_session_closed_on_error(self):
        """Session must be closed even when an unexpected error occurs."""
        mock_session = AsyncMock()
        mock_session_gen = AsyncMock()
        mock_session_gen.__anext__.return_value = mock_session

        with (
            patch("module.scheduler.jobs.rss_refresh.get_db_session") as mock_get_db,
            patch(
                "module.scheduler.jobs.rss_refresh.create_downloader",
                side_effect=RuntimeError("Config error"),
            ),
        ):
            mock_get_db.return_value = mock_session_gen
            await rss_refresh_job()

        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_job_triggers_downloads_per_feed_and_runs_source_backfill(self):
        """Each processed feed should sync downloader promptly and honor source backfill."""
        mock_session = AsyncMock()
        mock_session_gen = AsyncMock()
        mock_session_gen.__anext__.return_value = mock_session

        mock_rss_item = MagicMock()
        mock_rss_item.id = 1
        mock_rss_item.name = "Test RSS"
        mock_rss_item.url = "https://mikanani.me/RSS/Bangumi?bangumiId=123&subgroupid=7"
        mock_rss_item.last_status = None

        mock_bangumi = MagicMock()
        mock_bangumi.id = 99
        mock_bangumi.eps_collect = False
        mock_bangumi.deleted = False
        mock_bangumi.pending_review = False
        mock_bangumi.active = True
        mock_bangumi.rss_link = (
            "https://mikanani.me/RSS/Bangumi?bangumiId=123&subgroupid=7"
        )

        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_execute_result)
        mock_session.commit = AsyncMock()

        with (
            patch("module.scheduler.jobs.rss_refresh.get_db_session") as mock_get_db,
            patch("module.scheduler.jobs.rss_refresh.create_downloader") as mock_create_downloader,
            patch("module.scheduler.jobs.rss_refresh.build_mikan_limiter_from_settings"),
            patch("module.scheduler.jobs.rss_refresh.MikanClient") as mock_mikan_cls,
            patch("module.scheduler.jobs.rss_refresh.MikanResolver"),
            patch("module.scheduler.jobs.rss_refresh.MikanEpisodeRefRepository"),
            patch("module.scheduler.jobs.rss_refresh.RSSRepository") as mock_rss_repo_cls,
            patch("module.scheduler.jobs.rss_refresh.BangumiRepository") as mock_bangumi_repo_cls,
            patch("module.scheduler.jobs.rss_refresh.RssPipeline") as mock_pipeline_cls,
            patch("module.scheduler.jobs.rss_refresh.RSSEngine.parse_rss_feed", return_value=[]),
            patch("module.scheduler.jobs.rss_refresh.RSSEngine.download_bangumi", new_callable=AsyncMock) as mock_download_bangumi,
            patch("module.scheduler.jobs.rss_refresh._trigger_downloads", new_callable=AsyncMock) as mock_trigger_downloads,
            patch("module.scheduler.jobs.rss_refresh._build_global_filter_pattern", return_value=None),
            patch("module.scheduler.jobs.rss_refresh.settings") as mock_settings,
        ):
            mock_get_db.return_value = mock_session_gen
            mock_create_downloader.return_value = AsyncMock()

            mock_settings.rss_parser.filter = []
            mock_settings.mikan.base_url = "https://mikanani.me"
            mock_settings.mikan.timeout_seconds = 10
            mock_settings.bangumi_manage.eps_complete = True
            mock_settings.bangumi_manage.eps_complete_from_source = True

            mock_mikan_client = AsyncMock()
            mock_mikan_cls.return_value.__aenter__ = AsyncMock(return_value=mock_mikan_client)
            mock_mikan_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_rss_repo = AsyncMock()
            mock_rss_repo.get_enabled = AsyncMock(return_value=[mock_rss_item])
            mock_rss_repo.update_status = AsyncMock()
            mock_rss_repo_cls.return_value = mock_rss_repo

            mock_bangumi_repo = AsyncMock()
            mock_bangumi_repo.get_by_rss = AsyncMock(return_value=[mock_bangumi])
            mock_bangumi_repo_cls.return_value = mock_bangumi_repo

            mock_pipeline = AsyncMock()
            mock_pipeline.run_for_feed = AsyncMock(return_value=PipelineResult(items_seen=0))
            mock_pipeline_cls.return_value = mock_pipeline

            mock_download_bangumi.return_value = {
                "status": True,
                "message": "Downloaded 12 torrents",
                "count": 12,
            }

            await rss_refresh_job()

        mock_download_bangumi.assert_awaited_once()
        assert mock_download_bangumi.await_args.args[2] == 99
        mock_trigger_downloads.assert_awaited_once()


class TestTriggerDownloads:
    @pytest.mark.integration
    async def test_skips_torrents_matching_bangumi_filter(self, db_session):
        """Direct downloader sync must honor per-bangumi exclusion filters."""
        from module.domain.models.bangumi import Bangumi
        from module.domain.models.series import Series
        from module.domain.models.torrent import Torrent
        from module.repositories.torrent import TorrentRepository

        series = Series(
            canonical_title="能帮我弄干净吗？",
            normalized_title="能帮我弄干净吗",
            season=1,
            root_path="/downloads/能帮我弄干净吗？",
            pending_review=False,
        )
        db_session.add(series)
        await db_session.flush()

        bangumi = Bangumi(
            series_id=series.id,
            rss_id=15,
            mikan_subgroup_id=1210,
            group_name="黑白字幕组",
            filter="简",
            rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=3826&subgroupid=1210",
            active=True,
        )
        db_session.add(bangumi)
        await db_session.flush()

        keep = Torrent(
            bangumi_id=bangumi.id,
            rss_id=15,
            name="[黑白字幕组] 可以帮忙洗干净吗？ [繁日内嵌]",
            url="https://example.com/trad.torrent",
            hash="trad",
            downloaded=False,
        )
        excluded = Torrent(
            bangumi_id=bangumi.id,
            rss_id=15,
            name="[黑白字幕组] 可以帮忙洗干净吗？ [简日内嵌]",
            url="https://example.com/simp.torrent",
            hash="simp",
            downloaded=False,
        )
        db_session.add_all([keep, excluded])
        await db_session.commit()

        downloader = AsyncMock()
        downloader.add_torrents = AsyncMock(return_value=True)

        await _trigger_downloads(db_session, downloader)
        await db_session.commit()

        downloader.add_torrents.assert_awaited_once()
        assert downloader.add_torrents.await_args.kwargs["urls"] == [
            "https://example.com/trad.torrent"
        ]

        torrents = await TorrentRepository(db_session).get_by_bangumi(bangumi.id)
        by_hash = {torrent.hash: torrent for torrent in torrents}
        assert by_hash["trad"].downloaded is True
        assert by_hash["simp"].downloaded is False
