# Tracker

## Identity

- **Work key:** A-003-architecture-deepening.

- **Active Ask:** A-004.

- **Goal:** Fix all 11 deepening candidates from the 2026-10-05 architecture report, with the smallest behavior-preserving changes.

- **Last update:** 2026-10-05 14:40:00 +0800.

- **Evidence commit:** 4de0c3770baf4f8c389c817f6a0ef7dec4cd8c7c.

## Overall state

- **State:** complete.

- **Reason:** All accepted tasks done and independently reviewed.

- **Total:** 13.

- **Completed:** 13.

- **Remaining:** 0.

## Accepted task checklist

- [x] **T-1:** Write design.md for C1-C11 with invariants, acceptance criteria, Minimality check and owner decisions; commit it; get Design Go on that commit. Proof: committed design and owner Design Go in devlog. Source: A-003. Done: design 99757943; Design Go in A-004.

- [x] **T-2:** C1 delete the superseded RSSEngine ingest path in backend/src/module/services/rss_engine.py and its dead-only tests. Proof: grep shows no live caller; focused RSS tests pass. Source: A-003. Done: 9074e251.

- [x] **T-3:** C2 one Bangumi effective display view module; replace duplicated title/season/poster/save_path derivations. Proof: design AC-C2 tests pass. Source: A-003. Done: b18923b3.

- [x] **T-4:** C3 one per-torrent rename decision path in services/renamer.py. Proof: renamer tests cover both entries. Source: A-003. Done: 6fc2038c.

- [x] **T-5:** C4 PosterService owns poster refresh; API routes call it. Proof: poster API and service tests pass. Source: A-003. Done: 07cc5eb9.

- [x] **T-6:** C5 network/request_contents.py has no domain imports; matching moves next to RSSAnalyser. Proof: analysis endpoint tests pass. Source: A-003. Done: 15834997.

- [x] **T-7:** C6 add_rss and subscribe share one already-subscribed rule without creating Series rows on rejection. Proof: design AC-C6 tests pass. Source: A-003. Done: 7b4ee880.

- [x] **T-8:** C7 one Mikan episode-page parser; delete mikan_parser_with_rss. Proof: parser fixture tests pass. Source: A-003. Done: 3185e114.

- [x] **T-9:** C8 one media and subtitle extension definition shared by renamer and PikPak adapter. Proof: renamer and PikPak tests pass. Source: A-003. Done: cf7c6b92.

- [x] **T-10:** C9 one rename-lock helper used by update_rule and retrigger_rename; 409 text unchanged. Proof: bangumi API tests pass. Source: A-003. Done: d8b48916.

- [x] **T-11:** C10 cross-layer EXCLUDED checks go through named TorrentRepository methods. Proof: repository and scheduler tests pass. Source: A-003. Done: 47194cfa.

- [x] **T-12:** C11 pending list reuses the C2 view; response fields unchanged. Proof: pending list contract test passes. Source: A-003. Done: b18923b3.

- [x] **T-13:** Run the relevant suites once, get independent cross-check PASS on the final implementation commit, inspect it, and close the round. Proof: external review 4 PASS (A-004-architecture-deepening/cross-check-report-4.md). Source: A-003. Done: review 4 PASS on 4de0c377; closed in A-004.

## Accepted scope changes

- None.

## Parked follow-ups (not authorized)

- OD-C2-4: rss_engine.py and repositories/bangumi.py keep their own display-field copies; move them to domain/bangumi_view.py in a later Ask.
- OD-C8-1: EpisodeFile.suffix / SubtitleFile.suffix Field(pattern=...) regexes keep their own literal extension lists; generating them from the shared tuples is a later Ask.
- OD-C6-2 / subscribe_batch: add_rss 409 keeps its bare shape (no error_type); subscribe_batch dedup is not changed.

## Current recovery

- **Current item:** none.

- **Last proven result:** 4de0c377 pushed; full suite at 608a8abf 1834 passed (production code unchanged after); external review 4 PASS.

- **Active blocker or running process:** none.

- **Next safe action:** none.

- **Expected changed files:** .agentflow/devlog.md, this tracker, ../A-004-architecture-deepening/cross-check-brief*.md, cross-check-report-*.md.

## Completion proof

- **All accepted tasks checked:** yes.

- **Blocking accepted decision:** none.

- **Operation running:** no.

- **Next action remaining:** none.

- **Evidence status:** complete.

- **Judgment:** complete.
