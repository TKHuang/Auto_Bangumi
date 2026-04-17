# Bangumi Identity Refactor (Backend v2) — Design Spec

- **Status**: Draft
- **Date**: 2026-04-17
- **Branch**: `refactor/backendv2`
- **Scope**: Backend schema, RSS pipeline, rename pipeline, WebUI alignment
- **Non-goals (explicit)**: multi-worker deployment, backwards-compatible API, downloader protocol changes

---

## 1. 問題陳述

現行 schema 將 `Bangumi` 的身分鍵定義為 `(official_title, season, group_name)`，等於在資料層明文寫死「同一部番 + 不同字幕組 = 不同 bangumi」。這造成三類實際問題：

1. **字幕組漂移**：同一訂閱週期內 parser 抽出的 `group_name` 字串會變動（例如 `[AAA]` → `[AAA&BBB]`），導致同一部番被建為多筆 bangumi
2. **中文譯名分歧**：不同字幕組對同一部番給出不同中文譯名（例如官方 `LasTame Season2` vs 合作組 `悲剧元凶的最强外道最终BOSS女王为民竭力`），`title_raw` 不同 → 即便人工 normalize 也難以合併
3. **UI 與媒體庫重複**：重複 bangumi 生成重複資料夾，媒體庫（Jellyfin/Plex）看到多個同名 series

此外，現行實作有多處併發與冪等性脆弱點（RSS refresh 無 lock、`update_simple` 繞過樂觀鎖、`_auto_create_bangumi` 為 TOCTOU、migration 無版本化），隨業務成長遲早會爆發。

## 2. 實證資料（來自生產 DB `bangumi.db` 2026-04-17 快照）

```text
bangumi #91: 身为悲剧始作俑者的最强邪恶BOSS女王为民竭心尽力。 第二季
  rss_link : mikanani.me/RSS/Bangumi?bangumiId=3906&subgroupid=370
  group    : 弗里吉亚宫内厅字幕组&LoliHouse
  title_raw: 悲剧元凶的最强外道最终BOSS女王为民竭力

bangumi #93: 身为悲剧始作俑者的最强邪恶BOSS女王为民竭心尽力。 第二季
  rss_link : mikanani.me/RSS/Bangumi?bangumiId=3906&subgroupid=370   ← 完全相同
  group    : LoliHouse
  title_raw: LasTame Season2
```

兩筆共用同一 Mikan `(bangumiId=3906, subgroupid=370)`、同一 poster、同一 save_path，但因為 `group_name` 字串差異被判為不同 bangumi。系統已經**在 rss_link 欄位**擁有正確識別所需資訊，只是 identity 設計沒利用它。

現況統計：62 bangumi、523 torrent、14 rssitem，已知 1 組重複（91/93）。

## 3. 目標

- **G-1** 同一部番（以 Mikan ID 為準）在 DB 中僅有一筆 `Series` 實體
- **G-2** 字幕組漂移不再產生重複 bangumi
- **G-3** 提供受控、可觀測、可回溯的重複合併機制
- **G-4** RSS / Rename 排程有明確併發策略，同時對外部服務（Mikan、PikPak、qBittorrent）有速率節流
- **G-5** Mikan 外部解析失敗時不靜默：UI 必須在合理時間內反映異常
- **G-6** Schema 變更透過 Alembic 版本化，未來可安全演進
- **G-7** Rename 輸出符合 Jellyfin 原生 TV Shows library 命名規範

## 4. 非目標（YAGNI 邊界）

- 不支援多 worker（永遠假設 `uvicorn workers=1`）
- 不支援 Jellyfin Movies 式的「同集多版本」UI stacking（Jellyfin TV shows 原生無此能力）
- 不保留任何 deprecated 欄位、endpoint、WebUI 元件 —— 一次重寫到位
- 不自動匯流跨來源 series（Mikan + nyaa 同一部番）—— 僅提供 `pending_review` 手動確認候選

## 5. 架構總覽

