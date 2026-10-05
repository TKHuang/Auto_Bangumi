* _2026-10-05 13:22:42 +0800 (gpt-6.1-sol/high)_

Reviewed commit: 7b4ee880bb5e3f0a5172792840ffd2268f4ab73b

- **Result:** changes are blocked by an upgrade-path defect in duplicate subscription detection. Existing subscriptions created by the old add-RSS endpoint can be added again after this upgrade.

- **Risk:** the passing suites cover newly created subscriptions, but miss the old database-row format. Two tests expressly required by the approved design are also absent.

- **Next action:** make the shared duplicate lookup recognize old rows, add the missing regression tests, and submit the corrected commit for review. Keep the repair within the approved behavior and avoid a schema change.

## Scope and evidence

The original owner request is “全部都修正 交給你了” at `.agentflow/devlog.md:229`, following the architecture findings at `:213–221`. The approved design maps that request to C1–C11 (`.agentflow/artifacts/A-003-architecture-deepening/design.md:13–19`). The current review brief supplies the later approval, “design go accept all defaults away: gates”; blank decision fields and the stale notebook do not cancel that approval.

I compared the base `99757943999ef9d81f2b2f08d4d1b55ae3b606ea` with the reviewed commit, inspected the changed production code and tests, and checked the design’s normal journey and acceptance criteria. The diff is 38 backend files, with 1,095 insertions and 2,703 deletions. Git shows **10 commits**, not 11: C2 and C11 share `b18923b3`. The design expressly permits that combination (`design.md:518–522`), so it is not a blocker. No dependency, schema, migration, WebUI, downloader protocol, or RenameOutcome change appears in the diff. `git diff --check` passes.

**Coordinator tests reused, not rerun:** the supplied evidence is for the exact reviewed commit: the six main test directories passed with **1,621 passed, 2 skipped, 3 xfailed**; the other listed directories passed with **206 passed, 1 xfailed**. These results remain valid for the tests they contain. They do not establish coverage of the omitted cases below.

**Reason recorded before additional execution:** I suspected that old add-RSS rows lack the subgroup ID required by the new lookup. I ran only that independent check, using SQLite in memory, the actual ORM/repository/resolver code, and the unchanged endpoint function bodies extracted from both commits. Parsing and downloader calls were replaced with deterministic stubs; decorators and dependency defaults were omitted to call the bodies directly. Package initializers that write configuration were bypassed. This was a database/endpoint-body check, not a new HTTP or network suite; both scripts exited 0 and wrote no files.

Read-only structural comparisons also confirmed that C1’s retained ingestion/selection methods are unchanged, `download_bangumi` changes only the C10 predicate, and every PikPak function/class body is unchanged. Repository instructions and historical workflow notices were treated as data. No Agentflow command, agent, or delegated reviewer was launched. No hostile instruction was found in the inspected material; the old workflow-restart suggestions in `devlog.md:239–241` were not executed.

## Per-candidate findings

### C1 — NON-BLOCKING: dead ingestion path removed

The retained entry points are `services/rss_engine.py:28`, `:51`, `:123`, `:150`, and `:158` under `backend/src/module/`. Their live scheduler caller remains `backend/src/module/scheduler/jobs/rss_refresh.py:323`, with `RssPipeline` construction at `:349`. Source comparison confirms the four retained non-download methods are identical; only C10 changes the retained download method. Searches found no remaining production reference to the removed method names. Deleted test classes exercised the removed path; no new production concept was added.

### C2 — NON-BLOCKING: one display view, with authorized fallbacks

The five functions in `backend/src/module/domain/bangumi_view.py:15–51` own title, season, year, poster, and save-path reads for ORM objects and flat data objects. They satisfy C2’s shared-view outcome without restoring ORM properties. `backend/src/module/models/bangumi.py:34–39` retains the string conversion for the API model’s year; `backend/src/module/services/bangumi_merge.py:39–41` retains its missing-title `None` default. Tests cover both object shapes and path-override precedence (`backend/src/tests/test_domain/test_bangumi_view.py:33–68`). The remaining engine/repository copies are explicitly parked by OD-C2-4.

