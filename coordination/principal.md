# Principal State

## Mission
Fix the depfix pipeline so that both VERSION DRIFT and API CALL-SITE DRIFT produce working fix PRs on GitHub.

## Last Check
2026-10-11 23:48 CEST — all agents were idle, T-17 unassigned. Dispatched.

## Tasks
- T-17: running (researcher) — assigned 2026-10-11 23:48 CEST. Watch for commit in research/ within 15 min.
- T-18: ready, depends on T-17 (fix ts_exports_diff for multi-major)
- T-19: ready, depends on T-17 + T-18 (fix plan to generate PRs)
- T-20: ready, depends on T-19 (e2e test on test repos)
- T-21: ready, depends on T-20 (real-repo validation)
- T-22: ready, depends on T-18 + T-19 (push PR to GitHub)

## Running Tasks
- T-17 researcher (started 2026-10-11 23:48 CEST, no commit yet — expected)
- Smoke test triggered to tester (last smoke 2026-10-09 15:02, 6/6 passed; >4h old)

## Issues Found
- TEAM-REGISTRY showed implementer still on T-16, but T-16 no longer exists in TASKS.json (old mission). Reset implementer to idle.
- Researcher inbox note (2026-10-10): _augment_with_repo_exports wiring missing from dependency_check runner.py; repo_exports.py is dead code there. Folded into T-17 scope item (3).
- dependency_check has had no commits in the last 6 hours.

## Human Directives
- 2026-10-11: New mission. Models upgraded (Fable 5.1, Opus 5.5, Sonnet 5). All code changes go to dependency_check. PRs must be pushed to GitHub.

## Next Actions
1. Next wake-up: verify researcher committed progress on T-17; ping if no commit after 15 min.
2. When T-17 reaches review and reviewer accepts: assign T-18 to implementer.
3. Record smoke test result when tester reports.
