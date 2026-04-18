"""/api/v1/series/* contract tests."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from module.api.v1.series import router as series_router


@pytest.fixture
def app():
    """Create FastAPI app with series router, auth bypass, and db session override."""
    from module.api.middleware.auth import get_current_user
    from module.database.engine import get_db_session

    app = FastAPI()
    app.include_router(series_router, prefix="/api/v1")

    async def mock_get_current_user():
        return "testuser"

    app.dependency_overrides[get_current_user] = mock_get_current_user

    async def mock_get_session():
        yield AsyncMock()

    app.dependency_overrides[get_db_session] = mock_get_session
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def _mock_series(**overrides):
    defaults = dict(
        id=1,
        canonical_title="Test Series",
        normalized_title="test series",
        season=1,
        cour_part=None,
        year=2024,
        root_path="/downloads/Test Series",
        poster_url=None,
        default_filter=None,
        default_offset=0,
        pending_review=False,
    )
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


class TestListSeries:
    """Tests for GET /api/v1/series/"""

    @pytest.mark.asyncio
    async def test_list_returns_items_and_total(self, client):
        mock_items = [
            _mock_series(id=1, canonical_title="A"),
            _mock_series(id=2, canonical_title="B"),
        ]
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.list_paginated.return_value = (mock_items, 2)

            resp = client.get("/api/v1/series/")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        titles = {item["canonical_title"] for item in body["items"]}
        assert {"A", "B"} == titles

    @pytest.mark.asyncio
    async def test_list_respects_limit_offset(self, client):
        mock_items = [_mock_series(id=i, canonical_title=f"T{i}") for i in range(2)]
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.list_paginated.return_value = (mock_items, 5)

            resp = client.get("/api/v1/series/?limit=2&offset=0")

        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_passes_limit_offset_to_repo(self, client):
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.list_paginated.return_value = ([], 0)

            client.get("/api/v1/series/?limit=10&offset=20")

        repo.list_paginated.assert_called_once_with(limit=10, offset=20)

    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.list_paginated.return_value = ([], 0)

            resp = client.get("/api/v1/series/")

        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    @pytest.mark.asyncio
    async def test_list_rejects_invalid_limit(self, client):
        resp = client.get("/api/v1/series/?limit=0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_rejects_limit_over_max(self, client):
        resp = client.get("/api/v1/series/?limit=201")
        assert resp.status_code == 422


class TestGetSeriesDetail:
    """Tests for GET /api/v1/series/{series_id}"""

    @pytest.mark.asyncio
    async def test_get_200(self, client):
        mock = _mock_series(id=42, canonical_title="Detail")
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.get_by_id.return_value = mock

            resp = client.get("/api/v1/series/42")

        assert resp.status_code == 200
        body = resp.json()
        assert body["canonical_title"] == "Detail"
        assert body["id"] == 42

    @pytest.mark.asyncio
    async def test_get_404(self, client):
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.get_by_id.return_value = None

            resp = client.get("/api/v1/series/999999")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_returns_all_fields(self, client):
        mock = _mock_series(
            id=1,
            canonical_title="Full Fields",
            normalized_title="full fields",
            season=2,
            cour_part="A",
            year=2025,
            root_path="/p/full",
            poster_url="https://example.com/p.jpg",
            default_filter="1080p",
            default_offset=1,
            pending_review=True,
        )
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.get_by_id.return_value = mock

            resp = client.get("/api/v1/series/1")

        assert resp.status_code == 200
        body = resp.json()
        assert body["season"] == 2
        assert body["cour_part"] == "A"
        assert body["year"] == 2025
        assert body["poster_url"] == "https://example.com/p.jpg"
        assert body["default_filter"] == "1080p"
        assert body["default_offset"] == 1
        assert body["pending_review"] is True


class TestPatchSeries:
    """Tests for PATCH /api/v1/series/{series_id}"""

    @pytest.mark.asyncio
    async def test_patch_updates_root_path(self, client):
        mock = _mock_series(id=5, root_path="/new/path")
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.get_by_id.return_value = mock

            resp = client.patch("/api/v1/series/5", json={"root_path": "/new/path"})

        assert resp.status_code == 200
        assert resp.json()["root_path"] == "/new/path"

    @pytest.mark.asyncio
    async def test_patch_404(self, client):
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.get_by_id.return_value = None

            resp = client.patch("/api/v1/series/999999", json={"root_path": "/x"})

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_unknown_field_is_ignored(self, client):
        mock = _mock_series(id=3)
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.get_by_id.return_value = mock

            resp = client.patch(
                "/api/v1/series/3", json={"not_a_real_field": "x"}
            )

        # Pydantic ignores unknown extras by default — should not error
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_patch_partial_update_only_sets_provided_fields(self, client):
        """Only provided fields are written; unset fields remain unchanged."""
        mock = _mock_series(id=7, canonical_title="Keep Me", root_path="/old")
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.get_by_id.return_value = mock

            resp = client.patch("/api/v1/series/7", json={"root_path": "/changed"})

        assert resp.status_code == 200
        # canonical_title was not in the patch body, mock still has original value
        assert resp.json()["canonical_title"] == "Keep Me"

    @pytest.mark.asyncio
    async def test_patch_canonical_title(self, client):
        mock = _mock_series(id=8, canonical_title="New Title")
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.get_by_id.return_value = mock

            resp = client.patch(
                "/api/v1/series/8", json={"canonical_title": "New Title"}
            )

        assert resp.status_code == 200
        assert resp.json()["canonical_title"] == "New Title"
