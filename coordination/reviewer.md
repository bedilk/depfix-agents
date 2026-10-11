# Reviewer State

## Current Task
Idle — checked 2026-10-12. No tasks in status=review. Acked principal directive f58fefba (use read-only git show/diff on dependency_check; never checkout/commit there without flock on depfix-agents/.local/git.lock).
T-18 still status=running. Branch fix/t18-multi-major-removals now has 1 commit ahead of main: 22fba34 "migrate pending depfix-agents work and repair ruby/typecheck regressions" (providers.yaml +590, 40 skill files, eval corpora, repo_exports.py + orchestrator/runner.py +97, ruby_* fixes, pyproject mypy bump to 3.12). This is NOT the T-18 classifier/ts_exports fix — when T-18 is submitted, review that commit too since it rides on the branch (check: mypy numpy ignore is scoped, runner.py _augment_with_repo_exports matches accepted T-15 code 7896cff).

## Waiting For
- T-18 (ts_exports_diff fix) — implementer working, branch exists, no code submitted yet
- T-19 (plan fix for fix PRs) — depends on T-18
- T-22 (PR push) — depends on T-18 + T-19

## Pre-Review Notes for T-18/T-19
From T-17 research, the key changes to watch in review:
1. **classifier.py:40** — package recovery from feed_key (must handle all feed formats, not just ts_exports)
2. **upgrade.py:140** — removing METHOD_REMOVED exclusion (must ensure fix quality when no new_api exists). REJECT if the gate is removed without a check that replacement info is available.
3. **runner.py:991** — METHOD_REMOVED routing change (must not produce garbage PRs for truly unfixable removals)
4. **Drift capture in orchestrator** — must not duplicate if scan already captured it

## Reviews Completed

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
