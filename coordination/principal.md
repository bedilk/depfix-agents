# Principal State

## Mission
Fix the depfix pipeline so that both VERSION DRIFT and API CALL-SITE DRIFT produce working fix PRs on GitHub.

## Last Check
2026-10-12 00:02 CEST — Check-in. T-17 receipt present (ACCEPTED, 68fbf11); task is done. Acked 5 inbox messages (reviewer verdict, researcher idle x2, implementer PR #10 status, implementer concurrency hazard). T-18 branch still 0 commits over main, but implementer has an uncommitted classifier.py edit (_package_from_feed_key, a T-19 spec item) on the main checkout of dependency_check. Pinged implementer: commit on the feature branch (based on PR #10 branch), use flock on dependency_check git ops, T-18 commit by 00:20 CEST. Nothing new assignable: T-19..T-22 blocked on T-18. Researcher and reviewer idle.

## Tasks
- T-17: done. ACCEPTED, receipt coordination/review/T-17_receipt.json. Reviewer caution for T-19: gate METHOD_REMOVED on replacement info being available rather than removing the upgrade.py:140 gate outright.
- T-18: running (implementer). Precondition done (PR #10, reconciliation). Feature branch fix/t18-multi-major-removals has 0 commits over main as of 00:01.
- T-19: ready, depends on T-17 + T-18. Spec: research/t18-t19-implementation-spec.md
- T-20: ready, depends on T-19 (tester)
- T-21: ready, depends on T-20
- T-22: ready, depends on T-18 + T-19

## Running Tasks
- T-18 implementer (assigned 23:55 CEST; uncommitted WIP on main checkout as of 00:02; ping sent 00:02; stall deadline 00:20 CEST if no commit on fix/t18-multi-major-removals)

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

## Human Directives
- 2026-10-11: New mission. Models upgraded (Fable 5.1, Opus 5.5, Sonnet 5). All code changes go to dependency_check. PRs must be pushed to GitHub.

## Next Actions
1. Check `git log main..fix/t18-multi-major-removals` in dependency_check; if still 0 commits by 00:20 CEST, second ping and flag as stalled.
2. Human: decide on the dependency_check concurrency fix (lock vs worktrees vs single mutating agent).
3. When T-18 is ACCEPTED: assign T-19 to implementer (spec already in research/).
4. Flag PR #10 (fix/migrate-agent-changes) to the human for review.
