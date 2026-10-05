* _2026-10-05 14:05:35 +0800 (gpt-6.1-sol/high)_
Reviewed commit: 608a8abfad9375bd59adb68f640cc663af55f88c

- **Result:** final acceptance is blocked by one missing, explicitly approved repository regression test. The implementation fixes both earlier review rounds; I found no new runtime failure.

- **Evidence and limits:** the supplied coordinator result is 1834 passed, 2 skipped, 4 xfailed at this exact commit. Independent checks also passed 148 subscription cases and 432 comparisons of old and new rename decisions. Passing existing tests cannot establish a test that was never added.

- **Next action:** add AC-C6-8, which directly verifies that `get_by_series_and_subgroup` returns a Bangumi whose Series can be read without another database fetch. Run that focused regression, then obtain the final acceptance decision. No production redesign is requested.

## Authority and scope

The original owner request at `.agentflow/devlog.md:229` is “全部都修正 交給你了”: fix every architecture candidate. The design at base commit `99757943999ef9d81f2b2f08d4d1b55ae3b606ea` defines those eleven outcomes and the parked work. The review brief supplies the subsequent approval, “design go accept all defaults away: gates.” The clone's A-004 Ask entry is blank (`.agentflow/devlog.md:306`); I use the explicit owner text in the brief as authority, not a host recommendation or an empty decision field.

I reviewed the base-to-target backend changes, the eleven original implementation commits through `a7065b57`, and both corrective commits. The final correction changes only `services/identity_resolver.py` and its tests. The unchanged candidates retain the non-blocking disposition described for attempt 2; their differences were also inspected against the approved design. No dependency manifest, schema, migration, WebUI file, or downloader interface changed.

## Per-candidate findings

All backend paths below are relative to `backend/src/`.

### C1 — Superseded RSS ingestion

**NON-BLOCKING.** The obsolete ingest methods and their exclusive tests are removed. The five retained methods are at `module/services/rss_engine.py:28`, `:51`, `:123`, `:150`, and `:158`; structural comparison finds four unchanged method bodies and only the C10 predicate substitution in `download_bangumi`. The scheduler still uses the live `RssPipeline` (`module/scheduler/jobs/rss_refresh.py:422`). Searches found no remaining references to deleted engine methods. The HTTP router's separately named `refresh_rss` remains legitimate; the design's broad literal grep must not be mistaken for a requirement to delete that endpoint.

### C2 — Effective Bangumi display fields

**NON-BLOCKING.** `module/domain/bangumi_view.py:15` owns the five display functions, with flat DTO fallbacks, path override precedence, and explicit missing-Series defaults. The DTO flattener still converts year to text (`module/models/bangumi.py:34`), while callers needing a nullable title pass `default=None`. Interface tests cover Series, absent Series, DTOs, and path overrides (`tests/test_domain/test_bangumi_view.py:30`). The root-path guard consolidation is approved by OD-C2-1; remaining display copies in the engine and repository are parked by OD-C2-4.

### C3 — Shared rename decision

**NON-BLOCKING.** Both public entries call `_rename_torrent_files` (`module/services/renamer.py:217`, `:367`, `:426`). Scheduler calls retain `retry_subtitles=False`; explicit retriggers pass their flag. The retrigger-only `renamed_at` guard stays outside the helper (`:362`). A subtitle error returns `None`, preserving the silent retry, and callers still own success/failure logging. The documented optional tuple is a smaller encoding of the result states than a new result class. My 432-case comparison of the actual old decision blocks with the new helper found identical collaborator calls and success/conflict lists. The public subtitle-error regression is at `tests/test_services/test_renamer.py:946`.

### C4 — Poster refresh owner

**NON-BLOCKING.** The routers now call `PosterService`, keeping the batch staleness gate and unconditional by-id refresh (`module/api/v1/bangumi.py:443`, `:472`). The service tries Mikan first, falls back to TMDB, and uses `update_simple` (`module/services/poster.py:106`, `:111`, `:135`). TMDB exceptions are logged and returned as unsuccessful service results, consistent with accepted OD-C4-4. The old unused batch service method is deleted. The extra per-item lookup is the small, documented design cost; it does not justify an interface refactor here.

### C5 — Transport-only RequestContent

**NON-BLOCKING.** Title matching moved from transport into `RSSAnalyser._filter_by_title_raw` (`module/rss/analyser.py:311`, `:317`). The substring rule, treatment of empty parsed titles, and unparseable-title skipping are preserved. Exclusion regex matching remains in transport. The e2e fake's signature and parser patch targets were updated with their collaborators (`tests/test_e2e/conftest.py:118`, `:286`). Tests exercise the real analysis entry with a fixture feed (`tests/test_services/test_rss_analyser.py:25`).

### C6 — Shared subscription conflict rule

