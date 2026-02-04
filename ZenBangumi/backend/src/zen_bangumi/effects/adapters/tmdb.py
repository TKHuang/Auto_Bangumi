"""TMDB API client adapter for anime metadata and poster fetching."""

import logging
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class TMDBResult(BaseModel):
    """TMDB search result model."""

    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str
    poster_path: Optional[str] = Field(None, alias="poster_path")
    first_air_date: Optional[str] = Field(None, alias="first_air_date")


class TMDBClient:
    """TMDB API client for anime metadata and poster fetching."""

    BASE_URL = "https://api.themoviedb.org/3"
    POSTER_BASE_URL = "https://image.tmdb.org/t/p/w500"

    def __init__(self, api_key: str):
        """
        Initialize TMDB client.

        Args:
            api_key: TMDB API key
        """
        self.api_key = api_key

    async def search_anime(
        self, title: str, season: int = 1, language: str = "zh-CN"
    ) -> Optional[TMDBResult]:
        """
        Search for anime on TMDB.

        Args:
            title: Anime title to search
            season: Season number (for reference, not used in search)
            language: Language code for search results

        Returns:
            TMDBResult if found, None otherwise

        Raises:
            httpx.HTTPError: If API request fails
        """
        url = f"{self.BASE_URL}/search/tv"
        params = {
            "query": title,
            "language": language,
            "api_key": self.api_key,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()

            data = response.json()
            results = data.get("results", [])

            if not results:
                logger.debug(f"No TMDB results found for: {title}")
                return None

            # Return the first result
            first_result = results[0]
            logger.debug(f"TMDB found: {first_result.get('name')} (ID: {first_result.get('id')})")

            return TMDBResult(
                id=first_result.get("id"),
                name=first_result.get("name"),
                poster_path=first_result.get("poster_path"),
                first_air_date=first_result.get("first_air_date"),
            )

    async def fetch_poster(self, poster_path: str, save_to: Path) -> Path:
        """
        Download and cache poster image.

        Implements poster caching:
        - If poster already exists at save_to, return path immediately (cache hit)
        - If not, download and save (cache miss)

        Args:
            poster_path: TMDB poster path (e.g., "/abc123.jpg")
            save_to: Path to save poster file

        Returns:
            Path to saved poster file

        Raises:
            httpx.HTTPError: If download fails
            IOError: If file save fails
        """
        # Cache hit: file already exists
        if save_to.exists():
            logger.debug(f"Poster cache hit: {save_to}")
            return save_to

        # Cache miss: download poster
        url = f"{self.POSTER_BASE_URL}{poster_path}"
        logger.debug(f"Downloading poster from: {url}")

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()

        # Ensure parent directory exists
        save_to.parent.mkdir(parents=True, exist_ok=True)

        # Save poster to file
        save_to.write_bytes(response.content)
        logger.debug(f"Poster saved to: {save_to}")

        return save_to