```text
┌────────────────────────────────────────────────────────────────┐
│  RSS Refresh (cron / manual API)                                │
│    ↓                                                             │
│  RssLockRegistry.try_acquire(rss_id)  ← skip-if-held            │
│    ↓                                                             │
│  parse_feed() → list[TransientTorrent]                          │
│    ↓                                                             │
│  enrich_with_mikan()  ── rate_limiter["mikan"] ─→ Mikan          │
│    │   ├─ cache hit  → mikan_episode_ref                        │
│    │   └─ cache miss → fetch + parse + persist                  │
│    ↓                                                             │
│  identity_resolver(torrent)                                      │
│    Tier 1: (mikan_bangumi_id, mikan_subgroup_id) → Series       │
│    Tier 2: (norm_title, season, cour_part) → Series (fallback)  │
│    Tier 3: 無匹配 → 建暫存 series + pending_review              │
│    ↓                                                             │
│  auto-create Bangumi if needed (same-rss, same-subgroup key)    │
│    ↓                                                             │
│  persist Torrent (add_all_or_ignore on (info_hash, bangumi_id)) │
│    ↓                                                             │
│  download via Downloader ── rate_limiter[type] ─→ qB / PikPak    │
│                                                                  │
│  (若 Mikan 階段失敗)                                              │
│    ↓                                                             │
│  persist to pending_torrent_enrichment (staging queue)          │
│    next cron 重試；resolve 成功後轉正                              │
└────────────────────────────────────────────────────────────────┘

Rename (cron, asyncio.Lock):
  get_unrenamed_torrents() filtered by bangumi.active=true
    ↓
  group by series (effective_path = bangumi.path_override or series.root_path)
    ↓
  rename to <series.canonical_title> SNNENN.<ext>
    ↓
  write renamed_at, renamed_file_count
```

## 6. Schema 設計

### 6.1 新增表

#### `series`

```sql
CREATE TABLE series (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  mikan_bangumi_id   INTEGER,                     -- nullable，非 Mikan 來源為 NULL
  canonical_title    TEXT    NOT NULL,            -- 顯示用，取自 Mikan 或使用者編輯
  normalized_title   TEXT    NOT NULL,            -- 正規化後，用於 fallback identity
  season             INTEGER NOT NULL DEFAULT 1,
  cour_part          TEXT,                        -- 'latter'|'former'|'part'|'cour'|NULL
  year               INTEGER,                     -- nullable
  root_path          TEXT    NOT NULL,            -- rename 權威路徑
  poster_url         TEXT,
  default_filter     TEXT,                        -- 預設排除規則（bangumi 可覆寫）
  default_offset     INTEGER DEFAULT 0,
  pending_review     BOOLEAN NOT NULL DEFAULT 0,  -- Tier 3 或跨來源匯流候選
  created_at         DATETIME NOT NULL,
  updated_at         DATETIME NOT NULL,
  version            INTEGER NOT NULL DEFAULT 1,
  CONSTRAINT uq_series_mikan UNIQUE (mikan_bangumi_id),
  CONSTRAINT uq_series_fallback UNIQUE (normalized_title, season, cour_part)
);
CREATE INDEX idx_series_normalized ON series(normalized_title);
```

注意兩條 UNIQUE 互不衝突：Mikan 來源的 series `mikan_bangumi_id` 非 NULL（受第一條約束）；非 Mikan 來源 `mikan_bangumi_id` 為 NULL（在 SQLite 中 NULL 不參與 UNIQUE 判定），身分由第二條守衛。

#### `mikan_episode_ref` (Mikan 頁面抓取快取)

```sql
CREATE TABLE mikan_episode_ref (
  info_hash          TEXT PRIMARY KEY,            -- torrent info_hash (== Mikan URL 最後 hex 段)
  mikan_bangumi_id   INTEGER,
  mikan_subgroup_id  INTEGER,                     -- nullable（有些 item 沒 subgroup）
  canonical_title    TEXT,
  poster_url         TEXT,
  fetched_at         DATETIME NOT NULL,
  attempt_count      INTEGER NOT NULL DEFAULT 0,
  last_error         TEXT,
  parse_status       TEXT NOT NULL                -- 'ok' | 'failed' | 'non_mikan'
);
CREATE INDEX idx_mikan_ref_series ON mikan_episode_ref(mikan_bangumi_id, mikan_subgroup_id);
```

#### `pending_torrent_enrichment` (staging queue)

```sql
CREATE TABLE pending_torrent_enrichment (
  info_hash          TEXT PRIMARY KEY,
  raw_name           TEXT NOT NULL,
  homepage           TEXT NOT NULL,
  url                TEXT NOT NULL,
  rss_id             INTEGER NOT NULL REFERENCES rssitem(id) ON DELETE CASCADE,
  published_at       DATETIME,
  first_seen_at      DATETIME NOT NULL,
  attempt_count      INTEGER NOT NULL DEFAULT 0,
  last_error         TEXT,
  last_attempt_at    DATETIME
);
CREATE INDEX idx_pending_rss ON pending_torrent_enrichment(rss_id);
```

Mikan resolve 成功 → 建立 `torrent` row → 從本表刪除。本表長度即 Dashboard 顯示的 pending 數量。

#### `bangumi_merge_history`

