# Reviewer State

## Current Task
Round 2 (continued). T-15 REJECTED.

## Reviews Completed

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

### T-15: Repo-version-aware ts_exports diff — REJECTED (round 2)
- Commit reviewed: 20d5564 (orchestrator integration) + 5f33afa (repo_exports.py + 16 tests)
- Sub-case A (installed - latest exports diff) is correctly implemented and tested
- **CRITICAL**: Sub-case B missing from committed code. startTransaction (removed in sentry v8) is absent from both v10.75.3 and v11.6.0 exports, so removed={} and no synthetic change is produced. The sentry v6-app acceptance criterion is NOT satisfied.
- Sub-case B code exists in working tree (uncommitted) but has a mypy type error at repo_exports.py:197
- Additionally: sub-case B re-fetches installed version tarball unnecessarily (already fetched in repo_version_exports_diff)
- No tests for orchestrator _augment_with_repo_exports method
- Tests run: 908 passed (committed), 1 failed (pre-existing isolation issue), typecheck clean, lint clean
- Receipt: coordination/review/T-15_receipt.json

## Pending
- T-15 returns to implementer for sub-case B commit + mypy fix

## Notes
- Pre-existing test failure: test_repo_shipped_providers_file_is_valid passes individually but fails in full suite (test isolation issue)
