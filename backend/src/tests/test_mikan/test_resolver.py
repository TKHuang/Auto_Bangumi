"""MikanResolver orchestrator tests (spec §8)."""
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from module.concurrency.rate_limiter import RateLimiter
from module.mikan.client import MikanClient
from module.mikan.resolver import MikanResolver
from module.repositories.mikan_ref import MikanEpisodeRefRepository

_FIX = Path(__file__).parent.parent / "fixtures" / "mikan"


def _load(name: str) -> str:
    return (_FIX / name).read_text(encoding="utf-8")


@pytest.fixture
def fake_limiter():
    return RateLimiter(max_concurrent=4, min_interval_ms=0)


@pytest.mark.integration
class TestMikanResolverCacheHit:
    async def test_returns_cached_ok_without_network(
        self, db_session, fake_limiter, httpx_mock: HTTPXMock
    ):
        repo = MikanEpisodeRefRepository(db_session)
        await repo.upsert(
            info_hash="cached",
            parse_status="ok",
            mikan_bangumi_id=7,
            mikan_subgroup_id=8,
            canonical_title="Cached",
            poster_url="/p.jpg",
        )
        await db_session.commit()

        async with MikanClient("https://mikanani.me", 10) as client:
            resolver = MikanResolver(client=client, limiter=fake_limiter, mikan_ref_repo=repo)
            ref = await resolver.resolve("cached")

        # No HTTP calls should have been made.
        assert httpx_mock.get_requests() == []
        assert ref is not None
        assert ref.mikan_bangumi_id == 7


@pytest.mark.integration
class TestMikanResolverCacheMiss:
    async def test_fetches_parses_persists(
        self, db_session, fake_limiter, httpx_mock: HTTPXMock
    ):
        httpx_mock.add_response(
            url="https://mikanani.me/Home/Episode/newhash",
            text=_load("episode_page_subscribe_button.html"),
            status_code=200,
        )
        # Resolver now caches the poster locally — mock the image fetch.
        httpx_mock.add_response(
            url="https://mikanani.me/images/Bangumi/202410/730372c2.jpg",
            content=b"\x89PNG\r\n",
            status_code=200,
        )

        repo = MikanEpisodeRefRepository(db_session)
        with patch(
            "module.mikan.resolver.save_image",
            return_value="posters/abc12345.jpg",
        ):
            async with MikanClient("https://mikanani.me", 10) as client:
                resolver = MikanResolver(
                    client=client, limiter=fake_limiter, mikan_ref_repo=repo
                )
                ref = await resolver.resolve("newhash")
                await db_session.commit()

        assert ref is not None
        assert ref.mikan_bangumi_id == 3906
        assert ref.mikan_subgroup_id == 370
        # Poster URL is now the cached local path, not the raw Mikan path.
        assert ref.poster_url == "posters/abc12345.jpg"

        row = await repo.get("newhash")
        assert row.parse_status == "ok"
        assert row.mikan_bangumi_id == 3906
        assert row.canonical_title.startswith("身为悲剧")
        assert row.poster_url == "posters/abc12345.jpg"

    async def test_poster_fetch_failure_keeps_raw_url(
        self, db_session, fake_limiter, httpx_mock: HTTPXMock
    ):
        """If the poster image cannot be downloaded, fall back to whatever
        the parser extracted (still better than dropping the URL entirely).
        Resolution itself must not fail."""
        httpx_mock.add_response(
            url="https://mikanani.me/Home/Episode/posterfail",
            text=_load("episode_page_subscribe_button.html"),
            status_code=200,
        )
        httpx_mock.add_response(
            url="https://mikanani.me/images/Bangumi/202410/730372c2.jpg",
            status_code=502,
        )

        repo = MikanEpisodeRefRepository(db_session)
        async with MikanClient("https://mikanani.me", 10) as client:
            resolver = MikanResolver(
                client=client, limiter=fake_limiter, mikan_ref_repo=repo
            )
            ref = await resolver.resolve("posterfail")
            await db_session.commit()

        assert ref is not None
        assert ref.mikan_bangumi_id == 3906
        # Raw poster path preserved on cache failure.
        assert ref.poster_url and ref.poster_url.startswith("/images/")

    async def test_non_mikan_page_persists_as_non_mikan(
        self, db_session, fake_limiter, httpx_mock: HTTPXMock
    ):
        httpx_mock.add_response(
            url="https://mikanani.me/Home/Episode/notmikan",
            text=_load("episode_page_no_ref.html"),
            status_code=200,
        )

        repo = MikanEpisodeRefRepository(db_session)
        async with MikanClient("https://mikanani.me", 10) as client:
            resolver = MikanResolver(client=client, limiter=fake_limiter, mikan_ref_repo=repo)
            ref = await resolver.resolve("notmikan")
            await db_session.commit()

        assert ref is None
        row = await repo.get("notmikan")
        assert row.parse_status == "non_mikan"

    async def test_http_error_persists_as_failed_and_records_limiter(
        self, db_session, fake_limiter, httpx_mock: HTTPXMock
    ):
        httpx_mock.add_response(
            url="https://mikanani.me/Home/Episode/boom",
            status_code=503,
        )

        repo = MikanEpisodeRefRepository(db_session)
        async with MikanClient("https://mikanani.me", 10) as client:
            resolver = MikanResolver(client=client, limiter=fake_limiter, mikan_ref_repo=repo)
            ref = await resolver.resolve("boom")
            await db_session.commit()

        assert ref is None
        row = await repo.get("boom")
        assert row.parse_status == "failed"
        assert "503" in row.last_error
        assert fake_limiter.is_degraded() is True


@pytest.mark.integration
class TestMikanResolverSkipsCachedNonMikan:
    """Once cached as non_mikan, never retried per spec §6.1."""

    async def test_cached_non_mikan_is_not_refetched(
        self, db_session, fake_limiter, httpx_mock: HTTPXMock
    ):
        repo = MikanEpisodeRefRepository(db_session)
        await repo.upsert(info_hash="skip", parse_status="non_mikan")
        await db_session.commit()

        async with MikanClient("https://mikanani.me", 10) as client:
            resolver = MikanResolver(client=client, limiter=fake_limiter, mikan_ref_repo=repo)
            ref = await resolver.resolve("skip")

        assert ref is None
        assert httpx_mock.get_requests() == []
