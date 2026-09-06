* _2026-09-06 23:08:36 (GPT-6)_

# 兩項架構深化設計

狀態：等待此設計 commit 的 Design Go。尚未修改 source 或 tests。
程式基準：937d9f2b，refactor/backendv2。

## 原始 Ask 與已確認決定

- 使用者：`$improve-codebase-architecture` → `全部` → `ok`。
- 同時深入「訂閱選擇規則」及「PikPak 任務解讀」。
- 預覽後新增、符合目前規則的項目仍可下載。手動排除的項目不可下載。
- PikPak 只重構內部。清單、完成數、重新命名及外部 interface 的行為不變。
- 本設計不含 source 實作授權；依 Agentflow 另需 `Design Go: <design-commit>`。

## 最小設計與證據

### 1. 深化既有 RSSEngine 的訂閱選擇規則

**修正原候選：** 不合併整個訂閱生命週期。啟用、重建單筆、重建批次的交易範圍不同；把它們塞進一個 orchestrator 會改變行為。

- `rss_engine.py:242` 已有 `_torrent_excluded_by_filter`；沿用同一判斷，收回本檔其他重複 regex。
- `rss.py:810` 的待審核預覽改用相同選擇規則；來源同步、可見項目查詢及回應欄位不變。
- 在既有 RSSEngine module 內讓預覽與 `download_bangumi` 共用 filter 判斷，下載仍由既有 `download_bangumi` interface 承擔 included override、去重與 EXCLUDED。
- 若需讓預覽呼叫既有 filter 判斷，將現有 helper 調整為 module 內可用名稱；不另加只做轉呼叫的 module。
- 繼續在確認下載時讀取最新 RSS，不把 included_hashes 改為封閉的允許清單。
- 不搬動 `bangumi.py:736-778` 的啟用鎖、排除寫入、commit、下載順序。
- 不搬動 `collector.py:393-472,588-720` 的刪除、重建、單筆/批次提交與補償流程。
- `TorrentRepository.exclude_hashes:177-216` 已集中 sentinel persistence，保留此 seam。

選擇優先序：

| 候選 | 結果 |
|---|---|
| 已有 EXCLUDED，包含同時出現在 included 的情況 | 不下載 |
| 已下載 | 不再下載 |
| included 且未被以上條件擋住 | 可略過 filter |
| 其餘候選，包含預覽後新增項目 | 用目前 filter 判斷 |

收益：增加 locality，filter 語意只改一處。維持既有 deep 下載 module 的 leverage；不把交易責任搬到不相容的 seam。

**拒絕較小但無效的方案：** 只包裝 `exclude_hashes` 沒有集中任何新規則。
**拒絕較大的方案：** 新增 SubscriptionSelection 類別、通用 transaction orchestrator 或多一個 pass-through module，沒有目前的使用需求。

### 2. 深化既有 PikPak adapter 的任務解讀

- `pikpak.py:615-657` 與 `1921-1956` 重複解析 task hash、查詢 hash→雲端路徑。將此共同責任收進本檔的內部 implementation。
- 重用既有 `_resolve_task_files`、`_normalize_task_state`；集中共同的狀態優先序，避免兩份常數漂移。
- 若合併 task 解讀需要額外模式旗標或改變呼叫次數，先只集中 hash/路徑 lookup 與狀態優先序，不新增 snapshot class。
- 呼叫者傳入 `cloud_paths`（包含空 dict）時，維持不查資料庫。
- 沒傳 map 時，維持現有批次查詢與 fallback 行為。
- 保留 `torrents_info` 的 task ID fallback、無路徑略過、filter 後才去重及清單順序。
- 保留 `get_hash_status_map` 只接納有效 hash、無路徑仍可回報 phase，以及例外回傳空 dict。
- 保留快取失效時機、檔案解析次數，以及同 hash 取較佳狀態、同順位保留原項目的規則。
- 不修改 DownloaderProtocol 或 qBittorrent adapter；RenameOutcome 仍為 OK / CONFLICT / ERROR。

