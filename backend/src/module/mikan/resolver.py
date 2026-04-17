"""MikanResolver — orchestrates cache + rate-limited fetch + parse + persist
(spec §8).

Flow per resolve(info_hash):
  1. Check mikan_episode_ref cache
     - parse_status='ok'        → return MikanRef from row (no network)
     - parse_status='non_mikan' → return None (no network, never retry)
     - parse_status='failed'    → retry path (fall through to fetch)
     - cache miss               → fetch path
  2. Acquire rate limiter, fetch page via MikanClient
  3. Feed limiter HTTP status (so 429/503 triggers degradation)
  4. Parse HTML
     - MikanRef extracted   → upsert cache as 'ok', return ref
     - No ref extracted      → upsert cache as 'non_mikan', return None
  5. On fetch error: upsert cache as 'failed' + last_error, return None
"""
from __future__ import annotations

from typing import Optional

from module.concurrency.rate_limiter import RateLimiter
from module.mikan.client import MikanClient, MikanFetchError
from module.mikan.parser import MikanRef, parse_mikan_page
from module.repositories.mikan_ref import MikanEpisodeRefRepository


class MikanResolver:
    def __init__(
        self,
        client: MikanClient,
        limiter: RateLimiter,
        mikan_ref_repo: MikanEpisodeRefRepository,
    ):
        self._client = client
        self._limiter = limiter
        self._repo = mikan_ref_repo

    async def resolve(self, info_hash: str) -> Optional[MikanRef]:
        """Return MikanRef on success, None if the page is not a Mikan episode
        page or the fetch failed. All outcomes persist to mikan_episode_ref."""
        cached = await self._repo.get(info_hash)
        if cached is not None:
            if cached.parse_status == "ok":
                return MikanRef(
                    mikan_bangumi_id=cached.mikan_bangumi_id,
                    mikan_subgroup_id=cached.mikan_subgroup_id,
                    canonical_title=cached.canonical_title,
                    poster_url=cached.poster_url,
                )
            if cached.parse_status == "non_mikan":
                return None
            # parse_status == "failed" → fall through and retry

        async with self._limiter:
            try:
                html, status = await self._client.fetch_episode_page(info_hash)
                self._limiter.record_result(status)
            except MikanFetchError as exc:
                if exc.status is not None:
                    self._limiter.record_result(exc.status)
                await self._repo.upsert(
                    info_hash=info_hash,
                    parse_status="failed",
                    last_error=str(exc),
                )
                return None

        ref = parse_mikan_page(html)
        if ref is None:
            await self._repo.upsert(
                info_hash=info_hash,
                parse_status="non_mikan",
            )
            return None

        await self._repo.upsert(
            info_hash=info_hash,
            parse_status="ok",
            mikan_bangumi_id=ref.mikan_bangumi_id,
            mikan_subgroup_id=ref.mikan_subgroup_id,
            canonical_title=ref.canonical_title,
            poster_url=ref.poster_url,
        )
        return ref
