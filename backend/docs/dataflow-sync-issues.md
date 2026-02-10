# Backend Dataflow Cross-Reference: Unsynchronized Paths

> Generated: 2026-02-09
> Branch: refactor/backend
> Scope: All paths that create/modify Bangumi, Torrent, and RSSItem records

## Data Models

| Model | Key mutable fields |
|-------|-------------------|
| **Bangumi** | `save_path`, `added`, `deleted`, `pending_review`, `eps_collect`, `filter`, `year`, `rss_id`, `global_filter_matches` |
| **Torrent** | `downloaded`, `pikpak_cloud_path`, `renamed_at`, `renamed_file_count`, `state`, `bangumi_id` |
| **RSSItem** | `last_status`, `enabled` |

## Bangumi Creation Paths

| Path | File | `save_path` has year? | `added` | `eps_collect` | `year` set? |
|------|------|-----------------------|---------|---------------|-------------|
| `add_rss` (non-aggregate) | `api/v1/rss.py:130` | YES | False | False | YES |
| `_auto_create_bangumi` (aggregate refresh) | `services/rss_engine.py:173` | **NO** | True | False | **NO** |
| `create_bangumi_from_torrent` | `services/rss_engine.py:429` | **NO** | False | False | **NO** |
| `subscribe_season` | `services/collector.py:330` | YES | True | True | YES |
| `subscribe_batch` | `services/collector.py:475` | YES | True | True | YES |

## All Issues

### ISSUE 1 (HIGH): `save_path` generation missing `year` in multiple paths

`gen_save_path(base, title, season, year)` produces `<base>/<title (year)>/Season <n>` with year, but `<base>/<title>/Season <n>` without.

| Path | Passes `year`? | Location |
|------|---------------|----------|
| `add_rss` (non-aggregate) | YES | `api/v1/rss.py:130` |
| `subscribe_season` | YES | `services/collector.py:330` |
| `subscribe_batch` | YES | `services/collector.py:475` |
| `update_rule` (`_gen_save_path`) | YES | `api/v1/bangumi.py:28` |
| `_auto_create_bangumi` (aggregate refresh) | **NO** | `services/rss_engine.py:173` |
| `create_bangumi_from_torrent` | **NO** | `services/rss_engine.py:429` |
| `download_bangumi` fallback | **NO** | `services/rss_engine.py:568` |
| `refresh_rss` inline download fallback | **NO** | `services/rss_engine.py:335` |

**Impact**: Auto-created bangumi from aggregate RSS get `save_path` without year (e.g., `/downloads/Bangumi/Title/Season 1`). If the same bangumi is manually recreated via subscribe, the new path becomes `/downloads/Bangumi/Title (2025)/Season 1`. Files end up in different directories. The renamer reads `bangumi.save_path` and moves files there, so this causes file location mismatches.

---

### ISSUE 2 (HIGH): `year` field never set on auto-created bangumi

`_auto_create_bangumi` (`rss_engine.py:176-195`) builds the create dict but **never includes `"year"` key**. Even if `bangumi_data` from the parser had a year attribute, it is discarded.

Meanwhile, `add_rss` includes `"year": data.year` where data comes from `analyser.link_to_data()` which can extract year from Mikan/TMDB metadata.

**Impact**: Same show added via aggregate RSS (`year=None`) vs manual add (`year="2025"`) produces different save_paths and different DB records. This compounds Issue 1.

---

### ISSUE 3 (LOW): `added` flag set inconsistently

| Path | `added` value |
|------|--------------|
| `add_rss` (non-aggregate) | `False` |
| `_auto_create_bangumi` | `True` |
| `create_bangumi_from_torrent` | `False` |
| `subscribe_season` | `True` |
| `subscribe_batch` | `True` |

**Impact**: `added` is not currently used in `get_active()` filter or any gating logic, so this is cosmetic. But inconsistent state could cause issues if future code relies on it.

---

### ISSUE 4 (HIGH): Existing un-downloaded torrents never retried during refresh

In `rss_engine.py:308-343`:

```python
if matched_torrents:
    inserted_count = await torrent_repo.add_all_or_ignore(matched_torrents)
    if inserted_count > 0:  # <-- only downloads if NEW rows were inserted
        for torrent in matched_torrents:
            ...
```

If `inserted_count == 0` (all torrents already exist in DB), the entire download loop is skipped. Torrents that were inserted in a previous refresh but never successfully downloaded (`downloaded=False`) will never be retried.

**Impact**: Orphaned torrent records with `downloaded=False` that permanently miss their download window.

---

### ISSUE 5 (MEDIUM): `mark_downloaded_by_hash` skipped when `db_torrent` is None

In `rss_engine.py:314-341`:

