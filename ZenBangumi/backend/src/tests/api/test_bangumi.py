import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from zen_bangumi.domain.models.bangumi import Bangumi
from zen_bangumi.domain.models.torrent import Torrent


@pytest.fixture
async def sample_bangumi(db_session: AsyncSession) -> Bangumi:
    bangumi = Bangumi(
        official_title="Test Anime",
        title_raw="Test Anime Raw",
        season=1,
        group_name="TestGroup",
        filter="720,\\d+-\\d+",
        rss_link="https://example.com/rss",
        offset=0,
        version=1,
    )
    db_session.add(bangumi)
    await db_session.commit()
    await db_session.refresh(bangumi)
    return bangumi


@pytest.fixture
async def pending_bangumi(db_session: AsyncSession) -> Bangumi:
    bangumi = Bangumi(
        official_title="Pending Anime",
        title_raw="Pending Anime Raw",
        season=1,
        group_name="TestGroup",
        filter="720",
        rss_link="https://example.com/rss/pending",
        pending_review=True,
        version=1,
    )
    db_session.add(bangumi)
    await db_session.commit()
    await db_session.refresh(bangumi)
    return bangumi


@pytest.fixture
async def sample_torrent(db_session: AsyncSession, sample_bangumi: Bangumi) -> Torrent:
    torrent = Torrent(
        hash="abc123",
        name="Test Anime - 01.mkv",
        bangumi_id=sample_bangumi.id,
        downloaded=True,
    )
    db_session.add(torrent)
    await db_session.commit()
    await db_session.refresh(torrent)
    return torrent


