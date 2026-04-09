# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

AutoBangumi is an automated anime subscription and download management system. It monitors RSS feeds (primarily Mikan Project), auto-downloads via qBittorrent or PikPak, renames files to media-library-friendly format (S01E01), and provides a Vue web UI.

## Build & Run Commands

### Backend (Python/FastAPI)

```bash
cd backend

# Run all e2e tests (~65s, 144 tests)
uv run python -m pytest src/tests/test_e2e/ -q

# Run a specific test module
uv run python -m pytest src/tests/test_repositories/test_torrent.py -q

# Run a single test
uv run python -m pytest src/tests/test_repositories/test_torrent.py::TestTorrentRepository::test_create_torrent_success -q

# Run unit tests (fast, no network)
uv run python -m pytest src/tests/test_repositories/ src/tests/test_domain/ src/tests/test_services/ -q

# Dev server (without Docker)
uv run uvicorn main:app --reload --port 7893 --app-dir src
```

### WebUI (Vue 3 + Vite)

```bash
cd webui
pnpm install
pnpm dev          # dev server
pnpm build        # production build
pnpm test         # vitest
pnpm lint:fix     # eslint
pnpm format       # prettier
```

### Docker development

```bash
make dev           # start dev environment (docker compose)
make down          # stop
make logs-backend  # follow backend logs
make clean         # stop + remove volumes
```

## Architecture

### Layered Backend (backend/src/)

```
API (api/v1/)  →  Services (services/)  →  Repositories (repositories/)  →  Domain Models (domain/models/)
                      ↓                         ↓
               Downloader (services/downloader/)  Database (database/engine.py)
```

- **Domain Models** (`domain/models/`): SQLAlchemy ORM models (Bangumi, Torrent, RSSItem, User). All inherit from `Base` + `TimestampMixin` + `VersionMixin`.
- **Repositories** (`repositories/`): Async data access, one per entity. Each takes `AsyncSession` in constructor.
- **Services** (`services/`): Business logic. Key services:
  - `rss_engine.py` — RSS feed parsing, torrent matching, filter logic
  - `collector.py` — Season subscription, bangumi creation, download orchestration
  - `renamer.py` — File rename to S01E01 format
  - `downloader/` — Protocol-based abstraction. Factory creates qBittorrent or PikPak.
- **API** (`api/v1/`): FastAPI routers. Auth via OAuth2 form-data (username/password), JWT tokens.
- **Scheduler** (`scheduler/`): APScheduler v4 (alpha) wrapping `AsyncScheduler`. Two recurring jobs: `rss_refresh` and `rename`.

### Database

SQLite via `aiosqlite` + SQLAlchemy async. Schema created via `Base.metadata.create_all` on startup. Manual migrations in `main.py:_run_migrations()` (PRAGMA-based column detection, no Alembic).

### Downloader Protocol

`services/downloader/interface.py` defines `DownloaderProtocol`. Implementations: `QBittorrentDownloader`, `PikPakDownloader`. Factory in `factory.py` (PikPak instances are cached for auth token reuse).

### WebUI

Vue 3 + Vite + UnoCSS. Pages in `webui/src/pages/`, API clients in `webui/src/api/`. i18n with `en.json`/`zh-CN.json`.

## Key Patterns

### Filter Logic

Filters are **exclusion** patterns. Torrents matching the regex are **rejected**:
```python
if re.search(bangumi.filter, torrent.name):  # match = reject
```
Global filter applied at RSS fetch time. Per-bangumi filter applied at match time. Comma-separated, converted to `|` regex.

### TorrentState

The `state` field on Torrent has 10 enum values but only `EXCLUDED` is actively used. All normal torrents stay at `PENDING` (the default). Real-time download status comes from querying the downloader API directly via `downloader.torrents_info()`. **Any query returning user-visible torrents must filter `state != EXCLUDED`** — use `get_visible_by_bangumi()` or `get_visible_by_rss()` instead of `get_by_bangumi()` / `get_by_rss()`.

### Excluded Torrents

When users manually deselect torrents during RSS subscription, sentinel rows are inserted with `name=""`, `url=""`, `downloaded=True`, `state=EXCLUDED`. These prevent cronjob re-downloads via the `(hash, bangumi_id)` unique constraint. They must never appear in UI queries or enter the rename pipeline.

### Startup Migrations

`main.py:_run_migrations()` runs on every startup inside `conn.run_sync()`. Uses PRAGMA table_info to detect missing columns, then ALTER TABLE. Idempotent.

## Testing

- **Test isolation**: E2E tests use `_reset_database()` which disposes the engine and deletes the DB file per test.
- **APScheduler hang fix**: E2E conftest patches `AsyncScheduler.stop` with a no-op to prevent cancel-scope issues in TestClient teardown.
- **RequestContent patching**: Must patch `RequestContent` in ALL consuming modules, not just the source module.
- **Fixtures**: `backend/src/tests/fixtures/` has sample RSS XML, config JSON, and HTML pages.
- **Auth in tests**: OAuth2 form-data: `POST /api/v1/auth/login` with `username=admin&password=adminadmin`.

## Configuration

Settings loaded from `config/config.json` (mounted volume in Docker). Key config paths:
- `downloader.type`: `"qbittorrent"` or `"pikpak"`
- `downloader.path`: Base save path for downloads
- `program.rss_time`: RSS refresh interval (seconds)
- `program.rename_time`: Rename check interval (seconds)
