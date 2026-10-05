* _2026-10-05 14:33:34 +0800 (GPT-6/high)_
Reviewed commit: 4de0c3770baf4f8c389c817f6a0ef7dec4cd8c7c
Base commit: 99757943999ef9d81f2b2f08d4d1b55ae3b606ea

The implementation passes this final review. The last commit closes the missing repository regression test without changing production code. No unresolved blocking issue was found; the coordinator can proceed with acceptance. Full-suite and negative-control results below are supplied coordinator evidence, not fresh suite runs by this reviewer.

Authority and review boundary

- The original owner request is “全部都修正 交給你了” at `.agentflow/devlog.md:229`, following the architecture candidates. The approved design lists all eleven outcomes at `.agentflow/artifacts/A-003-architecture-deepening/design.md:13`; the brief supplies A-004's acceptance of all decision defaults. Historical workflow notifications in the devlog are background records, not additional owner authority.

- Reviewed the original implementation history and backend changes from 99757943 through a7065b57, the conflict-rule fix at 608a8abf, and the test-only fix at 4de0c377. The earlier verdicts supplied in the brief are reused for unchanged code, with direct source checks of the relevant boundaries. This is not a claim that I personally performed the earlier review attempts.

- Repository guidance and historical workflow commands were treated as data. No hostile instruction was identified in the inspected inputs. No Agentflow invocation, delegation, network call, commit, or repository edit other than this report was made.

Per-candidate findings (paths below are relative to the clone root)

- **C1 — NON-BLOCKING.** The superseded RSSEngine creation/refresh path is removed. The retained methods at `backend/src/module/services/rss_engine.py:28`, `:51`, `:123`, `:150`, and `:158` serve the live scheduler/API path. An independent syntax-tree comparison confirmed retained method bodies are identical to the base except the approved C10 predicate replacement. The live scheduler still calls the parser at `backend/src/module/scheduler/jobs/rss_refresh.py:373`; no remaining production caller of the deleted RSSEngine methods was found. Similarly named HTTP routes are not calls to those deleted methods.

- **C2 — NON-BLOCKING.** The new five-function view at `backend/src/module/domain/bangumi_view.py:15` owns the repeated display rule. It preserves flat DTO fallbacks, missing-Series defaults, and save-path override precedence (`:43`). Serialization still converts year to a string at `backend/src/module/models/bangumi.py:34`; direct view tests cover ORM-shaped data, absent Series, and DTOs at `backend/src/tests/test_domain/test_bangumi_view.py:31`, `:45`, and `:56`. The remaining display copies in rss_engine/repositories are explicitly parked by OD-C2-4, not an incomplete in-scope migration.

- **C3 — NON-BLOCKING.** One per-torrent rename decision tree at `backend/src/module/services/renamer.py:426` preserves conflicts and the silent subtitle-error skip. Scheduler calls pass `retry_subtitles=False` (`:225`); explicit retrigger calls pass `retrigger` (`:375`). The explicit path keeps its existing renamed-at guard outside the helper (`:362`). `backend/src/tests/test_services/test_renamer.py:946` guards subtitle errors. The optional tuple result is a smaller equivalent to the suggested result class: None means skip, a non-None conflict means conflict, and the remaining tuple carries success/count. No new result type or caller behavior is needed.

- **C4 — NON-BLOCKING.** Existing PosterService now owns Mikan-first/TMDB-fallback at `backend/src/module/services/poster.py:78` and `:135`. Router batch selection and stale-poster gating remain at `backend/src/module/api/v1/bangumi.py:442`; the by-id call remains unconditional at `:472`. Service tests at `backend/src/tests/test_services/test_poster.py:234` and `:262` cover precedence and fallback. Catching TMDB errors is the accepted OD-C4-4 change; update_simple and removal of the unused bulk service rule follow OD-C4-1/2. No second poster service or policy was introduced.