```python
db_torrent = await torrent_repo.get_by_hash(torrent.hash)
# ... download happens ...
if success:
    if db_torrent:  # <-- what if None?
        await torrent_repo.mark_downloaded_by_hash(...)
```

After `add_all_or_ignore`, the torrent exists in DB. But `get_by_hash` can return None if the torrent hash is None. If `db_torrent` is None, the download is sent to the downloader but `mark_downloaded_by_hash` is never called.

**Impact**: Torrent added to downloader but DB shows `downloaded=False`, `pikpak_cloud_path=None`. The torrent becomes a phantom — exists in downloader but DB doesn't know.

---

### ISSUE 6 (LOW): `pikpak_cloud_path` semantics are confused

`mark_downloaded_by_hash` sets `pikpak_cloud_path = save_path` where `save_path` is the bangumi's save path, not a PikPak-specific cloud path.

| Caller | What gets stored |
|--------|-----------------|
| `refresh_rss` inline download | `bangumi.save_path or gen_save_path(...)` |
| `download_bangumi` | `bangumi.save_path or gen_save_path(...)` |
| `collect_season` | `bangumi.save_path or gen_save_path(...)` |
| `download_torrent` (API) | `bangumi.save_path` directly |
| `clear_rename_status` | `new_cloud_path` param (from `update_rule`) |

**Impact**: For qBittorrent users, the field stores local filesystem paths. If the user switches downloader type, the field contains stale data from the previous downloader. The PikPak renamer reads this field as the cloud folder path (`pikpak.py:619`).

---

### ISSUE 7 (MEDIUM): enable/disable naming confusion — two separate flag systems

| Operation | What it does |
|-----------|-------------|
| API `enable_rule()` | Sets `deleted = False` |
| API `disable_rule()` | Sets `deleted = True` |
| Repo `enable()` | Sets `pending_review = False` |
| Repo `disable()` | Sets `pending_review = True` |

Both `deleted` and `pending_review` must be `False` for `get_active()` to include a bangumi. A bangumi can be in states:
- `deleted=True, pending_review=False` — disabled by user
- `deleted=False, pending_review=True` — auto-disabled by filter
- `deleted=True, pending_review=True` — both flags set

**Impact**: Re-enabling only clears ONE flag. If a bangumi has BOTH flags set, `enable_rule` only clears `deleted` but `pending_review=True` still keeps it inactive. The user has no way to clear both flags in one operation (except `activate_pending_bangumi` which only works for pending_review).

---

### ISSUE 8 (MEDIUM): `enable_rule` doesn't re-trigger downloads

When a user disables a bangumi (`deleted=True`), new torrents during `refresh_rss` are skipped (not matched because `get_active()` excludes deleted). When re-enabled via `enable_rule`, only `deleted=False` is set. No re-download is triggered for torrents that appeared while disabled.

**Impact**: Missed episodes between disable and re-enable are never downloaded unless user manually triggers refresh or download.

---

### ISSUE 9 (HIGH): Soft-deleted bangumi blocks aggregate re-creation

`get_by_composite_key` filters `deleted == False`. So if a bangumi was soft-deleted (`deleted=True`), `_auto_create_bangumi` during aggregate RSS refresh won't find it via `get_by_composite_key`.

However, the DB unique constraint `(official_title, season, group_name)` still holds the deleted row. The `bangumi_repo.create()` call raises `ValueError` (caught at `rss_engine.py:207`). The fallback `get_by_composite_key` still can't find the deleted record.

**Impact**: After soft-deleting a bangumi from aggregate RSS, the next refresh silently fails to re-create it. The show is effectively permanently removed from aggregate RSS even though the RSS feed still contains it. Only a hard delete (`delete_rule`) would free the unique constraint.

---

### ISSUE 10 (MEDIUM): Manual re-download uses updated save_path

In `bangumi.py:474-486`:

```python
success = await downloader.add_torrents(
    urls=[torrent.url],
    save_path=bangumi.save_path or "",
)
if success:
    torrent.pikpak_cloud_path = bangumi.save_path
```

If `bangumi.save_path` was updated (e.g., via `update_rule` which regenerates it with year), the torrent downloads to the NEW path. But previously downloaded files remain in the OLD path.

**Impact**: Files for the same bangumi scattered across different directories. The renamer tries to rename based on current `bangumi.save_path`, potentially not finding files in old locations.

---

### ISSUE 11 (LOW): Two parallel ORM models with different fields

| Layer | Torrent fields |
|-------|---------------|
| SQLModel (`models/torrent.py`) | Missing `state`, `pikpak_task_id` |
| Domain (`domain/models/torrent.py`) | Has `state`, `pikpak_task_id` |

The repositories import from `domain/models/` while the service layer sometimes creates SQLModel `Torrent` instances. When `add_all_or_ignore` processes them, it falls back to `TorrentState.PENDING` (line 44: `state if state is not None else TorrentState.PENDING`).

