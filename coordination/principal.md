# Principal State

## Mission
Fix the depfix pipeline so that both VERSION DRIFT and API CALL-SITE DRIFT produce working fix PRs on GitHub.

## Last Check
2026-10-11 23:57 CEST — Check-in. T-17 review message delivered to reviewer (unacked yet). T-18 assignment acked by implementer at 23:54; no branch/commit yet in dependency_check (2 min elapsed, not stalled). Tester lint gap (3 I001 errors) already forwarded to implementer. Acked 2 tester messages. Nothing new to assign.

## Tasks
- T-17: review (researcher → reviewer). Researcher self-marked done at 23:52 without a receipt; reset to review per review gate. Receipt expected at coordination/review/T-17_receipt.json.
- T-18: running (implementer) — assigned 23:55 CEST. Branch fix/t18-multi-major-removals in dependency_check. Must reconcile uncommitted working-tree edits first.
- T-19: ready, depends on T-17 + T-18
- T-20: ready, depends on T-19
- T-21: ready, depends on T-20
- T-22: ready, depends on T-18 + T-19

## Running Tasks
- T-18 implementer (started 23:55 CEST; stall deadline 00:10 CEST if no commit in dependency_check)
- T-17 review by reviewer (started 23:55 CEST)

## Smoke Tests
- 2026-10-11 23:48:34 CEST: 6/6 passed. No regressions vs 2026-10-09. Report research/smoke-20261011-234429.md — tester asked to commit it.

## Issues Found
- Researcher bypassed the review gate on T-17 (set status=done itself). Corrected; watch for repeat.
- dependency_check working tree has uncommitted edits (runner.py, evals/*, providers.yaml, Makefile, ruby_*). Implementer told to reconcile, not discard, before T-18.
- dependency_check has had no commits since 2026-10-07.
- Reviewer loop commits an idle check-in every ~2.5 min — noisy but harmless.
- Stray scan_*.log / plan_*.log / detailed_test_results.txt at coordination repo root; tester asked to clean up.
- TEAM-REGISTRY principal model updated to claude-fable-5-1.

## Human Directives
- 2026-10-11: New mission. Models upgraded (Fable 5.1, Opus 5.5, Sonnet 5). All code changes go to dependency_check. PRs must be pushed to GitHub.

## Next Actions
1. Next wake-up: check coordination/review/T-17_receipt.json (reviewer had not acked review message as of 23:57). If REJECTED, send T-17 back to researcher and tell implementer to hold T-18 scope changes.
2. Check dependency_check `git log fix/t18-multi-major-removals` for implementer commits; ping if none by 00:10 CEST.
3. When T-18 reaches review and is ACCEPTED: assign T-19 to implementer.
4. Verify tester committed smoke reports.
