# Add RSS and subscribe

A user pastes a Mikan RSS link, AB parses the bangumi, shows its torrents split into Keep and Exclude, and on Subscribe sends the kept torrents to PikPak under `Bangumi-dev/<title>/Season N`. Excluded torrents become EXCLUDED sentinel rows so the cron job never downloads them.

## Sub-features

- `rss-add` adds the RSS row (`POST /api/v1/rss/add?skip_bangumi=true`).
- `rss-analyse` parses the bangumi and lists torrents with the rule's own filter applied, which starts as a copy of the global filter (`POST /api/v1/rss/recreate/{id}`, `POST /api/v1/rss/analysis/torrents?_filter=...`).
- `rss-select` moves torrents between Keep and Exclude.
- `rss-subscribe` creates the bangumi, inserts sentinel rows, and adds kept torrents to PikPak (`POST /api/v1/rss/subscribe`).

## How to get to it (user POV)

- Top bar → Add RSS icon (`+`) → paste link → `Next` → torrent dialog → `Subscribe`.
- RSS Manager (`/#/rss`) lists the added RSS. (Not yet driven.)

## Driving it with agent-browser

Preconditions:

- Baseline from the README. A single-subgroup Mikan feed: `https://mikanani.me/RSS/Bangumi?bangumiId=<id>&subgroupid=<sid>`. Find ids on `https://mikanani.me/Home/Bangumi/<id>`. Choose a subgroup whose titles do not match the global filter (`720`, `\d+-\d`, `GB`, `合集`, `简`). Proved with `bangumiId=3883&subgroupid=370` (LoliHouse, 39 episodes).

- **Open dialog.** `agent-browser click '.i-icon-add-one'` then `agent-browser wait 'input[placeholder="Please enter the RSS link"]'`. The form shows `RSS Link`, `Name`, an aggregate switch, a parser button `mikan`, and `Next`.
- **Add and analyse.** `agent-browser fill 'input[placeholder="Please enter the RSS link"]' '<feed>'` then `agent-browser find role button click --name Next`, then `agent-browser wait 15000`. The dialog `Review Bangumi Rules` opens. It shows the parsed title in `Official Title`, season `1`, a `Subscribe` button, and a `Keep (N)` list. The log shows `POST /api/v1/rss/add?skip_bangumi=true` and `POST /api/v1/rss/recreate/1` with 200. PikPak is not called yet.
- **Keep one episode.** For each episode except the newest: `agent-browser find text "<show> - 01 [" click` (loop the number). Check `agent-browser snapshot | grep -E "Keep|Exclude"` shows `Keep (1)` and `Exclude (N-1)`. Screenshot.
- **Subscribe.** `agent-browser find role button click --name Subscribe`, `agent-browser wait 20000`. The dialog closes. The log shows `[Collector] Inserted N-1 excluded torrents for <title>`, `Adding download to PikPak: ...`, the DEBUG lines `Download added, result: {... 'task': {'id': '<task id>' ...` and `[Engine] download_bangumi: inserted 1/1 torrents`, and `POST /api/v1/rss/subscribe?file=false` 200. Note the task id for the delete check.
- **Proof (side effects).** `$S/db.sh "select state, count(*), min(pikpak_cloud_path) from torrent group by state"` prints a header row, then `excluded | N-1 | None` and `pending | 1 | Bangumi-dev/<title>/Season 1`. Save it and the auth lines to `$RUN`.
- **Cleanup.** Follow `bangumi-delete.md`, then delete the RSS.

## Gotchas

- `make dev` alone does not trigger the login; the rename job right after startup does. With an expired refresh token, it does one full login at that moment.
- Do not count items in a Mikan feed with `grep -c '<item>'`: the XML is one line, so it always prints 1.
- `Next` is not "analyse only". With `skip_bangumi=false` (old UI, direct API use), `/rss/add` creates the bangumi and downloads at once.
- `bangumi_manage.eps_complete_from_source` is on in dev config. The `rss_refresh` job (every 9999 s, and once at startup) re-downloads from the bangumi's own feed. Excluded sentinels stop it from taking excluded episodes.
- `Found 498 hash-status entries in PikPak` is the whole account, production included. It is a read. Do not act on those tasks.
- Closing `Review Bangumi Rules` without `Subscribe` deletes the RSS row that `Next` created (`ab-rss-recreate.vue`, `ab-topbar.vue`; read from source, not driven), so there may be no RSS left to clean up.
- `<title>` in the path is the official title with illegal path characters replaced. A bangumi that joins an existing series downloads to that series' `root_path`.
