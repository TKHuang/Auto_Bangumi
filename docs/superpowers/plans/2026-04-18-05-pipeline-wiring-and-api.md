# Pipeline Wiring + API Rewrite + Shim Removal (Phase 05)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the RSS refresh path through `RssLockRegistry`, `MikanResolver`, `IdentityResolver`, and the `pending_torrent_enrichment` queue. Add the new `/api/v1/series/*`, `/api/v1/bangumi/merge`, `/api/v1/pending-resolution/*`, and `/api/v1/health/*` endpoints. Remove the `Bangumi` `@property` compat shims and clear all 10 `TODO(plan05)` markers. Backend-only — WebUI rewrite is deferred to a future plan.

**Architecture:**
- The RSS refresh job becomes the single chokepoint that owns concurrency control. Each `rss_id` acquires a per-RSS lock from `RssLockRegistry` (skip-if-held). Inside the lock, every fetched torrent is resolved through `MikanResolver` (which uses the rate limiter + cache). Resolved torrents flow to `IdentityResolver`; unresolvable ones land in `pending_torrent_enrichment`.
- A new scheduled job (`enrichment_retry`) drains `pending_torrent_enrichment` independently. Successful retries promote the torrent to a real torrent + bangumi row.
- API rewrite is mostly additive (new `/series/*` routes); the existing `/bangumi/*` endpoints stay for now and just expose the new schema via existing repos. The `@property` shims on `Bangumi` go away once every caller reads through the Series relationship.
- `/api/v1/health/mikan` and `/api/v1/health/concurrency` expose the existing `MikanHealth`, `RateLimiter`, and `RssLockRegistry` state — no new state is invented.

**Tech Stack:** FastAPI async, SQLAlchemy 2.0 + aiosqlite, APScheduler v4, pytest + pytest-httpx.

**Out of scope (deferred):**
- WebUI new pages (`/series`, `/pending-resolution`, `/merge-history`) — Plan 06.
- Dashboard banner components — Plan 06.
- `migrate_duplicates` rehearsal on production snapshot (Plan 04 Task 13) — operational, not code.

---

## File Map

### Created
- `backend/src/module/services/pipeline/__init__.py`
- `backend/src/module/services/pipeline/rss_pipeline.py` — orchestrator that walks an RSS feed end-to-end (lock → fetch → resolve → enqueue|create).
- `backend/src/module/services/pending_enrichment.py` — read/write helpers around `pending_torrent_enrichment`.
- `backend/src/module/scheduler/jobs/enrichment_retry.py` — scheduled drain of the queue.
- `backend/src/module/api/v1/series.py` — `/api/v1/series/*` router.
- `backend/src/module/api/v1/merge.py` — `/api/v1/bangumi/merge` and `/api/v1/merge-history/*` routers.
- `backend/src/module/api/v1/pending_resolution.py` — `/api/v1/pending-resolution/*` router.
- `backend/src/module/api/v1/health.py` — `/api/v1/health/mikan` and `/api/v1/health/concurrency` routers.
- `backend/src/tests/test_services/test_rss_pipeline.py`
- `backend/src/tests/test_services/test_pending_enrichment.py`
- `backend/src/tests/test_scheduler/test_enrichment_retry.py`
- `backend/src/tests/test_api_contract/test_series.py`
- `backend/src/tests/test_api_contract/test_merge.py`
- `backend/src/tests/test_api_contract/test_pending_resolution.py`
- `backend/src/tests/test_api_contract/test_health.py`

### Modified
- `backend/src/module/scheduler/jobs/rss_refresh.py` — delegate to `RssPipeline.run_for_feed(rss_id)` per feed.
- `backend/src/module/services/rss_engine.py` — `_auto_create_bangumi` and `create_bangumi_from_torrent` lose the inline IdentityResolver dance; they get called by `RssPipeline` after Mikan enrichment instead.
- `backend/src/module/services/collector.py` — `subscribe_season` / `subscribe_batch` receive the resolved Series via the pipeline; remove the inline `resolve_series_for_rss` call.
- `backend/src/module/api/v1/__init__.py` — register the four new routers.
- `backend/src/module/api/v1/rss.py` — re-enable duplicate-by-title check via `SeriesRepository.find_by_canonical_title`; remove `TODO(plan05)` markers; rewrite read sites to access `bangumi.series.*` directly.
- `backend/src/module/api/v1/bangumi.py` — same: rewrite read sites + remove `TODO(plan05)` markers.
- `backend/src/module/services/rss_engine.py` — remove `getattr(bangumi, "title_raw", None)` reads (3 sites); after Series resolution, `series.canonical_title` is authoritative.
- `backend/src/module/searcher/searcher.py` — replace `getattr(bangumi, "title_raw", None)` read.
- `backend/src/module/network/request_contents.py` — replace `getattr(bangumi, "title_raw", None)` read.
- `backend/src/module/rss/analyser.py` — replace `getattr(bangumi, "title_raw", None)` read.
- `backend/src/module/repositories/bangumi.py` — drop `_DROPPED_COLUMNS` filter, drop `_SILENT_DROP_ON_WRITE`, drop `_apply_update_dict` legacy remap branches. Keep only the new schema.
- `backend/src/module/domain/models/bangumi.py` — REMOVE `@property official_title`, `season`, `year`, `save_path`, `poster_link` shims.
- `backend/src/module/repositories/series.py` — add `find_by_canonical_title(title: str)`.
- `backend/src/module/scheduler/scheduler.py` (or wherever jobs are registered) — register `enrichment_retry` job.

---

## Task 1: Series repository — `find_by_canonical_title`

**Files:**
- Modify: `backend/src/module/repositories/series.py`
- Create: `backend/src/tests/test_repositories/test_series_find_by_title.py`

**Background:** Plan 04 Task 12 disabled the duplicate-by-title check at `api/v1/rss.py:131` because `find_by_official_title` had been removed and there was no series-aware replacement. This task adds the lookup so Task 7 can re-enable the check.