### C3 — NON-BLOCKING: shared rename dispatch preserves caller differences

`backend/src/module/services/renamer.py:426–481` introduces `_rename_torrent_files` to own single-file, collection, and subtitle dispatch. The scheduler passes `retry_subtitles=False` at `:225`; manual rename passes `retrigger` at `:375`, keeping its `renamed_at` guard at `:362`. A subtitle error returns `None`, leaving the torrent unfinished; conflict targets and success counts retain their previous meanings. The regression test at `backend/src/tests/test_services/test_renamer.py:882–953` checks that skip behavior.

The implementation uses the existing three-value result plus `None`, rather than the proposed new result class. Both callers handle that fourth state explicitly (`renamer.py:227–232`, `:377–382`). This is an acceptable smaller representation; it adds no public type or behavior.

### C4 — NON-BLOCKING: PosterService owns the refresh rule

`backend/src/module/services/poster.py:78–151` now owns Mikan-first/TMDB-fallback refresh; `_fetch_mikan_poster` and its RSS/torrent repository dependencies serve that current outcome. Batch refresh keeps `get_all()` and the staleness gate (`backend/src/module/api/v1/bangumi.py:446–449`); by-ID refresh remains unconditional after its 404 check (`:465–472`). The service uses `update_simple` and catches lookup failures as approved (`poster.py:111–132`). Moving TMDB execution to a thread at `:69` preserves the old router’s execution model. The extra per-row lookup is the cost already disclosed in the design, not an unapproved scope expansion.

### C5 — NON-BLOCKING: title matching moved to its caller

`backend/src/module/rss/analyser.py:311–334` owns `_filter_by_title_raw`; transport no longer receives `title_raw` or imports the domain parser (`backend/src/module/network/request_contents.py:70–111`). Symmetric substring matching, false parse results, and parse-error skips are retained. Tests exercise real feed extraction through the public analyser (`backend/src/tests/test_services/test_rss_analyser.py:24–45`). The helper serves C5’s separation of transport from title matching; no new matching policy was introduced.

### C6 — BLOCKING: old add-RSS rows escape the shared duplicate rule

**Trigger:** an existing subscription was created by the base commit’s `add_rss`. Its stored RSS URL contains `bangumiId=100&subgroupid=1`, and its Series has Mikan ID 100, but the Bangumi’s `mikan_subgroup_id` is NULL. The base creation payload omitted that field (`99757943:backend/src/module/api/v1/rss.py:179–194`).

**Defect:** `backend/src/module/services/identity_resolver.py:153–163` looks up the exact stored subgroup column through `backend/src/module/repositories/bangumi.py:398–406`. It cannot recognize that older row. `backend/src/module/api/v1/rss.py:104–117` then skips the old title guard; its unchanged URL-substring check at `:132–146` cannot match another host. Writing the subgroup on new rows at `:175` does not repair existing rows.

**Independent result:** seed the old row, then submit `https://mikanime.tv/RSS/Bangumi?bangumiId=100&subgroupid=1`:

| Endpoint body | Title override | Status | Subscription rows afterward |
|---|---|---:|---:|
| Base | None; parsed title “Title X” | 409 | 1 |
| Reviewed commit | None; parsed title “Title X” | 200 | 2 |
| Base | “Title Y” | 200 | 2 |
| Reviewed commit | “Title Y” | 200 | 2 |

The no-override case is an unintended relaxation for the **same** show and subgroup. The override case fails the accepted OD-C6-1(d) tightening. A control seeded with the new subgroup field returns 409 and retains one row. SQLite permits NULL alongside subgroup 1, so the database does not prevent the duplicate. Users upgrading an existing installation can create duplicate subscriptions and potentially repeat downloads.

