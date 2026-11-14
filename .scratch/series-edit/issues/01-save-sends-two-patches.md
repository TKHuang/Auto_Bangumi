# Series Save sends two PATCH requests

Status: ready-for-agent

One click on `Save` in Series Detail sends `PATCH /api/v1/series/{id}` twice with the same body.

Evidence: the 2026-11-14 verify pass (`dev-config/verify-evidence/20261114-221834-maintain-pass/series-patch.log`) shows two `PATCH /api/v1/series/33` 200 lines for one click.

Cause: `commitSave` in `webui/src/pages/index/series.vue` patches through the API client and then calls `seriesStore.updateSeries`, which in `webui/src/store/series.ts` sends the same patch again without `await`. A failure of the second request never reaches `saveError`.

Expected: one PATCH per Save, and its error shown in the panel.
