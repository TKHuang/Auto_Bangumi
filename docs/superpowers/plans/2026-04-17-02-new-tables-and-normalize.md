# Plan 02 — New Tables + ORM + Repositories + Normalize Title

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce the four new SQLAlchemy models (`Series`, `MikanEpisodeRef`, `PendingTorrentEnrichment`, `BangumiMergeHistory`), their Alembic revisions, their repositories, and the `normalize_title` function used by the fallback identity resolver — without touching existing tables or business logic.

**Architecture:** Phase 1 is **purely additive**. New tables and code modules are created; no column on `bangumi` / `torrent` is added, renamed, or dropped yet. Each new table lands as its own Alembic revision (0002–0005) so rollback granularity matches the spec. Phase 3 will wire these into the RSS pipeline; Phase 4 will modify existing tables. Keeping this plan additive-only means it can be reverted cleanly by `alembic downgrade 0001_baseline` + file deletion.

**Tech Stack:** SQLAlchemy 2.0 async (aiosqlite), Alembic >=1.13, OpenCC (Traditional↔Simplified Chinese), pytest-asyncio.

**Spec reference:** [docs/superpowers/specs/2026-04-17-bangumi-identity-refactor-design.md](../specs/2026-04-17-bangumi-identity-refactor-design.md) §6.1, §6.4, §7.

**Out of scope for this plan (explicit):**
- Changes to `bangumi` / `torrent` table schemas → Plan 04
- RSS pipeline integration with resolver → Plan 03
- Mikan page scraping implementation → Plan 03
- Rate limiter, per-RSS lock → Plan 03
- Merge transaction logic → Plan 04
- API / WebUI changes → Plan 05+

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/pyproject.toml` | Modify | Add `opencc>=1.1.9` |
| `backend/src/module/domain/text/__init__.py` | Create | Package marker |
| `backend/src/module/domain/text/normalize.py` | Create | `normalize_title()` |
| `backend/src/module/domain/models/series.py` | Create | `Series` ORM |
| `backend/src/module/domain/models/mikan_ref.py` | Create | `MikanEpisodeRef` ORM |
| `backend/src/module/domain/models/pending_enrichment.py` | Create | `PendingTorrentEnrichment` ORM |
| `backend/src/module/domain/models/merge_history.py` | Create | `BangumiMergeHistory` ORM |
| `backend/alembic/env.py` | Modify (4 times) | Register each new model module |
| `backend/alembic/versions/0002_add_series.py` | Create | Alembic revision |
| `backend/alembic/versions/0003_add_mikan_ref.py` | Create | Alembic revision |
| `backend/alembic/versions/0004_add_pending_enrichment.py` | Create | Alembic revision |
| `backend/alembic/versions/0005_add_merge_history.py` | Create | Alembic revision |
| `backend/src/module/repositories/series.py` | Create | CRUD + identity lookups |
| `backend/src/module/repositories/mikan_ref.py` | Create | Cache upsert + health |
| `backend/src/module/repositories/pending_enrichment.py` | Create | Queue operations |
| `backend/src/module/repositories/merge_history.py` | Create | Audit log + blacklist |
| `backend/src/tests/test_domain/test_normalize.py` | Create | `normalize_title` unit tests |
| `backend/src/tests/test_domain/test_new_models.py` | Create | ORM column smoke tests |
| `backend/src/tests/test_repositories/test_series.py` | Create | Series repo tests |
| `backend/src/tests/test_repositories/test_mikan_ref.py` | Create | MikanEpisodeRef repo tests |
| `backend/src/tests/test_repositories/test_pending_enrichment.py` | Create | Pending repo tests |
| `backend/src/tests/test_repositories/test_merge_history.py` | Create | Merge history repo tests |
| `backend/src/tests/test_repositories/conftest.py` | Create (if absent) | `db_session` fixture shared across repo tests |
| `backend/src/tests/test_migrations/test_phase1_migrations.py` | Create | Full chain upgrade/downgrade/cycle test |

---

## Prerequisites

- Branch: `refactor/backendv2`
- Plan 01 landed (Alembic baseline at `0001_baseline`, `main.py` uses `run_migrations()`)
- Working tree clean: `git status` shows nothing modified
- All tests green: `cd backend && uv run python -m pytest src/tests/ -q` reports `1051+ passed`

---

### Task 1: Add OpenCC dependency

**Files:**

- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Edit pyproject.toml**

In `backend/pyproject.toml`, add `"opencc>=1.1.9",` to the `dependencies` array in alphabetical order (after `httpx`):

```toml
    "aiosqlite>=0.20",
    "alembic>=1.13",
    "apscheduler>=4.0.0a6",
    "httpx>=0.28",
    "opencc>=1.1.9",
```

- [ ] **Step 2: Install**

Run:
```bash
cd /Users/tk/ws/Auto_Bangumi/backend && uv sync --extra dev
```

Expected: `opencc` appears in resolved packages, no errors.

- [ ] **Step 3: Verify import works and conversion is correct**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && uv run python -c "
from opencc import OpenCC
cc = OpenCC('t2s')
print(cc.convert('葬送的芙莉蓮'))
"
```

Expected output: `葬送的芙莉莲` (Traditional `蓮` → Simplified `莲`).

If the output is unchanged, the OpenCC dict files aren't bundled with the package that was installed. In that case run `uv add opencc-python-reimplemented` as a fallback (pure-Python with bundled dicts), then repeat Step 3.

- [ ] **Step 4: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/pyproject.toml backend/uv.lock && \
  git commit -m "feat: add opencc dependency for title normalization"
```

---

### Task 2: Implement `normalize_title()`

**Files:**

- Create: `backend/src/module/domain/text/__init__.py` (empty)
- Create: `backend/src/module/domain/text/normalize.py`
- Create: `backend/src/tests/test_domain/test_normalize.py`

- [ ] **Step 1: Write failing tests**

Create `backend/src/tests/test_domain/test_normalize.py`:

```python
"""Tests for title normalization (spec §7)."""
import pytest

from module.domain.text.normalize import normalize_title


