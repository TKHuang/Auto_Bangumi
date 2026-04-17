# Plan 03 — Mikan HTTP Layer + Concurrency Primitives + Identity Resolver

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the infrastructure that resolves a torrent's identity through Mikan: HTTP client with rate limiting + Mikan page parser + resolver that persists to the `mikan_episode_ref` cache, plus the per-RSS lock and the three-tier `IdentityResolver` service using `SeriesRepository`.

**Architecture:** Purely additive, no schema changes, no RSS job mutation. This plan builds standalone modules (`module.mikan`, `module.concurrency`, `module.services.identity_resolver`) that Plan 05 will wire into `rss_engine.py` after Plan 04 migrates the `bangumi` table. Every unit is covered by unit tests; one integration test verifies the three-tier resolver against `SeriesRepository` with an HTTPX mock.

**Tech Stack:** `httpx>=0.28` (already in deps), `pytest-httpx` for HTTP mocking, `pytest-asyncio` for async tests, `anyio` for timing helpers in rate-limiter tests.

**Spec reference:** [docs/superpowers/specs/2026-04-17-bangumi-identity-refactor-design.md](../specs/2026-04-17-bangumi-identity-refactor-design.md) §6.4, §8, §9.

**Out of scope for this plan (explicit):**
- RSS refresh job wiring into `MikanResolver` → Plan 05
- `bangumi` table schema changes → Plan 04
- Merge transaction / `migrate_duplicates.py` → Plan 04
- Rename pipeline changes → Plan 04
- API / WebUI / Dashboard → Plan 05
- `torrent` table `mikan_bangumi_id` / `mikan_subgroup_id` columns → Plan 04

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/pyproject.toml` | Modify | Add `pytest-httpx>=0.30`, `anyio>=4.0` to dev extras |
| `backend/src/module/mikan/__init__.py` | Create | Package marker |
| `backend/src/module/mikan/parser.py` | Create | `MikanRef` dataclass + `parse_mikan_page()` |
| `backend/src/module/mikan/client.py` | Create | `MikanClient` — HTTPX wrapper, timeout + base_url from config |
| `backend/src/module/mikan/resolver.py` | Create | `MikanResolver` — orchestrator: cache → client → parser → persist |
| `backend/src/module/concurrency/__init__.py` | Create | Package marker |
| `backend/src/module/concurrency/rate_limiter.py` | Create | `RateLimiter` class with dynamic degradation |
| `backend/src/module/concurrency/rss_lock.py` | Create | `RssLockRegistry` skip-if-held |
| `backend/src/module/concurrency/registry.py` | Create | Module-level `RateLimiter` singletons |
| `backend/src/module/conf/models.py` | Modify | Add `Mikan` section to `Config` |
| `backend/src/module/conf/config.py` | Read only | No changes; Mikan reads from `settings.mikan` |
| `backend/src/module/services/identity_resolver.py` | Create | Three-tier `IdentityResolver` service |
| `backend/src/tests/fixtures/mikan/episode_page_subscribe_button.html` | Create | Tier A fixture (data-bangumiid attr) |
| `backend/src/tests/fixtures/mikan/episode_page_anchor_only.html` | Create | Tier B fixture (/Home/Bangumi anchor) |
| `backend/src/tests/fixtures/mikan/episode_page_rss_link_only.html` | Create | Tier C fixture (RSS URL) |
| `backend/src/tests/fixtures/mikan/episode_page_no_ref.html` | Create | Fails all three tiers |
| `backend/src/tests/fixtures/mikan/episode_page_503.html` | Create | 503 error body |
| `backend/src/tests/test_mikan/__init__.py` | Create | Package marker |
| `backend/src/tests/test_mikan/test_parser.py` | Create | Parser unit tests |
| `backend/src/tests/test_mikan/test_client.py` | Create | Client unit tests (mocked HTTPX) |
| `backend/src/tests/test_mikan/test_resolver.py` | Create | Resolver unit tests |
| `backend/src/tests/test_concurrency/__init__.py` | Create | Package marker |
| `backend/src/tests/test_concurrency/test_rate_limiter.py` | Create | Rate limiter unit tests |
| `backend/src/tests/test_concurrency/test_rss_lock.py` | Create | RSS lock unit tests |
| `backend/src/tests/test_concurrency/test_registry.py` | Create | Registry singleton tests |
| `backend/src/tests/test_services/test_identity_resolver.py` | Create | Three-tier resolver integration tests |

---

## Prerequisites

- Branch: `refactor/backendv2`
- Plan 02 landed (head revision `0005_add_merge_history`, all 4 new repositories available)
- Working tree clean: `git status` shows nothing modified
- Unit + migration tests green: `cd backend && uv run python -m pytest src/tests/test_repositories/ src/tests/test_domain/ src/tests/test_services/ src/tests/test_migrations/ -q` reports `1111+ passed`
- E2E tests green: `cd backend && uv run python -m pytest src/tests/test_e2e/ -q` reports `144 passed, 1 xfailed`

---

### Task 1: Add pytest-httpx + anyio dev dependencies

**Files:**

- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Edit pyproject.toml**

In `backend/pyproject.toml`, inside the `[project.optional-dependencies]` → `dev` array, add `pytest-httpx>=0.30,` and `anyio>=4.0,`. Read the file first to find the existing `dev = [...]` block. Insert in alphabetical order.

- [ ] **Step 2: Install**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && uv sync --extra dev
```

Expected: `pytest-httpx` and `anyio` appear in resolved packages, no errors.

- [ ] **Step 3: Verify import**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -c "import pytest_httpx; import anyio; print('OK', pytest_httpx.__version__, anyio.__version__)"
```

Expected: `OK <v1> <v2>` (no ImportError).

- [ ] **Step 4: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/pyproject.toml backend/uv.lock && \
  git commit -m "feat: add pytest-httpx + anyio dev dependencies"
```

---

### Task 2: Mikan parser — `MikanRef` + `parse_mikan_page()`

**Files:**

- Create: `backend/src/module/mikan/__init__.py` (empty)
- Create: `backend/src/module/mikan/parser.py`
- Create: `backend/src/tests/fixtures/mikan/episode_page_subscribe_button.html`
- Create: `backend/src/tests/fixtures/mikan/episode_page_anchor_only.html`
- Create: `backend/src/tests/fixtures/mikan/episode_page_rss_link_only.html`
- Create: `backend/src/tests/fixtures/mikan/episode_page_no_ref.html`
- Create: `backend/src/tests/test_mikan/__init__.py` (empty)
- Create: `backend/src/tests/test_mikan/test_parser.py`

- [ ] **Step 1: Create the four HTML fixtures**

Create `backend/src/tests/fixtures/mikan/episode_page_subscribe_button.html` — realistic Mikan episode page with the subscribe button data attributes (Tier A):

```html
<!DOCTYPE html>
<html lang="zh-cn">
<head><title>Mikan Project - Episode</title></head>
<body>
<div class="container">
  <div class="bangumi-title"><a href="/Home/Bangumi/3906">身为悲剧始作俑者的最强邪恶BOSS女王为民竭心尽力。 第二季</a></div>
  <div class="bangumi-poster" style="background-image: url('/images/Bangumi/202410/730372c2.jpg');"></div>
  <div class="episode-info">
    <a class="btn btn-default js-subscribe-bangumi" data-bangumiid="3906" data-subtitlegroupid="370" href="#">訂閱</a>
  </div>
  <div class="leftbar-item">
    <a href="/Home/Bangumi/3906#370">查看此字幕組的全部更新</a>
  </div>
  <a class="mikan-rss" href="/RSS/Bangumi?bangumiId=3906&subgroupid=370">RSS</a>
</div>
</body>
</html>
```

Create `backend/src/tests/fixtures/mikan/episode_page_anchor_only.html` — Mikan page without subscribe button but with the `/Home/Bangumi/{id}#{sub}` anchor (Tier B):

