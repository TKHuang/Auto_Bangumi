# Rename downloaded episodes

When a PikPak download finishes, the `rename` job (every `program.rename_time` = 60 s in dev) renames the file in place to the `<title> S01E40.mkv` format. A single-file task keeps its folder, `Bangumi-dev/<title>/Season N/` for a new series.

## Sub-features

- `rename-auto` renames finished downloads on the job tick. It picks torrents with no `renamed_at` whose PikPak task is `completed` or `missing`.
- `rename-retrigger` clears the rename state and re-runs rename for one bangumi (`POST /api/v1/bangumi/{id}/retrigger-rename`, 409 while the rename lock is held). Saving a rule with a changed season or title runs the same path.
- `rename-conflicts` lists name conflicts (`GET /api/v1/bangumi/rename-conflicts`) and retries one (`POST /api/v1/bangumi/rename-conflicts/{torrent_id}/retry`). Conflict rows are never retried by the job. API only; the WebUI has no conflict screen.

## How to get to it (user POV)

- Automatic: subscribe and wait.
- HomePage → bangumi card → `Re-rename`.
- HomePage → bangumi card → `Torrents` shows each torrent's PikPak status.

## Driving it with agent-browser

Preconditions:

- A bangumi with one PikPak download in `Bangumi-dev` (from `rss-subscribe.md`). The 2026-11-14 run finished in under a minute; it is not guaranteed.

- **Wait for finish.** Poll `$S/api.sh "$RUN" GET /api/v1/bangumi/torrent/<bangumi id>` until `"status":"completed"`. Do not poll faster than every 30 s; each call lists PikPak tasks. `name` stays the RSS title after rename; it never shows the new file name.
- **Rename on the tick.** Within 60 s the log shows `Renaming file in PikPak: <old path> -> <folder>/<title> S01E<nn>.<ext>`, `Successfully renamed file to: <title> S01E<nn>.<ext>`, `[Renamer] Successfully renamed torrent <torrent id> with 1 files`, and `Rename job completed successfully`.
- **Re-rename in the WebUI.** `agent-browser find text "<title>" click`, then `agent-browser find role button click --name Re-rename`. The popup closes. The log shows `[Renamer] Start rename_bangumi for bangumi_id=<id>, retrigger=True`, `Cleared rename status`, and, for a file that already has its name, `File already has target name`, then `POST /api/v1/bangumi/<id>/retrigger-rename` 200.
- **Torrents list.** Reopen the card, `agent-browser find role button click --name Torrents`. The table shows the RSS title and `completed` (`archived` once the PikPak task is gone).
- **Proof.** Save the log lines above (`grep -E 'Renamer|Renaming file in PikPak|Successfully renamed|Rename job|already has target'`). `$S/db.sh "select id, rename_status, renamed_at, renamed_file_count, rename_conflict_target from torrent where state='pending'"` prints `done`, a timestamp, `1`, `None`.

## Gotchas

- The log format has no logger name, so grep message text, not `module.services.renamer`.
- `rename_status` stores lowercase values (`done`, `conflict`).
- Pressing Escape on the `Torrents` list closes the `Edit Rule` popup too. Click the card again before the next action.