@pytest.mark.unit
class TestNormalizeTitle:
    def test_trad_simp_chinese_match(self):
        n_trad, _ = normalize_title("葬送的芙莉蓮")
        n_simp, _ = normalize_title("葬送的芙莉莲")
        assert n_trad == n_simp

    def test_fullwidth_halfwidth_match(self):
        n_full, _ = normalize_title("Re：从零开始的异世界生活 第二季")
        n_half, _ = normalize_title("Re:從零開始的異世界生活 第二季")
        assert n_full == n_half

    def test_season_marker_stripped_for_chinese(self):
        n1, _ = normalize_title("我推的孩子 第三季")
        n2, _ = normalize_title("【我推的孩子】 第三季")
        assert n1 == n2

    def test_season_marker_stripped_for_english(self):
        n_en, _ = normalize_title("Re:Zero Season 2")
        n_s2, _ = normalize_title("Re:Zero S2")
        assert "season" not in n_en
        assert "s2" not in n_s2

    def test_cour_part_latter(self):
        _, cour = normalize_title("Re：从零开始的异世界生活 第二季 后半部分")
        assert cour == "latter"

    def test_cour_part_former(self):
        _, cour = normalize_title("Re：从零开始的异世界生活 第二季 前半部分")
        assert cour == "former"

    def test_cour_part_part_n(self):
        _, cour = normalize_title("Series Name Part 2")
        assert cour == "part"

    def test_cour_part_none_default(self):
        _, cour = normalize_title("葬送的芙莉蓮")
        assert cour is None

    def test_brackets_are_stripped(self):
        n1, _ = normalize_title("【我推的孩子】 第三季")
        n2, _ = normalize_title("我推的孩子 第三季")
        assert n1 == n2

    def test_zhuzhu_trad_simp_match(self):
        n_trad, _ = normalize_title("咒術迴戰")
        n_simp, _ = normalize_title("咒术回战")
        assert n_trad == n_simp

    def test_cour_and_season_together(self):
        a, cour_a = normalize_title("Re：从零开始的异世界生活 第二季 后半部分")
        b, cour_b = normalize_title("Re：从零开始的异世界生活 第二季")
        assert a == b
        assert cour_a == "latter"
        assert cour_b is None

    def test_empty_string(self):
        n, cour = normalize_title("")
        assert n == ""
        assert cour is None

    def test_all_whitespace(self):
        n, cour = normalize_title("   ")
        assert n == ""
        assert cour is None

    def test_lowercase_latin(self):
        n_upper, _ = normalize_title("Fate")
        n_lower, _ = normalize_title("fate")
        assert n_upper == n_lower
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_domain/test_normalize.py -v
```

Expected: `ModuleNotFoundError: No module named 'module.domain.text'` (collection error).

- [ ] **Step 3: Create package marker**

Create `backend/src/module/domain/text/__init__.py` as an empty file.

- [ ] **Step 4: Implement `normalize_title`**

Create `backend/src/module/domain/text/normalize.py`:

```python
"""Title normalization for fallback (non-Mikan) series identity matching.

Produces a (normalized_title, cour_part) tuple so that:
  - Traditional / Simplified Chinese variants collapse
  - Full-width / half-width punctuation collapse
  - Season markers (第N季 / Season N / SN) are stripped (kept in season field)
  - Cour markers (后半部分 / Part N / Cour N) are extracted as a separate field
  - Brackets, punctuation and whitespace are dropped

Used by SeriesRepository.get_by_fallback() when no Mikan ID is available.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

from opencc import OpenCC

_cc_t2s = OpenCC("t2s")

_SEASON_PATTERNS = [
    r"第\s*[0-9一二三四五六七八九十百]+\s*[季期]",
    r"[Ss]eason\s*\d+",
    r"\bS\d+\b",
    r"\bSP\b",
    r"\bOVA\b",
    r"\bOAD\b",
]

_COUR_PATTERNS: list[tuple[str, str]] = [
    (r"后半部分|後半部分|后半|後半", "latter"),
    (r"前半部分|前半部分|前半", "former"),
    (r"第\s*[0-9一二]+\s*部分", "part"),
    (r"[Pp]art\s*\d+", "part"),
    (r"[Cc]our\s*\d+", "cour"),
]


def normalize_title(raw: str) -> tuple[str, Optional[str]]:
    """Return (normalized_title, cour_part).

    cour_part is one of 'latter' | 'former' | 'part' | 'cour' | None.
    """
    s = unicodedata.normalize("NFKC", raw)
    s = _cc_t2s.convert(s)

    cour: Optional[str] = None
    for pattern, kind in _COUR_PATTERNS:
        if re.search(pattern, s):
            cour = kind
            s = re.sub(pattern, "", s)
            break

    for pattern in _SEASON_PATTERNS:
        s = re.sub(pattern, "", s)

    # Keep: CJK unified (U+4E00-U+9FFF), Hiragana+Katakana (U+3040-U+30FF),
    # word chars (Latin letters + digits + underscore). Drop everything else.
    s = re.sub(r"[^\w\u4e00-\u9fff\u3040-\u30ff]+", "", s)
    return s.lower().strip(), cour
```

- [ ] **Step 5: Run tests to verify all pass**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_domain/test_normalize.py -v
```

Expected: 14 tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/domain/text/__init__.py \
          backend/src/module/domain/text/normalize.py \
          backend/src/tests/test_domain/test_normalize.py && \
  git commit -m "feat: normalize_title for series fallback identity"
```

---

### Task 3: `Series` ORM + alembic revision 0002

This task creates the `Series` ORM, registers it in `alembic/env.py`, and generates revision `0002_add_series`. The interleaving (model → env.py → revision) matters: autogenerate only picks up a new table once its model module is imported in `env.py` **and** the current DB head does not yet contain it.

**Files:**

- Create: `backend/src/module/domain/models/series.py`
- Create: `backend/src/tests/test_domain/test_new_models.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0002_add_series.py`

- [ ] **Step 1: Write failing ORM smoke test**

Create `backend/src/tests/test_domain/test_new_models.py`:

```python
"""Smoke tests for new ORM models (spec §6.1)."""
import pytest

from module.domain.models.series import Series


@pytest.mark.unit
class TestSeriesModel:
    def test_series_has_required_columns(self):
        cols = {c.name for c in Series.__table__.columns}
        expected = {
            "id", "mikan_bangumi_id", "canonical_title", "normalized_title",
            "season", "cour_part", "year", "root_path", "poster_url",
            "default_filter", "default_offset", "pending_review",
            "created_at", "updated_at", "version",
        }
        assert expected.issubset(cols), f"missing: {expected - cols}"

    def test_series_unique_constraints(self):
        uq_names = {c.name for c in Series.__table__.constraints
                    if c.__class__.__name__ == "UniqueConstraint"}
        assert "uq_series_mikan" in uq_names
        assert "uq_series_fallback" in uq_names
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_domain/test_new_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'module.domain.models.series'`.

- [ ] **Step 3: Create the model**

Create `backend/src/module/domain/models/series.py`:

```python
"""Series domain model - the stable anime identity layer (spec §6.1).

A Series represents one anime (one Mikan bangumiId, or one (normalized_title,
season, cour_part) tuple for non-Mikan sources). Multiple Bangumi (subscriptions)
can point to the same Series via Bangumi.series_id (added in Plan 04).
"""

from typing import Optional

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, VersionMixin


class Series(Base, TimestampMixin, VersionMixin):
    __tablename__ = "series"

    __table_args__ = (
        UniqueConstraint("mikan_bangumi_id", name="uq_series_mikan"),
        UniqueConstraint(
            "normalized_title", "season", "cour_part", name="uq_series_fallback"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mikan_bangumi_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    canonical_title: Mapped[str] = mapped_column(String, nullable=False)
    normalized_title: Mapped[str] = mapped_column(String, nullable=False, index=True)
    season: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cour_part: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    root_path: Mapped[str] = mapped_column(String, nullable=False)
    poster_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    default_filter: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    default_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

- [ ] **Step 4: Run ORM smoke test to verify pass**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_domain/test_new_models.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Register Series in `alembic/env.py`**

Edit `backend/alembic/env.py`. Find the block that imports the four legacy model modules (around line 24-27):

```python
import module.domain.models.user  # noqa: F401, E402
import module.domain.models.rss  # noqa: F401, E402
import module.domain.models.bangumi  # noqa: F401, E402
import module.domain.models.torrent  # noqa: F401, E402
```

Add one new import line immediately after:

```python
import module.domain.models.series  # noqa: F401, E402
```

- [ ] **Step 6: Autogenerate alembic revision**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  rm -f /tmp/alembic_gen.db && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/alembic_gen.db" \
    uv run alembic upgrade head && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/alembic_gen.db" \
    uv run alembic revision --autogenerate -m "add_series"
```

Expected output: a new file `backend/alembic/versions/<hex>_add_series.py` is created. The `upgrade()` body must contain exactly **one** `op.create_table('series', ...)` call plus the `uq_series_mikan`, `uq_series_fallback`, and `ix_series_normalized_title` definitions. The `downgrade()` body must contain `op.drop_table('series')`.

If the file contains any reference to a table other than `series`, abort — the env.py import added a previously-registered model that wasn't in the 0001 baseline. Revert the env.py edit and debug.

- [ ] **Step 7: Rename file and fix revision IDs**

Rename the generated file to `backend/alembic/versions/0002_add_series.py`. Edit the top of the file:

```python
revision: str = "0002_add_series"
down_revision: Union[str, Sequence[str], None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

- [ ] **Step 8: Test upgrade/downgrade cycle**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  rm -f /tmp/cycle.db && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/cycle.db" uv run alembic upgrade head && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/cycle.db" uv run alembic downgrade -1 && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/cycle.db" uv run alembic upgrade head && \
  sqlite3 /tmp/cycle.db ".tables"
```

Expected: all three alembic commands succeed. `.tables` output includes `series`.

- [ ] **Step 9: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/domain/models/series.py \
          backend/alembic/env.py \
          backend/alembic/versions/0002_add_series.py \
          backend/src/tests/test_domain/test_new_models.py && \
  git commit -m "feat: Series ORM + alembic 0002 add_series"
```

---

### Task 4: `MikanEpisodeRef` ORM + alembic revision 0003

**Files:**

- Create: `backend/src/module/domain/models/mikan_ref.py`
- Modify: `backend/src/tests/test_domain/test_new_models.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0003_add_mikan_ref.py`

- [ ] **Step 1: Append failing test**

Add to `backend/src/tests/test_domain/test_new_models.py`:

```python
from module.domain.models.mikan_ref import MikanEpisodeRef


@pytest.mark.unit
class TestMikanEpisodeRefModel:
    def test_required_columns(self):
        cols = {c.name for c in MikanEpisodeRef.__table__.columns}
        expected = {
            "info_hash", "mikan_bangumi_id", "mikan_subgroup_id",
            "canonical_title", "poster_url", "fetched_at",
            "attempt_count", "last_error", "parse_status",
        }
        assert expected.issubset(cols), f"missing: {expected - cols}"

    def test_info_hash_is_primary_key(self):
        pk_cols = [c.name for c in MikanEpisodeRef.__table__.primary_key.columns]
        assert pk_cols == ["info_hash"]
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_domain/test_new_models.py::TestMikanEpisodeRefModel -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Create the model**

Create `backend/src/module/domain/models/mikan_ref.py`:

```python
"""Mikan episode-page scraping cache (spec §6.1, §8.1).