```html
<!DOCTYPE html>
<html lang="zh-cn">
<head><title>Mikan Project - Episode</title></head>
<body>
<div class="container">
  <div class="bangumi-title"><a href="/Home/Bangumi/1234">葬送的芙莉蓮</a></div>
  <div class="bangumi-poster" style="background-image: url('/images/Bangumi/202309/frieren.jpg');"></div>
  <a href="/Home/Bangumi/1234#77">字幕組：LoliHouse</a>
</div>
</body>
</html>
```

Create `backend/src/tests/fixtures/mikan/episode_page_rss_link_only.html` — Mikan page where only the RSS link carries the IDs (Tier C):

```html
<!DOCTYPE html>
<html lang="zh-cn">
<head><title>Mikan Project - Episode</title></head>
<body>
<div class="container">
  <div class="bangumi-title"><a href="/Home/Bangumi/5555">進撃の巨人 The Final Season</a></div>
  <p>這一集的 RSS 訂閱：
    <a href="/RSS/Bangumi?bangumiId=5555&subgroupid=99">點此訂閱</a>
  </p>
</div>
</body>
</html>
```

Create `backend/src/tests/fixtures/mikan/episode_page_no_ref.html` — page without any of the three markers (e.g., error page or unrelated HTML):

```html
<!DOCTYPE html>
<html lang="zh-cn">
<head><title>Mikan Project</title></head>
<body>
<div class="container">
  <h1>404 - Not Found</h1>
  <p>頁面不存在</p>
</div>
</body>
</html>
```

- [ ] **Step 2: Write failing parser tests**

Create `backend/src/tests/test_mikan/__init__.py` as empty.

Create `backend/src/tests/test_mikan/test_parser.py`:

```python
"""Parser tests for Mikan episode pages (spec §8.1)."""
from pathlib import Path

import pytest

from module.mikan.parser import MikanRef, parse_mikan_page

_FIX = Path(__file__).parent.parent / "fixtures" / "mikan"


def _load(name: str) -> str:
    return (_FIX / name).read_text(encoding="utf-8")


@pytest.mark.unit
class TestParseMikanPage:
    def test_tier_a_subscribe_button(self):
        html = _load("episode_page_subscribe_button.html")
        ref = parse_mikan_page(html)
        assert ref == MikanRef(
            mikan_bangumi_id=3906,
            mikan_subgroup_id=370,
            canonical_title="身为悲剧始作俑者的最强邪恶BOSS女王为民竭心尽力。 第二季",
            poster_url="/images/Bangumi/202410/730372c2.jpg",
        )

    def test_tier_b_anchor_only(self):
        html = _load("episode_page_anchor_only.html")
        ref = parse_mikan_page(html)
        assert ref is not None
        assert ref.mikan_bangumi_id == 1234
        assert ref.mikan_subgroup_id == 77
        assert ref.canonical_title == "葬送的芙莉蓮"
        assert ref.poster_url == "/images/Bangumi/202309/frieren.jpg"

    def test_tier_c_rss_link_only(self):
        html = _load("episode_page_rss_link_only.html")
        ref = parse_mikan_page(html)
        assert ref is not None
        assert ref.mikan_bangumi_id == 5555
        assert ref.mikan_subgroup_id == 99
        # poster absent — field may be None but must not error
        assert ref.poster_url is None or isinstance(ref.poster_url, str)

    def test_no_ref_returns_none(self):
        html = _load("episode_page_no_ref.html")
        assert parse_mikan_page(html) is None

    def test_empty_input_returns_none(self):
        assert parse_mikan_page("") is None

    def test_prefers_tier_a_over_tier_b_when_both_present(self):
        """If subscribe button exists, do not downgrade to anchor."""
        html = (
            '<html><body>'
            '<a class="js-subscribe-bangumi" data-bangumiid="100" data-subtitlegroupid="1">sub</a>'
            '<a href="/Home/Bangumi/999#2">other</a>'
            '</body></html>'
        )
        ref = parse_mikan_page(html)
        assert ref is not None
        assert ref.mikan_bangumi_id == 100
        assert ref.mikan_subgroup_id == 1
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_mikan/test_parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'module.mikan'` (collection error).

- [ ] **Step 4: Create package marker + parser implementation**

Create `backend/src/module/mikan/__init__.py` as empty.

Create `backend/src/module/mikan/parser.py`:

```python
"""Mikan episode-page parser (spec §8.1).

Extracts (mikan_bangumi_id, mikan_subgroup_id) plus canonical_title and
poster_url from a fetched episode page. Uses three-tier fallback:

  Tier A: subscribe button data attributes (data-bangumiid + data-subtitlegroupid)
  Tier B: /Home/Bangumi/{id}#{sub} anchor
  Tier C: RSS URL ?bangumiId=&subgroupid=

Returns None if no tier matches (treat as non_mikan or parse_failed upstream).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MikanRef:
    mikan_bangumi_id: int
    mikan_subgroup_id: int
    canonical_title: Optional[str] = None
    poster_url: Optional[str] = None


_TIER_A = re.compile(
    r'data-bangumiid="(\d+)"\s+data-subtitlegroupid="(\d+)"',
)
_TIER_B = re.compile(r'/Home/Bangumi/(\d+)#(\d+)')
_TIER_C = re.compile(r'bangumiId=(\d+)&subgroupid=(\d+)')
_TITLE = re.compile(
    r'<div[^>]*class="[^"]*bangumi-title[^"]*"[^>]*>\s*'
    r'<a[^>]*>([^<]+)</a>'
)
_POSTER = re.compile(
    r'class="[^"]*bangumi-poster[^"]*"[^>]*style="[^"]*'
    r'background-image:\s*url\(\s*[\'"]?([^\'")]+)'
)


def _find_ids(html: str) -> Optional[tuple[int, int]]:
    for pattern in (_TIER_A, _TIER_B, _TIER_C):
        m = pattern.search(html)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def parse_mikan_page(html: str) -> Optional[MikanRef]:
    """Parse a Mikan episode page. Returns None if no (bangumi_id, subgroup_id)
    can be extracted via any of the three tiers."""
    if not html:
        return None

    ids = _find_ids(html)
    if ids is None:
        return None
    bid, sid = ids

    title_match = _TITLE.search(html)
    title = title_match.group(1).strip() if title_match else None

    poster_match = _POSTER.search(html)
    poster = poster_match.group(1) if poster_match else None

    return MikanRef(
        mikan_bangumi_id=bid,
        mikan_subgroup_id=sid,
        canonical_title=title,
        poster_url=poster,
    )
```

- [ ] **Step 5: Run tests and confirm pass**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_mikan/test_parser.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/mikan/__init__.py \
          backend/src/module/mikan/parser.py \
          backend/src/tests/test_mikan/__init__.py \
          backend/src/tests/test_mikan/test_parser.py \
          backend/src/tests/fixtures/mikan/ && \
  git commit -m "feat: Mikan episode-page parser with 3-tier fallback"
```

---

### Task 3: Mikan config section

**Files:**

- Modify: `backend/src/module/conf/models.py`

- [ ] **Step 1: Write failing test**

Create `backend/src/tests/test_mikan/test_config.py`:

```python
"""Verify Mikan config section shape."""
import pytest

from module.conf.models import Config, Mikan


