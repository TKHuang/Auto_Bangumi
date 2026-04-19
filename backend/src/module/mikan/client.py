"""HTTPX async wrapper for Mikan episode page fetches (spec §8.2).

Wraps base_url + timeout config. Does NOT do rate limiting (that's the
RateLimiter's job, applied at the caller side). Does NOT do retries — the
resolver owns retry policy via the pending_torrent_enrichment queue.

Errors are normalized to MikanFetchError so the resolver can uniformly write
parse_status='failed' + last_error to the cache.
"""
from __future__ import annotations

from typing import Optional

import httpx


class MikanFetchError(Exception):
    """Raised when fetching a Mikan page fails (HTTP non-2xx or network error).

    Attributes:
      status: HTTP status if the server responded; None for connection errors.
    """

    def __init__(self, message: str, *, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


class MikanClient:
    def __init__(self, base_url: str, timeout_seconds: int):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "MikanClient":
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch_episode_page(self, info_hash: str) -> tuple[str, int]:
        """Fetch /Home/Episode/{info_hash}. Returns (html, status_code).

        Raises MikanFetchError on non-2xx or network errors.
        """
        assert self._client is not None, "use MikanClient as an async context manager"
        url = f"{self._base_url}/Home/Episode/{info_hash}"
        try:
            response = await self._client.get(url)
        except httpx.HTTPError as exc:
            raise MikanFetchError(str(exc), status=None) from exc

        if response.status_code >= 400:
            raise MikanFetchError(
                f"HTTP {response.status_code} from {url}",
                status=response.status_code,
            )
        return response.text, response.status_code

    async def fetch_image(self, url_or_path: str) -> bytes:
        """Fetch an image by absolute URL or path (relative to base_url).

        Strips any querystring (Mikan appends ``?width=…&height=…`` for the
        responsive renderer; the underlying file is the same). Raises
        MikanFetchError on non-2xx / network errors.
        """
        assert self._client is not None, "use MikanClient as an async context manager"
        clean = url_or_path.split("?", 1)[0]
        if clean.startswith(("http://", "https://")):
            url = clean
        else:
            url = f"{self._base_url}{clean if clean.startswith('/') else '/' + clean}"
        try:
            response = await self._client.get(url)
        except httpx.HTTPError as exc:
            raise MikanFetchError(str(exc), status=None) from exc

        if response.status_code >= 400:
            raise MikanFetchError(
                f"HTTP {response.status_code} from {url}",
                status=response.status_code,
            )
        return response.content
