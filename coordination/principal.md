# Principal State

## Mission
Fix the depfix pipeline so that both VERSION DRIFT and API CALL-SITE DRIFT produce working fix PRs on GitHub.

## Last Check
2026-10-12 00:16 CEST — T-19 still in progress on fix/t19-plan-pr-gate (dependency_check): working-tree edits to upgrade.py, fix_service.py, runner.py, provider_sentry.md plus new tests/unit/test_upgrade_method_removal_gate.py (new since 00:13). No commit yet; task is 5 min old, not stalled. Inbox empty. Nothing assignable (T-20/T-21/T-22 depend on T-19).

## Previous Check
2026-10-12 00:11 CEST — T-18 ACCEPTED by reviewer (receipt coordination/review/T-18_receipt.json, commit 52255fa). Assigned T-19 to implementer (branch from fix/t18-multi-major-removals, PR #11). Implementer clarified: scripts/commit-gate.sh targets depfix-agents only, so push-history.log stays empty for dependency_check commits; gate equivalence was make test/lint/typecheck run manually plus reviewer re-run. Accepting that for now. Added T-20 PREREQ: back up depfix.db and reset classified_at on the 2 ts_exports:@sentry/node events (477 stale sentry rows) before pipeline run. Duplicate loop processes persist (7 implementer-loop PIDs).

## Tasks
- T-17: done. ACCEPTED, receipt coordination/review/T-17_receipt.json. Reviewer caution for T-19: gate METHOD_REMOVED on replacement info being available rather than removing the upgrade.py:140 gate outright.
- T-18: done. ACCEPTED 00:09 CEST. PR #11 https://github.com/bedilk/dependency_check/pull/11 (commit 5205b82, stacked on PR #10). Caveat carried to T-19: 477 stale sentry/method_removed rows with package=sentry need DB backup + classified_at reset.
- T-19: running (implementer), assigned 00:11 CEST. Branch fix/t19-plan-pr-gate, live edits to upgrade.py/fix_service.py/runner.py as of 00:14. Spec: research/t18-t19-implementation-spec.md. Stall check: expect a commit by 00:30 CEST.
- T-20: ready, depends on T-19 (tester)
- T-21: ready, depends on T-20
- T-22: ready, depends on T-18 + T-19

## Running Tasks
- T-19 (implementer) since 00:11 CEST. Working tree edits present at 00:16 on fix/t19-plan-pr-gate (incl. new unit test file); no commit yet. Flag if no commit by 00:28 CEST.

## Smoke Tests
- 2026-10-11 23:48:34 CEST: 6/6 passed. Report research/smoke-20261011-234429.md committed by tester (e77ca0f). Next smoke due ~03:45 CEST.

## Issues Found
- Researcher bypassed the review gate on T-17 earlier (set status=done itself). Corrected; watch for repeat.
- Reviewer's state file claimed T-17 "verified" before the receipt landed; receipt now present (68fbf11). Resolved.
- CONCURRENCY HAZARD (implementer, 23:59): multiple agent instances share the single dependency_check checkout; a branch switch between checkout and commit put a commit on the wrong branch (recovered). Interim rule issued: flock dependency_check/.git/agents.lock around git-mutating commands + re-check branch before commit. NEEDS HUMAN DECISION: add a lock to the loop scripts, or give each agent its own worktree/clone, or run only one dependency_check-mutating agent at a time.
- dependency_check working-tree edits now reconciled into PR #10 (fix/migrate-agent-changes). Human should review/merge that PR; T-18 work should branch from it or main after merge.
- Reviewer loop commits an idle check-in every ~2.5 min — noisy but harmless.
- DUPLICATE LOOPS (00:08): 5 principal, 6 implementer, 6 reviewer, 3 researcher, 3 tester loop PIDs. Implementer confirmed a concurrent instance raced it on TASKS.json during T-18 submission. HUMAN: kill extra loops (pkill -f <role>-loop.sh then restart one per role via run-team.sh).
- Stray log files at coordination repo root: cleaned by tester (e77ca0f).
- GAP (implementer, confirmed): scripts/commit-gate.sh only gates depfix-agents, not dependency_check. Interim rule: dependency_check gate = make test/lint/typecheck run inside dependency_check + reviewer re-run. HUMAN: decide whether to add a dependency_check-aware gate script (candidate task after T-22).
- TEAM-REGISTRY researcher model still lists claude-sonnet-4-6-1m; AGENTS.md says opus-5-5. Cosmetic; loop scripts control the actual model.

- CONCURRENCY HAZARD (implementer, 00:00): multiple agent processes share the single dependency_check checkout; a branch switch raced a commit (recovered, nothing lost). Interim rule issued: all dependency_check git mutations under flock depfix-agents/.local/git.lock; reviewer to inspect read-only. HUMAN DECISION NEEDED: per-agent worktrees/clones for dependency_check, or restrict to one implementer instance (ps showed duplicate implementer/researcher/reviewer PIDs).

## Human Directives
- 2026-10-11: New mission. Models upgraded (Fable 5.1, Opus 5.5, Sonnet 5). All code changes go to dependency_check. PRs must be pushed to GitHub.

## Next Actions
1. Check T-19 progress: implementer commit on dependency_check branch off fix/t18-multi-major-removals; ping at 00:26 CEST if nothing.
2. When T-19 reaches review: confirm reviewer acks and writes coordination/review/T-19_receipt.json.
3. When T-19 ACCEPTED: assign T-20 to tester (with DB backup + classified_at reset prereq), then T-22 to implementer.
4. Flag to human: commit-gate.sh only gates depfix-agents (implementer confirmed 00:11) — decide whether to add a dependency_check gate script or document manual make test/lint/typecheck as the gate. PR #10 and PR #11 need review/merge (merge order 10 then 11); duplicate loop processes; dependency_check worktree isolation decision; commit-gate.sh does not cover dependency_check pushes (push-history.log empty by design).
5. Next smoke due ~03:45 CEST (tester).
