# Bangumi Schema Migration + Merge Pipeline + Rename Refactor (Phase 04)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the new bangumi identity layer end-to-end: backfill `series_id` for every existing bangumi/torrent, auto-merge known production duplicates, drop the legacy bangumi columns, and switch the rename pipeline to series-derived paths/titles with `active`-bangumi gating + rename-conflict detection.

**Architecture:**
- Three-stage migration. Stage A (0006) fixes the Series fallback constraint (partial WHERE `mikan_bangumi_id IS NULL`) so cross-source Tier-3 inserts stop conflicting. Stage B (0007) adds *additive* nullable columns to bangumi + torrent so backfill can run without breaking the live ORM. Stage C (0008) is the destructive lockdown — drop legacy bangumi columns, make `series_id` NOT NULL, install partial UNIQUE constraints.
- Backfill is split from migrations: `scripts/backfill_series.py` walks every bangumi, extracts `mikan_bangumi_id`/`mikan_subgroup_id` from `rss_link` (regex), `get_or_create`s a Series, links the bangumi, and does the same for every torrent (via homepage). Idempotent.
- Auto-merge is split from backfill: `scripts/migrate_duplicates.py --dry-run|--execute` finds duplicate `(series_id, mikan_subgroup_id)` rows post-backfill, applies winner rules, and calls a single `BangumiMergeService.merge()` transaction that moves torrents, soft-deletes the loser, and writes `bangumi_merge_history`.
- Renamer is rewritten to drive paths from `series.root_path` (with optional `bangumi.path_override`), filenames from `series.canonical_title`, season number from `series.season`, with `bangumi.active=true` filter and a rename-conflict detector that surfaces warnings without aborting.
- Compat strategy for downstream callers (API routes, search, poster, etc.): `Bangumi` gains a SQLAlchemy `series` relationship plus thin `@property` accessors (`official_title`, `season`, `year`, `save_path`, `poster_link`) that delegate to the Series. Plan 05 rewrites those routes to use Series directly and removes the shims.

**Tech Stack:** SQLAlchemy 2.0 async + aiosqlite, Alembic with `render_as_batch=True`, OpenCC (already a dep), pytest-asyncio, pytest-httpx.

**Out of scope (covered later):**
- API route rewrite (`/api/v1/series/*`, `/api/v1/bangumi/merge`, `/api/v1/pending-resolution`, `/api/v1/health/*`) — Plan 05.
- WebUI pages and Dashboard banner — Plan 05.
- Wiring `MikanResolver`, `IdentityResolver`, `RssLockRegistry`, `pending_torrent_enrichment` into the live RSS refresh job — Plan 05.

---

## File Map

### Created
- `backend/alembic/versions/0006_series_fallback_partial.py` — convert `uq_series_fallback` and `uq_series_fallback_null_cour` to partial constraints scoped to non-Mikan rows.
- `backend/alembic/versions/0007_add_bangumi_series_link.py` — additive: bangumi gets `series_id` (nullable FK), `mikan_subgroup_id`, `active`, `path_override`, `observed_groups`; torrent gets `mikan_bangumi_id`, `mikan_subgroup_id`.
- `backend/alembic/versions/0008_lockdown_bangumi_identity.py` — destructive: drop legacy bangumi columns + composite UNIQUE; add partial UNIQUE constraints; make `series_id` NOT NULL.
- `backend/scripts/__init__.py` — package marker.
- `backend/scripts/backfill_series.py` — one-shot CLI that links every bangumi+torrent to a Series.
- `backend/scripts/migrate_duplicates.py` — `--dry-run|--execute` CLI that auto-merges duplicate bangumi via `BangumiMergeService`.
- `backend/src/module/services/bangumi_merge.py` — `BangumiMergeService.merge()` atomic transaction.
- `backend/src/tests/test_services/test_bangumi_merge.py` — merge service tests.
- `backend/src/tests/test_scripts/__init__.py`
- `backend/src/tests/test_scripts/test_backfill_series.py` — unit + integration tests for backfill CLI.
- `backend/src/tests/test_scripts/test_migrate_duplicates.py` — unit + integration tests for duplicate migration CLI.
- `backend/src/tests/test_migrations/test_0006_series_fallback.py` — verifies partial constraint behavior.
- `backend/src/tests/test_migrations/test_0007_add_bangumi_series_link.py` — verifies additive columns + downgrade.
- `backend/src/tests/test_migrations/test_0008_lockdown.py` — verifies dropped columns, partial UNIQUEs, NOT NULL.
- `backend/src/tests/test_services/test_renamer_active_filter.py` — renamer with active=false bangumi must skip.
- `backend/src/tests/test_services/test_renamer_conflict.py` — rename target collision is reported, not crashed.