```sql
CREATE TABLE bangumi_merge_history (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  merged_at          DATETIME NOT NULL,
  merged_by          TEXT NOT NULL,               -- 'auto_migration' | 'user:<name>'
  merge_reason       TEXT NOT NULL,               -- 'mikan_id_match' | 'manual_confirm'
  winner_bangumi_id  INTEGER NOT NULL REFERENCES bangumi(id),
  loser_bangumi_id   INTEGER NOT NULL REFERENCES bangumi(id),
  loser_snapshot     TEXT NOT NULL,               -- JSON：loser 合併前完整 row
  moved_torrent_ids  TEXT NOT NULL,               -- JSON array
  dropped_torrents   TEXT NOT NULL,               -- JSON：因 hash 衝突刪除的 torrent 快照
  undone_at          DATETIME,
  undone_by          TEXT
);
CREATE INDEX idx_merge_winner ON bangumi_merge_history(winner_bangumi_id);
CREATE INDEX idx_merge_loser  ON bangumi_merge_history(loser_bangumi_id);
```

### 6.2 修改 `bangumi`

| 操作 | 欄位 | 說明 |
|---|---|---|
| DROP | `save_path` | 移至 `series.root_path` |
| DROP | `official_title` | 取自 `series.canonical_title` |
| DROP | `year` | 移至 series |
| DROP | `season` | 移至 series |
| DROP | `season_raw` | parser 中間產物，不再持久化 |
| DROP | `title_raw` | 同上 |
| DROP | `poster_link` | 移至 `series.poster_url` |
| DROP | UNIQUE `(official_title, season, group_name)` | 由新身分鍵取代 |
| ADD  | `series_id` NOT NULL FK → `series(id)` | |
| ADD  | `mikan_subgroup_id` INTEGER | nullable（fallback 來源可為 NULL） |
| ADD  | `active` BOOLEAN NOT NULL DEFAULT 1 | rename pipeline 只處理 active |
| ADD  | `path_override` TEXT | nullable，opt-in 子資料夾 |
| ADD  | `observed_groups` TEXT | JSON array，歷史 group 字串 |
| KEEP | `rss_id`, `filter`, `offset`, `rule_name`, `dpi`, `source`, `subtitle`, `rss_link`, `added`, `deleted`, `pending_review`, `global_filter_matches` | |
| ADD  | UNIQUE `(series_id, mikan_subgroup_id)` WHERE `deleted = 0` | Mikan 來源身分（partial；排除已 soft-delete 的 merge loser） |
| ADD  | UNIQUE `(series_id, rss_id)` WHERE `mikan_subgroup_id IS NULL AND deleted = 0` | fallback 身分（partial index） |

注意 `group_name` 欄位**保留但非 identity**，僅作為 `observed_groups` 最新值的快捷顯示。

**重要**：兩條 UNIQUE 加上 `WHERE deleted = 0` 是必要的。Merge 流程會把 loser bangumi `deleted=1`，若不排除則 soft-delete 的行會佔用唯一性槽位，合併後無法還原、也無法產生新 bangumi 補位。

### 6.3 修改 `torrent`

| 操作 | 欄位 |
|---|---|
| ADD | `mikan_bangumi_id` INTEGER |
| ADD | `mikan_subgroup_id` INTEGER |
| KEEP | 其餘欄位不變；UNIQUE `(hash, bangumi_id)` 保留 |

### 6.4 身分解析順序

```python
def resolve_series(mikan_ref: MikanRef | None, norm_title: str, season: int, cour: str | None) -> Series:
    # Tier 1: Mikan ID 權威
    if mikan_ref and mikan_ref.bangumi_id:
        s = series_repo.get_by_mikan_id(mikan_ref.bangumi_id)
        if s: return s
        return series_repo.create(mikan_bangumi_id=mikan_ref.bangumi_id, ...)

    # Tier 2: 非 Mikan fallback
    s = series_repo.get_by_fallback(norm_title, season, cour)
    if s: return s

    # Tier 3: 建新 series 標 pending_review；若存在同 (norm_title, season, cour)
    # 的 Mikan series，額外標「疑似匯流候選」
    candidates = series_repo.find_possible_cross_source_merge(norm_title, season, cour)
    s = series_repo.create(pending_review=True, ...)
    if candidates:
        cross_source_merge_candidate_repo.create(new=s.id, candidates=candidates)
    return s
```

## 7. 標題正規化演算法

