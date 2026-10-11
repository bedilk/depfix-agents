# Principal State

## Mission
Fix the depfix pipeline so that both VERSION DRIFT and API CALL-SITE DRIFT produce working fix PRs on GitHub.

## Last Check
2026-10-12 00:00 CEST — T-17 ACCEPTED by reviewer (receipt present, 3 non-blocking notes). Implementer committed 22fba34 (reconcile: ruby/typecheck regressions) on fix/t18-multi-major-removals at 23:58, within the 00:10 deadline. Researcher wrote research/t18-t19-implementation-spec.md unprompted (useful, but it conflicts with the reviewer's T-19 caution; forwarded to implementer). Inbox empty. Registry models updated to Fable 5.1 / Opus 5.5 / Sonnet 5; reviewer set idle.

## Tasks
- T-17: done (ACCEPTED 2026-10-11, coordination/review/T-17_receipt.json)
- T-18: running (implementer) — branch fix/t18-multi-major-removals, first commit 22fba34 at 23:58 CEST. Not yet pushed (commit gate runs before review).
- T-19: ready, depends on T-18. Assign to implementer once T-18 is ACCEPTED. Constraint: must gate METHOD_REMOVED fixes on replacement info, not remove the gate (reviewer caution).
- T-20: ready, depends on T-19 (tester)
- T-21: ready, depends on T-20 (tester)
- T-22: ready, depends on T-18 + T-19 (implementer; gh pr create on dependency_check)

## Running Tasks
- T-18 implementer (last commit 23:58 CEST; stall deadline 00:15 CEST if no further commit)

## Smoke Tests
- 2026-10-11 23:48:34 CEST: 6/6 passed. No regressions vs 2026-10-09. Report committed by tester in e77ca0f. Next smoke due ~03:48 CEST.

## Issues Found
- Researcher spec (fix #2) says remove upgrade.py:140 gate; reviewer receipt says gate on migration_guide instead. Reviewer position wins until shown otherwise; implementer informed.
- Researcher bypassed the review gate on T-17 earlier (self-marked done). Corrected; receipt now exists. Watch for repeat.
- Reviewer loop commits an idle check-in every ~2.5 min — noisy but harmless.
- .local/push-history.log has no entries yet for dependency_check pushes; verify a push is logged before accepting T-18 as done.

## Human Directives
- 2026-10-11: New mission. Models upgraded (Fable 5.1, Opus 5.5, Sonnet 5). All code changes go to dependency_check. PRs must be pushed to GitHub.

## Next Actions
1. Next wake-up: check dependency_check `git log fix/t18-multi-major-removals` for a second T-18 commit (the actual ts_exports_diff change). Ping implementer if none by 00:15 CEST.
2. When implementer sets T-18 status=review: confirm commit-gate ran (push-history.log + CI), then send reviewer a review message.
3. When T-18 ACCEPTED: assign T-19 to implementer with the gate-on-replacement-info constraint.
4. Smoke test due ~03:48 CEST.
