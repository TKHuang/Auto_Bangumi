"""MikanClient HTTP wrapper tests."""
import pytest
from pytest_httpx import HTTPXMock

from module.mikan.client import MikanClient, MikanFetchError


@pytest.mark.unit
class TestMikanClientFetchEpisode:
    async def test_fetches_episode_page(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://mikanani.me/Home/Episode/abc123",
            text="<html><body>ok</body></html>",
            status_code=200,
        )
        async with MikanClient(base_url="https://mikanani.me", timeout_seconds=10) as c:
            html, status = await c.fetch_episode_page("abc123")
        assert status == 200
        assert "<html>" in html

    async def test_uses_configured_base_url(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://custom-mirror.example/Home/Episode/xyz",
            text="<html></html>",
            status_code=200,
        )
        async with MikanClient(base_url="https://custom-mirror.example", timeout_seconds=5) as c:
            await c.fetch_episode_page("xyz")
        # pytest_httpx fails if no matching request

    async def test_raises_on_http_503(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://mikanani.me/Home/Episode/boom",
            status_code=503,
            text="Service Unavailable",
        )
        async with MikanClient(base_url="https://mikanani.me", timeout_seconds=10) as c:
            with pytest.raises(MikanFetchError) as exc:
                await c.fetch_episode_page("boom")
        assert exc.value.status == 503

    async def test_raises_on_http_429(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://mikanani.me/Home/Episode/throttled",
            status_code=429,
        )
        async with MikanClient(base_url="https://mikanani.me", timeout_seconds=10) as c:
            with pytest.raises(MikanFetchError) as exc:
                await c.fetch_episode_page("throttled")
        assert exc.value.status == 429

    async def test_raises_on_network_error(self, httpx_mock: HTTPXMock):
        import httpx
        httpx_mock.add_exception(httpx.ConnectError("boom"))
        async with MikanClient(base_url="https://mikanani.me", timeout_seconds=1) as c:
            with pytest.raises(MikanFetchError) as exc:
                await c.fetch_episode_page("x")
        assert exc.value.status is None
        assert "boom" in str(exc.value)
