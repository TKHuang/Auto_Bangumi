"""Tests for TMDB API client adapter."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from tempfile import TemporaryDirectory

from zen_bangumi.effects.adapters.tmdb import TMDBClient, TMDBResult


class TestTMDBResult:
    """Tests for TMDBResult model."""

    def test_tmdb_result_creation_with_all_fields(self):
        """Test TMDBResult creation with all fields."""
        result = TMDBResult(
            id=1,
            name="Test Anime",
            poster_path="/abc123.jpg",
            first_air_date="2024-01-01",
        )

        assert result.id == 1
        assert result.name == "Test Anime"
        assert result.poster_path == "/abc123.jpg"
        assert result.first_air_date == "2024-01-01"

    def test_tmdb_result_creation_with_optional_fields_none(self):
        """Test TMDBResult creation with optional fields as None."""
        result = TMDBResult(
            id=2,
            name="Another Anime",
            poster_path=None,
            first_air_date=None,
        )

        assert result.id == 2
        assert result.name == "Another Anime"
        assert result.poster_path is None
        assert result.first_air_date is None


class TestTMDBClient:
    """Tests for TMDBClient class."""

    def test_tmdb_client_initialization(self):
        """Test TMDBClient initialization with API key."""
        client = TMDBClient(api_key="test_key_123")

        assert client.api_key == "test_key_123"
        assert client.BASE_URL == "https://api.themoviedb.org/3"
        assert client.POSTER_BASE_URL == "https://image.tmdb.org/t/p/w500"

    async def test_search_anime_returns_result_for_known_title(self):
        """Test search_anime returns TMDBResult for known title."""
        client = TMDBClient(api_key="test_key")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "id": 1,
                    "name": "Test Anime",
                    "poster_path": "/abc123.jpg",
                    "first_air_date": "2024-01-01",
                }
            ]
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await client.search_anime("Test Anime")

            assert result is not None
            assert result.id == 1
            assert result.name == "Test Anime"
            assert result.poster_path == "/abc123.jpg"
            assert result.first_air_date == "2024-01-01"

    async def test_search_anime_returns_none_for_unknown_title(self):
        """Test search_anime returns None for unknown title (404)."""
        client = TMDBClient(api_key="test_key")
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await client.search_anime("Unknown Anime Title XYZ")

            assert result is None

    async def test_search_anime_with_custom_language(self):
        """Test search_anime uses custom language parameter."""
        client = TMDBClient(api_key="test_key")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "id": 1,
                    "name": "Test Anime",
                    "poster_path": "/abc123.jpg",
                    "first_air_date": "2024-01-01",
                }
            ]
        }

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await client.search_anime("Test Anime", language="en-US")

            assert result is not None
            call_args = mock_get.call_args
            assert call_args[1]["params"]["language"] == "en-US"

    async def test_fetch_poster_downloads_and_saves_file(self):
        """Test fetch_poster downloads and saves file on cache miss."""
        client = TMDBClient(api_key="test_key")
        mock_response = MagicMock()
        mock_response.content = b"fake_image_data"

        with TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "posters" / "test.jpg"

            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_response

                result = await client.fetch_poster("/abc123.jpg", save_path)

                assert result == save_path
                assert save_path.exists()
                assert save_path.read_bytes() == b"fake_image_data"

    async def test_fetch_poster_cache_hit_returns_existing_file(self):
        """Test fetch_poster cache hit returns existing file without HTTP call."""
        client = TMDBClient(api_key="test_key")

        with TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "test.jpg"
            save_path.write_bytes(b"existing_image_data")

            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                result = await client.fetch_poster("/abc123.jpg", save_path)

                assert result == save_path
                assert save_path.read_bytes() == b"existing_image_data"
                mock_get.assert_not_called()

    async def test_fetch_poster_creates_parent_directories(self):
        """Test fetch_poster creates parent directories if they don't exist."""
        client = TMDBClient(api_key="test_key")
        mock_response = MagicMock()
        mock_response.content = b"fake_image_data"

        with TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "deep" / "nested" / "path" / "poster.jpg"

            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_response

                result = await client.fetch_poster("/abc123.jpg", save_path)

                assert result == save_path
                assert save_path.exists()
                assert save_path.parent.exists()

    async def test_fetch_poster_raises_on_http_error(self):
        """Test fetch_poster raises HTTPError on download failure."""
        client = TMDBClient(api_key="test_key")

        with TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "test.jpg"

            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_get.side_effect = Exception("Network error")

                with pytest.raises(Exception, match="Network error"):
                    await client.fetch_poster("/abc123.jpg", save_path)

    async def test_search_anime_api_url_construction(self):
        """Test search_anime constructs correct API URL."""
        client = TMDBClient(api_key="test_key_123")
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            await client.search_anime("Demon Slayer")

            call_args = mock_get.call_args
            assert call_args[0][0] == "https://api.themoviedb.org/3/search/tv"
            assert call_args[1]["params"]["query"] == "Demon Slayer"
            assert call_args[1]["params"]["api_key"] == "test_key_123"

    async def test_fetch_poster_url_construction(self):
        """Test fetch_poster constructs correct poster URL."""
        client = TMDBClient(api_key="test_key")
        mock_response = MagicMock()
        mock_response.content = b"fake_image_data"

        with TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "test.jpg"

            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_response

                await client.fetch_poster("/abc123.jpg", save_path)

                call_args = mock_get.call_args
                assert call_args[0][0] == "https://image.tmdb.org/t/p/w500/abc123.jpg"
