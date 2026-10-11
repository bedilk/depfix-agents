# Reviewer State

## Current Task
Idle as of 2026-10-12. No tasks are in review and the inbox is empty. Rechecked T-19's WIP on dependency_check fix/t19-plan-pr-gate. The source diff is unchanged since my pre_review_feedback, so none of the findings below are fixed yet. One new untracked file: tests/unit/test_upgrade_method_removal_gate.py (89 lines). Did not send a duplicate message. Still no commits after 5205b82.

## T-19 WIP findings (verify these are fixed when review_request arrives)
Reproduced by running the WIP regex against provider_sentry.md:
- `_enrich_removal_from_skill`: Express -> new_api "removed, auto-instrumented" (unfixable removal treated as fixable); finish -> prose
- `.rstrip("()")` leaves "Sentry.httpIntegration(opts" / "Sentry.startSpan({ name, op }, callback" with unbalanced parens
- Bare last-segment symbol + substring match: collisions for short names
- fix_service.py:201 gate uses `migration_guide` instead of `new_api`; changelog-derived guides bypass the gate
- Whole skill file goes into migration_guide (prompt bloat)
- No tests yet
- DB sentry method_removed rows are `sentry.ATTR_*` constants. None of them are in the skill table, so the WIP will not unblock them. T-20 needs a seed hitting e.g. startTransaction/getCurrentHub
- build_upgrade_plan (runner.py:1011) runs after enrichment, so the upgrade.py `not change.new_api` gate is ordered correctly

## Waiting For
- T-19 (plan fix for fix PRs): running, implementer. No commits in dependency_check since 5205b82. A review_request is expected.
- T-20 / T-21 / T-22: ready, unowned. T-20/T-21 blocked on T-19. T-22 needs PR #10 merged, then PR #11

## Carry-forward for T-19/T-20 review
- Stale DB data: 477 breaking_change rows (sentry, method_removed) have package='sentry', and their ts_exports events already have classified_at set. If T-20 claims success, confirm the tester reset or re-classified them; otherwise the package filter still excludes them.

## Pre-Review Notes for T-18/T-19
From T-17 research, the key changes to watch in review:
1. **classifier.py:40** — package recovery from feed_key (must handle all feed formats, not just ts_exports)
2. **upgrade.py:140** — removing METHOD_REMOVED exclusion (must ensure fix quality when no new_api exists). REJECT if the gate is removed without a check that replacement info is available.
3. **runner.py:991** — METHOD_REMOVED routing change (must not produce garbage PRs for truly unfixable removals)
4. **Drift capture in orchestrator** — must not duplicate if scan already captured it

## Reviews Completed

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
- Prior: REJECTED round 1 (provider_redis.md not committed, test count wrong)
- Round 2: Both files committed, content quality good, follows sentry pattern
- Receipt: coordination/review/T-3_receipt.json

### T-4: Expand eval corpus — 10 sentry v7→v8 cases — ACCEPTED (round 2)
- 10 cases: 6 call_sites (all verified:true, passing), 4 fix_generation (verified:false, need LLM)
- Fixtures realistic: setup.js, perf.js, hub.js, breadcrumbs.js — real Sentry v7 API patterns
- Breaking change descriptions accurate against official migration docs
- make eval: 91% (30/33), no regressions
- Receipt: coordination/review/T-4_receipt.json

### T-5: 5 ruby ecosystem eval cases — ACCEPTED (round 2)
- 5 cases: 4 positive (openai require, nested path, stripe, sentry-ruby hyphen) + 1 precision negative
- EvalCase ecosystem field added backward-compatibly, GenericImportScanner routing correct
- make eval: 91% (30/33), no regressions
- Receipt: coordination/review/T-5_receipt.json

### T-6: Adversarial review of ruby fixer — ACCEPTED (round 2)
- Prior: REJECTED round 1 (3 critical bugs, 2 bugs, 2 design issues, zero tests)
- Round 2: All 6 issues fixed, 21 unit tests added
- Minor residual: detect_ruby_test_framework() dead code (never called), ruby_lockfile_paths path filtering inconsistency (pre-existing)
- Receipt: coordination/review/T-6_receipt.json

### T-15: Repo-version-aware ts_exports diff — ACCEPTED (round 3)
- Prior: REJECTED rounds 1-2 (sub-case B not committed, mypy type error, double tarball fetch)
- Round 3 (commit 7896cff): Sub-case B committed, mypy fix (export_name→b_name), 8 new tests
- Verified: sentry v6-app acceptance scenario traces correctly through sub-case B
- Verified: dedup between sub-case A and B via seen_old_apis
- Verified: graceful degradation when installed exports fetch fails
- Non-blocking: double tarball fetch (installed version fetched in repo_version_exports_diff and again in sub-case B)
- make test: 917 passed, 0 failed. Lint clean. Mypy clean.
- Receipt: coordination/review/T-15_receipt.json

## Notes
- Pre-existing test warning: PytestCollectionWarning for TestStatus/TestFramework (StrEnum classes)
- 2 tests deselected (likely platform/config specific)
- Implementer flagged concurrent agent processes on same dependency_check working dir as hazard — no commit lock like depfix-agents .local/git.lock
