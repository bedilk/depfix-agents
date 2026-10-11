# Principal State

## Mission
Fix the depfix pipeline so that both VERSION DRIFT and API CALL-SITE DRIFT produce working fix PRs on GitHub.

## Last Check
2026-10-12 00:08 CEST — Check-in. Acked 3 inbox messages (researcher spec_updated 05550cd; implementer T-18 submitted twice). T-18 moved to status=review at 00:07: PR #11 (fix/t18-multi-major-removals, commit 5205b82, stacked on PR #10). Reviewer inbox has 2 unacked review_request messages; reviewer's last check-in (b19e565, 00:04) predates the submission, so pickup is pending. Nothing assignable — T-19/T-22 depend on T-18. No stalls. Duplicate loop processes worsening: ps shows 5 principal-loop, 6 implementer-loop, 3 researcher-loop, 6 reviewer-loop, 3 tester-loop PIDs; implementer reports a concurrent implementer-loop instance edited TASKS.json underneath it.

## Tasks
- T-17: done. ACCEPTED, receipt coordination/review/T-17_receipt.json. Reviewer caution for T-19: gate METHOD_REMOVED on replacement info being available rather than removing the upgrade.py:140 gate outright.
- T-18: review (reviewer). PR #11 https://github.com/bedilk/dependency_check/pull/11, commit 5205b82 on fix/t18-multi-major-removals (stacked on PR #10). Submitted 00:07 CEST; reviewer pickup deadline 00:17 CEST.
- T-19: ready, depends on T-17 + T-18. Spec: research/t18-t19-implementation-spec.md
- T-20: ready, depends on T-19 (tester)
- T-21: ready, depends on T-20
- T-22: ready, depends on T-18 + T-19

## Running Tasks
- None. T-18 awaiting reviewer (submitted 00:07 CEST; ping reviewer if no receipt/ack by 00:17 CEST).

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
- TEAM-REGISTRY researcher model still lists claude-sonnet-4-6-1m; AGENTS.md says opus-5-5. Cosmetic; loop scripts control the actual model.

- CONCURRENCY HAZARD (implementer, 00:00): multiple agent processes share the single dependency_check checkout; a branch switch raced a commit (recovered, nothing lost). Interim rule issued: all dependency_check git mutations under flock depfix-agents/.local/git.lock; reviewer to inspect read-only. HUMAN DECISION NEEDED: per-agent worktrees/clones for dependency_check, or restrict to one implementer instance (ps showed duplicate implementer/researcher/reviewer PIDs).

## Human Directives
- 2026-10-11: New mission. Models upgraded (Fable 5.1, Opus 5.5, Sonnet 5). All code changes go to dependency_check. PRs must be pushed to GitHub.

## Next Actions
1. Confirm reviewer acks the T-18 review_request and writes coordination/review/T-18_receipt.json; ping reviewer if nothing by 00:17 CEST.
2. When T-18 is ACCEPTED: assign T-19 to implementer — branch from fix/t18-multi-major-removals (per implementer), spec research/t18-t19-implementation-spec.md, carry reviewer's METHOD_REMOVED caution (gate on replacement info, do not drop upgrade.py:140 gate). Researcher's skill-file audit (c695348) is input for Fix 3.
3. If T-18 is REJECTED: return to implementer with receipt issues.
4. Flag to human: PR #10 and PR #11 need review/merge; duplicate loop processes; dependency_check worktree isolation decision.
5. Next smoke due ~03:45 CEST (tester).
