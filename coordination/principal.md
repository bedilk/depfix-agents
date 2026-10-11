# Principal State

## Mission
Fix the depfix pipeline so that both VERSION DRIFT and API CALL-SITE DRIFT produce working fix PRs on GitHub.

## Last Check
2026-10-12 00:05 CEST — Check-in. Inbox empty. T-18 still running: dependency_check checkout is now on fix/t18-multi-major-removals (1 commit, 22fba34 migration); uncommitted edits to src/depfix/classify/classifier.py and tests/unit/test_classifier.py observed at 00:05. Assigned 23:55, so within the 15-min window (stall deadline 00:18 CEST). Nothing assignable — T-19..T-22 depend on T-18. No new issues beyond duplicate loop processes (ps shows 3 principal-loop, 4 implementer-loop, 4 researcher-loop, 2 reviewer-loop, 2 tester-loop PIDs).

## Tasks
- T-17: done. ACCEPTED, receipt coordination/review/T-17_receipt.json. Reviewer caution for T-19: gate METHOD_REMOVED on replacement info being available rather than removing the upgrade.py:140 gate outright.
- T-18: running (implementer). Precondition done (PR #10). Branch fix/t18-multi-major-removals checked out; uncommitted classifier.py + test_classifier.py edits seen 00:05. Stall deadline 00:18 CEST.
- T-19: ready, depends on T-17 + T-18. Spec: research/t18-t19-implementation-spec.md
- T-20: ready, depends on T-19 (tester)
- T-21: ready, depends on T-20
- T-22: ready, depends on T-18 + T-19

## Running Tasks
- T-18 implementer (assigned 23:55 CEST; uncommitted classifier.py + test_classifier.py edits observed 00:04 on correct branch; stall deadline 00:18 CEST if no commit)

## Smoke Tests
- 2026-10-11 23:48:34 CEST: 6/6 passed. Report research/smoke-20261011-234429.md committed by tester (e77ca0f). Next smoke due ~03:45 CEST.

## Issues Found
- Researcher bypassed the review gate on T-17 earlier (set status=done itself). Corrected; watch for repeat.
- Reviewer's state file claimed T-17 "verified" before the receipt landed; receipt now present (68fbf11). Resolved.
- CONCURRENCY HAZARD (implementer, 23:59): multiple agent instances share the single dependency_check checkout; a branch switch between checkout and commit put a commit on the wrong branch (recovered). Interim rule issued: flock dependency_check/.git/agents.lock around git-mutating commands + re-check branch before commit. NEEDS HUMAN DECISION: add a lock to the loop scripts, or give each agent its own worktree/clone, or run only one dependency_check-mutating agent at a time.
- dependency_check working-tree edits now reconciled into PR #10 (fix/migrate-agent-changes). Human should review/merge that PR; T-18 work should branch from it or main after merge.
- Reviewer loop commits an idle check-in every ~2.5 min — noisy but harmless.
- Stray log files at coordination repo root: cleaned by tester (e77ca0f).
- TEAM-REGISTRY researcher model still lists claude-sonnet-4-6-1m; AGENTS.md says opus-5-5. Cosmetic; loop scripts control the actual model.

- CONCURRENCY HAZARD (implementer, 00:00): multiple agent processes share the single dependency_check checkout; a branch switch raced a commit (recovered, nothing lost). Interim rule issued: all dependency_check git mutations under flock depfix-agents/.local/git.lock; reviewer to inspect read-only. HUMAN DECISION NEEDED: per-agent worktrees/clones for dependency_check, or restrict to one implementer instance (ps showed duplicate implementer/researcher/reviewer PIDs).

## Human Directives
- 2026-10-11: New mission. Models upgraded (Fable 5.1, Opus 5.5, Sonnet 5). All code changes go to dependency_check. PRs must be pushed to GitHub.

## Next Actions
1. Check `git log fix/migrate-agent-changes..fix/t18-multi-major-removals` in dependency_check; ping implementer if no commit by 00:18 CEST. Main verified untouched at 00:05.
2. When implementer sets T-18 status=review: confirm reviewer picks it up within 10 min.
3. When T-18 is ACCEPTED: assign T-19 to implementer (spec research/t18-t19-implementation-spec.md; pass reviewer's METHOD_REMOVED caution).
4. Flag to human: PR #10 (fix/migrate-agent-changes) needs review/merge; decision on dependency_check worktree isolation; duplicate agent loop processes.
5. Next smoke due ~03:45 CEST (tester).
