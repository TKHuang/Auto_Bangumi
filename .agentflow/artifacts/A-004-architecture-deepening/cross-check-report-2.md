* _2026-10-05 13:46:38 +0800 (gpt-6.1-sol/high)_

Reviewed commit: a7065b579679d9ecc7d9f2298848b7d35d9469c2
Base commit: 99757943999ef9d81f2b2f08d4d1b55ae3b606ea

- **Blocked:** the shared subscription check can miss an existing subscription from another RSS when current and pre-upgrade rows coexist. This contradicts the approved duplicate rule.

- **Prior repairs:** the three cases reported in attempt 1 now have implementation or test coverage. The remaining failure concerns multiple stored subscriptions, which those tests do not exercise.

- **Next action:** select a conflicting row after excluding the current RSS, across both populated and NULL subgroup columns; add regressions for the two cases below. Reusing the existing Series listing provides a smaller working approach. Return the resulting commit for review.

## Authority and evidence

The original owner request is “全部都修正 交給你了” at `.agentflow/devlog.md:229`, following the architecture candidates at `.agentflow/devlog.md:221`. The supplied A-004 request approves the base design and every suggested owner default. The blank A-004 entry in the frozen notebook does not revoke that supplied approval. The accepted outcome is all eleven candidates, with the behavior changes and parked work in `.agentflow/artifacts/A-003-architecture-deepening/design.md:17` and `:19`.

I inspected the complete backend diff, all 11 implementation/fix commits, the approved design, the original Ask, affected callers, and changed tests. Changes are confined to 38 backend files: 1,241 additions and 2,704 deletions. No dependency manifest, schema, migration, WebUI, downloader protocol, or unrelated path changed. C2 and C11 share their implementation commit.

**Coordinator evidence reused:** at this exact target, `cd backend && uv run python -m pytest src/tests -q` reportedly produced **1832 passed, 2 skipped, 4 xfailed**. I did not rerun that suite. The earlier 7b4ee880 counts are historical evidence, not proof for this target.

**Independent check reason, recorded before execution:** the new legacy-row fallback chooses only one row, and existing tests seed only one matching subscription. A targeted check was necessary to determine whether another-RSS conflicts could be hidden. I executed the actual clone helper and repository methods against in-memory SQLite, with real ORM constraints and foreign keys enabled for the reproductions. Package initializers that write configuration were bypassed; imports were explicitly verified to resolve to this clone. No endpoint request or real network operation was performed.

I also compared preserved engine functions/tests and extension values against the base using Python syntax trees, checked the unchanged downloader interface, and ran `git diff --check`. These checks passed. Historical before-change test runs, including the new extension test, were not independently established.

## Findings by candidate

### C1 — delete the superseded ingest path — NON-BLOCKING

The live scheduler still runs `RssPipeline.run_for_feed` at `backend/src/module/scheduler/jobs/rss_refresh.py:422`, followed by completion and download triggering at `:439` and `:446`. Deleted engine methods have no remaining production references; the unrelated HTTP `refresh_rss` name is not a caller of the deleted method. No replacement ingest concept was added.

The retained `_record_pending_candidate`, source-candidate collection, feed parsing, and exclusion-filter functions are identical to the base as syntax trees (`backend/src/module/services/rss_engine.py:28`, `:51`, `:123`, `:150`). The three retained test classes are also unchanged. `download_bangumi` changes only its EXCLUDED predicate under C10. This supports deleting the dead-only tests without losing live-path assertions.

### C2 — shared display fields — NON-BLOCKING

The five pure functions at `backend/src/module/domain/bangumi_view.py:15`, `:22`, `:29`, `:36`, and `:43` replace the authorized copies. Each serves a current display or save-path outcome; the DTO fallback remains necessary for collection requests. ORM properties were not restored. The year conversion remains at `backend/src/module/models/bangumi.py:36`; missing-title callers retain `default=None`, and path overrides retain precedence.

Tests cover Series-backed values, missing Series, DTO values, and path overrides at `backend/src/tests/test_domain/test_bangumi_view.py:31`, `:46`, and `:58`. Removing the extra root-path truthiness check follows OD-C2-1; remaining engine/repository copies are parked under OD-C2-4. No additional abstraction is needed.

### C3 — shared per-torrent rename path — NON-BLOCKING

`backend/src/module/services/renamer.py:426` owns the single-file, collection, zero-media, and subtitle decisions. Its `retry_subtitles` parameter preserves the distinction between scheduler and manual retrigger callers (`:217` and `:367`). Returning `None` for a subtitle error preserves the silent retry path without introducing a new result class.