@pytest.mark.unit
class TestMikanConfig:
    def test_mikan_defaults(self):
        m = Mikan()
        assert m.base_url == "https://mikanani.me"
        assert m.timeout_seconds == 10
        assert m.max_concurrent == 2
        assert m.min_interval_ms == 500
        assert m.health_ok_window_hours == 1
        assert m.health_down_threshold_hours == 24

    def test_config_includes_mikan_by_default(self):
        c = Config()
        assert isinstance(c.mikan, Mikan)
        assert c.mikan.base_url == "https://mikanani.me"
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_mikan/test_config.py -v
```

Expected: `ImportError: cannot import name 'Mikan' from 'module.conf.models'`.

- [ ] **Step 3: Add `Mikan` class to `models.py`**

Edit `backend/src/module/conf/models.py`. After the `ExperimentalOpenAI` class (just before `class Config`), add:

```python
class Mikan(BaseModel):
    base_url: str = Field(
        "https://mikanani.me",
        description="Mikan site base URL (change here when domain migrates)",
    )
    timeout_seconds: int = Field(
        10,
        description="HTTP timeout per Mikan request",
    )
    max_concurrent: int = Field(
        2,
        description="Max concurrent Mikan requests (base rate for dynamic limiter)",
    )
    min_interval_ms: int = Field(
        500,
        description="Minimum gap between Mikan requests in milliseconds",
    )
    health_ok_window_hours: int = Field(
        1,
        description="Dashboard banner shows 'ok' if last success within this window",
    )
    health_down_threshold_hours: int = Field(
        24,
        description="Dashboard banner shows 'down' if no success within this window",
    )
```

Also edit `class Config` to add the `mikan` field. Find the lines:

```python
class Config(BaseModel):
    program: Program = Field(default_factory=lambda: Program())
```

And insert `mikan: Mikan = Field(default_factory=lambda: Mikan())` before the closing brace of the class body (above `experimental_openai` or right after `notification`). Keep alphabetical-ish order among the existing fields; here is the target structure:

```python
class Config(BaseModel):
    program: Program = Field(default_factory=lambda: Program())
    downloader: Downloader = Field(default_factory=lambda: Downloader())
    rss_parser: RSSParser = Field(default_factory=lambda: RSSParser())
    bangumi_manage: BangumiManage = Field(default_factory=lambda: BangumiManage())
    log: Log = Field(default_factory=lambda: Log())
    proxy: Proxy = Field(default_factory=lambda: Proxy())
    notification: Notification = Field(default_factory=lambda: Notification())
    mikan: Mikan = Field(default_factory=lambda: Mikan())
    experimental_openai: ExperimentalOpenAI = Field(default_factory=lambda: ExperimentalOpenAI())
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_mikan/test_config.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Verify existing tests still pass**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/ -q --ignore=src/tests/test_e2e
```

Expected: no regressions (all previously-green tests remain green).

- [ ] **Step 6: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/conf/models.py \
          backend/src/tests/test_mikan/test_config.py && \
  git commit -m "feat: Mikan config section with base_url + rate limits + health thresholds"
```

---

### Task 4: `MikanClient` — HTTPX async wrapper

**Files:**

- Create: `backend/src/module/mikan/client.py`
- Create: `backend/src/tests/test_mikan/test_client.py`

- [ ] **Step 1: Write failing tests**

Create `backend/src/tests/test_mikan/test_client.py`:

```python
"""MikanClient HTTP wrapper tests."""
import pytest
from pytest_httpx import HTTPXMock

from module.mikan.client import MikanClient, MikanFetchError


@pytest.mark.unit
class TestMikanClientFetchEpisode:
    async def test_fetches_episode_page(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://mikanani.me/Home/Episode/abc123",
            text="<html><body>ok</body></html>",
            status_code=200,
        )
        async with MikanClient(base_url="https://mikanani.me", timeout_seconds=10) as c:
            html, status = await c.fetch_episode_page("abc123")
        assert status == 200
        assert "<html>" in html

    async def test_uses_configured_base_url(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://custom-mirror.example/Home/Episode/xyz",
            text="<html></html>",
            status_code=200,
        )
        async with MikanClient(base_url="https://custom-mirror.example", timeout_seconds=5) as c:
            await c.fetch_episode_page("xyz")
        # pytest_httpx fails if no matching request — assertion implicit

    async def test_raises_on_http_503(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://mikanani.me/Home/Episode/boom",
            status_code=503,
            text="Service Unavailable",
        )
        async with MikanClient(base_url="https://mikanani.me", timeout_seconds=10) as c:
            with pytest.raises(MikanFetchError) as exc:
                await c.fetch_episode_page("boom")
        assert exc.value.status == 503

    async def test_raises_on_http_429(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://mikanani.me/Home/Episode/throttled",
            status_code=429,
        )
        async with MikanClient(base_url="https://mikanani.me", timeout_seconds=10) as c:
            with pytest.raises(MikanFetchError) as exc:
                await c.fetch_episode_page("throttled")
        assert exc.value.status == 429

    async def test_raises_on_network_error(self, httpx_mock: HTTPXMock):
        import httpx
        httpx_mock.add_exception(httpx.ConnectError("boom"))
        async with MikanClient(base_url="https://mikanani.me", timeout_seconds=1) as c:
            with pytest.raises(MikanFetchError) as exc:
                await c.fetch_episode_page("x")
        # Network failures have no HTTP status
        assert exc.value.status is None
        assert "boom" in str(exc.value)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_mikan/test_client.py -v
```

Expected: `ImportError: cannot import name 'MikanClient' from 'module.mikan.client'`.

- [ ] **Step 3: Implement `MikanClient`**

Create `backend/src/module/mikan/client.py`:

```python
"""HTTPX async wrapper for Mikan episode page fetches (spec §8.2).

Wraps base_url + timeout config. Does NOT do rate limiting (that's the
RateLimiter's job, applied at the caller side). Does NOT do retries — the
resolver owns retry policy via the pending_torrent_enrichment queue.

Errors are normalized to MikanFetchError so the resolver can uniformly write
parse_status='failed' + last_error to the cache.
"""
from __future__ import annotations

from typing import Optional

import httpx


class MikanFetchError(Exception):
    """Raised when fetching a Mikan page fails (HTTP non-2xx or network error).

    Attributes:
      status: HTTP status if the server responded; None for connection errors.
    """

    def __init__(self, message: str, *, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


class MikanClient:
    def __init__(self, base_url: str, timeout_seconds: int):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "MikanClient":
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch_episode_page(self, info_hash: str) -> tuple[str, int]:
        """Fetch /Home/Episode/{info_hash}. Returns (html, status_code).

        Raises MikanFetchError on non-2xx or network errors.
        """
        assert self._client is not None, "use MikanClient as an async context manager"
        url = f"{self._base_url}/Home/Episode/{info_hash}"
        try:
            response = await self._client.get(url)
        except httpx.HTTPError as exc:
            raise MikanFetchError(str(exc), status=None) from exc

        if response.status_code >= 400:
            raise MikanFetchError(
                f"HTTP {response.status_code} from {url}",
                status=response.status_code,
            )
        return response.text, response.status_code
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_mikan/test_client.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/mikan/client.py \
          backend/src/tests/test_mikan/test_client.py && \
  git commit -m "feat: MikanClient async HTTP wrapper"
```

---

### Task 5: `RateLimiter` — base class

**Files:**

- Create: `backend/src/module/concurrency/__init__.py` (empty)
- Create: `backend/src/module/concurrency/rate_limiter.py`
- Create: `backend/src/tests/test_concurrency/__init__.py` (empty)
- Create: `backend/src/tests/test_concurrency/test_rate_limiter.py`

- [ ] **Step 1: Write failing tests (base behavior only — degradation in Task 6)**

Create `backend/src/tests/test_concurrency/__init__.py` empty.

Create `backend/src/tests/test_concurrency/test_rate_limiter.py`:

```python
"""RateLimiter unit tests (base behavior, spec §9.2)."""
import asyncio
import time

import pytest

from module.concurrency.rate_limiter import RateLimiter


@pytest.mark.unit
class TestRateLimiterConcurrency:
    async def test_respects_max_concurrent(self):
        """At most max_concurrent entries into the critical section at once."""
        rl = RateLimiter(max_concurrent=2, min_interval_ms=0)
        in_flight = 0
        peak = 0

        async def worker():
            nonlocal in_flight, peak
            async with rl:
                in_flight += 1
                peak = max(peak, in_flight)
                await asyncio.sleep(0.05)
                in_flight -= 1

        await asyncio.gather(*(worker() for _ in range(6)))
        assert peak == 2

    async def test_respects_min_interval(self):
        """Successive calls are spaced by >= min_interval_ms."""
        rl = RateLimiter(max_concurrent=1, min_interval_ms=50)
        timestamps: list[float] = []

        async def worker():
            async with rl:
                timestamps.append(time.monotonic())

        for _ in range(3):
            await worker()

        gaps = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        assert all(g >= 0.045 for g in gaps), f"gaps too tight: {gaps}"


@pytest.mark.unit
class TestRateLimiterReleasesOnException:
    async def test_releases_semaphore_on_exception(self):
        rl = RateLimiter(max_concurrent=1, min_interval_ms=0)

        with pytest.raises(ValueError):
            async with rl:
                raise ValueError("oops")

        # Should still be acquirable afterwards — not deadlocked.
        async with asyncio.timeout(1):
            async with rl:
                pass
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_concurrency/test_rate_limiter.py -v
```

