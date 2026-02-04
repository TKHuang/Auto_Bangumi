"""Tests for search API endpoints."""

import pytest
from fastapi import status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_providers_requires_auth(client_no_auth: AsyncClient):
    """Test that listing providers requires authentication."""
    response = await client_no_auth.get("/api/v1/search/providers")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_list_providers_returns_mikan(client: AsyncClient):
    """Test that providers endpoint returns mikan in the list."""
    response = await client.get("/api/v1/search/providers")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert "providers" in data
    assert isinstance(data["providers"], list)
    assert "mikan" in data["providers"]


@pytest.mark.asyncio
async def test_search_anime_requires_auth(client_no_auth: AsyncClient):
    """Test that searching anime requires authentication."""
    response = await client_no_auth.get("/api/v1/search/test")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_search_anime_returns_501(client: AsyncClient):
    """Test that search endpoint returns 501 (blocked by Task 20)."""
    response = await client.get("/api/v1/search/test")
    assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
    
    data = response.json()
    assert "detail" in data
    assert "Task 20" in data["detail"] or "Not implemented" in data["detail"]


@pytest.mark.asyncio
async def test_search_anime_with_special_characters(client: AsyncClient):
    """Test that search handles special characters in keyword."""
    response = await client.get("/api/v1/search/test%20anime%20%E3%81%82")
    assert response.status_code == status.HTTP_501_NOT_IMPLEMENTED