@pytest.mark.asyncio
async def test_list_bangumi_all(
    client: AsyncClient, sample_bangumi: Bangumi, pending_bangumi: Bangumi
):
    response = await client.get("/api/v1/bangumi/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    assert any(b["official_title"] == "Test Anime" for b in data)


@pytest.mark.asyncio
async def test_list_bangumi_filter_active(
    client: AsyncClient, sample_bangumi: Bangumi, pending_bangumi: Bangumi
):
    response = await client.get("/api/v1/bangumi/", params={"active": True})
    assert response.status_code == 200
    data = response.json()
    assert all(not b["pending_review"] for b in data)
    assert any(b["official_title"] == "Test Anime" for b in data)
    assert not any(b["official_title"] == "Pending Anime" for b in data)


@pytest.mark.asyncio
async def test_list_bangumi_filter_pending_review(
    client: AsyncClient, sample_bangumi: Bangumi, pending_bangumi: Bangumi
):
    response = await client.get("/api/v1/bangumi/", params={"pending_review": True})
    assert response.status_code == 200
    data = response.json()
    assert all(b["pending_review"] for b in data)
    assert any(b["official_title"] == "Pending Anime" for b in data)
    assert not any(b["official_title"] == "Test Anime" for b in data)


@pytest.mark.asyncio
async def test_list_bangumi_filter_season(
    client: AsyncClient, db_session: AsyncSession
):
    bangumi1 = Bangumi(
        official_title="Season 1 Anime",
        title_raw="S1",
        season=1,
        group_name="G1",
        rss_link="https://example.com/s1",
    )
    bangumi2 = Bangumi(
        official_title="Season 2 Anime",
        title_raw="S2",
        season=2,
        group_name="G2",
        rss_link="https://example.com/s2",
    )
    db_session.add_all([bangumi1, bangumi2])
    await db_session.commit()
    
    response = await client.get("/api/v1/bangumi/", params={"season": 2})
    assert response.status_code == 200
    data = response.json()
    assert all(b["season"] == 2 for b in data)
    assert any(b["official_title"] == "Season 2 Anime" for b in data)


@pytest.mark.asyncio
async def test_get_bangumi_by_id(client: AsyncClient, sample_bangumi: Bangumi):
    response = await client.get(f"/api/v1/bangumi/{sample_bangumi.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_bangumi.id
    assert data["official_title"] == "Test Anime"
    assert data["version"] == 1


@pytest.mark.asyncio
async def test_get_bangumi_not_found(client: AsyncClient):
    response = await client.get("/api/v1/bangumi/999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_bangumi_success(
    client: AsyncClient, sample_bangumi: Bangumi, db_session: AsyncSession
):
    update_data = {
        "official_title": "Updated Anime Title",
        "season": 2,
        "offset": 5,
        "version": 1,
    }
    
    response = await client.put(
        f"/api/v1/bangumi/{sample_bangumi.id}", json=update_data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["official_title"] == "Updated Anime Title"
    assert data["season"] == 2
    assert data["offset"] == 5
    assert data["version"] == 2


@pytest.mark.asyncio
async def test_update_bangumi_version_conflict(
    client: AsyncClient, sample_bangumi: Bangumi
):
    update_data = {
        "official_title": "Updated Title",
        "version": 999,
    }
    
    response = await client.put(
        f"/api/v1/bangumi/{sample_bangumi.id}", json=update_data
    )
    assert response.status_code == 409
    assert "version conflict" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_bangumi_not_found(client: AsyncClient):
    update_data = {
        "official_title": "Updated Title",
        "version": 1,
    }
    
    response = await client.put("/api/v1/bangumi/999999", json=update_data)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_bangumi_success(
    client: AsyncClient, sample_bangumi: Bangumi, db_session: AsyncSession
):
    bangumi_id = sample_bangumi.id
    
    response = await client.delete(f"/api/v1/bangumi/{bangumi_id}")
    assert response.status_code == 200
    assert "deleted successfully" in response.json()["message"].lower()
    
    await db_session.refresh(sample_bangumi)
    assert sample_bangumi.deleted is True


@pytest.mark.asyncio
async def test_delete_bangumi_with_file_option(
    client: AsyncClient, sample_bangumi: Bangumi
):
    response = await client.delete(
        f"/api/v1/bangumi/{sample_bangumi.id}", params={"file": True}
    )
    assert response.status_code == 501
    assert "not yet implemented" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_bangumi_not_found(client: AsyncClient):
    response = await client.delete("/api/v1/bangumi/999999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_rename_bangumi_not_implemented(
    client: AsyncClient, sample_bangumi: Bangumi
):
    response = await client.post(f"/api/v1/bangumi/{sample_bangumi.id}/rename")
    assert response.status_code == 501
    assert "not yet implemented" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_activate_bangumi_not_pending(
    client: AsyncClient, sample_bangumi: Bangumi
):
    response = await client.post(f"/api/v1/bangumi/{sample_bangumi.id}/activate")
    assert response.status_code == 400
    assert "not in pending review state" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_activate_bangumi_not_implemented(
    client: AsyncClient, pending_bangumi: Bangumi
):
    response = await client.post(f"/api/v1/bangumi/{pending_bangumi.id}/activate")
    assert response.status_code == 501
    assert "not yet implemented" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_activate_bangumi_not_found(client: AsyncClient):
    response = await client.post("/api/v1/bangumi/999999/activate")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_collect_bangumi_not_implemented(
    client: AsyncClient, sample_bangumi: Bangumi
):
    response = await client.post(f"/api/v1/bangumi/{sample_bangumi.id}/collect")
    assert response.status_code == 501
    assert "not yet implemented" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_bangumi_torrents(
    client: AsyncClient, sample_bangumi: Bangumi, sample_torrent: Torrent
):
    response = await client.get(f"/api/v1/bangumi/{sample_bangumi.id}/torrents")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["id"] == sample_torrent.id
    assert data[0]["name"] == "Test Anime - 01.mkv"
    assert data[0]["bangumi_id"] == sample_bangumi.id


@pytest.mark.asyncio
async def test_get_bangumi_torrents_not_found(client: AsyncClient):
    response = await client.get("/api/v1/bangumi/999999/torrents")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_bangumi_poster(
    client: AsyncClient, db_session: AsyncSession
):
    bangumi = Bangumi(
        official_title="Anime with Poster",
        title_raw="Poster Test",
        season=1,
        group_name="TestGroup",
        rss_link="https://example.com/rss",
        poster_link="https://example.com/poster.jpg",
    )
    db_session.add(bangumi)
    await db_session.commit()
    await db_session.refresh(bangumi)
    
    response = await client.get(f"/api/v1/bangumi/{bangumi.id}/poster")
    assert response.status_code == 200
    assert "https://example.com/poster.jpg" in response.json()["message"]


@pytest.mark.asyncio
async def test_get_bangumi_poster_not_found(
    client: AsyncClient, sample_bangumi: Bangumi
):
    response = await client.get(f"/api/v1/bangumi/{sample_bangumi.id}/poster")
    assert response.status_code == 404
    assert "no poster" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_bangumi_poster_not_implemented(
    client: AsyncClient, sample_bangumi: Bangumi
):
    response = await client.put(f"/api/v1/bangumi/{sample_bangumi.id}/poster")
    assert response.status_code == 501
    assert "not yet implemented" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_batch_activate_not_implemented(client: AsyncClient):
    data = {"bangumi_ids": [1, 2, 3]}
    response = await client.post("/api/v1/bangumi/activate/batch", json=data)
    assert response.status_code == 501
    assert "not yet implemented" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_batch_delete_success(
    client: AsyncClient, db_session: AsyncSession
):
    bangumi1 = Bangumi(
        official_title="Batch Delete 1",
        title_raw="BD1",
        season=1,
        group_name="G1",
        rss_link="https://example.com/bd1",
    )
    bangumi2 = Bangumi(
        official_title="Batch Delete 2",
        title_raw="BD2",
        season=1,
        group_name="G2",
        rss_link="https://example.com/bd2",
    )
    db_session.add_all([bangumi1, bangumi2])
    await db_session.commit()
    await db_session.refresh(bangumi1)
    await db_session.refresh(bangumi2)
    
    bangumi_ids = [bangumi1.id, bangumi2.id]
    response = await client.request(
        "DELETE",
        "/api/v1/bangumi/batch",
        content=json.dumps(bangumi_ids),
        headers={"Content-Type": "application/json"},
    )
    if response.status_code != 200:
        print(f"Error response: {response.json()}")
    assert response.status_code == 200
    assert "deleted 2 bangumi successfully" in response.json()["message"].lower()
    
    await db_session.refresh(bangumi1)
    await db_session.refresh(bangumi2)
    assert bangumi1.deleted is True
    assert bangumi2.deleted is True


@pytest.mark.asyncio
async def test_batch_delete_with_errors(
    client: AsyncClient, sample_bangumi: Bangumi
):
    bangumi_ids = [sample_bangumi.id, 999999]
    response = await client.request(
        "DELETE",
        "/api/v1/bangumi/batch",
        content=json.dumps(bangumi_ids),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200
    message = response.json()["message"].lower()
    assert "deleted 1 bangumi" in message
    assert "1 errors" in message


@pytest.mark.asyncio
async def test_endpoints_require_auth(client_no_auth: AsyncClient):
    endpoints = [
        ("GET", "/api/v1/bangumi/"),
        ("GET", "/api/v1/bangumi/1"),
        ("PUT", "/api/v1/bangumi/1"),
        ("DELETE", "/api/v1/bangumi/1"),
        ("POST", "/api/v1/bangumi/1/rename"),
        ("POST", "/api/v1/bangumi/1/activate"),
        ("POST", "/api/v1/bangumi/1/collect"),
        ("GET", "/api/v1/bangumi/1/torrents"),
        ("GET", "/api/v1/bangumi/1/poster"),
        ("PUT", "/api/v1/bangumi/1/poster"),
        ("POST", "/api/v1/bangumi/activate/batch"),
        ("DELETE", "/api/v1/bangumi/batch"),
    ]
    
    for method, path in endpoints:
        if method == "GET":
            response = await client_no_auth.get(path)
        elif method == "PUT":
            response = await client_no_auth.put(
                path, json={"version": 1}
            )
        elif method == "POST":
            response = await client_no_auth.post(
                path, json={"bangumi_ids": [1]}
            )
        elif method == "DELETE":
            response = await client_no_auth.request(
                "DELETE",
                path,
                content=json.dumps([1]),
                headers={"Content-Type": "application/json"},
            )
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        assert response.status_code == 401, f"Expected 401 for {method} {path}"
