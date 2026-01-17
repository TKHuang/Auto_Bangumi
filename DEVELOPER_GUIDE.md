# AutoBangumi Developer Guide

> **Comprehensive documentation for understanding and developing AutoBangumi**

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Background Jobs](#background-jobs)
4. [RSS Management](#rss-management)
5. [Settings Hierarchy](#settings-hierarchy)
6. [Data Models](#data-models)
7. [Key Code Paths](#key-code-paths)
8. [Development Setup](#development-setup)
9. [API Reference](#api-reference)

---

## Project Overview

AutoBangumi is an automated anime/bangumi subscription and download management system. It:
- Monitors RSS feeds from sources like Mikan (蜜柑计划)
- Automatically downloads new episodes via BitTorrent (qBittorrent)
- Renames files following standard naming conventions (e.g., `S01E01`)
- Provides a web UI for management

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    API Layer (/api/v1)                                │   │
│  │   auth | bangumi | config | log | program | rss | search              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────────┤
│                         Core Layer                                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │  Program   │  │ RSSThread  │  │RenameThread│  │   Status   │            │
│  │ (startup)  │  │ (cron job) │  │ (cron job) │  │  (checker) │            │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘            │
├─────────────────────────────────────────────────────────────────────────────┤
│                       Business Logic Layer                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                    │
│  │   RSS    │  │  Parser  │  │ Manager  │  │ Searcher │                    │
│  │ Engine   │  │  Title   │  │ Renamer  │  │ Provider │                    │
│  │ Analyser │  │  Mikan   │  │ Collector│  │          │                    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                       Infrastructure Layer                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐                    │
│  │ Database │  │ Network  │  │Downloader│  │Notification│                   │
│  │ SQLModel │  │ Requests │  │qBittorrent│ │  Telegram │                   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Project Structure

```
Auto_Bangumi/
├── backend/
│   └── src/
│       ├── main.py                 # FastAPI app entry point
│       └── module/
│           ├── api/                # REST API endpoints
│           ├── core/               # Program, threads, status
│           ├── rss/                # RSS engine & analyser
│           ├── parser/             # Title parsing (raw, mikan, tmdb)
│           ├── database/           # SQLModel ORM layer
│           ├── downloader/         # qBittorrent client
│           ├── manager/            # Renamer, collector
│           ├── network/            # HTTP requests, RSS fetching
│           ├── models/             # Pydantic/SQLModel models
│           ├── conf/               # Settings management
│           └── notification/       # Telegram, etc.
└── webui/                          # Vue 3 frontend
```

---

## Background Jobs

Two background threads run continuously (cron-like behavior):

### RSSThread

**File:** `backend/src/module/core/sub_thread.py`

**Interval:** `settings.program.rss_time` (default: 900 seconds)

```python
def rss_loop(self):
    while not self.stop_event.is_set():
        with DownloadClient() as client, RSSEngine() as engine:
            # STEP 1: Discover new bangumi from aggregate feeds
            rss_list = engine.rss.search_aggregate()
            for rss in rss_list:
                self.analyser.rss_to_data(rss, engine)
            
            # STEP 2: Download new episodes for all active feeds
            engine.refresh_rss(client)
        
        # STEP 3: (Optional) Collect full seasons
        if settings.bangumi_manage.eps_complete:
            eps_complete()
        
        self.stop_event.wait(settings.program.rss_time)
```

### RenameThread

**File:** `backend/src/module/core/sub_thread.py`

**Interval:** `settings.program.rename_time` (default: 60 seconds)

```python
def rename_loop(self):
    while not self.stop_event.is_set():
        with Renamer() as renamer:
            renamed_info = renamer.rename()
        
        if settings.notification.enable:
            with PostNotification() as notifier:
                for info in renamed_info:
                    notifier.send_msg(info)
                    time.sleep(2)
        
        self.stop_event.wait(settings.program.rename_time)
```

---

## RSS Management

### RSS Processing Flow

```
┌────────────────────────────────────────────────────────────────┐
│  STEP 1: DISCOVER NEW BANGUMI                                  │
│  Query: aggregate=True AND enabled=True                        │
│                                                                │
│  FOR each RSS:                                                 │
│    1. get_torrents(rss.url) [GLOBAL filter applied]           │
│    2. match_list() - remove known bangumi                      │
│    3. raw_parser() for new ones [GLOBAL language/OpenAI]       │
│    4. official_title_parser() [PER-RSS parser setting]         │
│    5. bangumi.add_all() - save to database                     │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  STEP 2: DOWNLOAD NEW EPISODES                                 │
│  Query: enabled=True                                           │
│                                                                │
│  FOR each RSS:                                                 │
│    1. _get_torrents(rss) [GLOBAL filter applied]              │
│    2. check_new() - not in database                           │
│    3. FOR each new torrent:                                    │
│       a. match_torrent() [PER-BANGUMI filter]                 │
│       b. client.add_torrent()                                  │
│    4. torrent.add_all()                                        │
└────────────────────────────────────────────────────────────────┘
```

### RSS Processing Modes

| `aggregate` | `enabled` | Behavior |
|-------------|-----------|----------|
| `True` | `True` | Discovers NEW bangumi + Downloads for existing |
| `False` | `True` | Downloads for existing bangumi only |
| `*` | `False` | Completely ignored |

---

## Settings Hierarchy

```
GLOBAL (config.json)
  └── settings.rss_parser.filter      → Default exclusion filter
  └── settings.rss_parser.language    → Title language preference
  └── settings.bangumi_manage.enable  → Master switch for renamer
        │
        ▼
PER-RSS (RSSItem table)
  └── enabled                         → Process this feed
  └── aggregate                       → Discover NEW bangumi
  └── parser                          → mikan/tmdb/raw
        │
        ▼
PER-BANGUMI (Bangumi table)
  └── filter                          → Custom exclusion filter
  └── deleted                         → Soft-disable
  └── offset                          → Episode number offset
```

### Filter Behavior (Important!)

Filters are **EXCLUSION** patterns - torrents matching the filter are **REJECTED**:

```python
# Global filter applied at fetch time
if re.search(_filter, torrent_title) is None:  # NOT matching = keep
    torrents.append(torrent)

# Per-bangumi filter applied at match time  
if not re.search(bangumi.filter, torrent.name):  # NOT matching = accept
    return matched_bangumi
```

Default filter: `["720", "\\d+-\\d"]` excludes 720p and batch releases.

### Filter Inheritance

```
GLOBAL settings.rss_parser.filter: ["720", "\\d+-\\d"]
                    │
                    ▼ (copied at bangumi creation time)
PER-BANGUMI bangumi.filter: "720,\\d+-\\d"  (comma-separated)
                    │
                    ▼ (user can modify via API)
CUSTOMIZED bangumi.filter: "720,HEVC"  (per-show overrides)
```

**Note:** Changing global filter does NOT retroactively update existing bangumi.

---

## Data Models

### Core Models

```python
class RSSItem(SQLModel, table=True):
    id: int
    name: Optional[str]
    url: str                    # RSS feed URL
    aggregate: bool = False     # Discover new bangumi
    parser: str = "mikan"       # Parser type: mikan/tmdb/raw
    enabled: bool = True

class Bangumi(SQLModel, table=True):
    id: int
    official_title: str         # Display title
    title_raw: str              # Raw title for matching
    season: int = 1
    filter: str                 # Exclusion filter
    rss_link: str               # Associated RSS URLs
    deleted: bool = False       # Soft-delete
    eps_collect: bool = False   # Full season collected

class Torrent(SQLModel, table=True):
    id: int
    bangumi_id: Optional[int]   # FK to Bangumi
    rss_id: Optional[int]       # FK to RSSItem
    name: str
    url: str                    # Torrent/magnet URL
    downloaded: bool = False
```

### Model Relationships

```
RSSItem (1) ←─────── (N) Torrent (N) ───────→ (1) Bangumi
   │                      │                        │
   │ rss_id               │ bangumi_id             │
   └──────────────────────┴────────────────────────┘
```

---

## Key Code Paths

### New Episode Detection
```
RSS URL → get_xml() → rss_parser() → get_torrents()
       → check_new() → match_torrent() → add_torrent()
```

### New Bangumi Discovery
```
RSS URL → get_torrents() → match_list() → raw_parser()
       → official_title_parser() → bangumi.add_all()
```

### File Rename
```
get_torrent_info() → check_files() → torrent_parser()
       → gen_path() → rename_torrent_file() → notify()
```

---

## Development Setup

### Backend (Hot Reload)

```bash
cd backend
./dev.sh
# Swagger docs: http://localhost:7892/docs
```

### Frontend (Hot Reload)

```bash
cd webui
pnpm install
pnpm dev
```

**Note:** Update `webui/vite.config.ts` proxy target to `http://localhost:7892` for local dev.

---

## API Reference

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/status` | Get program status |
| GET | `/api/v1/start` | Start background threads |
| GET | `/api/v1/stop` | Stop background threads |
| GET | `/api/v1/rss` | List all RSS feeds |
| POST | `/api/v1/rss/add` | Add new RSS feed |
| POST | `/api/v1/rss/analysis` | Parse RSS link |
| GET | `/api/v1/bangumi/get/all` | List all bangumi |
| PATCH | `/api/v1/bangumi/update/{id}` | Update bangumi settings |

### Example: Add RSS Feed

```http
POST /api/v1/rss/add
Content-Type: application/json

{
  "url": "https://mikanani.me/RSS/Bangumi?bangumiId=xxx",
  "name": "My Anime",
  "aggregate": true,
  "parser": "mikan"
}
```

---

## Additional Documentation

For more detailed documentation, check the skill files at:
```
~/.skill-mcp/skills/auto-bangumi-dev/docs/
├── architecture.md       # Detailed architecture
├── rss-settings-flow.md  # RSS processing & settings
└── api-reference.md      # Complete API reference
```