Stores the parsed (bangumi_id, subgroup_id) extracted from each Mikan episode
page, keyed by the torrent's info_hash (which Mikan uses as the URL suffix).

parse_status values:
  - 'ok'         : parser extracted a MikanRef; mikan_bangumi_id is non-null
  - 'failed'     : Mikan fetch or parse failed; retry on next resolver pass
  - 'non_mikan'  : homepage URL is not a Mikan episode URL; never retry
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MikanEpisodeRef(Base):
    __tablename__ = "mikan_episode_ref"

    __table_args__ = (
        Index(
            "ix_mikan_episode_ref_series",
            "mikan_bangumi_id",
            "mikan_subgroup_id",
        ),
    )

    info_hash: Mapped[str] = mapped_column(String, primary_key=True)
    mikan_bangumi_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mikan_subgroup_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    canonical_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    poster_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    parse_status: Mapped[str] = mapped_column(String, nullable=False)
```

- [ ] **Step 4: Run ORM smoke test**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_domain/test_new_models.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Register MikanEpisodeRef in `alembic/env.py`**

Edit `backend/alembic/env.py`. Add one new import line after the existing `import module.domain.models.series` line:

```python
import module.domain.models.mikan_ref  # noqa: F401, E402
```

- [ ] **Step 6: Autogenerate revision**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  rm -f /tmp/alembic_gen.db && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/alembic_gen.db" \
    uv run alembic upgrade head && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/alembic_gen.db" \
    uv run alembic revision --autogenerate -m "add_mikan_ref"
```

Expected: a single `op.create_table('mikan_episode_ref', ...)` plus `op.create_index('ix_mikan_episode_ref_series', ...)` in `upgrade()`. Downgrade drops both.

- [ ] **Step 7: Rename and fix revision IDs**

Rename the generated file to `backend/alembic/versions/0003_add_mikan_ref.py`. Set:

```python
revision: str = "0003_add_mikan_ref"
down_revision: Union[str, Sequence[str], None] = "0002_add_series"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

- [ ] **Step 8: Test upgrade/downgrade cycle**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  rm -f /tmp/cycle.db && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/cycle.db" uv run alembic upgrade head && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/cycle.db" uv run alembic downgrade -1 && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/cycle.db" uv run alembic upgrade head && \
  sqlite3 /tmp/cycle.db ".tables"
```

Expected: `.tables` output now also includes `mikan_episode_ref`.

- [ ] **Step 9: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/domain/models/mikan_ref.py \
          backend/alembic/env.py \
          backend/alembic/versions/0003_add_mikan_ref.py \
          backend/src/tests/test_domain/test_new_models.py && \
  git commit -m "feat: MikanEpisodeRef ORM + alembic 0003 add_mikan_ref"
```

---

### Task 5: `PendingTorrentEnrichment` ORM + alembic revision 0004

**Files:**

- Create: `backend/src/module/domain/models/pending_enrichment.py`
- Modify: `backend/src/tests/test_domain/test_new_models.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0004_add_pending_enrichment.py`

- [ ] **Step 1: Append failing test**

Add to `backend/src/tests/test_domain/test_new_models.py`:

```python
from module.domain.models.pending_enrichment import PendingTorrentEnrichment


@pytest.mark.unit
class TestPendingTorrentEnrichmentModel:
    def test_required_columns(self):
        cols = {c.name for c in PendingTorrentEnrichment.__table__.columns}
        expected = {
            "info_hash", "raw_name", "homepage", "url", "rss_id",
            "published_at", "first_seen_at", "attempt_count",
            "last_error", "last_attempt_at",
        }
        assert expected.issubset(cols), f"missing: {expected - cols}"

    def test_rss_id_has_fk(self):
        col = PendingTorrentEnrichment.__table__.c.rss_id
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "rssitem"
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_domain/test_new_models.py::TestPendingTorrentEnrichmentModel -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Create the model**

Create `backend/src/module/domain/models/pending_enrichment.py`:

```python
"""Staging queue for RSS-parsed torrents awaiting Mikan ID resolution (spec §6.1, §8.3).

Rows exist here iff the RSS feed produced a torrent whose MikanEpisodeRef is not
yet resolvable (parse_status='failed' or Mikan unreachable). The resolver retries
on every RSS refresh tick; on success, a real Torrent row is created and the
staging row is deleted.

The length of this table is the Dashboard 'pending' count.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PendingTorrentEnrichment(Base):
    __tablename__ = "pending_torrent_enrichment"

    __table_args__ = (
        Index("ix_pending_torrent_enrichment_rss", "rss_id"),
    )

    info_hash: Mapped[str] = mapped_column(String, primary_key=True)
    raw_name: Mapped[str] = mapped_column(String, nullable=False)
    homepage: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    rss_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rssitem.id", ondelete="CASCADE"),
        nullable=False,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 4: Run ORM smoke test**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_domain/test_new_models.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Register in `alembic/env.py`**

Add one new line after `import module.domain.models.mikan_ref`:

```python
import module.domain.models.pending_enrichment  # noqa: F401, E402
```

- [ ] **Step 6: Autogenerate revision**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  rm -f /tmp/alembic_gen.db && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/alembic_gen.db" \
    uv run alembic upgrade head && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/alembic_gen.db" \
    uv run alembic revision --autogenerate -m "add_pending_enrichment"
```

Expected: a single `op.create_table('pending_torrent_enrichment', ...)` with the FK to `rssitem` (ondelete=CASCADE) plus the index.

- [ ] **Step 7: Rename and fix revision IDs**

Rename to `backend/alembic/versions/0004_add_pending_enrichment.py`. Set:

```python
revision: str = "0004_add_pending_enrichment"
down_revision: Union[str, Sequence[str], None] = "0003_add_mikan_ref"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

- [ ] **Step 8: Test cycle**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  rm -f /tmp/cycle.db && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/cycle.db" uv run alembic upgrade head && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/cycle.db" uv run alembic downgrade -1 && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/cycle.db" uv run alembic upgrade head && \
  sqlite3 /tmp/cycle.db ".tables"
```

Expected: `.tables` lists `pending_torrent_enrichment`.

- [ ] **Step 9: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/domain/models/pending_enrichment.py \
          backend/alembic/env.py \
          backend/alembic/versions/0004_add_pending_enrichment.py \
          backend/src/tests/test_domain/test_new_models.py && \
  git commit -m "feat: PendingTorrentEnrichment ORM + alembic 0004 add_pending_enrichment"
```

---

### Task 6: `BangumiMergeHistory` ORM + alembic revision 0005

**Files:**

- Create: `backend/src/module/domain/models/merge_history.py`
- Modify: `backend/src/tests/test_domain/test_new_models.py`
- Modify: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0005_add_merge_history.py`

- [ ] **Step 1: Append failing test**

Add to `backend/src/tests/test_domain/test_new_models.py`:

