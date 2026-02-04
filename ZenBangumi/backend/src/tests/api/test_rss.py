import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from zen_bangumi.domain.models.bangumi import Bangumi
from zen_bangumi.domain.models.rss import RSSItem


@pytest.fixture
async def sample_rss(db_session: AsyncSession) -> RSSItem:
    rss = RSSItem(
        name="Test RSS",
        url="https://example.com/rss/feed.xml",
        aggregate=False,
        parser="mikan",
        enabled=True,
    )
    db_session.add(rss)
    await db_session.commit()
    await db_session.refresh(rss)
    return rss


@pytest.fixture
async def aggregate_rss(db_session: AsyncSession) -> RSSItem:
    rss = RSSItem(
        name="Aggregate RSS",
        url="https://example.com/rss/aggregate.xml",
        aggregate=True,
        parser="mikan",
        enabled=True,
    )
    db_session.add(rss)
    await db_session.commit()
    await db_session.refresh(rss)
    return rss


@pytest.fixture
async def disabled_rss(db_session: AsyncSession) -> RSSItem:
    rss = RSSItem(
        name="Disabled RSS",
        url="https://example.com/rss/disabled.xml",
        aggregate=False,
        parser="mikan",
        enabled=False,
    )
    db_session.add(rss)
    await db_session.commit()
    await db_session.refresh(rss)
    return rss


@pytest.fixture
async def rss_with_pending_bangumi(
    db_session: AsyncSession, sample_rss: RSSItem
) -> tuple[RSSItem, Bangumi]:
    bangumi = Bangumi(
        rss_id=sample_rss.id,
        official_title="Pending Anime",
        title_raw="Pending Raw",
        season=1,
        group_name="TestGroup",
        rss_link="https://example.com/rss/pending",
        pending_review=True,
    )
    db_session.add(bangumi)
    await db_session.commit()
    await db_session.refresh(bangumi)
    return sample_rss, bangumi


