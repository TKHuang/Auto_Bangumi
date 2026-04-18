"""/api/v1/bangumi/merge + /api/v1/merge-history/* contract tests."""
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from module.api.v1.merge import router as merge_router


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """FastAPI app with merge router, auth bypass, and DB session override."""
    from module.api.middleware.auth import get_current_user
    from module.database.engine import get_db_session

    application = FastAPI()
    application.include_router(merge_router, prefix="/api/v1")

    async def mock_get_current_user():
        return "testuser"

    application.dependency_overrides[get_current_user] = mock_get_current_user

    async def mock_get_session():
        yield AsyncMock()

    application.dependency_overrides[get_db_session] = mock_get_session
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


def _mock_history(**overrides: Any) -> MagicMock:
    defaults = dict(
        id=1,
        winner_bangumi_id=10,
        loser_bangumi_id=20,
        merge_reason="test",
        merged_at=datetime(2024, 1, 1, 12, 0, 0),
        merged_by="api",
        undone_at=None,
        undone_by=None,
    )
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


# ---------------------------------------------------------------------------
# POST /api/v1/bangumi/merge
# ---------------------------------------------------------------------------


class TestMergeBangumi:
    """Tests for POST /api/v1/bangumi/merge."""

    @pytest.mark.asyncio
    async def test_merge_success_returns_history_id(self, client):
        mock_history = _mock_history(id=42, winner_bangumi_id=10, loser_bangumi_id=20)
        with patch("module.api.v1.merge.BangumiMergeService") as mock_cls:
            svc = AsyncMock()
            mock_cls.return_value = svc
            svc.merge.return_value = mock_history

            resp = client.post(
                "/api/v1/bangumi/merge",
                json={"winner_id": 10, "loser_id": 20, "reason": "duplicate"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["history_id"] == 42
        assert body["winner_id"] == 10
        assert body["loser_id"] == 20

    @pytest.mark.asyncio
    async def test_merge_calls_service_with_correct_args(self, client):
        mock_history = _mock_history(id=1, winner_bangumi_id=5, loser_bangumi_id=7)
        with patch("module.api.v1.merge.BangumiMergeService") as mock_cls:
            svc = AsyncMock()
            mock_cls.return_value = svc
            svc.merge.return_value = mock_history

            client.post(
                "/api/v1/bangumi/merge",
                json={"winner_id": 5, "loser_id": 7, "reason": "auto"},
            )

        svc.merge.assert_awaited_once_with(
            winner_id=5,
            loser_id=7,
            merge_reason="auto",
            merged_by="api",
        )

    @pytest.mark.asyncio
    async def test_merge_default_reason(self, client):
        mock_history = _mock_history(id=1)
        with patch("module.api.v1.merge.BangumiMergeService") as mock_cls:
            svc = AsyncMock()
            mock_cls.return_value = svc
            svc.merge.return_value = mock_history

            resp = client.post(
                "/api/v1/bangumi/merge",
                json={"winner_id": 1, "loser_id": 2},
            )

        assert resp.status_code == 200
        svc.merge.assert_awaited_once()
        call_kwargs = svc.merge.call_args.kwargs
        assert call_kwargs["merge_reason"] == "manual"

    @pytest.mark.asyncio
    async def test_merge_returns_400_on_value_error(self, client):
        with patch("module.api.v1.merge.BangumiMergeService") as mock_cls:
            svc = AsyncMock()
            mock_cls.return_value = svc
            svc.merge.side_effect = ValueError("pair is blacklisted")

            resp = client.post(
                "/api/v1/bangumi/merge",
                json={"winner_id": 1, "loser_id": 2, "reason": "test"},
            )

        assert resp.status_code == 400
        assert "blacklisted" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_merge_self_returns_400(self, client):
        with patch("module.api.v1.merge.BangumiMergeService") as mock_cls:
            svc = AsyncMock()
            mock_cls.return_value = svc
            svc.merge.side_effect = ValueError("winner_id and loser_id must differ")

            resp = client.post(
                "/api/v1/bangumi/merge",
                json={"winner_id": 5, "loser_id": 5, "reason": "x"},
            )

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_merge_missing_winner_id_returns_422(self, client):
        resp = client.post(
            "/api/v1/bangumi/merge",
            json={"loser_id": 2, "reason": "x"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_merge_missing_loser_id_returns_422(self, client):
        resp = client.post(
            "/api/v1/bangumi/merge",
            json={"winner_id": 1, "reason": "x"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/merge-history/
# ---------------------------------------------------------------------------


class TestListMergeHistory:
    """Tests for GET /api/v1/merge-history/."""

    @pytest.mark.asyncio
    async def test_list_returns_items_and_total(self, client):
        rows = [
            _mock_history(id=1, winner_bangumi_id=10, loser_bangumi_id=20),
            _mock_history(id=2, winner_bangumi_id=30, loser_bangumi_id=40),
        ]
        with patch("module.api.v1.merge.BangumiMergeHistoryRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.list_paginated.return_value = (rows, 2)

            resp = client.get("/api/v1/merge-history/")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_passes_limit_offset(self, client):
        with patch("module.api.v1.merge.BangumiMergeHistoryRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.list_paginated.return_value = ([], 0)

            client.get("/api/v1/merge-history/?limit=10&offset=20")

        repo.list_paginated.assert_awaited_once_with(limit=10, offset=20)

    @pytest.mark.asyncio
    async def test_list_empty(self, client):
        with patch("module.api.v1.merge.BangumiMergeHistoryRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.list_paginated.return_value = ([], 0)

            resp = client.get("/api/v1/merge-history/")

        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    @pytest.mark.asyncio
    async def test_list_item_fields(self, client):
        row = _mock_history(
            id=99,
            winner_bangumi_id=11,
            loser_bangumi_id=22,
            merge_reason="duplicate",
            merged_at=datetime(2024, 6, 15, 10, 30, 0),
            merged_by="api",
            undone_at=None,
            undone_by=None,
        )
        with patch("module.api.v1.merge.BangumiMergeHistoryRepository") as mock_cls:
            repo = AsyncMock()
            mock_cls.return_value = repo
            repo.list_paginated.return_value = ([row], 1)

            resp = client.get("/api/v1/merge-history/")

        item = resp.json()["items"][0]
        assert item["id"] == 99
        assert item["winner_bangumi_id"] == 11
        assert item["loser_bangumi_id"] == 22
        assert item["merge_reason"] == "duplicate"
        assert item["merged_by"] == "api"
        assert item["undone_at"] is None

    @pytest.mark.asyncio
    async def test_list_rejects_invalid_limit(self, client):
        resp = client.get("/api/v1/merge-history/?limit=0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_list_rejects_limit_over_max(self, client):
        resp = client.get("/api/v1/merge-history/?limit=201")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/merge-history/{id}/undo
# ---------------------------------------------------------------------------


class TestUndoMerge:
    """Tests for POST /api/v1/merge-history/{id}/undo."""

    @pytest.mark.asyncio
    async def test_undo_success(self, client):
        mock_history = _mock_history(id=5)
        with patch("module.api.v1.merge.BangumiMergeService") as mock_cls:
            svc = AsyncMock()
            mock_cls.return_value = svc
            svc.undo.return_value = mock_history

            resp = client.post("/api/v1/merge-history/5/undo")

        assert resp.status_code == 200
        body = resp.json()
        assert body["undone"] is True
        assert body["history_id"] == 5

    @pytest.mark.asyncio
    async def test_undo_calls_service_with_history_id(self, client):
        mock_history = _mock_history(id=7)
        with patch("module.api.v1.merge.BangumiMergeService") as mock_cls:
            svc = AsyncMock()
            mock_cls.return_value = svc
            svc.undo.return_value = mock_history

            client.post("/api/v1/merge-history/7/undo")

        svc.undo.assert_awaited_once_with(history_id=7, undone_by="api")

    @pytest.mark.asyncio
    async def test_undo_not_found_returns_404(self, client):
        with patch("module.api.v1.merge.BangumiMergeService") as mock_cls:
            svc = AsyncMock()
            mock_cls.return_value = svc
            svc.undo.side_effect = ValueError("merge history id=999 not found")

            resp = client.post("/api/v1/merge-history/999/undo")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_undo_already_undone_returns_400(self, client):
        with patch("module.api.v1.merge.BangumiMergeService") as mock_cls:
            svc = AsyncMock()
            mock_cls.return_value = svc
            svc.undo.side_effect = ValueError("merge already undone")

            resp = client.post("/api/v1/merge-history/3/undo")

        assert resp.status_code == 400
        assert "already undone" in resp.json()["detail"]
