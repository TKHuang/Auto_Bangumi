# Edit a series

A user opens Series (`/#/series`), opens one series, and edits its canonical title, default filter, or default offset. A title change also changes the series root path, so the UI asks for confirmation first.

## Sub-features

- `series-list` lists series (`GET /api/v1/series/?limit=100&offset=0`).
- `series-detail` opens one (`/#/series?id=<id>`, `GET /api/v1/series/{id}`).
- `series-save` saves only changed fields (`PATCH /api/v1/series/{id}`).
- `series-root-confirm` asks before a title change (`Confirm title change`).

## How to get to it (user POV)

- Sidebar `Series` → click a row → edit fields → Save.

## Driving it with agent-browser

Preconditions:

- At least one series. Subscribing (from `rss-subscribe.md`) creates one. With no series the page shows `No series yet.` Note its id: `$S/db.sh "select s.id from series s join bangumi b on b.series_id=s.id"`.

- **Open.** `agent-browser find role link click --name Series`, then `agent-browser find text "<title>" click` (rows are `row` elements named after their cells). The URL becomes `/#/series?id=<id>` and the heading `Series Detail` shows.
- **Fields.** The inputs have no accessible names. In `agent-browser snapshot -i` they appear in this order: textbox (canonical title), disabled textbox (root path), textbox (default filter), spinbutton (default offset). `Save` and `Cancel` stay disabled until a field changes.
- **Edit and save.** `agent-browser fill @<filter ref> 'verifytest'`, then `agent-browser find role button click --name Save`. The log shows `PATCH /api/v1/series/<id>` 200. Reopen `/#/series?id=<id>`; the field shows the new value.
- **Title confirm.** Change the title textbox and press `Save`. The dialog `Confirm title change` opens with `Cancel` and `Confirm`. Press its `Cancel`, then the panel's `Cancel`; the title reverts.
- **Proof.** `$S/db.sh "select id, canonical_title, root_path, default_filter, default_offset from series where id=<id>"` before and after. The endpoint logs nothing besides the access line, so the DB row and the PATCH 200 are the proof. Restore the filter afterwards; clearing it stores `''`, not `NULL`.

## Gotchas

- One `Save` sends two identical `PATCH` requests (`series.vue` and `store/series.ts` both send it). Expect two access lines. This is a product bug, not a harness problem.
- No code reads `default_filter` or `default_offset` yet, so saving them proves storage only, not filtering or episode numbering.
- Not yet driven: confirming a title change. Source reading says only `retrigger-rename` or a rule save moves files, not the rename job, although the dialog says files move "on the next rename cycle". Do not confirm it on a series whose files you want to keep.
