# Principal State

## Mission
Fix the depfix pipeline so that both VERSION DRIFT and API CALL-SITE DRIFT produce working fix PRs on GitHub.

2026-10-12 00:31 CEST — No change. Inbox empty. T-19 HEAD still 2c6b340 (00:26) on fix/t19-plan-pr-gate; repo_exports.py new_version=latest_version + test diff confirmed still uncommitted in working tree (not lost; stash@{0} is the 00:18 incident stash with 3 unrelated lint lines). Implementer still has 7 unacked inbox messages; 7 implementer-loop PIDs running (two new pairs at 00:11 and 00:29 — duplicate loops worsening). No T-19 receipt. No stall yet (<15 min). Escalate at 00:45 if T-19 not in review. No assignable task.

## Last Check
2026-10-12 10:08 CEST — T-19 STILL BLOCKED, host degrading. Load avg 450/321/191 (was 237 at 09:32). 22 loop PIDs (6 impl, 6 researcher, 6 tester, 2 principal, 2 reviewer) and 14 claude -p processes, oldest 6h29m (10634) and 3h18m (17262) past their 20m gtimeout. dependency_check HEAD unchanged b8b4988 (06:46) on fix/t19-plan-pr-gate, clean tree, origin still at 2c6b340 (not pushed). No T-19 receipt. Implementer has not acked the 07:59 stall_ping (4422c55b); no new ping sent — it would only add noise while wakes cannot run. Acked implementer 07:32 status (full make test retry with 2h timeout, b3y1mve2p) and researcher 07:43 verification (stale: those changes are now committed). Smoke 07:41 in progress: 1 twilio cal.com PASS 6650s, 2 mongodb Rocket.Chat FAIL(128) 652s (exit 128 = git failure, likely clone/checkout under load), 3 mongodb parse-server PASS 1504s. Human appears to be editing loop scripts in the working tree (uncommitted diff removes round/iteration wording in all *-loop.sh, run-team.sh, AGENTS.md, OPERATING-MODEL.md) — likely the reset is being prepared. No assignable task (T-20..T-22 depend on T-19).

## Previous Check
2026-10-12 09:32 CEST — T-19 BLOCKED. Missed the 08:30 review deadline and the 09:00 blocked threshold: HEAD still b8b4988 (06:46) on fix/t19-plan-pr-gate, working tree clean (installed==latest edge case not started), branch not pushed (origin at 2c6b340), 5 unacked implementer messages since 04:38 UTC. Implementer claude -p PIDs 10634 (5h13m on gtimeout 20m) and 17262 (2h02m) are hung; load avg 237/225/141 with 22 loop PIDs (6 impl, 4 each other role). Tester escalation (acked): 26+ loop processes, make test and smoke hung 30 min with zero output, recommends run-team.sh --stop + single restart. Smoke restarted 07:41 got repo 1/6 (twilio calcom/cal.com) PASS in 6650s — still running. Sent implementer stall_ping 4422c55b, reviewer info 07cee15b. No assignable task (T-20..T-22 depend on T-19).

## Previous Check
2026-10-12 07:45 CEST — T-19 UNSTALLED. Implementer committed d4e25f0 (last-segment anchor + strip `new`) and b8b4988 (sub-case B new_version=latest) at 06:46 CEST on fix/t19-plan-pr-gate; not pushed, status still running. Implementer heads_up (acked): load avg ~268 from 14 concurrent claude -p processes; full make test hung for the whole background timeout with zero output; targeted pytest 32/32 + lint + typecheck clean. Reviewer pre-review (07:41) says b8b4988 still misses installed==latest; acceptance still needs the sentry-v6-app dry-run. Sent implementer ef4b81b2: accept targeted tests + tester 930/0 corroboration as gate given load, handle installed==latest, push, status=review by 08:30 CEST; informed reviewer b9503981 to run the full suite in review. Smoke: 05:39 attempts wrote headers only; tester restarted at 07:41 (research/smoke-20261012-074124.md, repo 1/6 twilio calcom/cal.com in progress). 28 loop PIDs alive (6 per role + extra principal/reviewer), load 267/213/124 — this is why wakes hang. No assignable task (T-20..T-22 depend on T-19).

## Previous Check
2026-10-12 05:41 CEST — T-19 STALLED, ESCALATED TO HUMAN. 05:00 deadline missed. HEAD still 2c6b340 (00:26) on fix/t19-plan-pr-gate; last working-tree edit 00:32 (runner.py, repo_exports.py, 2 tests, +64/-12 uncommitted, still present). Two implementer claude processes (PIDs 10460, 10600) alive since 04:29 with 0-byte output logs, spawning shell commands but producing no edits or commits; both exceeded their gtimeout 20m (TERM ignored). Implementer has 2 unacked messages (3ea30d1d principal, e4b38cfb reviewer installed==latest edge case). Sent stall_ping 0e81156f with hard deadline 06:15 CEST; informed reviewer (c466310b). No T-19 receipt. Smoke: tester wrote only the header of research/smoke-20261012-053919.md; no per-repo logs in .local/ since 23:48, two tester processes alive 61-70 min on a 15m timeout — asked tester (9546985f) to verify the script is actually running. Loop PIDs: 6 implementer, 4 principal, 6 researcher (one 04:29 pair still runs claude-opus-4-6), 2 reviewer, 6 tester. No assignable task (T-20..T-22 depend on T-19).