收益：locality 集中在現有 PikPak module。兩種輸出共享必要知識，增加 leverage；既有 interface 與兩個真實 adapter 不變。

**拒絕較小但無效的方案：** 再包一層呼叫 `_normalize_task_state`，沒有移除重複知識。
**拒絕較大的方案：** 令 status map 直接呼叫 torrents_info，會遺失無雲端路徑的狀態；不可採用。

## 新概念與文件

無新資料欄位、class、設定、外部 interface、持久化型別或依賴。只重用現有 module 與內部 helper。
未找到 CONTEXT.md 或 docs/adr/；本輪沒有新增領域名詞，因此不建立空詞彙表。
遵守 `docs/superpowers/specs/2026-04-17-bangumi-identity-refactor-design.md`（Draft）所列 downloader protocol 非目標，以及 active、path_override 與不覆寫衝突檔案的既有行為。

## 修改範圍

程式只允許：

- `backend/src/module/services/rss_engine.py`
- `backend/src/module/api/v1/rss.py`
- `backend/src/module/services/downloader/pikpak.py`

測試沿用以下檔案，只增補必要的行為證明：

- `backend/src/tests/test_services/test_rss_engine.py`
- `backend/src/tests/test_api_contract/test_rss.py`
- `backend/src/tests/test_services/test_pikpak.py`
- 若需驗證真實啟用/訂閱先後順序，允許 `test_api_contract/test_bangumi.py` 與 `test_services/test_collector.py`；不得只新增 mock 呼叫次數測試。

不修改 WebUI、schema、migrations、下載器設定、部署或真實下載資料。
不將先前 init 的 `.gitignore`、`ag.json` 變動混入這次設計/實作 commit。

## 正常旅程與驗收

1. 真實測試 SQLite 建立 Bangumi 與候選；假 RSS 提供預覽項目。
2. 手選保留一個被 filter 擋住的項目，排除另一個；確認前來源新增一個符合規則的項目。
3. 透過既有 interface 下載：保留項與新項目送出，排除項未送出。
4. 再次下載：已下載與 EXCLUDED 項目不重複送出。來源標題別名、空選擇和現有 pending preview 測試保持通過。
5. PikPak 使用同一組假任務驗證兩種輸出：completed/error 重複 hash、失效 task 但檔案存在、空合集、缺雲端路徑與 supplied empty map。測試穿過既有 interface，不直接鎖死新 helper 的形狀。
6. 不用真實 PikPak/qBittorrent 做刪檔或下載測試。

這次要求保留行為：先在舊程式執行行為測試作基準，再重構；不為了 red-first 先破壞既有行為。如果測試暴露超出本 Ask 的缺陷，先記錄，不順手修正。

聚焦驗證（在 backend 執行）：

```sh
uv run python -m pytest src/tests/test_services/test_rss_engine.py src/tests/test_services/test_pikpak.py src/tests/test_api_contract/test_rss.py src/tests/test_api_contract/test_bangumi.py src/tests/test_services/test_collector.py -q
```

完整相關驗證（在 backend 執行）：

```sh
uv run python -m pytest src/tests/test_repositories/ src/tests/test_domain/ src/tests/test_services/ src/tests/test_api_contract/ src/tests/test_scheduler/ src/tests/test_e2e/ -q
```

實作完成後，主代理獨立檢查 diff 與測試證據，再作一次針對最終實作 commit 的只讀審查。審查須檢查 Outcome、Minimality、Conformance。
本輪是設計，以上應用測試尚未執行。沒有聲稱實作或驗收已完成。

## 開始條件

下一步：使用者提供此設計 commit 的 Design Go；接著逐項實作、執行驗證、檢查最終 diff。
若要換 branch/worktree，先依 Agentflow streams 設定處理；目前只在既有分支記錄設計。

Self-check: 兩項均保留行為；未合併不相容交易；無新外部 interface；所有測試命令僅為待執行驗證。
