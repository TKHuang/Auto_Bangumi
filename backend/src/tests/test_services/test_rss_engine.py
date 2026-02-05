"""Tests for RSS Engine Service."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from module.domain.models.bangumi import Bangumi
from module.domain.models.rss import RSSItem
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
    """Sample bangumi."""
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


class TestMatchTorrentToBangumi:
    """Test match_torrent_to_bangumi function."""

    @pytest.mark.asyncio
    async def test_match_torrent_no_filter(self, async_session, sample_bangumi, sample_torrent):
        """Test matching torrent to bangumi with no filter."""
        from module.repositories import BangumiRepository
        
        # Create bangumi in DB
        bangumi_repo = BangumiRepository(async_session)
        created_bangumi = await bangumi_repo.create({
            "official_title": "Test Anime",
            "title_raw": "Test Anime",
            "season": 1,
            "group_name": "TestGroup",
            "rss_link": "https://example.com/rss",
            "poster_link": "",
            "filter": "",
            "added": False,
            "deleted": False,
            "eps_collect": True,
            "offset": 0,
        })
        await async_session.commit()
        
        # Match torrent
        matched = await RSSEngine.match_torrent_to_bangumi(
            sample_torrent, bangumi_repo
        )
        
        assert matched is not None
        assert matched.id == created_bangumi.id
        assert sample_torrent.bangumi_id == created_bangumi.id

    @pytest.mark.asyncio
    async def test_match_torrent_with_filter_excluded(self, async_session, sample_torrent):
        """Test matching torrent with filter that excludes it."""
        from module.repositories import BangumiRepository
        
        bangumi_repo = BangumiRepository(async_session)
        created_bangumi = await bangumi_repo.create({
            "official_title": "Test Anime",
            "title_raw": "Test Anime",
            "season": 1,
            "group_name": "TestGroup",
            "rss_link": "https://example.com/rss",
            "poster_link": "",
            "filter": "1080p",  # Filter excludes 1080p
            "added": False,
            "deleted": False,
            "eps_collect": True,
            "offset": 0,
        })
        await async_session.commit()
        
        # Torrent name contains "1080p", should be excluded
        matched = await RSSEngine.match_torrent_to_bangumi(
            sample_torrent, bangumi_repo
        )
        
        # Should still set bangumi_id but return None (filtered)
        assert matched is None
        assert sample_torrent.bangumi_id == created_bangumi.id

    @pytest.mark.asyncio
    async def test_match_torrent_with_filter_accepted(self, async_session):
        """Test matching torrent with filter that accepts it."""
        from module.repositories import BangumiRepository
        
        bangumi_repo = BangumiRepository(async_session)
        created_bangumi = await bangumi_repo.create({
            "official_title": "Test Anime",
            "title_raw": "Test Anime",
            "season": 1,
            "group_name": "TestGroup",
            "rss_link": "https://example.com/rss",
            "poster_link": "",
            "filter": "720p",  # Filter excludes 720p, not 1080p
            "added": False,
            "deleted": False,
            "eps_collect": True,
            "offset": 0,
        })
        await async_session.commit()
        
        torrent = Torrent(
            name="[TestGroup] Test Anime - 01 [1080p]",
            url="https://example.com/torrent.torrent",
            hash="hash1",
        )
        
        matched = await RSSEngine.match_torrent_to_bangumi(torrent, bangumi_repo)
        
        assert matched is not None
        assert matched.id == created_bangumi.id

    @pytest.mark.asyncio
    async def test_match_torrent_no_match(self, async_session, sample_torrent):
        """Test matching torrent with no matching bangumi."""
        from module.repositories import BangumiRepository
        
        bangumi_repo = BangumiRepository(async_session)
        
        matched = await RSSEngine.match_torrent_to_bangumi(
            sample_torrent, bangumi_repo
        )
        
        assert matched is None


class TestRefreshRSS:
    """Test refresh_rss function."""

    @pytest.mark.asyncio
    async def test_refresh_single_rss(
        self, async_session, mock_downloader, sample_rss, sample_bangumi
    ):
        """Test refreshing a single RSS feed."""
        from module.repositories import RSSRepository, BangumiRepository, TorrentRepository
        
        # Setup repositories
        rss_repo = RSSRepository(async_session)
        bangumi_repo = BangumiRepository(async_session)
        torrent_repo = TorrentRepository(async_session)
        
        # Create RSS and Bangumi
        created_rss = await rss_repo.create({
            "name": "Test RSS",
            "url": "https://example.com/rss",
            "aggregate": False,
            "parser": "mikan",
            "enabled": True,
        })
        created_bangumi = await bangumi_repo.create({
            "official_title": "Test Anime",
            "title_raw": "Test Anime",
            "season": 1,
            "group_name": "TestGroup",
            "rss_link": "https://example.com/rss",
            "rss_id": created_rss.id,
            "poster_link": "",
            "filter": "",
            "added": False,
            "deleted": False,
            "eps_collect": True,
            "offset": 0,
        })
        await async_session.commit()
        
        # Mock parse_rss_feed
        with patch.object(RSSEngine, "parse_rss_feed") as mock_parse:
            mock_parse.return_value = [
                Torrent(
                    name="[TestGroup] Test Anime - 01 [1080p]",
                    url="https://example.com/torrent1.torrent",
                    homepage="https://example.com/episode/1",
                    hash="hash1",
                ),
            ]
            
            # Refresh RSS
            await RSSEngine.refresh_rss(
                async_session, mock_downloader, rss_id=created_rss.id
            )
        
        await async_session.commit()
        
        # Verify torrent was created
        torrents = await torrent_repo.get_by_rss(created_rss.id)
        assert len(torrents) == 1
        assert torrents[0].name == "[TestGroup] Test Anime - 01 [1080p]"
        assert torrents[0].bangumi_id == created_bangumi.id
        assert torrents[0].downloaded == True
        
        # Verify downloader was called
        mock_downloader.add_torrents.assert_called_once()
        
        # Verify RSS status updated
        updated_rss = await rss_repo.get_by_id(created_rss.id)
        assert updated_rss.last_status == "Success"
        assert updated_rss.last_error is None
        assert updated_rss.last_update is not None

    @pytest.mark.asyncio
    async def test_refresh_rss_error_handling(
        self, async_session, mock_downloader
    ):
        """Test refresh_rss handles errors gracefully."""
        from module.repositories import RSSRepository
        
        rss_repo = RSSRepository(async_session)
        
        # Create RSS
        created_rss = await rss_repo.create({
            "name": "Test RSS",
            "url": "https://example.com/rss",
            "aggregate": False,
            "parser": "mikan",
            "enabled": True,
        })
        await async_session.commit()
        
        # Mock parse_rss_feed to raise exception
        with patch.object(RSSEngine, "parse_rss_feed") as mock_parse:
            mock_parse.side_effect = Exception("Network error")
            
            # Refresh RSS should not raise
            await RSSEngine.refresh_rss(
                async_session, mock_downloader, rss_id=created_rss.id
            )
        
        await async_session.commit()
        
        # Verify RSS status shows error
        updated_rss = await rss_repo.get_by_id(created_rss.id)
        assert updated_rss.last_status == "Error"
        assert "Network error" in updated_rss.last_error
        assert updated_rss.last_update is not None

    @pytest.mark.asyncio
    async def test_refresh_rss_skip_unmatched_torrents(
        self, async_session, mock_downloader
    ):
        """Test refresh_rss skips torrents with no matching bangumi."""
        from module.repositories import RSSRepository, TorrentRepository
        
        rss_repo = RSSRepository(async_session)
        torrent_repo = TorrentRepository(async_session)
        
        # Create RSS (no bangumi)
        created_rss = await rss_repo.create({
            "name": "Test RSS",
            "url": "https://example.com/rss",
            "aggregate": False,
            "parser": "mikan",
            "enabled": True,
        })
        await async_session.commit()
        
        # Mock parse_rss_feed
        with patch.object(RSSEngine, "parse_rss_feed") as mock_parse:
            mock_parse.return_value = [
                Torrent(
                    name="[TestGroup] Unknown Anime - 01 [1080p]",
                    url="https://example.com/torrent1.torrent",
                    hash="hash1",
                ),
            ]
            
            await RSSEngine.refresh_rss(
                async_session, mock_downloader, rss_id=created_rss.id
            )
        
        await async_session.commit()
        
        # Verify no torrents were created
        torrents = await torrent_repo.get_by_rss(created_rss.id)
        assert len(torrents) == 0
        
        # Verify downloader was NOT called
        mock_downloader.add_torrents.assert_not_called()


class TestRefreshAllRSS:
    """Test refresh_all_rss function."""

    @pytest.mark.asyncio
    async def test_refresh_all_enabled_rss(
        self, async_session, mock_downloader
    ):
        """Test refreshing all enabled RSS feeds."""
        from module.repositories import RSSRepository, BangumiRepository
        
        rss_repo = RSSRepository(async_session)
        bangumi_repo = BangumiRepository(async_session)
        
        # Create two enabled RSS feeds
        rss1 = await rss_repo.create({
            "name": "RSS 1",
            "url": "https://example.com/rss1",
            "enabled": True,
        })
        rss2 = await rss_repo.create({
            "name": "RSS 2",
            "url": "https://example.com/rss2",
            "enabled": True,
        })
        
        # Create one disabled RSS (should be skipped)
        await rss_repo.create({
            "name": "RSS 3",
            "url": "https://example.com/rss3",
            "enabled": False,
        })
        
        # Create bangumi for each RSS
        await bangumi_repo.create({
            "official_title": "Anime 1",
            "title_raw": "Anime 1",
            "season": 1,
            "group_name": "Group1",
            "rss_link": "https://example.com/rss1",
            "rss_id": rss1.id,
            "poster_link": "",
            "filter": "",
        })
        await bangumi_repo.create({
            "official_title": "Anime 2",
            "title_raw": "Anime 2",
            "season": 1,
            "group_name": "Group2",
            "rss_link": "https://example.com/rss2",
            "rss_id": rss2.id,
            "poster_link": "",
            "filter": "",
        })
        await async_session.commit()
        
        # Mock parse_rss_feed
        with patch.object(RSSEngine, "parse_rss_feed") as mock_parse:
            mock_parse.return_value = []  # No new torrents
            
            await RSSEngine.refresh_all_rss(async_session, mock_downloader)
        
        await async_session.commit()
        
        # Verify parse was called twice (only for enabled RSS)
        assert mock_parse.call_count == 2
        
        # Verify both RSS feeds were updated
        updated_rss1 = await rss_repo.get_by_id(rss1.id)
        updated_rss2 = await rss_repo.get_by_id(rss2.id)
        assert updated_rss1.last_update is not None
        assert updated_rss2.last_update is not None


class TestCreateBangumiFromTorrent:
    """Test create_bangumi_from_torrent function."""

    @pytest.mark.asyncio
    async def test_create_bangumi_success(
        self, async_session, mock_downloader
    ):
        """Test creating bangumi from torrent."""
        from module.repositories import RSSRepository, TorrentRepository
        
        rss_repo = RSSRepository(async_session)
        torrent_repo = TorrentRepository(async_session)
        
        # Create RSS and torrent
        rss = await rss_repo.create({
            "name": "Test RSS",
            "url": "https://example.com/rss",
            "enabled": True,
        })
        
        torrent = await torrent_repo.create({
            "name": "[TestGroup] Test Anime - 01 [1080p]",
            "url": "https://example.com/torrent.torrent",
            "hash": "hash1",
            "rss_id": rss.id,
        })
        await async_session.commit()
        
        # Mock parser
        with patch("module.services.rss_engine.TitleParser") as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser_class.return_value = mock_parser
            
            # Mock raw_parser to return bangumi data
            mock_bangumi = Bangumi(
                official_title="Test Anime",
                title_raw="Test Anime",
                season=1,
                group_name="TestGroup",
                poster_link="",
                filter="",
            )
            mock_parser.raw_parser.return_value = mock_bangumi
            
            # Create bangumi from torrent
            result = await RSSEngine.create_bangumi_from_torrent(
                async_session, mock_downloader, torrent.id
            )
        
        await async_session.commit()
        
        assert result["status"] is True
        assert result["bangumi_id"] is not None
        
        # Verify torrent is linked to bangumi
        updated_torrent = await torrent_repo.get_by_hash("hash1")
        assert updated_torrent.bangumi_id is not None
        assert updated_torrent.downloaded is True

    @pytest.mark.asyncio
    async def test_create_bangumi_duplicate(self, async_session, mock_downloader):
        """Test creating bangumi when duplicate exists."""
        from module.repositories import RSSRepository, TorrentRepository, BangumiRepository
        
        rss_repo = RSSRepository(async_session)
        torrent_repo = TorrentRepository(async_session)
        bangumi_repo = BangumiRepository(async_session)
        
        # Create RSS, bangumi, and torrent
        rss = await rss_repo.create({
            "name": "Test RSS",
            "url": "https://example.com/rss",
            "enabled": True,
        })
        
        existing_bangumi = await bangumi_repo.create({
            "official_title": "Test Anime",
            "title_raw": "Test Anime",
            "season": 1,
            "group_name": "TestGroup",
            "rss_link": "https://example.com/rss",
            "poster_link": "",
            "filter": "",
        })
        
        torrent = await torrent_repo.create({
            "name": "[TestGroup] Test Anime - 01 [1080p]",
            "url": "https://example.com/torrent.torrent",
            "hash": "hash1",
            "rss_id": rss.id,
        })
        await async_session.commit()
        
        # Mock parser
        with patch("module.services.rss_engine.TitleParser") as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser_class.return_value = mock_parser
            
            mock_bangumi = Bangumi(
                official_title="Test Anime",
                title_raw="Test Anime",
                season=1,
                group_name="TestGroup",
                poster_link="",
                filter="",
            )
            mock_parser.raw_parser.return_value = mock_bangumi
            
            result = await RSSEngine.create_bangumi_from_torrent(
                async_session, mock_downloader, torrent.id
            )
        
        assert result["status"] is False
        assert "already exists" in result["message"].lower()


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
        
        # Create bangumi
        bangumi = await bangumi_repo.create({
            "official_title": "Test Anime",
            "title_raw": "Test Anime",
            "season": 1,
            "group_name": "TestGroup",
            "rss_link": "https://example.com/rss",
            "poster_link": "",
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
        
        # Create bangumi with filter
        bangumi = await bangumi_repo.create({
            "official_title": "Test Anime",
            "title_raw": "Test Anime",
            "season": 1,
            "group_name": "TestGroup",
            "rss_link": "https://example.com/rss",
            "poster_link": "",
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