Expected: `ModuleNotFoundError: No module named 'module.concurrency'`.

- [ ] **Step 3: Create package + base RateLimiter**

Create `backend/src/module/concurrency/__init__.py` empty.

Create `backend/src/module/concurrency/rate_limiter.py`:

```python
"""Async rate limiter with max-concurrent + min-interval gating (spec §9.2).

Used as an async context manager. Not thread-safe, but we run single-worker
uvicorn by design (spec §4).

Dynamic degradation (429/503 → halve concurrent, 10 successes → restore)
is layered on in Task 6 via record_result().
"""
from __future__ import annotations

import asyncio
import time


class RateLimiter:
    def __init__(self, max_concurrent: int, min_interval_ms: int):
        assert max_concurrent > 0
        assert min_interval_ms >= 0
        self._base_concurrent = max_concurrent
        self._sem = asyncio.Semaphore(max_concurrent)
        self._min_interval = min_interval_ms / 1000.0
        self._gate = asyncio.Lock()
        self._last_at: float = 0.0

    async def __aenter__(self) -> "RateLimiter":
        await self._sem.acquire()
        async with self._gate:
            now = time.monotonic()
            wait = self._last_at + self._min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_at = time.monotonic()
        return self

    async def __aexit__(self, *exc) -> None:
        self._sem.release()
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_concurrency/test_rate_limiter.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/concurrency/__init__.py \
          backend/src/module/concurrency/rate_limiter.py \
          backend/src/tests/test_concurrency/__init__.py \
          backend/src/tests/test_concurrency/test_rate_limiter.py && \
  git commit -m "feat: base RateLimiter with max-concurrent + min-interval"
```

---

### Task 6: `RateLimiter` dynamic degradation

**Files:**

- Modify: `backend/src/module/concurrency/rate_limiter.py`
- Modify: `backend/src/tests/test_concurrency/test_rate_limiter.py`

- [ ] **Step 1: Append failing tests for degradation**

Add to the end of `backend/src/tests/test_concurrency/test_rate_limiter.py`:

```python
@pytest.mark.unit
class TestRateLimiterDegradation:
    async def test_429_halves_concurrent(self):
        rl = RateLimiter(max_concurrent=4, min_interval_ms=0)
        assert rl.current_concurrent() == 4
        rl.record_result(status=429)
        assert rl.current_concurrent() == 2

    async def test_503_halves_concurrent(self):
        rl = RateLimiter(max_concurrent=4, min_interval_ms=0)
        rl.record_result(status=503)
        assert rl.current_concurrent() == 2

    async def test_halving_floors_at_one(self):
        rl = RateLimiter(max_concurrent=2, min_interval_ms=0)
        rl.record_result(status=429)
        assert rl.current_concurrent() == 1
        rl.record_result(status=429)
        assert rl.current_concurrent() == 1  # does not go below 1

    async def test_ten_consecutive_successes_restore(self):
        rl = RateLimiter(max_concurrent=4, min_interval_ms=0)
        rl.record_result(status=503)
        assert rl.current_concurrent() == 2

        for _ in range(9):
            rl.record_result(status=200)
        assert rl.current_concurrent() == 2  # not yet

        rl.record_result(status=200)
        assert rl.current_concurrent() == 4  # 10th success restores

    async def test_failure_between_successes_resets_counter(self):
        rl = RateLimiter(max_concurrent=4, min_interval_ms=0)
        rl.record_result(status=503)
        for _ in range(5):
            rl.record_result(status=200)
        rl.record_result(status=503)  # resets success counter
        for _ in range(5):
            rl.record_result(status=200)
        # Only 5 successes since last failure — still degraded
        assert rl.current_concurrent() == 1  # halved twice: 4 -> 2 -> 1

    async def test_is_degraded_flag(self):
        rl = RateLimiter(max_concurrent=4, min_interval_ms=0)
        assert rl.is_degraded() is False
        rl.record_result(status=429)
        assert rl.is_degraded() is True

        for _ in range(10):
            rl.record_result(status=200)
        assert rl.is_degraded() is False
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_concurrency/test_rate_limiter.py::TestRateLimiterDegradation -v
```

Expected: `AttributeError: 'RateLimiter' object has no attribute 'record_result'` (or similar).

- [ ] **Step 3: Add degradation logic to `RateLimiter`**

Replace the contents of `backend/src/module/concurrency/rate_limiter.py` with:

```python
"""Async rate limiter with max-concurrent + min-interval gating +
dynamic degradation on 429/503 (spec §9.2, §9.3).

State machine:
  - Base state: max_concurrent = base_concurrent
  - 429/503 received: max_concurrent = max(1, max_concurrent // 2)
                      success_counter := 0
  - 10 consecutive 2xx while degraded: max_concurrent = base_concurrent

Used as an async context manager. Not thread-safe; single-worker assumption.
"""
from __future__ import annotations

import asyncio
import time

_SUCCESS_THRESHOLD = 10
_DEGRADE_STATUSES = (429, 503)


class RateLimiter:
    def __init__(self, max_concurrent: int, min_interval_ms: int):
        assert max_concurrent > 0
        assert min_interval_ms >= 0
        self._base_concurrent = max_concurrent
        self._current_concurrent = max_concurrent
        self._sem = asyncio.Semaphore(max_concurrent)
        self._min_interval = min_interval_ms / 1000.0
        self._gate = asyncio.Lock()
        self._last_at: float = 0.0
        self._success_counter = 0

    def current_concurrent(self) -> int:
        return self._current_concurrent

    def is_degraded(self) -> bool:
        return self._current_concurrent < self._base_concurrent

    def record_result(self, status: int) -> None:
        """Update state based on HTTP response status.

        Call this after every request (including the 200 path). 429/503 halve
        concurrency and reset the success counter; other 2xx responses
        increment the counter and, when degraded, restore after
        _SUCCESS_THRESHOLD consecutive successes.
        """
        if status in _DEGRADE_STATUSES:
            self._success_counter = 0
            new = max(1, self._current_concurrent // 2)
            self._resize(new)
            return

        if 200 <= status < 300 and self.is_degraded():
            self._success_counter += 1
            if self._success_counter >= _SUCCESS_THRESHOLD:
                self._success_counter = 0
                self._resize(self._base_concurrent)

    def _resize(self, new_concurrent: int) -> None:
        """Swap the internal semaphore for one with a new concurrency budget.

        In-flight permits (acquired by callers currently inside the critical
        section) remain valid against the old semaphore — they'll release into
        a semaphore that no one waits on, which is fine. New waiters will use
        the new semaphore.
        """
        self._current_concurrent = new_concurrent
        self._sem = asyncio.Semaphore(new_concurrent)

    async def __aenter__(self) -> "RateLimiter":
        await self._sem.acquire()
        async with self._gate:
            now = time.monotonic()
            wait = self._last_at + self._min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_at = time.monotonic()
        return self

    async def __aexit__(self, *exc) -> None:
        self._sem.release()
```

- [ ] **Step 4: Run all rate limiter tests**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_concurrency/test_rate_limiter.py -v
```

Expected: 9 passed (3 base + 6 degradation).

- [ ] **Step 5: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/concurrency/rate_limiter.py \
          backend/src/tests/test_concurrency/test_rate_limiter.py && \
  git commit -m "feat: RateLimiter dynamic degradation on 429/503"
```

