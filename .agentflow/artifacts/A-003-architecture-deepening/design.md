* _2026-10-05 11:47:36 +0800 (claude-opus-5-5/medium)_

# A-003 design: fix all 11 architecture deepening candidates

## Summary

- **Result:** one design for all 11 candidates (C1-C11) from the 2026-10-05 architecture report. Ten are behavior-preserving. Two (C4 TMDB error handling, C6 add_rss duplicate rule) and one parser fix (C7 title) change observable behavior on purpose; each has an owner decision with a suggested default.

- **Risk:** the edits touch the hottest files (rss_engine.py, api/v1/bangumi.py, api/v1/rss.py, renamer.py). Order and file overlap are fixed below so each step stays small.

- **Next action:** owner gives `Design Go` on this design commit, and answers or accepts the owner decisions in the table below. Silence on a decision does not approve it.

## Original Ask and authority

- Owner: `/improve-codebase-architecture` produced an 11-candidate report; owner replied "全部都修正 交給你了" (fix all of them; I leave it to you).

- This covers: C1 delete dead RSSEngine ingest path; C2 Bangumi effective display view; C3 one rename decision tree; C4 PosterService owns poster refresh; C5 transport-only RequestContent; C6 one already-subscribed rule; C7 one Mikan page parser; C8 one extension list; C9 one rename-lock helper; C10 EXCLUDED rule in the repository; C11 pending list reuses the view.

- Not covered (parked as proposals, see each group): rss_engine.py and repositories/bangumi.py display-view sites (OD-C2-4), EpisodeFile/SubtitleFile regex patterns (OD-C8-1), subscribe_batch dedup, error_type fields on the add_rss 409 (OD-C6-2).

## Owner decisions (answer each `ans:`; empty means the suggested default is NOT yet approved)

