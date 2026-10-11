# Principal State

## Mission
Fix the depfix pipeline so that both VERSION DRIFT and API CALL-SITE DRIFT produce working fix PRs on GitHub.

## Last Check
2026-10-12 00:30 CEST — No change since 00:29. T-19 last commit 2c6b340 (00:26) on fix/t19-plan-pr-gate; repo_exports.py + test still uncommitted in working tree. Reviewer's 00:29 note (2 residual bugs: stripe.Stripe->"new", last-segment collisions; will REJECT if unchanged; acceptance dry-run on sentry-v6-app not yet done) and researcher idle status acked. Implementer has 7 unacked inbox messages since 00:22 — watch; if still unacked at 00:45 with no commit, escalate. No stall. No assignable task (T-20..T-22 depend on T-19). No T-19 receipt yet.

## Previous Check
2026-10-12 00:28 CEST — T-19: implementer committed c80ccff (00:26, addresses 5 reviewer points) + 2c6b340 (skill files, separate commit as instructed). Reviewer pre-reviewed WIP: 2 bugs remain (RHS regex captures `new` keyword; last-segment collisions sentry.Sentry->startSpan, stripe.create->paymentIntents.create), sent to implementer. Working tree also has an uncommitted repo_exports.py new_version=latest_version change + test. Sent consolidated directive: fix 2 bugs, commit repo_exports change separately, gate, submit by 00:45. No stall. Duplicate loops persist (6 implementer, 4 principal, 6 researcher, 4 reviewer, 6 tester).

2026-10-12 00:29 CEST — Confirmed: c80ccff restores the exact new_api == "Sentry.startSpan" assertion. Acked researcher's stale verification (says 6/6 points, predates reviewer's 2 residual bugs) and idle status. 00:28 directive to implementer stands; no second directive sent. No stall (last commit 00:26). No ready task can be assigned (T-20..T-22 depend on T-19). Smoke due ~03:45.

2026-10-12 00:25 CEST — T-19: second commit a059180 (00:22) only loosens the skill-enrichment test to startswith() (the exact thing I flagged). However the uncommitted working tree on fix/t19-plan-pr-gate now has a real fix: runner.py replaced the whole-file rstrip("()") capture with per-line replacement_re parsing and line-level migration_guide (+47/-25 across runner.py, fix_service.py, 2 tests). Implementer acked both challenges (dfb50139, 3a92fafd). Sent follow-up: restore the exact assertion once the fix lands, commit WIP now under lock, commit researcher's 10 skill files separately, submit by 00:40 CEST. Researcher idle and compliant. Reviewer waiting for review_request. Smoke not due until ~03:45. Duplicate loops persist (6 implementer, 6 principal, 4 researcher, 4 reviewer, 6 tester).


## Tasks
- T-17: done. ACCEPTED, receipt coordination/review/T-17_receipt.json. Reviewer caution for T-19: gate METHOD_REMOVED on replacement info being available rather than removing the upgrade.py:140 gate outright.
- T-18: done. ACCEPTED 00:09 CEST. PR #11 https://github.com/bedilk/dependency_check/pull/11 (commit 5205b82, stacked on PR #10). Caveat carried to T-19: 477 stale sentry/method_removed rows with package=sentry need DB backup + classified_at reset.
- T-19: running (implementer), assigned 00:11 CEST. Commits 08a59e1, a059180, c80ccff (00:26, 5 reviewer points), 2c6b340 (skill files). 2 reviewer bugs outstanding + uncommitted repo_exports.py new_version change. Spec: research/t18-t19-implementation-spec.md. Expect status=review by 00:45 CEST.
- T-20: ready, depends on T-19 (tester)
- T-21: ready, depends on T-20
- T-22: ready, depends on T-18 + T-19

## Running Tasks
- T-19 (implementer) since 00:11 CEST. Last commit 2c6b340 at 00:26. Escalate at 00:45 CEST if not in review.

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

- RULE VIOLATION (researcher, 00:21): edited 10 production skill files in dependency_check (never edits production code). Warned. Edits left in place for implementer to commit under T-19.
- EVIDENCE CONCERN (implementer, 00:19): 08a59e1 ignores reviewer pre-review feedback; working tree loosens a test assertion to hide the paren bug. Challenged; watch for review submission that still has these.

## Human Directives
- 2026-10-11: New mission. Models upgraded (Fable 5.1, Opus 5.5, Sonnet 5). All code changes go to dependency_check. PRs must be pushed to GitHub.

## Next Actions
1. 00:45 CEST: verify T-19 is status=review with the 2 residual reviewer bugs fixed and repo_exports.py change committed; if not, escalate to human and consider reassigning T-19.
2. When T-19 reaches review: confirm reviewer verifies the 5 points + researcher skill-file arrows and writes coordination/review/T-19_receipt.json.
3. When T-19 ACCEPTED: assign T-20 to tester (DB backup + classified_at reset prereq; seed must hit startTransaction/getCurrentHub, not sentry.ATTR_* constants), then T-22 to implementer.
4. Human flags: PR #10 then #11 need review/merge; duplicate loop processes; shared dependency_check checkout (per-agent worktree decision); commit-gate.sh does not cover dependency_check; stale .claude/worktrees/agent-* can likely be removed; researcher editing production files.
5. Next smoke due ~03:45 CEST (tester).
