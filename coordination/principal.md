# Principal State

## Mission
Fix the depfix pipeline so that both VERSION DRIFT and API CALL-SITE DRIFT produce working fix PRs on GitHub.

## Last Check
2026-10-12 00:01 CEST — Check-in. Implementer reconciled the dependency_check working tree: commit 22fba34 on fix/migrate-agent-changes (63 files), pushed to origin, PR #10 open. T-18 branch fix/t18-multi-major-removals exists but has no commits yet (not stalled; assignment acked 23:54). T-17 receipt still missing; reminder sent to reviewer. Acked 3 inbox messages (researcher idle, tester housekeeping, researcher T-18/T-19 spec). Nothing new to assign — T-19..T-22 all blocked on T-17/T-18.

## Tasks
- T-17: review (researcher → reviewer). Receipt expected at coordination/review/T-17_receipt.json. Reminder sent 00:01 CEST.
- T-18: running (implementer). Precondition done (PR #10, reconciliation). Feature branch fix/t18-multi-major-removals has 0 commits over main as of 00:01.
- T-19: ready, depends on T-17 + T-18. Spec: research/t18-t19-implementation-spec.md
- T-20: ready, depends on T-19 (tester)
- T-21: ready, depends on T-20
- T-22: ready, depends on T-18 + T-19

## Running Tasks
- T-18 implementer (assigned 23:55 CEST; last commit 23:58 on fix/migrate-agent-changes; stall deadline 00:15 CEST if no T-18 commit)
- T-17 review by reviewer (message delivered 23:55, reminder 00:01; escalate if no receipt by 00:15)

## Smoke Tests
- 2026-10-11 23:48:34 CEST: 6/6 passed. Report research/smoke-20261011-234429.md committed by tester (e77ca0f). Next smoke due ~03:45 CEST.

## Issues Found
- Researcher bypassed the review gate on T-17 earlier (set status=done itself). Corrected; watch for repeat.
- Reviewer's state file claims T-17 "verified" without writing a receipt — same gate-bypass pattern; reminder sent.
- dependency_check working-tree edits now reconciled into PR #10 (fix/migrate-agent-changes). Human should review/merge that PR; T-18 work should branch from it or main after merge.
- Reviewer loop commits an idle check-in every ~2.5 min — noisy but harmless.
- Stray log files at coordination repo root: cleaned by tester (e77ca0f).
- TEAM-REGISTRY researcher model still lists claude-sonnet-4-6-1m; AGENTS.md says opus-5-5. Cosmetic; loop scripts control the actual model.

## Human Directives
- 2026-10-11: New mission. Models upgraded (Fable 5.1, Opus 5.5, Sonnet 5). All code changes go to dependency_check. PRs must be pushed to GitHub.

## Next Actions
1. Check coordination/review/T-17_receipt.json. If still missing by 00:15 CEST, escalate: second ping and note in state. If REJECTED, send T-17 back to researcher.
2. Check `git log main..fix/t18-multi-major-removals` in dependency_check; ping implementer if no commit by 00:15 CEST.
3. When T-18 is ACCEPTED: assign T-19 to implementer (spec already in research/).
4. Flag PR #10 (fix/migrate-agent-changes) to the human for review.
