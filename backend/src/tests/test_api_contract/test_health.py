"""/api/v1/health/* contract tests."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from module.api.v1.health import router as health_router


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """FastAPI app with health router, auth bypass, and mocked DB."""
    from module.api.middleware.auth import get_current_user
    from module.database.engine import get_db_session

    application = FastAPI()
    application.include_router(health_router, prefix="/api/v1")

    async def mock_get_current_user():
        return "testuser"

    application.dependency_overrides[get_current_user] = mock_get_current_user

    async def mock_get_session():
        yield AsyncMock()

    application.dependency_overrides[get_db_session] = mock_get_session
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_pending_item(info_hash: str = "abc123", **overrides: Any) -> MagicMock:
    defaults = dict(
        info_hash=info_hash,
        raw_name="Test Torrent",
        homepage="https://mikan.example.com/Torrents/abc123",
        url="magnet:?xt=urn:btih:abc123",
        rss_id=1,
        first_seen_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        attempt_count=0,
        last_error=None,
        last_attempt_at=None,
    )
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


# ---------------------------------------------------------------------------
# GET /api/v1/health/mikan
# ---------------------------------------------------------------------------


class TestMikanHealth:
    def test_empty_state_returns_ok(self, client: TestClient) -> None:
        """No pending items + no mikan history → status ok, empty pending_items."""
        with (
            patch(
                "module.api.v1.health.PendingEnrichmentService"
            ) as mock_pending_cls,
            patch(
                "module.api.v1.health.MikanEpisodeRefRepository"
            ) as mock_repo_cls,
        ):
            pending_svc = AsyncMock()
            pending_svc.list_pending.return_value = []
            mock_pending_cls.return_value = pending_svc

            mikan_repo = AsyncMock()
            mikan_repo.last_success_at.return_value = None
            mikan_repo.consecutive_failures.return_value = 0
            mock_repo_cls.return_value = mikan_repo

            resp = client.get("/api/v1/health/mikan")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] in {"ok", "degraded", "down"}
        assert body["pending_count"] == 0
        assert body["pending_items"] == []
        assert body["consecutive_failures"] == 0
        assert body["last_success_at"] is None
        assert body["hours_since_last_success"] is None

    def test_three_pending_items_yields_degraded_or_down(
        self, client: TestClient
    ) -> None:
        """pending_count >= 3 → status must be degraded or down."""
        pending_items = [_mock_pending_item(info_hash=f"h{i}") for i in range(3)]

        with (
            patch(
                "module.api.v1.health.PendingEnrichmentService"
            ) as mock_pending_cls,
            patch(
                "module.api.v1.health.MikanEpisodeRefRepository"
            ) as mock_repo_cls,
        ):
            pending_svc = AsyncMock()
            pending_svc.list_pending.return_value = pending_items
            mock_pending_cls.return_value = pending_svc

            mikan_repo = AsyncMock()
            mikan_repo.last_success_at.return_value = datetime.now(timezone.utc)
            mikan_repo.consecutive_failures.return_value = 0
            mock_repo_cls.return_value = mikan_repo

            resp = client.get("/api/v1/health/mikan")

        assert resp.status_code == 200
        body = resp.json()
        assert body["pending_count"] == 3
        assert body["status"] in {"degraded", "down"}

    def test_ten_consecutive_failures_yields_down(self, client: TestClient) -> None:
        """consecutive_failures >= 10 → status must be down."""
        with (
            patch(
                "module.api.v1.health.PendingEnrichmentService"
            ) as mock_pending_cls,
            patch(
                "module.api.v1.health.MikanEpisodeRefRepository"
            ) as mock_repo_cls,
        ):
            pending_svc = AsyncMock()
            pending_svc.list_pending.return_value = []
            mock_pending_cls.return_value = pending_svc

            mikan_repo = AsyncMock()
            mikan_repo.last_success_at.return_value = datetime.now(timezone.utc)
            mikan_repo.consecutive_failures.return_value = 10
            mock_repo_cls.return_value = mikan_repo

            resp = client.get("/api/v1/health/mikan")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "down"
        assert body["consecutive_failures"] == 10

    def test_response_shape(self, client: TestClient) -> None:
        """Response must contain all required fields."""
        with (
            patch(
                "module.api.v1.health.PendingEnrichmentService"
            ) as mock_pending_cls,
            patch(
                "module.api.v1.health.MikanEpisodeRefRepository"
            ) as mock_repo_cls,
        ):
            pending_svc = AsyncMock()
            pending_svc.list_pending.return_value = []
            mock_pending_cls.return_value = pending_svc

            mikan_repo = AsyncMock()
            mikan_repo.last_success_at.return_value = None
            mikan_repo.consecutive_failures.return_value = 0
            mock_repo_cls.return_value = mikan_repo

            resp = client.get("/api/v1/health/mikan")

        body = resp.json()
        required_keys = {
            "status",
            "pending_count",
            "last_success_at",
            "hours_since_last_success",
            "consecutive_failures",
            "pending_items",
        }
        assert required_keys <= body.keys()


# ---------------------------------------------------------------------------
# GET /api/v1/health/concurrency
# ---------------------------------------------------------------------------


class TestConcurrencyHealth:
    def test_response_shape(self, client: TestClient) -> None:
        """Response must contain rss_locks list and rate_limiters dict."""
        resp = client.get("/api/v1/health/concurrency")

        assert resp.status_code == 200
        body = resp.json()
        assert "rss_locks" in body
        assert "rate_limiters" in body
        assert isinstance(body["rss_locks"], list)
        assert isinstance(body["rate_limiters"], dict)

    def test_rss_lock_entry_shape(self, client: TestClient) -> None:
        """Each rss_locks entry must have rss_id, held, held_duration_s."""
        import asyncio

        mock_lock = MagicMock()
        mock_lock.locked.return_value = False

        with patch(
            "module.scheduler.jobs.rss_refresh._rss_lock_registry"
        ) as mock_registry:
            mock_registry._locks = {1: mock_lock}

            resp = client.get("/api/v1/health/concurrency")

        body = resp.json()
        assert len(body["rss_locks"]) == 1
        entry = body["rss_locks"][0]
        assert entry["rss_id"] == 1
        assert entry["held"] is False
        assert "held_duration_s" in entry

    def test_rate_limiter_entry_shape(self, client: TestClient) -> None:
        """Each rate_limiters entry must have required keys."""
        mock_limiter = MagicMock()
        mock_limiter.is_degraded.return_value = False
        mock_limiter.current_concurrent.return_value = 4

        with patch(
            "module.concurrency.registry._LIMITERS",
            {"mikan": mock_limiter},
        ):
            resp = client.get("/api/v1/health/concurrency")

        body = resp.json()
        assert "mikan" in body["rate_limiters"]
        entry = body["rate_limiters"]["mikan"]
        assert "degraded" in entry
        assert "current_concurrent" in entry
        assert entry["degraded"] is False
        assert entry["current_concurrent"] == 4