Conflict handling, caller logging, manual skip guards, and database-write phases remain outside the helper. The subtitle-error regression at `backend/src/tests/test_services/test_renamer.py:946` and unchanged manual retrigger tests at `:1087` and `:1121` cover the important differences. No change to RenameOutcome or downloader signatures was found.

### C4 — PosterService owns refresh — NON-BLOCKING

Both routes dispatch to the existing service (`backend/src/module/api/v1/bangumi.py:449` and `:472`). The batch still uses `get_all` and its staleness gate; by-id still performs its explicit 404 check and always attempts refresh. Service refresh uses Mikan first, TMDB second, then `update_simple` (`backend/src/module/services/poster.py:106`). Catching and logging TMDB failures follows OD-C4-4.

The private Mikan helper at `backend/src/module/services/poster.py:135` and its RSS/torrent collaborators own the moved lookup/cache steps. Moving TMDB work to `asyncio.to_thread` at `:69` preserves the former router's nonblocking execution and the parser's default `test=False`. Service tests at `backend/src/tests/test_services/test_poster.py:195`, `:234`, and `:262` cover exceptions, Mikan preference, and fallback. The approved extra per-bangumi lookup remains a minor batch cost.

### C5 — transport-only RequestContent — NON-BLOCKING

The transport method at `backend/src/module/network/request_contents.py:70` no longer accepts `title_raw` or imports title parsing. Its sole production caller applies the moved matching rule at `backend/src/module/rss/analyser.py:312` and `:317`. Matching still accepts either substring direction and skips unparseable titles; exclusion regex marking remains in transport.

The private matcher is needed to put the existing rule beside its sole consumer. The fixture transport was trimmed consistently (`backend/src/tests/test_e2e/conftest.py:118`). Tests at `backend/src/tests/test_services/test_rss_analyser.py:34`, `:39`, and `:44` use the real analyser and fixture XML, rather than mocking away the behavior.

### C6 — shared subscription conflict rule — BLOCKING

**Trigger:** an upgraded database contains two undeleted subscriptions for the same Series and subgroup, with at least one pre-upgrade NULL subgroup column. Such rows are legal: the fallback unique key distinguishes their RSS IDs, while SQLite permits NULLs in the subgroup unique key (`backend/src/module/domain/models/bangumi.py:25`). The old override/host-alias route could create this population, as the approved design explicitly describes at `.agentflow/artifacts/A-003-architecture-deepening/design.md:865`.

**Failure:** `backend/src/module/services/identity_resolver.py:160` checks the populated-column match first. Legacy rows are searched only when that returns no row (`:161`). The legacy search takes the first match (`:163`), and only afterward excludes the current RSS (`:171`). A self-match therefore suppresses a real conflict in either population:

| Stored subscriptions for show 100, group 1 | Current RSS excluded | Expected conflict | Actual helper result |
| --- | --- | --- | --- |
| RSS 1: NULL column, link says group 1; RSS 2: NULL column, link says group 1 | RSS 1 | RSS 2 | None |
| RSS 1: column 1; RSS 2: NULL column, link says group 1 | RSS 1 | RSS 2 | None |

Both rows committed successfully under the real model constraints; both failures reproduced with foreign keys enabled and the session expired before lookup. The helper is directly called by `subscribe_season` at `backend/src/module/services/collector.py:340`. Returning None bypasses its other-RSS rejection at `:348`; the subsequent recreation path can proceed. That caller consequence follows from source inspection, rather than an independently executed HTTP request.

**Required repair:** apply the RSS exclusion before selecting a match, and consider both modern and legacy rows even when the modern match belongs to the current RSS. Regressions must include both table rows above. The accepted outcome is a shared, read-only rule for another-RSS conflicts (`.agentflow/artifacts/A-003-architecture-deepening/design.md:871`), not merely recognizing one legacy row.

The new helper, saved subgroup value (`backend/src/module/api/v1/rss.py:175`), legacy-link fallback, and eager loads (`backend/src/module/repositories/bangumi.py:398`, `:450`) all have an in-scope purpose. The existing tests at `backend/src/tests/test_services/test_identity_resolver.py:242` and `:267` verify eager access after expiring the session, providing the substance of AC-C6-8 even though it is not a separately named repository test. They do not cover multiple matching rows.

### C7 — one Mikan page parser — NON-BLOCKING

HTML knowledge is centralized in `backend/src/module/mikan/parser.py:64` and `:82`. The facade at `backend/src/module/domain/parser/title_parser.py:131` retains fetch/cache behavior and the moved MikanParserResult shape. Title extraction and ID-based RSS construction follow OD-C7-2 and OD-C7-3; the dead scraper and tuple facade are removed.