```python
from module.domain.models.merge_history import BangumiMergeHistory


@pytest.mark.unit
class TestBangumiMergeHistoryModel:
    def test_required_columns(self):
        cols = {c.name for c in BangumiMergeHistory.__table__.columns}
        expected = {
            "id", "merged_at", "merged_by", "merge_reason",
            "winner_bangumi_id", "loser_bangumi_id",
            "loser_snapshot", "moved_torrent_ids", "dropped_torrents",
            "undone_at", "undone_by",
        }
        assert expected.issubset(cols), f"missing: {expected - cols}"

    def test_both_bangumi_fks(self):
        winner_col = BangumiMergeHistory.__table__.c.winner_bangumi_id
        loser_col = BangumiMergeHistory.__table__.c.loser_bangumi_id
        assert any(fk.column.table.name == "bangumi" for fk in winner_col.foreign_keys)
        assert any(fk.column.table.name == "bangumi" for fk in loser_col.foreign_keys)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_domain/test_new_models.py::TestBangumiMergeHistoryModel -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Create the model**

Create `backend/src/module/domain/models/merge_history.py`:

```python
"""Audit log of bangumi merge operations (spec §6.1, §11).

Every merge writes a row here. undone_at NULL means the merge is active;
non-NULL means the user reverted it via the UI. The (winner, loser) pair is a
permanent blacklist against future auto-merges regardless of undone status.

loser_snapshot, moved_torrent_ids, dropped_torrents are stored as JSON strings
(SQLite has no native JSON but supports the text storage cleanly).
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BangumiMergeHistory(Base):
    __tablename__ = "bangumi_merge_history"

    __table_args__ = (
        Index("ix_bangumi_merge_history_winner", "winner_bangumi_id"),
        Index("ix_bangumi_merge_history_loser", "loser_bangumi_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merged_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    merged_by: Mapped[str] = mapped_column(String, nullable=False)
    merge_reason: Mapped[str] = mapped_column(String, nullable=False)
    winner_bangumi_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bangumi.id"), nullable=False
    )
    loser_bangumi_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bangumi.id"), nullable=False
    )
    loser_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    moved_torrent_ids: Mapped[str] = mapped_column(Text, nullable=False)
    dropped_torrents: Mapped[str] = mapped_column(Text, nullable=False)
    undone_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    undone_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
```

- [ ] **Step 4: Run ORM smoke test**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_domain/test_new_models.py -v
```

Expected: 8 tests PASS.

- [ ] **Step 5: Register in `alembic/env.py`**

Add one new line after `import module.domain.models.pending_enrichment`:

```python
import module.domain.models.merge_history  # noqa: F401, E402
```

- [ ] **Step 6: Autogenerate revision**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  rm -f /tmp/alembic_gen.db && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/alembic_gen.db" \
    uv run alembic upgrade head && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/alembic_gen.db" \
    uv run alembic revision --autogenerate -m "add_merge_history"
```

Expected: single `op.create_table('bangumi_merge_history', ...)` with both FKs and both indexes.

- [ ] **Step 7: Rename and fix revision IDs**

Rename to `backend/alembic/versions/0005_add_merge_history.py`. Set:

```python
revision: str = "0005_add_merge_history"
down_revision: Union[str, Sequence[str], None] = "0004_add_pending_enrichment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
```

- [ ] **Step 8: Test cycle**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  rm -f /tmp/cycle.db && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/cycle.db" uv run alembic upgrade head && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/cycle.db" uv run alembic downgrade -1 && \
  AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/cycle.db" uv run alembic upgrade head && \
  sqlite3 /tmp/cycle.db ".tables"
```

Expected: `.tables` lists `bangumi_merge_history`.

- [ ] **Step 9: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/domain/models/merge_history.py \
          backend/alembic/env.py \
          backend/alembic/versions/0005_add_merge_history.py \
          backend/src/tests/test_domain/test_new_models.py && \
  git commit -m "feat: BangumiMergeHistory ORM + alembic 0005 add_merge_history"
```

---

### Task 7: End-to-end migration chain test

Validates that the full `0001 → 0005` chain applies, rolls back, and re-applies cleanly on a fresh DB.

**Files:**

- Create: `backend/src/tests/test_migrations/test_phase1_migrations.py`

- [ ] **Step 1: Write the test**

Create `backend/src/tests/test_migrations/test_phase1_migrations.py`:

```python
"""Verify the full Phase 1 migration chain applies and reverts cleanly."""
import os
import subprocess
from pathlib import Path

import pytest
import sqlalchemy as sa

BACKEND_DIR = Path(__file__).parent.parent.parent.parent


def _run_alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["AB_ALEMBIC_DB_URL"] = f"sqlite+aiosqlite:///{db_path}"
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.mark.integration
def test_full_upgrade_creates_all_new_tables(tmp_path):
    db = tmp_path / "fresh.db"

    result = _run_alembic(["upgrade", "head"], db)
    assert result.returncode == 0, result.stderr

    engine = sa.create_engine(f"sqlite:///{db}")
    tables = set(sa.inspect(engine).get_table_names())
    assert {"bangumi", "rssitem", "torrent", "user"}.issubset(tables)
    assert {
        "series",
        "mikan_episode_ref",
        "pending_torrent_enrichment",
        "bangumi_merge_history",
    }.issubset(tables)


@pytest.mark.integration
def test_downgrade_to_baseline_drops_new_tables(tmp_path):
    db = tmp_path / "roll.db"

    assert _run_alembic(["upgrade", "head"], db).returncode == 0
    assert _run_alembic(["downgrade", "0001_baseline"], db).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    tables = set(sa.inspect(engine).get_table_names())
    assert "series" not in tables
    assert "mikan_episode_ref" not in tables
    assert "pending_torrent_enrichment" not in tables
    assert "bangumi_merge_history" not in tables
    assert {"bangumi", "rssitem", "torrent", "user"}.issubset(tables)


@pytest.mark.integration
def test_upgrade_downgrade_upgrade_is_idempotent(tmp_path):
    db = tmp_path / "cycle.db"

    assert _run_alembic(["upgrade", "head"], db).returncode == 0
    assert _run_alembic(["downgrade", "base"], db).returncode == 0
    assert _run_alembic(["upgrade", "head"], db).returncode == 0

    engine = sa.create_engine(f"sqlite:///{db}")
    tables = set(sa.inspect(engine).get_table_names())
    assert {
        "bangumi", "rssitem", "torrent", "user",
        "series", "mikan_episode_ref",
        "pending_torrent_enrichment", "bangumi_merge_history",
    }.issubset(tables)
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_migrations/test_phase1_migrations.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 3: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/tests/test_migrations/test_phase1_migrations.py && \
  git commit -m "test: full Phase 1 alembic chain upgrade/downgrade/cycle"
```

---

### Task 8: Set up shared `db_session` fixture for repository tests

**Files:**

- Create (if absent): `backend/src/tests/test_repositories/conftest.py`

- [ ] **Step 1: Check if fixture already exists**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  grep -rn "def db_session\|async def db_session" src/tests/
```

If any file already defines `db_session`, review that fixture and make sure it imports the four new models (series, mikan_ref, pending_enrichment, merge_history) so their tables are registered on the test metadata. Then skip directly to Step 3.

If no existing fixture is found, continue to Step 2.

- [ ] **Step 2: Create conftest.py**

Create `backend/src/tests/test_repositories/conftest.py`:

```python
"""Shared fixtures for repository-layer tests.