```python
import unicodedata, re
from opencc import OpenCC

_cc_t2s = OpenCC('t2s')  # Traditional → Simplified

_SEASON_PATTERNS = [
    r'第\s*[0-9一二三四五六七八九十]+\s*[季期]',
    r'[Ss]eason\s*\d+',
    r'\bS\d+\b',
    r'\bSP\b', r'\bOVA\b', r'\bOAD\b',
]

_COUR_PATTERNS = [
    (r'后半部分|後半部分|后半', 'latter'),
    (r'前半部分|前半部分|前半', 'former'),
    (r'第\s*[0-9一二]+\s*部分', 'part'),
    (r'[Pp]art\s*\d+',          'part'),
    (r'[Cc]our\s*\d+',          'cour'),
]

def normalize_title(raw: str) -> tuple[str, str | None]:
    """回傳 (normalized_title, cour_part)。"""
    s = unicodedata.normalize('NFKC', raw)
    s = _cc_t2s.convert(s)

    cour = None
    for pattern, kind in _COUR_PATTERNS:
        if re.search(pattern, s):
            cour = kind
            s = re.sub(pattern, '', s)
            break

    for pattern in _SEASON_PATTERNS:
        s = re.sub(pattern, '', s)

    s = re.sub(r'[^\w\u4e00-\u9fff\u3040-\u30ff]+', '', s)
    return s.lower().strip(), cour
```

### 測試矩陣（unit test 必含）

| 輸入 A | 輸入 B | 期望 |
|---|---|---|
| `Re：从零开始的异世界生活 第二季` | `Re:從零開始的異世界生活 第二季` | norm 相同、cour=None |
| `Re：从零开始的异世界生活 第二季 后半部分` | `Re：从零开始的异世界生活 第二季` | norm 相同、cour 不同 |
| `葬送的芙莉蓮` | `葬送的芙莉莲` | norm 相同 |
| `【我推的孩子】 第三季` | `我推的孩子 第三季` | norm 相同 |
| `咒術迴戰` | `咒术回战` | norm 相同 |

## 8. Mikan 整合

### 8.1 Episode 頁面解析

`homepage` 欄位格式：`https://{base_url}/Home/Episode/{info_hash}`。頁面有三個穩定抽取位置，按可靠度順序 fallback：

```python
def parse_mikan_page(html: str) -> MikanRef | None:
    # (A) subscribe button data attributes (最穩)
    m = re.search(r'data-bangumiid="(\d+)"\s+data-subtitlegroupid="(\d+)"', html)
    if m: return MikanRef(int(m[1]), int(m[2]))

    # (B) bangumi anchor /Home/Bangumi/{id}#{subgroup}
    m = re.search(r'/Home/Bangumi/(\d+)#(\d+)', html)
    if m: return MikanRef(int(m[1]), int(m[2]))

    # (C) RSS link ?bangumiId={id}&subgroupid={sub}
    m = re.search(r'bangumiId=(\d+)&subgroupid=(\d+)', html)
    if m: return MikanRef(int(m[1]), int(m[2]))

    return None
```

同時解析 canonical_title（`.bangumi-title a` 文字）與 poster URL（`.bangumi-poster background-image`）作為 series 初始化資料。

### 8.2 Base URL Config

```json
{
  "mikan": {
    "base_url": "https://mikanani.me",
    "timeout_seconds": 10,
    "max_concurrent": 2,
    "min_interval_ms": 500,
    "health_ok_window_hours": 1,
    "health_down_threshold_hours": 24
  }
}
```

Mikan 更換網域時，使用者改此欄位即可無痛切換，不需重建 image。

### 8.3 阻塞策略

若 RSS 帶入的 torrent 無法解析出 Mikan ID：
1. 寫入 `pending_torrent_enrichment`（不建 torrent、不建 bangumi）
2. 下次 RSS refresh 時，resolver 一併嘗試 staging queue 中舊項目
3. Resolve 成功 → 建 torrent → 從 staging 刪除
4. Dashboard 顯示 pending 數量與「最後成功解析時間」

## 9. 併發控制

### 9.1 Per-RSS Lock（skip-if-held）

```python
class RssLockRegistry:
    _locks: dict[int, asyncio.Lock] = {}
    _registry_mutex = asyncio.Lock()

    async def try_acquire(self, rss_id: int) -> asyncio.Lock | None:
        async with self._registry_mutex:
            lock = self._locks.setdefault(rss_id, asyncio.Lock())
        if lock.locked():
            return None
        await lock.acquire()
        return lock
```

RSS refresh cron + 手動 API 皆穿過此 registry。第二呼叫者 log 後跳過，不排隊。

### 9.2 Rate Limiter（per external service）

