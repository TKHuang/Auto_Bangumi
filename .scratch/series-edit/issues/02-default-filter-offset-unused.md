# Series default_filter and default_offset are stored but never read

Status: resolved

Series Detail lets the user edit Default Filter and Episode Offset, and `PATCH /api/v1/series/{id}` stores them (`series.default_filter`, `series.default_offset`). No non-test code reads either column (`rg default_filter backend/src --glob '!tests'` finds only the model and the API schema), so editing them changes nothing the user can observe.

Decide whether to wire them into filtering and episode numbering for the series' bangumi, or remove them from the UI.

## Answer

Wired up on codex/series-edit-fixes: BangumiRepository.create gives a new bangumi the series default_filter and default_offset when its own values are still the global defaults. The 2026-11-14 dev run added a second subgroup to a series with defaults verifyinherit / -3 and the new bangumi row carried both; the earlier bangumi kept its own.
