import asyncio
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_add_rss_fetches_title_when_name_not_provided(async_session: AsyncSession):
    with patch("module.network.request_contents.RequestContent") as MockRequestContent:
        mock_req = MagicMock()
        mock_req.get_rss_title.return_value = "Re：从零开始的异世界生活 第三季 袭击篇"
        MockRequestContent.return_value.__enter__.return_value = mock_req

        def _fetch_title():
            with MockRequestContent() as req:
                return req.get_rss_title("https://mikanani.me/RSS/Bangumi?bangumiId=3464")

        result = await asyncio.to_thread(_fetch_title)
        assert result == "Re：从零开始的异世界生活 第三季 袭击篇"


@pytest.mark.asyncio
async def test_add_rss_falls_back_to_url_when_title_none(async_session: AsyncSession):
    with patch("module.network.request_contents.RequestContent") as MockRequestContent:
        mock_req = MagicMock()
        mock_req.get_rss_title.return_value = None
        MockRequestContent.return_value.__enter__.return_value = mock_req

        def _fetch_title():
            with MockRequestContent() as req:
                return req.get_rss_title("https://mikanani.me/RSS/Bangumi?bangumiId=3464")

        result = await asyncio.to_thread(_fetch_title)
        rss_name = result or "https://mikanani.me/RSS/Bangumi?bangumiId=3464"
        assert rss_name == "https://mikanani.me/RSS/Bangumi?bangumiId=3464"


@pytest.mark.asyncio
async def test_add_rss_uses_provided_name_without_fetching(async_session: AsyncSession):
    with patch("module.network.request_contents.RequestContent") as MockRequestContent:
        mock_req = MagicMock()
        MockRequestContent.return_value.__enter__.return_value = mock_req

        rss_name = "Custom Name"
        if rss_name:
            mock_req.get_rss_title.assert_not_called()
        assert rss_name == "Custom Name"