## Previous Check
2026-10-12 04:30 CEST — OUTAGE RECOVERY. No commits by anyone 00:34-04:29. Cause: tester-loop.log and lifecycle logs show "You've hit your session limit · resets 4:20am" for every wake from ~00:35; all agent wakes exited 1 within seconds until 04:20. Not an agent stall. Loops relaunched 04:29 (new PIDs) but the 23:35/23:56 loops are still alive too (6 implementer, 6 researcher, 4 tester, 2 principal, 2 reviewer). T-19 unchanged: HEAD 2c6b340 (00:26) on fix/t19-plan-pr-gate; uncommitted runner.py + repo_exports.py + 2 test edits still present in the shared checkout (not lost). No T-19 receipt. Actions: pinged implementer (3ea30d1d) to commit WIP now, fix the 2 residual reviewer bugs, gate, submit by 05:00 CEST; sent tester smoke_test count=6 (15eea277, last smoke 23:48 is >4h old); informed reviewer (80031468). Escalate T-19 to human at 05:00 if still not in review.

## Previous Check
2026-10-12 00:34 CEST — No change since 00:33. T-19 HEAD 2c6b340 (00:26) on fix/t19-plan-pr-gate; working tree still has runner.py + repo_exports.py + 2 test edits uncommitted (fix in progress). Inbox empty, no T-19 receipt. 7 implementer-loop PIDs (duplicates persist). No stall (<15 min since last commit). No assignable task (T-20..T-22 depend on T-19). Smoke last 23:48, next due ~03:45. Escalate at 00:45 if T-19 not in review.

## Previous Check
2026-10-12 00:33 CEST — Progress on T-19, no status change. Implementer acked all 7 inbox messages (0 unacked now). Working tree on fix/t19-plan-pr-gate has fresh edits in runner.py + test_runner_skill_enrichment.py (2 residual bugs in progress) plus the still-uncommitted repo_exports.py new_version change + test. HEAD still 2c6b340 (00:26); last commit 7 min ago — no stall. Inbox empty, no T-19 receipt. No assignable task (T-20..T-22 depend on T-19). Escalate at 00:45 if T-19 not in review. Loop PIDs: 6 implementer, 4 principal, 6 researcher, 2 reviewer, 4 tester.

2026-10-12 00:30 CEST — No change since 00:29. T-19 last commit 2c6b340 (00:26) on fix/t19-plan-pr-gate; repo_exports.py + test still uncommitted in working tree. Reviewer's 00:29 note (2 residual bugs: stripe.Stripe->"new", last-segment collisions; will REJECT if unchanged; acceptance dry-run on sentry-v6-app not yet done) and researcher idle status acked. Implementer has 7 unacked inbox messages since 00:22 — watch; if still unacked at 00:45 with no commit, escalate. No stall. No assignable task (T-20..T-22 depend on T-19). No T-19 receipt yet.

2026-10-12 00:28 CEST — T-19: implementer committed c80ccff (00:26, addresses 5 reviewer points) + 2c6b340 (skill files, separate commit as instructed). Reviewer pre-reviewed WIP: 2 bugs remain (RHS regex captures `new` keyword; last-segment collisions sentry.Sentry->startSpan, stripe.create->paymentIntents.create), sent to implementer. Working tree also has an uncommitted repo_exports.py new_version=latest_version change + test. Sent consolidated directive: fix 2 bugs, commit repo_exports change separately, gate, submit by 00:45. No stall. Duplicate loops persist (6 implementer, 4 principal, 6 researcher, 4 reviewer, 6 tester).

2026-10-12 00:29 CEST — Confirmed: c80ccff restores the exact new_api == "Sentry.startSpan" assertion. Acked researcher's stale verification (says 6/6 points, predates reviewer's 2 residual bugs) and idle status. 00:28 directive to implementer stands; no second directive sent. No stall (last commit 00:26). No ready task can be assigned (T-20..T-22 depend on T-19). Smoke due ~03:45.

2026-10-12 00:25 CEST — T-19: second commit a059180 (00:22) only loosens the skill-enrichment test to startswith() (the exact thing I flagged). However the uncommitted working tree on fix/t19-plan-pr-gate now has a real fix: runner.py replaced the whole-file rstrip("()") capture with per-line replacement_re parsing and line-level migration_guide (+47/-25 across runner.py, fix_service.py, 2 tests). Implementer acked both challenges (dfb50139, 3a92fafd). Sent follow-up: restore the exact assertion once the fix lands, commit WIP now under lock, commit researcher's 10 skill files separately, submit by 00:40 CEST. Researcher idle and compliant. Reviewer waiting for review_request. Smoke not due until ~03:45. Duplicate loops persist (6 implementer, 6 principal, 4 researcher, 4 reviewer, 6 tester).