Each test gets an isolated SQLite DB created via Base.metadata.create_all
(not Alembic — that path is covered by test_migrations/). The DB lives in a
tmp_path so parallel tests never collide.
"""
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from module.domain.models.base import Base

# Import every model module so its __tablename__ registers with Base.metadata.
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

- [ ] **Step 3: Commit if a new file was created**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/tests/test_repositories/conftest.py && \
  git commit -m "test: shared db_session fixture for repository tests"
```

If Step 1 found an existing fixture and you only tweaked it to import the four new modules, commit that instead:

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add <file-you-changed> && \
  git commit -m "test: register new models in shared db_session fixture"
```

---

### Task 9: Implement `SeriesRepository`

**Files:**

- Create: `backend/src/module/repositories/series.py`
- Create: `backend/src/tests/test_repositories/test_series.py`

- [ ] **Step 1: Write failing tests**

Create `backend/src/tests/test_repositories/test_series.py`:

```python
"""SeriesRepository tests (spec §6.4 Tier 1 / Tier 2 identity lookup)."""
import pytest
import pytest_asyncio

from module.repositories.series import SeriesRepository


@pytest_asyncio.fixture
async def series_repo(db_session):
    return SeriesRepository(db_session)


@pytest.mark.integration
class TestSeriesCreate:
    async def test_create_minimal(self, series_repo, db_session):
        s = await series_repo.create({
            "canonical_title": "葬送的芙莉蓮",
            "normalized_title": "葬送的芙莉莲",
            "season": 1,
            "root_path": "/downloads/葬送的芙莉蓮",
        })
        await db_session.commit()
        assert s.id is not None
        assert s.canonical_title == "葬送的芙莉蓮"
        assert s.mikan_bangumi_id is None
        assert s.pending_review is False
        assert s.version == 1

    async def test_create_with_mikan_id(self, series_repo, db_session):
        s = await series_repo.create({
            "mikan_bangumi_id": 3906,
            "canonical_title": "身为悲剧始作俑者...",
            "normalized_title": "悲剧始作俑者",
            "season": 2,
            "root_path": "/downloads/LasTame/Season 2",
        })
        await db_session.commit()
        assert s.mikan_bangumi_id == 3906


@pytest.mark.integration
class TestSeriesGetByMikanId:
    async def test_get_by_mikan_id_hit(self, series_repo, db_session):
        await series_repo.create({
            "mikan_bangumi_id": 3906, "canonical_title": "X",
            "normalized_title": "x", "season": 1, "root_path": "/x",
        })
        await db_session.commit()

        found = await series_repo.get_by_mikan_id(3906)
        assert found is not None
        assert found.mikan_bangumi_id == 3906

    async def test_get_by_mikan_id_miss(self, series_repo):
        assert await series_repo.get_by_mikan_id(99999) is None


@pytest.mark.integration
class TestSeriesGetByFallback:
    async def test_hit(self, series_repo, db_session):
        await series_repo.create({
            "canonical_title": "Y", "normalized_title": "y",
            "season": 2, "cour_part": "latter", "root_path": "/y",
        })
        await db_session.commit()
        assert await series_repo.get_by_fallback("y", 2, "latter") is not None

    async def test_miss_wrong_season(self, series_repo, db_session):
        await series_repo.create({
            "canonical_title": "Y", "normalized_title": "y",
            "season": 2, "root_path": "/y",
        })
        await db_session.commit()
        assert await series_repo.get_by_fallback("y", 1, None) is None

    async def test_miss_wrong_cour(self, series_repo, db_session):
        await series_repo.create({
            "canonical_title": "Y", "normalized_title": "y",
            "season": 2, "cour_part": "latter", "root_path": "/y",
        })
        await db_session.commit()
        assert await series_repo.get_by_fallback("y", 2, None) is None


@pytest.mark.integration
class TestSeriesUniqueness:
    async def test_duplicate_mikan_id_rejected(self, series_repo, db_session):
        import sqlalchemy.exc

        await series_repo.create({
            "mikan_bangumi_id": 100, "canonical_title": "A",
            "normalized_title": "a1", "season": 1, "root_path": "/a",
        })
        await db_session.commit()

        with pytest.raises(sqlalchemy.exc.IntegrityError):
            await series_repo.create({
                "mikan_bangumi_id": 100, "canonical_title": "A dup",
                "normalized_title": "a2", "season": 1, "root_path": "/a2",
            })
            await db_session.commit()

    async def test_duplicate_fallback_key_rejected(self, series_repo, db_session):
        import sqlalchemy.exc

        await series_repo.create({
            "canonical_title": "B", "normalized_title": "b",
            "season": 1, "cour_part": None, "root_path": "/b",
        })
        await db_session.commit()

        with pytest.raises(sqlalchemy.exc.IntegrityError):
            await series_repo.create({
                "canonical_title": "B2", "normalized_title": "b",
                "season": 1, "cour_part": None, "root_path": "/b2",
            })
            await db_session.commit()


@pytest.mark.integration
class TestSeriesFindCrossSourceCandidates:
    async def test_finds_mikan_series_with_matching_fallback(self, series_repo, db_session):
        await series_repo.create({
            "mikan_bangumi_id": 3906, "canonical_title": "X Mikan",
            "normalized_title": "x", "season": 2, "cour_part": None,
            "root_path": "/x",
        })
        await db_session.commit()

        candidates = await series_repo.find_possible_cross_source_merge("x", 2, None)
        assert len(candidates) == 1
        assert candidates[0].mikan_bangumi_id == 3906

    async def test_returns_empty_when_no_match(self, series_repo):
        assert await series_repo.find_possible_cross_source_merge("none", 1, None) == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_repositories/test_series.py -v
```

Expected: ImportError on `module.repositories.series`.

- [ ] **Step 3: Implement `SeriesRepository`**

Create `backend/src/module/repositories/series.py`:

```python
"""SeriesRepository - identity resolution and CRUD for the series entity.

Identity lookup order (spec §6.4):
  Tier 1  get_by_mikan_id(mikan_bangumi_id)
  Tier 2  get_by_fallback(normalized_title, season, cour_part)
  Tier 3  find_possible_cross_source_merge(...) surfaces merge candidates
"""
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.series import Series


class SeriesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, series_id: int) -> Optional[Series]:
        return await self.session.get(Series, series_id)

    async def get_by_mikan_id(self, mikan_bangumi_id: int) -> Optional[Series]:
        stmt = select(Series).where(Series.mikan_bangumi_id == mikan_bangumi_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_fallback(
        self,
        normalized_title: str,
        season: int,
        cour_part: Optional[str],
    ) -> Optional[Series]:
        stmt = select(Series).where(
            and_(
                Series.normalized_title == normalized_title,
                Series.season == season,
                (Series.cour_part.is_(None) if cour_part is None
                 else Series.cour_part == cour_part),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_possible_cross_source_merge(
        self,
        normalized_title: str,
        season: int,
        cour_part: Optional[str],
    ) -> list[Series]:
        """Return Mikan-sourced series whose fallback key matches the input.

        Used when building a non-Mikan series to surface potential duplicates
        for manual user confirmation (spec §6.4 Tier 3).
        """
        stmt = select(Series).where(
            and_(
                Series.mikan_bangumi_id.is_not(None),
                Series.normalized_title == normalized_title,
                Series.season == season,
                (Series.cour_part.is_(None) if cour_part is None
                 else Series.cour_part == cour_part),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, data: dict) -> Series:
        series = Series(**data)
        self.session.add(series)
        await self.session.flush()
        await self.session.refresh(series)
        return series

    async def list_pending_review(self) -> list[Series]:
        stmt = select(Series).where(Series.pending_review == True)  # noqa: E712
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_repositories/test_series.py -v
```

Expected: 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/repositories/series.py \
          backend/src/tests/test_repositories/test_series.py && \
  git commit -m "feat: SeriesRepository with tier-1/tier-2 identity lookup"
```

---

### Task 10: Implement `MikanEpisodeRefRepository`

**Files:**

- Create: `backend/src/module/repositories/mikan_ref.py`
- Create: `backend/src/tests/test_repositories/test_mikan_ref.py`

- [ ] **Step 1: Write failing tests**

Create `backend/src/tests/test_repositories/test_mikan_ref.py`:

```python
"""MikanEpisodeRefRepository tests."""
import pytest
import pytest_asyncio

from module.repositories.mikan_ref import MikanEpisodeRefRepository


@pytest_asyncio.fixture
async def mikan_repo(db_session):
    return MikanEpisodeRefRepository(db_session)


@pytest.mark.integration
class TestMikanRefUpsert:
    async def test_upsert_inserts_new_row(self, mikan_repo, db_session):
        ref = await mikan_repo.upsert(
            info_hash="abc123",
            parse_status="ok",
            mikan_bangumi_id=3906,
            mikan_subgroup_id=370,
            canonical_title="LasTame S2",
            poster_url="posters/730372c2.jpg",
        )
        await db_session.commit()
        assert ref.info_hash == "abc123"
        assert ref.parse_status == "ok"
        assert ref.attempt_count == 1

    async def test_upsert_updates_existing_row(self, mikan_repo, db_session):
        await mikan_repo.upsert(info_hash="x", parse_status="failed", last_error="timeout")
        await db_session.commit()

        ref = await mikan_repo.upsert(
            info_hash="x",
            parse_status="ok",
            mikan_bangumi_id=100,
            mikan_subgroup_id=50,
        )
        await db_session.commit()

        assert ref.parse_status == "ok"
        assert ref.mikan_bangumi_id == 100
        assert ref.attempt_count == 2
        assert ref.last_error is None

    async def test_upsert_increments_attempts_on_repeated_failure(self, mikan_repo, db_session):
        await mikan_repo.upsert(info_hash="y", parse_status="failed", last_error="timeout")
        await db_session.commit()
        await mikan_repo.upsert(info_hash="y", parse_status="failed", last_error="timeout")
        await db_session.commit()
        ref = await mikan_repo.upsert(info_hash="y", parse_status="failed", last_error="503")
        await db_session.commit()

        assert ref.attempt_count == 3
        assert ref.last_error == "503"


@pytest.mark.integration
class TestMikanRefGet:
    async def test_get_hit(self, mikan_repo, db_session):
        await mikan_repo.upsert(info_hash="h", parse_status="ok", mikan_bangumi_id=1)
        await db_session.commit()
        assert (await mikan_repo.get("h")).parse_status == "ok"

    async def test_get_miss(self, mikan_repo):
        assert await mikan_repo.get("nothere") is None


@pytest.mark.integration
class TestMikanRefHealth:
    async def test_last_success_at(self, mikan_repo, db_session):
        await mikan_repo.upsert(info_hash="a", parse_status="ok", mikan_bangumi_id=1)
        await db_session.commit()
        assert await mikan_repo.last_success_at() is not None

    async def test_last_success_at_none_if_all_failed(self, mikan_repo, db_session):
        await mikan_repo.upsert(info_hash="f1", parse_status="failed")
        await mikan_repo.upsert(info_hash="f2", parse_status="failed")
        await db_session.commit()
        assert await mikan_repo.last_success_at() is None

    async def test_consecutive_failures(self, mikan_repo, db_session):
        for i in range(3):
            await mikan_repo.upsert(info_hash=f"z{i}", parse_status="failed")
        await db_session.commit()
        assert await mikan_repo.consecutive_failures() == 3

    async def test_consecutive_failures_resets_on_success(self, mikan_repo, db_session):
        for i in range(3):
            await mikan_repo.upsert(info_hash=f"z{i}", parse_status="failed")
        await db_session.commit()

        await mikan_repo.upsert(info_hash="ok1", parse_status="ok", mikan_bangumi_id=1)
        await db_session.commit()
        assert await mikan_repo.consecutive_failures() == 0
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_repositories/test_mikan_ref.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement repository**

Create `backend/src/module/repositories/mikan_ref.py`:

```python
"""MikanEpisodeRefRepository - Mikan page scrape cache with health metrics.

