"""Search service for anime search with SSE streaming support.

This module provides search functionality that yields results as they arrive
from various providers (currently Mikan only).
"""

import logging
from collections.abc import AsyncIterator
from typing import Literal

from pydantic import BaseModel

from ..effects.adapters.mikan import MikanAdapter

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """Search result for SSE streaming.
    
    Represents a single anime search result or error from a provider.
    """
    
    provider: str
    status: Literal["success", "error"]
    
    # Success fields
    mikan_id: str | None = None
    title: str | None = None
    year: str | None = None
    poster_url: str | None = None
    
    # Error fields
    error_message: str | None = None


async def search_anime(
    keyword: str,
    providers: list[str] | None = None,
) -> AsyncIterator[SearchResult]:
    """Search for anime across providers and yield results as they arrive.
    
    Args:
        keyword: Search keyword (anime title)
        providers: List of provider names (default: ["mikan"])
        
    Yields:
        SearchResult objects (success or error)
        
    Example:
        >>> async for result in search_anime("Frieren"):
        ...     if result.status == "success":
        ...         print(f"Found: {result.title}")
        ...     else:
        ...         print(f"Error: {result.error_message}")
    """
    if providers is None:
        providers = ["mikan"]
    
    for provider_name in providers:
        if provider_name == "mikan":
            async for result in _search_mikan(keyword):
                yield result
        else:
            # Unknown provider - yield error
            yield SearchResult(
                provider=provider_name,
                status="error",
                error_message=f"Unknown provider: {provider_name}",
            )


async def _search_mikan(keyword: str) -> AsyncIterator[SearchResult]:
    """Search Mikan provider and yield results.
    
    Args:
        keyword: Search keyword
        
    Yields:
        SearchResult objects (success or error)
    """
    adapter = MikanAdapter()
    
    try:
        async for parser_result in adapter.search(keyword):
            # Convert parser SearchResult to service SearchResult
            yield SearchResult(
                provider="mikan",
                status="success",
                mikan_id=parser_result.mikan_id,
                title=parser_result.title,
                year=parser_result.year,
                poster_url=parser_result.poster_url,
            )
    except Exception as e:
        logger.error(f"Mikan search error for '{keyword}': {e}")
        yield SearchResult(
            provider="mikan",
            status="error",
            error_message=str(e),
        )
