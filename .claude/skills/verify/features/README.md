# AutoBangumi verification map

This directory is the maintained source for verifying user-facing behavior of AutoBangumi. Read this index, then use the matching feature file as the recipe. Launch, doctor, evidence, and cleanup rules are in [`../SKILL.md`](../SKILL.md).

| Feature | File | Last proved |
|---|---|---|
| Add RSS and subscribe (download to PikPak) | [rss-subscribe.md](rss-subscribe.md) | 2026-11-08, WebUI path, end to end |
| Delete a bangumi with its files | [bangumi-delete.md](bangumi-delete.md) | 2026-11-08, API path only |
| Rename downloaded episodes | [rename.md](rename.md) | not yet |
| Edit a series | [series-edit.md](series-edit.md) | not yet |

## Baseline preconditions

- The stack was launched by this run through `make dev`, with `guard.sh` started first. Do not drive an instance you did not start.
- `doctor.sh` prints `DOCTOR OK`. `downloader.path` is `Bangumi-dev`.
- The dev DB has no bangumi, torrent, or rssitem rows (check with `db.sh`). Clean up left-over rows from an earlier run through the API before you start.
- Logged in to the WebUI as `admin` in the `ab-verify` agent-browser session.

## Driving conventions

- Use accessible names (`find role button --name`, `find text`) before CSS. The CSS handles listed in feature files are the ones that have no name.
- Every subscribe downloads real files into the user's paid PikPak storage. Keep one episode.
- Delete what you created, with `file=true`, before `cleanup.sh`.

## Proof and skip reporting

- Proof = screenshot before and after the action + the API response or DB row + the backend log line that shows the PikPak side effect.
- Record the feature file and the entry point used.
- If a precondition is missing (for example, no finished download for rename), report the journey as not verified and say why. Do not report another path as verified for it.