---

### Task 7: Rate limiter service registry

**Files:**

- Create: `backend/src/module/concurrency/registry.py`
- Create: `backend/src/tests/test_concurrency/test_registry.py`

- [ ] **Step 1: Write failing tests**

Create `backend/src/tests/test_concurrency/test_registry.py`:

```python
"""Rate limiter registry tests (spec §9.2)."""
import pytest

from module.concurrency.registry import (
    get_rate_limiter,
    build_mikan_limiter_from_settings,
)


@pytest.mark.unit
class TestRegistry:
    def setup_method(self):
        # Registry is module-level state; reset between tests.
        from module.concurrency import registry as r
        r._LIMITERS.clear()

    def test_get_same_instance_on_repeated_call(self):
        a = get_rate_limiter("mikan", max_concurrent=2, min_interval_ms=500)
        b = get_rate_limiter("mikan", max_concurrent=999, min_interval_ms=999)
        assert a is b  # subsequent config args ignored once registered

    def test_different_services_have_different_limiters(self):
        a = get_rate_limiter("mikan", max_concurrent=2, min_interval_ms=500)
        b = get_rate_limiter("pikpak", max_concurrent=1, min_interval_ms=1000)
        assert a is not b
        assert a.current_concurrent() == 2
        assert b.current_concurrent() == 1

    def test_build_mikan_limiter_reads_settings(self, monkeypatch):
        from module.conf.models import Mikan
        from module.conf import settings

        mikan_cfg = Mikan(max_concurrent=3, min_interval_ms=750)
        monkeypatch.setattr(settings, "mikan", mikan_cfg, raising=False)

        rl = build_mikan_limiter_from_settings()
        assert rl.current_concurrent() == 3
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_concurrency/test_registry.py -v
```

Expected: `ImportError: cannot import name 'get_rate_limiter' from 'module.concurrency.registry'`.

- [ ] **Step 3: Implement registry**

Create `backend/src/module/concurrency/registry.py`:

```python
"""Module-level RateLimiter singletons keyed by service name (spec §9.2).

Each external service (mikan, pikpak, qbittorrent) has its own limiter.
First call with (name, config) instantiates and stashes; subsequent calls with
the same name return the existing instance (config changes require restart).

Plan 05 will wire these into the RSS pipeline and downloader calls.
"""
from __future__ import annotations

from .rate_limiter import RateLimiter

_LIMITERS: dict[str, RateLimiter] = {}


def get_rate_limiter(
    name: str,
    max_concurrent: int,
    min_interval_ms: int,
) -> RateLimiter:
    """Return the singleton limiter for `name`, creating it on first call."""
    existing = _LIMITERS.get(name)
    if existing is not None:
        return existing
    limiter = RateLimiter(max_concurrent=max_concurrent, min_interval_ms=min_interval_ms)
    _LIMITERS[name] = limiter
    return limiter


def build_mikan_limiter_from_settings() -> RateLimiter:
    """Build (or fetch) the `mikan` limiter from the current runtime settings."""
    from module.conf import settings

    return get_rate_limiter(
        "mikan",
        max_concurrent=settings.mikan.max_concurrent,
        min_interval_ms=settings.mikan.min_interval_ms,
    )
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_concurrency/test_registry.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/concurrency/registry.py \
          backend/src/tests/test_concurrency/test_registry.py && \
  git commit -m "feat: rate limiter service registry with mikan builder"
```

---

### Task 8: `MikanResolver` — orchestrator

**Files:**

- Create: `backend/src/module/mikan/resolver.py`
- Create: `backend/src/tests/test_mikan/test_resolver.py`

- [ ] **Step 1: Write failing tests**

Create `backend/src/tests/test_mikan/test_resolver.py`:

```python
"""MikanResolver orchestrator tests (spec §8)."""
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from module.concurrency.rate_limiter import RateLimiter
from module.mikan.client import MikanClient
from module.mikan.resolver import MikanResolver
from module.repositories.mikan_ref import MikanEpisodeRefRepository

_FIX = Path(__file__).parent.parent / "fixtures" / "mikan"


def _load(name: str) -> str:
    return (_FIX / name).read_text(encoding="utf-8")


@pytest.fixture
def fake_limiter():
    return RateLimiter(max_concurrent=4, min_interval_ms=0)


@pytest.mark.integration
class TestMikanResolverCacheHit:
    async def test_returns_cached_ok_without_network(
        self, db_session, fake_limiter, httpx_mock: HTTPXMock
    ):
        repo = MikanEpisodeRefRepository(db_session)
        await repo.upsert(
            info_hash="cached",
            parse_status="ok",
            mikan_bangumi_id=7,
            mikan_subgroup_id=8,
            canonical_title="Cached",
            poster_url="/p.jpg",
        )
        await db_session.commit()

        async with MikanClient("https://mikanani.me", 10) as client:
            resolver = MikanResolver(client=client, limiter=fake_limiter, mikan_ref_repo=repo)
            ref = await resolver.resolve("cached")

        # No HTTP calls should have been made.
        assert httpx_mock.get_requests() == []
        assert ref is not None
        assert ref.mikan_bangumi_id == 7


@pytest.mark.integration
class TestMikanResolverCacheMiss:
    async def test_fetches_parses_persists(
        self, db_session, fake_limiter, httpx_mock: HTTPXMock
    ):
        httpx_mock.add_response(
            url="https://mikanani.me/Home/Episode/newhash",
            text=_load("episode_page_subscribe_button.html"),
            status_code=200,
        )

        repo = MikanEpisodeRefRepository(db_session)
        async with MikanClient("https://mikanani.me", 10) as client:
            resolver = MikanResolver(client=client, limiter=fake_limiter, mikan_ref_repo=repo)
            ref = await resolver.resolve("newhash")
            await db_session.commit()

        assert ref is not None
        assert ref.mikan_bangumi_id == 3906
        assert ref.mikan_subgroup_id == 370

        row = await repo.get("newhash")
        assert row.parse_status == "ok"
        assert row.mikan_bangumi_id == 3906
        assert row.canonical_title.startswith("身为悲剧")

    async def test_non_mikan_page_persists_as_non_mikan(
        self, db_session, fake_limiter, httpx_mock: HTTPXMock
    ):
        httpx_mock.add_response(
            url="https://mikanani.me/Home/Episode/notmikan",
            text=_load("episode_page_no_ref.html"),
            status_code=200,
        )

        repo = MikanEpisodeRefRepository(db_session)
        async with MikanClient("https://mikanani.me", 10) as client:
            resolver = MikanResolver(client=client, limiter=fake_limiter, mikan_ref_repo=repo)
            ref = await resolver.resolve("notmikan")
            await db_session.commit()

        assert ref is None
        row = await repo.get("notmikan")
        assert row.parse_status == "non_mikan"

    async def test_http_error_persists_as_failed_and_records_limiter(
        self, db_session, fake_limiter, httpx_mock: HTTPXMock
    ):
        httpx_mock.add_response(
            url="https://mikanani.me/Home/Episode/boom",
            status_code=503,
        )

        repo = MikanEpisodeRefRepository(db_session)
        async with MikanClient("https://mikanani.me", 10) as client:
            resolver = MikanResolver(client=client, limiter=fake_limiter, mikan_ref_repo=repo)
            ref = await resolver.resolve("boom")
            await db_session.commit()

        assert ref is None
        row = await repo.get("boom")
        assert row.parse_status == "failed"
        assert "503" in row.last_error
        # Limiter should have been degraded by the 503.
        assert fake_limiter.is_degraded() is True


@pytest.mark.integration
class TestMikanResolverSkipsCachedNonMikan:
    """Once cached as non_mikan, never retried per spec §6.1."""

    async def test_cached_non_mikan_is_not_refetched(
        self, db_session, fake_limiter, httpx_mock: HTTPXMock
    ):
        repo = MikanEpisodeRefRepository(db_session)
        await repo.upsert(info_hash="skip", parse_status="non_mikan")
        await db_session.commit()

        async with MikanClient("https://mikanani.me", 10) as client:
            resolver = MikanResolver(client=client, limiter=fake_limiter, mikan_ref_repo=repo)
            ref = await resolver.resolve("skip")

        assert ref is None
        assert httpx_mock.get_requests() == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_mikan/test_resolver.py -v
```

