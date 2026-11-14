# Delete a bangumi with its files

A user deletes a bangumi and chooses to delete its files. AB removes the bangumi and its torrent rows, and deletes exactly the PikPak tasks and files that bangumi owns.

## Sub-features

- `delete-keep-files` removes the rule but keeps PikPak files (`file=false`).
- `delete-with-files` also deletes the PikPak tasks and files (`file=true`).
- `disable` sets `bangumi.deleted` and keeps the torrent rows (Edit Rule dialog → arrow next to `Delete` → `Disable`). With `file=true` it still deletes the PikPak files.

## How to get to it (user POV)

- HomePage (`/#/bangumi`) → bangumi card. The card opens the `Edit Rule` popup directly; `Edit Rule` is its title, not a button. → `Delete` → `Delete Local File?` → `Yes` (`file=true`) or `No` (`file=false`).
- API, as the WebUI calls it: `DELETE /api/v1/bangumi/delete/{id}?file=true`.

## Driving it with agent-browser

Preconditions:

- A bangumi created by this run with one PikPak task (from `rss-subscribe.md`). Note its id (`$S/db.sh "select id from bangumi"`) and the task id from the `Download added` log line.

- **Delete through WebUI (proved).** `agent-browser find text "<title>" click` (the card has no accessible name), `agent-browser find role button click --name Delete`, check `Delete Local File?` is shown, then `agent-browser find role button click --name Yes`. The card disappears and the log shows `DELETE /api/v1/bangumi/delete/<id>?file=true` 200.
- **Delete through API.** `$S/api.sh "$RUN" DELETE "/api/v1/bangumi/delete/<id>?file=true"`. Response 200 with `Delete rule for <title>. Delete rule and torrents for <title>`. Without the second sentence, AB found no torrents it owns and deleted nothing in PikPak.
- **Proof.** The log shows `Batch deleting 1 offline tasks (delete_files=True)` and the DEBUG line `Delete tasks request: ... params={'task_ids': '<task id>', 'delete_files': 'true'}` with the id the subscribe created, and no `Batch task deletion failed`. `$S/db.sh "select (select count(*) from bangumi) b, (select count(*) from torrent) t"` prints `0 | 0`. The series the run created is gone too when no other bangumi uses it.

## Gotchas

- The task id in `Delete tasks request` must match the id this run created. Any other id means AB is about to delete a task it does not own (possibly production). Stop and report.
- The route returns 200 even when PikPak deletion fails. Only the log shows `Batch task deletion failed`.
- `Disable` is a menu `div` behind the unnamed arrow button, so `find role button` cannot reach it. Not yet driven.
- Delete the RSS separately: `DELETE /api/v1/rss/delete/<rss_id>`.