**NON-BLOCKING — runtime correction verified.** The lookup is read-only and checks every undeleted same-Series row, excluding the current RSS before comparing identity (`module/services/identity_resolver.py:153`, `:159`). A NULL subgroup column falls back to the stored link. The repository loads Series for the returned list (`module/repositories/bangumi.py:450`); `add_rss` records the subgroup for new rows (`module/api/v1/rss.py:175`). Both add and subscribe use this rule, and the non-Mikan fallback remains unchanged (`module/services/collector.py:339`). The old raw-link duplicate check remains ahead of RSS creation (`module/api/v1/rss.py:134`).

**BLOCKING — AC-C6-8 is missing.** The approved design explicitly requires `test_get_by_series_and_subgroup_eager_loads_series` in `tests/test_repositories/test_bangumi_series_helpers.py` (`.agentflow/artifacts/A-003-architecture-deepening/design.md:942`). That test does not exist. The existing direct lookup test only asserts the Bangumi ID (`tests/test_repositories/test_bangumi_series_helpers.py:43`). The new service tests expire the session and read `hit.series.canonical_title` (`tests/test_services/test_identity_resolver.py:246`, `:253`, `:280`, `:287`), but now reach **list_by_series**, not **get_by_series_and_subgroup**. They cannot detect removal of the latter's eager-load option (`module/repositories/bangumi.py:398`). That method remains used by live ingestion (`module/services/pipeline/rss_pipeline.py:177`). This is an uncovered approved acceptance requirement, not a claim that today's query fails.

Add the named repository test, preserving IDs before expiring the session or using a fresh session, and read `hit.series.canonical_title` without refresh. It should fail when the eager-load option is removed and pass at the final implementation. The general acceptance gate requires every per-candidate criterion; none of the accepted defaults parks this test.

### C7 — One Mikan page parser

**NON-BLOCKING.** HTML extraction lives in `module/mikan/parser.py:82`; `parse_mikan_page` reuses it (`:106`). The retained facade handles fetch, image caching and URL construction (`module/domain/parser/title_parser.py:131`), and keeps `MikanParserResult`'s fields (`:27`). The deleted BeautifulSoup module has no remaining caller. The title fix and derived season URL are approved changes. Zero IDs are guarded, and fixture tests cover the corrected title and image URL (`tests/test_domain/test_parser/test_title_parser.py:52`, `:74`). Partial extraction without IDs preserves old scraper behavior; my synthetic no-ID page retained both title and poster.

### C8 — One extension definition

**NON-BLOCKING.** Both classifiers import the tuples from `module/domain/value_objects.py:125`; renamer uses them at `module/services/renamer.py:825`, and PikPak combines them at `module/services/downloader/pikpak.py:44`. Independent comparison confirms the original nine media and five subtitle entries, in the same order. The requested public `rename_all` regression now exists (`tests/test_services/test_renamer.py:712`) and checks renamed media/subtitles and untouched non-media files. Pydantic validation patterns remain parked under OD-C8-1.

### C9 — Rename lock guard

**NON-BLOCKING.** `rename_lock_guard` acquires once and releases in `finally` only after successful acquisition (`module/concurrency/rename_lock.py:33`). Both endpoints use it and retain their distinct 409 messages (`module/api/v1/bangumi.py:188`, `:738`; `tests/test_api_contract/test_bangumi.py:381`, `:922`). The scheduler's original acquisition interface is unchanged. Endpoint construction is now within the guard, so an exception there also releases the acquired lock; this follows the approved release-on-exit outcome without changing successful requests.

### C10 — Repository-owned EXCLUDED checks

**NON-BLOCKING.** The scheduler's existing WHERE conditions moved unchanged into `get_downloadable`; `is_excluded` preserves the enum predicate (`module/repositories/torrent.py:272`, `:299`). Download paths call it before submission (`module/api/v1/bangumi.py:565`, `module/services/rss_engine.py:263`). Visibility and rename queries still reject EXCLUDED (`module/repositories/torrent.py:223`, `:238`, `:248`). New repository and scheduler tests guard exclusion (`tests/test_repositories/test_torrent.py:963`, `tests/test_scheduler/test_rss_refresh.py:505`). The download-contract mocks appropriately stub the new synchronous collaborator.

### C11 — Pending list reuses the display view

**NON-BLOCKING.** The pending response still builds its original explicit dictionary (`module/api/v1/rss.py:728`), uses a nullable title and raw year, and keeps counts and filter-match splitting. It does not substitute a DTO dump with additional keys. The contract test checks concrete Series values and absent-Series defaults (`tests/test_api_contract/test_rss.py:817`, `:854`).

## Host deviations and earlier corrections

