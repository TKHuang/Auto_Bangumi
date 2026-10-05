# Tracker

## Identity

- **Work key:** A-003-architecture-deepening.

- **Active Ask:** A-003.

- **Goal:** Fix all 11 deepening candidates from the 2026-10-05 architecture report, with the smallest behavior-preserving changes.

- **Last update:** 2026-10-05 11:50:00 +0800.

- **Evidence commit:** uncommitted.

## Overall state

- **State:** active.

- **Reason:** Work remains.

- **Total:** 13.

- **Completed:** 0.

- **Remaining:** 13.

## Accepted task checklist

- [ ] **T-1:** Write design.md for C1-C11 with invariants, acceptance criteria, Minimality check and owner decisions; commit it; get Design Go on that commit. Proof: committed design and owner Design Go in devlog. Source: A-003.

- [ ] **T-2:** C1 delete the superseded RSSEngine ingest path in backend/src/module/services/rss_engine.py and its dead-only tests. Proof: grep shows no live caller; focused RSS tests pass. Source: A-003.

- [ ] **T-3:** C2 one Bangumi effective display view module; replace duplicated title/season/poster/save_path derivations. Proof: design AC-C2 tests pass. Source: A-003.

- [ ] **T-4:** C3 one per-torrent rename decision path in services/renamer.py. Proof: renamer tests cover both entries. Source: A-003.

- [ ] **T-5:** C4 PosterService owns poster refresh; API routes call it. Proof: poster API and service tests pass. Source: A-003.

- [ ] **T-6:** C5 network/request_contents.py has no domain imports; matching moves next to RSSAnalyser. Proof: analysis endpoint tests pass. Source: A-003.

- [ ] **T-7:** C6 add_rss and subscribe share one already-subscribed rule without creating Series rows on rejection. Proof: design AC-C6 tests pass. Source: A-003.

- [ ] **T-8:** C7 one Mikan episode-page parser; delete mikan_parser_with_rss. Proof: parser fixture tests pass. Source: A-003.

- [ ] **T-9:** C8 one media and subtitle extension definition shared by renamer and PikPak adapter. Proof: renamer and PikPak tests pass. Source: A-003.

- [ ] **T-10:** C9 one rename-lock helper used by update_rule and retrigger_rename; 409 text unchanged. Proof: bangumi API tests pass. Source: A-003.

- [ ] **T-11:** C10 cross-layer EXCLUDED checks go through named TorrentRepository methods. Proof: repository and scheduler tests pass. Source: A-003.

- [ ] **T-12:** C11 pending list reuses the C2 view; response fields unchanged. Proof: pending list contract test passes. Source: A-003.

- [ ] **T-13:** Run the relevant suites once, get independent cross-check PASS on the final implementation commit, inspect it, and close the round. Source: A-003.

## Accepted scope changes

- None.

## Current recovery

- **Current item:** T-1.

- **Last proven result:** design.md written (C1-C11, 18 owner decisions); G1 baseline 88 passed on old code.

- **Active blocker or running process:** None.

- **Next safe action:** wait for owner Design Go on the design commit and answers to OD-* decisions in design.md.

- **Expected changed files:** .agentflow/devlog.md, .agentflow/artifacts/A-003-architecture-deepening/tracker.md, .agentflow/artifacts/A-003-architecture-deepening/design.md.

## Completion proof

- **All accepted tasks checked:** no.

- **Blocking accepted decision:** Design Go.

- **Operation running:** no.

- **Next action remaining:** T-1.

- **Evidence status:** current.

- **Judgment:** active.
