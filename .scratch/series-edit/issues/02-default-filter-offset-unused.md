# Series default_filter and default_offset are stored but never read

Status: needs-triage

Series Detail lets the user edit Default Filter and Episode Offset, and `PATCH /api/v1/series/{id}` stores them (`series.default_filter`, `series.default_offset`). No non-test code reads either column (`rg default_filter backend/src --glob '!tests'` finds only the model and the API schema), so editing them changes nothing the user can observe.

Decide whether to wire them into filtering and episode numbering for the series' bangumi, or remove them from the UI.