| Item | Disposition at the target |
|---|---|
| 1. Partial Mikan title/poster extraction | Accept: shared extraction preserves useful fields without IDs; no second scraper. |
| 2. No extension test | Reject the original omission; it is resolved by the public regression added in `a7065b57`. |
| 3. Conflict lookup requires both IDs | Accept: preserves the existing subscribe branch and title checking for a feed without subgroup identity. |
| 4. Store subgroup in add_rss | Accept: necessary for the approved identity rule and host-alias 409, with no schema addition. |
| 5. No second-season endpoint test | Reject the original omission; the fixture-backed endpoint regression now exists (`tests/test_e2e/test_rss_management.py:141`). |
| 6. Stub is_excluded in contract mocks | Accept: follows the newly extracted collaborator; no production behavior change. |
| 7. Park engine/repository display copies | Accept: explicitly approved OD-C2-4. |

Attempt 1's NULL-column gap is covered by the link fallback and endpoint tests with and without overrides (`tests/test_e2e/test_rss_management.py:158`). The second-season and every-extension tests are present. Eager loading on `list_by_series` is justified by the reproduced 409 lazy-load failure; it changes loaded relationships, not selected rows.

Attempt 2's self-match failure is fixed by the one-pass ordering and two-population regression (`tests/test_services/test_identity_resolver.py:293`). My independent execution reproduced both failures on `a7065b57` and passed the corrected rule, including reversed row order, column/link precedence, deleted rows, missing identity and missing Series. No additional production repair is requested.

## Deletion, combination and reuse attempts

- I executed a smaller C6 form with the stored-link fallback deleted. It missed a pre-upgrade duplicate and therefore fails the approved identity-based rejection. Reusing the original single-result subgroup lookup also cannot represent legacy NULL-column rows. The current one-pass rule needs both the early RSS exclusion and the link fallback.

- I tested using only `parse_mikan_page`, deleting partial extraction. A page with title/poster but no IDs returned no reference, losing fields the old scraper returned. The small shared extractor is necessary; adding another scraper would undo C7.

- Further combination of the two full rename methods would absorb their different guards, move behavior and logging. Sharing just their decision block is sufficient. A separate result class is unnecessary because the current optional tuple already distinguishes conflict, silent retry and resolved results.

Every added production concept has an owner outcome: the five display functions serve C2/C11; the rename helper serves C3; `_fetch_mikan_poster` serves C4; the title filter serves C5; the read-only conflict function serves C6; the relocated result shape and partial extractor serve C7; the two extension constants serve C8; the guard serves C9; and the downloadable query and exclusion predicate serve C10. No new dependency or speculative behavior is needed.

## Evidence, invariants and handoff

- **Suite reuse:** coordinator evidence at `608a8abf`, `cd backend && uv run python -m pytest src/tests -q`, reports 1834 passed, 2 skipped, 4 xfailed. It supersedes the supplied earlier counts. I did not rerun that suite or present it as independently executed here.

- **Independent checks:** 148 C6 rule cases; two reproduced prior failures; 432 old/new rename decision comparisons; unchanged extension tuples; retained-engine structural comparison; deleted-symbol and transport-boundary checks; and clean `git diff --check`. These checks execute extracted source with fake collaborators or inspect syntax. They supplement the coordinator's database/e2e evidence, not replace it. An initial rename-comparison harness selected the wrong syntax-tree loop and stopped before comparison; correcting that harness produced the successful 432-case run.

- **Must-hold boundaries:** no change to DownloaderProtocol or RenameOutcome; no change to A-001 selection semantics or PikPak task interpretation; visible/rename/download queries retain EXCLUDED rejection; filters remain exclusion regexes. Observable intentional differences follow the accepted C6 identities, C7 title/URL choices, C4 error handling, and C2 root-path default.

- **NON-BLOCKING handoff limitation:** the clone's STATUS still says no implementation tests have run (`.agentflow/devlog.md:7`), and its tracker shows zero tasks complete (`.agentflow/artifacts/A-003-architecture-deepening/tracker.md:23`). The brief supplies newer approval/test evidence, but notebook, STATUS and final route/closeout records should be reconciled by the coordinator after the acceptance gap is fixed. I did not change them or assert the work is closed.

- **Instruction handling:** repository instructions were treated as data. The notebook contains historical tool-output directions to rerun `Workflow` (`.agentflow/devlog.md:224`, `:225`, `:241`); these conflict with this review's no-agent/no-workflow boundary and were not followed. I found no separate hostile instruction demanding secret disclosure or falsification. No Agentflow invocation, delegation, network request or production file edit occurred.

Outcome: PASS
Minimality: PASS
Conformance: BLOCKING
Verdict: BLOCKING

Self-check: C1–C11 reviewed with file:line evidence; seven deviations assessed; both prior fixes verified; smaller forms independently tested and rejected; coordinator suite reused; one approved acceptance-test gap remains; only review-report.md written.