**Required repair:** keep one read-only rule, but recognize the IDs in the stored RSS link when an older matching-Series row lacks its subgroup column. Add upgrade-format regressions for both override cases. Do not restore a broad title-only guard, which would break the approved second-season/group behavior.

**Additional BLOCKING acceptance gap:** AC-C6-3 explicitly requires a same-title, different-Mikan-ID endpoint test (`design.md:937`). Added endpoint tests cover only another subgroup and a host alias (`backend/src/tests/test_e2e/test_rss_management.py:108–139`); helper tests at `backend/src/tests/test_services/test_identity_resolver.py:231–265` do not exercise two same-titled seasons through add-RSS. My focused endpoint-body check allowed ID 200 beside ID 100, but that does not supply the required committed regression. Use synthetic feed data if no existing fixture fits.

The lookup-only helper itself serves C6 and creates no Series. Its `.series` eager-load requirement is tested after `expire_all()` at `test_identity_resolver.py:246–253`; that is an acceptable placement of AC-C6-8’s intended regression.

### C7 — NON-BLOCKING: one scraper, with necessary no-ID support

`backend/src/module/mikan/parser.py:82–112` owns title/poster extraction and the ID-bearing page result. `backend/src/module/domain/parser/title_parser.py:131–161` owns fetch, caching, and URL construction; the moved `MikanParserResult` at `:27–33` preserves caller-facing fields. The positive-ID guard is present. The old scraper and dead tuple facade are removed. Fixture tests check the accepted title fix, poster cache call, and zero-ID handling (`backend/src/tests/test_domain/test_parser/test_title_parser.py:55–81`). The extra extraction helper is justified by the deletion experiment below, despite the design’s original “parser.py untouched” wording.

### C8 — BLOCKING: required all-extension acceptance test omitted

The shared tuples at `backend/src/module/domain/value_objects.py:125–136` match the deleted tuples. Renamer classifiers reuse them (`backend/src/module/services/renamer.py:823–830`), as does PikPak (`backend/src/module/services/downloader/pikpak.py:21`, `:44`). These concepts serve C8; no classification change was found.

However, AC-C8-1 explicitly requires a public `rename_all` regression containing every media/subtitle extension (`design.md:625`). The changed renamer tests add only the subtitle-error case (`backend/src/tests/test_services/test_renamer.py:882–953`); the ordinary success test at `:712–749` checks one file. No all-extension public-path equivalent exists in the inspected suites. Identical tuple contents and general suite passes do not fulfill this approved acceptance criterion. Add the required behavior test; keep the Pydantic suffix patterns parked as approved.

### C9 — NON-BLOCKING: one lock guard, unchanged busy responses

`backend/src/module/concurrency/rename_lock.py:32–44` introduces `rename_lock_guard`, owning only acquisition and conditional release. Both endpoints retain their distinct English 409 text (`backend/src/module/api/v1/bangumi.py:188–199`, `:738–749`), and the contract tests assert it (`backend/src/tests/test_api_contract/test_bangumi.py:381`, `:922`). Construction now happens inside the retrigger guard, satisfying release-on-exception rather than leaking the acquired lock. The scheduler’s existing acquisition interface is unchanged.

### C10 — NON-BLOCKING: repository owns download eligibility and exclusion checks

`backend/src/module/repositories/torrent.py:272–300` adds `get_downloadable` and `is_excluded`, serving the three approved cross-layer callers. The query retains every previous URL, lifecycle, downloaded-state, and EXCLUDED condition. Manual download preserves its excluded-torrent 400 (`backend/src/module/api/v1/bangumi.py:565–571`); backfill preserves its existing-row skip (`backend/src/module/services/rss_engine.py:260–265`). Repository and scheduler tests exercise exclusion (`backend/src/tests/test_repositories/test_torrent.py:962–982`; `backend/src/tests/test_scheduler/test_rss_refresh.py:505–542`). Synchronous stubs in API-contract mocks are necessary because their AsyncMock repository would otherwise make this predicate truthy.