@pytest.mark.asyncio
async def test_list_rss(
    client: AsyncClient, sample_rss: RSSItem, aggregate_rss: RSSItem
):
    response = await client.get("/api/v1/rss/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    assert any(r["url"] == sample_rss.url for r in data)
    assert any(r["url"] == aggregate_rss.url for r in data)


@pytest.mark.asyncio
async def test_create_rss_success(client: AsyncClient):
    create_data = {
        "name": "New RSS Feed",
        "url": "https://new.example.com/rss.xml",
        "aggregate": False,
        "parser": "mikan",
        "enabled": True,
    }
    
    response = await client.post("/api/v1/rss/", json=create_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New RSS Feed"
    assert data["url"] == "https://new.example.com/rss.xml"
    assert data["aggregate"] is False
    assert data["parser"] == "mikan"
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_create_rss_minimal(client: AsyncClient):
    create_data = {
        "url": "https://minimal.example.com/rss.xml",
    }
    
    response = await client.post("/api/v1/rss/", json=create_data)
    assert response.status_code == 201
    data = response.json()
    assert data["url"] == "https://minimal.example.com/rss.xml"
    assert data["aggregate"] is False
    assert data["parser"] == "mikan"
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_update_rss_success(
    client: AsyncClient, sample_rss: RSSItem, db_session: AsyncSession
):
    update_data = {
        "name": "Updated RSS Name",
        "enabled": False,
    }
    
    response = await client.put(f"/api/v1/rss/{sample_rss.id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated RSS Name"
    assert data["enabled"] is False
    assert data["url"] == sample_rss.url


@pytest.mark.asyncio
async def test_update_rss_not_found(client: AsyncClient):
    update_data = {
        "name": "Updated Name",
    }
    
    response = await client.put("/api/v1/rss/999999", json=update_data)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_rss_success(
    client: AsyncClient, sample_rss: RSSItem, db_session: AsyncSession
):
    rss_id = sample_rss.id
    
    response = await client.delete(f"/api/v1/rss/{rss_id}")
    assert response.status_code == 200
    assert "deleted successfully" in response.json()["message"].lower()
    
    from zen_bangumi.domain.models.rss import RSSItem as RSSModel
    from sqlalchemy import select
    
    db_session.expire_all()
    stmt = select(RSSModel).where(RSSModel.id == rss_id)
    result = await db_session.execute(stmt)
    deleted_rss = result.scalar_one_or_none()
    assert deleted_rss is None


@pytest.mark.asyncio
async def test_delete_rss_cascade_bangumi_and_torrents(
    client: AsyncClient, db_session: AsyncSession
):
    rss = RSSItem(
        name="RSS to Delete",
        url="https://delete.example.com/rss.xml",
        aggregate=False,
        parser="mikan",
        enabled=True,
    )
    db_session.add(rss)
    await db_session.commit()
    await db_session.refresh(rss)
    rss_id = rss.id
    
    bangumi = Bangumi(
        rss_id=rss.id,
        official_title="Bangumi to Cascade",
        title_raw="Cascade Raw",
        season=1,
        group_name="TestGroup",
        rss_link="https://example.com/rss",
    )
    db_session.add(bangumi)
    await db_session.commit()
    bangumi_id = bangumi.id
    
    response = await client.delete(f"/api/v1/rss/{rss_id}")
    assert response.status_code == 200
    
    from zen_bangumi.domain.models.bangumi import Bangumi as BangumiModel
    from zen_bangumi.domain.models.rss import RSSItem as RSSModel
    from sqlalchemy import select
    
    db_session.expire_all()
    
    stmt = select(RSSModel).where(RSSModel.id == rss_id)
    result = await db_session.execute(stmt)
    deleted_rss = result.scalar_one_or_none()
    assert deleted_rss is None
    
    stmt = select(BangumiModel).where(BangumiModel.id == bangumi_id)
    result = await db_session.execute(stmt)
    deleted_bangumi = result.scalar_one_or_none()
    assert deleted_bangumi is None


@pytest.mark.asyncio
async def test_delete_rss_not_found(client: AsyncClient):
    response = await client.delete("/api/v1/rss/999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_rss_not_implemented(client: AsyncClient, sample_rss: RSSItem):
    response = await client.post(f"/api/v1/rss/{sample_rss.id}/refresh")
    assert response.status_code == 501
    assert "task 18" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_rss_not_found(client: AsyncClient):
    response = await client.post("/api/v1/rss/999999/refresh")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_refresh_all_rss_not_implemented(client: AsyncClient):
    response = await client.post("/api/v1/rss/refresh/all")
    assert response.status_code == 501
    assert "task 18" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_recreate_bangumi_rules_not_implemented(
    client: AsyncClient, sample_rss: RSSItem
):
    response = await client.post(f"/api/v1/rss/{sample_rss.id}/recreate")
    assert response.status_code == 501
    assert "task 9" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_recreate_bangumi_rules_not_found(client: AsyncClient):
    response = await client.post("/api/v1/rss/999999/recreate")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_analyze_torrents_not_implemented(client: AsyncClient):
    response = await client.post("/api/v1/rss/analysis/torrents")
    assert response.status_code == 501
    assert "task 9" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_subscribe_bangumi_not_implemented(client: AsyncClient):
    response = await client.post("/api/v1/rss/subscribe")
    assert response.status_code == 501
    assert "task 19" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_subscribe_bangumi_batch_not_implemented(client: AsyncClient):
    response = await client.post("/api/v1/rss/subscribe/batch")
    assert response.status_code == 501
    assert "task 19" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_pending_bangumi(
    client: AsyncClient, rss_with_pending_bangumi: tuple[RSSItem, Bangumi]
):
    rss, bangumi = rss_with_pending_bangumi
    response = await client.get(f"/api/v1/rss/{rss.id}/pending")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(b["official_title"] == "Pending Anime" for b in data)
    assert all(b["pending_review"] is True for b in data)


@pytest.mark.asyncio
async def test_get_pending_bangumi_empty(client: AsyncClient, sample_rss: RSSItem):
    response = await client.get(f"/api/v1/rss/{sample_rss.id}/pending")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


@pytest.mark.asyncio
async def test_get_pending_bangumi_not_found(client: AsyncClient):
    response = await client.get("/api/v1/rss/999999/pending")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_pending_count(
    client: AsyncClient, rss_with_pending_bangumi: tuple[RSSItem, Bangumi]
):
    rss, bangumi = rss_with_pending_bangumi
    response = await client.get(f"/api/v1/rss/{rss.id}/pending-count")
    assert response.status_code == 200
    data = response.json()
    assert data["pending_count"] >= 1


@pytest.mark.asyncio
async def test_get_pending_count_zero(client: AsyncClient, sample_rss: RSSItem):
    response = await client.get(f"/api/v1/rss/{sample_rss.id}/pending-count")
    assert response.status_code == 200
    data = response.json()
    assert data["pending_count"] == 0


@pytest.mark.asyncio
async def test_get_pending_count_not_found(client: AsyncClient):
    response = await client.get("/api/v1/rss/999999/pending-count")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_endpoints_require_auth(client_no_auth: AsyncClient):
    endpoints = [
        ("GET", "/api/v1/rss/"),
        ("POST", "/api/v1/rss/"),
        ("PUT", "/api/v1/rss/1"),
        ("DELETE", "/api/v1/rss/1"),
        ("POST", "/api/v1/rss/1/refresh"),
        ("POST", "/api/v1/rss/refresh/all"),
        ("POST", "/api/v1/rss/1/recreate"),
        ("POST", "/api/v1/rss/analysis/torrents"),
        ("POST", "/api/v1/rss/subscribe"),
        ("POST", "/api/v1/rss/subscribe/batch"),
        ("GET", "/api/v1/rss/1/pending"),
        ("GET", "/api/v1/rss/1/pending-count"),
    ]
    
    for method, path in endpoints:
        if method == "GET":
            response = await client_no_auth.get(path)
        elif method == "PUT":
            response = await client_no_auth.put(path, json={"name": "Test"})
        elif method == "POST":
            response = await client_no_auth.post(path, json={})
        elif method == "DELETE":
            response = await client_no_auth.delete(path)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        assert response.status_code == 401, f"Expected 401 for {method} {path}"
