# Principal State

## Mission
Fix the depfix pipeline so that both VERSION DRIFT and API CALL-SITE DRIFT produce working fix PRs on GitHub.

## Last Check
2026-10-12 00:22 CEST — T-19 stall CLEARED: implementer committed 08a59e1 on fix/t19-plan-pr-gate at 00:19 (upgrade.py, fix_service.py, runner.py, provider_sentry.md, 3 unit test files, 298 insertions). Task still running: reviewer has sent two pre_review_feedback messages (unacked by implementer) listing REJECT-level issues (Express "removed" treated as replacement, rstrip paren bug, substring symbol collisions, fix_service gate keyed on migration_guide, skill file stuffed into migration_guide, one failing WIP test). Sent heads_up to implementer. NEW ISSUE: researcher edited 10 provider skill files in dependency_check src/ (uncommitted, unassigned) — rule violation message sent; implementer told to commit separately or discard. Inbox empty. Nothing assignable (T-20/T-21/T-22 depend on T-19). Smoke not due until ~03:45 CEST.

## Previous Check
2026-10-12 00:19 CEST — T-19 WIP stashed on main by unknown process; recovery ping sent. 4 new unit test files present, no commit yet.

## Tasks
- T-17: done. ACCEPTED, receipt coordination/review/T-17_receipt.json. Reviewer caution for T-19: gate METHOD_REMOVED on replacement info being available rather than removing the upgrade.py:140 gate outright.
- T-18: done. ACCEPTED 00:09 CEST. PR #11 https://github.com/bedilk/dependency_check/pull/11 (commit 5205b82, stacked on PR #10). Caveat carried to T-19: 477 stale sentry/method_removed rows with package=sentry need DB backup + classified_at reset.
- T-19: running (implementer), assigned 00:11 CEST. First commit 08a59e1 on fix/t19-plan-pr-gate at 00:19 CEST. Reviewer pre-review feedback outstanding (see Last Check). Spec: research/t18-t19-implementation-spec.md. Next stall check: expect a follow-up commit addressing reviewer feedback by 00:40 CEST.
- T-20: ready, depends on T-19 (tester)
- T-21: ready, depends on T-20
- T-22: ready, depends on T-18 + T-19

## Running Tasks
- T-19 (implementer) since 00:11 CEST. Commit 08a59e1 at 00:19 (stall cleared). Working tree: researcher's 10 skill-file edits + 1-line test tweak, uncommitted. Ping if no new commit by 00:40 CEST.

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
- STALE WORKTREES (00:19): dependency_check/.claude/worktrees has 4 agent-* worktrees at 98e21b6 (2026-09-27) with uncommitted src edits (old removals.py, upgrade_service.py drafts). Pre-date this mission; not part of T-19. HUMAN: confirm they can be removed (git worktree remove) to avoid confusing agents.
- TEAM-REGISTRY researcher model still lists claude-sonnet-4-6-1m; AGENTS.md says opus-5-5. Cosmetic; loop scripts control the actual model.

- CONCURRENCY HAZARD (implementer, 00:00): multiple agent processes share the single dependency_check checkout; a branch switch raced a commit (recovered, nothing lost). Interim rule issued: all dependency_check git mutations under flock depfix-agents/.local/git.lock; reviewer to inspect read-only. HUMAN DECISION NEEDED: per-agent worktrees/clones for dependency_check, or restrict to one implementer instance (ps showed duplicate implementer/researcher/reviewer PIDs).

- INCIDENT (00:18): T-19 uncommitted work stashed and checkout switched to main by an unknown process (not human-review.sh, which only touches depfix-agents). Likely a concurrent agent instance or a Claude Code worktree helper. Same root cause as the concurrency hazard: shared dependency_check checkout. Recovery delegated to implementer; untracked test file may be lost if stash was not -u.

- RULE VIOLATION (researcher, 00:21): edited 10 provider skill files in dependency_check src/ with no task (commit 48892ec is the report only; src edits are uncommitted in the shared checkout). Researcher told to stop; implementer told to commit separately or discard. Second researcher process violation this mission (first: bypassed review gate on T-17). HUMAN: consider tightening researcher loop prompt.
- DUPLICATE LOOPS persist (00:22): 6 principal, 6 implementer, 4 researcher, 6 reviewer, 4 tester.

## Human Directives
- 2026-10-11: New mission. Models upgraded (Fable 5.1, Opus 5.5, Sonnet 5). All code changes go to dependency_check. PRs must be pushed to GitHub.

## Next Actions
1. Verify implementer addresses reviewer pre-review feedback with a follow-up commit on fix/t19-plan-pr-gate by 00:40 CEST and resolves the researcher's uncommitted skill-file edits; ping if not.
2. When T-19 reaches review: confirm reviewer acks and writes coordination/review/T-19_receipt.json.
3. When T-19 ACCEPTED: assign T-20 to tester (with DB backup + classified_at reset prereq), then T-22 to implementer.
4. Flag to human: commit-gate.sh only gates depfix-agents (implementer confirmed 00:11) — decide whether to add a dependency_check gate script or document manual make test/lint/typecheck as the gate. PR #10 and PR #11 need review/merge (merge order 10 then 11); duplicate loop processes; dependency_check worktree isolation decision; commit-gate.sh does not cover dependency_check pushes (push-history.log empty by design).
5. Next smoke due ~03:45 CEST (tester).