### Modified
- `backend/src/module/domain/models/series.py` — adjust `__table_args__` to mirror migration 0006 (partial constraints).
- `backend/src/module/services/identity_resolver.py:90-129` — drop the Tier-3 mutation workaround; properly create a new pending Series when fallback key collides with a Mikan-sourced row.
- `backend/src/module/domain/models/bangumi.py` — add new columns (post-0007), then drop legacy columns + add `series` relationship + `@property` accessors (post-0008). Both edits live on the same final model file; the migration sequencing mirrors the table state.
- `backend/src/module/domain/models/torrent.py` — add `mikan_bangumi_id`, `mikan_subgroup_id`.
- `backend/src/module/repositories/bangumi.py` — add `get_by_series_and_subgroup`, `get_by_series_and_rss`, `list_by_series`, `deactivate_siblings_in_series`; remove `get_by_composite_key` and the composite-key validation in `create()` (which referenced dropped columns).
- `backend/src/module/repositories/torrent.py` — add `backfill_mikan_ids(torrent_id, mikan_bangumi_id, mikan_subgroup_id)`.
- `backend/src/module/services/renamer.py` — drive `bangumi_name` from `bangumi.series.canonical_title`, season from `bangumi.series.season`, target_save_path from `bangumi.path_override or bangumi.series.root_path`; filter `get_unrenamed()` for `active=true`; detect target-path collisions.
- `backend/src/module/repositories/torrent.py:92-102` — extend `_unrenamed_base_stmt()` with a join on Bangumi where `Bangumi.active == True`.
- `backend/src/module/services/collector.py` — when constructing bangumi rows, populate `series_id` via `IdentityResolver` and stop populating dropped fields; rely on `bangumi.official_title` property when read-side compat is needed.
- `backend/src/module/services/rss_engine.py` — same pattern as collector for any bangumi creation path that touched dropped fields.
- `backend/alembic/env.py:50-63` — extend `_include_object` allow-list for new partial indexes that ship with 0006/0008 (so future autogenerate doesn't drop them).

### Untouched but verified
- `backend/src/tests/test_e2e/` — must remain green throughout. Any e2e test that asserts old columns is broken and will be fixed in Task 14.
- `backend/src/module/api/v1/rss.py`, `backend/src/module/api/v1/bangumi.py` — kept compiling via `Bangumi` `@property` accessors; full rewrite happens in Plan 05.

---

## Conventions

- All test files use `pytest-asyncio` async fixtures via the shared `db_session` fixture in `backend/src/tests/conftest.py`.
- Migration tests use a tmp-path SQLite via `AB_ALEMBIC_DB_URL`.
- Run individual migrations: `cd backend && AB_ALEMBIC_DB_URL=sqlite+aiosqlite:///"$tmp/x.db" uv run alembic upgrade <rev>`.
- Frequent commits: each task ends with a single `feat:` / `fix:` / `chore:` commit.
- Branch is already `refactor/backendv2`; do not create a new branch.

---

## Task 1: Migration 0006 — partial Series fallback constraints

**Files:**
- Create: `backend/alembic/versions/0006_series_fallback_partial.py`
- Create: `backend/src/tests/test_migrations/test_0006_series_fallback.py`
- Modify: `backend/src/module/domain/models/series.py`
- Modify: `backend/alembic/env.py:50-63`

**Background:** Plan 03 Task 10 added a workaround in `IdentityResolver` because both `uq_series_fallback` (UNIQUE on `(normalized_title, season, cour_part)`) and the supplementary `uq_series_fallback_null_cour` partial index apply unconditionally — including to Mikan-sourced rows. Per spec §6.1, those constraints should only guard non-Mikan rows: Mikan-sourced series are identified by `uq_series_mikan` on `mikan_bangumi_id`. This task converts both constraints to partial indexes scoped to `WHERE mikan_bangumi_id IS NULL`, which unblocks the proper Tier-3 create path (Task 2).

- [ ] **Step 1: Write the failing test**

```python
# backend/src/tests/test_migrations/test_0006_series_fallback.py
"""Tests for migration 0006: convert series fallback constraints to partial."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).parent.parent.parent.parent  # backend/


def _run_alembic(target: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "alembic", "upgrade", target],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
    )


@pytest.mark.integration
def test_0006_allows_mikan_series_to_share_fallback_key(tmp_path):
    """After 0006, two Mikan-sourced series may share (normalized_title, season,
    cour_part) because the fallback partial index excludes them."""
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"

    result = _run_alembic("0006_series_fallback_partial", env)
    assert result.returncode == 0, f"upgrade failed:\n{result.stderr}"

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, cour_part, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (1001, 'A', 'foo', 1, NULL, '/p/A', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))
        # Same fallback key, different Mikan id → should NOT collide
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, cour_part, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (1002, 'B', 'foo', 1, NULL, '/p/B', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))


@pytest.mark.integration
def test_0006_still_blocks_duplicate_non_mikan_fallback(tmp_path):
    """Two non-Mikan series with identical fallback key must still collide."""
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0006_series_fallback_partial", env).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, cour_part, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (NULL, 'A', 'foo', 1, NULL, '/p/A', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))
    with engine.begin() as conn:
        with pytest.raises(sa.exc.IntegrityError):
            conn.execute(sa.text(
                "INSERT INTO series (mikan_bangumi_id, canonical_title, "
                "normalized_title, season, cour_part, root_path, default_offset, "
                "pending_review, created_at, updated_at, version) "
                "VALUES (NULL, 'B', 'foo', 1, NULL, '/p/B', 0, 0, "
                "'2026-01-01', '2026-01-01', 1)"
            ))


@pytest.mark.integration
def test_0006_mikan_unique_still_enforced(tmp_path):
    """uq_series_mikan must continue to block duplicate mikan_bangumi_id."""
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0006_series_fallback_partial", env).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, cour_part, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (2001, 'A', 'a', 1, NULL, '/p/A', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))
    with engine.begin() as conn:
        with pytest.raises(sa.exc.IntegrityError):
            conn.execute(sa.text(
                "INSERT INTO series (mikan_bangumi_id, canonical_title, "
                "normalized_title, season, cour_part, root_path, default_offset, "
                "pending_review, created_at, updated_at, version) "
                "VALUES (2001, 'B', 'b', 1, NULL, '/p/B', 0, 0, "
                "'2026-01-01', '2026-01-01', 1)"
            ))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest src/tests/test_migrations/test_0006_series_fallback.py -v`
Expected: FAIL — migration revision `0006_series_fallback_partial` does not exist.

- [ ] **Step 3: Author migration 0006**

Create `backend/alembic/versions/0006_series_fallback_partial.py`:

```python
"""series_fallback_partial

Revision ID: 0006_series_fallback_partial
Revises: 0005_add_merge_history
Create Date: 2026-04-18

Convert uq_series_fallback (and uq_series_fallback_null_cour) into partial
indexes scoped to WHERE mikan_bangumi_id IS NULL. Mikan-sourced series are
already identified by uq_series_mikan; the fallback key is only meaningful
for non-Mikan rows. This unblocks the proper Tier-3 cross-source create
path in IdentityResolver.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "0006_series_fallback_partial"
down_revision: Union[str, Sequence[str], None] = "0005_add_merge_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing full UNIQUE constraint and the NULL-cour helper,
    # then recreate both as partial indexes scoped to non-Mikan rows.
    with op.batch_alter_table("series") as batch_op:
        batch_op.drop_constraint("uq_series_fallback", type_="unique")
    op.execute("DROP INDEX IF EXISTS uq_series_fallback_null_cour")

    op.execute(
        "CREATE UNIQUE INDEX uq_series_fallback "
        "ON series (normalized_title, season, cour_part) "
        "WHERE mikan_bangumi_id IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_series_fallback_null_cour "
        "ON series (normalized_title, season) "
        "WHERE mikan_bangumi_id IS NULL AND cour_part IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_series_fallback")
    op.execute("DROP INDEX IF EXISTS uq_series_fallback_null_cour")

    # Restore the original (full) constraint + helper from 0002.
    with op.batch_alter_table("series") as batch_op:
        batch_op.create_unique_constraint(
            "uq_series_fallback",
            ["normalized_title", "season", "cour_part"],
        )
    op.execute(
        "CREATE UNIQUE INDEX uq_series_fallback_null_cour "
        "ON series (normalized_title, season) WHERE cour_part IS NULL"
    )
```

- [ ] **Step 4: Update `Series.__table_args__` to mirror the new partial constraints**

Edit `backend/src/module/domain/models/series.py:19-35`. Replace the block:

```python
    __table_args__ = (
        UniqueConstraint("mikan_bangumi_id", name="uq_series_mikan"),
        UniqueConstraint(
            "normalized_title", "season", "cour_part", name="uq_series_fallback"
        ),
        # Partial unique index for the NULL cour_part case.
        # SQL UNIQUE constraints treat NULLs as distinct, so two rows with
        # (normalized_title='x', season=1, cour_part=NULL) would not violate
        # uq_series_fallback. This partial index closes that gap.
        Index(
            "uq_series_fallback_null_cour",
            "normalized_title",
            "season",
            unique=True,
            sqlite_where=text("cour_part IS NULL"),
        ),
    )
```

with:

```python
    __table_args__ = (
        UniqueConstraint("mikan_bangumi_id", name="uq_series_mikan"),
        # Fallback identity is only meaningful for non-Mikan rows.
        # Mikan-sourced series are uniquely identified by mikan_bangumi_id;
        # forcing them to also satisfy (normalized_title, season, cour_part)
        # uniqueness blocks legitimate Tier-3 cross-source candidates.
        Index(
            "uq_series_fallback",
            "normalized_title",
            "season",
            "cour_part",
            unique=True,
            sqlite_where=text("mikan_bangumi_id IS NULL"),
        ),
        Index(
            "uq_series_fallback_null_cour",
            "normalized_title",
            "season",
            unique=True,
            sqlite_where=text(
                "mikan_bangumi_id IS NULL AND cour_part IS NULL"
            ),
        ),
    )
```

(`UniqueConstraint` import becomes unused; remove if so.)

- [ ] **Step 5: Update env.py allow-list to include the new partial UNIQUE name**

Edit `backend/alembic/env.py:50-63`. Replace `_include_object` with:

```python
def _include_object(obj, name, type_, reflected, compare_to):
    """Exclude objects managed outside SQLAlchemy metadata via op.execute().

    These partial indexes are encoded as Index(..., sqlite_where=text(...))
    in the ORM, but Alembic autogenerate cannot reliably round-trip them.
    Excluding them keeps revisions clean.
    """
    if type_ == "index" and name in (
        "idx_torrent_hash_bangumi",
        "uq_series_fallback",
        "uq_series_fallback_null_cour",
    ):
        return False
    return True
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && uv run pytest src/tests/test_migrations/test_0006_series_fallback.py -v`
Expected: 3 PASS.

- [ ] **Step 7: Run the full migration chain test to ensure no regression**

Run: `cd backend && uv run pytest src/tests/test_migrations/ -v`
Expected: ALL PASS (Plan 02/03 migration tests + the 3 new ones).

- [ ] **Step 8: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/alembic/versions/0006_series_fallback_partial.py \
        backend/src/module/domain/models/series.py \
        backend/alembic/env.py \
        backend/src/tests/test_migrations/test_0006_series_fallback.py
git commit -m "feat: scope series fallback uniqueness to non-Mikan rows"
```

---

## Task 2: IdentityResolver Tier-3 — drop the workaround

**Files:**
- Modify: `backend/src/module/services/identity_resolver.py:90-129`
- Modify: `backend/src/tests/test_services/test_identity_resolver.py` (the cross-source test)

**Background:** With Task 1 in place, `uq_series_fallback_null_cour` no longer blocks a non-Mikan series whose fallback key coincides with an existing Mikan series. The Plan 03 Task 10 workaround (mutating `pending_review=True` on the Mikan row instead of creating a new row) can now be replaced with the spec-conformant behavior: create a new Series with `pending_review=True` and surface the Mikan candidate ID.

- [ ] **Step 1: Locate the existing cross-source test**

Run: `cd backend && uv run pytest src/tests/test_services/test_identity_resolver.py -v -k cross_source`
Expected: PASS today (asserting the workaround behavior).

Open `backend/src/tests/test_services/test_identity_resolver.py` and find the test currently asserting the workaround (likely named like `test_tier3_cross_source_marks_existing_pending` or similar). Note its name and what it asserts.

- [ ] **Step 2: Rewrite that test to assert the spec behavior**

Replace the existing cross-source test body with:

```python
async def test_tier3_creates_new_pending_series_with_cross_source_candidates(
    db_session,
):
    """When a non-Mikan torrent's fallback key matches an existing Mikan
    series, IdentityResolver creates a NEW pending series and surfaces the
    Mikan candidate ID for manual review (spec §6.4 Tier 3)."""
    repo = SeriesRepository(db_session)
    # Existing Mikan series with the same fallback key
    mikan_row = await repo.create({
        "mikan_bangumi_id": 9999,
        "canonical_title": "Foo",
        "normalized_title": "foo",
        "season": 1,
        "cour_part": None,
        "root_path": "/downloads/Foo",
        "pending_review": False,
    })

    resolver = IdentityResolver(repo)
    result = await resolver.resolve(
        mikan_ref=None,
        normalized_title="foo",
        season=1,
        cour_part=None,
        raw_title_for_root="Foo (nyaa)",
    )

    assert result.tier == "pending_review"
    assert result.newly_created is True
    assert result.series.id != mikan_row.id
    assert result.series.mikan_bangumi_id is None
    assert result.series.pending_review is True
    assert result.merge_candidates == [mikan_row.id]

    # Mikan row must NOT have been mutated
    refreshed = await repo.get_by_id(mikan_row.id)
    assert refreshed.pending_review is False
```

- [ ] **Step 3: Run the rewritten test to confirm it fails**

Run: `cd backend && uv run pytest src/tests/test_services/test_identity_resolver.py::test_tier3_creates_new_pending_series_with_cross_source_candidates -v`
Expected: FAIL — current resolver still mutates the existing row.

- [ ] **Step 4: Replace the workaround in `identity_resolver.py`**

Edit `backend/src/module/services/identity_resolver.py:90-129`. Replace the block from `# Tier 2: fallback key — only non-Mikan sourced series qualify` through end of `resolve()`:

```python
        # Tier 2: fallback key — only non-Mikan sourced series qualify
        hit = await self._repo.get_by_fallback(normalized_title, season, cour_part)
        if hit is not None and hit.mikan_bangumi_id is None:
            return ResolvedIdentity(series=hit, tier="fallback", newly_created=False)

        # Tier 3: pending review. With the partial fallback constraint scoped
        # to mikan_bangumi_id IS NULL (migration 0006), inserting a new
        # non-Mikan series is safe even when an existing Mikan series shares
        # the same (normalized_title, season, cour_part). The Mikan row is
        # surfaced as a merge candidate; user / UI confirms the merge.
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

- [ ] **Step 5: Run the rewritten test to confirm it passes**

Run: `cd backend && uv run pytest src/tests/test_services/test_identity_resolver.py -v`
Expected: ALL PASS (rewritten cross-source test + others unchanged).

- [ ] **Step 6: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/src/module/services/identity_resolver.py \
        backend/src/tests/test_services/test_identity_resolver.py
git commit -m "fix: IdentityResolver Tier-3 creates new pending series (spec §6.4)"
```

---

## Task 3: Migration 0007 — additive bangumi/torrent columns

**Files:**
- Create: `backend/alembic/versions/0007_add_bangumi_series_link.py`
- Create: `backend/src/tests/test_migrations/test_0007_add_bangumi_series_link.py`

**Background:** Stage B of the schema rollout. Bangumi gains the new identity surface as nullable columns so the live ORM keeps working; backfill (Task 7) populates them; the lockdown migration (Task 9) makes `series_id` NOT NULL and adds partial UNIQUEs. Torrent gains `mikan_bangumi_id`/`mikan_subgroup_id` for downstream Series resolution and dedup. **Do not** modify the SQLAlchemy `Bangumi` / `Torrent` ORM models in this task — Task 4 does that, after the migration test confirms the SQL works.

- [ ] **Step 1: Write the failing test**

```python
# backend/src/tests/test_migrations/test_0007_add_bangumi_series_link.py
"""Tests for migration 0007: additive bangumi + torrent columns."""
import os
import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).parent.parent.parent.parent


def _run_alembic(target: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "alembic", "upgrade", target],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
    )


def _columns(db: Path, table: str) -> set[str]:
    engine = sa.create_engine(f"sqlite:///{db}")
    inspector = sa.inspect(engine)
    return {c["name"] for c in inspector.get_columns(table)}


@pytest.mark.integration
def test_0007_adds_bangumi_columns(tmp_path):
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"

    result = _run_alembic("0007_add_bangumi_series_link", env)
    assert result.returncode == 0, result.stderr

    cols = _columns(db, "bangumi")
    assert "series_id" in cols
    assert "mikan_subgroup_id" in cols
    assert "active" in cols
    assert "path_override" in cols
    assert "observed_groups" in cols
    # Old columns must remain — destructive drop happens in 0008
    assert "official_title" in cols
    assert "save_path" in cols


@pytest.mark.integration
def test_0007_adds_torrent_columns(tmp_path):
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0007_add_bangumi_series_link", env).returncode == 0

    cols = _columns(db, "torrent")
    assert "mikan_bangumi_id" in cols
    assert "mikan_subgroup_id" in cols


@pytest.mark.integration
def test_0007_active_default_true_for_existing_rows(tmp_path):
    """Server-default for active must be true so existing bangumi remain
    visible to the rename pipeline after migration."""
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"

    # Stop at 0005 so we can seed a legacy bangumi row, then upgrade to 0007.
    assert _run_alembic("0005_add_merge_history", env).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO bangumi (rss_id, official_title, title_raw, season, "
            "group_name, eps_collect, offset, filter, rss_link, added, "
            "deleted, pending_review, created_at, updated_at, version) "
            "VALUES (NULL, 'X', 'X', 1, 'G', 0, 0, '720', '', 0, 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))

    assert _run_alembic("0007_add_bangumi_series_link", env).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        active_val = conn.execute(
            sa.text("SELECT active FROM bangumi WHERE official_title='X'")
        ).scalar_one()
    assert active_val == 1


@pytest.mark.integration
def test_0007_downgrade_is_clean(tmp_path):
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0007_add_bangumi_series_link", env).returncode == 0

    result = subprocess.run(
        ["uv", "run", "alembic", "downgrade", "0005_add_merge_history"],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    cols = _columns(db, "bangumi")
    assert "series_id" not in cols
    assert "active" not in cols
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest src/tests/test_migrations/test_0007_add_bangumi_series_link.py -v`
Expected: FAIL — revision does not exist.

- [ ] **Step 3: Author migration 0007**

Create `backend/alembic/versions/0007_add_bangumi_series_link.py`:

```python
"""add_bangumi_series_link

Revision ID: 0007_add_bangumi_series_link
Revises: 0006_series_fallback_partial
Create Date: 2026-04-18

Stage B (additive). Bangumi gains the new identity surface as nullable
columns so the live ORM keeps working through backfill. Torrent gains
mikan_bangumi_id / mikan_subgroup_id for downstream Series resolution.

NOT NULL on bangumi.series_id and the partial UNIQUE constraints arrive
in 0008_lockdown_bangumi_identity, after backfill + migrate_duplicates.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_add_bangumi_series_link"
down_revision: Union[str, Sequence[str], None] = "0006_series_fallback_partial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bangumi") as batch_op:
        batch_op.add_column(
            sa.Column("series_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("mikan_subgroup_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),
            )
        )
        batch_op.add_column(
            sa.Column("path_override", sa.String(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("observed_groups", sa.Text(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_bangumi_series",
            "series",
            ["series_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_bangumi_series_id", ["series_id"], unique=False
        )

    with op.batch_alter_table("torrent") as batch_op:
        batch_op.add_column(
            sa.Column("mikan_bangumi_id", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("mikan_subgroup_id", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("torrent") as batch_op:
        batch_op.drop_column("mikan_subgroup_id")
        batch_op.drop_column("mikan_bangumi_id")

    with op.batch_alter_table("bangumi") as batch_op:
        batch_op.drop_index("ix_bangumi_series_id")
        batch_op.drop_constraint("fk_bangumi_series", type_="foreignkey")
        batch_op.drop_column("observed_groups")
        batch_op.drop_column("path_override")
        batch_op.drop_column("active")
        batch_op.drop_column("mikan_subgroup_id")
        batch_op.drop_column("series_id")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest src/tests/test_migrations/test_0007_add_bangumi_series_link.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Run the full migration chain to ensure no regression**

Run: `cd backend && uv run pytest src/tests/test_migrations/ -v`
Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/alembic/versions/0007_add_bangumi_series_link.py \
        backend/src/tests/test_migrations/test_0007_add_bangumi_series_link.py
git commit -m "feat: alembic 0007 add bangumi series link + torrent mikan refs"
```

---

## Task 4: Bangumi + Torrent ORM additive update

**Files:**
- Modify: `backend/src/module/domain/models/bangumi.py`
- Modify: `backend/src/module/domain/models/torrent.py`
- Create: `backend/src/tests/test_domain/test_bangumi_new_columns.py`

**Background:** Now that 0007 added the columns at the SQL layer, mirror them in the ORM so application code can write to them. This task is *purely additive* — do not drop any existing columns or constraints; that happens in Task 9 with migration 0008. The `series` relationship is added but kept lazy-loaded; callers that need it must `await session.refresh(bangumi, ['series'])` or use `selectinload`. (Plan 05 will revisit eager loading for API serialization.)

- [ ] **Step 1: Write the failing test**

```python
# backend/src/tests/test_domain/test_bangumi_new_columns.py
"""ORM additions for Bangumi (series link, active flag, etc.) and Torrent
(mikan refs) — additive only, no column drops yet."""
import pytest

from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.domain.models.torrent import Torrent


@pytest.mark.unit
def test_bangumi_has_new_columns():
    cols = {c.name for c in Bangumi.__table__.columns}
    assert "series_id" in cols
    assert "mikan_subgroup_id" in cols
    assert "active" in cols
    assert "path_override" in cols
    assert "observed_groups" in cols


@pytest.mark.unit
def test_bangumi_has_series_relationship():
    assert "series" in Bangumi.__mapper__.relationships


@pytest.mark.unit
def test_torrent_has_mikan_columns():
    cols = {c.name for c in Torrent.__table__.columns}
    assert "mikan_bangumi_id" in cols
    assert "mikan_subgroup_id" in cols


@pytest.mark.integration
async def test_bangumi_can_set_series_id_and_load_relationship(db_session):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    s = Series(
        mikan_bangumi_id=42,
        canonical_title="Demo",
        normalized_title="demo",
        season=1,
        root_path="/downloads/Demo",
        pending_review=False,
    )
    db_session.add(s)
    await db_session.flush()

    b = Bangumi(
        official_title="Demo (legacy)",
        title_raw="Demo",
        season=1,
        group_name="G",
        rss_link="",
        series_id=s.id,
        mikan_subgroup_id=370,
        active=True,
    )
    db_session.add(b)
    await db_session.flush()

    stmt = (
        select(Bangumi)
        .where(Bangumi.id == b.id)
        .options(selectinload(Bangumi.series))
    )
    refreshed = (await db_session.execute(stmt)).scalar_one()
    assert refreshed.series.canonical_title == "Demo"
    assert refreshed.series_id == s.id
    assert refreshed.active is True
    assert refreshed.mikan_subgroup_id == 370
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && uv run pytest src/tests/test_domain/test_bangumi_new_columns.py -v`
Expected: FAIL — `series_id` etc. not on the model.

- [ ] **Step 3: Add the new columns + relationship to `Bangumi`**

Edit `backend/src/module/domain/models/bangumi.py`. Append the new columns and a `series` relationship below the existing fields (do not delete anything yet). The full file becomes:

```python
"""Bangumi domain model."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, VersionMixin

if TYPE_CHECKING:
    from .series import Series


class Bangumi(Base, TimestampMixin, VersionMixin):
    """Bangumi (anime series) entity.

    Represents a tracked anime series with its metadata and download rules.
    """

    __tablename__ = "bangumi"

    __table_args__ = (
        UniqueConstraint(
            "official_title",
            "season",
            "group_name",
            name="uq_bangumi_title_season_group",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rss_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("rssitem.id"), nullable=True
    )
    official_title: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    title_raw: Mapped[str] = mapped_column(String, nullable=False)
    season: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    season_raw: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    group_name: Mapped[str] = mapped_column(String, nullable=False, default="Unknown")
    dpi: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    subtitle: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    eps_collect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filter: Mapped[str] = mapped_column(
        String, nullable=False, default="720,\\d+-\\d+"
    )
    rss_link: Mapped[str] = mapped_column(String, nullable=False, default="")
    poster_link: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    added: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rule_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    save_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pending_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    global_filter_matches: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # New identity surface (migration 0007). series_id becomes NOT NULL in 0008.
    series_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("series.id"), nullable=True, index=True
    )
    mikan_subgroup_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    path_override: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    observed_groups: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    series: Mapped[Optional["Series"]] = relationship("Series", lazy="select")
```

- [ ] **Step 4: Add the new columns to `Torrent`**

Edit `backend/src/module/domain/models/torrent.py`. Append two columns after `pikpak_task_id`:

```python
    mikan_bangumi_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mikan_subgroup_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd backend && uv run pytest src/tests/test_domain/test_bangumi_new_columns.py -v`
Expected: 4 PASS.

- [ ] **Step 6: Run the full unit + repo + domain suite to ensure no regression**

Run: `cd backend && uv run pytest src/tests/test_domain/ src/tests/test_repositories/ -q`
Expected: ALL PASS (Plan 02/03 baselines).

- [ ] **Step 7: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/src/module/domain/models/bangumi.py \
        backend/src/module/domain/models/torrent.py \
        backend/src/tests/test_domain/test_bangumi_new_columns.py
git commit -m "feat: bangumi/torrent ORM additive columns for series link"
```

---

## Task 5: BangumiRepository — series-aware identity helpers

**Files:**
- Modify: `backend/src/module/repositories/bangumi.py`
- Modify: `backend/src/module/repositories/torrent.py`
- Create: `backend/src/tests/test_repositories/test_bangumi_series_helpers.py`

**Background:** Add the new identity-resolution helpers the merge service and the rewritten RSS pipeline will use. Keep `get_by_composite_key` and `create()` validation alive for now — Task 9 will remove them when the legacy columns disappear. Also add a torrent backfill helper for Task 7.

- [ ] **Step 1: Write the failing tests**

```python
# backend/src/tests/test_repositories/test_bangumi_series_helpers.py
"""New BangumiRepository helpers for series-driven identity (Plan 04)."""
import pytest

from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.repositories.bangumi import BangumiRepository


async def _seed_series(db_session, **kw) -> Series:
    s = Series(
        canonical_title=kw.pop("canonical_title", "S"),
        normalized_title=kw.pop("normalized_title", "s"),
        season=kw.pop("season", 1),
        root_path=kw.pop("root_path", "/downloads/S"),
        pending_review=False,
        **kw,
    )
    db_session.add(s)
    await db_session.flush()
    return s


async def _seed_bangumi(db_session, *, series_id, **overrides) -> Bangumi:
    data = dict(
        official_title="legacy",
        title_raw="legacy",
        season=1,
        group_name="G",
        rss_link="",
        series_id=series_id,
        active=True,
    )
    data.update(overrides)
    b = Bangumi(**data)
    db_session.add(b)
    await db_session.flush()
    return b


@pytest.mark.integration
async def test_get_by_series_and_subgroup_finds_match(db_session):
    repo = BangumiRepository(db_session)
    s = await _seed_series(db_session, mikan_bangumi_id=1)
    b = await _seed_bangumi(db_session, series_id=s.id, mikan_subgroup_id=370)

    hit = await repo.get_by_series_and_subgroup(s.id, 370)
    assert hit is not None and hit.id == b.id


@pytest.mark.integration
async def test_get_by_series_and_subgroup_excludes_deleted(db_session):
    repo = BangumiRepository(db_session)
    s = await _seed_series(db_session, mikan_bangumi_id=2)
    b = await _seed_bangumi(
        db_session, series_id=s.id, mikan_subgroup_id=99, deleted=True,
    )

    assert await repo.get_by_series_and_subgroup(s.id, 99) is None


@pytest.mark.integration
async def test_get_by_series_and_rss_for_fallback_identity(db_session):
    repo = BangumiRepository(db_session)
    s = await _seed_series(db_session, normalized_title="t1")
    b = await _seed_bangumi(
        db_session, series_id=s.id, mikan_subgroup_id=None, rss_id=None,
    )
    # rss_id None should not match — fallback identity needs a real rss_id
    assert await repo.get_by_series_and_rss(s.id, None) is None


@pytest.mark.integration
async def test_list_by_series_returns_only_undeleted(db_session):
    repo = BangumiRepository(db_session)
    s = await _seed_series(db_session, mikan_bangumi_id=3)
    b1 = await _seed_bangumi(db_session, series_id=s.id, mikan_subgroup_id=1)
    b2 = await _seed_bangumi(
        db_session, series_id=s.id, mikan_subgroup_id=2, deleted=True,
    )
    rows = await repo.list_by_series(s.id)
    assert {b.id for b in rows} == {b1.id}


@pytest.mark.integration
async def test_deactivate_siblings_in_series(db_session):
    repo = BangumiRepository(db_session)
    s = await _seed_series(db_session, mikan_bangumi_id=4)
    b_keep = await _seed_bangumi(db_session, series_id=s.id, mikan_subgroup_id=1)
    b_other = await _seed_bangumi(db_session, series_id=s.id, mikan_subgroup_id=2)
    await repo.deactivate_siblings_in_series(s.id, except_bangumi_id=b_keep.id)
    await db_session.refresh(b_keep)
    await db_session.refresh(b_other)
    assert b_keep.active is True
    assert b_other.active is False
```

```python
# Append to backend/src/tests/test_repositories/test_torrent.py
@pytest.mark.integration
async def test_backfill_mikan_ids_persists_both(db_session):
    from module.repositories.torrent import TorrentRepository
    from module.domain.models.torrent import Torrent

    repo = TorrentRepository(db_session)
    t = Torrent(name="x", url="https://e.com", hash="abc", bangumi_id=None, rss_id=None)
    db_session.add(t)
    await db_session.flush()

    await repo.backfill_mikan_ids(t.id, mikan_bangumi_id=3906, mikan_subgroup_id=370)
    await db_session.refresh(t)
    assert t.mikan_bangumi_id == 3906
    assert t.mikan_subgroup_id == 370
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest src/tests/test_repositories/test_bangumi_series_helpers.py src/tests/test_repositories/test_torrent.py::test_backfill_mikan_ids_persists_both -v`
Expected: FAIL — repository methods do not exist.

- [ ] **Step 3: Add the helpers to `BangumiRepository`**

Edit `backend/src/module/repositories/bangumi.py`. Append to the class:

```python
    async def get_by_series_and_subgroup(
        self, series_id: int, mikan_subgroup_id: int
    ) -> Optional[Bangumi]:
        """Identity lookup for Mikan-sourced bangumi (spec §6.2 partial UNIQUE)."""
        stmt = select(Bangumi).where(
            and_(
                Bangumi.series_id == series_id,
                Bangumi.mikan_subgroup_id == mikan_subgroup_id,
                Bangumi.deleted == False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_series_and_rss(
        self, series_id: int, rss_id: Optional[int]
    ) -> Optional[Bangumi]:
        """Fallback identity for non-Mikan bangumi: (series_id, rss_id) when
        mikan_subgroup_id IS NULL. rss_id None never matches (no fallback key).
        """
        if rss_id is None:
            return None
        stmt = select(Bangumi).where(
            and_(
                Bangumi.series_id == series_id,
                Bangumi.rss_id == rss_id,
                Bangumi.mikan_subgroup_id.is_(None),
                Bangumi.deleted == False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_series(self, series_id: int) -> list[Bangumi]:
        stmt = select(Bangumi).where(
            and_(Bangumi.series_id == series_id, Bangumi.deleted == False)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def deactivate_siblings_in_series(
        self, series_id: int, except_bangumi_id: int
    ) -> int:
        """Set active=false on all undeleted siblings of `except_bangumi_id`
        within the same series. Returns the number of rows updated."""
        stmt = (
            update(Bangumi)
            .where(
                Bangumi.series_id == series_id,
                Bangumi.id != except_bangumi_id,
                Bangumi.deleted == False,
                Bangumi.active == True,
            )
            .values(active=False)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount
```

- [ ] **Step 4: Add `backfill_mikan_ids` to `TorrentRepository`**

Edit `backend/src/module/repositories/torrent.py`. Append:

```python
    async def backfill_mikan_ids(
        self,
        torrent_id: int,
        mikan_bangumi_id: Optional[int],
        mikan_subgroup_id: Optional[int],
    ) -> None:
        """One-shot setter used by scripts/backfill_series.py. Idempotent —
        overwrites whatever is currently stored."""
        stmt = (
            update(Torrent)
            .where(Torrent.id == torrent_id)
            .values(
                mikan_bangumi_id=mikan_bangumi_id,
                mikan_subgroup_id=mikan_subgroup_id,
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest src/tests/test_repositories/test_bangumi_series_helpers.py src/tests/test_repositories/test_torrent.py::test_backfill_mikan_ids_persists_both -v`
Expected: 6 PASS.

- [ ] **Step 6: Run the full repo suite for regression**

Run: `cd backend && uv run pytest src/tests/test_repositories/ -q`
Expected: ALL PASS.

- [ ] **Step 7: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/src/module/repositories/bangumi.py \
        backend/src/module/repositories/torrent.py \
        backend/src/tests/test_repositories/test_bangumi_series_helpers.py \
        backend/src/tests/test_repositories/test_torrent.py
git commit -m "feat: bangumi/torrent repo helpers for series-driven identity"
```

---

## Task 6: BangumiMergeService — atomic merge transaction

**Files:**
- Create: `backend/src/module/services/bangumi_merge.py`
- Create: `backend/src/tests/test_services/test_bangumi_merge.py`

**Background:** Spec §11.2 requires merge to atomically (a) move every torrent from loser to winner, (b) drop torrents that would violate the `(hash, bangumi_id)` UNIQUE on the winner side, (c) union `observed_groups`, (d) soft-delete the loser, (e) write a `bangumi_merge_history` row capturing snapshots and moved/dropped IDs. The service is the single chokepoint — both `migrate_duplicates.py` and the future API route `POST /api/v1/bangumi/merge` (Plan 05) call it.

- [ ] **Step 1: Write the failing test**

```python
# backend/src/tests/test_services/test_bangumi_merge.py
"""Atomic bangumi merge transaction (spec §11.2)."""
import json

import pytest

from module.domain.models.bangumi import Bangumi
from module.domain.models.merge_history import BangumiMergeHistory
from module.domain.models.series import Series
from module.domain.models.torrent import Torrent
from module.repositories.bangumi import BangumiRepository
from module.repositories.merge_history import BangumiMergeHistoryRepository
from module.repositories.torrent import TorrentRepository
from module.services.bangumi_merge import BangumiMergeService


async def _seed(db_session) -> tuple[Series, Bangumi, Bangumi]:
    s = Series(
        canonical_title="X", normalized_title="x", season=1,
        root_path="/p/X", pending_review=False, mikan_bangumi_id=42,
    )
    db_session.add(s)
    await db_session.flush()

    winner = Bangumi(
        official_title="X", title_raw="X", season=1, group_name="LoliHouse",
        rss_link="", series_id=s.id, mikan_subgroup_id=370, active=True,
        observed_groups=json.dumps(["LoliHouse"]),
    )
    loser = Bangumi(
        official_title="X", title_raw="X", season=1, group_name="A&LoliHouse",
        rss_link="", series_id=s.id, mikan_subgroup_id=370, active=True,
        observed_groups=json.dumps(["A&LoliHouse"]),
    )
    db_session.add_all([winner, loser])
    await db_session.flush()
    return s, winner, loser


@pytest.mark.integration
async def test_merge_moves_unique_torrents_to_winner(db_session):
    s, winner, loser = await _seed(db_session)
    t = Torrent(name="t1", url="u", hash="h-unique", bangumi_id=loser.id)
    db_session.add(t)
    await db_session.flush()

    svc = BangumiMergeService(db_session)
    history = await svc.merge(
        winner_id=winner.id, loser_id=loser.id,
        merge_reason="auto_migration", merged_by="auto_migration",
    )

    await db_session.refresh(t)
    assert t.bangumi_id == winner.id
    moved = json.loads(history.moved_torrent_ids)
    assert moved == [t.id]
    assert json.loads(history.dropped_torrents) == []


@pytest.mark.integration
async def test_merge_drops_torrents_that_would_violate_winner_unique(db_session):
    s, winner, loser = await _seed(db_session)
    # Both bangumi already have a torrent with hash 'h-conflict' — the loser
    # copy must be dropped (not moved) to honour (hash, bangumi_id) UNIQUE.
    db_session.add_all([
        Torrent(name="w", url="u", hash="h-conflict", bangumi_id=winner.id),
        Torrent(name="l", url="u", hash="h-conflict", bangumi_id=loser.id),
    ])
    await db_session.flush()

    svc = BangumiMergeService(db_session)
    history = await svc.merge(
        winner_id=winner.id, loser_id=loser.id,
        merge_reason="auto_migration", merged_by="auto_migration",
    )

    dropped = json.loads(history.dropped_torrents)
    assert len(dropped) == 1
    assert dropped[0]["hash"] == "h-conflict"
    assert dropped[0]["bangumi_id"] == loser.id


@pytest.mark.integration
async def test_merge_soft_deletes_loser_and_unions_observed_groups(db_session):
    s, winner, loser = await _seed(db_session)
    svc = BangumiMergeService(db_session)
    await svc.merge(
        winner_id=winner.id, loser_id=loser.id,
        merge_reason="auto_migration", merged_by="auto_migration",
    )
    await db_session.refresh(winner)
    await db_session.refresh(loser)
    assert loser.deleted is True
    assert set(json.loads(winner.observed_groups)) == {"LoliHouse", "A&LoliHouse"}


@pytest.mark.integration
async def test_merge_writes_full_history_row(db_session):
    s, winner, loser = await _seed(db_session)
    svc = BangumiMergeService(db_session)
    history = await svc.merge(
        winner_id=winner.id, loser_id=loser.id,
        merge_reason="mikan_id_match", merged_by="user:alice",
    )
    snap = json.loads(history.loser_snapshot)
    assert snap["id"] == loser.id
    assert snap["official_title"] == "X"
    assert history.merge_reason == "mikan_id_match"
    assert history.merged_by == "user:alice"
    assert history.winner_bangumi_id == winner.id


@pytest.mark.integration
async def test_merge_refuses_blacklisted_pair(db_session):
    s, winner, loser = await _seed(db_session)
    repo = BangumiMergeHistoryRepository(db_session)
    await repo.create(
        winner_id=winner.id, loser_id=loser.id,
        loser_snapshot={}, moved_torrent_ids=[], dropped_torrents=[],
        merge_reason="prior_merge", merged_by="auto_migration",
    )

    svc = BangumiMergeService(db_session)
    with pytest.raises(ValueError, match="blacklisted"):
        await svc.merge(
            winner_id=winner.id, loser_id=loser.id,
            merge_reason="auto_migration", merged_by="auto_migration",
        )


@pytest.mark.integration
async def test_merge_refuses_winner_equal_loser(db_session):
    s, winner, _ = await _seed(db_session)
    svc = BangumiMergeService(db_session)
    with pytest.raises(ValueError, match="must differ"):
        await svc.merge(
            winner_id=winner.id, loser_id=winner.id,
            merge_reason="auto_migration", merged_by="auto_migration",
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest src/tests/test_services/test_bangumi_merge.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `BangumiMergeService`**

Create `backend/src/module/services/bangumi_merge.py`:

```python
"""Atomic merge transaction for two bangumi rows (spec §11.2).

Both `scripts/migrate_duplicates.py` and the future
`POST /api/v1/bangumi/merge` route (Plan 05) call this service. It is the
single chokepoint that:

  1. Verifies the (winner, loser) pair is not blacklisted (spec §11.4).
  2. Moves every torrent on `loser_id` to `winner_id`, dropping any that
     would violate the (hash, bangumi_id) UNIQUE on the winner side.
  3. Unions the loser's observed_groups into the winner's.
  4. Soft-deletes the loser (deleted=True).
  5. Writes a bangumi_merge_history row capturing full snapshots.

All work happens in the calling AsyncSession's existing transaction; the
caller decides when to commit.
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.bangumi import Bangumi
from module.domain.models.merge_history import BangumiMergeHistory
from module.domain.models.torrent import Torrent
from module.repositories.bangumi import BangumiRepository
from module.repositories.merge_history import BangumiMergeHistoryRepository
from module.repositories.torrent import TorrentRepository


def _serialize_bangumi(b: Bangumi) -> dict:
    return {
        "id": b.id,
        "rss_id": b.rss_id,
        "official_title": b.official_title,
        "title_raw": b.title_raw,
        "season": b.season,
        "group_name": b.group_name,
        "rss_link": b.rss_link,
        "save_path": b.save_path,
        "series_id": b.series_id,
        "mikan_subgroup_id": b.mikan_subgroup_id,
        "active": b.active,
        "observed_groups": b.observed_groups,
        "deleted": b.deleted,
    }


def _serialize_torrent(t: Torrent) -> dict:
    return {
        "id": t.id,
        "bangumi_id": t.bangumi_id,
        "rss_id": t.rss_id,
        "name": t.name,
        "url": t.url,
        "hash": t.hash,
        "homepage": t.homepage,
        "downloaded": t.downloaded,
    }


def _union_groups(winner_json: Optional[str], loser_json: Optional[str]) -> str:
    def _decode(raw: Optional[str]) -> list[str]:
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return []
        return [g for g in data if isinstance(g, str)]

    union = sorted(set(_decode(winner_json)) | set(_decode(loser_json)))
    return json.dumps(union, ensure_ascii=False)


class BangumiMergeService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._bangumi_repo = BangumiRepository(session)
        self._torrent_repo = TorrentRepository(session)
        self._history_repo = BangumiMergeHistoryRepository(session)

    async def merge(
        self,
        *,
        winner_id: int,
        loser_id: int,
        merge_reason: str,
        merged_by: str,
    ) -> BangumiMergeHistory:
        if winner_id == loser_id:
            raise ValueError("winner_id and loser_id must differ")

        if await self._history_repo.is_pair_blacklisted(winner_id, loser_id):
            raise ValueError(
                f"pair ({winner_id}, {loser_id}) is blacklisted (spec §11.4)"
            )

        winner = await self._bangumi_repo.get_by_id(winner_id)
        if winner is None:
            raise ValueError(f"winner bangumi id={winner_id} not found")
        loser = await self._bangumi_repo.get_by_id(loser_id)
        if loser is None:
            raise ValueError(f"loser bangumi id={loser_id} not found")

        loser_snapshot = _serialize_bangumi(loser)

        # Existing torrent hashes on the winner — collisions get dropped, not moved.
        winner_torrents = await self._torrent_repo.get_by_bangumi(winner_id)
        winner_hashes = {t.hash for t in winner_torrents if t.hash is not None}

        moved: list[int] = []
        dropped: list[dict] = []

        loser_torrents = await self._torrent_repo.get_by_bangumi(loser_id)
        for t in loser_torrents:
            if t.hash is not None and t.hash in winner_hashes:
                dropped.append(_serialize_torrent(t))
                await self.session.delete(t)
            else:
                t.bangumi_id = winner_id
                moved.append(t.id)
        await self.session.flush()

        winner.observed_groups = _union_groups(
            winner.observed_groups, loser.observed_groups
        )
        loser.deleted = True
        loser.active = False
        await self.session.flush()

        history = await self._history_repo.create(
            winner_id=winner_id,
            loser_id=loser_id,
            loser_snapshot=loser_snapshot,
            moved_torrent_ids=moved,
            dropped_torrents=dropped,
            merge_reason=merge_reason,
            merged_by=merged_by,
        )
        return history
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest src/tests/test_services/test_bangumi_merge.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/src/module/services/bangumi_merge.py \
        backend/src/tests/test_services/test_bangumi_merge.py
git commit -m "feat: BangumiMergeService atomic merge transaction (spec §11.2)"
```

---

## Task 7: `scripts/backfill_series.py`

**Files:**
- Create: `backend/scripts/__init__.py`
- Create: `backend/scripts/backfill_series.py`
- Create: `backend/src/tests/test_scripts/__init__.py`
- Create: `backend/src/tests/test_scripts/test_backfill_series.py`

**Background:** This script implements spec §13.2 phases 3–5 in one pass. It reads every existing bangumi row, extracts `mikan_bangumi_id`/`mikan_subgroup_id` from the `rss_link` column when it matches the Mikan RSS shape, calls `IdentityResolver` to `get_or_create` a Series, and links the bangumi via `series_id` + `mikan_subgroup_id`. It then walks every torrent on those bangumi and backfills `mikan_bangumi_id` / `mikan_subgroup_id` from the bangumi's resolved values (homepage scraping is out of scope — Plan 05 will handle pending_torrent_enrichment via `MikanResolver`). Idempotent: re-runs are no-ops once everything is linked.

The Mikan RSS link shape is `mikanani.me/RSS/Bangumi?bangumiId=<int>&subgroupid=<int>` (also matches under `mikani.me`). For non-matching rss_link (Aggregate/Search RSS, or non-Mikan), the bangumi is linked to a Series via fallback identity using `normalize_title(official_title)` and `season`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/src/tests/test_scripts/test_backfill_series.py
"""Tests for scripts/backfill_series.py."""
import sys
from pathlib import Path

import pytest

# Make scripts/ importable
BACKEND_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.backfill_series import (  # noqa: E402
    extract_mikan_ids_from_rss,
    backfill_one_bangumi,
    backfill_torrents_for_bangumi,
)

from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.domain.models.torrent import Torrent
from module.repositories.bangumi import BangumiRepository
from module.repositories.series import SeriesRepository
from module.repositories.torrent import TorrentRepository


@pytest.mark.unit
@pytest.mark.parametrize("link, expected", [
    (
        "https://mikanani.me/RSS/Bangumi?bangumiId=3906&subgroupid=370",
        (3906, 370),
    ),
    (
        "http://mikanime.tv/RSS/Bangumi?bangumiId=42&subgroupid=7",
        (42, 7),
    ),
    (
        "https://mikanani.me/RSS/Bangumi?bangumiId=3906",
        (3906, None),
    ),
    (
        "https://nyaa.si/?page=rss",
        (None, None),
    ),
    ("", (None, None)),
    (None, (None, None)),
])
def test_extract_mikan_ids_from_rss(link, expected):
    assert extract_mikan_ids_from_rss(link) == expected


@pytest.mark.integration
async def test_backfill_one_bangumi_creates_mikan_series(db_session):
    repo_b = BangumiRepository(db_session)
    repo_s = SeriesRepository(db_session)

    b = Bangumi(
        official_title="Demo S2", title_raw="Demo S2", season=2,
        group_name="G",
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=100&subgroupid=20",
    )
    db_session.add(b)
    await db_session.flush()

    await backfill_one_bangumi(db_session, b)
    await db_session.refresh(b)

    assert b.series_id is not None
    assert b.mikan_subgroup_id == 20
    series = await repo_s.get_by_id(b.series_id)
    assert series.mikan_bangumi_id == 100
    assert series.canonical_title == "Demo S2"


@pytest.mark.integration
async def test_backfill_one_bangumi_uses_fallback_for_non_mikan(db_session):
    repo_s = SeriesRepository(db_session)

    b = Bangumi(
        official_title="Nyaa Show",
        title_raw="Nyaa Show 第二季",
        season=2,
        group_name="G",
        rss_link="https://nyaa.si/?page=rss",
    )
    import module.domain.models.bangumi  # noqa: F401
    db_session.add(b)
    await db_session.flush()

    await backfill_one_bangumi(db_session, b)
    await db_session.refresh(b)

    assert b.series_id is not None
    assert b.mikan_subgroup_id is None
    series = await repo_s.get_by_id(b.series_id)
    assert series.mikan_bangumi_id is None


@pytest.mark.integration
async def test_backfill_one_bangumi_is_idempotent(db_session):
    b = Bangumi(
        official_title="Idempotent", title_raw="Idempotent", season=1,
        group_name="G",
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=200&subgroupid=11",
    )
    db_session.add(b)
    await db_session.flush()

    await backfill_one_bangumi(db_session, b)
    await db_session.refresh(b)
    first_series_id = b.series_id

    await backfill_one_bangumi(db_session, b)
    await db_session.refresh(b)
    assert b.series_id == first_series_id


@pytest.mark.integration
async def test_backfill_two_bangumi_share_series_when_mikan_id_matches(db_session):
    """Production case: rows 91 + 93 share bangumiId=3906/subgroupid=370."""
    b1 = Bangumi(
        official_title="Same", title_raw="Same A", season=1, group_name="A",
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=3906&subgroupid=370",
    )
    b2 = Bangumi(
        official_title="Same", title_raw="Same B", season=1, group_name="B",
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=3906&subgroupid=370",
    )
    db_session.add_all([b1, b2])
    await db_session.flush()

    await backfill_one_bangumi(db_session, b1)
    await backfill_one_bangumi(db_session, b2)
    await db_session.refresh(b1)
    await db_session.refresh(b2)

    assert b1.series_id == b2.series_id
    assert b1.mikan_subgroup_id == b2.mikan_subgroup_id == 370


@pytest.mark.integration
async def test_backfill_torrents_propagates_mikan_ids(db_session):
    b = Bangumi(
        official_title="X", title_raw="X", season=1, group_name="G",
        rss_link="https://mikanani.me/RSS/Bangumi?bangumiId=500&subgroupid=99",
    )
    db_session.add(b)
    await db_session.flush()
    await backfill_one_bangumi(db_session, b)

    t = Torrent(name="x", url="u", hash="h1", bangumi_id=b.id)
    db_session.add(t)
    await db_session.flush()

    n = await backfill_torrents_for_bangumi(db_session, b)
    await db_session.refresh(t)
    assert n == 1
    assert t.mikan_bangumi_id == 500
    assert t.mikan_subgroup_id == 99
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest src/tests/test_scripts/test_backfill_series.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Create the package marker**

Create `backend/scripts/__init__.py` (empty file).
Create `backend/src/tests/test_scripts/__init__.py` (empty file).

- [ ] **Step 4: Implement the backfill module**

Create `backend/scripts/backfill_series.py`:

```python
"""One-shot script: link every existing bangumi + torrent to a Series.

Usage (from backend/):
  uv run python -m scripts.backfill_series           # default DB
  AB_ALEMBIC_DB_URL=sqlite+aiosqlite:///path uv run python -m scripts.backfill_series

Idempotent. Re-runs only touch rows where series_id IS NULL or
mikan_*_id IS NULL.

Phases (per spec §13.2):
  3. Link bangumi -> series (get_or_create via IdentityResolver).
  4. Backfill torrent.mikan_bangumi_id / mikan_subgroup_id from bangumi.
  5. Backfill bangumi.mikan_subgroup_id (covered by step 3 since rss_link
     carries the subgroupid for Mikan rows).
"""
from __future__ import annotations

import asyncio
import logging
import re
import sys
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from module.database.engine import AsyncSessionLocal
from module.domain.models.bangumi import Bangumi
from module.domain.models.torrent import Torrent
from module.repositories.bangumi import BangumiRepository
from module.repositories.series import SeriesRepository
from module.repositories.torrent import TorrentRepository
from module.services.identity_resolver import IdentityResolver
from module.mikan.parser import MikanRef
from module.domain.text.normalize import normalize_title  # added in Plan 02 Task 2


logger = logging.getLogger(__name__)

_MIKAN_RSS_RE = re.compile(
    r"mikan(?:ani|ime)?\.(?:me|tv)/RSS/Bangumi\?bangumiId=(\d+)"
    r"(?:&subgroupid=(\d+))?",
    re.IGNORECASE,
)


def extract_mikan_ids_from_rss(
    rss_link: Optional[str],
) -> tuple[Optional[int], Optional[int]]:
    """Return (mikan_bangumi_id, mikan_subgroup_id) extracted from rss_link
    or (None, None) when the link isn't a Mikan RSS URL."""
    if not rss_link:
        return None, None
    match = _MIKAN_RSS_RE.search(rss_link)
    if not match:
        return None, None
    bangumi_id = int(match.group(1))
    subgroup_id = int(match.group(2)) if match.group(2) is not None else None
    return bangumi_id, subgroup_id


async def backfill_one_bangumi(session: AsyncSession, bangumi: Bangumi) -> None:
    """Resolve a Series for `bangumi` and link via series_id /
    mikan_subgroup_id. No-op when already linked."""
    if bangumi.series_id is not None:
        return

    mikan_bangumi_id, mikan_subgroup_id = extract_mikan_ids_from_rss(
        bangumi.rss_link
    )

    mikan_ref: Optional[MikanRef] = None
    if mikan_bangumi_id is not None:
        mikan_ref = MikanRef(
            mikan_bangumi_id=mikan_bangumi_id,
            mikan_subgroup_id=mikan_subgroup_id or 0,
            canonical_title=bangumi.official_title,
            poster_url=bangumi.poster_link,
        )

    raw_title = bangumi.official_title or bangumi.title_raw or "Untitled"
    norm, cour = normalize_title(raw_title)

    resolver = IdentityResolver(SeriesRepository(session))
    resolved = await resolver.resolve(
        mikan_ref=mikan_ref,
        normalized_title=norm,
        season=bangumi.season,
        cour_part=cour,
        raw_title_for_root=raw_title,
    )

    bangumi.series_id = resolved.series.id
    bangumi.mikan_subgroup_id = mikan_subgroup_id
    if bangumi.observed_groups is None:
        # Seed observed_groups with the current group_name
        import json
        bangumi.observed_groups = json.dumps([bangumi.group_name or "Unknown"])
    await session.flush()


async def backfill_torrents_for_bangumi(
    session: AsyncSession, bangumi: Bangumi
) -> int:
    """Propagate bangumi's resolved Mikan IDs onto its torrents that haven't
    been backfilled yet. Returns the number of rows updated."""
    if bangumi.series_id is None:
        return 0

    series = await SeriesRepository(session).get_by_id(bangumi.series_id)
    if series is None:
        return 0
    mikan_bid = series.mikan_bangumi_id
    mikan_sid = bangumi.mikan_subgroup_id

    if mikan_bid is None and mikan_sid is None:
        return 0

    stmt = (
        update(Torrent)
        .where(
            Torrent.bangumi_id == bangumi.id,
            Torrent.mikan_bangumi_id.is_(None),
        )
        .values(mikan_bangumi_id=mikan_bid, mikan_subgroup_id=mikan_sid)
    )
    result = await session.execute(stmt)
    await session.flush()
    return result.rowcount


async def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    async with async_session_factory() as session:
        all_bangumi = (
            await session.execute(select(Bangumi).where(Bangumi.deleted == False))
        ).scalars().all()
        logger.info("Backfilling %d bangumi rows", len(all_bangumi))

        bangumi_count = 0
        torrent_count = 0
        for bangumi in all_bangumi:
            await backfill_one_bangumi(session, bangumi)
            bangumi_count += 1
            torrent_count += await backfill_torrents_for_bangumi(session, bangumi)

        await session.commit()
        logger.info(
            "Backfill complete: %d bangumi linked, %d torrents updated",
            bangumi_count,
            torrent_count,
        )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && uv run pytest src/tests/test_scripts/test_backfill_series.py -v`
Expected: 6 PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/scripts/__init__.py \
        backend/scripts/backfill_series.py \
        backend/src/tests/test_scripts/__init__.py \
        backend/src/tests/test_scripts/test_backfill_series.py
git commit -m "feat: backfill_series script (spec §13.2 phases 3-5)"
```

---

## Task 8: `scripts/migrate_duplicates.py`

**Files:**
- Create: `backend/scripts/migrate_duplicates.py`
- Create: `backend/src/tests/test_scripts/test_migrate_duplicates.py`

**Background:** Once `backfill_series.py` has run, duplicate bangumi (rows 91 + 93 in the production snapshot) share the same `(series_id, mikan_subgroup_id)` tuple. This script finds them, applies winner rules from spec §11.1, and calls `BangumiMergeService.merge()` to fold each loser into a winner. Two modes: `--dry-run` prints the planned merges and exits with rc 0; `--execute` performs them and writes `bangumi_merge_history`.

**Winner rules (spec §11.1, applied in order):**
1. `added=True` ranks above `added=False`
2. Higher torrent count wins
3. Newer `updated_at` wins

**Pairs already in `bangumi_merge_history` are skipped** (spec §11.4 permanent blacklist).

- [ ] **Step 1: Write the failing tests**

```python
# backend/src/tests/test_scripts/test_migrate_duplicates.py
"""Tests for scripts/migrate_duplicates.py."""
import json
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.migrate_duplicates import (  # noqa: E402
    find_duplicate_groups,
    pick_winner,
    plan_merges,
    execute_merges,
)

from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.domain.models.torrent import Torrent
from module.repositories.merge_history import BangumiMergeHistoryRepository


async def _seed_series(db_session, mikan_id) -> Series:
    s = Series(
        canonical_title="X", normalized_title="x", season=1,
        root_path="/p/X", pending_review=False, mikan_bangumi_id=mikan_id,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.mark.integration
async def test_find_duplicate_groups_picks_shared_subgroup(db_session):
    s = await _seed_series(db_session, 100)
    a = Bangumi(
        official_title="A", title_raw="A", season=1, group_name="G1",
        rss_link="", series_id=s.id, mikan_subgroup_id=1,
    )
    b = Bangumi(
        official_title="A", title_raw="A", season=1, group_name="G2",
        rss_link="", series_id=s.id, mikan_subgroup_id=1,
    )
    c = Bangumi(
        official_title="A", title_raw="A", season=1, group_name="G3",
        rss_link="", series_id=s.id, mikan_subgroup_id=2,  # different sub → not a dup
    )
    db_session.add_all([a, b, c])
    await db_session.flush()

    groups = await find_duplicate_groups(db_session)
    assert len(groups) == 1
    assert {row.id for row in groups[0]} == {a.id, b.id}


@pytest.mark.integration
async def test_pick_winner_prefers_added_then_torrent_count(db_session):
    s = await _seed_series(db_session, 200)
    a = Bangumi(
        official_title="A", title_raw="A", season=1, group_name="G1",
        rss_link="", series_id=s.id, mikan_subgroup_id=1, added=False,
    )
    b = Bangumi(
        official_title="A", title_raw="A", season=1, group_name="G2",
        rss_link="", series_id=s.id, mikan_subgroup_id=1, added=True,
    )
    db_session.add_all([a, b])
    await db_session.flush()

    winner_id = await pick_winner(db_session, [a, b])
    assert winner_id == b.id


@pytest.mark.integration
async def test_pick_winner_breaks_tie_on_torrent_count(db_session):
    s = await _seed_series(db_session, 300)
    a = Bangumi(
        official_title="A", title_raw="A", season=1, group_name="G1",
        rss_link="", series_id=s.id, mikan_subgroup_id=1, added=False,
    )
    b = Bangumi(
        official_title="A", title_raw="A", season=1, group_name="G2",
        rss_link="", series_id=s.id, mikan_subgroup_id=1, added=False,
    )
    db_session.add_all([a, b])
    await db_session.flush()
    # Give `b` two torrents
    db_session.add_all([
        Torrent(name="t1", url="u", hash="h1", bangumi_id=b.id),
        Torrent(name="t2", url="u", hash="h2", bangumi_id=b.id),
    ])
    await db_session.flush()
    winner_id = await pick_winner(db_session, [a, b])
    assert winner_id == b.id


@pytest.mark.integration
async def test_plan_merges_skips_blacklisted_pairs(db_session):
    s = await _seed_series(db_session, 400)
    a = Bangumi(
        official_title="A", title_raw="A", season=1, group_name="G1",
        rss_link="", series_id=s.id, mikan_subgroup_id=1, added=True,
    )
    b = Bangumi(
        official_title="A", title_raw="A", season=1, group_name="G2",
        rss_link="", series_id=s.id, mikan_subgroup_id=1, added=False,
    )
    db_session.add_all([a, b])
    await db_session.flush()

    # Pre-blacklist the pair
    await BangumiMergeHistoryRepository(db_session).create(
        winner_id=a.id, loser_id=b.id,
        loser_snapshot={}, moved_torrent_ids=[], dropped_torrents=[],
        merge_reason="prior", merged_by="auto_migration",
    )

    plans = await plan_merges(db_session)
    assert plans == []


@pytest.mark.integration
async def test_execute_merges_writes_history_and_soft_deletes(db_session):
    s = await _seed_series(db_session, 500)
    winner = Bangumi(
        official_title="W", title_raw="W", season=1, group_name="WG",
        rss_link="", series_id=s.id, mikan_subgroup_id=7, added=True,
    )
    loser = Bangumi(
        official_title="L", title_raw="L", season=1, group_name="LG",
        rss_link="", series_id=s.id, mikan_subgroup_id=7, added=False,
    )
    db_session.add_all([winner, loser])
    await db_session.flush()

    plans = await plan_merges(db_session)
    assert len(plans) == 1

    n = await execute_merges(db_session, plans)
    assert n == 1
    await db_session.refresh(loser)
    assert loser.deleted is True
    histories = await BangumiMergeHistoryRepository(db_session).list_all()
    assert len(histories) == 1
    assert histories[0].winner_bangumi_id == winner.id
    assert histories[0].loser_bangumi_id == loser.id
    assert histories[0].merge_reason == "mikan_id_match"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest src/tests/test_scripts/test_migrate_duplicates.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the duplicate-migration module**

Create `backend/scripts/migrate_duplicates.py`:

```python
"""Auto-merge duplicate bangumi rows produced by the legacy identity scheme.

Usage (from backend/):
  uv run python -m scripts.migrate_duplicates --dry-run
  uv run python -m scripts.migrate_duplicates --execute

Run AFTER scripts/backfill_series.py has linked every bangumi to a Series.
Duplicate detection is purely DB-driven: same (series_id, mikan_subgroup_id)
on undeleted rows, OR same (series_id, rss_id) when mikan_subgroup_id IS NULL.

Winner rules (spec §11.1, applied in order):
  1. added=True ranks above added=False
  2. Higher torrent_count
  3. Newer updated_at

Pairs already present in bangumi_merge_history are skipped (spec §11.4).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from module.database.engine import async_session_factory
from module.domain.models.bangumi import Bangumi
from module.domain.models.torrent import Torrent
from module.repositories.merge_history import BangumiMergeHistoryRepository
from module.services.bangumi_merge import BangumiMergeService

logger = logging.getLogger(__name__)


@dataclass
class MergePlan:
    winner_id: int
    loser_id: int
    series_id: int
    mikan_subgroup_id: int | None
    reason: str  # 'mikan_id_match' or 'fallback_key_match'


async def find_duplicate_groups(session: AsyncSession) -> list[list[Bangumi]]:
    """Return groups of >= 2 bangumi rows sharing the same identity key."""
    # Mikan-identity duplicates: (series_id, mikan_subgroup_id) both non-null.
    mikan_stmt = (
        select(Bangumi.series_id, Bangumi.mikan_subgroup_id)
        .where(
            Bangumi.deleted == False,
            Bangumi.series_id.is_not(None),
            Bangumi.mikan_subgroup_id.is_not(None),
        )
        .group_by(Bangumi.series_id, Bangumi.mikan_subgroup_id)
        .having(func.count("*") > 1)
    )
    mikan_keys = (await session.execute(mikan_stmt)).all()

    # Fallback-identity duplicates: (series_id, rss_id) where mikan_subgroup_id IS NULL.
    fallback_stmt = (
        select(Bangumi.series_id, Bangumi.rss_id)
        .where(
            Bangumi.deleted == False,
            Bangumi.series_id.is_not(None),
            Bangumi.mikan_subgroup_id.is_(None),
            Bangumi.rss_id.is_not(None),
        )
        .group_by(Bangumi.series_id, Bangumi.rss_id)
        .having(func.count("*") > 1)
    )
    fallback_keys = (await session.execute(fallback_stmt)).all()

    groups: list[list[Bangumi]] = []
    for series_id, sub_id in mikan_keys:
        rows = (await session.execute(
            select(Bangumi).where(
                Bangumi.series_id == series_id,
                Bangumi.mikan_subgroup_id == sub_id,
                Bangumi.deleted == False,
            )
        )).scalars().all()
        groups.append(list(rows))
    for series_id, rss_id in fallback_keys:
        rows = (await session.execute(
            select(Bangumi).where(
                Bangumi.series_id == series_id,
                Bangumi.rss_id == rss_id,
                Bangumi.mikan_subgroup_id.is_(None),
                Bangumi.deleted == False,
            )
        )).scalars().all()
        groups.append(list(rows))
    return groups


async def _torrent_count(session: AsyncSession, bangumi_id: int) -> int:
    stmt = select(func.count(Torrent.id)).where(Torrent.bangumi_id == bangumi_id)
    return int((await session.execute(stmt)).scalar() or 0)


async def pick_winner(session: AsyncSession, group: list[Bangumi]) -> int:
    """Return the bangumi_id that should keep its torrents (winner)."""
    counts = {b.id: await _torrent_count(session, b.id) for b in group}

    def key(b: Bangumi) -> tuple:
        return (
            0 if b.added else 1,           # added=True first
            -counts.get(b.id, 0),           # more torrents first
            -(b.updated_at.timestamp() if b.updated_at else 0),  # newer first
        )

    winner = min(group, key=key)
    return winner.id


async def plan_merges(session: AsyncSession) -> list[MergePlan]:
    history_repo = BangumiMergeHistoryRepository(session)
    plans: list[MergePlan] = []
    for group in await find_duplicate_groups(session):
        if len(group) < 2:
            continue
        winner_id = await pick_winner(session, group)
        for row in group:
            if row.id == winner_id:
                continue
            if await history_repo.is_pair_blacklisted(winner_id, row.id):
                logger.info(
                    "skip pair (winner=%d, loser=%d) — already in history",
                    winner_id, row.id,
                )
                continue
            reason = (
                "mikan_id_match" if row.mikan_subgroup_id is not None
                else "fallback_key_match"
            )
            plans.append(MergePlan(
                winner_id=winner_id,
                loser_id=row.id,
                series_id=row.series_id,
                mikan_subgroup_id=row.mikan_subgroup_id,
                reason=reason,
            ))
    return plans


async def execute_merges(
    session: AsyncSession, plans: list[MergePlan]
) -> int:
    svc = BangumiMergeService(session)
    n = 0
    for p in plans:
        await svc.merge(
            winner_id=p.winner_id,
            loser_id=p.loser_id,
            merge_reason=p.reason,
            merged_by="auto_migration",
        )
        n += 1
    await session.commit()
    return n


async def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true",
                       help="print planned merges and exit")
    group.add_argument("--execute", action="store_true",
                       help="perform the merges and write history")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    async with async_session_factory() as session:
        plans = await plan_merges(session)
        if not plans:
            logger.info("No duplicates to merge.")
            return 0

        logger.info("Planned merges (%d):", len(plans))
        for p in plans:
            logger.info(
                "  series=%d sub=%s reason=%s  winner=%d  loser=%d",
                p.series_id, p.mikan_subgroup_id, p.reason,
                p.winner_id, p.loser_id,
            )

        if args.dry_run:
            return 0

        n = await execute_merges(session, plans)
        logger.info("Executed %d merges.", n)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && uv run pytest src/tests/test_scripts/test_migrate_duplicates.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/scripts/migrate_duplicates.py \
        backend/src/tests/test_scripts/test_migrate_duplicates.py
git commit -m "feat: migrate_duplicates CLI with dry-run/execute (spec §11.1)"
```

---

## Task 9: Migration 0008 — lockdown bangumi identity (destructive)

**Files:**
- Create: `backend/alembic/versions/0008_lockdown_bangumi_identity.py`
- Create: `backend/src/tests/test_migrations/test_0008_lockdown.py`
- Modify: `backend/src/module/domain/models/bangumi.py`
- Modify: `backend/src/module/repositories/bangumi.py`

**Background:** Stage C — the destructive lockdown. The migration:
1. Drops legacy bangumi columns: `save_path`, `official_title`, `year`, `season`, `season_raw`, `title_raw`, `poster_link`.
2. Drops the legacy `uq_bangumi_title_season_group` UNIQUE.
3. Makes `series_id` NOT NULL.
4. Adds two partial UNIQUE indexes:
   - `uq_bangumi_series_subgroup` on `(series_id, mikan_subgroup_id)` WHERE `deleted=0`
   - `uq_bangumi_series_rss_fallback` on `(series_id, rss_id)` WHERE `mikan_subgroup_id IS NULL AND deleted=0`

The ORM update in this same task drops the legacy `Mapped[]` columns and adds `@property` accessors (`official_title`, `season`, `year`, `save_path`, `poster_link`) that delegate to `self.series` so existing read-side callers (API routers, search, poster service) keep compiling. Plan 05 will rewrite those callers to use `.series.canonical_title` etc. directly and remove the shims.

`BangumiRepository.create()` must also drop its composite-key validation (which references `official_title`/`season`/`group_name` as identity).

- [ ] **Step 1: Write the failing test**

```python
# backend/src/tests/test_migrations/test_0008_lockdown.py
"""Tests for migration 0008: bangumi identity lockdown (destructive)."""
import os
import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).parent.parent.parent.parent


def _run_alembic(target: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "alembic", "upgrade", target],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
    )


def _bangumi_columns(db: Path) -> set[str]:
    engine = sa.create_engine(f"sqlite:///{db}")
    inspector = sa.inspect(engine)
    return {c["name"] for c in inspector.get_columns("bangumi")}


@pytest.mark.integration
def test_0008_drops_legacy_bangumi_columns(tmp_path):
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0008_lockdown_bangumi_identity", env).returncode == 0

    cols = _bangumi_columns(db)
    for dropped in (
        "save_path", "official_title", "year", "season",
        "season_raw", "title_raw", "poster_link",
    ):
        assert dropped not in cols, f"{dropped} should be dropped by 0008"


@pytest.mark.integration
def test_0008_makes_series_id_not_null(tmp_path):
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0008_lockdown_bangumi_identity", env).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        with pytest.raises(sa.exc.IntegrityError):
            conn.execute(sa.text(
                "INSERT INTO bangumi (rss_id, group_name, eps_collect, "
                "offset, filter, rss_link, added, deleted, pending_review, "
                "created_at, updated_at, version, active) "
                "VALUES (NULL, 'g', 0, 0, '720', '', 0, 0, 0, "
                "'2026-01-01', '2026-01-01', 1, 1)"
            ))


@pytest.mark.integration
def test_0008_partial_unique_blocks_dup_subgroup(tmp_path):
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0008_lockdown_bangumi_identity", env).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (1, 'X', 'x', 1, '/p/X', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))
        conn.execute(sa.text(
            "INSERT INTO bangumi (rss_id, group_name, eps_collect, "
            "offset, filter, rss_link, added, deleted, pending_review, "
            "created_at, updated_at, version, series_id, mikan_subgroup_id, "
            "active) "
            "VALUES (NULL, 'g1', 0, 0, '720', '', 0, 0, 0, "
            "'2026-01-01', '2026-01-01', 1, 1, 7, 1)"
        ))

    with engine.begin() as conn:
        with pytest.raises(sa.exc.IntegrityError):
            conn.execute(sa.text(
                "INSERT INTO bangumi (rss_id, group_name, eps_collect, "
                "offset, filter, rss_link, added, deleted, pending_review, "
                "created_at, updated_at, version, series_id, "
                "mikan_subgroup_id, active) "
                "VALUES (NULL, 'g2', 0, 0, '720', '', 0, 0, 0, "
                "'2026-01-01', '2026-01-01', 1, 1, 7, 1)"
            ))


@pytest.mark.integration
def test_0008_partial_unique_skips_deleted_rows(tmp_path):
    """Soft-deleted rows must NOT occupy the unique slot (else merge undo
    can't restore + new bangumi can't fill the slot)."""
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0008_lockdown_bangumi_identity", env).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (1, 'X', 'x', 1, '/p/X', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))
        # First row is deleted=1 — should NOT block the second insert
        conn.execute(sa.text(
            "INSERT INTO bangumi (rss_id, group_name, eps_collect, "
            "offset, filter, rss_link, added, deleted, pending_review, "
            "created_at, updated_at, version, series_id, mikan_subgroup_id, "
            "active) "
            "VALUES (NULL, 'g1', 0, 0, '720', '', 0, 1, 0, "
            "'2026-01-01', '2026-01-01', 1, 1, 7, 0)"
        ))
        conn.execute(sa.text(
            "INSERT INTO bangumi (rss_id, group_name, eps_collect, "
            "offset, filter, rss_link, added, deleted, pending_review, "
            "created_at, updated_at, version, series_id, mikan_subgroup_id, "
            "active) "
            "VALUES (NULL, 'g2', 0, 0, '720', '', 0, 0, 0, "
            "'2026-01-01', '2026-01-01', 1, 1, 7, 1)"
        ))


@pytest.mark.integration
def test_0008_fallback_unique_uses_rss_when_subgroup_null(tmp_path):
    db = tmp_path / "test.db"
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db}"
    assert _run_alembic("0008_lockdown_bangumi_identity", env).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO series (mikan_bangumi_id, canonical_title, "
            "normalized_title, season, root_path, default_offset, "
            "pending_review, created_at, updated_at, version) "
            "VALUES (NULL, 'X', 'x', 1, '/p/X', 0, 0, "
            "'2026-01-01', '2026-01-01', 1)"
        ))
        conn.execute(sa.text(
            "INSERT INTO rssitem (name, url, parser, aggregate, enabled, "
            "created_at, updated_at, version) "
            "VALUES ('r1', 'u1', 'mikan', 0, 1, "
            "'2026-01-01', '2026-01-01', 1)"
        ))
        conn.execute(sa.text(
            "INSERT INTO bangumi (rss_id, group_name, eps_collect, "
            "offset, filter, rss_link, added, deleted, pending_review, "
            "created_at, updated_at, version, series_id, mikan_subgroup_id, "
            "active) "
            "VALUES (1, 'g1', 0, 0, '720', '', 0, 0, 0, "
            "'2026-01-01', '2026-01-01', 1, 1, NULL, 1)"
        ))
    with engine.begin() as conn:
        with pytest.raises(sa.exc.IntegrityError):
            conn.execute(sa.text(
                "INSERT INTO bangumi (rss_id, group_name, eps_collect, "
                "offset, filter, rss_link, added, deleted, pending_review, "
                "created_at, updated_at, version, series_id, "
                "mikan_subgroup_id, active) "
                "VALUES (1, 'g2', 0, 0, '720', '', 0, 0, 0, "
                "'2026-01-01', '2026-01-01', 1, 1, NULL, 1)"
            ))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest src/tests/test_migrations/test_0008_lockdown.py -v`
Expected: FAIL — revision does not exist.

- [ ] **Step 3: Author migration 0008**

Create `backend/alembic/versions/0008_lockdown_bangumi_identity.py`:

```python
"""lockdown_bangumi_identity

Revision ID: 0008_lockdown_bangumi_identity
Revises: 0007_add_bangumi_series_link
Create Date: 2026-04-18

Stage C (destructive). Drops legacy bangumi columns now that
backfill_series.py + migrate_duplicates.py have produced a clean
series_id-driven identity. Adds the partial UNIQUE constraints that lock
identity in place.

PRECONDITIONS (caller must verify before running upgrade head past 0007):
  - Every undeleted bangumi has series_id NOT NULL
  - Duplicates have been merged (otherwise UNIQUE blows up at upgrade)
  - bangumi.db has been backed up

Downgrade restores the dropped columns as nullable but cannot restore
their data — restore from backup if you need the legacy values.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_lockdown_bangumi_identity"
down_revision: Union[str, Sequence[str], None] = "0007_add_bangumi_series_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("bangumi") as batch_op:
        # Drop legacy composite-key UNIQUE
        batch_op.drop_constraint(
            "uq_bangumi_title_season_group", type_="unique"
        )
        # Drop legacy columns
        batch_op.drop_column("save_path")
        batch_op.drop_column("official_title")
        batch_op.drop_column("year")
        batch_op.drop_column("season")
        batch_op.drop_column("season_raw")
        batch_op.drop_column("title_raw")
        batch_op.drop_column("poster_link")
        # Make series_id NOT NULL
        batch_op.alter_column(
            "series_id", existing_type=sa.Integer(), nullable=False
        )

    # Partial UNIQUEs (encoded via op.execute since SQLAlchemy autogenerate
    # can't round-trip them; mirrored on the ORM via Index(sqlite_where=...))
    op.execute(
        "CREATE UNIQUE INDEX uq_bangumi_series_subgroup "
        "ON bangumi (series_id, mikan_subgroup_id) WHERE deleted = 0"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_bangumi_series_rss_fallback "
        "ON bangumi (series_id, rss_id) "
        "WHERE mikan_subgroup_id IS NULL AND deleted = 0"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_bangumi_series_rss_fallback")
    op.execute("DROP INDEX IF EXISTS uq_bangumi_series_subgroup")

    with op.batch_alter_table("bangumi") as batch_op:
        batch_op.alter_column(
            "series_id", existing_type=sa.Integer(), nullable=True
        )
        batch_op.add_column(sa.Column("poster_link", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("title_raw", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("season_raw", sa.String(), nullable=True))
        batch_op.add_column(sa.Column(
            "season", sa.Integer(), nullable=True
        ))
        batch_op.add_column(sa.Column("year", sa.String(), nullable=True))
        batch_op.add_column(sa.Column(
            "official_title", sa.String(), nullable=True
        ))
        batch_op.add_column(sa.Column("save_path", sa.String(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_bangumi_title_season_group",
            ["official_title", "season", "group_name"],
        )
```

- [ ] **Step 4: Update the env.py allow-list to include the new partial indexes**

Edit `backend/alembic/env.py`. Update `_include_object` index names tuple:

```python
    if type_ == "index" and name in (
        "idx_torrent_hash_bangumi",
        "uq_series_fallback",
        "uq_series_fallback_null_cour",
        "uq_bangumi_series_subgroup",
        "uq_bangumi_series_rss_fallback",
    ):
        return False
```

- [ ] **Step 5: Update `Bangumi` ORM — drop legacy columns + add property shims**

Edit `backend/src/module/domain/models/bangumi.py`. Replace the file with:

```python
"""Bangumi domain model (post-0008 lockdown).

Identity is driven by (series_id, mikan_subgroup_id) for Mikan-sourced rows
and (series_id, rss_id) for fallback rows. Display-side fields like
canonical_title, save_path, year, poster_url live on Series; the @property
accessors below delegate so that read-side callers (API routes, search,
poster) keep compiling. Plan 05 rewrites those callers to read from
`bangumi.series` directly and these shims will be removed.
"""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, ForeignKey, Index, Integer, String, Text, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, VersionMixin

if TYPE_CHECKING:
    from .series import Series


class Bangumi(Base, TimestampMixin, VersionMixin):
    __tablename__ = "bangumi"

    __table_args__ = (
        Index(
            "uq_bangumi_series_subgroup",
            "series_id", "mikan_subgroup_id",
            unique=True,
            sqlite_where=text("deleted = 0"),
        ),
        Index(
            "uq_bangumi_series_rss_fallback",
            "series_id", "rss_id",
            unique=True,
            sqlite_where=text(
                "mikan_subgroup_id IS NULL AND deleted = 0"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rss_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("rssitem.id"), nullable=True
    )
    series_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("series.id"), nullable=False, index=True
    )
    mikan_subgroup_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    # Subscription + filter behaviour
    group_name: Mapped[str] = mapped_column(
        String, nullable=False, default="Unknown"
    )
    dpi: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    subtitle: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    eps_collect: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filter: Mapped[str] = mapped_column(
        String, nullable=False, default="720,\\d+-\\d+"
    )
    rss_link: Mapped[str] = mapped_column(String, nullable=False, default="")
    added: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rule_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pending_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    global_filter_matches: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )

    # New v2 fields
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    path_override: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    observed_groups: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    series: Mapped["Series"] = relationship("Series", lazy="select")

    # ---- Read-side compat shims (delegated to series, removed in Plan 05) ----

    @property
    def official_title(self) -> Optional[str]:
        return self.series.canonical_title if self.series is not None else None

    @property
    def season(self) -> int:
        return self.series.season if self.series is not None else 1

    @property
    def year(self) -> Optional[int]:
        return self.series.year if self.series is not None else None

    @property
    def save_path(self) -> Optional[str]:
        if self.path_override:
            return self.path_override
        return self.series.root_path if self.series is not None else None

    @property
    def poster_link(self) -> Optional[str]:
        return self.series.poster_url if self.series is not None else None

    # title_raw / season_raw are parser intermediates — not exposed.
```

- [ ] **Step 6: Drop composite-key validation in `BangumiRepository.create()`**

Edit `backend/src/module/repositories/bangumi.py`. Replace the existing `create()` and `get_by_composite_key()` methods. Remove `get_by_composite_key()` entirely. Replace `create()` body:

```python
    async def create(self, data: dict) -> Bangumi:
        if "group_name" in data and not data["group_name"]:
            data["group_name"] = "Unknown"
        bangumi = Bangumi(**data)
        self.session.add(bangumi)
        await self.session.flush()
        await self.session.refresh(bangumi)
        return bangumi
```

Also delete the `get_active()` filter on `pending_review` if it depends on dropped columns — it doesn't, so leave it. But `get_pending_review()` is fine. Just ensure no lingering reference to `Bangumi.official_title` / `season` exists in this file. Run:

`cd backend && grep -n "official_title\|\.season\|\.year\|\.save_path\|\.poster_link\|title_raw\|season_raw" src/module/repositories/bangumi.py`

If any references remain in queries (e.g. `find_by_official_title`), delete those methods (they referenced dropped columns and have no callers post-Plan 05). Confirm they're unused by:

`cd backend && grep -rn "find_by_official_title\|get_by_composite_key" src/ --include="*.py"`

Delete every dead method.

- [ ] **Step 7: Run the migration tests**

Run: `cd backend && uv run pytest src/tests/test_migrations/test_0008_lockdown.py -v`
Expected: 5 PASS.

- [ ] **Step 8: Run the full migration chain**

Run: `cd backend && uv run pytest src/tests/test_migrations/ -v`
Expected: ALL PASS.

- [ ] **Step 9: Run repo + domain suites — expect breakage in callers using dropped fields**

Run: `cd backend && uv run pytest src/tests/test_repositories/ src/tests/test_domain/ -q`

If any test asserts `bangumi.official_title=...` as a constructor kwarg or in a dict, update it to set `series_id` + use `series.canonical_title` (or rely on the property). For each failure, fix the test in this same task — they're all symptoms of the legacy field shape. Document each fix in the commit message.

- [ ] **Step 10: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/alembic/versions/0008_lockdown_bangumi_identity.py \
        backend/alembic/env.py \
        backend/src/module/domain/models/bangumi.py \
        backend/src/module/repositories/bangumi.py \
        backend/src/tests/test_migrations/test_0008_lockdown.py \
        backend/src/tests/test_repositories/ \
        backend/src/tests/test_domain/
git commit -m "feat: alembic 0008 lockdown bangumi identity + ORM rewrite"
```

---

## Task 10: Renamer refactor — series-driven paths + active filter + conflict detection

**Files:**
- Modify: `backend/src/module/services/renamer.py`
- Modify: `backend/src/module/repositories/torrent.py`
- Create: `backend/src/tests/test_services/test_renamer_active_filter.py`
- Create: `backend/src/tests/test_services/test_renamer_conflict.py`

**Background:** Per spec §10:
1. The renamer derives `bangumi_name` from `bangumi.series.canonical_title` (was `bangumi.official_title`), `season` from `bangumi.series.season`, and `effective_root` from `bangumi.path_override or bangumi.series.root_path`.
2. Inactive bangumi (`active=false`) must be invisible to the rename pipeline so simultaneously-tracked sibling subgroups don't fight over filenames.
3. When the renamer is about to write a target path that already exists for a *different* hash, it logs a warning, **skips the file** (does not abort the whole batch), and surfaces the conflict in the return value so Plan 05's Dashboard can pick it up.

The compat property `bangumi.official_title` (Task 9) means most call sites in `renamer.py` still work — but `bangumi.season` is the same identifier name as the property, so reading it works too. The actual semantic change is wiring `effective_root` and the active filter; the conflict path is brand new.

`generate_rename_path()` itself stays untouched — it consumes `bangumi_name` (str), not the Bangumi row.

- [ ] **Step 1: Write the failing tests**

```python
# backend/src/tests/test_services/test_renamer_active_filter.py
"""Inactive bangumi must not reach the renamer."""
import pytest

from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.domain.models.torrent import Torrent
from module.repositories.torrent import TorrentRepository


@pytest.mark.integration
async def test_get_unrenamed_filters_inactive_bangumi(db_session):
    s = Series(
        canonical_title="X", normalized_title="x", season=1,
        root_path="/p/X", pending_review=False,
    )
    db_session.add(s)
    await db_session.flush()

    active = Bangumi(
        group_name="A", rss_link="", series_id=s.id, active=True,
    )
    inactive = Bangumi(
        group_name="B", rss_link="", series_id=s.id, mikan_subgroup_id=2,
        active=False,
    )
    db_session.add_all([active, inactive])
    await db_session.flush()

    db_session.add_all([
        Torrent(name="ta", url="u", hash="ha", bangumi_id=active.id),
        Torrent(name="ti", url="u", hash="hi", bangumi_id=inactive.id),
    ])
    await db_session.flush()

    repo = TorrentRepository(db_session)
    rows = await repo.get_unrenamed()
    ids = {t.id for t in rows}
    # Only the torrent on the active bangumi may surface
    assert any(t.bangumi_id == active.id for t in rows)
    assert not any(t.bangumi_id == inactive.id for t in rows)
```

```python
# backend/src/tests/test_services/test_renamer_conflict.py
"""Rename target collisions are reported, not crashed (spec §10.3)."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from module.domain.models.bangumi import Bangumi
from module.domain.models.series import Series
from module.domain.models.torrent import Torrent
from module.services.renamer import RenamerService


class _FakeFile:
    def __init__(self, name):
        self.name = name


class _FakeTorrentInfo:
    def __init__(self, *, name, hash, files, save_path="/dl"):
        self.name = name
        self.hash = hash
        self.files = files
        self.save_path = save_path


@pytest.mark.integration
async def test_rename_records_conflict_when_target_exists(db_session, monkeypatch):
    s = Series(
        canonical_title="Demo", normalized_title="demo", season=1,
        root_path="/dl/Demo", pending_review=False, mikan_bangumi_id=1,
    )
    db_session.add(s)
    await db_session.flush()
    bangumi = Bangumi(
        group_name="G", rss_link="", series_id=s.id, mikan_subgroup_id=1,
        active=True,
    )
    db_session.add(bangumi)
    await db_session.flush()
    torrent = Torrent(
        name="src", url="u", hash="hash-new", bangumi_id=bangumi.id,
    )
    db_session.add(torrent)
    await db_session.flush()

    downloader = MagicMock()
    downloader.torrents_info = AsyncMock(return_value=[
        _FakeTorrentInfo(
            name="src", hash="hash-new",
            files=[_FakeFile("Demo S01E01.mkv")],
        ),
    ])
    # Simulate target-already-exists by making rename_file return False with
    # a "destination already exists" sentinel via raising.
    downloader.torrents_rename_file = AsyncMock(return_value=False)

    svc = RenamerService(db_session)
    # Force the renamer to detect a conflict via a stub helper; spec scope is
    # "log + report", not OS-level FS check. We monkeypatch the helper.
    monkeypatch.setattr(svc, "_target_exists_with_different_hash",
                        AsyncMock(return_value=True))

    result = await svc.rename_all(downloader)

    # The conflict must be reported via the return value; the torrent must
    # not be marked renamed_at.
    await db_session.refresh(torrent)
    assert torrent.renamed_at is None
    assert any(r.get("conflict") for r in result), result
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && uv run pytest src/tests/test_services/test_renamer_active_filter.py src/tests/test_services/test_renamer_conflict.py -v`
Expected: FAIL — active filter not in repo, `_target_exists_with_different_hash` not on RenamerService.

- [ ] **Step 3: Update `_unrenamed_base_stmt` to filter active bangumi**

Edit `backend/src/module/repositories/torrent.py`. Replace `_unrenamed_base_stmt`:

```python
    def _unrenamed_base_stmt(self):
        from module.domain.models.bangumi import Bangumi
        return (
            select(Torrent)
            .join(Bangumi, Bangumi.id == Torrent.bangumi_id)
            .where(
                and_(
                    Torrent.renamed_at.is_(None),
                    Torrent.state != TorrentState.EXCLUDED,
                    Bangumi.active == True,
                    Bangumi.deleted == False,
                )
            )
        )
```

- [ ] **Step 4: Wire `effective_root` + conflict detection in RenamerService**

Edit `backend/src/module/services/renamer.py`. Add the helper and modify `_rename_single_file` / `_rename_collection` to consult it.

After `_classify_files` (near the bottom of the class), add:

```python
    @staticmethod
    def effective_root(bangumi: Bangumi) -> Optional[str]:
        """Return path_override when set, else the linked series root_path."""
        if bangumi.path_override:
            return bangumi.path_override
        if bangumi.series is not None:
            return bangumi.series.root_path
        return None

    async def _target_exists_with_different_hash(
        self,
        downloader: "DownloaderProtocol",
        torrent_hash: str,
        target_path: str,
    ) -> bool:
        """Best-effort collision probe. Returns True when the downloader
        reports `target_path` already exists for a different hash. The
        downloader interface doesn't expose a direct check, so we ask for
        all completed torrents and look for a hash≠ that owns target_path.
        Subclasses or future downloader work may make this cheaper.
        """
        try:
            all_info = await downloader.torrents_info(status_filter="completed")
        except Exception:
            return False
        for info in all_info:
            if info.hash and info.hash.lower() == torrent_hash.lower():
                continue
            for f in getattr(info, "files", []) or []:
                if getattr(f, "name", None) == target_path:
                    return True
        return False
```

Add `Optional` to the imports if missing.

Modify `_rename_single_file` to consult the conflict probe before performing the rename. Replace the body of `_rename_single_file`:

```python
    async def _rename_single_file(
        self,
        torrent_info: Any,
        media_path: str,
        bangumi: Bangumi,
        downloader: DownloaderProtocol,
    ) -> tuple[bool, int, Optional[str]]:
        """Returns (success, file_count, conflict_target).

        conflict_target is a non-None target path string when a rename was
        skipped due to a collision (spec §10.3); the caller surfaces it in
        the return payload for Dashboard reporting.
        """
        ep = self.parser.torrent_parser(
            torrent_name=torrent_info.name,
            torrent_path=media_path,
            season=bangumi.season,
        )
        if not ep:
            logger.warning(
                f"[Renamer] Failed to parse: torrent_name={torrent_info.name}, "
                f"media_path={media_path}"
            )
            return False, 0, None

        new_path = self.generate_rename_path(
            ep, bangumi.official_title, self.rename_method
        )
        logger.info(
            f"[Renamer] Rename check: '{media_path}' -> '{new_path}' "
            f"(parsed season={ep.season}, target season={bangumi.season})"
        )

        if media_path == new_path:
            logger.debug(f"[Renamer] Skipped (same path): {media_path}")
            return True, 1, None

        if await self._target_exists_with_different_hash(
            downloader, torrent_info.hash, new_path,
        ):
            logger.warning(
                f"[Renamer] Conflict: '{new_path}' already exists for a "
                f"different torrent — skipping (spec §10.3)"
            )
            return False, 0, new_path

        success = await downloader.torrents_rename_file(
            torrent_info.hash, media_path, new_path
        )
        if not success:
            logger.warning(f"[Renamer] rename_torrent_file failed: {media_path}")
            return False, 0, None

        return True, 1, None
```

Adjust callers of `_rename_single_file` in `rename_all` and `rename_bangumi` to unpack the new third return value:

In `rename_all`, change:
```python
            if len(media_files) == 1:
                success, file_count = await self._rename_single_file(
                    torrent_info,
                    media_files[0],
                    bangumi,
                    downloader,
                )
```
to:
```python
            conflict_target: Optional[str] = None
            if len(media_files) == 1:
                success, file_count, conflict_target = await self._rename_single_file(
                    torrent_info,
                    media_files[0],
                    bangumi,
                    downloader,
                )
```

And update the `rename_successes` collection to also track conflicts:

```python
        rename_successes: list[tuple[int, int]] = []
        rename_conflicts: list[tuple[int, str]] = []
```

Inside the loop, when `conflict_target is not None`, append `(db_torrent.id, conflict_target)` to `rename_conflicts` and continue.

In the Phase 3 write block, extend the result dict:

```python
            for torrent_id, target in rename_conflicts:
                renamed_results.append(
                    {"torrent_id": torrent_id, "file_count": 0,
                     "conflict": target}
                )
```

Apply analogous changes in `rename_bangumi`. (Skip `_rename_collection` rewrite for this task; multi-file collision detection is unusual enough that Plan 05 can address it if needed.)

- [ ] **Step 5: Run the renamer tests**

Run: `cd backend && uv run pytest src/tests/test_services/test_renamer_active_filter.py src/tests/test_services/test_renamer_conflict.py src/tests/test_services/test_renamer.py -v`
Expected: PASS for new tests; PASS or quick-fix for the existing renamer test suite.

If any pre-existing renamer test breaks because it didn't set `series_id` on its bangumi fixture, fix the fixture (set `series_id` to a freshly created Series). Document each fix.

- [ ] **Step 6: Run the full repo + service suite**

Run: `cd backend && uv run pytest src/tests/test_repositories/ src/tests/test_services/ -q`
Expected: ALL PASS.

- [ ] **Step 7: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/src/module/services/renamer.py \
        backend/src/module/repositories/torrent.py \
        backend/src/tests/test_services/test_renamer_active_filter.py \
        backend/src/tests/test_services/test_renamer_conflict.py \
        backend/src/tests/test_services/test_renamer.py
git commit -m "feat: renamer uses series paths + active filter + conflict detection"
```

---

## Task 11: Collector + RSS engine — write series_id on bangumi creation

**Files:**
- Modify: `backend/src/module/services/collector.py`
- Modify: `backend/src/module/services/rss_engine.py`

**Background:** These two services are the only places that *create* `Bangumi` rows on the live RSS path. With Task 9 in place, `Bangumi.__init__` no longer accepts `official_title`, `save_path`, `year`, `season`, `season_raw`, `title_raw`, `poster_link`, so callers must:
1. Resolve a Series via `IdentityResolver` (Plan 03).
2. Create the bangumi with `series_id`, `mikan_subgroup_id` (extracted from rss_link via `extract_mikan_ids_from_rss` from Task 7), `active=True`, and the surviving columns (`group_name`, `rss_id`, `rss_link`, `filter`, `offset`, etc.).

Because Plan 05 fully rewires the RSS pipeline (Mikan resolver + pending_torrent_enrichment), Plan 04's job here is **minimal**: anywhere a Bangumi is constructed today via legacy fields, swap to series-aware construction. Read-side accesses to `bangumi.official_title` etc continue to work via the property shims, so no other changes are needed.

This is a refactor with substantial surface area. Do it as one task with frequent intra-task commits if needed.

- [ ] **Step 1: Survey the construction sites**

Run:
```bash
cd backend && grep -n "Bangumi(" src/module/services/collector.py src/module/services/rss_engine.py
```

For every `Bangumi(...)` call, note the fields being set.

Run:
```bash
cd backend && grep -n '"official_title"\|"title_raw"\|"season_raw"\|"save_path"\|"poster_link"' src/module/services/collector.py src/module/services/rss_engine.py
```

For every dict-literal that's then passed to `BangumiRepository.create(data)`, note the same.

- [ ] **Step 2: Refactor each construction site to series-driven shape**

For each construction site identified, replace the legacy fields with:

```python
from module.services.identity_resolver import IdentityResolver
from module.repositories.series import SeriesRepository
from module.utils.normalize import normalize_title
from module.mikan.parser import MikanRef
from scripts.backfill_series import extract_mikan_ids_from_rss

# Inside the construction code:
mikan_bangumi_id, mikan_subgroup_id = extract_mikan_ids_from_rss(rss_link)
mikan_ref = None
if mikan_bangumi_id is not None:
    mikan_ref = MikanRef(
        mikan_bangumi_id=mikan_bangumi_id,
        mikan_subgroup_id=mikan_subgroup_id or 0,
        canonical_title=parsed_title,
        poster_url=parsed_poster,
    )

norm, cour = normalize_title(parsed_title)
resolver = IdentityResolver(SeriesRepository(self.session))
resolved = await resolver.resolve(
    mikan_ref=mikan_ref,
    normalized_title=norm,
    season=parsed_season,
    cour_part=cour,
    raw_title_for_root=parsed_title,
)

bangumi_data = {
    "rss_id": rss_id,
    "rss_link": rss_link,
    "group_name": group_name or "Unknown",
    "filter": filter_str,
    "offset": offset,
    "series_id": resolved.series.id,
    "mikan_subgroup_id": mikan_subgroup_id,
    "active": True,
    # Optional surviving fields the parser produced:
    "dpi": dpi,
    "source": source,
    "subtitle": subtitle,
}
bangumi = await self.bangumi_repo.create(bangumi_data)
```

(Adapt local variable names and removed fields per call site. Do NOT pass `official_title`, `title_raw`, `season`, `season_raw`, `save_path`, `year`, `poster_link` — they're gone.)

If `_auto_create_bangumi` (or similar) does a "find existing then create" flow that previously used `BangumiRepository.get_by_composite_key`, replace the lookup with:

```python
existing = (
    await self.bangumi_repo.get_by_series_and_subgroup(
        resolved.series.id, mikan_subgroup_id
    )
    if mikan_subgroup_id is not None
    else await self.bangumi_repo.get_by_series_and_rss(
        resolved.series.id, rss_id
    )
)
if existing is not None:
    return existing
```

Plan 05 will harden this path with proper Mikan resolver wiring; Task 11 just keeps it compiling.

- [ ] **Step 3: Run the e2e suite**

Run: `cd backend && uv run pytest src/tests/test_e2e/ -q`
Expected: PASS for all tests that don't depend on dropped legacy bangumi field assertions. If a test fails because it asserts `bangumi.title_raw == "..."`, accept the known break — Task 14 sweeps the pre-existing test fixtures. Note each failure for Task 14.

If a test fails because the new construction path didn't write a series_id (programming error in Task 11), fix it now.

- [ ] **Step 4: Run unit + repo + services tests**

Run: `cd backend && uv run pytest src/tests/test_repositories/ src/tests/test_services/ src/tests/test_domain/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/src/module/services/collector.py \
        backend/src/module/services/rss_engine.py
git commit -m "refactor: collector + rss_engine create bangumi via Series identity"
```

---

## Task 12: Drop dead bangumi fields from peripheral services

**Files (touch only what breaks):**
- Modify (only if compile-broken): `backend/src/module/services/poster.py`
- Modify (only if compile-broken): `backend/src/module/services/search.py`, `services/search_adapter.py`
- Modify (only if compile-broken): `backend/src/module/searcher/searcher.py`
- Modify (only if compile-broken): `backend/src/module/rss/analyser.py`
- Modify (only if compile-broken): `backend/src/module/network/request_contents.py`
- Modify (only if compile-broken): `backend/src/module/api/v1/bangumi.py`
- Modify (only if compile-broken): `backend/src/module/api/v1/rss.py`
- Modify (only if compile-broken): `backend/src/module/domain/parser/title_parser.py`
- Modify (only if compile-broken): `backend/src/module/domain/parser/analyser/mikan_parser.py`
- Modify (only if compile-broken): `backend/src/module/domain/parser/analyser/tmdb_parser.py`
- Modify (only if compile-broken): `backend/src/module/services/downloader/pikpak.py`
- Modify (only if compile-broken): `backend/src/module/models/bangumi.py`
- Modify (only if compile-broken): `backend/src/module/domain/value_objects.py`

**Background:** With Task 9's compat properties (`bangumi.official_title`, `season`, `year`, `save_path`, `poster_link`), most read-side callers should still compile. This task is targeted cleanup: import errors, kwargs that referenced dropped fields, fields no longer in the dict envelope. **Do not** rewrite these modules wholesale — Plan 05 owns the API and serialization rewrite. Only patch what the Python interpreter / pytest collector refuses to even load.

The triage rule:
- Read-side access to `bangumi.official_title`, `bangumi.season`, `bangumi.year`, `bangumi.save_path`, `bangumi.poster_link` → no change needed (property shim handles it).
- Write-side `bangumi.X = value` for a dropped field → drop the line; if the side effect mattered, set `bangumi.series.canonical_title = value` etc. (with a `await session.refresh(bangumi, ['series'])` first).
- Constructor / dict-literal containing a dropped key → drop the key.
- Anywhere `models.bangumi.Bangumi` (the Pydantic shadow) carries dropped fields, leave it for Plan 05 — it's a DTO, not the ORM.

- [ ] **Step 1: Run the import test**

Run: `cd backend && uv run python -c "import module.services.poster; import module.services.search; import module.searcher.searcher; import module.rss.analyser; import module.network.request_contents; import module.api.v1.bangumi; import module.api.v1.rss; import module.domain.parser.title_parser"`

Note every ImportError / AttributeError. Each one points to a write-side reference that Task 9 broke.

- [ ] **Step 2: Patch each broken site minimally**

For each error:
- ImportError on a Bangumi field → no fix; rerun to surface the next error.
- `bangumi.poster_link = X` → `if bangumi.series is not None: bangumi.series.poster_url = X` (and `await session.flush()`).
- `bangumi.save_path = X` (write) → `bangumi.path_override = X` (writes go to the new override field; reads come from path_override or series.root_path via the property).
- `bangumi.title_raw`, `bangumi.season_raw` writes → drop the assignment; the parser intermediates aren't persisted anymore.
- `BangumiRepository.update_simple({"poster_link": X})` → `BangumiRepository.update_simple({"path_override": X})` for save_path; for poster_link, update the related Series via `SeriesRepository`.
- `BangumiRepository.create({"official_title": ..., "title_raw": ...})` → use the Task 11 series-aware shape (refactor inline if it's a small site; otherwise leave a `# TODO(plan05): rewrite` and raise NotImplementedError to make the failure obvious during Plan 05).

- [ ] **Step 3: Run the import test again until clean**

Run: `cd backend && uv run python -c "import module.api.v1.bangumi; import module.api.v1.rss"`
Expected: no errors.

- [ ] **Step 4: Run the unit + repo + services suites**

Run: `cd backend && uv run pytest src/tests/test_repositories/ src/tests/test_services/ src/tests/test_domain/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/src/module/
git commit -m "refactor: peripheral services drop legacy bangumi field writes"
```

---

## Task 13: Backfill + migrate_duplicates rehearsal on production snapshot

**Files:**
- Document only — no code changes.

**Background:** Spec §13.2 phase 7 mandates a backup-and-rehearse step before stage 9 hits live data. This task runs the full backfill → migrate_duplicates → 0008 chain against a copy of the production database, captures the result, and produces a short writeup. Failure here halts the plan — escalate.

- [ ] **Step 1: Snapshot the current production DB schema**

Run:
```bash
cp /path/to/production/bangumi.db /tmp/bangumi-pre-plan04.db
sqlite3 /tmp/bangumi-pre-plan04.db ".schema bangumi" > /tmp/pre-schema.sql
sqlite3 /tmp/bangumi-pre-plan04.db "SELECT COUNT(*) FROM bangumi WHERE deleted=0;"
sqlite3 /tmp/bangumi-pre-plan04.db "SELECT COUNT(*) FROM torrent;"
```

(Substitute the actual production path. From memory: `/app/data/bangumi.db` inside container `ab`. Copy via `docker cp ab:/app/data/bangumi.db /tmp/bangumi-pre-plan04.db`.)

- [ ] **Step 2: Upgrade the snapshot to revision 0007**

Run:
```bash
cd backend && AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/bangumi-pre-plan04.db" \
  uv run alembic upgrade 0007_add_bangumi_series_link
```

Expected: clean upgrade. Verify additive columns are present:

```bash
sqlite3 /tmp/bangumi-pre-plan04.db ".schema bangumi" | grep -E "series_id|active|path_override"
```

- [ ] **Step 3: Run backfill_series**

Run:
```bash
cd backend && AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/bangumi-pre-plan04.db" \
  uv run python -m scripts.backfill_series
```

Expected log: "Backfill complete: 62 bangumi linked, ~523 torrents updated" (numbers from the production snapshot; allow drift).

Verify:
```bash
sqlite3 /tmp/bangumi-pre-plan04.db \
  "SELECT COUNT(*) FROM bangumi WHERE series_id IS NULL AND deleted=0;"
# Expected: 0
```

- [ ] **Step 4: Run migrate_duplicates --dry-run**

Run:
```bash
cd backend && AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/bangumi-pre-plan04.db" \
  uv run python -m scripts.migrate_duplicates --dry-run
```

Expected: at least one planned merge for the known production duplicate (rows 91 + 93). If no duplicates appear, halt — backfill or detection logic is broken.

- [ ] **Step 5: Run migrate_duplicates --execute**

Run:
```bash
cd backend && AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/bangumi-pre-plan04.db" \
  uv run python -m scripts.migrate_duplicates --execute
```

Expected: "Executed N merges." and the loser rows have `deleted=1`. Verify:

```bash
sqlite3 /tmp/bangumi-pre-plan04.db \
  "SELECT id, deleted FROM bangumi WHERE id IN (91, 93);"
sqlite3 /tmp/bangumi-pre-plan04.db \
  "SELECT winner_bangumi_id, loser_bangumi_id FROM bangumi_merge_history;"
```

- [ ] **Step 6: Upgrade past 0008 lockdown**

Run:
```bash
cd backend && AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/bangumi-pre-plan04.db" \
  uv run alembic upgrade 0008_lockdown_bangumi_identity
```

Expected: clean upgrade. Verify legacy columns are gone:

```bash
sqlite3 /tmp/bangumi-pre-plan04.db ".schema bangumi" | grep -c "official_title"
# Expected: 0
```

- [ ] **Step 7: Document the rehearsal in the plan file**

Append the rehearsal log to this plan file (after the file-map section, under a new "Rehearsal log" heading):

```markdown
## Rehearsal Log (Production Snapshot 2026-04-1?)

- Pre-state: 62 bangumi, 523 torrents.
- Backfill: 62 bangumi linked, X torrents updated.
- Duplicates detected: <list>.
- Merges executed: <N>.
- Post-state schema: legacy columns dropped, partial UNIQUEs in place.
- Anomalies: <none / list>.
```

- [ ] **Step 8: Commit the rehearsal log**

```bash
cd /Users/tk/ws/Auto_Bangumi
git add docs/superpowers/plans/2026-04-18-04-bangumi-schema-and-rename.md
git commit -m "docs: plan 04 rehearsal log against production snapshot"
```

---

## Task 14: Fix pre-existing stale tests

**Files:**
- Modify: `backend/src/tests/test_scheduler/test_rename_job.py`
- Modify: `backend/src/tests/test_api_contract/test_rss.py`

**Background:** Plan 03 Task 3 documented 10 pre-existing failures in `test_rename_job.py` (8) and `test_rss.py` (2). Their common shape is `mock.patch("module.scheduler.jobs.rename.get_db_session")` — a symbol that no longer exists. After Task 11 rewrote the rename pipeline, fix the mocks to patch the actual session-providing path (`module.database.engine.async_session_factory` or whatever the rewritten code uses).

Some failures may also be Plan 04-specific symptoms of dropped bangumi fields in fixtures.

- [ ] **Step 1: Run the failing tests to capture the current error**

Run:
```bash
cd backend && uv run pytest src/tests/test_scheduler/test_rename_job.py \
  src/tests/test_api_contract/test_rss.py -v 2>&1 | tail -80
```

Note each failure mode.

- [ ] **Step 2: Replace stale mocks**

For each `mock.patch("module.scheduler.jobs.rename.get_db_session")` (or similar dead symbol), find what the rename job actually uses today:

```bash
cd backend && grep -n "session\|async_session\|get_db" src/module/scheduler/jobs/rename.py
```

Update the patch target accordingly. If the rename job now uses `module.database.engine.async_session_factory`, patch that.

For fixture rows missing `series_id`, add a Series creation step.

- [ ] **Step 3: Verify the tests pass**

Run:
```bash
cd backend && uv run pytest src/tests/test_scheduler/test_rename_job.py \
  src/tests/test_api_contract/test_rss.py -v
```
Expected: ALL PASS.

- [ ] **Step 4: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/src/tests/test_scheduler/test_rename_job.py \
        backend/src/tests/test_api_contract/test_rss.py
git commit -m "test: fix stale mocks in rename job + rss api contract tests"
```

---

## Task 15: Full sanity pass

**Files:** None — verification only.

- [ ] **Step 1: Run the unit + repo + domain + services + migrations + scripts suites**

Run:
```bash
cd backend && uv run pytest \
  src/tests/test_repositories/ src/tests/test_domain/ src/tests/test_services/ \
  src/tests/test_migrations/ src/tests/test_concurrency/ src/tests/test_mikan/ \
  src/tests/test_scripts/ -q
```
Expected: ALL PASS (no new failures vs Plan 03 baseline of 1151 passed + 2 skipped + 2 xfailed; expect ~30+ new tests from Plan 04).

- [ ] **Step 2: Run the e2e suite**

Run: `cd backend && uv run pytest src/tests/test_e2e/ -q`
Expected: 144 passed + 1 xfailed (or better — fewer xfailed).

If any e2e test fails for a Plan 04 reason, fix it inline now (do not commit a broken e2e suite as "done"). Document the fix in the commit.

- [ ] **Step 3: Run the API contract + scheduler suites**

Run:
```bash
cd backend && uv run pytest src/tests/test_api_contract/ src/tests/test_scheduler/ -q
```
Expected: ALL PASS.

- [ ] **Step 4: Verify alembic upgrade + downgrade is clean on a fresh DB**

Run:
```bash
TMP=$(mktemp -d)
cd backend && AB_ALEMBIC_DB_URL="sqlite+aiosqlite:///$TMP/x.db" \
  uv run alembic upgrade head && \
AB_ALEMBIC_DB_URL="sqlite+aiosqlite:///$TMP/x.db" \
  uv run alembic downgrade base && \
AB_ALEMBIC_DB_URL="sqlite+aiosqlite:///$TMP/x.db" \
  uv run alembic upgrade head
```
Expected: clean upgrade → clean downgrade → clean re-upgrade. No errors.

- [ ] **Step 5: Commit (no-op if no changes)**

If Step 2 fix-ups produced changes, commit them:
```bash
cd /Users/tk/ws/Auto_Bangumi
git add backend/src/tests/
git commit -m "test: plan 04 final sanity pass fixups"
```

If nothing changed, skip the commit and proceed.

---

## Self-Review Checklist (controller runs after Task 15)

After all tasks pass:

1. **Spec coverage**:
   - §6.2 bangumi DROP/ADD: covered by Task 9 (migration 0008 + ORM rewrite).
   - §6.2 partial UNIQUEs: covered by Task 9.
   - §6.3 torrent ADD: covered by Tasks 3 + 4.
   - §11.2 merge transaction: covered by Task 6.
   - §11.4 permanent blacklist: covered by Task 6 (BangumiMergeService) + Task 8 (migrate_duplicates skip).
   - §13.2 phases 3-5 backfill: covered by Task 7.
   - §13.2 phases 6-8 dry-run + execute + history: covered by Task 8.
   - §13.2 phase 9 destructive lockdown: covered by Task 9.
   - §10.1 effective_path + canonical_title in filenames: covered by Task 10.
   - §10.2 active=true filter: covered by Task 10.
   - §10.3 rename conflict skip + report: covered by Task 10.

2. **Out-of-scope items** (confirmed deferred to Plan 05):
   - `MikanResolver`/`IdentityResolver` wiring into RSS refresh job.
   - `pending_torrent_enrichment` queue consumer.
   - API rewrite (`/api/v1/series/*`, merge endpoints, health endpoints).
   - WebUI new pages.
   - Removal of `Bangumi` `@property` compat shims.

3. **Type consistency**:
   - `MergePlan` defined in Task 8, used in Task 8.
   - `BangumiMergeService.merge()` signature consistent across Tasks 6 + 8.
   - `extract_mikan_ids_from_rss` signature consistent across Tasks 7 + 11.
   - `effective_root` (RenamerService static method) consistent with `bangumi.path_override` semantics in Bangumi ORM (Task 9).

4. **Migration linearity**:
   - 0005 → 0006 (Task 1) → 0007 (Task 3) → 0008 (Task 9). Single linear chain, no branches.