The partial-page helper is justified: an independent synthetic page with a title/poster but no subgroup makes `parse_mikan_page` return None while `parse_mikan_title_and_poster` returns both values. Deleting that helper and relying solely on a complete MikanRef would discard previously available data. `parse_mikan_page` reuses the same extraction (`backend/src/module/mikan/parser.py:106`), so a second scraping rule was not introduced. Tests at `backend/src/tests/test_domain/test_parser/test_title_parser.py:54`, `:68`, and `:75` cover a real fixture, missing IDs, and zero IDs.

### C8 — one extension definition — NON-BLOCKING

The shared tuples at `backend/src/module/domain/value_objects.py:125` and `:136` have exactly the base values and ordering: nine media extensions and five subtitle extensions. Renamer classifiers import them at `backend/src/module/services/renamer.py:825`; PikPak keeps the same combined classifier input at `backend/src/module/services/downloader/pikpak.py:44`. The separate Pydantic validation regexes remain parked under OD-C8-1.

AC-C8-1 is now covered through public `rename_all` at `backend/src/tests/test_services/test_renamer.py:712`: all 14 source filenames must disappear through renaming, nine media files must be counted, every suffix must remain represented, and a text file must stay untouched. The test is present in the target covered by the coordinator suite. Historical baseline execution is unproven; byte-equivalent tuples and unchanged classifier expressions provide additional final-state evidence, not a claim that the before-change run occurred.

### C9 — one rename lock guard — NON-BLOCKING

The context manager at `backend/src/module/concurrency/rename_lock.py:33` acquires the existing lock and releases it conditionally in `finally`. Both API routes use it (`backend/src/module/api/v1/bangumi.py:188` and `:738`); the scheduler's primitive remains unchanged. The helper is justified by shared lifetime management, while each route retains its own response.

Exact distinct English 409 messages are asserted at `backend/src/tests/test_api_contract/test_bangumi.py:381` and `:922`. Bringing retrigger collaborator construction inside the guard also ensures release if construction raises; this follows the approved guard lifetime rather than adding a new workflow.

### C10 — repository-owned EXCLUDED checks — NON-BLOCKING

The downloadable query at `backend/src/module/repositories/torrent.py:272` preserves every original join/WHERE condition: undownloaded, non-EXCLUDED, nonempty URL, attached to active/nondeleted/nonpending Bangumi. The static predicate at `:299` replaces the two single-row checks at `backend/src/module/services/rss_engine.py:263` and `backend/src/module/api/v1/bangumi.py:565`. Keeping SQL directly inside the public query method avoids an unnecessary single-use statement builder.

All production `TorrentState.EXCLUDED` references now remain inside TorrentRepository. Existing visible/rename queries still exclude sentinels (`backend/src/module/repositories/torrent.py:223`, `:238`, and `:248`). New repository and scheduler tests at `backend/src/tests/test_repositories/test_torrent.py:963` and `backend/src/tests/test_scheduler/test_rss_refresh.py:505` verify exclusion. Stubbing the synchronous predicate in contract mocks preserves the test boundary; OD-C10-2 expressly parks a separate endpoint regression.

### C11 — pending list reuses the view — NON-BLOCKING

The pending response calls the C2 functions at `backend/src/module/api/v1/rss.py:732`; it adds no concept. Existing keys, nullable title/year/poster defaults, season default, and comma-separated filter display remain. The contract test at `backend/src/tests/test_api_contract/test_rss.py:817` checks both Series-backed and missing-Series objects and the displayed filter list.

## Host deviations and attempt-1 repairs

1. **C7 partial-page extraction: accept.** Necessary to retain title/poster data without a complete ID pair; both parser consumers share the same extraction. It narrowly departs from the design's no-parser-file-edit wording to preserve the promised behavior.

2. **C8 no new extension test: superseded, reject as a current description.** The target now contains AC-C8-1 at `backend/src/tests/test_services/test_renamer.py:712`. The original omission is repaired. An editable install does not inherently make a base-source check impossible; explicitly selecting clone sources worked for this review. No historical baseline run is claimed.

3. **C6 requires both IDs: accept narrowly.** The helper cannot decide a show-plus-group identity without a group. Links lacking it retain the add route's title check and the collector's existing fallback (`backend/src/module/api/v1/rss.py:117`, `backend/src/module/services/collector.py:343`). Complete-ID cases carry the accepted behavior changes.