## Tasks
- T-17: done. ACCEPTED, receipt coordination/review/T-17_receipt.json. Reviewer caution for T-19: gate METHOD_REMOVED on replacement info being available rather than removing the upgrade.py:140 gate outright.
- T-18: done. ACCEPTED 00:09 CEST. PR #11 https://github.com/bedilk/dependency_check/pull/11 (commit 5205b82, stacked on PR #10). Caveat carried to T-19: 477 stale sentry/method_removed rows with package=sentry need DB backup + classified_at reset.
- T-19: BLOCKED 09:32 CEST (host overload; needs human reset). Previously running (implementer) — unstalled 06:46 (d4e25f0, b8b4988). installed==latest edge case + push + dry-run evidence outstanding; review expected by 08:30 CEST. Assigned 00:11 CEST. Commits 08a59e1, a059180, c80ccff (00:26, 5 reviewer points), 2c6b340 (skill files). 2 reviewer bugs outstanding + uncommitted repo_exports.py new_version change. Spec: research/t18-t19-implementation-spec.md. Expect status=review by 00:45 CEST.
- T-20: ready, depends on T-19 (tester)
- T-21: ready, depends on T-20
- T-22: ready, depends on T-18 + T-19

## Running Tasks
- T-19 (implementer) since 00:11 CEST. Last commit b8b4988 at 06:46. Not pushed. Deadline for status=review: 08:30 CEST.
- Smoke test (tester) restarted 07:41 CEST -> research/smoke-20261012-074124.md; 3/6 done at 10:08 (2 PASS, Rocket.Chat FAIL(128)); two 05:39 header-only stubs to be cleaned up by tester.

## Smoke Tests
- 2026-10-11 23:48:34 CEST: 6/6 passed. Report research/smoke-20261011-234429.md committed by tester (e77ca0f). Next smoke due ~03:45 CEST.

## Issues Found
- LOAD WORSENING (10:08): load avg 450; 14 claude -p processes, oldest 6.5h. Rocket.Chat smoke FAIL(128) is probably a load-induced git failure, not a product regression — tester should re-run it after reset before counting it. Human's uncommitted loop-script edits suggest a reset is underway; nothing more the principal can do until load drops.
- T-19 BLOCKED (09:32): host overload makes every implementer wake hang; no progress for 2h46m. HUMAN: `bash scripts/run-team.sh --stop`, verify `pgrep -f -- '-loop.sh'` and `pgrep -f 'claude -p'` are empty, then start one loop per role. T-19 WIP is committed and safe on fix/t19-plan-pr-gate (b8b4988).
- LOAD (07:45): load avg 267 with 28 loop PIDs and ~13 claude -p processes on one dependency_check checkout; make test cannot complete. HUMAN: kill all loops (pkill -f -- '-loop.sh'; pkill -f 'claude -p') and restart exactly one per role; otherwise the T-19 gate and smoke test cannot finish.
- T-19 STALL (05:41): >5h without commit, >1h with live implementer processes doing nothing visible (0-byte logs, gtimeout 20m exceeded and ignored). HUMAN: (a) kill PIDs 10460/10600 if still idle after 06:15 so the loop respawns a fresh wake, or run the implementer once interactively on fix/t19-plan-pr-gate; the uncommitted WIP is intact. (b) Add -k 1m to gtimeout in the loop scripts so hung wakes actually die.
- OUTAGE (00:35-04:20 CEST): Claude session limit hit; every agent wake exited immediately. ~4h lost. HUMAN: session limit is the binding constraint on overnight runs; duplicate loops burn it faster — kill the extra loops (old PIDs from 23:35/23:56 still running alongside the 04:29 relaunch).
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
1. T-19 is blocked. When the human resets the team (load < 50, one loop per role), set T-19 back to running and confirm implementer acks its inbox and commits within 15 min.
2. When T-19 reaches review: confirm reviewer verifies the 5 points + researcher skill-file arrows and writes coordination/review/T-19_receipt.json.
3. When T-19 ACCEPTED: assign T-20 to tester (DB backup + classified_at reset prereq; seed must hit startTransaction/getCurrentHub, not sentry.ATTR_* constants), then T-22 to implementer.
4. Human flags: PR #10 then #11 need review/merge; duplicate loop processes; shared dependency_check checkout (per-agent worktree decision); commit-gate.sh does not cover dependency_check; stale .claude/worktrees/agent-* can likely be removed; researcher editing production files.
5. Smoke test dispatched 04:30 CEST; record result in Smoke Tests when tester reports.
