import pytest
from collections.abc import AsyncIterator
from unittest.mock import patch

from zen_bangumi.services.search import SearchResult, search_anime
from zen_bangumi.domain.parser.mikan_parser import SearchResult as ParserSearchResult


@pytest.mark.asyncio
async def test_search_anime_returns_async_iterator():
    """search_anime should return an AsyncIterator."""
    result = search_anime("test", providers=["mikan"])
    
    assert isinstance(result, AsyncIterator)


@pytest.mark.asyncio
async def test_search_anime_yields_success_results():
    """search_anime should yield success results from Mikan adapter."""
    mock_parser_results = [
        ParserSearchResult(
            mikan_id="123",
            title="Frieren: Beyond Journey's End",
            year="2023",
            poster_url="https://example.com/poster.jpg",
        ),
        ParserSearchResult(
            mikan_id="456",
            title="Frieren Season 2",
            year="2024",
            poster_url=None,
        ),
    ]
    
    async def mock_search(keyword: str) -> AsyncIterator[ParserSearchResult]:
        for result in mock_parser_results:
            yield result
    
    with patch("zen_bangumi.services.search.MikanAdapter") as MockAdapter:
        mock_instance = MockAdapter.return_value
        mock_instance.search = mock_search
        
        results = []
        async for result in search_anime("Frieren", providers=["mikan"]):
            results.append(result)
        
        assert len(results) == 2
        
        assert results[0].provider == "mikan"
        assert results[0].status == "success"
        assert results[0].mikan_id == "123"
        assert results[0].title == "Frieren: Beyond Journey's End"
        assert results[0].year == "2023"
        assert results[0].poster_url == "https://example.com/poster.jpg"
        assert results[0].error_message is None
        
        assert results[1].provider == "mikan"
        assert results[1].status == "success"
        assert results[1].mikan_id == "456"
        assert results[1].title == "Frieren Season 2"
        assert results[1].year == "2024"
        assert results[1].poster_url is None


@pytest.mark.asyncio
async def test_search_anime_provider_error_yields_error_result():
    """search_anime should yield error result when provider fails."""
    async def mock_search_error(keyword: str) -> AsyncIterator[ParserSearchResult]:
        raise Exception("Network timeout")
        yield  # Make it a generator
    
    with patch("zen_bangumi.services.search.MikanAdapter") as MockAdapter:
        mock_instance = MockAdapter.return_value
        mock_instance.search = mock_search_error
        
        results = []
        async for result in search_anime("test", providers=["mikan"]):
            results.append(result)
        
        assert len(results) == 1
        assert results[0].provider == "mikan"
        assert results[0].status == "error"
        assert results[0].error_message == "Network timeout"
        assert results[0].mikan_id is None
        assert results[0].title is None


@pytest.mark.asyncio
async def test_search_anime_unknown_provider_yields_error():
    """search_anime should yield error for unknown providers."""
    results = []
    async for result in search_anime("test", providers=["unknown_provider"]):
        results.append(result)
    
    assert len(results) == 1
    assert results[0].provider == "unknown_provider"
    assert results[0].status == "error"
    assert "Unknown provider" in results[0].error_message


@pytest.mark.asyncio
async def test_search_anime_default_provider_is_mikan():
    """search_anime should default to mikan provider when none specified."""
    mock_parser_results = [
        ParserSearchResult(
            mikan_id="789",
            title="Test Anime",
            year=None,
            poster_url=None,
        ),
    ]
    
    async def mock_search(keyword: str) -> AsyncIterator[ParserSearchResult]:
        for result in mock_parser_results:
            yield result
    
    with patch("zen_bangumi.services.search.MikanAdapter") as MockAdapter:
        mock_instance = MockAdapter.return_value
        mock_instance.search = mock_search
        
        results = []
        async for result in search_anime("test"):
            results.append(result)
        
        assert len(results) == 1
        assert results[0].provider == "mikan"


@pytest.mark.asyncio
async def test_search_anime_streaming_behavior():
    """search_anime should yield results as they arrive (streaming)."""
    yielded_order = []
    
    async def mock_search_with_delay(keyword: str) -> AsyncIterator[ParserSearchResult]:
        for i in range(3):
            yielded_order.append(f"yield_{i}")
            yield ParserSearchResult(
                mikan_id=str(i),
                title=f"Anime {i}",
                year=None,
                poster_url=None,
            )
    
    with patch("zen_bangumi.services.search.MikanAdapter") as MockAdapter:
        mock_instance = MockAdapter.return_value
        mock_instance.search = mock_search_with_delay
        
        received_order = []
        async for result in search_anime("test", providers=["mikan"]):
            received_order.append(f"received_{result.mikan_id}")
        
        assert len(received_order) == 3
        assert received_order[0] == "received_0"
        assert received_order[1] == "received_1"
        assert received_order[2] == "received_2"


@pytest.mark.asyncio
async def test_search_anime_multiple_providers():
    """search_anime should handle multiple providers sequentially."""
    mock_parser_results = [
        ParserSearchResult(
            mikan_id="111",
            title="Mikan Result",
            year=None,
            poster_url=None,
        ),
    ]
    
    async def mock_search(keyword: str) -> AsyncIterator[ParserSearchResult]:
        for result in mock_parser_results:
            yield result
    
    with patch("zen_bangumi.services.search.MikanAdapter") as MockAdapter:
        mock_instance = MockAdapter.return_value
        mock_instance.search = mock_search
        
        results = []
        async for result in search_anime("test", providers=["mikan", "unknown"]):
            results.append(result)
        
        assert len(results) == 2
        assert results[0].provider == "mikan"
        assert results[0].status == "success"
        assert results[1].provider == "unknown"
        assert results[1].status == "error"


@pytest.mark.asyncio
async def test_search_result_model_validation():
    """SearchResult model should validate correctly."""
    success_result = SearchResult(
        provider="mikan",
        status="success",
        mikan_id="123",
        title="Test Anime",
        year="2024",
        poster_url="https://example.com/poster.jpg",
    )
    
    assert success_result.provider == "mikan"
    assert success_result.status == "success"
    assert success_result.error_message is None
    
    error_result = SearchResult(
        provider="mikan",
        status="error",
        error_message="Connection failed",
    )
    
    assert error_result.provider == "mikan"
    assert error_result.status == "error"
    assert error_result.mikan_id is None
    assert error_result.title is None
