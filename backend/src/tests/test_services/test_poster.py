"""Tests for poster service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models import Bangumi, TorrentState
from module.repositories import BangumiRepository
from module.services.poster import PosterService


@pytest.fixture
def mock_session():
    """Create mock AsyncSession."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def poster_service(mock_session):
    """Create PosterService with mock session."""
    return PosterService(mock_session)


class TestFetchPoster:
    """Tests for fetch_poster method."""

    @pytest.mark.asyncio
    async def test_fetch_poster_success(self, poster_service):
        """Test successful poster fetch from TMDB."""
        import sys
        import types
        
        # Mock the tmdb_parser function at the point where it's imported
        mock_tmdb_info = MagicMock(
            poster_link="posters/abc123.jpg",
            title="Test Anime",
        )
        
        # Create a mock module for tmdb_parser
        mock_module = types.ModuleType("tmdb_parser")
        mock_module.tmdb_parser = MagicMock(return_value=mock_tmdb_info)
        
        # Patch the import inside fetch_poster
        with patch.dict(sys.modules, {"module.domain.parser.analyser.tmdb_parser": mock_module}):
            result = await poster_service.fetch_poster("Test Anime", season=1)
            assert result == "posters/abc123.jpg"

    @pytest.mark.asyncio
    async def test_fetch_poster_not_found(self, poster_service):
        """Test poster fetch when TMDB returns no results."""
        import sys
        import types
        
        mock_module = types.ModuleType("tmdb_parser")
        mock_module.tmdb_parser = MagicMock(return_value=None)
        
        with patch.dict(sys.modules, {"module.domain.parser.analyser.tmdb_parser": mock_module}):
            result = await poster_service.fetch_poster("Unknown Anime", season=1)
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_poster_no_poster_link(self, poster_service):
        """Test poster fetch when TMDB result has no poster_link."""
        import sys
        import types
        
        mock_tmdb_info = MagicMock(poster_link=None, title="Test Anime")
        mock_module = types.ModuleType("tmdb_parser")
        mock_module.tmdb_parser = MagicMock(return_value=mock_tmdb_info)
        
        with patch.dict(sys.modules, {"module.domain.parser.analyser.tmdb_parser": mock_module}):
            result = await poster_service.fetch_poster("Test Anime", season=1)
            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_poster_with_season(self, poster_service):
        """Test fetch_poster passes season parameter."""
        import sys
        import types
        
        mock_tmdb_info = MagicMock(
            poster_link="posters/xyz789.jpg",
            title="Test Anime",
        )
        mock_module = types.ModuleType("tmdb_parser")
        mock_tmdb_func = MagicMock(return_value=mock_tmdb_info)
        mock_module.tmdb_parser = mock_tmdb_func
        
        with patch.dict(sys.modules, {"module.domain.parser.analyser.tmdb_parser": mock_module}):
            await poster_service.fetch_poster("Test Anime", season=2)
            # Verify tmdb_parser was called
            mock_tmdb_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_poster_uses_language_setting(self, poster_service):
        """Test fetch_poster uses language from settings."""
        import sys
        import types
        
        mock_tmdb_info = MagicMock(
            poster_link="posters/abc123.jpg",
            title="Test Anime",
        )
        mock_module = types.ModuleType("tmdb_parser")
        mock_tmdb_func = MagicMock(return_value=mock_tmdb_info)
        mock_module.tmdb_parser = mock_tmdb_func
        
        with patch.dict(sys.modules, {"module.domain.parser.analyser.tmdb_parser": mock_module}):
            with patch("module.services.poster.settings") as mock_settings:
                mock_settings.rss_parser.language = "zh"
                
                await poster_service.fetch_poster("Test Anime")
                
                # Verify language was passed to tmdb_parser
                call_args = mock_tmdb_func.call_args
                assert call_args[0][1] == "zh"