```python
class RateLimiter:
    def __init__(self, max_concurrent: int, min_interval_ms: int):
        self._sem = asyncio.Semaphore(max_concurrent)
        self._min_interval = min_interval_ms / 1000
        self._last_at = 0.0
        self._gate = asyncio.Lock()
        self._degraded_until = 0.0
        self._base_concurrent = max_concurrent

    async def __aenter__(self):
        await self._sem.acquire()
        async with self._gate:
            now = time.monotonic()
            wait = self._last_at + self._min_interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_at = time.monotonic()
        return self

    async def __aexit__(self, *exc):
        self._sem.release()

    async def record_result(self, status: int):
        """ 由呼叫端回報 HTTP status，觸發降級/恢復。"""
        ...
```

Registry 中預設三組：
- `mikan`       → max_concurrent=2, interval=500ms
- `pikpak`      → max_concurrent=1, interval=1000ms
- `qbittorrent` → max_concurrent=5, interval=100ms

皆 config 化。

### 9.3 動態降級

收到 HTTP 429/503 → `max_concurrent //= 2`, 冷卻 60 秒。連續 10 次成功 → 恢復至 config 基準。

## 10. Rename Pipeline

### 10.1 有效路徑與檔名

```text
effective_root = bangumi.path_override or series.root_path
target_dir     = {effective_root}/Season {series.season:02d}/
target_file    = {series.canonical_title} S{series.season:02d}E{episode:02d}{ext}
```

`series.root_path` 預設由 config `downloader.path` 加 `series.canonical_title` 形成。

`episode` 來源：沿用現有 `TitleParser.torrent_parser()`，從 torrent 內**檔案名稱**（不是 torrent 名稱）抽出集數；搭配 `bangumi.offset` 調整。此流程不變。

**不把 group_name 寫入檔名**。原因見 §10.2。

### 10.2 Jellyfin 相容性

- Series 資料夾格式：`<canonical_title>` 或 `<canonical_title> (year)`（year 非必要）
- Season 資料夾：`Season NN`（零填充）
- Episode 檔名：`<canonical_title> SNNENN.<ext>` —— Kodi SxxExx 標準
- Jellyfin TV Shows 原生不支援多版本堆疊，放兩個 `S01E01.*.mkv` 會變成 UI 衝突而非版本選擇
- 因此：同 series 同時只允許**一個 active bangumi**，`bangumi.active=false` 的不進 rename pipeline
- 進階使用者若要保留多字幕組版本，透過 `bangumi.path_override` 將檔案導至其他目錄（Jellyfin 會視為不同 series，metadata 分裂，使用者自行承擔）

### 10.3 Active Bangumi 切換流程

1. 使用者在 WebUI 勾選 series 中要 activate 的 bangumi（通常只有一個）
2. 原 active bangumi 自動 deactivate
3. 若新 active bangumi 下載的檔案與既有檔案碰撞（相同 target_file 但 hash 不同）：
   - 預設行為：跳過新檔 rename，log 警告
   - Dashboard 顯示「Rename Conflict」徽章，列出碰撞檔案
   - 使用者可手動選擇保留哪版、或覆寫、或設 `path_override`

## 11. 重複合併

### 11.1 自動合併（migration 期）

`scripts/migrate_duplicates.py`：

```text
--dry-run    印出將合併的 pair 與預估結果
--execute    實際執行
```

前置條件：migration 階段 3-5 已完成（所有 bangumi 具 `series_id` 與 `mikan_subgroup_id`；duplicate 已透過共用 series_id 體現）。

演算法：

1. 查詢 `SELECT series_id, mikan_subgroup_id, array_agg(bangumi_id) FROM bangumi WHERE deleted = 0 GROUP BY 1, 2 HAVING COUNT(*) > 1`
2. 對 `mikan_subgroup_id IS NULL` 的情形改以 `(series_id, rss_id)` 分組
3. 每組 duplicate 依 winner 規則排序（§11 總論）→ 自動合併（§11.2 transaction）
4. 合併結果寫 `bangumi_merge_history`（`merged_by='auto_migration'`, `merge_reason='mikan_id_match'` 或 `'fallback_key_match'`）

Winner 規則（依序）：

1. `added=True` 優先
2. `torrent_count` 多者
3. `updated_at` 新者

### 11.2 合併 Transaction

```python
async def merge_bangumi(winner_id, loser_id, reason, actor):
    async with session.begin():
        winner = await bangumi_repo.get(winner_id)
        loser  = await bangumi_repo.get(loser_id)
        loser_snap = serialize(loser)
        moved, dropped = [], []

        for t in await torrent_repo.get_by_bangumi(loser_id):
            conflict = await torrent_repo.get_by_hash_and_bangumi(t.hash, winner_id)
            if conflict:
                dropped.append(serialize(t))
                await torrent_repo.delete(t.id)
            else:
                t.bangumi_id = winner_id
                moved.append(t.id)

        winner.observed_groups = sorted(set(winner.observed_groups) | set(loser.observed_groups))
        loser.deleted = True

        await merge_history_repo.create(
            winner_id=winner_id, loser_id=loser_id,
            loser_snapshot=loser_snap,
            moved_torrent_ids=moved, dropped_torrents=dropped,
            merge_reason=reason, merged_by=actor,
        )
```