Expected: `ImportError: cannot import name 'MikanResolver' from 'module.mikan.resolver'`.

- [ ] **Step 3: Implement `MikanResolver`**

Create `backend/src/module/mikan/resolver.py`:

```python
"""MikanResolver — orchestrates cache + rate-limited fetch + parse + persist
(spec §8).

Flow per resolve(info_hash):
  1. Check mikan_episode_ref cache
     - parse_status='ok'        → return MikanRef from row (no network)
     - parse_status='non_mikan' → return None (no network, never retry)
     - parse_status='failed'    → retry path (fall through to fetch)
     - cache miss               → fetch path
  2. Acquire rate limiter, fetch page via MikanClient
  3. Feed limiter HTTP status (so 429/503 triggers degradation)
  4. Parse HTML
     - MikanRef extracted   → upsert cache as 'ok', return ref
     - No ref extracted      → upsert cache as 'non_mikan', return None
  5. On fetch error: upsert cache as 'failed' + last_error, return None
"""
from __future__ import annotations

from typing import Optional

from module.concurrency.rate_limiter import RateLimiter
from module.mikan.client import MikanClient, MikanFetchError
from module.mikan.parser import MikanRef, parse_mikan_page
from module.repositories.mikan_ref import MikanEpisodeRefRepository


class MikanResolver:
    def __init__(
        self,
        client: MikanClient,
        limiter: RateLimiter,
        mikan_ref_repo: MikanEpisodeRefRepository,
    ):
        self._client = client
        self._limiter = limiter
        self._repo = mikan_ref_repo

    async def resolve(self, info_hash: str) -> Optional[MikanRef]:
        """Return MikanRef on success, None if the page is not a Mikan episode
        page or the fetch failed. All outcomes persist to mikan_episode_ref."""
        cached = await self._repo.get(info_hash)
        if cached is not None:
            if cached.parse_status == "ok":
                return MikanRef(
                    mikan_bangumi_id=cached.mikan_bangumi_id,
                    mikan_subgroup_id=cached.mikan_subgroup_id,
                    canonical_title=cached.canonical_title,
                    poster_url=cached.poster_url,
                )
            if cached.parse_status == "non_mikan":
                return None
            # parse_status == "failed" → fall through and retry

        async with self._limiter:
            try:
                html, status = await self._client.fetch_episode_page(info_hash)
                self._limiter.record_result(status)
            except MikanFetchError as exc:
                if exc.status is not None:
                    self._limiter.record_result(exc.status)
                await self._repo.upsert(
                    info_hash=info_hash,
                    parse_status="failed",
                    last_error=str(exc),
                )
                return None

        ref = parse_mikan_page(html)
        if ref is None:
            await self._repo.upsert(
                info_hash=info_hash,
                parse_status="non_mikan",
            )
            return None

        await self._repo.upsert(
            info_hash=info_hash,
            parse_status="ok",
            mikan_bangumi_id=ref.mikan_bangumi_id,
            mikan_subgroup_id=ref.mikan_subgroup_id,
            canonical_title=ref.canonical_title,
            poster_url=ref.poster_url,
        )
        return ref
```

- [ ] **Step 4: Tests need `db_session` fixture — relocate or add to conftest**

The `MikanResolver` tests use the `db_session` fixture which is currently scoped to `backend/src/tests/test_repositories/conftest.py`. To share it with `test_mikan/`, move the fixture (and the model imports) up to `backend/src/tests/conftest.py`. Read the existing file first; if it doesn't exist, create it:

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  ls src/tests/conftest.py 2>/dev/null || echo "not present"
```

If present, append the fixture. If absent, create `backend/src/tests/conftest.py`:

```python
"""Project-wide pytest fixtures.

Repository and service tests share the same DB fixture; keep the async
engine construction in one place.
"""
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from module.domain.models.base import Base

# Register every model so Base.metadata.create_all builds the full schema.
import module.domain.models.user  # noqa: F401
import module.domain.models.rss  # noqa: F401
import module.domain.models.bangumi  # noqa: F401
import module.domain.models.torrent  # noqa: F401
import module.domain.models.series  # noqa: F401
import module.domain.models.mikan_ref  # noqa: F401
import module.domain.models.pending_enrichment  # noqa: F401
import module.domain.models.merge_history  # noqa: F401


@pytest_asyncio.fixture
async def db_session(tmp_path):
    db_file = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()
```

Then delete the now-redundant `backend/src/tests/test_repositories/conftest.py` to avoid fixture duplication:

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  rm src/tests/test_repositories/conftest.py
```

- [ ] **Step 5: Run tests**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_mikan/test_resolver.py src/tests/test_repositories/ -v
```

Expected: 5 new resolver tests pass + all previous repository tests still pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/mikan/resolver.py \
          backend/src/tests/test_mikan/test_resolver.py \
          backend/src/tests/conftest.py && \
  git rm backend/src/tests/test_repositories/conftest.py && \
  git commit -m "feat: MikanResolver orchestrator with cache + rate-limited fetch"
```

---

### Task 9: `RssLockRegistry` — skip-if-held

**Files:**

- Create: `backend/src/module/concurrency/rss_lock.py`
- Create: `backend/src/tests/test_concurrency/test_rss_lock.py`

- [ ] **Step 1: Write failing tests**

Create `backend/src/tests/test_concurrency/test_rss_lock.py`:

```python
"""RssLockRegistry tests (spec §9.1)."""
import asyncio

import pytest

from module.concurrency.rss_lock import RssLockRegistry


@pytest.mark.unit
class TestRssLockRegistry:
    async def test_first_acquire_returns_lock(self):
        registry = RssLockRegistry()
        lock = await registry.try_acquire(rss_id=1)
        assert lock is not None
        lock.release()

    async def test_second_acquire_while_held_returns_none(self):
        registry = RssLockRegistry()
        first = await registry.try_acquire(rss_id=1)
        assert first is not None

        second = await registry.try_acquire(rss_id=1)
        assert second is None

        first.release()

    async def test_acquire_returns_lock_after_release(self):
        registry = RssLockRegistry()
        first = await registry.try_acquire(rss_id=1)
        first.release()

        second = await registry.try_acquire(rss_id=1)
        assert second is not None
        second.release()

    async def test_different_rss_ids_are_independent(self):
        registry = RssLockRegistry()
        a = await registry.try_acquire(rss_id=1)
        b = await registry.try_acquire(rss_id=2)
        assert a is not None
        assert b is not None
        a.release()
        b.release()

    async def test_concurrent_acquire_only_one_wins(self):
        """Under concurrent try_acquire on the same rss_id, exactly one wins."""
        registry = RssLockRegistry()

        async def attempt() -> bool:
            lock = await registry.try_acquire(rss_id=42)
            if lock is None:
                return False
            await asyncio.sleep(0.01)
            lock.release()
            return True

        results = await asyncio.gather(*(attempt() for _ in range(5)))
        # Exactly one of the five attempts should win. The others see it held
        # and return None.
        assert sum(results) == 1
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_concurrency/test_rss_lock.py -v
```

Expected: `ImportError: cannot import name 'RssLockRegistry' from 'module.concurrency.rss_lock'`.

- [ ] **Step 3: Implement `RssLockRegistry`**

Create `backend/src/module/concurrency/rss_lock.py`:

```python
"""Per-RSS asyncio lock registry with skip-if-held semantics (spec §9.1).

RSS refresh (cron) and manual refresh API share this registry. If a refresh
is already running for an rss_id, new attempts return None instead of
queueing — the caller logs and skips.
"""
from __future__ import annotations

import asyncio
from typing import Optional


class RssLockRegistry:
    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = {}
        self._registry_mutex = asyncio.Lock()

    async def try_acquire(self, rss_id: int) -> Optional[asyncio.Lock]:
        """Return the acquired lock on success, or None if already held.

        Caller is responsible for calling `.release()` exactly once.
        """
        async with self._registry_mutex:
            lock = self._locks.setdefault(rss_id, asyncio.Lock())
            if lock.locked():
                return None
            await lock.acquire()
            return lock
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_concurrency/test_rss_lock.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/concurrency/rss_lock.py \
          backend/src/tests/test_concurrency/test_rss_lock.py && \
  git commit -m "feat: RssLockRegistry per-RSS skip-if-held"
```

---

### Task 10: `IdentityResolver` service — three-tier

**Files:**

- Create: `backend/src/module/services/identity_resolver.py`
- Create: `backend/src/tests/test_services/test_identity_resolver.py`

- [ ] **Step 1: Write failing tests**

Create `backend/src/tests/test_services/test_identity_resolver.py`:

```python
"""IdentityResolver integration tests (spec §6.4)."""
import pytest

from module.mikan.parser import MikanRef
from module.repositories.series import SeriesRepository
from module.services.identity_resolver import IdentityResolver, ResolvedIdentity


@pytest.mark.integration
class TestIdentityResolverTier1:
    async def test_mikan_match_returns_existing_series(self, db_session):
        series_repo = SeriesRepository(db_session)
        existing = await series_repo.create({
            "mikan_bangumi_id": 3906,
            "canonical_title": "LasTame S2",
            "normalized_title": "lastame",
            "season": 2,
            "root_path": "/downloads/LasTame/Season 2",
        })
        await db_session.commit()

        resolver = IdentityResolver(series_repo=series_repo)
        result = await resolver.resolve(
            mikan_ref=MikanRef(mikan_bangumi_id=3906, mikan_subgroup_id=370,
                               canonical_title="LasTame S2", poster_url=None),
            normalized_title="different_but_ignored",
            season=2,
            cour_part=None,
            raw_title_for_root="LasTame Season2",
        )
        assert isinstance(result, ResolvedIdentity)
        assert result.series.id == existing.id
        assert result.tier == "mikan"
        assert result.newly_created is False

    async def test_mikan_miss_creates_new_series_from_mikan_ref(self, db_session):
        series_repo = SeriesRepository(db_session)
        resolver = IdentityResolver(series_repo=series_repo)

        result = await resolver.resolve(
            mikan_ref=MikanRef(mikan_bangumi_id=1234, mikan_subgroup_id=99,
                               canonical_title="葬送的芙莉蓮",
                               poster_url="/p/frieren.jpg"),
            normalized_title="葬送的芙莉莲",
            season=1,
            cour_part=None,
            raw_title_for_root="葬送的芙莉蓮",
        )
        await db_session.commit()

        assert result.series.mikan_bangumi_id == 1234
        assert result.series.canonical_title == "葬送的芙莉蓮"
        assert result.series.normalized_title == "葬送的芙莉莲"
        assert result.series.poster_url == "/p/frieren.jpg"
        assert result.tier == "mikan"
        assert result.newly_created is True
        assert result.series.pending_review is False


@pytest.mark.integration
class TestIdentityResolverTier2:
    async def test_no_mikan_ref_falls_back_to_existing_series(self, db_session):
        series_repo = SeriesRepository(db_session)
        existing = await series_repo.create({
            "canonical_title": "Fallback Show",
            "normalized_title": "fallbackshow",
            "season": 1,
            "root_path": "/downloads/fallbackshow",
        })
        await db_session.commit()

        resolver = IdentityResolver(series_repo=series_repo)
        result = await resolver.resolve(
            mikan_ref=None,
            normalized_title="fallbackshow",
            season=1,
            cour_part=None,
            raw_title_for_root="Fallback Show",
        )
        assert result.series.id == existing.id
        assert result.tier == "fallback"
        assert result.newly_created is False
        assert result.series.pending_review is False


@pytest.mark.integration
class TestIdentityResolverTier3:
    async def test_creates_pending_review_series_when_no_match(self, db_session):
        series_repo = SeriesRepository(db_session)
        resolver = IdentityResolver(series_repo=series_repo)

        result = await resolver.resolve(
            mikan_ref=None,
            normalized_title="unknownshow",
            season=1,
            cour_part=None,
            raw_title_for_root="Unknown Show",
        )
        await db_session.commit()

        assert result.series.pending_review is True
        assert result.tier == "pending_review"
        assert result.newly_created is True
        assert result.series.canonical_title == "Unknown Show"

    async def test_flags_cross_source_candidates(self, db_session):
        """If a Mikan-sourced series exists with matching fallback key, the
        Tier-3 result surfaces it as a merge candidate."""
        series_repo = SeriesRepository(db_session)
        mikan_existing = await series_repo.create({
            "mikan_bangumi_id": 100,
            "canonical_title": "Mikan Version",
            "normalized_title": "sharedtitle",
            "season": 1,
            "root_path": "/downloads/mikan",
        })
        await db_session.commit()

        resolver = IdentityResolver(series_repo=series_repo)
        result = await resolver.resolve(
            mikan_ref=None,
            normalized_title="sharedtitle",
            season=1,
            cour_part=None,
            raw_title_for_root="Nyaa Version",
        )
        await db_session.commit()

        assert result.series.pending_review is True
        assert result.tier == "pending_review"
        assert result.merge_candidates == [mikan_existing.id]
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_services/test_identity_resolver.py -v
```

Expected: `ModuleNotFoundError: No module named 'module.services.identity_resolver'`.

- [ ] **Step 3: Implement `IdentityResolver`**

Create `backend/src/module/services/identity_resolver.py`:

```python
"""IdentityResolver — three-tier series identity lookup (spec §6.4).

Tier 1 (mikan): MikanRef.mikan_bangumi_id → Series.mikan_bangumi_id
  - Hit  → return existing
  - Miss → create new Series from MikanRef data

Tier 2 (fallback): (normalized_title, season, cour_part) → Series
  - Hit  → return existing (used when no MikanRef is available)

Tier 3 (pending_review): no match in tiers 1/2
  - Create new Series with pending_review=True
  - If a Mikan-sourced series exists with the same fallback key, surface it
    as a cross-source merge candidate (caller / UI decides whether to merge)

`raw_title_for_root` is the human-readable title used to derive the
Series.canonical_title and root_path when creating a new row. Normally this
is `MikanRef.canonical_title` when Mikan resolved, else the torrent's raw
title (best guess).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

from module.conf import settings
from module.domain.models.series import Series
from module.mikan.parser import MikanRef
from module.repositories.series import SeriesRepository


@dataclass
class ResolvedIdentity:
    series: Series
    tier: str  # "mikan" | "fallback" | "pending_review"
    newly_created: bool
    merge_candidates: list[int] = field(default_factory=list)


_ILLEGAL_PATH_CHARS = re.compile(r'[\\/:*?"<>|]+')


def _safe_path_component(title: str) -> str:
    """Strip characters that would confuse file systems (PikPak + Win + POSIX).

    Mirrors the sanitation applied in the legacy save_path pipeline (see
    commit f327af6c). Replaces runs of illegal chars with a single space.
    """
    cleaned = _ILLEGAL_PATH_CHARS.sub(" ", title).strip()
    return cleaned or "untitled"


def _derive_root_path(title: str) -> str:
    base = settings.downloader.path.rstrip("/\\")
    return os.path.join(base, _safe_path_component(title))


class IdentityResolver:
    def __init__(self, series_repo: SeriesRepository):
        self._repo = series_repo

    async def resolve(
        self,
        mikan_ref: Optional[MikanRef],
        normalized_title: str,
        season: int,
        cour_part: Optional[str],
        raw_title_for_root: str,
    ) -> ResolvedIdentity:
        # Tier 1: Mikan authoritative
        if mikan_ref is not None:
            hit = await self._repo.get_by_mikan_id(mikan_ref.mikan_bangumi_id)
            if hit is not None:
                return ResolvedIdentity(series=hit, tier="mikan", newly_created=False)

            title = mikan_ref.canonical_title or raw_title_for_root
            created = await self._repo.create({
                "mikan_bangumi_id": mikan_ref.mikan_bangumi_id,
                "canonical_title": title,
                "normalized_title": normalized_title,
                "season": season,
                "cour_part": cour_part,
                "poster_url": mikan_ref.poster_url,
                "root_path": _derive_root_path(title),
                "pending_review": False,
            })
            return ResolvedIdentity(series=created, tier="mikan", newly_created=True)

        # Tier 2: fallback key
        hit = await self._repo.get_by_fallback(normalized_title, season, cour_part)
        if hit is not None:
            return ResolvedIdentity(series=hit, tier="fallback", newly_created=False)

        # Tier 3: pending review, possibly with cross-source candidates
        candidates = await self._repo.find_possible_cross_source_merge(
            normalized_title, season, cour_part,
        )
        created = await self._repo.create({
            "canonical_title": raw_title_for_root,
            "normalized_title": normalized_title,
            "season": season,
            "cour_part": cour_part,
            "root_path": _derive_root_path(raw_title_for_root),
            "pending_review": True,
        })
        return ResolvedIdentity(
            series=created,
            tier="pending_review",
            newly_created=True,
            merge_candidates=[c.id for c in candidates],
        )
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_services/test_identity_resolver.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/services/identity_resolver.py \
          backend/src/tests/test_services/test_identity_resolver.py && \
  git commit -m "feat: IdentityResolver three-tier series identity lookup"
```