- [ ] **Step 1: Write the failing test**

```python
# backend/src/tests/test_repositories/test_series_find_by_title.py
import pytest
from module.domain.models.series import Series
from module.repositories.series import SeriesRepository


@pytest.mark.integration
async def test_find_by_canonical_title_returns_undeleted_match(db_session):
    s = Series(
        canonical_title="Demo",
        normalized_title="demo",
        season=1,
        root_path="/p/Demo",
        pending_review=False,
    )
    db_session.add(s)
    await db_session.flush()

    repo = SeriesRepository(db_session)
    found = await repo.find_by_canonical_title("Demo")
    assert found is not None and found.id == s.id

    # case-insensitive
    found_ci = await repo.find_by_canonical_title("demo")
    assert found_ci is not None and found_ci.id == s.id

    # miss
    miss = await repo.find_by_canonical_title("Other")
    assert miss is None
```

- [ ] **Step 2: Run, verify it fails**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
uv run pytest src/tests/test_repositories/test_series_find_by_title.py -v
```

- [ ] **Step 3: Implement `find_by_canonical_title`**

In `backend/src/module/repositories/series.py`, add:

```python
async def find_by_canonical_title(self, title: str) -> Optional[Series]:
    """Case-insensitive lookup by canonical_title. Returns first match or None."""
    stmt = select(Series).where(
        func.lower(Series.canonical_title) == title.lower()
    )
    result = await self.session.execute(stmt)
    return result.scalars().first()
```

Add `from sqlalchemy import func` import if missing.

- [ ] **Step 4: Pass + commit**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
uv run pytest src/tests/test_repositories/test_series_find_by_title.py -v
```

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/src/module/repositories/series.py \
        backend/src/tests/test_repositories/test_series_find_by_title.py
git commit -m "feat: SeriesRepository.find_by_canonical_title for duplicate detection"
```

---

## Task 2: pending_torrent_enrichment repository helpers

**Files:**
- Create or extend: `backend/src/module/services/pending_enrichment.py`
- Create: `backend/src/tests/test_services/test_pending_enrichment.py`

**Background:** The `pending_torrent_enrichment` table was added in migration 0004. We need a thin service layer for: enqueue, list, mark-attempted (increment `attempt_count`, set `last_error`), delete-on-success.

- [ ] **Step 1: Write tests**

```python
# backend/src/tests/test_services/test_pending_enrichment.py
import pytest
from module.services.pending_enrichment import PendingEnrichmentService


@pytest.mark.integration
async def test_enqueue_then_list(db_session):
    svc = PendingEnrichmentService(db_session)
    await svc.enqueue(
        info_hash="hash-1",
        raw_name="[Group] Title",
        homepage="https://mikanani.me/Home/Episode/hash-1",
        url="magnet:?...",
        rss_id=1,
        published_at=None,
    )
    pending = await svc.list_pending()
    assert len(pending) == 1
    assert pending[0].info_hash == "hash-1"


@pytest.mark.integration
async def test_enqueue_idempotent_on_same_hash(db_session):
    svc = PendingEnrichmentService(db_session)
    await svc.enqueue(info_hash="h", raw_name="x", homepage=None,
                      url="u", rss_id=1, published_at=None)
    await svc.enqueue(info_hash="h", raw_name="x", homepage=None,
                      url="u", rss_id=1, published_at=None)
    pending = await svc.list_pending()
    assert len(pending) == 1


@pytest.mark.integration
async def test_mark_attempted_increments_count(db_session):
    svc = PendingEnrichmentService(db_session)
    await svc.enqueue(info_hash="h", raw_name="x", homepage=None,
                      url="u", rss_id=1, published_at=None)
    await svc.mark_attempted("h", error="503 Service Unavailable")
    pending = await svc.list_pending()
    assert pending[0].attempt_count == 1
    assert pending[0].last_error == "503 Service Unavailable"


@pytest.mark.integration
async def test_remove_by_hash(db_session):
    svc = PendingEnrichmentService(db_session)
    await svc.enqueue(info_hash="h", raw_name="x", homepage=None,
                      url="u", rss_id=1, published_at=None)
    await svc.remove("h")
    assert await svc.list_pending() == []
