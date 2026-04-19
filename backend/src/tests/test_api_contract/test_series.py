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
    async def test_patch_root_path_is_ignored(self, client):
        """root_path was removed from SeriesPatch — it is derived from
        canonical_title server-side. A direct edit must be silently
        dropped (Pydantic ignores unknown extras)."""
        mock = _mock_series(id=5, root_path="/old")
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.get_by_id.return_value = mock

            resp = client.patch("/api/v1/series/5", json={"root_path": "/hijack"})

        assert resp.status_code == 200
        assert mock.root_path == "/old"

    @pytest.mark.asyncio
    async def test_patch_404(self, client):
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.get_by_id.return_value = None

            resp = client.patch(
                "/api/v1/series/999999", json={"canonical_title": "x"}
            )

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
        mock = _mock_series(
            id=7, canonical_title="Keep Me", default_filter="orig"
        )
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.get_by_id.return_value = mock

            resp = client.patch(
                "/api/v1/series/7", json={"default_offset": 3}
            )

        assert resp.status_code == 200
        # canonical_title and default_filter were not in the patch body,
        # mock still has original values
        assert resp.json()["canonical_title"] == "Keep Me"
        assert resp.json()["default_filter"] == "orig"

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

    @pytest.mark.asyncio
    async def test_patch_canonical_title_recomputes_normalized_title(self, client):
        """Editing canonical_title must refresh normalized_title so the
        fallback identity key (used by non-Mikan resolution) stays in sync."""
        mock = _mock_series(
            id=9,
            canonical_title="旧 Old Title",
            normalized_title="stale value",
        )
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.get_by_id.return_value = mock

            resp = client.patch(
                "/api/v1/series/9",
                json={"canonical_title": "新作標題 New Title"},
            )

        assert resp.status_code == 200
        # normalize_title is deterministic; assert the mock attr was
        # overwritten to something different from the stale seed.
        assert mock.normalized_title != "stale value"
        assert mock.normalized_title  # non-empty

    @pytest.mark.asyncio
    async def test_patch_filter_does_not_touch_normalized_title(self, client):
        """Edits to fields other than canonical_title must NOT trigger
        normalized_title recompute."""
        mock = _mock_series(
            id=10,
            canonical_title="Unchanged",
            normalized_title="unchanged-normalized",
        )
        with patch("module.api.v1.series.SeriesRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.get_by_id.return_value = mock

            resp = client.patch(
                "/api/v1/series/10", json={"default_filter": "1080p"}
            )

        assert resp.status_code == 200
        assert mock.normalized_title == "unchanged-normalized"

    @pytest.mark.asyncio
    async def test_patch_canonical_title_recomputes_root_path(self, client):
        """Editing canonical_title must derive a new root_path so the
        download folder follows the title. Users cannot edit root_path
        independently — it is always derived."""
        mock = _mock_series(
            id=11,
            canonical_title="Old Title",
            root_path="/downloads/Old Title",
        )
        with patch("module.api.v1.series.SeriesRepository") as mock_cls, \
             patch(
                "module.services.identity_resolver._derive_root_path",
                return_value="/downloads/Brand New",
            ) as mock_derive:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.get_by_id.return_value = mock

            resp = client.patch(
                "/api/v1/series/11",
                json={"canonical_title": "Brand New"},
            )

        assert resp.status_code == 200
        mock_derive.assert_called_once_with("Brand New")
        assert mock.root_path == "/downloads/Brand New"