### 11.3 Undo

還原 loser 狀態 + 搬 torrent 回去 + 復活被 drop 的 torrent。UI 按鈕附 caveat 對話框：

> 還原只影響資料庫紀錄。已下載或改名的檔案不會自動搬回 loser 的目錄。

### 11.4 永久黑名單保護

兩個 bangumi 一旦曾出現在 `bangumi_merge_history` 任一行中作為 `(winner_bangumi_id, loser_bangumi_id)` 的任一組合（**方向無關**，A→B 或 B→A 都算），且該行是否被 undone 無關，則：

- `migrate_duplicates.py`（以及未來任何 auto-merge 排程）**永遠跳過這對**
- 使用者 undo 後的意圖受保護
- 若使用者改變主意要合併，只能透過 WebUI 手動觸發 `POST /api/v1/bangumi/merge`（顯式 intent）

### 11.5 級聯合併處理

若 A 合併進 B（history#1），B 合併進 C（history#2）。使用者嘗試 undo history#1：
- 檢查是否存在以 A.loser_id 或 B.loser_id 為 target 的更新 history 且尚未 undo → 拒絕並提示「必須先 undo 較新的合併」

## 12. 可觀測性

### 12.1 Health API

```text
GET /api/v1/health/mikan
→ {
    "status": "ok" | "degraded" | "down",
    "pending_count": <int>,
    "last_success_at": "<iso>",
    "hours_since_last_success": <float>,
    "consecutive_failures": <int>,
    "pending_items": [
      { "info_hash", "torrent_name", "homepage", "attempts", "last_error", "first_seen_at" }
    ]
  }

GET /api/v1/health/concurrency
→ {
    "rss_locks": [{"rss_id", "held", "held_duration_s"}],
    "rate_limiters": {
      "<service>": {"queue", "in_flight", "req_per_min", "error_rate_5m", "degraded"}
    }
  }
```

### 12.2 狀態判定

```text
ok        : last_success_at < 1h AND pending_count < 3
degraded  : 1h <= last_success_at < 24h OR pending_count >= 3
down      : last_success_at >= 24h OR consecutive_failures >= 10
```

閾值皆 config 化。

### 12.3 UI 三層

- **Dashboard banner**（系統級）：degraded 黃、down 紅。down 時附「檢查 Mikan 設定」連結
- **`/pending-resolution`**（項目級）：列表 + 手動重試按鈕。Polling 30s
- **Bangumi/Series 徽章**（脈絡級）：pending_review 時顯示

狀態完全由 DB 驅動，auto-clear（resolve 成功 → pending 刪除 → 下次 poll 回空 → UI 徽章消失）。不提供手動 dismiss。

## 13. Migration 計畫

### 13.1 工具：Alembic

引入 Alembic 管理 schema 版本。現有 `_run_migrations()` 中的累積變更作為 baseline (revision 0001)。

```text
backend/
├── alembic.ini
└── alembic/
    ├── env.py
    └── versions/
        ├── 0001_baseline.py            ← 現況 snapshot
        ├── 0002_add_series.py
        ├── 0003_add_mikan_episode_ref.py
        ├── 0004_add_pending_torrent_enrichment.py
        ├── 0005_add_merge_history.py
        ├── 0006_refactor_bangumi_identity.py  ← drop columns + change unique
        └── 0007_add_torrent_mikan_refs.py
```

`main.py` 啟動時呼叫 `alembic.upgrade('head')` 取代 `_run_migrations()`。

### 13.2 資料遷移階段

