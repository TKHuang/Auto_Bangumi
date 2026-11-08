# Edit a series

A user opens Series (`/#/series`), opens one series, and edits its canonical title, default filter, or default offset. Changing the title moves the series root path, so the UI asks for confirmation first.

## Sub-features

- `series-list` lists series (`GET /api/v1/series/`).
- `series-detail` opens one (`/#/series?id=<id>`, `GET /api/v1/series/{id}`).
- `series-save` saves only changed fields (`PATCH /api/v1/series/{id}`).
- `series-root-confirm` asks before a title change that moves the root path.

## How to get to it (user POV)

- Sidebar `Series` → click a row → edit fields → Save.

## Driving it with agent-browser

Preconditions:

- At least one series. Subscribing (from `rss-subscribe.md`) creates one. With no series the page shows `No series yet.`

- **Open.** `agent-browser find role link click --name Series`, then click the row. The panel title is `Series Detail`.
- **Edit and save.** Change the default filter and save. `PATCH /api/v1/series/{id}` returns the new value; reopen the detail to confirm.
- **Proof.** Not yet proved; record selectors here after the first run.

## Gotchas

- Not yet driven. Changing `canonical_title` relocates the download folder in `Bangumi-dev`; do not test it on a series that has files you want to keep.