**Impact**: Works by accident. Any new domain-only fields added in the future won't be populated when created via the SQLModel path.

---

### ISSUE 12 (MEDIUM): Subscribe/refresh race condition

`subscribe_season` sets `rss.last_status = "Recreating"` and `refresh_rss` checks for this to skip. But:

1. `subscribe_season` commits the bangumi creation BEFORE downloading torrents
2. Between commit and download, `refresh_rss` could see the new bangumi and try to download the same torrents
3. If the refresh started BEFORE the status was set to "Recreating", it's already past the check

**Impact**: Duplicate download requests to PikPak/qBittorrent during recreation. PikPak's `_delete_existing_tasks_for_redownload` partially mitigates this. qBittorrent would reject the duplicate.

---

### ISSUE 13 (MEDIUM): Rename state stuck at RENAMING on failure

In `renamer.py:164-175`, if rename fails in `rename_all()`, `state` stays at `RENAMING` but `renamed_at` stays `None`. On next rename cycle:
- `get_unrenamed()` picks it up again (`renamed_at IS NULL`)
- `TorrentStateMachine.start_rename()` throws (RENAMING→RENAMING not valid)
- Exception caught at debug level, processing continues anyway

**Impact**: Works by accident (exception swallowed, processing continues). But the state is semantically incorrect and the torrent is re-processed every 60s, wasting cycles. In `rename_bangumi()` (API path), the same issue exists but rollback IS implemented (line 418-420).

---

### ISSUE 14 (LOW): `get_unrenamed()` ignores `torrent.state`

Query: `WHERE downloaded=True AND renamed_at IS NULL`

This means torrents in states like `PENDING`, `DOWNLOADING`, `ERROR`, `STALE`, `MISSING` could be picked up for rename if they happen to have `downloaded=True`.

**Impact**: The state machine provides no real gating for the rename job. Only `downloaded` and `renamed_at` matter. This makes the state enum partially decorative for the rename flow.

---

### ISSUE 15 (HIGH): `_auto_create_bangumi` never stores `year` in create dict

The create dict at `rss_engine.py:176-195` does not include a `"year"` key. Even if `bangumi_data` from `raw_parser()` had year information, it is silently discarded.

**Impact**: All auto-created bangumi have `year=None` in the database. This is the root cause of Issue 1 (save_path without year) and causes permanent data divergence between auto-created and manually-added bangumi for the same show.

---

## Fields Modified By Multiple Paths (Cross-Reference Matrix)

| Field | `add_rss` | `subscribe` | `auto_create` | `refresh_rss` | `rename_job` | `update_rule` | `enable/disable` | `download_torrent` |
|-------|-----------|-------------|---------------|---------------|-------------|---------------|-------------------|-------------------|
| `bangumi.save_path` | SET (w/year) | SET (w/year) | SET (no year) | — | — | SET (w/year) | — | — |
| `bangumi.added` | False | True | True | — | — | user value | — | — |
| `bangumi.deleted` | False | False | False | — | — | user value | True/False | — |
| `bangumi.pending_review` | False→True | False→True | False→True | True (filter) | — | — | — | — |
| `bangumi.eps_collect` | False | True | False | — | — | user value | — | — |
| `bangumi.year` | parsed | parsed | **NEVER SET** | — | — | user value | — | — |
| `torrent.downloaded` | True | True | — | True | — | — | — | True |
| `torrent.pikpak_cloud_path` | save_path | save_path | — | save_path | — | new_path | — | bangumi.save_path |
| `torrent.renamed_at` | — | — | — | — | now() | None (if changed) | — | None |
| `torrent.state` | PENDING | PENDING | — | PENDING | RENAMING→RENAMED | — | — | — |

## Priority Recommendation

**Fix first (HIGH — real data inconsistency in normal usage):**
1. Issues 1, 2, 15 — Add `year` to `_auto_create_bangumi` and `create_bangumi_from_torrent`, pass `year` to all `gen_save_path` calls
2. Issue 4 — Re-attempt download for existing un-downloaded torrents during refresh
3. Issue 9 — Handle soft-deleted bangumi in unique constraint check during auto-create

**Fix second (MEDIUM — edge cases and correctness):**
4. Issue 5 — Guard against `db_torrent=None` in refresh download loop
5. Issue 7 — Clarify enable/disable semantics or merge the two flag systems
6. Issue 8 — Optionally re-trigger download on enable
7. Issue 12 — Improve race condition handling between subscribe and refresh
8. Issue 13 — Add state rollback in `rename_all()` failure path

**Fix later (LOW — cosmetic/future-proofing):**
9. Issues 3, 6, 11, 14 — Flag consistency, naming, ORM unification
