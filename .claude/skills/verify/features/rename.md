# Rename downloaded episodes

When a PikPak download finishes, the `rename` job (every `program.rename_time` = 60 s in dev) renames the file in `Bangumi-dev/<title>/Season N/` to the `S01E39` format.

## Sub-features

- `rename-auto` renames finished downloads on the job tick.
- `rename-retrigger` re-runs rename for one bangumi (`POST /api/v1/bangumi/{id}/retrigger-rename`).
- `rename-conflicts` lists name conflicts (`GET /api/v1/bangumi/rename-conflicts`).

## How to get to it (user POV)

- Automatic: subscribe and wait.
- HomePage → bangumi card → torrent status (`GET /api/v1/bangumi/torrent/{id}`).

## Driving it with agent-browser

Preconditions:

- A bangumi with one finished PikPak download in `Bangumi-dev` (from `rss-subscribe.md`). PikPak offline download of a popular torrent usually finishes in seconds to minutes; it is not guaranteed.

- **Wait for finish.** Poll `$S/api.sh "$RUN" GET /api/v1/bangumi/torrent/<id>` until the torrent shows a finished state. Do not poll faster than every 30 s; each call lists PikPak tasks.
- **Rename.** Wait for one rename tick (60 s), or call `retrigger-rename`. The log shows the rename lines from `module.services.renamer`.
- **Proof.** The torrent status shows the new name with `S01E<nn>`. Not yet proved; record the exact log lines and fields here after the first run.

## Gotchas

- Not yet driven. Treat every step above as a draft until a run proves it.
