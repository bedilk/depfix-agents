# Principal State

## Mission
Fix the depfix pipeline so that both VERSION DRIFT and API CALL-SITE DRIFT produce working fix PRs on GitHub.

## Last Check
2026-10-11 23:51 CEST — T-17 in progress (researcher actively writing). Smoke 6/6 passed. No stalls.

## Tasks
- T-17: running (researcher) — assigned 2026-10-11 23:48 CEST. Draft research/plan-zero-pr-root-cause.md exists (218 lines, modified 23:50), not yet committed. Draft identifies 3 root causes: METHOD_REMOVED→REPORT_ONLY, no multi-major BreakingChange records, plan never captures drift without prior scan.
- T-18: ready, depends on T-17 (fix ts_exports_diff for multi-major)
- T-19: ready, depends on T-17 + T-18 (fix plan to generate PRs)
- T-20: ready, depends on T-19 (e2e test on test repos)
- T-21: ready, depends on T-20 (real-repo validation)
- T-22: ready, depends on T-18 + T-19 (push PR to GitHub)

## Running Tasks
- T-17 researcher (started 23:48 CEST, draft on disk at 23:50, no commit yet — stall deadline 00:03 CEST)

## Smoke Tests
- 2026-10-11 23:48:34 CEST: 6/6 passed (stripe, openai, elasticsearch x2, octokit, anthropic). No regressions vs 2026-10-09. Report: research/smoke-20261011-234429.md (still untracked — tester must commit it).

## Issues Found
- Researcher inbox note (2026-10-10): _augment_with_repo_exports wiring missing from dependency_check runner.py; folded into T-17 scope item (3). Note: dependency_check working tree has uncommitted edits to runner.py, evals/*, providers.yaml, Makefile — implementer must reconcile before T-18.
- dependency_check has had no commits since 2026-10-07.
- Reviewer loop commits an idle check-in every ~2.5 min — noisy but harmless.
- Smoke report files from 2026-10-09 and 2026-10-11 are untracked in research/.

## Human Directives
- 2026-10-11: New mission. Models upgraded (Fable 5.1, Opus 5.5, Sonnet 5). All code changes go to dependency_check. PRs must be pushed to GitHub.

## Next Actions
1. Next wake-up: verify researcher committed T-17 and set status=review; ping if no commit by 00:03 CEST.
2. When T-17 is reviewed/accepted: assign T-18 to implementer (include researcher's 3 root causes and the uncommitted runner.py diff in dependency_check).
3. Ask tester to commit untracked smoke reports.