| # | 階段 | 可 rollback | 說明 |
|---|---|---|---|
| 1 | 引入 Alembic + 0001 baseline | ✓ | 現況封存 |
| 2 | 建 series / mikan_episode_ref / pending 表 | ✓ | 純新增 |
| 3 | 為每筆現有 bangumi `get_or_create` series（取 rss_link 抽 mikan_bangumi_id，無則 fallback 鍵），bangumi 新增 `series_id` 欄位（此階段為 nullable）並填值 | ✓ | 多 bangumi 可對應同一 series（duplicate 已在此步驟顯現） |
| 4 | 為每筆現有 torrent backfill mikan_bangumi_id / mikan_subgroup_id（透過 rss_link 或爬 homepage） | ✓ | 純新增 |
| 5 | 為每筆 bangumi 新增 `mikan_subgroup_id` 欄位並填值（取 torrent 多數決，或直接取 rss_link 的 subgroupid） | ✓ | 此時尚未施加 UNIQUE |
| 6 | 跑 `migrate_duplicates.py --dry-run` 預覽 | ✓ | 無寫入 |
| 7 | 備份 `bangumi.db` → `bangumi.db.bak-<timestamp>` | ✓ | file copy |
| 8 | 跑 `migrate_duplicates.py --execute`（含 auto-merge + soft delete loser） | 可 undo（per-pair） | 寫 merge_history |
| 9 | Alembic：施加 bangumi 的 partial UNIQUE + 將 `series_id` 改 NOT NULL + drop 舊欄位（official_title/year/season/... 見 §6.2） | ⚠ destructive，需備份 | 一旦完成，舊欄位不可復 |
| 10 | 切流：新 identity resolver / rename pipeline 上線 | ✓ code-level rollback | |

### 13.3 Rollback 策略

- 階段 1-8：直接 `alembic downgrade`（merge 紀錄可透過 `/merge-history` UI undo 或清空 merge_history 表）
- 階段 9：從 `bangumi.db.bak-<timestamp>` 還原
- 階段 10：git revert 程式碼 + 可選擇性 alembic downgrade 至階段 8

## 14. API 變更（不保留舊 endpoint）

### 14.1 重寫

| 舊 | 新 |
|---|---|
| `GET /api/v1/bangumi/` | `GET /api/v1/series/`（回傳 series + active bangumi 摘要） |
| `GET /api/v1/bangumi/{id}` | `GET /api/v1/series/{id}` 或 `GET /api/v1/bangumi/{id}`（保留用於深層操作） |
| `POST /api/v1/rss/subscribe` | 行為不變但改動 request/response schema 對齊新 model |
| `POST /api/v1/rss/subscribe/batch` | 同上，並補 `excluded_hashes` 支援（對齊 subscribe_season） |
| `POST /api/v1/bangumi/{id}/activate` | 保留，新增「切換 active 且 deactivate 同 series 其他 bangumi」行為 |

### 14.2 新增

```text
GET    /api/v1/series/                            list
GET    /api/v1/series/{id}                        detail + bangumi
POST   /api/v1/series/{id}/merge-candidates       查看疑似匯流
POST   /api/v1/series/{id}/merge                  執行手動合併
POST   /api/v1/bangumi/merge                      手動合併兩 bangumi
GET    /api/v1/merge-history                      清單
POST   /api/v1/merge-history/{id}/undo            undo
GET    /api/v1/pending-resolution                 alias → /health/mikan pending_items
POST   /api/v1/pending-resolution/{hash}/retry    立即重試單筆
GET    /api/v1/health/mikan                       § 12.1
GET    /api/v1/health/concurrency                 § 12.1
```

## 15. WebUI 變更

### 15.1 新頁面

- `/series`：主列表（取代現行 `/bangumi`）
- `/series/:id`：單一 series，內嵌 bangumi 列表與 active 切換
- `/pending-resolution`：Mikan 待解析項目
- `/merge-history`：合併紀錄 + undo

### 15.2 Dashboard 元件

- Mikan Health Banner（§ 12.3）
- Rate Limiter 降級指示（可選，phase 後段）
- Rename Conflict 提示

### 15.3 元件遷移

舊 `BangumiCard`、`BangumiList`、`BangumiDetail` 全數重寫對應新 schema；舊 i18n key 視情況保留 / 重新命名。

## 16. 測試策略

### 16.1 Unit

- `normalize_title()`：§ 7 測試矩陣
- `parse_mikan_page()`：三層 fallback，每層各一 fixture
- `RateLimiter`：並發超過上限時正確排隊、429 後降級、連續成功恢復
- `RssLockRegistry`：skip-if-held 正確性

### 16.2 Integration / E2E（擴充現有 `test_e2e/`）

- Aggregate RSS 送入含同一 Mikan `(bangumiId, subgroupid)` 但 `group_name` 不同兩筆 item → 應只產生一筆 bangumi
- Mikan 503 模擬 → torrent 進入 pending queue → Mikan 恢復後自動清空
- 手動觸發 `/rss/refresh/all` 與 cron 同時發生 → 第二個 skip（log 可驗）
- `migrate_duplicates.py --execute` 對含 91/93 的 snapshot DB 正確合併，`merge_history` row 存在，undo 可復原
- 切換 active bangumi → 原 active 自動 deactivate → rename pipeline 只處理新 active
- Rename conflict：active 切換後新檔 target_file 已存在且 hash 不同 → 跳過 + Dashboard 顯示徽章