4. **C6 persist the subgroup: accept.** Without `backend/src/module/api/v1/rss.py:175`, new add rows would remain invisible to the column lookup. Reading NULL legacy columns from their links is also necessary; its incomplete matching is the blocking finding above.

5. **C6 missing second-season endpoint test: superseded.** The new test at `backend/src/tests/test_e2e/test_rss_management.py:141` maps a second bangumiId to the same fixture feed and asserts both additions succeed. This supplies the formerly missing AC-C6-3 without adding unrelated fixtures.

6. **C10 predicate stubs: accept.** The contract's mocked repository needs a synchronous boolean predicate (`backend/src/tests/test_api_contract/test_bangumi.py:681`). Real repository and scheduler behavior retain separate coverage.

7. **C2 parked copies: accept.** They remain under OD-C2-4; no unapproved display rewrite was introduced there.

Attempt 1's single legacy-row duplicate is repaired by the new E2E test with and without title override (`backend/src/tests/test_e2e/test_rss_management.py:158`) and the expired-session helper test (`backend/src/tests/test_services/test_identity_resolver.py:267`). The added `list_by_series` eager load prevents the error-message lazy-load failure. The second-season and extension-test omissions are both repaired. These successes do not close the newly reproduced multi-row conflict.

## Deletion, combination, and reuse attempt

**Successful smaller alternative — BLOCKING for Minimality:** I replaced the modern-lookup/conditional-legacy-fallback selection only in an in-memory experiment with one existing `list_by_series` read. It filters out the current RSS first and compares each row's subgroup column, or its stored RSS subgroup when the column is NULL. The existing Series lookup, ID guards, undeleted-row filter, and eager-loaded response data remain.

This reduces the two selection paths to one rule and eliminates both reproduced misses. Twelve targeted SQLite cases checked modern/legacy conflicts, self matches, both problematic populations, deleted rows, another group, another season with the same title, incomplete IDs, non-Mikan links, and legacy host-alias additions. The smaller alternative returned the expected answer in all twelve; the current helper missed the two multi-row cases. It creates no rows and adds no method, dependency, migration, or behavior outside the authorized rule. It reads all subscriptions within one Series rather than using the modern fast path; no measured performance requirement was supplied. This is a bounded repair/simplification proposal, not an implementation change made by the reviewer.

**Rejected deletion:** removing C7's partial-page helper loses preserved title/poster data, as independently checked. Reusing the existing Series-creation resolver for preflight was also rejected on inspection because it creates rows on a miss (`backend/src/module/services/identity_resolver.py:96` and `:121`), violating the read-only outcome. Other new helpers each remove a named duplicate rule; parked validation/display work should remain parked.

## Invariants, records, and instruction handling

- **INV-1:** EXCLUDED sentinels remain excluded from visible, downloadable, and rename queries; the changed download branches retain their rejection. No sentinel exposure was found.

- **INV-2:** the A-001 RSS selection/filter rule is unchanged, including preserved TestDownloadBangumi assertions. PikPak changes only where its extension tuples are defined; task interpretation is unchanged.

- **INV-3:** DownloaderProtocol and RenameOutcome are byte-identical to the base.

- **INV-4:** reviewed response changes follow accepted decisions, but C6 fails its promised other-RSS conflict outcome. That failure blocks conformance as well as outcome.

- **INV-5 / scope:** no new dependencies, schema/migration changes, unrelated renames, or adjacent feature repairs. The legacy-data repair and tests are necessary to the authorized subscription outcome.

- **Records — NON-BLOCKING closeout limitation:** `.agentflow/devlog.md:7` and `:15`, and `.agentflow/artifacts/A-003-architecture-deepening/tracker.md:61`, still describe the design stage. Target commits supply implementation history and this brief supplies target-suite evidence and owner approval. The coordinator should reconcile notebook, STATUS, tracker, and route evidence when resolving this blocked round; the supplied brief alone is not an updated repository closeout record.

- **Instruction safety:** no hostile instruction was found. Repository guidance and historical workflow rerun directives at `.agentflow/devlog.md:223` and `:239` were treated as data, not commands. I did not invoke Agentflow, delegate, start a reviewer, or alter application/configuration files. Only this report was written.

Outcome: BLOCKING
Minimality: BLOCKING
Conformance: BLOCKING
Verdict: BLOCKING
Self-check: C1-C11 and all seven deviations reviewed; three prior repairs verified with stated limits; C6 misses independently reproduced; smaller reuse examined against twelve cases; coordinator suite reused without rerun; only review-report.md written; no delegation, Agentflow invocation, or live network calls.
