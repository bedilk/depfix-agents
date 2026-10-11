# Reviewer State

## Current Task
Idle — no tasks pending review. T-17 is `running` (assigned to researcher at 2026-10-11T21:48Z) but researcher hasn't started yet — assignment message still unacked. T-18–T-22 all `ready`, no owner assigned. Last checked 2026-10-11.

dependency_check repo: latest commit is 722c263 (security hardening). No new code changes since last check.

Waiting for:
- T-17 research report (researcher must complete first)
- T-18 (ts_exports_diff fix) — will need code review once implementer submits
- T-19 (plan fix for fix PRs) — will need code review once implementer submits
- T-22 (PR push) — will verify CI once opened

No work to do until researcher completes T-17 and implementer submits T-18/T-19 for review.

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

### T-15: Repo-version-aware ts_exports diff — ACCEPTED (round 3)
- Prior: REJECTED rounds 1-2 (sub-case B not committed, mypy type error, double tarball fetch)
- Round 3 (commit 7896cff): Sub-case B committed, mypy fix (export_name→b_name), 8 new tests
- Verified: sentry v6-app acceptance scenario traces correctly through sub-case B
- Verified: dedup between sub-case A and B via seen_old_apis
- Verified: graceful degradation when installed exports fetch fails
- Non-blocking: double tarball fetch (installed version fetched in repo_version_exports_diff and again in sub-case B)
- make test: 917 passed, 0 failed. Lint clean. Mypy clean.
- Receipt: coordination/review/T-15_receipt.json

## Pending
- T-17 research (no code review needed — but may review the research report quality)
- T-18 and T-19 are the next code review tasks once implementer submits
- T-20 and T-21 are tester tasks (no code review needed)
- T-22 is a PR push task (will verify CI)

## Notes
- Pre-existing test warning: PytestCollectionWarning for TestStatus/TestFramework (StrEnum classes)
- 2 tests deselected (likely platform/config specific)