```

- [ ] **Step 2: Implement service**

```python
# backend/src/module/services/pending_enrichment.py
"""Service layer for pending_torrent_enrichment queue."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.pending_enrichment import PendingTorrentEnrichment


class PendingEnrichmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue(
        self,
        *,
        info_hash: str,
        raw_name: str,
        homepage: Optional[str],
        url: str,
        rss_id: int,
        published_at: Optional[datetime],
    ) -> None:
        """Insert or ignore (info_hash is the primary key). Idempotent."""
        stmt = sqlite_insert(PendingTorrentEnrichment).values(
            info_hash=info_hash,
            raw_name=raw_name,
            homepage=homepage,
            url=url,
            rss_id=rss_id,
            published_at=published_at,
            first_seen_at=datetime.utcnow(),
            attempt_count=0,
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["info_hash"])
        await self.session.execute(stmt)

    async def list_pending(self) -> list[PendingTorrentEnrichment]:
        result = await self.session.execute(
            select(PendingTorrentEnrichment).order_by(
                PendingTorrentEnrichment.first_seen_at
            )
        )
        return list(result.scalars().all())

    async def mark_attempted(self, info_hash: str, *, error: str) -> None:
        await self.session.execute(
            update(PendingTorrentEnrichment)
            .where(PendingTorrentEnrichment.info_hash == info_hash)
            .values(
                attempt_count=PendingTorrentEnrichment.attempt_count + 1,
                last_error=error,
                last_attempt_at=datetime.utcnow(),
            )
        )

    async def remove(self, info_hash: str) -> None:
        await self.session.execute(
            delete(PendingTorrentEnrichment).where(
                PendingTorrentEnrichment.info_hash == info_hash
            )
        )
```

- [ ] **Step 3: Pass + commit**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
uv run pytest src/tests/test_services/test_pending_enrichment.py -v
```

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/src/module/services/pending_enrichment.py \
        backend/src/tests/test_services/test_pending_enrichment.py
git commit -m "feat: PendingEnrichmentService — idempotent queue for unresolvable torrents"
```

---

## Task 3: RssPipeline orchestrator

**Files:**
- Create: `backend/src/module/services/pipeline/__init__.py` (empty)
- Create: `backend/src/module/services/pipeline/rss_pipeline.py`
- Create: `backend/src/tests/test_services/test_rss_pipeline.py`

**Background:** This is the chokepoint that owns concurrency + Mikan resolution + enqueueing. Per spec §8.3 + §9.1:

```
for each rss_id:
  lock = await RssLockRegistry.try_acquire(rss_id)
  if lock is None: log "skip", continue
  try:
    feed_items = await fetch_rss(rss_id)
    for item in feed_items:
      mikan_ref = await MikanResolver.resolve(item.homepage)
      if mikan_ref is None:
        await PendingEnrichmentService.enqueue(item)
        continue
      resolved_series = await IdentityResolver.resolve(mikan_ref, ...)
      torrent = await TorrentRepository.create({... mikan_bangumi_id, mikan_subgroup_id ...})
      bangumi = await BangumiRepository.get_or_create_for_series(resolved_series, item.rss_id)
  finally:
    lock.release()
```

The pipeline does NOT trigger downloads — that stays in the existing collector flow which the pipeline calls when bangumi creation succeeds.

- [ ] **Step 1: Write the orchestrator skeleton + happy-path test**

```python
# backend/src/module/services/pipeline/rss_pipeline.py
"""End-to-end RSS feed processor: lock → fetch → resolve → create | enqueue."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from module.concurrency.rss_lock_registry import RssLockRegistry
from module.mikan.resolver import MikanResolver
from module.services.identity_resolver import resolve_series_for_rss
from module.services.pending_enrichment import PendingEnrichmentService
from module.repositories.bangumi import BangumiRepository
from module.repositories.torrent import TorrentRepository

logger = logging.getLogger(__name__)


@dataclass
class FeedItem:
    info_hash: str
    raw_name: str
    homepage: Optional[str]
    url: str
    rss_id: int
    published_at: Optional[object]
    rss_link: str
    parsed_title: str
    parsed_season: int
    parsed_poster: Optional[str]


@dataclass
class PipelineResult:
    skipped_locked: bool = False
    items_seen: int = 0
    items_enqueued: int = 0
    items_resolved: int = 0
    items_failed: int = 0


class RssPipeline:
    def __init__(
        self,
        session: AsyncSession,
        *,
        lock_registry: RssLockRegistry,
        mikan_resolver: MikanResolver,
    ) -> None:
        self.session = session
        self.lock_registry = lock_registry
        self.mikan_resolver = mikan_resolver
        self._pending = PendingEnrichmentService(session)
        self._bangumi_repo = BangumiRepository(session)
        self._torrent_repo = TorrentRepository(session)

    async def run_for_feed(
        self, rss_id: int, items: list[FeedItem]
    ) -> PipelineResult:
        result = PipelineResult()

        lock = await self.lock_registry.try_acquire(rss_id)
        if lock is None:
            logger.info("skip rss_id=%d (lock held)", rss_id)
            result.skipped_locked = True
            return result

        try:
            for item in items:
                result.items_seen += 1
                try:
                    await self._process_item(item)
                    result.items_resolved += 1
                except _Pending:
                    result.items_enqueued += 1
                except Exception as exc:
                    logger.exception("pipeline item failed: %s", exc)
                    result.items_failed += 1
            await self.session.commit()
        finally:
            lock.release()
        return result

    async def _process_item(self, item: FeedItem) -> None:
        if item.homepage is None:
            await self._pending.enqueue(
                info_hash=item.info_hash, raw_name=item.raw_name,
                homepage=None, url=item.url, rss_id=item.rss_id,
                published_at=item.published_at,
            )
            raise _Pending

        mikan_ref = await self.mikan_resolver.resolve(item.homepage)
        if mikan_ref is None:
            await self._pending.enqueue(
                info_hash=item.info_hash, raw_name=item.raw_name,
                homepage=item.homepage, url=item.url, rss_id=item.rss_id,
                published_at=item.published_at,
            )
            raise _Pending

        resolved = await resolve_series_for_rss(
            session=self.session,
            rss_link=item.rss_link,
            parsed_title=item.parsed_title,
            parsed_season=item.parsed_season,
            parsed_poster=item.parsed_poster,
        )

        existing_bangumi = await self._bangumi_repo.get_by_series_and_subgroup(
            resolved.series.id, mikan_ref.mikan_subgroup_id
        )
        if existing_bangumi is None:
            existing_bangumi = await self._bangumi_repo.create({
                "series_id": resolved.series.id,
                "mikan_subgroup_id": mikan_ref.mikan_subgroup_id,
                "rss_id": item.rss_id,
                "rss_link": item.rss_link,
                "group_name": "Unknown",
                "active": True,
            })

        await self._torrent_repo.create({
            "bangumi_id": existing_bangumi.id,
            "rss_id": item.rss_id,
            "name": item.raw_name,
            "url": item.url,
            "hash": item.info_hash,
            "homepage": item.homepage,
            "mikan_bangumi_id": mikan_ref.mikan_bangumi_id,
            "mikan_subgroup_id": mikan_ref.mikan_subgroup_id,
        })

        await self._pending.remove(item.info_hash)


class _Pending(Exception):
    """Raised internally to signal an item went to the pending queue."""