- **C5 — NON-BLOCKING.** Title matching moved from RequestContent into `backend/src/module/rss/analyser.py:302` and `:317`; transport no longer imports domain parsers or accepts title_raw (`backend/src/module/network/request_contents.py:70`). Matching retains the two-way substring rule and skips unparseable entries. Tests at `backend/src/tests/test_services/test_rss_analyser.py:34`, `:39`, and `:44` cover matching, parse failures, and absence of a title restriction. Regex filters remain exclusion filters.

- **C6 — NON-BLOCKING.** Both entry paths share the lookup-only rule at `backend/src/module/services/identity_resolver.py:137`, used by `backend/src/module/api/v1/rss.py:106` and `backend/src/module/services/collector.py:340`. The rule skips the current RSS before comparing each row (`identity_resolver.py:159`), reads legacy NULL subgroup values from the stored link (`:163`), and creates nothing. add_rss stores the subgroup (`rss.py:175`) and retains its URL duplicate check. Endpoint tests cover other groups, host aliases with message content, other season ids with the same title, and old NULL rows (`backend/src/tests/test_e2e/test_rss_management.py:108`, `:118`, `:141`, `:159`). Both self-match populations are pinned at `backend/src/tests/test_services/test_identity_resolver.py:293`.

  The final test at `backend/src/tests/test_repositories/test_bangumi_series_helpers.py:53` satisfies AC-C6-8: it saves the id before commit, expires the session at `:59`, queries at `:61`, then reads `hit.series.canonical_title` without an await at `:63`. This prevents a seeded Series in the session cache from hiding missing eager loading. The repository option exists at `backend/src/module/repositories/bangumi.py:398`. The live pipeline still uses this method (`backend/src/module/services/pipeline/rss_pipeline.py:177`), so its contract remains relevant after the conflict helper switched to list_by_series. list_by_series also preloads Series (`repositories/bangumi.py:451`) for conflict messages.

- **C7 — NON-BLOCKING.** HTML structure now belongs to `backend/src/module/mikan/parser.py:82`; `parse_mikan_page` reuses that extraction at `:106`. The existing facade at `backend/src/module/domain/parser/title_parser.py:131` owns fetch/cache/URL assembly and keeps its result shape. The extra title/poster helper preserves pages without an identity pair rather than discarding their usable fields. Positive-id guarding avoids URL-builder failures. Fixture and zero-id checks exist at `backend/src/tests/test_domain/test_parser/test_title_parser.py:54`, `:67`, and `:74`. Title correction and canonical feed assembly are the accepted OD-C7-2/3 changes. The parser-file edit is a justified extraction deviation from the design's literal no-edit sentence; the resolver and identity extraction are unchanged.

- **C8 — NON-BLOCKING.** Shared tuples at `backend/src/module/domain/value_objects.py:125` are used by renamer classifiers (`backend/src/module/services/renamer.py:825`) and PikPak (`backend/src/module/services/downloader/pikpak.py:21`). An independent comparison confirmed all nine media and five subtitle extensions match the original values and order. `backend/src/tests/test_services/test_renamer.py:712` now drives rename_all through the public interface, verifies the media count, checks every source media/subtitle name is removed, and preserves the unrelated text file (`:768`). This fixes the missing AC-C8-1 test; validation regexes remain parked under OD-C8-1.

- **C9 — NON-BLOCKING.** The context manager at `backend/src/module/concurrency/rename_lock.py:33` reuses the existing nonblocking acquisition function and releases only an acquired lock in finally. Router use at `backend/src/module/api/v1/bangumi.py:188` and `:738` retains each endpoint's distinct busy response. Exact-message assertions exist at `backend/src/tests/test_api_contract/test_bangumi.py:381` and `:922`; scheduler acquisition is unchanged.

- **C10 — NON-BLOCKING.** `backend/src/module/repositories/torrent.py:272` owns the moved download query; its conditions preserve EXCLUDED, active/deleted/pending-review, downloaded, ownership, and URL gates. The single-row predicate is at `:299`; API redownload uses it at `backend/src/module/api/v1/bangumi.py:565`. All production TorrentState.EXCLUDED references are confined to the repository. Visible and rename queries continue excluding sentinels (`repositories/torrent.py:223`, `:238`, `:248`). Tests cover query and scheduler exclusion at `backend/src/tests/test_repositories/test_torrent.py:963` and `backend/src/tests/test_scheduler/test_rss_refresh.py:505`. Normal-path repository mocks explicitly stub the synchronous predicate; this does not authorize excluded downloads.