upsert() is the single write path. parse_status='ok' clears last_error.
Health queries feed the Dashboard Mikan banner.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.mikan_ref import MikanEpisodeRef


class MikanEpisodeRefRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, info_hash: str) -> Optional[MikanEpisodeRef]:
        return await self.session.get(MikanEpisodeRef, info_hash)

    async def upsert(
        self,
        info_hash: str,
        parse_status: str,
        mikan_bangumi_id: Optional[int] = None,
        mikan_subgroup_id: Optional[int] = None,
        canonical_title: Optional[str] = None,
        poster_url: Optional[str] = None,
        last_error: Optional[str] = None,
    ) -> MikanEpisodeRef:
        """Create or update a cache row. Increments attempt_count each call."""
        existing = await self.get(info_hash)
        now = datetime.now(timezone.utc)

        if existing is None:
            ref = MikanEpisodeRef(
                info_hash=info_hash,
                parse_status=parse_status,
                mikan_bangumi_id=mikan_bangumi_id,
                mikan_subgroup_id=mikan_subgroup_id,
                canonical_title=canonical_title,
                poster_url=poster_url,
                last_error=last_error,
                fetched_at=now,
                attempt_count=1,
            )
            self.session.add(ref)
            await self.session.flush()
            await self.session.refresh(ref)
            return ref

        existing.parse_status = parse_status
        existing.fetched_at = now
        existing.attempt_count = existing.attempt_count + 1
        if parse_status == "ok":
            existing.mikan_bangumi_id = mikan_bangumi_id
            existing.mikan_subgroup_id = mikan_subgroup_id
            existing.canonical_title = canonical_title
            existing.poster_url = poster_url
            existing.last_error = None
        else:
            existing.last_error = last_error
        await self.session.flush()
        await self.session.refresh(existing)
        return existing

    async def last_success_at(self) -> Optional[datetime]:
        stmt = (
            select(func.max(MikanEpisodeRef.fetched_at))
            .where(MikanEpisodeRef.parse_status == "ok")
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def consecutive_failures(self) -> int:
        """Count failed entries since the most recent success.

        Used for Mikan health 'down' detection (spec §12.2).
        """
        last_ok = await self.last_success_at()
        stmt = select(func.count()).where(MikanEpisodeRef.parse_status == "failed")
        if last_ok is not None:
            stmt = stmt.where(MikanEpisodeRef.fetched_at > last_ok)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_repositories/test_mikan_ref.py -v
```

Expected: 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/repositories/mikan_ref.py \
          backend/src/tests/test_repositories/test_mikan_ref.py && \
  git commit -m "feat: MikanEpisodeRefRepository with health metrics"
```

---

### Task 11: Implement `PendingTorrentEnrichmentRepository`

**Files:**

- Create: `backend/src/module/repositories/pending_enrichment.py`
- Create: `backend/src/tests/test_repositories/test_pending_enrichment.py`

- [ ] **Step 1: Write failing tests**

Create `backend/src/tests/test_repositories/test_pending_enrichment.py`:

```python
"""PendingTorrentEnrichmentRepository tests."""
import pytest
import pytest_asyncio

from module.domain.models.rss import RSSItem
from module.repositories.pending_enrichment import PendingTorrentEnrichmentRepository


@pytest_asyncio.fixture
async def rss_id(db_session):
    rss = RSSItem(name="test", url="https://example.com/rss", enabled=True)
    db_session.add(rss)
    await db_session.flush()
    await db_session.commit()
    return rss.id


@pytest_asyncio.fixture
async def pending_repo(db_session):
    return PendingTorrentEnrichmentRepository(db_session)


@pytest.mark.integration
class TestPendingEnrichmentEnqueue:
    async def test_enqueue_new_row(self, pending_repo, db_session, rss_id):
        row = await pending_repo.enqueue(
            info_hash="a", raw_name="[Group] X - 01",
            homepage="https://mikanani.me/Home/Episode/a",
            url="https://mikanani.me/Download/a.torrent",
            rss_id=rss_id,
        )
        await db_session.commit()
        assert row.info_hash == "a"
        assert row.attempt_count == 0
        assert row.last_error is None
        assert row.first_seen_at is not None

    async def test_enqueue_duplicate_is_noop(self, pending_repo, db_session, rss_id):
        await pending_repo.enqueue(
            info_hash="b", raw_name="A", homepage="h", url="u", rss_id=rss_id
        )
        await db_session.commit()
        row = await pending_repo.enqueue(
            info_hash="b", raw_name="A", homepage="h", url="u", rss_id=rss_id
        )
        await db_session.commit()
        assert row.attempt_count == 0


@pytest.mark.integration
class TestPendingEnrichmentMarkAttempt:
    async def test_mark_attempt_increments(self, pending_repo, db_session, rss_id):
        await pending_repo.enqueue(
            info_hash="c", raw_name="A", homepage="h", url="u", rss_id=rss_id
        )
        await db_session.commit()

        await pending_repo.mark_attempt("c", error="timeout")
        await db_session.commit()
        await pending_repo.mark_attempt("c", error="503")
        await db_session.commit()

        row = await pending_repo.get("c")
        assert row.attempt_count == 2
        assert row.last_error == "503"
        assert row.last_attempt_at is not None


@pytest.mark.integration
class TestPendingEnrichmentDelete:
    async def test_delete_removes_row(self, pending_repo, db_session, rss_id):
        await pending_repo.enqueue(
            info_hash="d", raw_name="A", homepage="h", url="u", rss_id=rss_id
        )
        await db_session.commit()

        await pending_repo.delete("d")
        await db_session.commit()
        assert await pending_repo.get("d") is None


@pytest.mark.integration
class TestPendingEnrichmentList:
    async def test_list_all_ordered_by_first_seen(self, pending_repo, db_session, rss_id):
        await pending_repo.enqueue(info_hash="e1", raw_name="A", homepage="h", url="u", rss_id=rss_id)
        await pending_repo.enqueue(info_hash="e2", raw_name="B", homepage="h", url="u", rss_id=rss_id)
        await pending_repo.enqueue(info_hash="e3", raw_name="C", homepage="h", url="u", rss_id=rss_id)
        await db_session.commit()

        rows = await pending_repo.list_all(limit=10)
        assert [r.info_hash for r in rows] == ["e1", "e2", "e3"]

    async def test_list_all_respects_limit(self, pending_repo, db_session, rss_id):
        for i in range(5):
            await pending_repo.enqueue(info_hash=f"l{i}", raw_name="A", homepage="h", url="u", rss_id=rss_id)
        await db_session.commit()

        rows = await pending_repo.list_all(limit=2)
        assert len(rows) == 2

    async def test_count(self, pending_repo, db_session, rss_id):
        for i in range(3):
            await pending_repo.enqueue(info_hash=f"n{i}", raw_name="A", homepage="h", url="u", rss_id=rss_id)
        await db_session.commit()
        assert await pending_repo.count() == 3
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_repositories/test_pending_enrichment.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement repository**

Create `backend/src/module/repositories/pending_enrichment.py`:

```python
"""PendingTorrentEnrichmentRepository - staging queue for blocked torrents.

The length of this queue is the Dashboard 'pending' count shown to the user.
enqueue() is idempotent per info_hash; mark_attempt() tracks retry history.
delete() is called on successful resolution.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.pending_enrichment import PendingTorrentEnrichment


class PendingTorrentEnrichmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def enqueue(
        self,
        info_hash: str,
        raw_name: str,
        homepage: str,
        url: str,
        rss_id: int,
        published_at: Optional[datetime] = None,
    ) -> PendingTorrentEnrichment:
        """Idempotent insert. Returns the existing row unchanged if info_hash already in queue."""
        existing = await self.get(info_hash)
        if existing is not None:
            return existing

        row = PendingTorrentEnrichment(
            info_hash=info_hash,
            raw_name=raw_name,
            homepage=homepage,
            url=url,
            rss_id=rss_id,
            published_at=published_at,
            first_seen_at=datetime.now(timezone.utc),
            attempt_count=0,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def get(self, info_hash: str) -> Optional[PendingTorrentEnrichment]:
        return await self.session.get(PendingTorrentEnrichment, info_hash)

    async def mark_attempt(self, info_hash: str, error: Optional[str]) -> None:
        row = await self.get(info_hash)
        if row is None:
            return
        row.attempt_count = row.attempt_count + 1
        row.last_error = error
        row.last_attempt_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def delete(self, info_hash: str) -> None:
        row = await self.get(info_hash)
        if row is not None:
            await self.session.delete(row)
            await self.session.flush()

    async def list_all(self, limit: int = 100) -> list[PendingTorrentEnrichment]:
        stmt = (
            select(PendingTorrentEnrichment)
            .order_by(PendingTorrentEnrichment.first_seen_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        stmt = select(func.count()).select_from(PendingTorrentEnrichment)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_repositories/test_pending_enrichment.py -v
```

Expected: 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/repositories/pending_enrichment.py \
          backend/src/tests/test_repositories/test_pending_enrichment.py && \
  git commit -m "feat: PendingTorrentEnrichmentRepository staging queue"
```

---

### Task 12: Implement `BangumiMergeHistoryRepository`

This repository is a write-once audit log. Task 12 covers only CRUD + blacklist lookup; the actual merge transaction logic lives in Plan 04.

**Files:**

- Create: `backend/src/module/repositories/merge_history.py`
- Create: `backend/src/tests/test_repositories/test_merge_history.py`

- [ ] **Step 1: Write failing tests**

Create `backend/src/tests/test_repositories/test_merge_history.py`:

```python
"""BangumiMergeHistoryRepository tests."""
import json

import pytest
import pytest_asyncio

from module.domain.models.bangumi import Bangumi
from module.repositories.merge_history import BangumiMergeHistoryRepository


@pytest_asyncio.fixture
async def winner_loser(db_session):
    """Create two real bangumi rows to reference as winner/loser."""
    w = Bangumi(official_title="W", title_raw="W", season=1, group_name="G1")
    l = Bangumi(official_title="L", title_raw="L", season=1, group_name="G2")
    db_session.add_all([w, l])
    await db_session.flush()
    await db_session.commit()
    return w, l


@pytest_asyncio.fixture
async def merge_repo(db_session):
    return BangumiMergeHistoryRepository(db_session)


@pytest.mark.integration
class TestMergeHistoryCreate:
    async def test_create(self, merge_repo, db_session, winner_loser):
        w, l = winner_loser
        h = await merge_repo.create(
            winner_id=w.id, loser_id=l.id,
            loser_snapshot={"id": l.id, "official_title": "L"},
            moved_torrent_ids=[10, 11],
            dropped_torrents=[],
            merge_reason="mikan_id_match",
            merged_by="auto_migration",
        )
        await db_session.commit()
        assert h.id is not None
        assert h.undone_at is None
        assert json.loads(h.loser_snapshot)["official_title"] == "L"
        assert json.loads(h.moved_torrent_ids) == [10, 11]


@pytest.mark.integration
class TestMergeHistoryBlacklist:
    async def test_is_blacklisted_after_merge(self, merge_repo, db_session, winner_loser):
        w, l = winner_loser
        await merge_repo.create(
            winner_id=w.id, loser_id=l.id,
            loser_snapshot={}, moved_torrent_ids=[], dropped_torrents=[],
            merge_reason="mikan_id_match", merged_by="auto",
        )
        await db_session.commit()

        # Direction does not matter
        assert await merge_repo.is_pair_blacklisted(w.id, l.id) is True
        assert await merge_repo.is_pair_blacklisted(l.id, w.id) is True

    async def test_blacklist_survives_undone(self, merge_repo, db_session, winner_loser):
        w, l = winner_loser
        h = await merge_repo.create(
            winner_id=w.id, loser_id=l.id,
            loser_snapshot={}, moved_torrent_ids=[], dropped_torrents=[],
            merge_reason="mikan_id_match", merged_by="auto",
        )
        await db_session.commit()

        await merge_repo.mark_undone(h.id, actor="user:admin")
        await db_session.commit()

        # Still blacklisted per spec §11.4
        assert await merge_repo.is_pair_blacklisted(w.id, l.id) is True

    async def test_not_blacklisted_when_no_history(self, merge_repo):
        assert await merge_repo.is_pair_blacklisted(999, 1000) is False


@pytest.mark.integration
class TestMergeHistoryMarkUndone:
    async def test_mark_undone(self, merge_repo, db_session, winner_loser):
        w, l = winner_loser
        h = await merge_repo.create(
            winner_id=w.id, loser_id=l.id,
            loser_snapshot={}, moved_torrent_ids=[], dropped_torrents=[],
            merge_reason="manual_confirm", merged_by="user:x",
        )
        await db_session.commit()

        await merge_repo.mark_undone(h.id, actor="user:admin")
        await db_session.commit()

        reloaded = await merge_repo.get_by_id(h.id)
        assert reloaded.undone_at is not None
        assert reloaded.undone_by == "user:admin"

    async def test_mark_undone_twice_raises(self, merge_repo, db_session, winner_loser):
        w, l = winner_loser
        h = await merge_repo.create(
            winner_id=w.id, loser_id=l.id,
            loser_snapshot={}, moved_torrent_ids=[], dropped_torrents=[],
            merge_reason="manual_confirm", merged_by="user:x",
        )
        await db_session.commit()

        await merge_repo.mark_undone(h.id, actor="user:admin")
        await db_session.commit()

        with pytest.raises(ValueError):
            await merge_repo.mark_undone(h.id, actor="user:admin")


@pytest.mark.integration
class TestMergeHistoryList:
    async def test_list_all(self, merge_repo, db_session, winner_loser):
        w, l = winner_loser
        await merge_repo.create(
            winner_id=w.id, loser_id=l.id,
            loser_snapshot={}, moved_torrent_ids=[], dropped_torrents=[],
            merge_reason="mikan_id_match", merged_by="auto",
        )
        await db_session.commit()
        assert len(await merge_repo.list_all()) >= 1

    async def test_list_active_only(self, merge_repo, db_session, winner_loser):
        w, l = winner_loser
        h1 = await merge_repo.create(
            winner_id=w.id, loser_id=l.id,
            loser_snapshot={}, moved_torrent_ids=[], dropped_torrents=[],
            merge_reason="mikan_id_match", merged_by="auto",
        )
        await db_session.commit()
        await merge_repo.mark_undone(h1.id, actor="user:admin")
        await db_session.commit()

        active = await merge_repo.list_all(active_only=True)
        assert all(r.undone_at is None for r in active)
        assert h1.id not in [r.id for r in active]
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_repositories/test_merge_history.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement repository**

Create `backend/src/module/repositories/merge_history.py`:

```python
"""BangumiMergeHistoryRepository - write-once audit log for merges.

The actual merge transaction (moving torrents, soft-deleting loser) is
implemented in Plan 04. This repo only records history rows and answers
'has this pair ever been merged?' for the permanent-blacklist rule
(spec §11.4).
"""
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from module.domain.models.merge_history import BangumiMergeHistory


class BangumiMergeHistoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, history_id: int) -> Optional[BangumiMergeHistory]:
        return await self.session.get(BangumiMergeHistory, history_id)

    async def create(
        self,
        winner_id: int,
        loser_id: int,
        loser_snapshot: dict,
        moved_torrent_ids: list[int],
        dropped_torrents: list[dict],
        merge_reason: str,
        merged_by: str,
    ) -> BangumiMergeHistory:
        row = BangumiMergeHistory(
            merged_at=datetime.now(timezone.utc),
            merged_by=merged_by,
            merge_reason=merge_reason,
            winner_bangumi_id=winner_id,
            loser_bangumi_id=loser_id,
            loser_snapshot=json.dumps(loser_snapshot, ensure_ascii=False, default=str),
            moved_torrent_ids=json.dumps(moved_torrent_ids),
            dropped_torrents=json.dumps(dropped_torrents, ensure_ascii=False, default=str),
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def mark_undone(self, history_id: int, actor: str) -> None:
        row = await self.get_by_id(history_id)
        if row is None:
            raise ValueError(f"merge history id={history_id} not found")
        if row.undone_at is not None:
            raise ValueError(f"merge history id={history_id} already undone")
        row.undone_at = datetime.now(timezone.utc)
        row.undone_by = actor
        await self.session.flush()

    async def is_pair_blacklisted(self, a_id: int, b_id: int) -> bool:
        """Return True if (a, b) or (b, a) appears in history (direction-agnostic).

        Per spec §11.4 undone status is irrelevant: once merged, the pair is
        permanently excluded from auto-merge.
        """
        stmt = select(BangumiMergeHistory.id).where(
            or_(
                and_(
                    BangumiMergeHistory.winner_bangumi_id == a_id,
                    BangumiMergeHistory.loser_bangumi_id == b_id,
                ),
                and_(
                    BangumiMergeHistory.winner_bangumi_id == b_id,
                    BangumiMergeHistory.loser_bangumi_id == a_id,
                ),
            )
        ).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_all(self, active_only: bool = False) -> list[BangumiMergeHistory]:
        stmt = select(BangumiMergeHistory).order_by(BangumiMergeHistory.merged_at.desc())
        if active_only:
            stmt = stmt.where(BangumiMergeHistory.undone_at.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_repositories/test_merge_history.py -v
```

Expected: 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /Users/tk/ws/Auto_Bangumi && \
  git add backend/src/module/repositories/merge_history.py \
          backend/src/tests/test_repositories/test_merge_history.py && \
  git commit -m "feat: BangumiMergeHistoryRepository with permanent-blacklist lookup"
```

---

### Task 13: Full test-suite sanity pass

**Files:** None.

- [ ] **Step 1: Run unit + migration tests**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_repositories/ src/tests/test_domain/ src/tests/test_services/ src/tests/test_migrations/ -q
```

Expected: all previous tests still green plus new Phase 1 tests green. The `1051` baseline should grow by roughly 56 (14 normalize + 8 ORM smoke + 10 series + 8 mikan_ref + 8 pending + 8 merge + 3 migration chain).

- [ ] **Step 2: Run full e2e suite**

```bash
cd /Users/tk/ws/Auto_Bangumi/backend && \
  uv run python -m pytest src/tests/test_e2e/ -q
```

Expected: `144 passed, 1 xfailed` (unchanged from Plan 01 baseline). Phase 1 does not alter any existing pipeline code, so e2e count must stay the same.

If any e2e test fails, STOP and investigate — do not continue to Plan 03.

- [ ] **Step 3: Re-run production DB smoke test to verify chain applies cleanly**

```bash
cp ~/autobangumi/ab-data/bangumi.db /tmp/prod_smoke_p1.db && \
cd /Users/tk/ws/Auto_Bangumi/backend && \
AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/prod_smoke_p1.db" \
  uv run python -c "
import asyncio, sys
sys.path.insert(0, 'src')
from module.database.migrate import run_migrations
asyncio.run(run_migrations())
print('OK')
" && \
sqlite3 /tmp/prod_smoke_p1.db "SELECT version_num FROM alembic_version; SELECT 'bangumi',COUNT(*) FROM bangumi UNION ALL SELECT 'torrent',COUNT(*) FROM torrent UNION ALL SELECT 'series',COUNT(*) FROM series;"
```

Expected:
- `alembic_version` = `0005_add_merge_history`
- `bangumi` count unchanged (62 as of 2026-04-17 snapshot)
- `torrent` count unchanged (523)
- `series` count = 0 (Phase 1 does not populate series; Plan 04 does that)

No commit — observation only.

---

## Post-Plan Verification Checklist

After all tasks complete:

- [ ] `cd backend && uv run alembic history` prints a linear chain: `<base> -> 0001_baseline -> 0002_add_series -> 0003_add_mikan_ref -> 0004_add_pending_enrichment -> 0005_add_merge_history (head)`
- [ ] `cd backend && rm -f /tmp/fresh.db && AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/fresh.db" uv run alembic upgrade head && AB_ALEMBIC_DB_URL="sqlite+aiosqlite:////tmp/fresh.db" uv run alembic current` prints `0005_add_merge_history (head)`
- [ ] `cd backend && uv run python -m pytest src/tests/ -q` reports `1107+ passed`
- [ ] `cd backend && uv run python -m pytest src/tests/test_e2e/ -q` reports `144 passed, 1 xfailed`
- [ ] Production DB copy smoke test: all counts unchanged on legacy columns; new tables exist and are empty
- [ ] `grep -rn "bangumi.save_path\|official_title\|title_raw\|poster_link" backend/src/module/repositories/ backend/src/module/services/` — existing code still references these columns (they are untouched in Phase 1)
- [ ] `git log --oneline refactor/backendv2` shows Plan 01 commits followed by Plan 02 commits

---

## Commit Summary (Phase 1)

Approximate commit sequence:

1. `feat: add opencc dependency for title normalization`
2. `feat: normalize_title for series fallback identity`
3. `feat: Series ORM + alembic 0002 add_series`
4. `feat: MikanEpisodeRef ORM + alembic 0003 add_mikan_ref`
5. `feat: PendingTorrentEnrichment ORM + alembic 0004 add_pending_enrichment`
6. `feat: BangumiMergeHistory ORM + alembic 0005 add_merge_history`
7. `test: full Phase 1 alembic chain upgrade/downgrade/cycle`
8. `test: shared db_session fixture for repository tests` (or amended existing)
9. `feat: SeriesRepository with tier-1/tier-2 identity lookup`
10. `feat: MikanEpisodeRefRepository with health metrics`
11. `feat: PendingTorrentEnrichmentRepository staging queue`
12. `feat: BangumiMergeHistoryRepository with permanent-blacklist lookup`

---

## Exit Criteria

Phase 1 is complete when:

1. Four new tables exist at head revision `0005_add_merge_history`
2. All four ORM models + repositories ship with unit tests
3. `normalize_title()` passes the spec §7 test matrix
4. Full test suite green: unit (~1107) + e2e (144 + 1 xfailed)
5. Production DB smoke test confirms row counts on legacy tables unchanged
6. Plan 03 (MikanResolver + rate limiter + RSS pipeline integration) can start using these new repositories without schema changes to existing tables

---

## Known Follow-ups (tracked for later plans)

- **Plan 03:** MikanResolver HTTP scraper, three-tier identity resolver, per-RSS lock, rate limiter, RSS pipeline integration
- **Plan 04:** Modify `bangumi` table (drop deprecated columns, add `series_id` NOT NULL, partial unique indexes), merge transaction logic, `migrate_duplicates.py` script, rename pipeline changes
- **Plan 05:** API rewrite (`/api/v1/series`, `/api/v1/merge-history`, `/api/v1/health/mikan`), WebUI pages, Dashboard banner