---

### Task 11: Full test-suite sanity pass

**Files:** None.

- [ ] **Step 1: Run unit + migration + mikan + concurrency tests**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_repositories/ \
                          src/tests/test_domain/ \
                          src/tests/test_services/ \
                          src/tests/test_migrations/ \
                          src/tests/test_mikan/ \
                          src/tests/test_concurrency/ \
                          -q
```

Expected: all previously-green tests remain green plus the new Plan 03 tests. Approximate growth over Plan 02 baseline (1111 passed):
- 6 parser + 5 client + 5 resolver = 16 mikan
- 3 base + 6 degradation + 3 registry + 5 rss_lock = 17 concurrency
- 2 config
- 5 identity_resolver
- **Total new ≈ 40**, target ≈ **1151 passed**.

- [ ] **Step 2: Run e2e suite**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_e2e/ -q
```

Expected: `144 passed, 1 xfailed` — unchanged from Plan 02 baseline. Plan 03 did not modify any pipeline code, so e2e count must stay the same. If any e2e test fails, STOP and investigate.

- [ ] **Step 3: Production DB smoke test**

```bash
cp ~/autobangumi/ab-data/bangumi.db /tmp/prod_smoke_p3.db && \
cd /Users/tk/ws/Auto_Bangumi/backend && \
AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/prod_smoke_p3.db" \
  uv run python -c "
import asyncio, sys
sys.path.insert(0, 'src')
from module.database.migrate import run_migrations
asyncio.run(run_migrations())
print('OK')
" && \
sqlite3 /tmp/prod_smoke_p3.db "SELECT version_num FROM alembic_version; \
  SELECT 'bangumi',COUNT(*) FROM bangumi UNION ALL \
  SELECT 'torrent',COUNT(*) FROM torrent UNION ALL \
  SELECT 'series',COUNT(*) FROM series UNION ALL \
  SELECT 'mikan_episode_ref',COUNT(*) FROM mikan_episode_ref;"
```

Expected:
- `alembic_version` = `0005_add_merge_history` (Plan 03 adds no migrations)
- bangumi / torrent counts unchanged from Plan 02 smoke test (62 / 523 as of 2026-04-17)
- `series` and `mikan_episode_ref` counts = 0 (no data populated yet)

No commit — observation only.

---

## Post-Plan Verification Checklist

- [ ] `cd backend && uv run python -c "from module.mikan.parser import MikanRef, parse_mikan_page; print('ok')"` succeeds
- [ ] `cd backend && uv run python -c "from module.mikan.client import MikanClient, MikanFetchError; print('ok')"` succeeds
- [ ] `cd backend && uv run python -c "from module.mikan.resolver import MikanResolver; print('ok')"` succeeds
- [ ] `cd backend && uv run python -c "from module.concurrency.rate_limiter import RateLimiter; print('ok')"` succeeds
- [ ] `cd backend && uv run python -c "from module.concurrency.rss_lock import RssLockRegistry; print('ok')"` succeeds
- [ ] `cd backend && uv run python -c "from module.concurrency.registry import get_rate_limiter, build_mikan_limiter_from_settings; print('ok')"` succeeds
- [ ] `cd backend && uv run python -c "from module.services.identity_resolver import IdentityResolver, ResolvedIdentity; print('ok')"` succeeds
- [ ] `cd backend && uv run python -m pytest src/tests/ -q --ignore=src/tests/test_e2e` reports `1151+ passed`
- [ ] `cd backend && uv run python -m pytest src/tests/test_e2e/ -q` reports `144 passed, 1 xfailed`
- [ ] Production DB smoke test: counts unchanged, new tables empty
- [ ] `git log --oneline 3942b753..HEAD` shows Plan 03 commits (10 expected)

---

## Commit Summary (Phase 2)

Approximate commit sequence:

1. `feat: add pytest-httpx + anyio dev dependencies`
2. `feat: Mikan episode-page parser with 3-tier fallback`
3. `feat: Mikan config section with base_url + rate limits + health thresholds`
4. `feat: MikanClient async HTTP wrapper`
5. `feat: base RateLimiter with max-concurrent + min-interval`
6. `feat: RateLimiter dynamic degradation on 429/503`
7. `feat: rate limiter service registry with mikan builder`
8. `feat: MikanResolver orchestrator with cache + rate-limited fetch`
9. `feat: RssLockRegistry per-RSS skip-if-held`
10. `feat: IdentityResolver three-tier series identity lookup`

---

## Exit Criteria

Phase 2 is complete when:

1. `MikanResolver` can resolve a cached torrent (cache hit, no HTTP) OR fetch + parse + persist a new one
2. `RateLimiter` correctly degrades on 429/503 and restores after 10 consecutive successes
3. `RssLockRegistry` returns None on held locks (skip-if-held)
4. `IdentityResolver` correctly dispatches to tier 1/2/3 and surfaces cross-source merge candidates when applicable
5. All tests green: ~1151+ unit/integration + 144 e2e + 1 xfailed
6. Production DB smoke test shows schema unchanged (Plan 03 did not touch migrations)
7. Plan 04 (bangumi table migration + merge transaction + migrate_duplicates.py + rename pipeline) can start using these modules

---

## Known Follow-ups (tracked for later plans)

- **Plan 04:** Modify `bangumi` table (drop deprecated columns, add `series_id` NOT NULL + `mikan_subgroup_id` + `active` + `path_override` + `observed_groups`, add partial unique indexes), add `torrent.mikan_bangumi_id` + `torrent.mikan_subgroup_id`, merge transaction logic, `migrate_duplicates.py` script (auto-merge + backfill), rename pipeline switch to `series.root_path` + `active` filtering, Rename Conflict detection.
- **Plan 05:** Wire `MikanResolver` + `RssLockRegistry` + `IdentityResolver` + `RateLimiter` into `rss_engine.py` and the `rss_refresh_job` scheduler. Persist `pending_torrent_enrichment` rows for unresolved torrents. API rewrite (`/api/v1/series`, `/api/v1/merge-history`, `/api/v1/health/mikan`, `/api/v1/health/concurrency`, `/api/v1/pending-resolution`). WebUI pages (`/series`, `/series/:id`, `/merge-history`, `/pending-resolution`). Dashboard banner.