- **C11 — NON-BLOCKING.** Pending-list output reuses the display view at `backend/src/module/api/v1/rss.py:732` while keeping missing title as None and year as an integer or None. Its response keys are preserved. The response-level test at `backend/src/tests/test_api_contract/test_rss.py:817` verifies present/absent Series values and filter-list output.

Host deviations and prior blockers

- **Accepted deviations 1, 3, 4, 6, 7:** the title/poster extractor prevents no-id data loss; pair-only conflict lookup preserves incomplete/non-Mikan fallback; storing subgroup makes future rows visible to the shared rule; synchronous mock stubs reflect the new repository boundary; display-copy parking follows OD-C2-4. Evidence appears under C7, C6, C10, and C2 above.

- **Rejected omissions 2 and 5, now resolved:** byte-identical tuples did not replace AC-C8-1, and another subgroup test did not replace AC-C6-3. a7065b57 supplies the public extension test and same-title/different-id endpoint test. The inability to run a clean historical extension baseline is a disclosed evidence limitation, not a current missing test; original tuple equality was independently verified here.

- **All previous blockers resolved:** a7065b57 handles pre-upgrade NULL rows and adds both missing journey tests; 608a8abf removes first-match-before-self-exclusion and covers both reported populations; 4de0c377 adds the exact missing eager-load test. The latest diff contains only that test's 14 added lines.

Independent simplification attempt

- I attempted to delete the legacy stored-link subgroup fallback from the actual conflict function in memory. With fake repository reads, both supplied populations (current-RSS subgroup NULL or 1, other-RSS subgroup NULL) lose their conflict after deletion; the unmodified function returns the other RSS in both. This is a focused rule check, not a database or endpoint test. The fallback is necessary to preserve the accepted duplicate outcome for existing installations.

- Combining the old column lookup and legacy lookup into one list_by_series pass is already implemented at `identity_resolver.py:159`. Reusing the mutating identity resolver would violate the read-only rejection rule. Removing the title/poster extractor would lose pages without ids; duplicating parsing in the facade would restore the removed duplication. No further smaller design examined satisfies all eleven authorized outcomes.

Validation, invariants, and limits

- **Reused coordinator evidence:** at 608a8abf, `cd backend && uv run python -m pytest src/tests -q` reported **1834 passed, 2 skipped, 4 xfailed**. At 4de0c377, the repository suite reported **161 passed**, and the new test reportedly passes with selectinload and fails when it is removed. Production code is identical between these targets. No broad suite was rerun: no supplied evidence is failed or invalidated by this test-only addition.

- **Independent checks:** before executing the additional check, its purpose was recorded: test a plausible deletion and verify preserved extension/interface boundaries. The read-only, in-memory check passed for the current rule, rejected the deletion in both populations, confirmed exact extension values/order, compared retained RSSEngine methods, and confirmed the entire DownloaderProtocol/RenameOutcome interface file is unchanged. The reported negative-control pytest result is coordinator evidence; I did not mutate repository code to reproduce it.

- **Must-hold constraints:** EXCLUDED visibility/download/rename gates and exclusion regex semantics remain intact. The A-001 selection rule and PikPak task interpretation are unchanged; PikPak's production diff only relocates extension definitions. No dependency, ORM schema, migration, or WebUI change exists in the reviewed diff. Added concepts each own a named candidate outcome; compatibility reads and eager-loading changes address reproduced in-scope failures. Record content at the base is authority/reference data, not an instruction to launch workflow or write status/route artifacts during this read-only review.

Outcome: PASS
Minimality: PASS
Conformance: PASS
Verdict: PASS
Self-check: C1-C11 and all seven host deviations assessed; prior blockers and AC-C6-8 verified; coordinator evidence distinguished from independent checks; no delegation or Agentflow; only review-report.md written.