### 16.3 Fixture 擴充

- `episode_page_multi_group.html`（`[AAA&BBB]` 合作發布）
- `episode_page_no_subgroup.html`（沒 subscribeBangumiPage button）
- `mikan_503.txt`
- `non_mikan_nyaa.xml`
- 包含繁簡中 / CJK / 【】 的 torrent title sample

## 17. 實作階段

| # | 範圍 | 預估 | 出口條件 |
|---|---|---|---|
| 0 | Alembic 導入、baseline、CI 跑 `upgrade head` | 1 天 | migration 命令可重放 |
| 1 | 新表 schema + ORM model + repo + 單元測試 | 2-3 天 | 新表 CRUD 綠燈 |
| 2 | `normalize_title` + `parse_mikan_page` + `MikanResolver` + cache + rate limiter | 3-4 天 | fixture tests 綠燈 |
| 3 | RSS pipeline 串接新 identity resolver + pending queue + per-RSS lock | 2 天 | E2E RSS 場景綠燈 |
| 4 | `bangumi_merge_history` + undo + `migrate_duplicates.py` + backfill script | 2-3 天 | dry-run 報告正確 |
| 5 | Rename pipeline 改走 series.root_path + active 規則 + conflict detection | 1-2 天 | rename E2E 綠燈 |
| 6 | API 重寫 + WebUI 新頁 + Dashboard 元件 | 3-5 天 | 主要流程可操作 |
| 7 | 測試補齊 + 文件更新 + 壓測 rate limiter | 2-3 天 | 64s e2e 保持綠、新增 e2e 綠 |

**合計 16-23 人日**。建議在 staging DB copy 上先完整跑一輪 phase 0-7 後再對 production 執行。

## 18. 風險與未決項

### 18.1 已知風險

- **Mikan 頁面改版**：若 data-attribute 改名，三層 parser 仍可靠 fallback；但若三層同時失效需手動更新 regex。**緩解**：健康檢查 `consecutive_failures >= 10` 觸發 down 狀態警報
- **Alembic 與現有 `_run_migrations()` 重疊**：baseline 必須精準 reflect 現況，否則 downgrade 會炸。**緩解**：baseline 產生後立即在 staging copy 跑 upgrade/downgrade 驗證 idempotent
- **階段 8 drop column 不可逆**：依賴備份。**緩解**：自動備份腳本內建於 migration command
- **active bangumi 切換後的檔案衝突**：使用者需介入決策。**緩解**：Dashboard 徽章明確提示，不靜默
- **OpenCC 依賴**：需新增 Python 套件。**緩解**：輕量（~1MB），已是中文 NLP 標準

### 18.2 未決項

- Mikan RSS 帶入的 torrent 有極少部分可能無 subgroupid（例如 Mikan 自聚合的 feed）：其 bangumi 的 fallback 身分鍵如何設計尚需 staging 驗證後決定（目前預設走 `(series_id, rss_id)` partial unique）
- 跨來源匯流（Mikan + nyaa）的 UI 展示位置尚未決定：放 series 詳情頁 tab？還是獨立 `/merge-candidates` 頁？
- Rate limiter 的降級閾值（429 → 並發砍半 / 10 次成功恢復）數字未經實測，phase 7 壓測時調整

### 18.3 Out of Scope（本次不處理）

- 多 worker / 水平擴展（§ 4）
- 非 SQLite 資料庫（PostgreSQL / MySQL migration 未來再議）
- Mikan 以外的 metadata provider 整合（TMDB / Bangumi.tv 未來 phase）
- 自動 quality selection（同 series 多 bangumi 時系統幫使用者選擇 active）

---

## Appendix A：現有 production DB 處理清單

基於 2026-04-17 snapshot：

| Bangumi IDs | 處理 |
|---|---|
| 91, 93 | 階段 3 後兩者共享同一 series（mikan_bangumi_id=3906）；階段 8 自動合併：winner=93（updated_at 較新），移 1 torrent，寫 merge_history |
| 55, 57, 58, 59 (Re:Zero 系列) | 各對應不同 mikan_bangumi_id（701/2348/3464/2259），階段 3 各建獨立 series，不觸發合併 |
| 45, 49, 50 (我推的孩子 S1/S2/S3) | 各 season 獨立 rss、不同 mikan_bangumi_id，各自獨立 series，不合併 |
| 其餘 54 筆 | 每筆 1:1 對應一筆 series（mikan_bangumi_id 從 rss_link 抽），無重複 |
