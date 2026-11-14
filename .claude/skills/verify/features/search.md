# Search bangumi

A user types a keyword in the top-bar search, picks a provider (`mikan`, `nyaa`, `dmhy`), and gets one result per bangumi and subgroup. Mikan reads `/Home/Search`, then each bangumi page, and streams hits over SSE as each page parses. Clicking a result opens the add-RSS flow with its `RSS/Bangumi?bangumiId=&subgroupid=` link.

## Sub-features

- `search-providers` lists providers (`GET /api/v1/search/provider`).
- `search-stream` streams results (`GET /api/v1/search/bangumi?site=<provider>&keywords=<words>`, at most 10 words).

## How to get to it (user POV)

- Top bar → magnifier button → type → Enter.

## Driving it with agent-browser

Preconditions:

- Baseline from the README. Search does not call PikPak.

- **Open.** The magnifier is the first unnamed `button [expanded=false]` in `agent-browser snapshot -i` (the second one opens the program menu). Click its ref, then check `input[placeholder="Type to search"]` exists.
- **Search.** `agent-browser fill 'input[placeholder="Type to search"]' '<keyword>'`, `agent-browser press Enter`, `agent-browser wait 20000`. The provider button shows `mikan`. Results list the title, season, and subgroup; `agent-browser eval "document.querySelectorAll('.search-list > *').length"` counts them (20 for `光之美少女` on 2026-11-14).
- **Proof.** The log shows `GET /api/v1/search/bangumi?site=mikan&keywords=...` 200 and the DEBUG line `https://mikanani.me:443 "GET /Home/Search?searchstr=...` 200. Screenshot the list.

## Gotchas

- Clicking a result opens the add-RSS dialog. Subscribing from there downloads to PikPak; follow `rss-subscribe.md` and keep one episode.
- Press Escape to close the search panel.
