# Delete a bangumi with its files

A user deletes a bangumi and chooses to delete its files. AB removes the bangumi and its torrent rows, and deletes exactly the PikPak tasks and files that bangumi owns.

## Sub-features

- `delete-keep-files` removes the rule but keeps PikPak files (`file=false`).
- `delete-with-files` also deletes the PikPak tasks and files (`file=true`).
- `disable` disables the rule instead (Edit Rule dialog → `Disable`).

## How to get to it (user POV)

- HomePage (`/#/bangumi`) → bangumi card → `Edit Rule` → `Delete` → a dialog asks whether to delete files.
- API, as the WebUI calls it: `DELETE /api/v1/bangumi/delete/{id}?file=true`.

## Driving it with agent-browser

Preconditions:

- A bangumi created by this run with one PikPak task (from `rss-subscribe.md`). Note its id (`$S/db.sh "select id from bangumi"`) and the task id from the `Download added` log line.

- **Delete through API (proved).** `$S/api.sh "$RUN" DELETE "/api/v1/bangumi/delete/<id>?file=true"`. Response 200 with `Delete rule and torrents for <title>`. The log shows `Batch deleting 1 offline tasks (delete_files=True)` and `task_ids': '<task id>'`, the same id as the subscribe created.
- **Delete through WebUI (not yet driven).** Open HomePage, click the card, `agent-browser find role button click --name "Edit Rule"`, then `Delete`, then the delete-files choice. Record the selectors here after the first run.
- **Proof.** `$S/db.sh "select (select count(*) from bangumi) b, (select count(*) from torrent) t"` prints `0 | 0`.

## Gotchas

- The task id in `Batch deleting` must match the id this run created. Any other id means AB is about to delete a task it does not own (possibly production). Stop and report.
- Delete the RSS separately: `DELETE /api/v1/rss/delete/<rss_id>`.