```

```python
# backend/src/tests/test_services/test_rss_pipeline.py
"""RssPipeline orchestration tests."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from module.services.pipeline.rss_pipeline import (
    FeedItem, PipelineResult, RssPipeline,
)
from module.mikan.parser import MikanRef


def _item(info_hash="h", homepage="https://mikanani.me/Home/Episode/h"):
    return FeedItem(
        info_hash=info_hash, raw_name="[G] T", homepage=homepage,
        url="magnet:?", rss_id=1, published_at=None,
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=99&subgroupid=7",
        parsed_title="Show", parsed_season=1, parsed_poster=None,
    )


@pytest.mark.integration
async def test_skip_when_lock_held(db_session):
    locks = MagicMock()
    locks.try_acquire = AsyncMock(return_value=None)
    resolver = MagicMock()

    pipeline = RssPipeline(db_session, lock_registry=locks, mikan_resolver=resolver)
    result = await pipeline.run_for_feed(rss_id=1, items=[_item()])

    assert result.skipped_locked is True
    resolver.resolve.assert_not_called()


@pytest.mark.integration
async def test_unresolvable_homepage_enqueues(db_session):
    lock = MagicMock()
    locks = MagicMock()
    locks.try_acquire = AsyncMock(return_value=lock)
    resolver = MagicMock()
    resolver.resolve = AsyncMock(return_value=None)

    pipeline = RssPipeline(db_session, lock_registry=locks, mikan_resolver=resolver)
    items = [_item(info_hash="h1"), _item(info_hash="h2")]
    result = await pipeline.run_for_feed(rss_id=1, items=items)

    assert result.items_enqueued == 2
    assert result.items_resolved == 0
    lock.release.assert_called_once()


@pytest.mark.integration
async def test_resolved_item_creates_bangumi_and_torrent(db_session):
    lock = MagicMock()
    locks = MagicMock()
    locks.try_acquire = AsyncMock(return_value=lock)
    resolver = MagicMock()
    resolver.resolve = AsyncMock(return_value=MikanRef(
        mikan_bangumi_id=99, mikan_subgroup_id=7,
        canonical_title="Show", poster_url=None,
    ))

    pipeline = RssPipeline(db_session, lock_registry=locks, mikan_resolver=resolver)
    result = await pipeline.run_for_feed(rss_id=1, items=[_item()])

    assert result.items_resolved == 1
    assert result.items_enqueued == 0
```

- [ ] **Step 2: Run + iterate**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
uv run pytest src/tests/test_services/test_rss_pipeline.py -v
```

Adjust import paths and constructor signatures as needed (verify `RssLockRegistry` and `MikanResolver` actual locations / signatures by reading the existing files).

- [ ] **Step 3: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/src/module/services/pipeline/ \
        backend/src/tests/test_services/test_rss_pipeline.py
git commit -m "feat: RssPipeline orchestrator wires lock → mikan → identity → enqueue"
```

---

## Task 4: enrichment_retry scheduled job

**Files:**
- Create: `backend/src/module/scheduler/jobs/enrichment_retry.py`
- Modify: `backend/src/module/scheduler/scheduler.py` (or wherever jobs register)
- Create: `backend/src/tests/test_scheduler/test_enrichment_retry.py`

**Background:** The `pending_torrent_enrichment` queue needs a periodic drain. Each tick:
1. List pending items.
2. For each: re-fetch the homepage via MikanResolver; if it now resolves, route through the same pipeline as fresh items; if not, increment attempt_count.

- [ ] **Step 1: Test**

```python
# backend/src/tests/test_scheduler/test_enrichment_retry.py
from unittest.mock import AsyncMock, MagicMock
import pytest

from module.scheduler.jobs.enrichment_retry import drain_pending


@pytest.mark.integration
async def test_drain_calls_resolver_for_each_pending_item(db_session, monkeypatch):
    from module.services.pending_enrichment import PendingEnrichmentService
    svc = PendingEnrichmentService(db_session)
    await svc.enqueue(info_hash="h1", raw_name="x", homepage="u1",
                      url="m", rss_id=1, published_at=None)
    await svc.enqueue(info_hash="h2", raw_name="y", homepage="u2",
                      url="m", rss_id=1, published_at=None)
    await db_session.commit()

    resolver = MagicMock()
    resolver.resolve = AsyncMock(return_value=None)  # both stay pending

    summary = await drain_pending(db_session, mikan_resolver=resolver)

    assert summary["attempted"] == 2
    assert summary["resolved"] == 0
    assert summary["still_pending"] == 2
    assert resolver.resolve.await_count == 2
```

- [ ] **Step 2: Implement**

```python
# backend/src/module/scheduler/jobs/enrichment_retry.py
"""Scheduled job: drain pending_torrent_enrichment via MikanResolver."""
from __future__ import annotations

import logging
from typing import Any

from module.services.pending_enrichment import PendingEnrichmentService

logger = logging.getLogger(__name__)


async def drain_pending(session, *, mikan_resolver) -> dict[str, int]:
    svc = PendingEnrichmentService(session)
    pending = await svc.list_pending()
    summary = {"attempted": 0, "resolved": 0, "still_pending": 0}

    for item in pending:
        summary["attempted"] += 1
        if item.homepage is None:
            await svc.mark_attempted(
                item.info_hash, error="no homepage url"
            )
            summary["still_pending"] += 1
            continue
        try:
            ref = await mikan_resolver.resolve(item.homepage)
        except Exception as exc:
            await svc.mark_attempted(item.info_hash, error=f"{type(exc).__name__}: {exc}")
            summary["still_pending"] += 1
            continue
        if ref is None:
            await svc.mark_attempted(item.info_hash, error="resolver returned None")
            summary["still_pending"] += 1
            continue
        # If we get here, the resolver succeeded — but creating the torrent
        # row requires more pipeline state we don't have here. Plan 06 will
        # connect drain_pending to the full RssPipeline. For now, just keep
        # the row queued and bump its attempt_count so it's visible.
        await svc.mark_attempted(item.info_hash, error="(resolved; awaiting pipeline integration)")
        summary["resolved"] += 1

    await session.commit()
    return summary
```

(The plan acknowledges drain_pending's full pipeline integration is iterative. Get the polling + status reporting working first; subsequent tasks tighten the loop.)

- [ ] **Step 3: Wire into scheduler**

In `scheduler/scheduler.py` (or wherever `rss_refresh` is registered), add an analogous registration for `enrichment_retry` with config-driven interval (default 300s).

- [ ] **Step 4: Pass + commit**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
uv run pytest src/tests/test_scheduler/test_enrichment_retry.py -v
```

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/src/module/scheduler/jobs/enrichment_retry.py \
        backend/src/module/scheduler/scheduler.py \
        backend/src/tests/test_scheduler/test_enrichment_retry.py
git commit -m "feat: enrichment_retry scheduled job drains pending queue"
```

---

## Task 5: Wire RssPipeline into rss_refresh job

**Files:**
- Modify: `backend/src/module/scheduler/jobs/rss_refresh.py`
- Modify: `backend/src/tests/test_scheduler/test_rss_refresh*.py` (if any)

**Background:** Replace the existing rss_refresh body (which calls collector / rss_engine directly) with a single delegation to `RssPipeline.run_for_feed(rss_id, items)`. The job is now a thin loop over RSS items.

- [ ] **Step 1: Read the existing rss_refresh**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
cat src/module/scheduler/jobs/rss_refresh.py
```

Identify how it currently fetches items, calls collector / rss_engine, and stores results. Map each section to the new RssPipeline interface.

- [ ] **Step 2: Rewrite to delegate**

The new shape:

```python
async def rss_refresh(...) -> None:
    async with AsyncSessionLocal() as session:
        registry = get_or_create_lock_registry()
        mikan_resolver = get_or_create_mikan_resolver()
        pipeline = RssPipeline(session, lock_registry=registry, mikan_resolver=mikan_resolver)

        for rss in await RSSItemRepository(session).get_active():
            items = await fetch_rss_items(rss)  # adapter for existing fetch
            result = await pipeline.run_for_feed(rss.id, items=[
                _to_feed_item(rss, raw) for raw in items
            ])
            log_summary(rss.id, result)
```

`_to_feed_item` adapts the existing parser output to the `FeedItem` dataclass.

- [ ] **Step 3: Run rss_refresh tests + e2e**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
uv run pytest src/tests/test_scheduler/ src/tests/test_e2e/ -q
```

If e2e breaks because the test fixtures expect direct rss_engine behavior, update them to match the new pipeline path.

- [ ] **Step 4: Commit**

```
git commit -m "refactor: rss_refresh delegates to RssPipeline"
```

---

## Task 6: API — `/api/v1/series/*`

**Files:**
- Create: `backend/src/module/api/v1/series.py`
- Modify: `backend/src/module/api/v1/__init__.py` (register router)
- Create: `backend/src/tests/test_api_contract/test_series.py`

**Endpoints:**
- `GET /api/v1/series/` → list (paginated)
- `GET /api/v1/series/{id}` → detail (includes active bangumi summary)
- `PATCH /api/v1/series/{id}` → update `canonical_title`, `root_path`, `default_filter`, `default_offset`

- [ ] **Step 1: Write contract tests**

```python
# backend/src/tests/test_api_contract/test_series.py
import pytest


@pytest.mark.integration
async def test_list_series_returns_array(authed_client, db_session):
    from module.domain.models.series import Series
    s = Series(canonical_title="A", normalized_title="a", season=1,
               root_path="/p", pending_review=False)
    db_session.add(s)
    await db_session.commit()

    resp = await authed_client.get("/api/v1/series/")
    assert resp.status_code == 200
    body = resp.json()
    assert any(item["canonical_title"] == "A" for item in body["items"])


@pytest.mark.integration
async def test_get_series_detail(authed_client, db_session):
    from module.domain.models.series import Series
    s = Series(canonical_title="B", normalized_title="b", season=1,
               root_path="/p", pending_review=False)
    db_session.add(s)
    await db_session.commit()

    resp = await authed_client.get(f"/api/v1/series/{s.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["canonical_title"] == "B"


@pytest.mark.integration
async def test_patch_series_updates_root_path(authed_client, db_session):
    from module.domain.models.series import Series
    s = Series(canonical_title="C", normalized_title="c", season=1,
               root_path="/old", pending_review=False)
    db_session.add(s)
    await db_session.commit()

    resp = await authed_client.patch(
        f"/api/v1/series/{s.id}", json={"root_path": "/new"},
    )
    assert resp.status_code == 200

    await db_session.refresh(s)
    assert s.root_path == "/new"
```

- [ ] **Step 2: Implement router**

```python
# backend/src/module/api/v1/series.py
"""/api/v1/series/* endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from module.database.engine import get_session
from module.repositories.series import SeriesRepository

router = APIRouter(prefix="/api/v1/series", tags=["series"])


class SeriesItem(BaseModel):
    id: int
    canonical_title: str
    season: int
    cour_part: Optional[int] = None
    year: Optional[int] = None
    root_path: str
    poster_url: Optional[str] = None
    pending_review: bool


class SeriesList(BaseModel):
    items: list[SeriesItem]
    total: int


class SeriesPatch(BaseModel):
    canonical_title: Optional[str] = None
    root_path: Optional[str] = None
    default_filter: Optional[str] = None
    default_offset: Optional[int] = None
    poster_url: Optional[str] = None


@router.get("/", response_model=SeriesList)
async def list_series(
    limit: int = Query(50, le=200),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    repo = SeriesRepository(session)
    items, total = await repo.list_paginated(limit=limit, offset=offset)
    return SeriesList(
        items=[SeriesItem.model_validate(s, from_attributes=True) for s in items],
        total=total,
    )


@router.get("/{series_id}", response_model=SeriesItem)
async def get_series(series_id: int, session: AsyncSession = Depends(get_session)):
    repo = SeriesRepository(session)
    s = await repo.get_by_id(series_id)
    if s is None:
        raise HTTPException(404, "series not found")
    return SeriesItem.model_validate(s, from_attributes=True)


@router.patch("/{series_id}", response_model=SeriesItem)
async def patch_series(
    series_id: int,
    body: SeriesPatch,
    session: AsyncSession = Depends(get_session),
):
    repo = SeriesRepository(session)
    s = await repo.get_by_id(series_id)
    if s is None:
        raise HTTPException(404, "series not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    await session.commit()
    return SeriesItem.model_validate(s, from_attributes=True)
```

If `SeriesRepository.list_paginated` doesn't exist, add a thin wrapper:
```python
async def list_paginated(self, *, limit: int, offset: int) -> tuple[list[Series], int]:
    total = (await self.session.execute(select(func.count(Series.id)))).scalar()
    rows = (await self.session.execute(
        select(Series).order_by(Series.canonical_title).limit(limit).offset(offset)
    )).scalars().all()
    return list(rows), int(total or 0)
```

- [ ] **Step 3: Register router**

In `backend/src/module/api/v1/__init__.py` (or wherever the v1 routers are aggregated), import and include `series.router`.

- [ ] **Step 4: Pass + commit**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
uv run pytest src/tests/test_api_contract/test_series.py -v
```

```
git commit -m "feat: /api/v1/series CRUD endpoints"
```

---

## Task 7: API — `/api/v1/bangumi/merge` + `/api/v1/merge-history/*`

**Files:**
- Create: `backend/src/module/api/v1/merge.py`
- Modify: `backend/src/module/api/v1/__init__.py`
- Create: `backend/src/tests/test_api_contract/test_merge.py`

**Endpoints:**
- `POST /api/v1/bangumi/merge` body `{"winner_id": int, "loser_id": int, "reason": str}` → calls `BangumiMergeService.merge()`.
- `GET /api/v1/merge-history/` → list (paginated).
- `POST /api/v1/merge-history/{id}/undo` → restore loser, move torrents back, mark history `undone_at`.

- [ ] **Step 1: Tests**

```python
# backend/src/tests/test_api_contract/test_merge.py
import pytest


@pytest.mark.integration
async def test_merge_two_bangumi(authed_client, db_session):
    # Setup: Series + two Bangumi rows
    from module.domain.models.series import Series
    from module.domain.models.bangumi import Bangumi
    s = Series(canonical_title="X", normalized_title="x", season=1,
               root_path="/p", pending_review=False)
    db_session.add(s)
    await db_session.flush()
    b1 = Bangumi(series_id=s.id, mikan_subgroup_id=1, group_name="A",
                 rss_link="", active=True)
    b2 = Bangumi(series_id=s.id, mikan_subgroup_id=2, group_name="B",
                 rss_link="", active=True)
    db_session.add_all([b1, b2])
    await db_session.commit()

    resp = await authed_client.post(
        "/api/v1/bangumi/merge",
        json={"winner_id": b1.id, "loser_id": b2.id, "reason": "manual_test"},
    )
    assert resp.status_code == 200, resp.json()

    await db_session.refresh(b2)
    assert b2.deleted is True

    history_resp = await authed_client.get("/api/v1/merge-history/")
    assert any(h["loser_bangumi_id"] == b2.id for h in history_resp.json()["items"])


@pytest.mark.integration
async def test_undo_restores_loser(authed_client, db_session):
    # ... after a merge, POST /merge-history/{id}/undo and verify loser.deleted == False
    ...
```

- [ ] **Step 2: Implement router**

```python
# backend/src/module/api/v1/merge.py
"""Manual bangumi merge + merge-history endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from module.database.engine import get_session
from module.repositories.merge_history import BangumiMergeHistoryRepository
from module.services.bangumi_merge import BangumiMergeService

router = APIRouter(tags=["merge"])


class MergeRequest(BaseModel):
    winner_id: int
    loser_id: int
    reason: str = "manual"


class MergeResponse(BaseModel):
    history_id: int
    winner_id: int
    loser_id: int


@router.post("/api/v1/bangumi/merge", response_model=MergeResponse)
async def merge_bangumi(
    body: MergeRequest,
    session: AsyncSession = Depends(get_session),
    user: object = Depends(...),  # use the existing auth dependency
):
    svc = BangumiMergeService(session)
    try:
        history = await svc.merge(
            winner_id=body.winner_id,
            loser_id=body.loser_id,
            merge_reason=body.reason,
            merged_by=getattr(user, "username", "api"),
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    await session.commit()
    return MergeResponse(
        history_id=history.id,
        winner_id=body.winner_id,
        loser_id=body.loser_id,
    )


@router.get("/api/v1/merge-history/")
async def list_merge_history(
    limit: int = 50, offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    repo = BangumiMergeHistoryRepository(session)
    items, total = await repo.list_paginated(limit=limit, offset=offset)
    return {
        "items": [
            {
                "id": h.id,
                "winner_bangumi_id": h.winner_bangumi_id,
                "loser_bangumi_id": h.loser_bangumi_id,
                "merge_reason": h.merge_reason,
                "merged_at": h.merged_at.isoformat(),
                "undone_at": h.undone_at.isoformat() if h.undone_at else None,
            }
            for h in items
        ],
        "total": total,
    }


@router.post("/api/v1/merge-history/{history_id}/undo")
async def undo_merge(
    history_id: int,
    session: AsyncSession = Depends(get_session),
    user: object = Depends(...),
):
    svc = BangumiMergeService(session)
    try:
        await svc.undo(history_id=history_id, undone_by=getattr(user, "username", "api"))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    await session.commit()
    return {"undone": True}
```

If `BangumiMergeService.undo()` doesn't exist yet, add it inside this task. The undo body:
1. Load history row; if `undone_at` is not None, raise `ValueError("already undone")`.
2. Resurrect loser: `loser.deleted = False; loser.active = False` (don't auto-reactivate — user may need to choose).
3. Move torrents back: for each torrent currently on `winner_id` whose hash is in `loser_snapshot["moved_torrent_ids"]`, set `bangumi_id = loser_id`.
4. Re-create dropped torrents from `dropped_torrents` snapshot.
5. Set `history.undone_at = datetime.utcnow()`, `history.undone_by = undone_by`.

- [ ] **Step 3: Pass + commit**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
uv run pytest src/tests/test_api_contract/test_merge.py -v
```

```
git commit -m "feat: /api/v1/bangumi/merge + /api/v1/merge-history/* endpoints"
```

---

## Task 8: API — `/api/v1/pending-resolution/*`

**Files:**
- Create: `backend/src/module/api/v1/pending_resolution.py`
- Modify: `backend/src/module/api/v1/__init__.py`
- Create: `backend/src/tests/test_api_contract/test_pending_resolution.py`

**Endpoints:**
- `GET /api/v1/pending-resolution/` → list pending items with attempt_count, last_error, etc.
- `POST /api/v1/pending-resolution/{info_hash}/retry` → run a single resolve attempt now.

- [ ] **Step 1: Tests**

```python
# backend/src/tests/test_api_contract/test_pending_resolution.py
import pytest


@pytest.mark.integration
async def test_list_pending(authed_client, db_session):
    from module.services.pending_enrichment import PendingEnrichmentService
    svc = PendingEnrichmentService(db_session)
    await svc.enqueue(info_hash="h1", raw_name="x",
                      homepage="u", url="m", rss_id=1, published_at=None)
    await db_session.commit()

    resp = await authed_client.get("/api/v1/pending-resolution/")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(i["info_hash"] == "h1" for i in items)
```

- [ ] **Step 2: Implement router**

Pattern: load `PendingEnrichmentService.list_pending()`, return JSON. The retry endpoint instantiates `MikanResolver` and runs a single resolve.

- [ ] **Step 3: Pass + commit**

---

## Task 9: API — `/api/v1/health/mikan` + `/api/v1/health/concurrency`

**Files:**
- Create: `backend/src/module/api/v1/health.py`
- Modify: `backend/src/module/api/v1/__init__.py`
- Create: `backend/src/tests/test_api_contract/test_health.py`

**Background:** Per spec §12.1 + §12.2:

```text
GET /api/v1/health/mikan
→ {
    "status": "ok" | "degraded" | "down",
    "pending_count": <int>,
    "last_success_at": "<iso>",
    "hours_since_last_success": <float>,
    "consecutive_failures": <int>,
    "pending_items": [...]
  }

GET /api/v1/health/concurrency
→ {
    "rss_locks": [...],
    "rate_limiters": {...}
  }
```

State sources: `MikanResolver.health_snapshot()`, `RssLockRegistry.snapshot()`, `RateLimiterRegistry.snapshot()`. If any of these don't exist as methods today, ADD them in this task as part of the implementation.

Status formula:
```
ok        : last_success_at < 1h AND pending_count < 3
degraded  : 1h <= last_success_at < 24h OR pending_count >= 3
down      : last_success_at >= 24h OR consecutive_failures >= 10
```

- [ ] **Step 1: Tests**
- [ ] **Step 2: Implement router + helper snapshot methods on each component**
- [ ] **Step 3: Pass + commit**

---

## Task 10: Re-enable duplicate-by-title check in `add_rss`

**Files:**
- Modify: `backend/src/module/api/v1/rss.py:131` (the `existing_by_title = None` placeholder + dead block)

**Background:** Plan 04 Task 12 disabled this check because `find_by_official_title` was removed and no series-aware replacement existed. Task 1 of this plan added `SeriesRepository.find_by_canonical_title`.

- [ ] **Step 1: Replace placeholder**

At `api/v1/rss.py` line ~131, replace:

```python
# TODO(plan05): re-enable duplicate-by-title check ...
# (placeholder that does nothing)
```

with:

```python
norm, _ = normalize_title(data.official_title)
existing_series = await SeriesRepository(session).find_by_canonical_title(
    data.official_title
)
if existing_series is not None:
    return u_response(ResponseModel(
        msg_en=f"Series '{data.official_title}' already exists (id={existing_series.id})",
        status_code=409,
    ))
```

(Adjust the response shape to match the existing `u_response` / `ResponseModel` style; verify by reading the file context.)

- [ ] **Step 2: Pass + commit**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
uv run pytest src/tests/test_api_contract/test_rss.py -v
```

```
git commit -m "feat: re-enable duplicate-by-title check via SeriesRepository.find_by_canonical_title"
```

---

## Task 11: Drop `@property` shims on `Bangumi`

**Files:**
- Modify: `backend/src/module/domain/models/bangumi.py` — DELETE 5 @property shims
- Modify: ALL callers of `bangumi.official_title`, `.season`, `.year`, `.save_path`, `.poster_link` — rewrite to read through `bangumi.series.*`

**Background:** This is a fan-out cleanup. The shims hide which call sites still need rewriting. Removing them surfaces every caller via `AttributeError`.

The substitution table:
- `bangumi.official_title` → `bangumi.series.canonical_title`
- `bangumi.season` → `bangumi.series.season`
- `bangumi.year` → `bangumi.series.year`
- `bangumi.poster_link` → `bangumi.series.poster_url`
- `bangumi.save_path` → `bangumi.path_override or bangumi.series.root_path`

Callers MUST ensure `bangumi.series` is loaded (via `selectinload`) before accessing it.

- [ ] **Step 1: Inventory**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
grep -rn "bangumi\.official_title\|bangumi\.season\b\|bangumi\.year\|bangumi\.save_path\|bangumi\.poster_link" src/module/ --include="*.py"
```

(Take care with `bangumi.season` — it may match `bangumi.season_raw` or `bangumi.seasons`. Use word boundary.)

- [ ] **Step 2: For each call site, replace with the series-direct read**

Most sites are read-side: log lines, response payloads, search adapters. Each should switch to `bangumi.series.X`. Where the surrounding query doesn't `selectinload(Bangumi.series)`, add it.

The PATCH `/bangumi/update/{bangumi_id}` endpoint already routes writes through `_apply_update_dict`'s series delegations (Plan 04 Task 12 fix). After Task 11, `_apply_update_dict` can be SIMPLIFIED — drop the legacy-key handlers, keep only direct-column writes.

- [ ] **Step 3: Drop the shims**

In `backend/src/module/domain/models/bangumi.py`, DELETE these methods:
```python
@property
def official_title(self): ...
@property
def season(self): ...
@property
def year(self): ...
@property
def save_path(self): ...
@property
def poster_link(self): ...
```

- [ ] **Step 4: Drop the legacy field handlers in BangumiRepository**

Remove from `repositories/bangumi.py`:
- `_DROPPED_COLUMNS` frozenset (no callers should pass legacy keys anymore)
- `_SILENT_DROP_ON_WRITE` frozenset
- All `_apply_update_dict` branches that handle `official_title`, `season`, `year`, `title_raw`, `season_raw`, `save_path`, `poster_link`. Keep only the no-op pass-through.

`create()` and `update_simple()` become pure direct-column operations.

- [ ] **Step 5: Run full sweep — expect cascade failures**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
uv run pytest -q 2>&1 | tail -30
```

Iterate. Each failure points at a missed call site. Repeat Step 2 for each. Goal: full sweep stays green.

- [ ] **Step 6: Commit**

```
git commit -m "refactor: drop Bangumi compat shims; all readers go through Series"
```

---

## Task 12: Sweep remaining `TODO(plan05)` markers

**Files:** various — driven by grep.

- [ ] **Step 1: Inventory**

```bash
cd /Users/tk/ws/Auto_Bangumi
grep -rn "TODO(plan05)" backend/src/ --include="*.py"
```

Expected hits (after Task 11 removed several): 0–3.

- [ ] **Step 2: Resolve each**

For each remaining marker:
- If the cited work is already done by an earlier Plan 05 task, just delete the marker.
- If it's truly unaddressed, do the minimal fix.

- [ ] **Step 3: Verify zero remaining**

```bash
grep -rn "TODO(plan05)" backend/src/ --include="*.py"
```

Expected: zero matches.

- [ ] **Step 4: Commit**

```
git commit -m "chore: clear remaining TODO(plan05) markers"
```

---

## Task 13: Full sanity pass

**Files:** None — verification only.

- [ ] **Step 1: Full test sweep**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
uv run pytest -q 2>&1 | tail -5
```

Expected: 1607+ passed, 0 failed.

- [ ] **Step 2: alembic up/down/up clean**

```bash
TMP=$(mktemp -d)
cd /Users/tk/ws/Auto_Bangumi/backend
AB_ALEMBIC_DB_URL="sqlite+aiosqlite:///$TMP/x.db" uv run alembic upgrade head
AB_ALEMBIC_DB_URL="sqlite+aiosqlite:///$TMP/x.db" uv run alembic downgrade base
AB_ALEMBIC_DB_URL="sqlite+aiosqlite:///$TMP/x.db" uv run alembic upgrade head
```

- [ ] **Step 3: Manual import check**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
uv run python -c "
from module.api.v1 import series, merge, pending_resolution, health
from module.services.pipeline.rss_pipeline import RssPipeline
from module.services.pending_enrichment import PendingEnrichmentService
from module.scheduler.jobs.enrichment_retry import drain_pending
print('all new modules import ok')
"
```

- [ ] **Step 4: Final API surface check**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend
uv run python -c "
from main import app
for route in app.routes:
    if hasattr(route, 'path') and route.path.startswith('/api/v1'):
        print(getattr(route, 'methods', set()), route.path)
" | sort
```

Verify these are present:
- `GET /api/v1/series/`
- `GET /api/v1/series/{id}`
- `PATCH /api/v1/series/{id}`
- `POST /api/v1/bangumi/merge`
- `GET /api/v1/merge-history/`
- `POST /api/v1/merge-history/{id}/undo`
- `GET /api/v1/pending-resolution/`
- `POST /api/v1/pending-resolution/{info_hash}/retry`
- `GET /api/v1/health/mikan`
- `GET /api/v1/health/concurrency`

---

## Self-Review Checklist (controller runs after Task 13)

1. **Spec coverage**
   - §8.3 阻塞策略 (pending_torrent_enrichment): Tasks 2 + 3 + 4
   - §9.1 RssLockRegistry skip-if-held: Task 3 + 5
   - §11.2 atomic merge endpoint: Task 7
   - §11.4 merge-history undo: Task 7
   - §12.1 Health API: Task 9
   - §14.1 + §14.2 API rewrite: Tasks 6 + 7 + 8 + 9

2. **Out of scope (deferred)**
   - WebUI pages (`/series`, `/pending-resolution`, `/merge-history`)
   - Dashboard banner (Mikan health, rename conflicts)
   - Rate-limiter degradation indicator UI

3. **Type consistency**
   - `RssPipeline.run_for_feed` signature consistent across Tasks 3, 4, 5
   - `PendingEnrichmentService` API consistent across Tasks 2, 3, 4, 8
   - `BangumiMergeService.merge` / `.undo` signature consistent across Tasks 7 and Plan 04 Task 6

4. **Cleanup verification**
   - Zero `TODO(plan05)` markers remain (Task 12)
   - Zero `@property` shims on `Bangumi` (Task 11)
   - `_DROPPED_COLUMNS` / `_SILENT_DROP_ON_WRITE` removed from `BangumiRepository` (Task 11)

5. **Migration linearity**
   - 0001 → 0008 unchanged; this plan adds NO new migrations.