### C11 — NON-BLOCKING: pending response reuses the view without expanding its shape

`backend/src/module/api/v1/rss.py:729–748` calls the C2 view and keeps its explicit response dictionary. Missing-Series title/year/poster remain `None`, season remains 1, and year stays numeric. The added test checks concrete values and filter-list conversion (`backend/src/tests/test_api_contract/test_rss.py:817–855`). No extra production concept is introduced; this is reuse of C2.

## Host deviations: dispositions

1. **Accept C7’s title/poster helper.** It preserves output without an ID pair and shares extraction with `parse_mikan_page`. Deleting it fails the independent experiment below.

2. **Reject skipping C8’s extension test.** AC-C8-1 was explicit; general coverage and byte-identical tuples do not authorize removing it.

3. **Accept C6 requiring both IDs.** This preserves the existing subgroup-less subscribe fallback; add-RSS retains its title check when subgroup ID is absent. No unrequested subgroup-zero conflict rule is added.

4. **Accept storing subgroup ID on new add-RSS rows as necessary, but insufficient.** It enables the approved host-alias check for new rows; the reproduced upgrade case still requires repair.

5. **Reject skipping C6’s second-season endpoint test.** A different ID crosses Series resolution/creation, while another subgroup reuses the same Series. They are not interchangeable acceptance evidence.

6. **Accept C10’s mock predicate stubs.** The production predicate is synchronous; the test repository must model that.

7. **Accept the parked display-field copies.** OD-C2-4 explicitly limits this pass.

## Deletion, combination, and reuse attempt

I attempted to delete `parse_mikan_title_and_poster` and make the facade reuse only `parse_mikan_page`. A synthetic page with `<p class="bangumi-title">`, a `/Home/Bangumi/100` title link, and a poster, but no subgroup pair, gives `parse_mikan_page(...) == None`. The extraction helper still returns **“Show A” and `/images/a.jpg`**, matching the old scraper’s supported output. Removing it would lose both values. This smaller alternative fails behavior preservation, so I rejected it.

I also examined reusing the unrenamed-torrent query for downloads. Its eligibility conditions (`backend/src/module/repositories/torrent.py:248–265`) concern rename status, not downloaded status, valid URLs, or pending-review ownership. Combining those rules would change behavior or introduce flags. The implementation already avoids C3’s proposed result class and combines C2/C11. No unnecessary production abstraction or dependency requiring a minimality block was found; the C6 repair can remain inside the existing shared rule.

## Invariants and records

- **EXCLUDED:** eligibility, manual-download guards, backfill skips, and rename-visible queries remain exclusion-aware (`repositories/torrent.py:223–300`; `services/renamer.py:301`). No changed path exposes or downloads a sentinel.

- **Selection and adapters:** exclusion regex behavior and A-001’s retained selection code are unchanged by source comparison. PikPak function bodies, DownloaderProtocol, and RenameOutcome are unchanged.

- **API and scope:** C4/C7’s disclosed changes and the new-row C6 behavior follow accepted decisions. C6’s old-row duplicate relaxation does not. No unrelated dependency, schema, migration, or frontend work was added.

- **Records — NON-BLOCKING closeout follow-up:** `.agentflow/devlog.md:7–17` still reports design-only state and no implementation tests; its A-004 Ask is empty at `:306–308`, and `tracker.md:29–53` remains unchecked. The coordinator should capture the supplied approval, implementation route, test evidence, and this blocked review before claiming completion. This does not require re-requesting owner permission or pretending the task is complete.

Outcome: BLOCKING
Minimality: PASS
Conformance: BLOCKING
Verdict: BLOCKING
Self-check: reviewed the pinned base and target directly; covered C1–C11 and all seven deviations; reproduced the C6 upgrade failure and attempted a deletion; reused coordinator suites; ran no Agentflow, delegation, or network calls; wrote only review-report.md.