class TestRefreshAllPosters:
    """Tests for refresh_all_posters method."""

    @pytest.mark.asyncio
    async def test_refresh_all_posters_success(self, poster_service):
        """Test successful refresh of all posters."""
        # Create mock bangumi
        bangumi1 = MagicMock(
            id=1,
            official_title="Anime 1",
            season=1,
            poster_link=None,
            version=1,
        )
        bangumi2 = MagicMock(
            id=2,
            official_title="Anime 2",
            season=1,
            poster_link="posters/existing.jpg",
            version=1,
        )

        with patch.object(
            poster_service.bangumi_repo, "get_active"
        ) as mock_get_active:
            with patch.object(
                poster_service.bangumi_repo, "update"
            ) as mock_update:
                with patch.object(
                    poster_service, "fetch_poster"
                ) as mock_fetch:
                    mock_get_active.return_value = [bangumi1, bangumi2]
                    mock_fetch.return_value = "posters/new123.jpg"

                    result = await poster_service.refresh_all_posters()

                    assert result["total"] == 2
                    assert result["updated"] == 1
                    assert result["failed"] == 0
                    # Should only update bangumi1 (bangumi2 already has poster)
                    mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_all_posters_no_results(self, poster_service):
        """Test refresh when no bangumi found."""
        with patch.object(
            poster_service.bangumi_repo, "get_active"
        ) as mock_get_active:
            mock_get_active.return_value = []

            result = await poster_service.refresh_all_posters()

            assert result["total"] == 0
            assert result["updated"] == 0
            assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_refresh_all_posters_fetch_failure(self, poster_service):
        """Test refresh when poster fetch fails."""
        bangumi = MagicMock(
            id=1,
            official_title="Anime 1",
            season=1,
            poster_link=None,
            version=1,
        )

        with patch.object(
            poster_service.bangumi_repo, "get_active"
        ) as mock_get_active:
            with patch.object(poster_service, "fetch_poster") as mock_fetch:
                mock_get_active.return_value = [bangumi]
                mock_fetch.return_value = None

                result = await poster_service.refresh_all_posters()

                assert result["total"] == 1
                assert result["updated"] == 0
                assert result["failed"] == 1

    @pytest.mark.asyncio
    async def test_refresh_all_posters_exception_handling(self, poster_service):
        """Test refresh handles exceptions gracefully."""
        bangumi = MagicMock(
            id=1,
            official_title="Anime 1",
            season=1,
            poster_link=None,
            version=1,
        )

        with patch.object(
            poster_service.bangumi_repo, "get_active"
        ) as mock_get_active:
            with patch.object(poster_service, "fetch_poster") as mock_fetch:
                mock_get_active.return_value = [bangumi]
                mock_fetch.side_effect = Exception("Network error")

                result = await poster_service.refresh_all_posters()

                assert result["total"] == 1
                assert result["updated"] == 0
                assert result["failed"] == 1

    @pytest.mark.asyncio
    async def test_refresh_all_posters_skips_existing(self, poster_service):
        """Test refresh skips bangumi that already have posters."""
        bangumi = MagicMock(
            id=1,
            official_title="Anime 1",
            season=1,
            poster_link="posters/existing.jpg",
            version=1,
        )

        with patch.object(
            poster_service.bangumi_repo, "get_active"
        ) as mock_get_active:
            with patch.object(poster_service, "fetch_poster") as mock_fetch:
                mock_get_active.return_value = [bangumi]

                result = await poster_service.refresh_all_posters()

                assert result["total"] == 1
                assert result["updated"] == 0
                assert result["failed"] == 0
                # fetch_poster should not be called for bangumi with existing poster
                mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_all_posters_multiple_updates(self, poster_service):
        """Test refresh updates multiple bangumi."""
        bangumi1 = MagicMock(
            id=1,
            official_title="Anime 1",
            season=1,
            poster_link=None,
            version=1,
        )
        bangumi2 = MagicMock(
            id=2,
            official_title="Anime 2",
            season=1,
            poster_link=None,
            version=1,
        )

        with patch.object(
            poster_service.bangumi_repo, "get_active"
        ) as mock_get_active:
            with patch.object(
                poster_service.bangumi_repo, "update"
            ) as mock_update:
                with patch.object(
                    poster_service, "fetch_poster"
                ) as mock_fetch:
                    mock_get_active.return_value = [bangumi1, bangumi2]
                    mock_fetch.side_effect = [
                        "posters/new1.jpg",
                        "posters/new2.jpg",
                    ]

                    result = await poster_service.refresh_all_posters()

                    assert result["total"] == 2
                    assert result["updated"] == 2
                    assert result["failed"] == 0
                    assert mock_update.call_count == 2