- **OD-C10-1** (G1-rss-ingest): Accept TorrentRepository.get_downloadable() and TorrentRepository.is_excluded() as the new method names?

  - Suggested default: Yes, accept as-is (matches the candidate's own suggested name 'downloadable query'); rename only on naming-convention objection.

  - ans:

- **OD-C10-2** (G1-rss-ingest): api/v1/bangumi.py's download_torrent 400-for-excluded branch has no existing test coverage (API-contract or e2e). Add one now, or leave covered only indirectly via the new TorrentRepository.is_excluded unit test?

  - Suggested default: Leave covered indirectly via the repository-level is_excluded test for this candidate; file the missing e2e/API-contract coverage as a separate follow-up if the owner wants that gap closed.

  - ans:

- **OD-C2-1** (G2-display-view): effective_save_path: drop the redundant `series.root_path` truthiness guard present in 4 of 6 current call sites (models/bangumi.py, collector.py, bangumi_merge.py, rss_refresh.py) so all 6 sites share one check (`series is not None`), matching renamer.py/api/v1/bangumi.py's 2 sites? This is unreachable today since Series.root_path is NOT NULL and always non-empty by construction (_derive_root_path).

  - Suggested default: Accept — unify on `series is not None`, document the root_path-non-empty invariant with a one-line comment in bangumi_view.py.

  - ans:

- **OD-C2-2** (G2-display-view): Delete api/v1/rss.py:_sqlmodel_to_domain_bangumi now (confirmed zero callers, stale docstring referencing properties that no longer exist at all) rather than leaving it for a separate dead-code ticket?

  - Suggested default: Delete now — same file is already being touched for C11, zero behavior risk (no callers).

  - ans:

- **OD-C2-3** (G2-display-view): Also migrate 4 inline duplicates in api/v1/bangumi.py found during investigation but not named by the original review (lines ~213-215, ~469, ~516, and ~67 found by review issue #1 — same series-or-default pattern)?

  - Suggested default: Include them — same fix, same already-edited file, avoids leaving an obviously-identical pattern half converted next to the migrated ones.

  - ans:

- **OD-C2-4** (G2-display-view): rss_engine.py (9 sites) and repositories/bangumi.py:214 (1 site) have the identical duplicated idiom but are not in this pass's files_to_change, which makes AC-C2-4's original repo-wide grep false. Pull them into this pass's scope, or park them as a named follow-up and narrow AC-C2-4 to the files actually touched here?

  - Suggested default: Park — rss_engine.py is the busiest file in the RSS pipeline and a likely collision point with sibling architecture-review groups; pulling in 10 more call sites nearly doubles this ticket's diff for a pure dedup with no behavior fix riding on it. Narrow AC-C2-4 to the 8 files in files_to_change and file a follow-up ticket for rss_engine.py + repositories/bangumi.py.

  - ans:

- **OD-C3-1** (G3-rename): Should the scheduler path (rename_all) also retry subtitle renames when the primary rename failed (pass retry_subtitles_without_success=True), matching rename_bangumi's retrigger behavior?

  - Suggested default: No — keep rename_all passing False (current behavior unchanged); no ticket or test asks for scheduler-side subtitle retry.

  - ans:

- **OD-C8-1** (G3-rename): Should EpisodeFile.suffix / SubtitleFile.suffix Pydantic Field(pattern=...) regex strings also be generated from the shared MEDIA_EXTENSIONS/SUBTITLE_EXTENSIONS tuples, closing the third copy of the extension list?

  - Suggested default: No — leave the two Field patterns as literal regex strings; touching Pydantic validation on EpisodeFile/SubtitleFile is a larger blast radius than this behavior-preserving pass authorizes. File as a follow-up if wanted.

  - ans:

- **OD-C7-1** (G4-poster-mikan): Keep TitleParser.mikan_parser_with_rss name/shape as the facade, or literally delete the name per the candidate's wording and have all 6 call sites call parse_mikan_page + a new combinator directly?

  - Suggested default: Keep the facade name/shape; only its scraping internals are deleted/replaced by parse_mikan_page. Avoids churn in rss/analyser.py, rss_engine.py, and 3 test files for zero behavior gain.

  - ans:

- **OD-C7-2** (G4-poster-mikan): Adopt parse_mikan_page's title extraction (fixes a real div.bangumi-title bug) or preserve the old, currently-broken-on-real-pages empty-title result for byte compatibility?

  - Suggested default: Adopt the fix - strictly more correct, and every caller already treats an empty title as a no-op.

  - ans:

- **OD-C7-3** (G4-poster-mikan): Build season_rss_link from (mikan_bangumi_id, mikan_subgroup_id) via build_season_rss_url, or port the old 4-tier HTML scrape verbatim?

  - Suggested default: Use build_season_rss_url - identical output on every known fixture, more robust, deletes ~90 lines instead of duplicating them.

  - ans:

- **OD-C7-4** (G4-poster-mikan): Delete the dead TitleParser.mikan_parser tuple method (zero callers) or keep it unused?

  - Suggested default: Delete it - no behavior change, no caller anywhere.

  - ans:

- **OD-C4-1** (G4-poster-mikan): Use update_simple (matches today's router behavior) or update(expected_version=...) (today's dead PosterService behavior) for the DB write?

  - Suggested default: update_simple - preserves current behavior exactly, avoids introducing a new ConcurrentModificationError failure mode.

  - ans:

- **OD-C4-2** (G4-poster-mikan): Delete PosterService.refresh_all_posters() (unused, narrower/different rule) or keep it unused?

  - Suggested default: Delete it and its tests - nothing calls it; keeping it means keeping a second refresh rule, which the candidate says to stop doing.

  - ans:

- **OD-C4-3** (G4-poster-mikan): Should the batch endpoint switch from bangumi_repo.get_all() to PosterService's old get_active()?

  - Suggested default: No - keep get_all() so the set of bangumi considered for refresh does not silently change.

  - ans:

- **OD-C4-4** (G4-poster-mikan): Accept that a TMDB-lookup exception now gets caught and logged (batch loop continues; by-id endpoint returns 200 instead of 500), instead of today's uncaught-exception/abort behavior?

  - Suggested default: Accept it - strictly more robust for a best-effort refresh endpoint, and no existing test asserts a 500 on TMDB failure for either endpoint.

  - ans:

- **OD-C6-1** (G5-subscription): add_rss currently blocks ANY non-aggregate submission whose official_title text matches an existing Series, regardless of season or fansub group. The fix replaces this, for Mikan-sourced submissions only, with the same series+mikan_subgroup identity rule subscribe_season already uses. Net effect, re-verified this run and now covering FOUR changes, not three: (a) a second season of the same show is now allowed, (b) a second fansub group for the same show+season is now allowed, (c) two unrelated Mikan shows that happen to share identical title text are now allowed, and (d) NEW -- a Mikan request carrying an official_title override that today silently succeeds against a differently-worded duplicate URL (same bangumiId+subgroupid, different host/text, so neither the skipped title check nor the text-based find_by_any_rss_link fires) now gets a 409 instead. Non-Mikan submissions are unaffected. Accept all four as the intended effect of switching add_rss's Mikan-sourced duplicate rule from text-based to identity-based?

  - Suggested default: Yes -- adopt all four. (a) and (b) are the explicit goal of this candidate (today a user can already do both via POST /subscribe; add_rss just had a stricter, inconsistent guard). (c) and (d) are both narrow and symmetric consequences of the same switch from text identity to show identity: the webui never exercises this code path today (see Verified facts, apiRSS.add always passes skip_bangumi=true), so no live user journey changes either way; (d) is a strictly safer direction (catching a real duplicate the old text check missed) and is now covered by a dedicated test (AC-C6-7) asserting the 409 body content, not just the status code.

  - ans:

- **OD-C6-2** (G5-subscription): The new 409 for a Mikan identity conflict in add_rss -- should it add `error_type`/`existing_bangumi` fields (matching the shape webui/src/components/ab-add-rss.vue's DuplicateError type already declares but which add_rss has never actually sent), or keep the bare {status, status_code, msg_en, msg_zh} shape used today?

  - Suggested default: Keep the bare shape (no behavior/contract change). Nothing reads `error_type`/`existing_bangumi` today -- the webui's add-RSS dialog always calls POST /rss/add with skip_bangumi=true (webui/src/components/ab-add-rss.vue:195), so it never reaches this code path at all. Adding those fields now would be speculative; add them later only if a caller is wired to use them.

  - ans:

## Order of work

1. C1 (delete dead code) first. It removes most of rss_engine.py and its dead tests, so later steps read less code.

2. C8, then C3 (renamer.py, disjoint regions), then C9 (api/v1/bangumi.py rename lock).

3. C7, then C4 (C4 uses the C7 parser result).

4. C2, then C11 (C11 imports the C2 view). Keep diffs to the named functions.

5. C5 and C10 (independent files; C10's rss_engine.py edit is inside the kept download_bangumi).

6. C6 last (largest behavior decision).

- One commit per candidate, each with its tests, so any one can be reverted alone.

## Normal journey

1. Before each candidate, run its focused tests on the old code and record the baseline count.

2. For a behavior change (C4 OD-C4-4, C6, C7 OD-C7-2), first add a failing test that shows the new behavior, then change the code.

3. For a pure refactor, add only interface-level tests that the design names, and keep them green before and after.

4. After all 11, run the backend suites once: `cd backend && uv run python -m pytest src/tests/test_repositories/ src/tests/test_domain/ src/tests/test_services/ src/tests/test_api_contract/ src/tests/test_scheduler/ src/tests/test_e2e/ -q`, compare with the A-001 baseline (two known baseline E2E failures), then send the final commit to an independent read-only reviewer.

5. No real PikPak, qBittorrent or Mikan network calls; no WebUI, schema, or migration change.

## Invariants

- INV-1: EXCLUDED sentinel torrents never appear in user-visible queries or the rename pipeline. Start: true at HEAD a348c193. Failure: any visible/downloadable query returns a row with state EXCLUDED.

- INV-2: the A-001 shared RSS selection rule and the PikPak task interpretation do not change. Failure: test_rss_engine.py TestDownloadBangumi or test_pikpak.py changes result.

- INV-3: DownloaderProtocol and RenameOutcome (OK / CONFLICT / ERROR) do not change. Failure: any adapter signature change in the diff.

- INV-4: API response bodies and status codes stay the same, except the cases named in an accepted owner decision. Failure: an API contract test changes without a matching decision.

- INV-5: no new dependency, schema change, or migration. Failure: pyproject.toml, alembic, or ORM column change in the diff.

- Per-candidate invariants are listed as INV-C<n>-<k> in each group below.

## Acceptance criteria

- AC-1 (INV-1..5): every per-candidate AC-C<n>-<k> below passes, with the exact test named there.

- AC-2: the combined backend suite has no new failure compared with the A-001 baseline (focused184, core1475 passed/2 skipped/2 xfailed, offline E2E142 passed/1 skipped/2 known failures).

- AC-3: an independent reviewer returns Outcome, Minimality and Conformance PASS on the final implementation commit.

## Minimality check

- **Smallest outcome:** each candidate removes one duplicated rule or dead path, and adds at most one module or method (C2 bangumi_view.py; C9 one rename-lock helper; C10 one or two repository methods; C6 one lookup-only identity call).

- **Simpler alternative considered:** fix only the drift bugs (C3 subtitle guard, C7 title) and leave the copies. Rejected: the owner asked to fix all candidates, and the copies are the cause of the drift.

- **Larger alternative rejected:** merging add/subscribe/activation transactions (A-001 rejected), ORM @property shims (removed on purpose in Plan 05), a hybrid_property for EXCLUDED, changing DownloaderProtocol.

- Each group below has its own Minimality check per candidate.

## Group designs

The sections below come from five read-only design agents. A separate reviewer checked each against the code; four groups were revised to fix the reviewer's issues (notes inline).

## Group G1-rss-ingest — verified design

All line numbers below are from the current on-disk files (re-read during this investigation), not the architecture-review estimates. Baseline run before any edit: `cd backend && uv run python -m pytest src/tests/test_services/test_rss_engine.py src/tests/test_services/test_request_contents.py src/tests/test_e2e/test_rss_analysis.py src/tests/test_e2e/test_known_issues.py src/tests/test_scheduler/test_rss_refresh.py -q` → **88 passed**. This is the green baseline all candidates must stay green against (plus new tests added below).

---

### C1 · Delete the superseded RSSEngine ingest path

**Outcome:** `backend/src/module/services/rss_engine.py` keeps only the methods the live path (`scheduler/jobs/rss_refresh.py:run_refresh_once` → `RssPipeline`) actually calls. The old incremental auto-create/refresh loop (superseded by `RssPipeline` + `MikanResolver`) is removed, along with the tests that only exercised it.

**Verified facts (re-checked now):**
- Live ingest path: `rss_refresh_job` → `run_refresh_once` (`scheduler/jobs/rss_refresh.py:342`) calls `RSSEngine.parse_rss_feed` (line 392) and `RssPipeline.run_for_feed` (line 441), then `_run_eps_completion` calls `RSSEngine.download_bangumi` (line 288), then `_trigger_downloads` (line 465).
- `RSSEngine.match_torrent_to_bangumi` (rss_engine.py:209-232), `_build_bangumi_from_mikan` (243-301), `_enqueue_pending_enrichment` (304-334), `_auto_create_bangumi` (337-577), `refresh_rss` (580-793), `refresh_all_rss` (796-805), `create_bangumi_from_torrent` (808-954) have **zero callers** outside this file and its own test module (`grep -rn` over `backend/src`, confirmed). `api/v1/rss.py:439`'s endpoint is also named `refresh_rss` but it calls `scheduler.jobs.rss_refresh.run_refresh_once`, not `RSSEngine.refresh_rss` — coincidental name collision, not a caller.
- Orphaned module-level helpers once the above are deleted (no remaining caller): `_FILTERED` (line 29), `_extract_season_from_title` (32-49, only called from `_build_bangumi_from_mikan`), `_extract_mikan_bangumi_id` (52-56, only called from `_is_cross_season`), `_is_cross_season` (59-66, only called from `refresh_rss`), `_match_torrent_in_list` (69-80, only called from `refresh_rss`).
- Imports that become unused after deletion: `from typing import Optional` (only used inside deleted signatures), `TitleParser`, `BangumiParsingError`, `Bangumi as BangumiSchema`, `build_canonical_bangumi_url`, `resolve_series_for_rss`. **Must keep**: `asyncio`, `re`, `AsyncSession`, `settings`, `Bangumi` (still used in `_record_pending_candidate`'s type hint), `Torrent`, `gen_save_path`, `extract_mikan_ids_from_rss` (still used in `collect_pending_candidates_from_source`, line 149), `BangumiRepository`, `RSSRepository`, `TorrentRepository`, `DownloaderProtocol`, `RequestContent`.
- `TestMatchTorrentToBangumi` (test_rss_engine.py:321-427), `TestRefreshRSS` (428-809), `TestRefreshAllRSS` (810-879), `TestCreateBangumiFromTorrent` (880-1146), `TestAggregateRefreshRollbackSafety` (1492-end) exercise only the deleted methods — confirmed by reading each class; none reach the live `RssPipeline`/`finalize_resolved_item` path. `TestAggregateRefreshRollbackSafety` guards an FK-rollback hazard specific to the deleted incremental-commit dance; the live pipeline commits bangumi+torrent together per item (`rss_pipeline.py:114`) before `_run_eps_completion` ever runs, so the hazard doesn't exist there — nothing to port.
- `TestParseRSSFeed` (85-135), `TestCollectPendingCandidatesFromSource` (136-320), `TestDownloadBangumi` (1147-1491) exercise kept, live-reachable methods — keep unchanged.
- `tests/test_e2e/test_known_issues.py:27-45` (`TestIssue1And2And15_YearMissing`) and the `TestIssue4_UndownloadedNeverRetried` / `TestIssue12_SubscribeRefreshRace` docstrings (lines ~96, ~340, ~357) drive the real HTTP endpoint `POST /api/v1/rss/refresh/{id}` (live path), but their comments say "via `_auto_create_bangumi`" / "`rss_engine.py refresh_rss`" — stale, since that's dead code now. Checked the live equivalent (`RssPipeline`/`finalize_resolved_item`) has no `year` field either, so the documented bug still reproduces through the live path; only the comment's code reference is wrong.

**Exact change:**
- Delete from `backend/src/module/services/rss_engine.py`: lines 29 (`_FILTERED`), 32-80 (`_extract_season_from_title`, `_extract_mikan_bangumi_id`, `_is_cross_season`, `_match_torrent_in_list`), 209-232 (`match_torrent_to_bangumi`), 243-334 (`_build_bangumi_from_mikan`, `_enqueue_pending_enrichment`), 337-793 (`_auto_create_bangumi`, `refresh_rss`), 796-954 (`refresh_all_rss`, `create_bangumi_from_torrent`). Trim the now-unused imports listed above.
- Keep unchanged: `_record_pending_candidate`, `collect_pending_candidates_from_source`, `parse_rss_feed`, `torrent_excluded_by_filter`, `download_bangumi`.
- Delete test classes `TestMatchTorrentToBangumi`, `TestRefreshRSS`, `TestRefreshAllRSS`, `TestCreateBangumiFromTorrent`, `TestAggregateRefreshRollbackSafety` from `tests/test_services/test_rss_engine.py`. Keep `TestParseRSSFeed`, `TestCollectPendingCandidatesFromSource`, `TestDownloadBangumi`.
- In `tests/test_e2e/test_known_issues.py`, rewrite the stale code references only (no assertion changes): `TestIssue1And2And15_YearMissing` docstring → "the live RSS pipeline (`services/pipeline/rss_pipeline.py:finalize_resolved_item`) never sets `year` on auto-created bangumi"; `TestIssue4_UndownloadedNeverRetried` docstring → reference `scheduler/jobs/rss_refresh.py:_trigger_downloads`/`RssPipeline` instead of `rss_engine.py refresh_rss`; `TestIssue12_SubscribeRefreshRace` inline comment likewise. Also update the mirrored docstring note in `module/rss/analyser.py:82` ("See services/rss_engine._build_pending_bangumi_from_mikan") if it still points at a deleted symbol — correct to point at `_pending_bangumi_from_mikan` in the same file or drop the cross-reference.

**Behavior change:** none. Everything deleted is unreachable from any running code path (API, scheduler, scripts, webui). Comment edits do not change test bodies or assertions.

**Invariants:**
- INV-C1-1: start — `run_refresh_once`/`RssPipeline` is the only live ingest path. preserved — after deletion, `grep -rn "RSSEngine\."` across `module/` still resolves only to `parse_rss_feed`, `download_bangumi`, `collect_pending_candidates_from_source`, `torrent_excluded_by_filter`, `_record_pending_candidate`. failure — any new grep hit on a deleted symbol name means something still depended on it and deletion was wrong.
- INV-C1-2: start — full backend test suite is green before the change. preserved — it stays green after (dead code removal changes no runtime behavior). failure — any test outside the deleted classes fails after deletion (signals a hidden caller that was missed).

**Acceptance criteria:**
- AC-C1-1: `grep -rn "match_torrent_to_bangumi\|_build_bangumi_from_mikan\|_enqueue_pending_enrichment\|_auto_create_bangumi\|refresh_rss\|refresh_all_rss\|create_bangumi_from_torrent" backend/src/module` returns nothing. Verify by running that grep.
- AC-C1-2: `cd backend && uv run python -m pytest src/tests/test_services/test_rss_engine.py -q` passes (now only `TestParseRSSFeed`, `TestCollectPendingCandidatesFromSource`, `TestDownloadBangumi`).
- AC-C1-3: `cd backend && uv run python -m pytest src/tests/test_e2e/ -q` still shows the same pass/xfail count as today's baseline (144 passed + 1 xfailed per CLAUDE.md), proving `TestIssue1And2And15_YearMissing` etc. still exercise the live bug through the HTTP endpoint after the comment edit.
- AC-C1-4: `cd backend && uv run ruff check src/module/services/rss_engine.py` (or equivalent lint) reports no unused-import warnings for the trimmed import block.

**Minimality check:** Smallest outcome is literally "delete the dead subtree, including its orphaned private helpers and now-unused imports, and the tests that only drove it." No simpler alternative (e.g. leaving the dead code as-is) satisfies the owner's authorization to fix this candidate. Nothing new is introduced — pure deletion.

**Owner decisions:** None — this is pure dead-code removal with no behavior change and no ambiguity in scope.

---

### C5 · Make `network/request_contents.py` transport-only

**Outcome:** `RequestContent.get_torrents_with_filter` stops importing/using `TitleParser`/`BangumiParsingError` and stops doing title_raw substring matching. That matching logic moves to `RSSAnalyser` (its sole caller), which already inherits `TitleParser` and already imports `BangumiParsingError` — zero new imports needed there.

**Verified facts (re-checked now):**
- `RequestContent.get_torrents_with_filter` is `network/request_contents.py:70-144`. Its only caller anywhere in the repo is `RSSAnalyser.analyse_torrents` (`module/rss/analyser.py:303-313`), which is reached only by `POST /api/v1/rss/analysis/torrents` (`api/v1/rss.py:616`) and `AsyncRSSAnalyserAdapter.analyse_torrents` (`services/search_adapter.py:114-128`, used by the search feature). Confirmed via repo-wide grep.
- Inside `get_torrents_with_filter`, lines 92-119: lazy-imports `BangumiParsingError`/`TitleParser`, instantiates a parser, calls `raw_parser(_title)`, and does the substring match `title_raw not in parsed.title_raw and parsed.title_raw not in title_raw`. This is business/domain logic (title parsing), not transport.
- `RSSAnalyser` (`module/rss/analyser.py:59`) already subclasses `TitleParser` and already has `from module.domain.value_objects import BangumiParsingError, ResponseModel` at the top of the file (line 7) — the exact pieces needed are already present with no new import.
- `tests/test_e2e/conftest.py:118-167` has a hand-written `MockRequestContent.get_torrents_with_filter` that duplicates the *same* title_raw/TitleParser logic, and per CLAUDE.md's "RequestContent patching in tests" note it is patched into `module.rss.analyser.RequestContent` (conftest.py:302) among others — this fake must be kept in sync with the real transport method's shape or the e2e tests silently drift.
- `tests/test_services/test_request_contents.py:158-190` (`TestGetTorrentsWithFilter`) never exercises `title_raw` — safe to drop the parameter from the real method without touching this test file.
- No test anywhere exercises `title_raw` filtering through the real, unmocked `get_torrents_with_filter`/`analyse_torrents` path: `test_api_contract/test_download.py:100` and `test_services/test_search_adapter.py` both mock `analyse_torrents` itself, bypassing the real matching logic entirely, and the one e2e test that hits `POST /rss/analysis/torrents` (`test_e2e/test_rss_analysis.py:65-103`) never passes `title_raw`. This is a genuine coverage gap — a baseline test is needed before moving the logic (see below).

**Exact change:**
- `network/request_contents.py`: remove the `title_raw` parameter and lines 92-119's matching block from `get_torrents_with_filter`. The method keeps: XML fetch, `_get_filter`, the `filtered` bool computation, hash extraction, dict assembly. `RequestContent.get_torrents` is untouched.
- `module/rss/analyser.py`: add a small private method, e.g. `_filter_by_title_raw(self, torrents: list[dict], title_raw: str) -> list[dict]`, holding exactly the moved logic (try `self.raw_parser(t["name"])`, catch `BangumiParsingError` → skip, substring-match `parsed.title_raw` against `title_raw`). `analyse_torrents` becomes:
  ```python
  def analyse_torrents(self, rss, _filter=None, title_raw=None):
      with RequestContent() as req:
          torrents = req.get_torrents_with_filter(rss.url, _filter)
      if title_raw:
          torrents = self._filter_by_title_raw(torrents, title_raw)
      return torrents
  ```
- `tests/test_e2e/conftest.py`: trim `MockRequestContent.get_torrents_with_filter` (118-167) to drop the `title_raw` param and the duplicated TitleParser block, mirroring the real transport-only method, so the fake and the real implementation stay symmetric (this is the exact failure mode CLAUDE.md's "RequestContent is patched in tests in ALL consuming modules" note warns about).
- New test file `backend/src/tests/test_services/test_rss_analyser.py`: add a baseline test exercising `RSSAnalyser.analyse_torrents(rss, title_raw=...)` end-to-end against a real/fixture RSS feed (no mocking of `analyse_torrents` itself), asserting the title_raw substring-match behavior. Run it first against the **old** code (logic still in `RequestContent`) to confirm it's green, then keep it green after the move.

**Behavior change:** none observable from `analyse_torrents`'s callers (`api/v1/rss.py:616`, `search_adapter.py`). `get_torrents_with_filter`'s public signature narrows (drops an optional kwarg) but it has exactly one caller, which is updated in the same change.

**Invariants:**
- INV-C5-1: start — `RequestContent` has no dependency on `TitleParser`/`BangumiParsingError`/domain parsing after the move. preserved — `grep -n "TitleParser\|BangumiParsingError" backend/src/module/network/request_contents.py` returns nothing. failure — a future PR re-adds a domain import to the network module.
- INV-C5-2: start — `POST /api/v1/rss/analysis/torrents?title_raw=X` returns the same filtered list it did before the move, for the same fixture feed. preserved — the new `test_rss_analyser.py` baseline test passes unchanged across the refactor. failure — the test's asserted torrent set changes.

**Acceptance criteria:**
- AC-C5-1: `grep -n "title_raw" backend/src/module/network/request_contents.py` returns nothing (new test: none needed, this is a structural check).
- AC-C5-2: new test `tests/test_services/test_rss_analyser.py::test_analyse_torrents_title_raw_matches_substring` (and a sibling `..._skips_unparseable`) — run once against old code (must pass, characterizing current behavior), then again after the move (must still pass).
- AC-C5-3: `cd backend && uv run python -m pytest src/tests/test_services/test_request_contents.py src/tests/test_e2e/test_rss_analysis.py src/tests/test_services/test_search_adapter.py -q` stays green.

**Minimality check:** Smallest fix is moving the already-duplicated logic to the one caller that already has every dependency it needs via inheritance — no new class, no new module, no new dependency. Considered leaving `title_raw` as a pass-through param on `get_torrents_with_filter` that just calls back into an injected matcher — rejected as an unrequested abstraction (a parameterized callback for one caller). The mock fake in conftest.py must shrink too, or it stops mirroring the real method and the "patch in ALL consuming modules" trap C LAUDE.md calls out would reappear in reverse (fake does more than the real thing).

**Owner decisions:** None — the move has one caller, one clean destination, and no ambiguity.

---

### C10 · Route cross-layer EXCLUDED checks through TorrentRepository

**Outcome:** The three sites that hand-roll the `TorrentState.EXCLUDED` check move onto `TorrentRepository`, mirroring the pattern the repository already uses for every other EXCLUDED-aware query (`get_visible_by_bangumi`, `get_visible_by_rss`, `_unrenamed_base_stmt`, `get_rename_conflicts`, `clear_rename_status`).

**Verified facts (re-checked now):**
1. `scheduler/jobs/rss_refresh.py:_trigger_downloads` (def at line 146; the raw query is lines 160-177): a `select(Torrent).join(Bangumi, ...)` with `Torrent.downloaded == False`, `Torrent.state != TorrentState.EXCLUDED`, `Torrent.bangumi_id.is_not(None)`, `Torrent.url.is_not(None)`/`!= ""`, `Bangumi.active == True`, `Bangumi.deleted == False`, `Bangumi.pending_review == False`. This exact shape (Torrent+Bangumi join, filtered by both EXCLUDED state and bangumi lifecycle) is the one place in the codebase that encodes "is this torrent currently downloadable" — no repository method currently expresses it, though `TorrentRepository._unrenamed_base_stmt` (`repositories/torrent.py:248-266`) is the established precedent for exactly this join/filter pattern for a different purpose (rename eligibility).
2. `api/v1/bangumi.py:631` inside `download_torrent` (endpoint body starts line 620): `if torrent.state == TorrentState.EXCLUDED:` — a single-row boolean guard on an already-fetched `Torrent`, not a query. `TorrentRepository` is already imported and instantiated in this function (`torrent_repo = TorrentRepository(session)`, line 621).
3. `services/rss_engine.py:1062` inside `download_bangumi` (a **kept** method per C1 — `download_bangumi` is not deleted): `existing.downloaded or existing.state == TorrentState.EXCLUDED` — same single-row boolean pattern as #2. `torrent_repo = TorrentRepository(session)` is already in scope in this function too. **C1 does not delete this site** — `download_bangumi` is explicitly kept, so C10 must still fix it here.
4. No `hybrid_property` exists on `Torrent`/`Bangumi` today, and the task forbids introducing one; a plain predicate method on the repository is the right shape, consistent with "no hybrid_property."
5. After the `_trigger_downloads` move, `TorrentState` and `and_` become unused imports in `scheduler/jobs/rss_refresh.py` (verified: `TorrentState` and `and_` are each used only inside the deleted block; `select`, `Torrent`, `Bangumi` are still used elsewhere in the file for `bangumi_stmt`/`_build_feed_item`). After the `api/v1/bangumi.py` fix, `TorrentState` import there (line 22) becomes unused (its only use was line 631). After the `rss_engine.py` fix, `TorrentState` import there (line 12) becomes unused too (Torrent stays needed throughout).
6. Existing test `tests/test_scheduler/test_rss_refresh.py::TestTriggerDownloads::test_skips_torrents_matching_bangumi_filter` (line 440) calls `_trigger_downloads(db_session, downloader)` directly and asserts on which torrent got downloaded — this is a baseline behavior test that must stay green unchanged across the refactor (it exercises the function's public shape, not its internal query). It does **not** currently plant an EXCLUDED-state torrent, so it does not pin that specific branch — a gap directly relevant to this candidate.

**Exact change:**
- `repositories/torrent.py`: add
  ```python
  def _downloadable_base_stmt(self):
      from module.domain.models.bangumi import Bangumi
      return (
          select(Torrent)
          .join(Bangumi, Bangumi.id == Torrent.bangumi_id)
          .where(
              and_(
                  Torrent.downloaded == False,  # noqa: E712
                  Torrent.state != TorrentState.EXCLUDED,
                  Torrent.bangumi_id.is_not(None),
                  Torrent.url.is_not(None),
                  Torrent.url != "",
                  Bangumi.active == True,  # noqa: E712
                  Bangumi.deleted == False,  # noqa: E712
                  Bangumi.pending_review == False,  # noqa: E712
              )
          )
      )

  async def get_downloadable(self) -> list[Torrent]:
      result = await self.session.execute(self._downloadable_base_stmt())
      return list(result.scalars().all())

  @staticmethod
  def is_excluded(torrent: Torrent) -> bool:
      return torrent.state == TorrentState.EXCLUDED
  ```
  (mirrors `_unrenamed_base_stmt`/`get_unrenamed` directly above it).
- `scheduler/jobs/rss_refresh.py:_trigger_downloads`: replace the inline `stmt`/`select`/`and_` block (lines 160-177) with `pending_torrents = await TorrentRepository(session).get_downloadable()`. Drop the now-unused `TorrentState` and `and_` imports.
- `api/v1/bangumi.py:631`: replace `if torrent.state == TorrentState.EXCLUDED:` with `if torrent_repo.is_excluded(torrent):`. Drop the now-unused `TorrentState` import (line 22).
- `services/rss_engine.py:1062`: replace `existing.downloaded or existing.state == TorrentState.EXCLUDED` with `existing.downloaded or torrent_repo.is_excluded(existing)`. Drop `TorrentState` from the `from module.domain.models.torrent import Torrent, TorrentState` import (keep `Torrent`).

**Behavior change:** none. Every query/condition is moved verbatim; `is_excluded`/`get_downloadable` are pure refactors of existing boolean/SQL expressions.

**Invariants:**
- INV-C10-1: start — "a torrent is EXCLUDED" is checked via `Torrent.state == TorrentState.EXCLUDED`/`!= TorrentState.EXCLUDED` at exactly the sites listed. preserved — after the change, every one of those three sites calls `TorrentRepository.is_excluded(...)` or `TorrentRepository.get_downloadable()` instead of comparing the enum inline; `grep -rn "TorrentState.EXCLUDED" backend/src/module` only shows matches inside `repositories/torrent.py`. failure — a new call site elsewhere compares `TorrentState.EXCLUDED` directly instead of using the repository method.
- INV-C10-2: start — `_trigger_downloads` only ever enqueues torrents from active, non-deleted, non-pending-review bangumi, excluding EXCLUDED-state rows. preserved — `get_downloadable()`'s WHERE clause is byte-identical to the deleted inline statement. failure — `test_skips_torrents_matching_bangumi_filter` or the new EXCLUDED-specific test (below) fails.

**Acceptance criteria:**
- AC-C10-1: `grep -rn "TorrentState.EXCLUDED" backend/src/module` shows only `repositories/torrent.py` (the two sites inside `_downloadable_base_stmt`/`is_excluded`, plus the pre-existing ones in `get_visible_by_bangumi`, `get_visible_by_rss`, `_unrenamed_base_stmt`, `get_rename_conflicts`, `clear_rename_status`, `exclude_hashes`).
- AC-C10-2: new test `tests/test_repositories/test_torrent.py::TestGetDownloadable::test_excludes_excluded_state_torrent` — create one PENDING and one EXCLUDED torrent under the same active bangumi, call `TorrentRepository(session).get_downloadable()`, assert only the PENDING one comes back. Add alongside it `TestIsExcluded::test_true_for_excluded_false_for_pending` for the one-line predicate.
- AC-C10-3: extend `tests/test_scheduler/test_rss_refresh.py::TestTriggerDownloads` with `test_skips_excluded_state_torrent` — same shape as the existing `test_skips_torrents_matching_bangumi_filter` (line 440) but with an EXCLUDED-state row instead of a filter-matching name; run once before the refactor (must pass — it's characterizing existing, correct behavior) and again after (must still pass).
- AC-C10-4: `cd backend && uv run python -m pytest src/tests/test_scheduler/test_rss_refresh.py src/tests/test_repositories/test_torrent.py src/tests/test_api_contract/test_bangumi.py src/tests/test_services/test_rss_engine.py::TestDownloadBangumi -q` stays green.

**Minimality check:** Two new one-purpose methods on the repository that already owns every other EXCLUDED-aware query (`get_visible_by_bangumi`/`get_visible_by_rss`/`_unrenamed_base_stmt`), built by copying the existing precedent pattern verbatim — no new class, no hybrid_property (explicitly ruled out by the task), no new file. Considered doing nothing for the two single-row checks (#2, #3) since they're one-liners — rejected because the owner explicitly asked to route *all three* cross-layer sites through named repository methods so the invariant has exactly one encoding to change if it ever stops being a plain enum (e.g. a soft-delete timestamp); a one-line static predicate is the smallest thing that satisfies that ask.

**Owner decisions:**
- OD-C10-1: `get_downloadable()`/`is_excluded()` as the method names (matches the candidate's own suggested name "downloadable query"). Suggested default: accept as-is; rename only if it collides with naming conventions elsewhere.
- OD-C10-2: `api/v1/bangumi.py`'s `download_torrent` 400-for-excluded branch currently has no API-contract or e2e test at all (confirmed by grep — no test asserts "Cannot download an excluded torrent"). Suggested default: cover it indirectly via the new `is_excluded` unit test (AC-C10-2) rather than adding a full e2e test for an untested branch that isn't otherwise part of this candidate's scope; add the e2e test separately if the owner wants that gap closed now.

---

### Cross-candidate notes

**Ordering dependencies:**
- C1 and C10 both touch `services/rss_engine.py`. Apply C1's deletions first (it removes ~900 lines and the `TorrentState`/`Optional`/etc. imports), then apply C10's one-line change inside the now-renumbered `download_bangumi`. Doing C10 first would mean re-finding the line after C1 shifts everything.
- C5 touches `network/request_contents.py`, `rss/analyser.py`, and `tests/test_e2e/conftest.py` only — no file overlap with C1 or C10, can land independently/in parallel.
- C10 touches `scheduler/jobs/rss_refresh.py`, `api/v1/bangumi.py`, `repositories/torrent.py`, and (one line in) `services/rss_engine.py` — no overlap with C5; the `rss_engine.py` overlap with C1 is covered above.
- Within C1, delete the test classes in the same commit/step as the production code deletion (not before, not after) so the tree never has tests referencing already-deleted symbols or production code with no test coverage gap window.

---

# G2-display-view — design (revised)

Scope: C2 (re-deepen the Bangumi effective display view) and C11 (reuse it in `get_pending_bangumi_list`). Read-only investigation done against HEAD `a348c193`; line numbers below are current, not the stale ones in the original review notes.

All 4 reviewer issues were verified against code and are accepted (3 by fixing the design, 1 by adding a named owner decision that narrows scope instead of expanding it). See "Review notes" at the end for the disposition of each.

---

### C2 · One pure-function view module for Bangumi display fields

**Outcome:** One small module, `backend/src/module/domain/bangumi_view.py`, holds `effective_title`, `effective_season`, `effective_year`, `effective_poster`, `effective_save_path`. Every call site that currently repeats "read through `bangumi.series`, else fall back" **in the files this ticket touches** imports and calls these instead of re-deriving it inline. No ORM `@property` is reintroduced (that is exactly what commit 3ea83fc1 / plan Task 11 deliberately removed, to force `.series` eager-loading to be visible at each call site via `AttributeError` — see `docs/superpowers/plans/2026-04-18-05-pipeline-wiring-and-api.md` Task 11). Plain functions preserve that visibility while removing the duplication.

**Why shims were removed (verified):** Task 11 of the plan doc (lines 1188–1259) deleted 5 `@property` shims on the ORM `Bangumi` specifically so every caller surfaces via `AttributeError` and is forced to either read `bangumi.series.X` directly or add `selectinload(Bangumi.series)`. The duplication the review flags is the result of that sweep landing as ad-hoc inline copies instead of one shared helper — the fix is a helper *function* (still forces an explicit, greppable call), not reintroducing the property.

**Verified facts (file:line, re-checked now):**
- `backend/src/module/services/collector.py:25-47` — `_resolve_title`/`_resolve_season`/`_resolve_poster`: duck-typed, handle both ORM `Bangumi` (via `.series`) and the flat Pydantic DTO (`module.models.Bangumi`, via `.official_title`/`.season`/`.poster_link`). Confirmed load-bearing: `api/v1/rss.py:622-627` `download_collection` passes the **Pydantic DTO** (not ORM) into `collect_season`, so the DTO branch is live code, not dead defensiveness.
- `backend/src/module/services/collector.py:186-199` — inline save_path 3-way fallback (`path_override` → `series.root_path`+season if `series_root` truthy → `getattr(bangumi, "save_path", None)` DTO fallback). This 3rd tier only applies to `collect_season`.
- `backend/src/module/services/collector.py:410` (`subscribe_season`) and `:601` (`subscribe_batch`) — inline `bangumi.series.canonical_title if bangumi.series is not None else ""`, ORM-only, used only for a log/dict label, not identity.
- `backend/src/module/models/bangumi.py:20-74` — `_orm_bangumi_to_flat`: ORM→dict flattener invoked only from `_flatten_orm` (`:108-125`) when `model_validate()` sees a real ORM `Bangumi` instance (isinstance check, not duck typing). Title default `""`, poster default `None`, season default `1` (all same semantics as collector's resolvers), **year is cast to `str`**, and save_path has the same 3-tier fallback as collector's but additionally guards `elif series is not None and series.root_path:` (truthiness, not just presence).
- `backend/src/module/api/v1/bangumi.py:37-52` — `_orm_title`/`_bangumi_save_path`: ORM-only (no DTO branch). `_orm_title` default `""` — for an ORM object (no `official_title` attribute) this is **identical** to `_resolve_title`'s result. `_bangumi_save_path` checks `series is None` only (no root_path truthiness) before building the path — differs from `models/bangumi.py`'s extra truthiness guard, matches collector's effective result for all real data (root_path is `NOT NULL`, non-empty by construction, see below).
- `backend/src/module/api/v1/bangumi.py:55-67` **`_poster_needs_refresh`** — `poster = bangumi.series.poster_url if bangumi.series is not None else None` (verified live, line 67). This is the same pattern `effective_poster` replaces. **Missed in the prior pass of this design; added to scope now** (Review issue #1, BLOCKING — accepted).
- `backend/src/module/api/v1/bangumi.py:213-215` (`update_rule`, old season/title), `:469` (`refresh_poster`, `_canonical`), `:516` (`refresh_poster_by_id`, `_bg_canonical`) — three more inline copies of the same `series.X if series is not None else default` pattern, not named in the original review but found during investigation; same file, same fix.
- `backend/src/module/services/renamer.py:360` calls `full_save_path` (`:604-618`, identical logic to `_bangumi_save_path`, no root_path truthiness guard). `renamer.py:533-534`, `:683-684`, `:810-811` — three identical inline `_season`/`_title` blocks in `_rename_single_file`, `_rename_collection`, `_rename_subtitles`. `renamer.py:596-602` `effective_root` (static method) has **zero callers** — pre-existing dead code, out of scope for this ticket (not named in the review, deleting it is a separate, unrelated cleanup).
- `backend/src/module/services/poster.py:94-96` and `:149-150` — identical `_poster`/`_title`/`_season` inline reads.
- `backend/src/module/services/bangumi_merge.py:33-42` `_serialize_bangumi` — same pattern, **but title defaults to `None`** (not `""`) when `series` is `None`, and the save-path fallback keeps the root_path-truthiness guard.
- `backend/src/module/scheduler/jobs/rss_refresh.py:217-224` — same pattern as `bangumi_merge.py` for season/root/save_path (root_path-truthiness guard present), title defaults to `""` here (differs from bangumi_merge's `None`).
- `backend/src/module/api/v1/rss.py:36-71` `_sqlmodel_to_domain_bangumi` — confirmed **zero callers** anywhere in the repo (only its own `def`). Its docstring is stale (talks about "read-only properties on the ORM model", which no longer exist at all — they were deleted, not made read-only). Dead code.
- `backend/src/module/api/v1/rss.py:740-744` `get_pending_bangumi_list` — see C11.
- `backend/src/module/domain/models/series.py:44-51` — `canonical_title`, `root_path` are `NOT NULL` columns; `root_path` is always produced by `_derive_root_path(title)` in `identity_resolver.py` (never empty by construction). This is the fact that makes the "root_path truthiness" divergence between call sites unobservable in practice (see Owner Decision OD-C2-1).
- **Out of scope, confirmed and parked, not migrated this pass** (Review issue #2, MAJOR — accepted via OD-C2-4 below): `backend/src/module/services/rss_engine.py` has 9 more inline copies of the identical series-fallback idiom at lines 74, 220, 694, 735-737, 896, 927-929, 1005, 1077-1079 (title/season/root_path variants — verified live, exact match to the review's citation). `backend/src/module/repositories/bangumi.py:214` (`match_poster`) has one more poster_url variant: `data.series.poster_url if data.series is not None else ""` (verified live).

**Exact change:**
1. New file `backend/src/module/domain/bangumi_view.py` (pure functions, no SQLAlchemy/Pydantic imports needed — plain `getattr` duck typing, same style as collector's existing resolvers):
   - `effective_title(data, default: str | None = "") -> str | None` — `series = getattr(data, "series", None)`; if present, `return series.canonical_title or ""`; else `return getattr(data, "official_title", default) or default`.
   - `effective_season(data) -> int` — same body as current `_resolve_season`.
   - `effective_year(data) -> int | None` — `series` present → `series.year`; else `getattr(data, "year", None)`. Returns the **raw** `Optional[int]`; callers needing the stringified DTO form (`models/bangumi.py` only) do the `str(...)` cast themselves.
   - `effective_poster(data) -> str | None` — same body as current `_resolve_poster`.
   - `effective_save_path(data) -> str | None` — `path_override = getattr(data, "path_override", None)`; if truthy return it; `series = getattr(data, "series", None)`; if present, `return str(PurePosixPath(series.root_path) / f"Season {effective_season(data)}")`; else `return getattr(data, "save_path", None)`.
2. `module/services/collector.py` — delete `_resolve_title`/`_resolve_season`/`_resolve_poster` (:25-47) and the inline save_path block (:186-199); import the 5 functions from `bangumi_view`; replace the 3 call sites (`collect_season`, `subscribe_season`, `subscribe_batch`) and the 2 inline title reads (:410, :601) with `effective_title(...)` etc. `collect_season`'s save path becomes `effective_save_path(bangumi) or gen_save_path(...)` (unchanged outer fallback to `gen_save_path`).
3. `module/models/bangumi.py` — `_orm_bangumi_to_flat` body replaced: `canonical_title`/`season_val`/`poster_val` computed via `effective_title(obj)`/`effective_season(obj)`/`effective_poster(obj)`; `year_val = (lambda y: str(y) if y is not None else None)(effective_year(obj))`; `save_path_val = effective_save_path(obj)`. The isinstance-based ORM-vs-dict detection in `_flatten_orm` (:108-125) is untouched (separate concern).
4. `module/api/v1/bangumi.py` — delete `_orm_title`/`_bangumi_save_path` (:37-52); import `effective_title`/`effective_save_path`/`effective_poster` from `bangumi_view`; update all 10 call sites: `:67` (`_poster_needs_refresh`, `poster = effective_poster(bangumi)` — **added per Review issue #1**), `:85`, `:213-215`, `:268`, `:295`, `:368`, `:436`, `:469`, `:516`, `:661`, `:859`, `:942`.
5. `module/services/renamer.py` — `full_save_path` (:604-618) becomes a one-line delegate to `effective_save_path` (kept as a static method so the public surface/import path for callers and tests is unchanged); the 3 inline `_season`/`_title` blocks (:533-534, :683-684, :810-811) replaced with `effective_season(bangumi)`/`effective_title(bangumi)`. `effective_root` (:596-602) left untouched (dead, out of scope).
6. `module/services/poster.py` — 2 inline blocks (:94-96, :149-150) replaced with calls to `effective_title`/`effective_season`/`effective_poster`.
7. `module/services/bangumi_merge.py` — `_serialize_bangumi` (:33-42): `_title = effective_title(b, default=None)`, `_season = effective_season(b)`, `_save_path = effective_save_path(b)` (the save-path 3rd-tier DTO fallback is a no-op here since `b` is always ORM and ORM has no `save_path` attribute — see OD-C2-1 for the root_path-truthiness note).
8. `module/scheduler/jobs/rss_refresh.py` — lines 217-224 replaced with `effective_title(bangumi)` (default `""`, unchanged), `effective_season(bangumi)`, `effective_save_path(bangumi)`.
9. `module/api/v1/rss.py` — delete dead `_sqlmodel_to_domain_bangumi` (:36-71); see C11 for `get_pending_bangumi_list`.
10. **Not changed this pass, explicitly parked** (OD-C2-4): `module/services/rss_engine.py` (9 sites) and `module/repositories/bangumi.py:214` keep their inline fallback idiom as-is. Not in `files_to_change`.

**Behavior change:** None for the public API/response contracts. One internal, practically-unreachable tightening:
- `effective_save_path` always treats "`series` present" as sufficient to build `root_path/Season N` (no extra `series.root_path` truthiness check). Four of six migrated call sites (`models/bangumi.py`, `collector.py`'s save-path block, `bangumi_merge.py`, `rss_refresh.py`) have that extra guard today; the other two (`renamer.full_save_path`, `api/v1/bangumi._bangumi_save_path`) don't. Since `Series.root_path` is a `NOT NULL` column always populated by `_derive_root_path(title)` (never empty string in any code path that creates a `Series`), this divergence cannot be hit by real data. Documented as OD-C2-1 below instead of silently picking one.
- Dead-code deletions (`_sqlmodel_to_domain_bangumi`, nothing else) have zero callers — not a behavior change by definition.
- `rss_engine.py` and `repositories/bangumi.py:214` are left untouched by this pass (OD-C2-4) — zero behavior change there, by definition, since no code moves.

**Invariants:**
- **INV-C2-1**: Start — any caller holding an ORM `Bangumi` with `.series` loaded (or a flat Pydantic DTO with `official_title`/`season`/`poster_link`/`save_path`). Preserved — `effective_title/season/year/poster/save_path` return the exact same value the inline code at that call site returned before, for every real (non-empty-root_path) input. Failure — any call site's title/season/poster/save_path/year value changes for real data after the migration.
- **INV-C2-2**: Start — a caller needing a non-`""` sentinel (`bangumi_merge.py`, `rss.py`'s `get_pending_bangumi_list`) for a missing series. Preserved — `effective_title(data, default=None)` returns `None`, not `""`, in that case. Failure — `_serialize_bangumi`'s `official_title` field changes from `None` to `""` for a bangumi whose `.series` failed to load.
- **INV-C2-3**: Start — `module/domain/bangumi_view.py` imports nothing from `module.domain.models.*` or `module.models.*`. Preserved — no circular import is introduced (today `module/models/bangumi.py` lazily imports `module.domain.models.bangumi.Bangumi` only for the isinstance check in `_flatten_orm`; that stays a lazy import, unrelated to the new module). Failure — any import cycle at module load time.

**Acceptance criteria:**
- **AC-C2-1**: New `backend/src/tests/test_domain/test_bangumi_view.py` — `test_effective_title_orm_with_series`, `test_effective_title_orm_without_series_default_empty`, `test_effective_title_dto_fallback`, `test_effective_title_custom_default_none` (covers INV-C2-2), `test_effective_season_series_and_dto_and_bare_default`, `test_effective_year_series_and_dto`, `test_effective_poster_series_and_dto`, `test_effective_save_path_path_override_precedence`, `test_effective_save_path_series_root_and_season`, `test_effective_save_path_dto_fallback_when_no_series`. Each asserts the exact return value via `module.domain.bangumi_view` public functions (module interface, not internals).
- **AC-C2-2**: Baseline regression (run once before refactor, once after — must stay green both times, same pass count). Command, with its measured count reconciled (Review issue #4, MINOR — accepted; prior count of 137 silently assumed `test_api_contract/test_rss.py` was folded in without listing it):
  ```
  cd backend && uv run python -m pytest \
    src/tests/test_services/test_collector.py \
    src/tests/test_services/test_renamer.py \
    src/tests/test_services/test_poster.py \
    src/tests/test_services/test_bangumi_merge.py \
    src/tests/test_scheduler/test_rss_refresh.py \
    src/tests/test_api_contract/test_bangumi.py \
    src/tests/test_api_contract/test_rss.py \
    src/tests/test_domain/test_models.py -q
  ```
  Verified now on HEAD `a348c193`: collector+rss_refresh+domain_models = 45; renamer+poster+bangumi_merge+test_api_contract/test_bangumi.py = 101; test_api_contract/test_rss.py = 36. Full command above = 182 passed. Gate is "same count before and after", not the literal number, but the doc must not record a command/count pair that contradicts itself.
- **AC-C2-3**: `grep -rn "_sqlmodel_to_domain_bangumi" backend/src/` returns nothing after deletion.
- **AC-C2-4**: Completeness grep, narrowed to the files actually in `files_to_change` for this pass and extended to all 4 fallback variants (title/season/poster/root_path), fixing Review issues #2 and #3 (MAJOR + MINOR — accepted):
  ```
  grep -rnE 'canonical_title if.*series is not None else|\.season if.*series is not None else|poster_url if.*series is not None else|root_path if.*series is not None else' \
    backend/src/module/services/collector.py \
    backend/src/module/models/bangumi.py \
    backend/src/module/api/v1/bangumi.py \
    backend/src/module/services/renamer.py \
    backend/src/module/services/poster.py \
    backend/src/module/services/bangumi_merge.py \
    backend/src/module/scheduler/jobs/rss_refresh.py \
    backend/src/module/api/v1/rss.py
  ```
  Must return nothing after migration. This intentionally does **not** scan `rss_engine.py` or `repositories/bangumi.py` — those are out of scope per OD-C2-4, not silently "passing" a completeness claim they were never meant to satisfy.

**Minimality check:** Smallest outcome is one new file with 5 one-purpose functions reused by import, no class, no new dependency. Considered and rejected: (a) restoring `@property` shims — explicitly rejected by the prior plan and by this ticket's constraint; (b) one mega "flatten" function returning a dict everywhere (like `_orm_bangumi_to_flat`) — rejected because several call sites (renamer, poster) need only 1-2 of the 5 fields and already have the right ORM type, so building an unused dict is waste; (c) a method on `Series` or `Bangumi` ORM class — rejected, same objection as (a): it would hide the fan-out the plan wanted visible, and `Series`/ORM `Bangumi` must stay DTO-agnostic (the DTO fallback is not a `Series` concern). Each of the 5 functions is needed: title/season/poster/save_path are each duplicated 6+ times; year is duplicated in 2 places but kept for symmetry and because C11 needs it. Expanding scope to `rss_engine.py` (9 sites) and `repositories/bangumi.py` (1 site) was considered and rejected for this pass (OD-C2-4) — it roughly doubles the diff and touches the RSS matching engine, the highest-risk, most contended file in the repo for concurrent architecture-review work, for a purely cosmetic dedup with no behavior fix riding on it.

**Owner decisions:**
- **OD-C2-1**: Unify `effective_save_path` on "series present → build path" (no extra `root_path` truthiness check), dropping the redundant guard that exists today in `models/bangumi.py`, `collector.py`, `bangumi_merge.py`, and `rss_refresh.py` (4 of 6 sites) but not in `renamer.full_save_path`/`api/v1/bangumi._bangumi_save_path` (the other 2). Unreachable today because `Series.root_path` is `NOT NULL` and always non-empty by construction. *Suggested default: accept — add a one-line comment in `bangumi_view.py` stating the `root_path` non-empty invariant it relies on.*
- **OD-C2-2**: Delete `api/v1/rss.py:_sqlmodel_to_domain_bangumi` now (confirmed zero callers, stale docstring referencing properties that no longer exist at all) rather than leaving it "maybe dead" for a future ticket. *Suggested default: delete now — it's in a file already being touched for C11, and leaving confirmed-dead code with a wrong docstring is actively misleading to the next reader.*
- **OD-C2-3**: Also migrate the three inline duplicates found during investigation but not named by the original review (`api/v1/bangumi.py:213-215`, `:469`, `:516`), plus `_poster_needs_refresh` at `:67` found by review issue #1. *Suggested default: include all four — same fix, same already-edited file, zero extra risk, leaves no half-migrated file.*
- **OD-C2-4** (new, resolves Review issue #2): `rss_engine.py` (9 sites) and `repositories/bangumi.py:214` (1 site) have the identical duplicated idiom but are not touched by this pass. Pull them in now, or park them as a named follow-up and keep AC-C2-4's completeness check scoped to the files this ticket actually edits? *Suggested default: park — `rss_engine.py` is the RSS fetch/matching engine, the highest-traffic file for the broader architecture review (other candidate groups are likely editing it), and pulling in 10 more call sites nearly doubles this ticket's diff for a change with no behavior fix attached. AC-C2-4 is narrowed to the 8 files in `files_to_change` (see above) so it stops asserting a repo-wide completeness it doesn't deliver. File a follow-up ticket for `rss_engine.py` + `repositories/bangumi.py` once this group lands, so the dedup doesn't collide with whichever group is mid-edit on `rss_engine.py` right now.*

---

### C11 · `get_pending_bangumi_list` reuses the C2 view functions

**Outcome:** `api/v1/rss.py:get_pending_bangumi_list` stops hand-deriving `official_title`/`year`/`season`/`poster_link` from `bangumi.series` and calls the C2 view functions instead. Response JSON shape, keys, and types are byte-for-byte unchanged.

**Verified facts (file:line, re-checked now):** `backend/src/module/api/v1/rss.py:739-764`:
```python
for bangumi in pending_list:
    _b_series = bangumi.series
    _b_title = _b_series.canonical_title if _b_series is not None else None
    _b_year = _b_series.year if _b_series is not None else None
    _b_season = _b_series.season if _b_series is not None else 1
    _b_poster = _b_series.poster_url if _b_series is not None else None
    bangumi_data.append({
        "id": bangumi.id, "rss_id": bangumi.rss_id,
        "official_title": _b_title, "year": _b_year, "season": _b_season,
        "group_name": bangumi.group_name, "dpi": bangumi.dpi, "source": bangumi.source,
        "subtitle": bangumi.subtitle, "filter": bangumi.filter, "rss_link": bangumi.rss_link,
        "poster_link": _b_poster, "pending_review": bangumi.pending_review,
        "global_filter_matches": ([m.strip() for m in bangumi.global_filter_matches.split(",")]
                                   if bangumi.global_filter_matches else []),
    })
```
`year` is the **raw `int | None`** from `Series.year` (no `str()` cast — differs from `models/bangumi.py`'s DTO, which does cast; must stay raw here). `official_title` defaults to `None` (not `""`) when `.series` is missing — same as `bangumi_merge.py`'s `_serialize_bangumi`, differs from the `""`-default majority.

**Exact change:**
```python
from module.domain.bangumi_view import effective_title, effective_season, effective_year, effective_poster
...
for bangumi in pending_list:
    bangumi_data.append({
        "id": bangumi.id, "rss_id": bangumi.rss_id,
        "official_title": effective_title(bangumi, default=None),
        "year": effective_year(bangumi),
        "season": effective_season(bangumi),
        "group_name": bangumi.group_name, "dpi": bangumi.dpi, "source": bangumi.source,
        "subtitle": bangumi.subtitle, "filter": bangumi.filter, "rss_link": bangumi.rss_link,
        "poster_link": effective_poster(bangumi), "pending_review": bangumi.pending_review,
        "global_filter_matches": ([m.strip() for m in bangumi.global_filter_matches.split(",")]
                                   if bangumi.global_filter_matches else []),
    })
```
`global_filter_matches` CSV→list split, `pending_count`/`active_count` computation, and every other field stay untouched. Do **not** switch to `Bangumi.model_validate(bangumi).model_dump()` — that is the Pydantic DTO (`module/models/bangumi.py`) which has extra fields (`title_raw`, `added`, `save_path`, `torrent_count`, `completed_count`, ...) not in this endpoint's response contract.

**Behavior change:** None — `effective_title(bangumi, default=None)`/`effective_season`/`effective_year`/`effective_poster` reproduce the exact same per-field values for every input (verified field-by-field above: default `None` for title explicitly requested via the `default` param; year stays the raw `int | None`; season/poster already match the shared functions unconditionally).

**Invariants:**
- **INV-C11-1**: Start — a pending bangumi row with `.series` either loaded-and-present or `None`. Preserved — `official_title` is `None` (not `""`) exactly when `.series` is `None`; `year` is a raw `int | None`, never a string. Failure — either field's type or missing-series value changes.
- **INV-C11-2**: Start — response is consumed by the WebUI aggregate-pending screen. Preserved — the response dict's key set and per-key JSON type are identical before/after (no `model_dump()`-style extra keys). Failure — any new/missing/retyped key in the `"bangumi"` list items.

**Acceptance criteria:**
- **AC-C11-1**: Extend `backend/src/tests/test_api_contract/test_rss.py::TestGetAggregatePending` with a new test, e.g. `test_get_aggregate_pending_fields_use_series`, that builds a pending-bangumi mock with a *real* (non-auto-mock) `.series` object (`canonical_title`, `year`, `season`, `poster_url` set to concrete values) and a second mock with `.series = None`, then asserts `data["bangumi"][i]["official_title"]`/`"year"`/`"season"`/`"poster_link"` match exactly — including `official_title is None` and `year` being an `int` (not `str`) for the series-less case. (The existing `test_get_aggregate_pending_success` only asserts key presence, not values — it is not a sufficient regression guard on its own, per the investigation above.)
- **AC-C11-2**: Existing `test_get_aggregate_pending_success` and `test_get_aggregate_pending_not_aggregate` (same file) still pass unchanged.
- **AC-C11-3**: `backend/src/tests/test_e2e/test_rss_subscribe_flow.py` (uses the real `/rss/aggregate/pending/{rss_id}` route end-to-end) still passes unchanged — exercises the route through the real DB/ORM path, not mocks.

**Minimality check:** Smallest outcome is swapping 5 lines of local derivation for 4 function calls in the same loop, keeping every other field and the dict shape untouched. Considered and rejected: using `Bangumi.model_validate(...).model_dump()` — explicitly excluded by the ticket ("do NOT use model_dump which adds fields") and verified correct: the Pydantic DTO has ~10 more fields than this endpoint's contract. Considered and rejected: calling `_orm_bangumi_to_flat(bangumi)` and picking 4 keys out of its dict — works but computes `save_path`/`poster_val`/all direct-column fields needlessly for every pending row; calling the 4 small functions directly is less work and reads the same.

**Owner decisions:** None beyond OD-C2-1..4 above (C11 only consumes the C2 module).

---

## Cross-cutting

**Ordering:** C2 must land first (or in the same commit) — C11's import of `module.domain.bangumi_view` doesn't exist until C2 creates it. Within C2, the new module + collector.py + models/bangumi.py should land together (collector.py's DTO-fallback behavior for `/rss/collect` is the highest-risk path — it's exercised by `test_services/test_collector.py` and should be green before touching the other, lower-risk files).

**File-overlap risk with other groups:** `api/v1/bangumi.py` and `api/v1/rss.py` are large files likely touched by other candidate groups in this architecture review (e.g. anything touching activation/rebuild lifecycle, which this ticket is explicitly barred from re-proposing). Land C2/C11 as a tightly-scoped diff (only the named functions/blocks) to minimize merge conflicts with sibling groups touching the same files. `rss_engine.py` is deliberately excluded from this pass's scope (OD-C2-4) for the same reason, at higher stakes — it is the busiest file in the RSS pipeline.

---

## Review notes

All 4 issues from the prior review were re-verified live against HEAD `a348c193`. None rejected.

- **Issue #1 (BLOCKING, C2 — missed `_poster_needs_refresh` at `api/v1/bangumi.py:67`):** Confirmed by direct read — `poster = bangumi.series.poster_url if bangumi.series is not None else None` is live at that exact line, inside a file already in `files_to_change`. Accepted. Added to step 4's exact-change list and to OD-C2-3's "also migrate" set, since it is the same pattern in the same already-edited file.
- **Issue #2 (MAJOR, C2 — AC-C2-4 false against `rss_engine.py`/`repositories/bangumi.py`):** Confirmed by grep — 9 sites in `rss_engine.py` (lines 74, 220, 694, 735-737, 896, 927-929, 1005, 1077-1079) and 1 in `repositories/bangumi.py:214`, none in `files_to_change`. Accepted, resolved via option (b) from the review's own fix suggestion: added **OD-C2-4** parking these as a named follow-up (not silently dropped), and narrowed AC-C2-4's grep to only the 8 files this pass actually edits. Rejected option (a) (pulling them into scope now) on minimality grounds: `rss_engine.py` is the RSS matching engine, the single highest file-overlap risk in this architecture review, and pulling in 10 more call sites for a pure dedup (no behavior fix attached) roughly doubles the diff for no added safety. This is a scope decision for the owner to confirm, not a unilateral call — see OD-C2-4's suggested default.
- **Issue #3 (MINOR, C2 — AC-C2-4 grep misses poster_url/root_path variants):** Confirmed — the original grep only matched `canonical_title`/`season` idioms. Accepted. AC-C2-4's grep now has 4 alternations (title/season/poster/root_path) instead of 2.
- **Issue #4 (MINOR, C2 — AC-C2-2's count doesn't reconcile with its own command):** Confirmed by running the exact commands: collector+rss_refresh+domain_models = 45 (matches); renamer+poster+bangumi_merge+bangumi-contract = 101 (not part of the "137" claim without test_rss.py); test_api_contract/test_rss.py = 36 separately. 101+36=137, but test_rss.py was never listed in AC-C2-2's quoted command. Accepted. AC-C2-2 now lists `test_api_contract/test_rss.py` explicitly in its command (it already appears in `focused_test_command` at the top level — this fix just makes AC-C2-2's own quoted command consistent with that), and states the reconciled total (182) instead of an ambiguous "137".

---

# G3-rename design (revised)

Repo: `/Users/tk/ws/Auto_Bangumi`, branch `refactor/backendv2`. Line numbers re-verified against current HEAD `a348c193`. This revision resolves all 4 reviewer issues (2 MAJOR, 2 MINOR) from the prior pass; see "Review notes" at the end of each candidate for disposition.

---

### C3 · Merge per-torrent rename decision tree

**Outcome:** One shared private method decides, for a single torrent, which rename path to take (single file / collection / zero-media) and whether to run the subtitle pass — called from both `rename_all` and `rename_bangumi`. The surrounding Phase-1/2/3 structure (caches, PikPak move-torrent logic, DB commit) stays in each caller, untouched.

**Verified facts (re-checked now):**
- `backend/src/module/services/renamer.py:130` `rename_all` — per-torrent loop body `181-285`.
- `backend/src/module/services/renamer.py:321` `rename_bangumi` — per-torrent loop body `393-482`.
- Drift confirmed: `rename_all` line 226 and line 248 both read `if success and subtitle_files:`; `rename_bangumi` line 426 and line 448 both read `if (success or retrigger) and subtitle_files:`.
- Extra differences found while reading, preserved as-is:
  1. `rename_all:204-208` logs a per-torrent summary line before dispatch. `rename_bangumi` has no equivalent.
  2. `rename_all:279-281` logs a success line. `rename_bangumi:477` has no success log — only the failure log at `480-482`/`283-285`. Pre-existing asymmetry, not touched.
  3. **Silent-skip path** (both functions, identical today): when the media rename succeeds but the subtitle pass returns `RenameOutcome.ERROR`, the code `continue`s before the final `if success: … else: logger.warning(...)` block. The torrent lands in neither `rename_successes` nor `rename_conflicts`, and no log line fires — implicit retry next run. Must be kept exactly.
  4. The zero-media-files branch already logs "has no media files" unconditionally, and if the subtitle pass then leaves `success=False`, the bottom block *also* logs "Failed to rename torrent {id}". Both lines can fire together today; the merge must not deduplicate them.
  5. Phase-3 DB-write blocks (`287-319` vs `484-517`) are byte-identical in shape; only local variable names differ. Untouched by this design.
  6. Arguments into `_rename_single_file`/`_rename_collection`/`_rename_subtitles` are identical in shape at both call sites, which is what makes a shared method possible.
  7. PikPak collection-folder move logic (`rename_bangumi:360-389`) only exists in `rename_bangumi`'s Phase 2, before the per-torrent loop, untouched by this refactor.
  8. **(Added per reviewer MINOR finding)** `rename_bangumi:405-406` has `if db_torrent.renamed_at is not None: continue`, with no counterpart in `rename_all`'s loop. This guard runs before `_classify_files` and is what makes `test_rename_bangumi_with_retrigger` (test_renamer.py:949) and `test_rename_bangumi_retrigger_keeps_failed_torrent_retryable` (test_renamer.py:983) behave correctly after `clear_rename_status`. **It stays in `rename_bangumi`'s own loop, outside the shared method's scope** — the shared method starts at `_classify_files`, not before it. The two per-torrent preambles are NOT otherwise identical; this guard is `rename_bangumi`-only.

**Exact change:**
- Add one new private method on `RenamerService`, e.g. `_rename_torrent_entry(self, torrent_info, db_torrent, bangumi, downloader, all_torrent_info, *, retry_subtitles_without_success: bool, log_summary: bool) -> _EntryOutcome`, where `_EntryOutcome` is a small `NamedTuple`/`dataclass` carrying the three-way result unambiguously:
  - `conflict_target: Optional[str]` — non-`None` ⇒ caller appends to `rename_conflicts` and continues.
  - `skip: bool` — `True` ⇒ caller does nothing (reproduces the silent-skip path), no append, no log.
  - `success: bool`, `file_count: int` — otherwise, caller's own dispatch decides: append to `rename_successes` on `True` (and maybe log success, per each caller's own asymmetry), or log the existing "Failed to rename torrent {id}" warning on `False`.
  - **The shared method never logs success or failure itself.** It computes and returns the outcome only; all logging (summary, success, failure) stays caller-owned, matching each caller's existing asymmetry (item 1, item 2 above).
  - `retry_subtitles_without_success` replaces the literal `success` / `success or retrigger` condition: `rename_all` passes `False` (preserves `success and subtitle_files`), `rename_bangumi` passes `retrigger` (preserves `(success or retrigger) and subtitle_files`).
  - `log_summary` replaces difference (1): `rename_all` passes `True` and logs the summary line itself before calling the shared method (or the method takes a logger callback — simplest: caller logs it, since it's a pre-dispatch concern); `rename_bangumi` passes `False`/omits it.
- `rename_all` (`181-285`): keeps its `renamed_at`-guard-free preamble, keeps its summary log (item 1), calls `_rename_torrent_entry(..., retry_subtitles_without_success=False)`, then does the 3-way dispatch itself: conflict → append; skip → nothing; success → append + log success (item 2); failure → log "Failed to rename torrent {id}".
- `rename_bangumi` (`393-482`): keeps its own `renamed_at is not None: continue` guard (item 8) *before* calling the shared method, calls `_rename_torrent_entry(..., retry_subtitles_without_success=retrigger)`, then the same 3-way dispatch, minus the success log it never had.
- No change to `_rename_single_file`, `_rename_collection`, `_rename_subtitles`, `_classify_files`, Phase 1, Phase 2 (move logic), or Phase 3 in either function.

**Behavior change:** None. `rename_all` continues to pass `retry_subtitles_without_success=False`; failure/success logging stays exactly where it is today, just relocated from inline code into each caller's dispatch block that follows the shared-method call.

**Invariants:**
- `INV-C3-1` — start: a torrent's media rename succeeds but its subtitle rename errors. Preserved guarantee: the torrent is recorded in neither `rename_successes` nor `rename_conflicts`, and no "Failed to rename" log line is emitted for it. Failure condition: the merged method or caller dispatch accidentally logs a failure or marks it done.
- `INV-C3-2` — start: `rename_all` processes a torrent. Preserved guarantee: subtitle retry only runs when `success=True` (`retry_subtitles_without_success=False` always for `rename_all`). Failure condition: scheduler-path subtitles get retried on a failed primary rename.
- `INV-C3-3` — start: `rename_bangumi` runs with `retrigger=True`, primary rename reports `success=False` for an already-cleared torrent. Preserved guarantee: subtitle pass still runs (matches `(success or retrigger)`). Failure condition: subtitles stop being retried under `retrigger=True`.
- `INV-C3-4` — Phase-3 DB write blocks and dict shapes in both functions are untouched; refactor only touches the per-torrent dispatch inside Phase 2.
- `INV-C3-5` — (new, from item 8) `rename_bangumi`'s `renamed_at is not None` skip-guard runs before the shared method is ever called and is never moved into it. Failure condition: a future edit pulls this guard into `_rename_torrent_entry` and silently applies it to `rename_all` too (which has no such guard today).

**Acceptance criteria:**
- `AC-C3-1` — `backend/src/tests/test_services/test_renamer.py::test_rename_all_records_subtitle_conflict` (existing, line 803) still passes unmodified.
- `AC-C3-2` — `backend/src/tests/test_services/test_renamer.py::test_rename_bangumi_with_retrigger` (line 949) and `::test_rename_bangumi_retrigger_keeps_failed_torrent_retryable` (line 983) still pass unmodified — the second is the exact regression guard for `INV-C3-3`/`INV-C3-5`.
- `AC-C3-3` — New baseline test (pure refactor ⇒ run on old code first to confirm it already holds) in `test_renamer.py`: `test_rename_all_subtitle_error_after_success_is_silently_skipped` — single-media-file torrent where the media rename succeeds and the subtitle rename returns `RenameOutcome.ERROR`; assert `rename_all`'s return list is empty and the DB torrent's `rename_status`/`renamed_at` are untouched (covers `INV-C3-1`).
- `AC-C3-4` — `test_renamer.py::test_rename_all_success` (line 712) and `::test_rename_bangumi_basic` (line 917) still pass — general smoke coverage of the merged dispatch for both callers.

**Minimality check:** Smallest outcome is deduplicating only the per-torrent dispatch block, not the whole function (Phase 1/2/3 differ too much). A bare-tuple return was considered instead of a small result type, but the 3-way outcome (conflict / silent-skip / resolved) needs a 4th state beyond what `_rename_single_file` already returns, so a tiny typed result is justified.

**Owner decisions:**
- `OD-C3-1` — Should `rename_all` ever pass `retry_subtitles_without_success=True`? Suggested default: **no** — keep `rename_all` passing `False` (current behavior); no ticket or test asks for scheduler-side subtitle retry.

**Review notes (C3):**
- MAJOR issue accepted: the prior draft said in one place the shared method "can" log the failure line, and in another place said the caller's dispatch logs it — those are mutually exclusive and would have double-logged "Failed to rename torrent {id}" on every real failure. **Fixed by striking the "can live inside the shared method" option entirely.** The shared method now only returns the typed outcome; all logging (summary, success, failure) is caller-owned, per the "Exact change" section above. This also makes `log_summary` simpler to reason about — it was never really a flag the shared method needed, since the summary log in `rename_all` happens before the shared method is called at all.
- MINOR issue accepted: `rename_bangumi:405-406`'s `renamed_at is not None` guard was missed in the original "Verified facts" / "Extra differences" list. **Fixed by adding it as item 8**, with an explicit statement that it stays in `rename_bangumi`'s own loop, outside `_rename_torrent_entry`'s scope, plus a new `INV-C3-5` to guard against a future implementer accidentally folding it into the shared method.

---

### C8 · Media/subtitle extensions duplicated

**Outcome:** One tuple each for media and subtitle extensions, defined once in `module/domain/value_objects.py`, imported by `renamer.py` and `pikpak.py`.

**Verified facts (re-checked now):**
- `backend/src/module/services/renamer.py:869` — `media_exts = (".mkv", ".mp4", ".avi", ".wmv", ".webm", ".flv", ".mov", ".ts", ".m2ts")` (inside `_is_media_file`).
- `backend/src/module/services/renamer.py:874` — `subtitle_exts = (".ass", ".ssa", ".srt", ".sub", ".vtt")` (inside `_is_subtitle_file`).
- `backend/src/module/services/downloader/pikpak.py:43-55` — `MEDIA_EXTENSIONS` (same 9, same order), `SUBTITLE_EXTENSIONS` (same 5, same order), `DOWNLOAD_FILE_EXTENSIONS = MEDIA_EXTENSIONS + SUBTITLE_EXTENSIONS`. Byte-identical confirmed.
- `value_objects.py:132,145` encode the same extension sets a third time, as Pydantic `Field(pattern=...)` regex strings — a different representation for a different purpose (construction-time validation). Left untouched (see owner decision).
- `grep -rn "\.mkv\|\.mp4\|MEDIA_EXTENSIONS\|SUBTITLE_EXTENSIONS\|m2ts" module/` found no other extension list.
- No test references `_is_media_file`, `_is_subtitle_file`, `MEDIA_EXTENSIONS`, or `SUBTITLE_EXTENSIONS` directly today. `test_renamer.py:1170` only patches `_classify_files` out wholesale via `patch.object(service, "_classify_files", return_value=...)` to stub it — it never asserts on `_classify_files`'s own return value as a behavior check; it uses it as a seam to bypass classification for an unrelated test.

**Exact change:**
- In `backend/src/module/domain/value_objects.py`, near `EpisodeFile`/`SubtitleFile`, add:
  ```python
  MEDIA_EXTENSIONS: tuple[str, ...] = (".mkv", ".mp4", ".avi", ".wmv", ".webm", ".flv", ".mov", ".ts", ".m2ts")
  SUBTITLE_EXTENSIONS: tuple[str, ...] = (".ass", ".ssa", ".srt", ".sub", ".vtt")
  ```
- `backend/src/module/services/renamer.py`: import `MEDIA_EXTENSIONS, SUBTITLE_EXTENSIONS` from `module.domain.value_objects`; `_is_media_file`/`_is_subtitle_file` reference the imported tuples instead of local literals. Same method names, same call sites — no interface change.
- `backend/src/module/services/downloader/pikpak.py`: replace local `MEDIA_EXTENSIONS`/`SUBTITLE_EXTENSIONS` literals with an import from `module.domain.value_objects`; keep the local `DOWNLOAD_FILE_EXTENSIONS = MEDIA_EXTENSIONS + SUBTITLE_EXTENSIONS`.
- Leave `EpisodeFile.suffix` / `SubtitleFile.suffix` regex `Field(pattern=...)` strings as literal strings (see owner decision).

**Behavior change:** None. Same tuples, same contents, same order — only the definition site moves.

**Invariants:**
- `INV-C8-1` — `RenamerService._is_media_file`/`_is_subtitle_file` and `pikpak._name_has_download_file_extension` classify the exact same set of filenames before and after the move.

**Acceptance criteria (revised):**
- `AC-C8-1` — **(Revised per reviewer MAJOR finding)** New baseline-behavior test (pure refactor ⇒ run first on old code to confirm it already passes), added to `backend/src/tests/test_services/test_renamer.py`, driven through the **public interface** (`rename_all`), not `_classify_files` directly: `test_rename_all_handles_all_known_extensions` — give one torrent a file list with one filename per extension in `MEDIA_EXTENSIONS` and one per extension in `SUBTITLE_EXTENSIONS` (via the mock downloader's `torrents_info`, same pattern as `test_rename_all_success`), run `rename_all`, and assert on the public return shape: the torrent is classified as a collection (multiple media files), `file_count` reflects all media files renamed, and no file is dropped or misclassified. This exercises `_classify_files` only as a side effect of `rename_all`, consistent with how every other rename test in this file is written, and satisfies the task's rule that "tests must go through the module interface, not lock helper shapes."
- `AC-C8-2` — Existing `test_renamer.py` suite (any test touching `_classify_files` via `rename_all`/`rename_bangumi`, e.g. `test_rename_all_success` at line 712) and the PikPak test module exercising `_name_has_download_file_extension`/`_task_represents_single_file` still pass unmodified.

**Minimality check:** Smallest fix is relocating the two tuples genuinely duplicated verbatim (renamer.py ↔ pikpak.py). Deriving the Pydantic `Field(pattern=...)` regex strings dynamically from the same tuples was considered and rejected — it touches model validation on two widely-used domain value objects for a cosmetic win, a larger blast radius than this behavior-preserving pass authorizes.

**Owner decisions:**
- `OD-C8-1` — Should `EpisodeFile.suffix`/`SubtitleFile.suffix` `Field(pattern=...)` also be generated from `MEDIA_EXTENSIONS`/`SUBTITLE_EXTENSIONS`, closing the third copy? Suggested default: **no, leave as literal regex strings** — file as a follow-up if the owner wants it.

**Review notes (C8):**
- MAJOR issue accepted: the original `AC-C8-1` called `RenamerService._classify_files` directly — a leading-underscore internal helper — which breaks the task's explicit rule against locking helper shapes, and was inconsistent with every other test in the file (all of which drive `rename_all`/`rename_bangumi` and assert on public return shapes). **Fixed** by rewriting `AC-C8-1` to drive `rename_all` with a mock downloader file list covering every extension and asserting on the public return (`file_count`, no dropped/misclassified files), per the reviewer's suggested fix.

---

### C9 · Rename lock 409 dance

**Outcome:** One async-context-manager helper in `module/concurrency/rename_lock.py` owns acquire + conditional release; both endpoints keep their own exact 409 response bodies.

**Verified facts (re-checked now):**
- `backend/src/module/concurrency/rename_lock.py:1-24` — `try_acquire_rename_lock()` (module-level `asyncio.Lock`, returns the lock or `None` if already held). Unchanged by this design; still used as-is by the scheduler's rename job (out of scope — task names only the two API endpoints).
- `backend/src/module/api/v1/bangumi.py:188-277` `update_rule`: acquires at line ~203, on `None` returns `409` with `msg_en="Rename is already in progress. Please try Apply again shortly."`, `msg_zh="当前正在执行重命名，请稍后再试。"`, then `try: … finally: lock.release()`.
- `backend/src/module/api/v1/bangumi.py` `retrigger_rename`: acquires similarly, on `None` returns `409` with `msg_en="Rename is already in progress. Please try again shortly."` (no "Apply"), `msg_zh` byte-identical to `update_rule`'s, then `try: … finally: lock.release()` around the rename call + response building.
- Difference confirmed: `msg_en` text differs ("Please try Apply again shortly." vs "Please try again shortly."); `msg_zh` is byte-identical in both. This is the WebUI-visible contract to preserve exactly.
- `retrigger_rename` builds `downloader`/`renamer` before the `try` (after lock acquisition); `update_rule` builds `downloader` inside `try`. Not normalized — construction has no side effects needing lock protection, and leaving each function's existing order keeps the diff smallest.
- **(Corrected per reviewer MINOR finding)** Near-duplicate tests already exist today, found via `grep -n "def test_update_rule\|def test_retrigger_rename" backend/src/tests/test_api_contract/test_bangumi.py`: `test_update_returns_409_when_rename_lock_held` at `backend/src/tests/test_api_contract/test_bangumi.py:361` and `test_retrigger_rename_returns_409_when_lock_held` at `backend/src/tests/test_api_contract/test_bangumi.py:930`. Both currently assert only `"rename" in msg_en.lower()`, not the exact distinct wording, so there is still a real gap to close — but the design should name these tests up front rather than defer to a grep "at implementation time" (see fix below).

**Exact change:**
- In `backend/src/module/concurrency/rename_lock.py`, add (stdlib `contextlib.asynccontextmanager`, no new dependency):
  ```python
  from contextlib import asynccontextmanager

  @asynccontextmanager
  async def rename_lock_guard():
      """Acquire the shared rename lock; yields None if already held.

      Caller is responsible for returning its own 409 response when the
      yielded value is None (message text is each caller's contract, not
      this helper's).
      """
      lock = await try_acquire_rename_lock()
      try:
          yield lock
      finally:
          if lock is not None:
              lock.release()
  ```
- `update_rule`: replace the acquire-and-409 block plus the `try:`/`finally: lock.release()` wrapper with:
  ```python
  async with rename_lock_guard() as lock:
      if lock is None:
          return JSONResponse(status_code=409, content={"msg_en": "Rename is already in progress. Please try Apply again shortly.", "msg_zh": "当前正在执行重命名，请稍后再试。"})
      # ...unchanged body that was inside try:...
  ```
  (the function's `return` statements inside the body work unchanged — exiting the `async with` on return still runs the generator's `finally`, matching the old `finally: lock.release()` exactly).
- `retrigger_rename`: same transformation, keeping its own distinct `msg_en` text ("Please try again shortly.", no "Apply").
- The scheduler's rename job is left untouched — it doesn't return a 409, it just skips the cycle, and it isn't named in the task.

**Behavior change:** None. Same lock object, same acquire/release ordering, same 409 status codes and bilingual bodies verbatim, same control flow.

**Invariants:**
- `INV-C9-1` — start: rename lock already held when `update_rule` is called. Preserved guarantee: response is `409` with the exact `msg_en`/`msg_zh` pair quoted above for `update_rule`; the lock is not touched since `rename_lock_guard` never acquired it.
- `INV-C9-2` — start: same, for `retrigger_rename`. Preserved guarantee: response is `409` with `retrigger_rename`'s own distinct `msg_en` text.
- `INV-C9-3` — start: lock acquired successfully, handler body raises or returns normally. Preserved guarantee: lock is always released exactly once.

**Acceptance criteria (revised):**
- `AC-C9-1` — **(Revised per reviewer MINOR finding)** Extend the two existing tests in `backend/src/tests/test_api_contract/test_bangumi.py` — `test_update_returns_409_when_rename_lock_held` (line 361) and `test_retrigger_rename_returns_409_when_lock_held` (line 930) — with an exact `msg_en` equality assertion (`== "Rename is already in progress. Please try Apply again shortly."` and `== "Rename is already in progress. Please try again shortly."` respectively), rather than adding new tests, proving the two messages stay distinct after the helper lands.
- `AC-C9-2` — Scheduler rename-job tests exercising `try_acquire_rename_lock` directly (locate via `grep -rn "try_acquire_rename_lock" backend/src/tests/test_scheduler/`) still pass unmodified — confirms the scheduler's independent use of `try_acquire_rename_lock` is untouched.
- `AC-C9-3` — Existing happy-path tests for `update_rule`/`retrigger_rename` (e.g. `test_update_success`, `test_retrigger_rename_success` at line 897) still pass — confirms the lock is still released after a normal (non-409) run, through the new context manager.

**Minimality check:** Stdlib `contextlib.asynccontextmanager` beats a bespoke class; the helper owns only acquire/release mechanics, not the response bodies, so the two endpoints' divergent `msg_en` text needs no parameter, no config, and no new abstraction. Rejected: baking the message text into the helper (would need a parameter per call site for marginal benefit, and risks the two "same" messages drifting together by accident, contrary to "response text is a contract").

**Owner decisions:**
- `OD-C9-1` — None needed; default (keep both 409 messages exactly as they are today) fully satisfies the task's own default instruction.

**Review notes (C9):**
- MINOR issue accepted: the prior draft deferred naming the existing 409 tests to "a grep at implementation time," when the design process itself should have found them (it did an equivalent grep rigorously for C3/C8). **Fixed** by naming `test_update_returns_409_when_rename_lock_held` (test_bangumi.py:361) and `test_retrigger_rename_returns_409_when_lock_held` (test_bangumi.py:930) explicitly and changing `AC-C9-1` to "extend these two existing tests" rather than "add ... if none exist."

---

**Ordering/dependencies (unchanged):** C8 (extension constants) has no dependency on C3 or C9 and can land independently/first. C3 touches disjoint line ranges in `renamer.py` from C8 (C8: `_is_media_file`/`_is_subtitle_file` bodies + imports; C3: per-torrent loop bodies in `rename_all`/`rename_bangumi`) — land C8 first to avoid rebasing C3, or combine in one PR since both are small and non-overlapping. C9 (`api/v1/bangumi.py` + `rename_lock.py`) is fully independent of C3/C8 and can land in any order, including in parallel. No candidate re-touches A-001's shared RSS selection or PikPak task-interpretation code.

---

## GROUP G4-poster-mikan — design (revised)

Investigated on current `refactor/backendv2` HEAD (a348c193). Line numbers below are current, not drifted. This revision resolves all 8 reviewer issues; see "Review notes" per issue for what changed and why.

---

### C7 · One Mikan episode-page scraper

**Outcome.** `parse_mikan_page` (regex, pure) becomes the only HTML scraper for a Mikan episode page. `domain/parser/analyser/mikan_parser.py` (BeautifulSoup scraper + its own HTTP fetch + its own poster caching) is deleted. The public facade callers already use — `TitleParser.mikan_parser_with_rss(homepage)` — keeps its name and return shape, so none of the 6 production call sites change.

**Verified facts (re-checked now)**
- `backend/src/module/mikan/parser.py:82` `parse_mikan_page(html)` — pure, takes already-fetched HTML, returns `MikanRef(mikan_bangumi_id, mikan_subgroup_id, canonical_title, poster_url)` or `None`. 3-tier id fallback (`_TIER_A/B/C`, line 59-63). Also already defines `build_season_rss_url(bangumi_id, subgroup_id, base_url=...)` (line 145-156) producing `f"{base}/RSS/Bangumi?bangumiId={bid}&subgroupid={sid}"`, and raising `ValueError` when `bangumi_id <= 0 or subgroup_id <= 0` (line 153-154).
- `backend/src/module/domain/parser/analyser/mikan_parser.py` is 176 lines total (1-176, whole file); `mikan_parser_with_rss(homepage)` itself starts at line 37. It fetches HTML itself via `RequestContent().get_html()`, scrapes title via BS4 selector `p.bangumi-title a[href^="/Home/Bangumi/"]`, scrapes poster via `div.bangumi-poster` style, downloads the image and calls `save_image()` to get a local `posters/*.jpg` path, and scrapes `season_rss_link` via a 4-method CSS/regex fallback chain (`_extract_season_rss_link`, line 84 onward) that **builds the exact same URL format** as `build_season_rss_url`.
- **Found bug, not a hypothetical**: the old title selector only matches `p.bangumi-title`. The real-markup fixture used for `parse_mikan_page`'s own tests (`tests/fixtures/mikan/episode_page_subscribe_button.html`) uses `<div class="bangumi-title">`. The old scraper's title selector does **not** match that markup → `official_title` comes back `""` on current real Mikan pages. `parse_mikan_page`'s `_TITLE` regex matches both `div` and `p` (`mikan/parser.py:64-67`) and is verified correct by `tests/test_mikan/test_parser.py::TestParseMikanPage::test_tier_a_subscribe_button`.
- Poster raw value is identical between scrapers on the same fixture: old BS4 extracts `/images/Bangumi/202410/730372c2.jpg` from the style attribute; `parse_mikan_page`'s `_POSTER` regex extracts the same string into `poster_url`. Only the *old* scraper then downloads+caches it; `parse_mikan_page` intentionally stays pure (no I/O) — confirmed by its docstring and by `mikan/resolver.py` doing the download/cache step itself, separately, via `MikanClient`/`save_image`.
- **Call-site audit** (why the facade, not the module, is the real seam): no production code imports `mikan_parser_with_rss`/`MikanParserResult` from `domain/parser/analyser/mikan_parser.py` directly. All 6 production call sites go through the `TitleParser` method: `rss/analyser.py:65` (`_pending_bangumi_from_mikan`), `rss/analyser.py:122` (`official_title_parser`), `services/rss_engine.py:263` (`_build_bangumi_from_mikan`), `services/rss_engine.py:355` (`_auto_create_bangumi`), and (via C4) `services/poster.py`. Only 2 test files import the dataclass directly: `test_services/test_rss_engine.py:1028`, `test_domain/test_parser/test_aggregate_resilience.py:18`.
- `domain/parser/title_parser.py:113-122` — `TitleParser.mikan_parser` (tuple-returning `(poster, title)` wrapper around the old module function) has **zero callers** anywhere in `src/module` or `src/tests` (checked with grep for `.mikan_parser(` excluding `_with_rss`, no hits). Dead code.
- `src/tests/test_e2e/conftest.py:303-304` patches `module.domain.parser.analyser.mikan_parser.RequestContent` and `...save_image` directly (per-module patching, the known project pattern) — this patch target must move with the fetch/cache code.

**Exact change**
- Delete `backend/src/module/domain/parser/analyser/mikan_parser.py` entirely (scraper, `_extract_season_rss_link`, `MikanParserResult`, both functions).
- `backend/src/module/domain/parser/analyser/__init__.py`: drop the `from .mikan_parser import ...` line (keep the other 4 re-exports untouched).
- `backend/src/module/domain/parser/title_parser.py`:
  - Add a local `@dataclass class MikanParserResult: poster_link: str; official_title: str; season_rss_link: Optional[str] = None` (same fields, same name — only its *location* moves).
  - Import `parse_mikan_page`, `build_season_rss_url` from `module.mikan.parser`; `RequestContent` from `module.network`; `save_image` from `module.utils`; `parse_url` from `urllib3.util` (all already-used utilities, no new dependency).
  - Reimplement `mikan_parser_with_rss(homepage)` body: fetch `html = RequestContent().get_html(homepage)` (unchanged I/O), `ref = parse_mikan_page(html)`; if `ref is None` return `MikanParserResult("", "", None)` (parity with old total-miss case); else `official_title = ref.canonical_title or ""`; if `ref.poster_url`: resolve `base_url` the same way the old code did (`parse_url(homepage)` → scheme+host), strip `?...`, `img = RequestContent().get_content(f"{base_url}{poster_path}")`, `poster_link = save_image(img, suffix)` (same download+cache call, now fed by the regex-extracted path instead of the BS4-extracted one — same value on real markup); `season_rss_link`: when `ref.mikan_bangumi_id > 0 and ref.mikan_subgroup_id > 0`, call `build_season_rss_url(ref.mikan_bangumi_id, ref.mikan_subgroup_id, base_url=base_url)`, else `None` (the `> 0` guard replaces `build_season_rss_url`'s own `ValueError` raise — see fixed issue below, was MINOR-C7-1).
  - Delete the dead `mikan_parser` tuple method (and its import) — unreachable, no behavior change.
- No change to `backend/src/module/mikan/parser.py` or `mikan/resolver.py` — `parse_mikan_page` and `build_season_rss_url` are reused as-is, confirming they are already the single scraper/url-builder.

**Behavior change**
- `official_title` from the Mikan path now comes back correctly on real pages that use `div.bangumi-title` (it was silently `""` before) — a bug fix, not a regression. Everywhere `official_title` reaches a caller it already goes through `re.sub(r"[/:.\\]", " ", ...)` and the same season-from-title parsing, so no caller needs a code change, only better input.
- `season_rss_link` is now derived from the (bangumi_id, subgroup_id) pair instead of scraping anchor/subscribe-button HTML for an RSS link. Same URL string format and value on every fixture and real-markup sample on hand; only diverges from the old scraper on a page where the ids parse correctly but the old 4-tier HTML scrape would have found a *different* (and un-exercised-by-tests) RSS link — no such case is in the test suite or fixtures.
- Poster handling (download + `save_image` + local path) is unchanged; only the raw source-path extraction moves from BS4 to regex (both yield the identical raw value on `episode_page_subscribe_button.html` / `episode_page_anchor_only.html`).
- No change to any HTTP response, DB field, or the `TitleParser.mikan_parser_with_rss` call signature.

**Invariants**
- INV-C7-1: start — any production code that needs an episode-page scrape calls `TitleParser.mikan_parser_with_rss` (never a second scraper). preserved — `parse_mikan_page` is the only place with HTML-structure knowledge; `title_parser.py` only does fetch/download/URL-building. failure — a new call site reimplements BS4 scraping instead of calling the facade.
- INV-C7-2: start — `MikanResolver` (async path) is untouched by this change. preserved — `mikan/resolver.py` and `mikan/parser.py` have zero lines changed. failure — any edit to those two files under this candidate.
- INV-C7-3: start — `mikan_parser_with_rss(homepage)` always returns a `MikanParserResult`-shaped object (never raises on a non-Mikan, malformed, or pathological-id page). preserved — `parse_mikan_page` returning `None` maps to the empty-result object; a zero/negative id pair maps `season_rss_link` to `None` instead of calling `build_season_rss_url` (which would raise `ValueError` on `<= 0` input — the id guard exists specifically to uphold this invariant). failure — a `None`/missing-field return, or an uncaught `ValueError`, reaching a caller that does `.poster_link`.

**Acceptance criteria**
- AC-C7-1: given `episode_page_subscribe_button.html`, `TitleParser().mikan_parser_with_rss(homepage)` (with `RequestContent`/`save_image` mocked to return that fixture's bytes and a deterministic cache path) returns `official_title == "身为悲剧始作俑者的最强邪恶BOSS女王为民竭心尽力。 第二季"` and `season_rss_link == "https://mikanani.me/RSS/Bangumi?bangumiId=3906&subgroupid=370"`. New test: `backend/src/tests/test_domain/test_parser/test_title_parser.py::TestMikanParserWithRss::test_subscribe_button_fixture`.
- AC-C7-2: given `episode_page_no_ref.html` (404 page), `mikan_parser_with_rss` returns `MikanParserResult("", "", None)` and does not raise. New test: same file, `test_no_ref_fixture_returns_empty_result`.
- AC-C7-3 (new, fixes MINOR-C7-1): a synthetic HTML fixture with `data-bangumiid="0" data-subtitlegroupid="370"` (id parses to 0, a pathological-but-possible regex match) — `mikan_parser_with_rss` returns a `MikanParserResult` with `season_rss_link is None` and does not raise `ValueError`. New test: same file, `test_zero_bangumi_id_does_not_raise`.
- AC-C7-4 (baseline, run on OLD code before the change to document current — broken — behavior): a test instantiating the *old* `domain/parser/analyser/mikan_parser.mikan_parser_with_rss` against `episode_page_subscribe_button.html` shows `official_title == ""` (selector mismatch). Run once, informational, not kept after the module is deleted.
- AC-C7-5: `backend/src/tests/test_e2e/test_bangumi_crud.py::TestRefreshPoster::test_refresh_poster_all` and the rest of `src/tests/test_e2e/` (144 tests) pass unmodified after `conftest.py`'s patch targets move.
- AC-C7-6: `pytest backend/src/tests/test_mikan/ backend/src/tests/test_domain/test_parser/ backend/src/tests/test_services/test_rss_engine.py -q` passes (covers `parse_mikan_page` untouched, `MikanResolver` untouched, and the two import-path fixes).

**Minimality check** — smallest outcome: delete the duplicate scraper, keep every caller-facing name identical. Simpler alternative considered: rename the facade to match "delete mikan_parser_with_rss" literally and have all 6 call sites call `parse_mikan_page` + a new helper directly — rejected, it touches `rss/analyser.py`, `rss_engine.py`, and 3 test files for zero behavior gain over keeping the existing facade name. Each part is needed: `MikanParserResult` dataclass is needed because 6 call sites read `.poster_link`/`.official_title`/`.season_rss_link` by attribute; `build_season_rss_url` reuse is needed because it replaces ~90 lines of scraping with a 1-line call using data `parse_mikan_page` already extracted; the `> 0` id guard is needed because `build_season_rss_url` raises on bad input and the facade's contract (INV-C7-3) is "never raises."

**Owner decisions**
- OD-C7-1 — Q: Keep `TitleParser.mikan_parser_with_rss` name/shape as the facade (my default), or literally delete the name and have every caller call `parse_mikan_page` + a new combinator directly? A (default): keep the facade name; only its *scraping internals* are deleted/replaced. Rationale: 6 production call sites + 3 test files key off this exact name; renaming is pure churn.
- OD-C7-2 — Q: Adopt `parse_mikan_page`'s title extraction (fixes the `div.bangumi-title` bug) as the new output, or preserve the old (currently-broken-on-real-pages) `""` result for byte-for-byte compatibility? A (default): adopt the fix — it is strictly more correct and every caller already treats an empty title as "nothing extracted," so this only improves data, never breaks a caller's branch.
- OD-C7-3 — Q: Build `season_rss_link` from `(mikan_bangumi_id, mikan_subgroup_id)` via `build_season_rss_url`, or port the old 4-tier HTML scrape verbatim? A (default): use `build_season_rss_url` — identical format/value on every known fixture, strictly more robust (can't be fooled by page layout), and deletes ~90 lines instead of adding ~90 duplicated lines.
- OD-C7-4 — Q: Delete the unused `TitleParser.mikan_parser` tuple method, or keep it as an unused convenience? A (default): delete — zero callers found, no behavior change.

**Review notes (C7)**
- MINOR-C7-1 (build_season_rss_url can raise on a 0 id, contradicting INV-C7-3) — **accepted, fixed in this revision**. Re-verified: `build_season_rss_url` (`mikan/parser.py:153-154`) does raise `ValueError` when either id is `<= 0`, and `_TIER_A/B/C` are plain `\d+` captures that can match a literal `"0"` on a pathological page. Fix: the "Exact change" section now guards the call with `ref.mikan_bangumi_id > 0 and ref.mikan_subgroup_id > 0` before calling `build_season_rss_url`, falling back to `season_rss_link = None` otherwise — same outcome as "ids absent." Added AC-C7-3 to cover it. No owner decision needed; this is a pure bug-prevention guard, not a behavior trade-off.
- MINOR-C7-2 (file-line citation said "37-177, whole file" for a 1-176 file) — **accepted, fixed in this revision**. Re-verified: `wc -l` reports 176 lines; `mikan_parser_with_rss` starts at line 37. Citation corrected to "176 lines total (1-176, whole file); `mikan_parser_with_rss` itself starts at line 37" above.

---

### C4 · Poster refresh duplication

**Outcome.** `PosterService` becomes the single owner of the poster-refresh rule (Mikan-first via `TitleParser.mikan_parser_with_rss`, then TMDB fallback via `tmdb_parser`). The two router endpoints (`refresh_poster`, `refresh_poster_by_id`) stop duplicating that ~35-line block and instead call the service. The `_poster_needs_refresh` staleness gate stays exactly where it is and applies only to the batch endpoint's loop, per instructions.

**Verified facts (re-checked now)**
- `backend/src/module/api/v1/bangumi.py:460-497` `refresh_poster` (batch, `POST /refresh/poster/all`): loads `bangumi_repo.get_all()`, loops, gates each bangumi on `_poster_needs_refresh(bangumi)`, and inline does: if `bangumi.rss_id` → look up rss → if `rss.parser == "mikan"` → look up torrent homepage → `asyncio.to_thread(parser.mikan_parser_with_rss, torrent.homepage)` inside a `try/except Exception` that only `logger.warning`s and falls through → on `result.poster_link` call `bangumi_repo.update_simple(id, {"poster_link": ...})`; else (or on Mikan exception/miss) → **no try/except** around `asyncio.to_thread(tmdb_parser, canonical, language)` → update if found. Re-verified line-by-line: the Mikan branch (line 478-484) is wrapped in `try/except Exception`; the TMDB branch (line 486-491) is not wrapped at all — an uncaught `tmdb_parser` exception propagates straight out of the endpoint.
- `backend/src/module/api/v1/bangumi.py:500-544` `refresh_poster_by_id` (single, `POST /refresh/poster/{id}`): the **identical** block, unconditional (no `_poster_needs_refresh` check), after an explicit 404 if the bangumi doesn't exist. Same asymmetry: Mikan branch (line 525-531) caught, TMDB branch (line 533-538) not caught.
- `TitleParser` and `RSSRepository` are imported at module level in `bangumi.py` and, re-verified by grep, used **only** inside these two endpoints (no other endpoint in the file references either name).
- `backend/src/module/services/poster.py` — `PosterService.__init__` only builds `self.bangumi_repo` (no `asyncio`/`TitleParser` import in the file today); `fetch_poster` (36-71) is TMDB-only and is reusable as-is; `refresh_all_posters` (73-122) iterates `bangumi_repo.get_active()` (not `get_all()` — a *different* bangumi set than the router uses) and gates on "has a `poster_url` already" (a different, narrower gate than `_poster_needs_refresh`); `refresh_poster` (124-179) updates via `bangumi_repo.update(id, data, expected_version=bangumi.version)` — optimistic locking — and the **entire fetch+update body is wrapped in one blanket `try/except Exception`** (line 151-179) that turns any failure, including an update conflict, into a non-raising `{"success": False, "message": f"Error: {e}"}` return. This is a materially different error-handling shape than the router's current split (Mikan caught / TMDB uncaught).
- `PosterService` has **no production caller** — confirmed by codegraph ("1 caller" = its own test file `test_services/test_poster.py`) and by grep (`grep -rln PosterService src/` returns only `services/poster.py` and its test).
- Router's HTTP response for both endpoints is a fixed `{"msg_en": "Refresh poster link successfully.", "msg_zh": "..."}` regardless of whether any individual bangumi's poster actually updated — the per-bangumi success/failure never reaches the HTTP response today, and no test asserts an HTTP 500 on a TMDB failure for either endpoint (re-checked: no such assertion exists in `test_api_contract/test_bangumi.py`'s `TestRefreshPoster*` classes). So the response body/status is unaffected either way, but the *failure-propagation shape* (abort-mid-loop vs. caught-and-continue) is a real, previously-undisclosed behavior change — see fixed issue below (was MAJOR-C4-2).
- Tests that exercise these endpoints and patch router-internal collaborators by name: `test_api_contract/test_bangumi.py::TestRefreshPoster::{test_refresh_poster_all_success (line 542), test_refresh_poster_all_refetches_when_cached_file_missing (line 555)}` and `::TestRefreshPosterById::test_refresh_poster_by_id_success (line 592)` all `patch("module.api.v1.bangumi.RSSRepository")` and `patch("module.api.v1.bangumi.TitleParser")` directly (re-verified by reading the file: lines 544-546, 567-569, 594-596). **This includes `test_refresh_poster_all_success`, which the original design missed** — see fixed issue below (was BLOCKING-C4-1).
- `test_services/test_poster.py::TestRefreshPoster` (lines 266-357) re-verified test-by-test: `test_refresh_poster_success` (277-279) and `test_refresh_poster_returns_message` (344-346) each `patch.object(poster_service.bangumi_repo, "update")` and assert `mock_update.assert_called_once()` — these two *do* break under OD-C4-1's `update` → `update_simple` switch. `test_refresh_poster_fetch_failure` (304-318) and `test_refresh_poster_exception_handling` (321-337) patch only `get_by_id` and `fetch_poster`, never `update` — `fetch_poster` returns `None` or raises in both, so `update`/`update_simple` is never reached and neither test asserts on it. **The prior design draft (and the review that flagged it) over-stated this: only 2 of the 4 named tests actually need a rewrite for the `update`→`update_simple` switch itself** — see corrected scope below (was MAJOR-C4-1, partially rejected).

**Exact change**
- `backend/src/module/services/poster.py`:
  - Add `import asyncio` and `from module.domain.parser.title_parser import TitleParser` to the module's imports (both needed by the new Mikan step below — fixes MINOR-C4-2 from the prior draft, which omitted them).
  - `__init__`: add `self.rss_repo = RSSRepository(session)`, `self.torrent_repo = TorrentRepository(session)` (import from `module.repositories`, same package `BangumiRepository` already comes from).
  - Replace `refresh_poster(bangumi_id)`'s body: after the existing not-found check, add the Mikan-first step, matching the router's current try/except shape exactly (including the log line the router already has):
    ```
    poster_link = None
    if bangumi.rss_id:
        rss = await self.rss_repo.get_by_id(bangumi.rss_id)
        if rss and rss.parser == "mikan":
            torrent = await self.torrent_repo.get_by_bangumi_with_homepage(bangumi.id)
            if torrent and torrent.homepage:
                try:
                    result = await asyncio.to_thread(TitleParser().mikan_parser_with_rss, torrent.homepage)
                    poster_link = result.poster_link or None
                except Exception as e:
                    logger.warning(f"[Poster] Mikan parser failed for {_title}: {e}")
    if not poster_link:
        poster_link = await self.fetch_poster(_title, _season)
    ```
    — then update and return exactly as today (fall through to the existing `if poster_link: update + return success` / `else: return not-found message` shape). This is the router's `poster_fetched` logic, moved, with the diagnostic `logger.warning` line preserved verbatim (fixes MINOR-C4-1 from the prior draft, which dropped it).
  - Change the DB write from `bangumi_repo.update(..., expected_version=...)` to `bangumi_repo.update_simple(id, {"poster_link": poster_link})` to match the router's current (lock-free) behavior exactly — see OD-C4-1.
  - Delete `refresh_all_posters()` entirely (dead rule, different bangumi-selection and gate than the router needs — see OD-C4-2).
  - Keep `fetch_poster()` unchanged (still the TMDB step, now called from the rewritten `refresh_poster`). Keep the existing blanket `try/except Exception` wrapping the whole method body (unchanged structurally; it now also covers the Mikan step's non-exceptional paths, which is fine since the Mikan step has its own inner try/except already) — see the disclosed behavior change below (fixes MAJOR-C4-2 from the prior draft).
- `backend/src/module/api/v1/bangumi.py`:
  - `refresh_poster` (batch): keep `bangumi_repo.get_all()` and the `_poster_needs_refresh(bangumi)` gate exactly as-is; replace the inline Mikan/TMDB block with `poster_service = PosterService(session)` once before the loop, and inside the gate: `await poster_service.refresh_poster(bangumi.id)` (ignore/log the returned dict — HTTP response is unaffected either way).
  - `refresh_poster_by_id`: keep the existing explicit not-found 404 check (unchanged, cheapest way to preserve that exact 404 body); then call `await poster_service.refresh_poster(bangumi_id)` unconditionally (no gate), same as today.
  - Remove the now-unused module-level `TitleParser`/`RSSRepository`/`TorrentRepository` imports and the inline `from module.domain.parser.analyser.tmdb_parser import tmdb_parser` local imports — re-verified these names have no other use in the file once both endpoints are rewritten.

**Behavior change**
- HTTP-observable surface is unchanged: same routes, same gate (batch only), same fallback order (Mikan → TMDB), same final response shape (fixed `msg_en`/`msg_zh`, 200).
- **Disclosed change (was missing from the prior draft, now stated per MAJOR-C4-2):** today, an uncaught exception from `tmdb_parser` propagates out of either endpoint undamped — in the batch endpoint this aborts the `for` loop mid-iteration (no commit, remaining bangumi untouched, request ends in an unhandled-exception/500); in the by-id endpoint it is a 500 for that one bangumi. After this change, `PosterService.refresh_poster`'s existing blanket `try/except Exception` (poster.py:151-179, unchanged by this candidate) catches that same TMDB exception, logs it, and returns a non-raising `{"success": False, ...}` dict — the batch loop continues to the next bangumi instead of aborting, and the by-id endpoint returns its normal 200 "refreshed" response instead of a 500. This is strictly more robust (one bad TMDB lookup no longer kills the whole batch run or surfaces a 500 for a single bangumi), but it is an observable change in failure handling, not a no-op refactor. See OD-C4-4 below for the owner decision this requires.
- The DB-write call changes from `update` (optimistic-locked) to `update_simple` (lock-free), matching current router behavior exactly (OD-C4-1) — no new `ConcurrentModificationError` is introduced.
- `PosterService.refresh_all_posters()` no longer exists (it was unreachable from any route).

**Invariants**
- INV-C4-1: start — the batch endpoint only touches a bangumi when `_poster_needs_refresh` is true. preserved — the gate check stays in the router's loop, unchanged, wrapping the new `poster_service.refresh_poster(...)` call. failure — the gate moves inside `PosterService` and silently also applies to the by-id endpoint.
- INV-C4-2: start — the by-id endpoint always attempts a refresh regardless of staleness. preserved — no gate is added around its `poster_service.refresh_poster(...)` call. failure — any `_poster_needs_refresh` check appears on that path.
- INV-C4-3: start — a bangumi update from this flow never raises `ConcurrentModificationError`. preserved — `update_simple` (no optimistic lock), not `update(expected_version=...)`. failure — switching to `update()` reintroduces a failure mode the router never has today.

**Acceptance criteria**
- AC-C4-1 (fixes BLOCKING-C4-1): `test_api_contract/test_bangumi.py::TestRefreshPoster::test_refresh_poster_all_success` (line 542) — rewritten to `patch("module.api.v1.bangumi.PosterService")` (single collaborator mock with `refresh_poster = AsyncMock()`) instead of `RSSRepository`/`TitleParser`, since those module-level names are removed from `bangumi.py`.
- AC-C4-2: `test_api_contract/test_bangumi.py::TestRefreshPoster::test_refresh_poster_all_refetches_when_cached_file_missing` (line 555) — rewritten the same way: patch `module.api.v1.bangumi.PosterService` (single collaborator mock with `refresh_poster = AsyncMock()`) instead of `TitleParser`/`RSSRepository`/`TorrentRepository`; asserts `poster_service.refresh_poster.assert_awaited_once_with(1)` is only called when `_poster_needs_refresh` returns `True`.
- AC-C4-3: `test_api_contract/test_bangumi.py::TestRefreshPosterById::test_refresh_poster_by_id_success` (line 592) — rewritten the same way; asserts `poster_service.refresh_poster` is awaited even when a staleness-gate mock would say "not stale" (proves the by-id path has no gate).
- AC-C4-4 (corrected scope for MAJOR-C4-1): `test_services/test_poster.py::TestRefreshPoster` —
  - `test_refresh_poster_success` (line 270) and `test_refresh_poster_returns_message` (line 338): rewritten to `patch.object(poster_service.bangumi_repo, "update_simple")` in place of `"update"`, asserting `mock_update_simple.assert_called_once()`. These are the only 2 of the 4 existing tests in this class that assert on the DB-write call.
  - `test_refresh_poster_fetch_failure` (line 304) and `test_refresh_poster_exception_handling` (line 321): **not rewritten for the update→update_simple switch** (they never patched or asserted on `update`), but each gets its `_make_bangumi_mock()` bangumi given an explicit `bangumi.rss_id = None` so the new Mikan step short-circuits immediately and these tests keep exercising only the TMDB/`fetch_poster` path they were written for, without the new `rss_repo`/`torrent_repo` calls hitting the raw mock session.
  - Two new tests: `test_refresh_poster_tries_mikan_first` (mocks `rss_repo.get_by_id` → `parser="mikan"`, `torrent_repo.get_by_bangumi_with_homepage` → homepage, `TitleParser.mikan_parser_with_rss` → a result with `poster_link`; asserts `fetch_poster` (TMDB) is **not** called and `bangumi_repo.update_simple` is called with the Mikan poster_link); `test_refresh_poster_falls_back_to_tmdb_when_mikan_empty` (Mikan step yields no poster_link, `bangumi.rss_id = None` → `fetch_poster` is called, same as `test_refresh_poster_success`).
  - `TestRefreshAllPosters` class is deleted (method no longer exists).
- AC-C4-5: `backend/src/tests/test_e2e/test_bangumi_crud.py::TestRefreshPoster::test_refresh_poster_all` (e2e, 144-suite) passes unmodified.
- Focused run: `cd backend && uv run python -m pytest src/tests/test_api_contract/test_bangumi.py src/tests/test_services/test_poster.py src/tests/test_api_contract/test_poster_needs_refresh.py -q`.

**Minimality check** — smallest outcome: one new method body in the already-existing (but dead) `PosterService`, two thinner router endpoints; no new file, no new class, no new dependency. Simpler alternative considered: extract a private helper function in `bangumi.py` instead of using `PosterService` — rejected, because the task explicitly names `PosterService` as the intended owner and it already exists with the right constructor shape (`session` in, repo attributes out); using it also finally gives it a live caller instead of leaving it dead. Each part needed: `rss_repo`/`torrent_repo` additions are needed because the Mikan step requires both; keeping the gate in the router is needed because `PosterService.refresh_poster` is also called unconditionally by the by-id endpoint; the explicit `bangumi.rss_id = None` fixture tweak in two existing tests is needed only because those tests use a loose `MagicMock()` bangumi whose default `.rss_id` attribute is truthy and would otherwise route into the new (unmocked) `rss_repo` call — the minimal fix is a one-line fixture change, not a rewrite of the test body.

**Owner decisions**
- OD-C4-1 — Q: Use `update_simple` (no optimistic lock, matches today's router behavior) or `update(expected_version=...)` (today's dead `PosterService` behavior)? A (default): `update_simple` — preserves current behavior exactly; switching to the locked variant would add a new failure mode (`ConcurrentModificationError`) on a path that has never raised it.
- OD-C4-2 — Q: Delete `PosterService.refresh_all_posters()` (unused, different bangumi-selection and gate than the router needs), or keep it unused for a hypothetical future bulk-TMDB-only caller? A (default): delete it and its `TestRefreshAllPosters` tests — nothing calls it, and keeping a second, narrower "refresh all" rule around is exactly the "two rules" the candidate says to stop having.
- OD-C4-3 — Q: Should the batch endpoint switch its bangumi source from `bangumi_repo.get_all()` to `PosterService`'s old `get_active()`? A (default): no — keep `get_all()`, to avoid silently changing which bangumi are considered for a poster refresh.
- OD-C4-4 (new, fixes MAJOR-C4-2) — Q: Accept that a TMDB-lookup exception now gets caught and logged (batch loop continues to the next bangumi; by-id endpoint returns its normal 200 instead of a 500), instead of today's uncaught-exception/abort behavior? A (default): accept it — it is strictly more robust for an endpoint whose only job is "best-effort refresh everything you can," and no existing test asserts a 500 on TMDB failure for either endpoint, so nothing currently depends on the abort behavior. Alternative (not taken): add a second, outer try/except in the router around the `poster_service.refresh_poster(...)` call that re-raises, to byte-for-byte preserve today's abort-on-TMDB-failure behavior — rejected as unnecessary churn for a failure mode nothing tests or depends on.

**Review notes (C4)**
- BLOCKING-C4-1 (`test_refresh_poster_all_success` breaks because it patches module-level `RSSRepository`/`TitleParser` after they're removed) — **accepted, fixed in this revision**. Re-verified: `bangumi.py`'s `TitleParser`/`RSSRepository` are used only inside the two rewritten endpoints, and `test_refresh_poster_all_success` (line 542-553) does `patch("module.api.v1.bangumi.RSSRepository")` / `patch("module.api.v1.bangumi.TitleParser")`. Fixed by adding it to AC-C4-1 (previously only the "refetches" test was listed; the "_all_success" test was missed).
- MAJOR-C4-1 (4 tests in `test_services/test_poster.py` assert on `update`, all break) — **accepted in part, corrected in this revision**. Re-verified each of the 4 named tests individually: only `test_refresh_poster_success` and `test_refresh_poster_returns_message` actually `patch.object(poster_service.bangumi_repo, "update")` and assert on it; `test_refresh_poster_fetch_failure` and `test_refresh_poster_exception_handling` never patch or assert on `update` at all (their `fetch_poster` mock returns `None` / raises, so `update` is never reached in either the old or new code path). The review's literal claim that all 4 need an `update`→`update_simple` rewrite is overbroad. What those two tests *do* need, which the review didn't name, is a one-line `bangumi.rss_id = None` fixture tweak so the new (unmocked) Mikan step in `PosterService.refresh_poster` doesn't make a live call through `self.rss_repo` against the raw `AsyncMock` session. AC-C4-4 above lists the corrected, per-test scope.
- MAJOR-C4-2 (hidden behavior change: TMDB exception propagation goes from uncaught-abort to caught-and-continue) — **accepted, fixed in this revision**. Re-verified: router's TMDB branches (bangumi.py:486-491, 533-538) have no try/except, while `PosterService.refresh_poster`'s existing body (poster.py:151-179) wraps everything in one blanket `try/except Exception`. The "Behavior change" section now states this exact divergence, and OD-C4-4 gives the owner a decision with a suggested default instead of asserting "no observable change."
- MINOR-C4-1 (diagnostic `logger.warning` line dropped from the Mikan except block) — **accepted, fixed in this revision**. The "Exact change" pseudocode for `services/poster.py` now includes `logger.warning(f"[Poster] Mikan parser failed for {_title}: {e}")` verbatim, matching both current router endpoints.
- MINOR-C4-2 (missing `import asyncio` / `TitleParser` import in the file-level change list) — **accepted, fixed in this revision**. Added both imports explicitly to the first bullet of `services/poster.py`'s "Exact change" list.
- MINOR-C4-3 (batch loop re-fetches each bangumi inside `PosterService.refresh_poster`, turning 1 query into N+1) — **accepted as a documented, deliberate cost, not fixed**. Re-verified: `PosterService.refresh_poster(bangumi_id)` does its own `bangumi_repo.get_by_id(bangumi_id)` even though the router's `get_all()` loop already holds the bangumi in memory. This is noted here rather than fixed because avoiding it means changing `PosterService.refresh_poster`'s signature to optionally accept a pre-loaded `Bangumi` — a public-interface change to the very method both endpoints call, for a performance cost that is one extra indexed primary-key lookup per bangumi in an admin-triggered, infrequent, already-serial (one `asyncio.to_thread` per bangumi) batch endpoint. Not worth the interface churn; flagged here as an accepted minor cost, consistent with the "smallest maintainable change" instruction. No owner decision needed — this is a performance note, not a behavior change.

---

### Overlap note

C4's new `PosterService.refresh_poster` calls `TitleParser().mikan_parser_with_rss(...)` — the exact facade C7 keeps stable. C4 does not depend on C7's internal rework of *how* that facade computes its result (it only reads `.poster_link`), so the two candidates touch disjoint production files (`services/poster.py` + `api/v1/bangumi.py` for C4; `domain/parser/title_parser.py` + `domain/parser/analyser/*` for C7) and can be implemented and reviewed independently. Land C7 first anyway, since the task frames C4 as "using the C7 result," and it lets C4's new tests assert against the corrected (bug-fixed) Mikan output rather than the old broken one.

---

## G5-subscription

### Review notes

All three reviewer issues were re-verified against current code this run. None are rejected; all three are folded into the design below.

- **MAJOR (official_title-override tightening omitted from the table):** Confirmed. In `add_rss` today (`rss.py:128-142`), the title check only runs `if not official_title` — supplying any `official_title` override skips it unconditionally, and `find_by_any_rss_link` (`rss.py:144-159`) is a raw substring match on URL text (`func.instr(Bangumi.rss_link, rss_link) > 0`), so two Mikan URLs with different text but the same `(bangumiId, subgroupid)` (e.g. `mikanani.me` vs `mikanime.tv` host alias — both match `_MIKAN_RSS_RE` in `mikan/parser.py:34-37`) never collide today. Point 3 of "Exact change" runs the new identity check for every Mikan-sourced request regardless of `official_title`, so this exact input flips 200→409. Fixed below: added as a table row, folded into OD-C6-1, and given its own acceptance criterion (AC-C6-7) with a message-content assertion.
- **MINOR (`SeriesRepository.get_all` doesn't exist):** Confirmed by reading `repositories/series.py` — its only reads are `get_by_id`, `get_by_mikan_id`, `get_by_fallback`, `find_possible_cross_source_merge`, `find_by_canonical_title`, `list_paginated`, `list_pending_review`. Fixed: AC-C6-6 now points at `list_paginated(limit=.., offset=0)`'s returned `total`, an existing method, instead of inventing a call.
- **MINOR (lazy-load reliance on `existing.series` in the new 409 message):** Confirmed by reading `bangumi.py:394-406` — `get_by_series_and_subgroup` has no `.options(selectinload(Bangumi.series))`, unlike `get_by_id`, `get_all`, `get_active`, `get_pending_review`, `get_by_rss`, and `find_by_any_rss_link` in the same file, all of which carry that option for the same reason. Fixed below: the eager-load option is added directly to `get_by_series_and_subgroup` itself (one line, in `bangumi.py`, matching the file's own convention) rather than patched around in the new function — this fixes it for *both* existing callers (`collector.py`'s `subscribe_season`) and the new `find_conflicting_mikan_subscription`, with no behavior change (it only changes how the relationship is loaded, not what it returns). `backend/src/module/repositories/bangumi.py` is added to files_to_change for this one-line addition. AC-C6-7 (new) also asserts the 409 body's `msg_en`/`msg_zh` content, and a new repository test asserts `.series` is accessible without a lazy-load error.

### C6 · Share one read-only "already subscribed" identity check between `add_rss` and `subscribe_season`

**Outcome:** Mikan-sourced duplicate detection in `add_rss` and `subscribe_season` uses the same rule (same series + same `mikan_subgroup_id`, rejected only when it belongs to a different RSS). The rule is read-only: it never creates a `Series` row, so a rejected `add_rss` request leaves no trace. Non-Mikan duplicate handling in each endpoint is untouched. `subscribe_batch` is untouched (out of scope).

#### Verified facts (re-checked now, this run)

- `add_rss` (`backend/src/module/api/v1/rss.py:93-219`) duplicate checks, both read-only, both run **before** `rss_repo.create()` (line 161) and before any `Series`/`Bangumi` row exists:
  - `SeriesRepository.find_by_canonical_title(data.official_title)` (`series.py:77-90`, case-insensitive text match, **no season/source awareness**) → 409, only when the caller did **not** pass `official_title` (`rss.py:129-142`).
  - `BangumiRepository.find_by_any_rss_link(rss_links)` (`bangumi.py:182-197`, SQL `instr` substring match against every non-deleted `Bangumi.rss_link`) → 409, unconditionally (`rss.py:144-159`).
  - The title check is legacy, not a deliberate season-aware design: it was disabled in Plan 04 Task 12 and "re-enabled" verbatim in Plan 05 Task 10 (`docs/superpowers/plans/2026-04-18-05-pipeline-wiring-and-api.md:1143-1183`) purely to restore pre-refactor behavior after `Bangumi.official_title` moved to `Series.canonical_title`.
- `subscribe_season` (`backend/src/module/services/collector.py:263-390`):
  - Calls `resolve_series_for_rss` (`identity_resolver.py:134-171`) which **creates** a `Series` row on a Tier-1/Tier-2 miss (`identity_resolver.py:90-131`, Tier 3).
  - Then picks the conflict check by source: Mikan → `BangumiRepository.get_by_series_and_subgroup(_series_id, _mikan_subgroup_id)` (`collector.py:367-369`, `bangumi.py:394-406`); non-Mikan fallback → `get_by_series_and_rss(_series_id, data.rss_id)` (`collector.py:371-373`, `bangumi.py:408-425`).
  - Rejects (`raise ValueError` → caller maps to 409, `rss.py:648-653`) only `if existing_active and existing_active.rss_id != data.rss_id` (`collector.py:375`).
  - **Traced, no live bug today:** a Tier-3 "miss" always creates a *brand-new* `series_id`, which by construction cannot already have a bangumi row under it — so `existing_active` is always `None` right after a fresh creation. `resolve_series_for_rss` never wastes a `Series` row on a request that `subscribe_season` goes on to reject. The "don't create on reject" requirement matters only because the *shared* predicate will also be called from `add_rss`, which must stay fully read-only (it has no transaction to roll back a stray `Series` row inside).
  - **The non-Mikan fallback branch is an intentional no-op, not a bug to fix here.** `get_by_series_and_rss(series_id, data.rss_id)` is looked up *by* `data.rss_id`, so `existing_active.rss_id != data.rss_id` can never be true for a row it just found by that same `rss_id`. This is confirmed as deliberate, tested, documented behavior in `backend/src/tests/test_services/test_collector.py:294-361` (`test_subscribe_season_duplicate_from_different_rss`): *"duplicate detection via composite key is disabled... acceptable post-0008 behavior; duplicate prevention is handled at the DB UNIQUE index level"* — see the partial unique indexes on `Bangumi` (`domain/models/bangumi.py:24-45`: `uq_bangumi_series_subgroup` for Mikan rows, `uq_bangumi_series_rss_fallback` for fallback rows). C6 must not change this; it is someone else's accepted decision, not this candidate's problem.
  - **Coverage gap found:** no existing test actually exercises the Mikan-branch *reject* path (a genuine `mikan_subgroup_id` conflict raising the `ValueError`). Grepped `test_collector.py`, `test_rss.py`, all `test_e2e/*.py` — none construct two Mikan RSS links with the same `bangumiId`+`subgroupid` and assert the 409. A baseline test for this exact branch must be added before refactoring it (see Acceptance criteria).
- `IdentityResolver` (`identity_resolver.py:61-131`) has **no** lookup-only path today — `resolve()` always creates on a Tier-1/2 miss (Tier 3). Confirms the task's suspicion: a new read-only function is needed, there's nothing to reuse as-is.
- `BangumiRepository.find_by_any_rss_link` and `SeriesRepository.find_by_canonical_title` each have exactly one caller (`rss.py`), as the task stated — grep-confirmed.
- `BangumiRepository.get_by_series_and_subgroup` (`bangumi.py:394-406`) has **no** `selectinload(Bangumi.series)` option, unlike `get_by_id`, `get_all`, `get_active`, `get_pending_review`, `get_by_rss`, and `find_by_any_rss_link` in the same file — re-verified this run, grep for `selectinload` in `bangumi.py` shows every other series-touching read method carries it, this one doesn't.
- WebUI caller (`webui/src/components/ab-add-rss.vue:166-196`, `webui/src/api/rss.ts:20-48`): the **only** call site of `apiRSS.add` in the whole webui always passes `{ skipBangumi: true }` (`ab-add-rss.vue:195`), unconditionally, for every new RSS (aggregate or not). `skip_bangumi=True` takes the early-return branch (`rss.py:113-122`) that never reaches either duplicate check. **The non-aggregate duplicate-check block this candidate changes is currently unreachable from the webui.** Real bangumi creation from the UI goes through `apiDownload.subscribe` → `POST /rss/subscribe` → `subscribe_season`. The webui's `DuplicateError` type (`ab-add-rss.vue:129-143`, expects `error_type: 'duplicate_official_title' | 'duplicate_rss_link'` and `existing_bangumi`) is never satisfied by the current 409 payloads either way (`rss.py:134-142`/`154-159` send only `status/status_code/msg_en/msg_zh`) — this mismatch is pre-existing and outside C6; it does not block or get fixed by this change (see OD-C6-2).
- `extract_mikan_ids_from_rss` matching is purely regex-based on URL text (`mikan/parser.py:34-56`, `_MIKAN_RSS_RE` accepts host aliases `mikan(ani|ime)?.(me|tv)`), independent of `find_by_any_rss_link`'s raw substring match on the whole stored string — two URLs can carry identical `(bangumiId, subgroupid)` while being unrelated as text. This is the basis for the new MAJOR-issue table row below.

#### Exact change

1. **Add `selectinload(Bangumi.series)` to `get_by_series_and_subgroup`** in `backend/src/module/repositories/bangumi.py:394-406` (one line, `.options(selectinload(Bangumi.series))` on the existing `select(Bangumi)...` statement), matching the convention every other series-touching read method in this file already follows. Pure read-shape fix, same rows returned, no behavior change — benefits both the existing `subscribe_season` caller and the new function below, so the fix lives once, where both callers route through, not patched around in the new function.
2. **Add one read-only free function** in `backend/src/module/services/identity_resolver.py`, next to `resolve_series_for_rss`:
   ```python
   async def find_conflicting_mikan_subscription(
       session: AsyncSession, *, rss_link: str, exclude_rss_id: Optional[int],
   ) -> Optional[Bangumi]:
   ```
   Body: `extract_mikan_ids_from_rss(rss_link)` → if no `mikan_bangumi_id`, return `None`. Else `SeriesRepository(session).get_by_mikan_id(mikan_bangumi_id)` → if no `Series`, return `None` (this is the "lookup, don't create" fix: it stops at Tier 1/2, never falls through to Tier-3 `create`). Else `BangumiRepository(session).get_by_series_and_subgroup(series.id, mikan_subgroup_id or 0)`; return it only `if existing is not None and existing.rss_id != exclude_rss_id`, else `None`. Uses only existing repo read methods (`get_by_mikan_id`, `get_by_series_and_subgroup`, now eager-loading `.series` per point 1) — no new repo method, no new class.
3. **`collector.py` `subscribe_season`** (`collector.py:367-369`): replace the one line `existing_active = await bangumi_repo.get_by_series_and_subgroup(_series_id, _mikan_subgroup_id)` with `existing_active = await find_conflicting_mikan_subscription(session, rss_link=data.rss_link, exclude_rss_id=data.rss_id)`. Everything else in the method (ordering, `resolve_series_for_rss` call, the fallback `else` branch at `collector.py:371-373`, the `raise ValueError` at `collector.py:375-390`) is untouched. The new call independently re-derives the same `Series` row `resolve_series_for_rss` just resolved via the same Tier-1 lookup (`get_by_mikan_id`) — one extra cheap indexed SELECT, same answer, proven equivalent by the trace above.
4. **`rss.py` `add_rss`** (`rss.py:129-159`): before the existing title check, branch on `extract_mikan_ids_from_rss(data.rss_link or "")`:
   - Mikan-sourced (`mikan_bangumi_id is not None`): call `find_conflicting_mikan_subscription(session, rss_link=data.rss_link, exclude_rss_id=None)`; on a hit, return the same 409 shape as today (`msg_en`/`msg_zh` naming the conflicting bangumi's `series.canonical_title`, now safe to read — eager-loaded per point 1), skip `find_by_canonical_title` entirely. **This branch runs unconditionally for Mikan-sourced requests, whether or not the caller passed `official_title`** — this is the deliberate behavior change OD-C6-1 now covers in full (including the new tightening row in the table below).
   - Non-Mikan (`mikan_bangumi_id is None`): keep today's `if not official_title: find_by_canonical_title(...)` block exactly as-is.
   - `find_by_any_rss_link` check (`rss.py:144-159`) keeps running unconditionally afterward, for both branches, exactly as today — not touched.

#### Behavior change

- **None** for: `subscribe_season`'s fallback (non-Mikan) branch, `subscribe_batch`, `add_rss`'s non-Mikan branch, any WebUI-reachable flow (none of this code is reachable from the webui today — see Verified facts), `DownloaderProtocol`, `RenameOutcome`, EXCLUDED-sentinel handling, filter-is-exclusion-regex semantics, A-001's shared RSS selection / PikPak task rules.
- **Changed**, `add_rss` only, Mikan-sourced non-aggregate requests (owner sign-off: OD-C6-1, now covering relaxations (a)-(c) AND the tightening (d) below):

  | Example | Old `add_rss` result | New `add_rss` result |
  |---|---|---|
  | Add Mikan `bangumiId=100&subgroupid=1` ("Show A"), then add the exact same URL again | 409 (title match) | 409 (identity match) — unchanged outcome |
  | (a) Add `bangumiId=100&subgroupid=1` ("Show A"), then add `bangumiId=100&subgroupid=2` ("Show A", different fansub group) | 409 (title match blocks it) | 200 — now allowed, matches `subscribe_season`'s existing rule |
  | (b) Add `bangumiId=100` S1 ("Show A"), then add `bangumiId=200` S2 ("Show A", Mikan gives each season its own bangumiId) | 409 (title match blocks it) | 200 — now allowed |
  | (c) Add `bangumiId=100` ("Show A"), then add unrelated `bangumiId=300` whose parsed title also happens to be "Show A" (e.g. a remake) | 409 (title match blocks it) | 200 — no longer blocked at add time; only the DB layer / manual review catches it later |
  | Add `bangumiId=100&subgroupid=1` with `official_title` manually overridden, then add the same URL again with a different override | 409 (caught by `find_by_any_rss_link`, title check was already skipped) | 409 (caught by identity check) — unchanged outcome |
  | **(d) NEW — tightening:** Add `https://mikanani.me/RSS/Bangumi?bangumiId=100&subgroupid=1` with `official_title="X"` override. Then add `https://mikanime.tv/RSS/Bangumi?bangumiId=100&subgroupid=1` (same ids, different host text, no substring overlap) with `official_title="Y"` override. | 200 (title check skipped because `official_title` present; `find_by_any_rss_link` is a text substring check and the two URLs share no substring, so it never fires) | **409** — the identity check runs regardless of `official_title` and matches on `(bangumiId, subgroupid)`, not URL text |

#### Owner decisions (restated to cover the tightening)

- **OD-C6-1** now explicitly covers four effects, not three: (a) second fansub group allowed, (b) second season allowed, (c) two unrelated same-titled Mikan shows allowed, and **(d) a `official_title`-overridden Mikan request that today silently succeeds against a differently-worded duplicate URL now gets a 409 instead.** Net effect restated: add_rss's Mikan-sourced duplicate rule becomes identity-based (same show+fansub-group) instead of text-based (title string / URL substring), in both directions — it relaxes where text differed but identity matched, and it tightens where text differed and identity also matched but text-based checks happened to miss it. Default: adopt all four — (a)/(b) are the explicit goal (subscribe_season already allows them); (d) is the direct, intended consequence of making the rule identity-based instead of text-based, not a side effect to special-case around; (c) and (d) are both narrow because the webui never exercises this code path today (see Verified facts), so no live user journey changes.

#### Invariants

- **INV-C6-1** — Start: `find_conflicting_mikan_subscription` is called with any `(rss_link, exclude_rss_id)`. Preserved: the function never calls `SeriesRepository.create`, `BangumiRepository.create`, or `resolve_series_for_rss`/`IdentityResolver.resolve` (which do create) — directly or transitively. Failure: any future edit adds such a call inside this function or a helper it calls.
- **INV-C6-2** — Start: a non-Mikan (`extract_mikan_ids_from_rss` returns `(None, None)`) request to `subscribe_season`. Preserved: `existing_active` for that request is computed exactly as today (via `get_by_series_and_rss(_series_id, data.rss_id)`), and the method never raises `ValueError` for a cross-RSS fallback duplicate — this stays a DB-UNIQUE-index-only guarantee, per `test_subscribe_season_duplicate_from_different_rss`. Failure: that test starts failing, or a new check makes `subscribe_season` raise for a fallback-tier cross-RSS duplicate.
- **INV-C6-3** — Start: any non-aggregate, non-`skip_bangumi` `add_rss` request. Preserved: `BangumiRepository.find_by_any_rss_link` is still called, unconditionally, with the same `rss_links` split, for both Mikan and non-Mikan inputs. Failure: a code path reaches the `new_rss = await rss_repo.create(...)` line without that call having run first.
- **INV-C6-4** — Start/Preserved: no change to `EXCLUDED`-state filtering, filter-is-exclusion-regex semantics, A-001's shared selection rule, `DownloaderProtocol`, `RenameOutcome`, or any file outside `identity_resolver.py` / `collector.py` / `rss.py` / `repositories/bangumi.py` (the last limited to the one `selectinload` addition on `get_by_series_and_subgroup`, no logic change). Failure: a diff touches `rss_engine.py`, `downloader/`, `renamer.py`, `webui/`, or any other method in `bangumi.py`.

#### Acceptance criteria

- **AC-C6-1** (no-regression): `backend/src/tests/test_e2e/test_rss_management.py::TestAddRSS::test_add_duplicate_title_rejected` and `::test_add_duplicate_link_rejected` pass unmodified (same Mikan URL twice still 409).
- **AC-C6-2** (new, write failing-first against current code, then make it pass): add an e2e test, e.g. `test_add_same_mikan_show_different_subgroup_allowed` in `test_rss_management.py` — add a Mikan RSS for `bangumiId=X&subgroupid=1`, assert 200; add another for `bangumiId=X&subgroupid=2`, assert 200 (currently 409).
- **AC-C6-3** (new, failing-first): add an e2e test, e.g. `test_add_same_title_different_mikan_season_allowed` — add `bangumiId=X`, assert 200; add `bangumiId=Y` whose parsed `official_title` matches, assert 200 (currently 409).
- **AC-C6-4** (no-regression, non-Mikan untouched): `backend/src/tests/test_api_contract/test_rss.py::TestAddRSS::test_add_rss_rejects_duplicate_series_title` passes unmodified — it stubs `mock_data.rss_link = None`, so it already exercises the non-Mikan branch, which is untouched by this change.
- **AC-C6-5** (baseline-first for the behavior-preserving refactor of `subscribe_season`): before editing `collector.py`, add a test to `test_collector.py`, e.g. `test_subscribe_season_rejects_mikan_conflict_from_different_rss` — two Mikan RSS links sharing `bangumiId`+`subgroupid` but different `rss_id`, assert `subscribe_season` raises `ValueError` (this closes the coverage gap found above and is the pre-change baseline). Run it green on old code, then keep it green after the one-line swap. Existing `test_subscribe_season_success`, `test_subscribe_season_recreate_same_rss`, `test_subscribe_season_recovers_from_stale_rss_id`, `test_subscribe_season_duplicate_from_different_rss` must all still pass unmodified.
- **AC-C6-6** (new unit tests for the extracted function, FIXED — no `get_all` method exists on `SeriesRepository`): in `test_identity_resolver.py`, add direct tests for `find_conflicting_mikan_subscription`: non-Mikan `rss_link` → `None`; Mikan `rss_link` with no matching `Series` yet → `None` (and assert no `Series` row was created, by comparing `SeriesRepository(session).list_paginated(limit=1000, offset=0)`'s returned `total` before and after — an existing method, not a new one); Mikan `rss_link` matching an existing `Series`+subgroup under a *different* `rss_id` → returns that `Bangumi`; same `Series`+subgroup under the *same* `exclude_rss_id` → `None` (self-match is not a conflict).
- **AC-C6-7** (NEW, covers the MAJOR fix — the tightening row (d) above, with message-content assertion covering the MINOR eager-load fix): add an e2e test to `test_rss_management.py`, e.g. `test_add_mikan_conflict_across_different_host_text_rejected_with_override` — add `https://mikanani.me/RSS/Bangumi?bangumiId=X&subgroupid=1` with `official_title` override, assert 200; add `https://mikanime.tv/RSS/Bangumi?bangumiId=X&subgroupid=1` (same ids, no text overlap) with a *different* `official_title` override, assert 409, and assert the response's `msg_en`/`msg_zh` contains the first request's resolved series title (not just the status code — this is what would have silently broken, or silently passed for the wrong reason, under the pre-fix lazy-load reliance on `existing.series`).
- **AC-C6-8** (NEW, repository-level regression for the eager-load fix): in `backend/src/tests/test_repositories/test_bangumi_series_helpers.py`, add `test_get_by_series_and_subgroup_eager_loads_series` — seed a `Series` + matching `Bangumi`, call `get_by_series_and_subgroup`, then access `hit.series.canonical_title` directly (no further `await`/refresh). Without the `selectinload` fix this either raises a greenlet/lazy-load error under `AsyncSession` or depends on incidental identity-map ordering from an earlier call in the same test; with the fix it is a plain attribute read.

#### Minimality check

- Smallest outcome: one new free function (not a class, not a new repo method) reusing two existing repo reads (`get_by_mikan_id`, `get_by_series_and_subgroup`); one line swapped in `subscribe_season`; one branch added in `add_rss` ahead of its existing title check; one `selectinload` option added to an existing repo method to match its own file's convention. No new file, no new dependency, no schema/migration change.
- Simpler alternative considered and rejected: inlining the same ~6 lines separately in both `add_rss` and `subscribe_season` instead of a shared function — rejected because the task explicitly asks for *one* rule both paths share, and a duplicated inline copy is exactly the drift this candidate exists to remove.
- Simpler alternative considered and rejected: reusing `resolve_series_for_rss` directly from `add_rss` (zero new code) — rejected because it creates a `Series` row as a side effect of a request that may then be rejected by the `find_by_any_rss_link` check that runs after it; that is precisely the hazard the task called out and the invariant (INV-C6-1) that must hold for `add_rss`, which has no surrounding rollback for a stray `Series` insert before `rss_repo.create()`/`session.commit()`.
- Simpler alternative considered and rejected (for the eager-load fix): patching it locally inside `find_conflicting_mikan_subscription` only (e.g. a second query, or returning the `Series` alongside) — rejected because `subscribe_season`'s existing call to the same repo method has the identical latent fragility (it just happens not to read `.series` today), and the file already has an established convention (`selectinload` on every series-touching read) that this method alone was missing. Fixing it at the repo method fixes it for every caller, present and future, in one place — the smaller, more local patch would leave the shared method still broken for its original caller.
- Larger alternative considered and rejected: also "fixing" the non-Mikan fallback no-op in `subscribe_season`, or folding `subscribe_batch` into the same predicate — rejected: the fallback no-op is a documented, tested, accepted design decision (`test_subscribe_season_duplicate_from_different_rss`), not part of this candidate's ask; `subscribe_batch` has a different transaction shape (whole-RSS recreation) and was not named in C6 — both parked as separate proposals, not touched.
- Why each part is needed: the new function is needed because `IdentityResolver` has no lookup-only path (verified); the `add_rss` branch is needed because the task explicitly authorizes and asks for this exact behavior change (now including the tightening, signed off via OD-C6-1); the one-line `collector.py` swap is needed to make the rule actually *shared* rather than merely duplicated-but-equivalent; the `selectinload` line is needed because the shared predicate's result (`existing.series.canonical_title`) is read directly in a user-facing error message, and the file's own convention for every other series-touching read already carries it.

Self-check: 11 candidates covered (C1-C11); behavior changes listed only under owner decisions; no source or test edited for this design; tests named here are not yet run except the recorded G1 baseline.
