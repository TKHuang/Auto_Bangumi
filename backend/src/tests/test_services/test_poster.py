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


def _make_bangumi_mock(
    id: int = 1,
    title: str = "Anime",
    season: int = 1,
    poster_url: str | None = None,
    version: int = 1,
) -> MagicMock:
    """Create a MagicMock bangumi with a properly configured series sub-mock."""
    series_mock = MagicMock()
    series_mock.canonical_title = title
    series_mock.season = season
    series_mock.poster_url = poster_url

    bangumi = MagicMock()
    bangumi.id = id
    bangumi.version = version
    bangumi.series = series_mock
    bangumi.rss_id = None
    return bangumi


class TestFetchPoster:
    """Tests for fetch_poster method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "tmdb_info, expected",
        [
            pytest.param(
                MagicMock(poster_link="posters/abc123.jpg", title="Test Anime"),
                "posters/abc123.jpg",
                id="success",
            ),
            pytest.param(None, None, id="not_found"),
            pytest.param(
                MagicMock(poster_link=None, title="Test Anime"),
                None,
                id="no_poster_link",
            ),
        ],
    )
    async def test_fetch_poster(self, poster_service, tmdb_info, expected):
        """Test poster fetch result follows the TMDB lookup's poster_link."""
        import sys
        import types

        mock_module = types.ModuleType("tmdb_parser")
        mock_module.tmdb_parser = MagicMock(return_value=tmdb_info)

        with patch.dict(sys.modules, {"module.domain.parser.analyser.tmdb_parser": mock_module}):
            result = await poster_service.fetch_poster("Test Anime", season=1)
            assert result == expected

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


class TestRefreshPoster:
    """Tests for refresh_poster method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "title, poster_link",
        [
            pytest.param("Anime 1", "posters/new123.jpg", id="poster_link_returned"),
            pytest.param("Test Anime", "posters/new.jpg", id="message_includes_title"),
        ],
    )
    async def test_refresh_poster_success(self, poster_service, title, poster_link):
        """Test successful refresh of single poster."""
        bangumi = _make_bangumi_mock(id=1, title=title, poster_url=None)

        with patch.object(
            poster_service.bangumi_repo, "get_by_id"
        ) as mock_get:
            with patch.object(
                poster_service.bangumi_repo, "update_simple"
            ) as mock_update:
                with patch.object(
                    poster_service, "fetch_poster"
                ) as mock_fetch:
                    mock_get.return_value = bangumi
                    mock_fetch.return_value = poster_link

                    result = await poster_service.refresh_poster(1)

                    assert result["success"] is True
                    assert result["poster_link"] == poster_link
                    assert title in result["message"]
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
        bangumi = _make_bangumi_mock(id=1, title="Anime 1", poster_url=None)

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
        bangumi = _make_bangumi_mock(id=1, title="Anime 1", poster_url=None)

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
    async def test_refresh_poster_tries_mikan_first(self, poster_service):
        """Mikan RSS bangumi: the Mikan page poster wins; TMDB is not asked."""
        bangumi = _make_bangumi_mock(id=1, title="Anime 1")
        bangumi.rss_id = 7
        parser = MagicMock()
        parser.mikan_parser_with_rss.return_value = MagicMock(
            poster_link="posters/mikan.jpg"
        )

        with patch.object(poster_service.bangumi_repo, "get_by_id", return_value=bangumi), \
             patch.object(poster_service.bangumi_repo, "update_simple") as mock_update, \
             patch.object(
                 poster_service.rss_repo, "get_by_id",
                 return_value=MagicMock(parser="mikan"),
             ), \
             patch.object(
                 poster_service.torrent_repo, "get_by_bangumi_with_homepage",
                 return_value=MagicMock(homepage="https://mikanani.me/Home/Episode/x"),
             ), \
             patch("module.services.poster.TitleParser", return_value=parser), \
             patch.object(poster_service, "fetch_poster") as mock_fetch:
            result = await poster_service.refresh_poster(1)

        assert result["success"] is True
        mock_fetch.assert_not_called()
        mock_update.assert_called_once_with(1, {"poster_link": "posters/mikan.jpg"})

    @pytest.mark.asyncio
    async def test_refresh_poster_falls_back_to_tmdb_when_mikan_fails(self, poster_service):
        """A Mikan parser error is logged; TMDB supplies the poster."""
        bangumi = _make_bangumi_mock(id=1, title="Anime 1")
        bangumi.rss_id = 7
        parser = MagicMock()
        parser.mikan_parser_with_rss.side_effect = RuntimeError("page down")

        with patch.object(poster_service.bangumi_repo, "get_by_id", return_value=bangumi), \
             patch.object(poster_service.bangumi_repo, "update_simple") as mock_update, \
             patch.object(
                 poster_service.rss_repo, "get_by_id",
                 return_value=MagicMock(parser="mikan"),
             ), \
             patch.object(
                 poster_service.torrent_repo, "get_by_bangumi_with_homepage",
                 return_value=MagicMock(homepage="https://mikanani.me/Home/Episode/x"),
             ), \
             patch("module.services.poster.TitleParser", return_value=parser), \
             patch.object(poster_service, "fetch_poster", return_value="posters/tmdb.jpg"):
            result = await poster_service.refresh_poster(1)

        assert result["poster_link"] == "posters/tmdb.jpg"
        mock_update.assert_called_once_with(1, {"poster_link": "posters/tmdb.jpg"})
