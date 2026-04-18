"""/api/v1/pending-resolution/* contract tests."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from module.api.v1.pending_resolution import router as pending_router


# ---------------------------------------------------------------------------
# App fixture — mirrors the pattern used by test_series.py / test_merge.py
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """FastAPI app with pending-resolution router, auth bypass, and mocked DB."""
    from module.api.middleware.auth import get_current_user
    from module.database.engine import get_db_session

    application = FastAPI()
    application.include_router(pending_router, prefix="/api/v1")

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


def _mock_pending(info_hash: str = "h1", **overrides: Any) -> MagicMock:
    defaults = dict(
        info_hash=info_hash,
        raw_name="Test Torrent",
        homepage="https://mikan.example.com/h1",
        url="magnet:?xt=urn:btih:h1",
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
# GET /api/v1/pending-resolution/
# ---------------------------------------------------------------------------


class TestListPending:
    @pytest.mark.asyncio
    async def test_empty_list(self, client: TestClient) -> None:
        with patch("module.api.v1.pending_resolution.PendingEnrichmentService") as mock_cls:
            svc = AsyncMock()
            mock_cls.return_value = svc
            svc.list_pending.return_value = []

            resp = client.get("/api/v1/pending-resolution/")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    @pytest.mark.asyncio
    async def test_returns_items(self, client: TestClient) -> None:
        items = [_mock_pending("hA"), _mock_pending("hB")]
        with patch("module.api.v1.pending_resolution.PendingEnrichmentService") as mock_cls:
            svc = AsyncMock()
            mock_cls.return_value = svc
            svc.list_pending.return_value = items

            resp = client.get("/api/v1/pending-resolution/")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        hashes = {i["info_hash"] for i in body["items"]}
        assert hashes == {"hA", "hB"}

    @pytest.mark.asyncio
    async def test_limit_applied(self, client: TestClient) -> None:
        items = [_mock_pending(f"h{i}") for i in range(5)]
        with patch("module.api.v1.pending_resolution.PendingEnrichmentService") as mock_cls:
            svc = AsyncMock()
            mock_cls.return_value = svc
            svc.list_pending.return_value = items

            resp = client.get("/api/v1/pending-resolution/?limit=2")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["total"] == 5

    @pytest.mark.asyncio
    async def test_offset_applied(self, client: TestClient) -> None:
        items = [_mock_pending(f"h{i}") for i in range(4)]
        with patch("module.api.v1.pending_resolution.PendingEnrichmentService") as mock_cls:
            svc = AsyncMock()
            mock_cls.return_value = svc
            svc.list_pending.return_value = items

            resp = client.get("/api/v1/pending-resolution/?offset=2&limit=10")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["items"][0]["info_hash"] == "h2"

    @pytest.mark.asyncio
    async def test_item_fields(self, client: TestClient) -> None:
        item = _mock_pending(
            "hZ",
            attempt_count=3,
            last_error="timeout",
            last_attempt_at=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
        with patch("module.api.v1.pending_resolution.PendingEnrichmentService") as mock_cls:
            svc = AsyncMock()
            mock_cls.return_value = svc
            svc.list_pending.return_value = [item]

            resp = client.get("/api/v1/pending-resolution/")

        result = resp.json()["items"][0]
        assert result["info_hash"] == "hZ"
        assert result["attempt_count"] == 3
        assert result["last_error"] == "timeout"
        assert result["last_attempt_at"] is not None


# ---------------------------------------------------------------------------
# POST /api/v1/pending-resolution/{info_hash}/retry
# ---------------------------------------------------------------------------


class TestRetryPending:
    @pytest.mark.asyncio
    async def test_unknown_hash_returns_404(self, client: TestClient) -> None:
        with patch("module.api.v1.pending_resolution.PendingEnrichmentService"):
            with patch(
                "module.api.v1.pending_resolution.select",
                wraps=__import__("sqlalchemy", fromlist=["select"]).select,
            ):
                # Easiest: patch the session's execute to return None
                pass

        # Override session so scalar_one_or_none → None
        from module.api.middleware.auth import get_current_user
        from module.database.engine import get_db_session

        application = FastAPI()
        application.include_router(pending_router, prefix="/api/v1")

        async def _no_auth():
            return "user"

        application.dependency_overrides[get_current_user] = _no_auth

        async def _session_returning_none():
            session = AsyncMock()
            # execute().scalar_one_or_none() → None
            execute_result = MagicMock()
            execute_result.scalar_one_or_none.return_value = None
            session.execute = AsyncMock(return_value=execute_result)
            yield session

        application.dependency_overrides[get_db_session] = _session_returning_none
        c = TestClient(application)
        resp = c.post("/api/v1/pending-resolution/nonexistent/retry")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_resolver_returns_none_not_resolved(self, client: TestClient) -> None:
        """When resolver returns None the endpoint reports resolved=False."""
        from module.api.middleware.auth import get_current_user
        from module.database.engine import get_db_session

        application = FastAPI()
        application.include_router(pending_router, prefix="/api/v1")

        async def _no_auth():
            return "user"

        application.dependency_overrides[get_current_user] = _no_auth

        async def _session():
            session = AsyncMock()
            execute_result = MagicMock()
            execute_result.scalar_one_or_none.return_value = _mock_pending("hX")
            session.execute = AsyncMock(return_value=execute_result)
            yield session

        application.dependency_overrides[get_db_session] = _session
        c = TestClient(application)

        with patch("module.api.v1.pending_resolution._build_resolver_for_retry") as mock_bld:
            mock_bld.return_value = _FakeResolverCtx(resolve_result=None)
            resp = c.post("/api/v1/pending-resolution/hX/retry")

        assert resp.status_code == 200
        body = resp.json()
        assert body["resolved"] is False
        assert body["info_hash"] == "hX"

    @pytest.mark.asyncio
    async def test_resolver_returns_ref_resolved(self, client: TestClient) -> None:
        """When resolver returns a MikanRef the endpoint reports resolved=True."""
        from module.api.middleware.auth import get_current_user
        from module.database.engine import get_db_session
        from module.mikan.parser import MikanRef

        application = FastAPI()
        application.include_router(pending_router, prefix="/api/v1")

        async def _no_auth():
            return "user"

        application.dependency_overrides[get_current_user] = _no_auth

        async def _session():
            session = AsyncMock()
            execute_result = MagicMock()
            execute_result.scalar_one_or_none.return_value = _mock_pending("hR")
            session.execute = AsyncMock(return_value=execute_result)
            yield session

        application.dependency_overrides[get_db_session] = _session
        c = TestClient(application)

        ref = MikanRef(
            mikan_bangumi_id=99,
            mikan_subgroup_id=7,
            canonical_title="Show Title",
            poster_url=None,
        )
        with patch("module.api.v1.pending_resolution._build_resolver_for_retry") as mock_bld:
            mock_bld.return_value = _FakeResolverCtx(resolve_result=ref)
            resp = c.post("/api/v1/pending-resolution/hR/retry")

        assert resp.status_code == 200
        body = resp.json()
        assert body["resolved"] is True
        assert body["mikan_bangumi_id"] == 99
        assert body["mikan_subgroup_id"] == 7

    @pytest.mark.asyncio
    async def test_resolver_exception_returns_error(self, client: TestClient) -> None:
        """When the resolver raises, the endpoint returns resolved=False with error."""
        from module.api.middleware.auth import get_current_user
        from module.database.engine import get_db_session

        application = FastAPI()
        application.include_router(pending_router, prefix="/api/v1")

        async def _no_auth():
            return "user"

        application.dependency_overrides[get_current_user] = _no_auth

        async def _session():
            session = AsyncMock()
            execute_result = MagicMock()
            execute_result.scalar_one_or_none.return_value = _mock_pending("hE")
            session.execute = AsyncMock(return_value=execute_result)
            yield session

        application.dependency_overrides[get_db_session] = _session
        c = TestClient(application)

        with patch("module.api.v1.pending_resolution._build_resolver_for_retry") as mock_bld:
            mock_bld.return_value = _FakeResolverCtx(raise_exc=RuntimeError("fetch failed"))
            resp = c.post("/api/v1/pending-resolution/hE/retry")

        assert resp.status_code == 200
        body = resp.json()
        assert body["resolved"] is False
        assert "RuntimeError" in body["error"]


# ---------------------------------------------------------------------------
# Fake resolver context manager for monkeypatching
# ---------------------------------------------------------------------------


class _FakeResolverCtx:
    """Fake async context manager that yields an object with .resolve()."""

    def __init__(
        self,
        resolve_result: Any = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._result = resolve_result
        self._raise = raise_exc

    async def __aenter__(self) -> "_FakeResolverCtx":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def resolve(self, info_hash: str) -> Any:
        if self._raise is not None:
            raise self._raise
        return self._result