class TestRefreshPoster:
    """Tests for refresh_poster method."""

    @pytest.mark.asyncio
    async def test_refresh_poster_success(self, poster_service):
        """Test successful refresh of single poster."""
        bangumi = MagicMock(
            id=1,
            official_title="Anime 1",
            season=1,
            poster_link=None,
            version=1,
        )

        with patch.object(
            poster_service.bangumi_repo, "get_by_id"
        ) as mock_get:
            with patch.object(
                poster_service.bangumi_repo, "update"
            ) as mock_update:
                with patch.object(
                    poster_service, "fetch_poster"
                ) as mock_fetch:
                    mock_get.return_value = bangumi
                    mock_fetch.return_value = "posters/new123.jpg"

                    result = await poster_service.refresh_poster(1)

                    assert result["success"] is True
                    assert result["poster_link"] == "posters/new123.jpg"
                    mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_refresh_poster_not_found(self, poster_service):
        """Test refresh when bangumi not found."""
        with patch.object(
            poster_service.bangumi_repo, "get_by_id"
        ) as mock_get:
            mock_get.return_value = None

            with pytest.raises(ValueError, match="Bangumi not found"):
                await poster_service.refresh_poster(999)

    @pytest.mark.asyncio
    async def test_refresh_poster_fetch_failure(self, poster_service):
        """Test refresh when poster fetch fails."""
        bangumi = MagicMock(
            id=1,
            official_title="Anime 1",
            season=1,
            poster_link=None,
            version=1,
        )

        with patch.object(
            poster_service.bangumi_repo, "get_by_id"
        ) as mock_get:
            with patch.object(poster_service, "fetch_poster") as mock_fetch:
                mock_get.return_value = bangumi
                mock_fetch.return_value = None

                result = await poster_service.refresh_poster(1)

                assert result["success"] is False
                assert result["poster_link"] is None

    @pytest.mark.asyncio
    async def test_refresh_poster_exception_handling(self, poster_service):
        """Test refresh handles exceptions gracefully."""
        bangumi = MagicMock(
            id=1,
            official_title="Anime 1",
            season=1,
            poster_link=None,
            version=1,
        )

        with patch.object(
            poster_service.bangumi_repo, "get_by_id"
        ) as mock_get:
            with patch.object(poster_service, "fetch_poster") as mock_fetch:
                mock_get.return_value = bangumi
                mock_fetch.side_effect = Exception("Network error")

                result = await poster_service.refresh_poster(1)

                assert result["success"] is False
                assert "Error" in result["message"]

    @pytest.mark.asyncio
    async def test_refresh_poster_returns_message(self, poster_service):
        """Test refresh returns appropriate messages."""
        bangumi = MagicMock(
            id=1,
            official_title="Test Anime",
            season=1,
            poster_link=None,
            version=1,
        )

        with patch.object(
            poster_service.bangumi_repo, "get_by_id"
        ) as mock_get:
            with patch.object(
                poster_service.bangumi_repo, "update"
            ) as mock_update:
                with patch.object(
                    poster_service, "fetch_poster"
                ) as mock_fetch:
                    mock_get.return_value = bangumi
                    mock_fetch.return_value = "posters/new.jpg"

                    result = await poster_service.refresh_poster(1)

                    assert "Test Anime" in result["message"]
                    assert result["success"] is True
