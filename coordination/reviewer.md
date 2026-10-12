# Reviewer State

## Current Task
None pending. Review queue empty. Last checked 2026-10-12 ~13:10 CEST.

## Waiting For
- T-20: running (tester). E2E test on 3 repos. Evidence file research/e2e-fix-pr-results.md not yet written. Review carry-forward below.
- T-22: running (implementer). PR #12 still targets fix/t18-multi-major-removals (not main), no CI runs. Principal directive (acked 9d66125b): REJECT unless evidence_paths has PR URL with base=main and green CI run ID.
- T-23: running (researcher). Verification rollback root-cause. Evidence file research/t23-verification-rollback.md not yet written.
- T-21: ready, unowned. Blocked on T-20.

## Carry-forward for T-20 review
- Stale DB data: 477 breaking_change rows (sentry, method_removed) have package='sentry', and their ts_exports events already have classified_at set. If T-20 claims success, confirm the tester reset or re-classified them; otherwise the package filter still excludes them.
- Verification rollback gap: T-19 dry-run shows startTransaction/getCurrentHub reach fix-generation but verification reverts both (no_kept_edits). This is an LLM fix-quality / verification issue, not a routing issue. Should be tracked as a new task before T-20 E2E can fully pass.

## Reviews Completed

### T-19: Fix plan to generate fix PRs — ACCEPTED
- Commit chain a059180..0e9db45 on fix/t19-plan-pr-gate (8 commits)
- Key changes: (1) ghost-removal sentinel (old_version=="0.0.0" + METHOD_REMOVED) in applicability.py short-circuits to APPLIES, (2) repo_exports.py no longer bails on installed>=latest, sub-case B new_version=latest_version, (3) _enrich_removal_from_skill rewritten with line-by-line parsing, prose RHS rejection, ambiguity handling, (4) fix_service.py gate aligned from migration_guide to new_api
- Verified sentinel doesn't over-apply: only repo_exports.py sub-case B produces METHOD_REMOVED + "0.0.0"; lockfile.py uses DEPENDENCY_VERSION_BUMP
- Acceptance gap: startTransaction reaches fix-generation but verification reverts it. Routing is correct; LLM fix quality is downstream.
- make test: 937 passed, 0 failed. lint/mypy/format clean.
- Receipt: coordination/review/T-19_receipt.json

### T-18: ts_exports multi-major / classifier package recovery — ACCEPTED
- Commit 5205b82 on fix/t18-multi-major-removals, PR #11 stacked on #10 (no CI on PR)
- The multi-major criterion was already met by T-15's repo_exports (6.19.7 -> 11.6.0 is tested)
- Checked _package_from_feed_key against every feed_key format; npm dist-tag and :repo: suffix handled correctly
- Non-blocking: commit message misattributes the bug to repo_exports synthetics; overlapping tests; stale DB rows (see carry-forward)
- make test 921 passed; lint and mypy clean
- Receipt: coordination/review/T-18_receipt.json

### T-17: Research — plan produces 0 PRs — ACCEPTED
- Checked every cited file:line in dependency_check: classifier.py:40, store.py event_from_row (no raw), runner.py:396/991, upgrade.py:114/140, ts_exports.py:171/185, cli.py:1275 vs _cmd_pipeline:1908, applicability UNKNOWN
- DB: 477 sentry method_removed confirmed
- Non-blocking: "~6 ACTIONABLE" is an unsourced estimate; DB now has 2 @sentry/node drift rows
- Caution passed to T-19: don't remove the upgrade.py:140 gate outright; gate on replacement info being available
- make test: 917 passed
- Receipt: coordination/review/T-17_receipt.json

### T-3: Provider skill files for redis and postgresql — ACCEPTED (round 2)
- Receipt: coordination/review/T-3_receipt.json

### T-4: Expand eval corpus — 10 sentry v7→v8 cases — ACCEPTED (round 2)
- Receipt: coordination/review/T-4_receipt.json

### T-5: 5 ruby ecosystem eval cases — ACCEPTED (round 2)
- Receipt: coordination/review/T-5_receipt.json

### T-6: Adversarial review of ruby fixer — ACCEPTED (round 2)
- Receipt: coordination/review/T-6_receipt.json

### T-15: Repo-version-aware ts_exports diff — ACCEPTED (round 3)
- Receipt: coordination/review/T-15_receipt.json

## Notes
- Pre-existing test warning: PytestCollectionWarning for TestStatus/TestFramework (StrEnum classes)
- 2 tests deselected (likely platform/config specific)
