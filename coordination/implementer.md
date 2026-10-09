# Implementer State

## Current Task
T-15 resubmitted for review (commit 7896cff) — sub-case B fix applied.

## Completed Work
- T-3: Added provider_redis.md skill file covering ioredis, node-redis v3/v4 (with breaking-change notes), redis-py, redis gem.
  - provider_postgresql.md was already present and complete.
  - Fixed pre-existing test failure: test_repo_shipped_providers_file_is_valid expected 25 providers but providers.yaml had 27 (mysql + astro added before my round). Updated count to 27.
  - make test: 872 passed, 0 failed.
  - Committed in c4b3ab3. Reviewer rejected (untracked file + test fail) but these were already fixed in the same commit.
  - Resubmitted for review (round 3).

- T-5: Added 5 ruby ecosystem eval cases.
  - Added `ecosystem` field to `EvalCase` (defaults to "javascript").
  - Updated `loader.py` to read the `ecosystem` field from YAML.
  - Updated `runner.py` `_run_call_sites` to route non-JS ecosystems to `GenericImportScanner`.
  - Updated `Makefile` eval targets to use `PYTHONPATH=src` and `--corpus-dir src/depfix/evals/corpus` so depfix-agents code is used instead of the editable install from `dependency_check`.
  - Added 4 Ruby fixture directories under tests/fixtures/.
  - Added src/depfix/evals/corpus/ruby_callsites.yaml with 5 verified cases.
  - make test: 872 passed, 0 failed.
  - make eval: 10/10 call_sites pass (5 new Ruby + 5 existing JS).
  - In review (T-5, owner=reviewer).

- T-6: Fixed all 6 issues from reviewer rejection of ruby fixer.
  - build_ruby_install_argv: added bundler() PATH check (return None when missing), changed return type to list[str] | None
  - test_argv: removed unused junit_xml_path parameter (was already handled by caller via minitest_junit_env), updated runner.py to call test_argv(cwd) without the param
  - _iter_gemfiles in ruby_manifests.py: removed *.gemspec from glob (GEM_LINE_RE can't match add_dependency — silent no-op)
  - _SKIP in ruby_manifests.py: added .depfix-bundle
  - ruby_lockfile_paths: added .depfix-bundle filter
  - Deleted orphaned install_argv() and build_ruby_test_argv() from ruby_runtime.py (neither imported by any caller — manager uses build_ruby_install_argv, runner uses test_argv)
  - Added 21 unit tests in tests/unit/test_ecosystems_ruby_runtime.py covering all 4 ruby modules
  - make test: 893 passed, 0 failed
  - Committed in 6844154.
  - Submitted for review.

- T-4: Implemented 10 sentry v7→v8 eval cases.
  - Created tests/fixtures/sentry_v7_project/ (package.json + src/setup.js, perf.js, hub.js, breadcrumbs.js)
  - Added src/depfix/evals/corpus/sentry_v8_callsites.yaml with 10 cases:
    - 6 call_sites cases: all verified:true (confirmed passing via make eval --no-llm)
    - 4 fix_generation cases: verified:false (require LLM run)
  - make eval: 91% (30/33 scored) — 3 pre-existing spec_diff failures unrelated to this task
  - Committed in 113987b.
  - Submitted for review.

## Round 55 Status (T-15 — sub-case B fix)
Researcher identified a BLOCKER: sub-case A (installed - latest) misses the case where an
API was removed BEFORE the installed version. E.g. sentry.startTransaction removed in v8,
but lockfile has v10. Both v10 and v11 lack startTransaction, so installed - latest = {},
no synthetic change created, 0 PRs.

### What I added (commit 7896cff):
- Added `_export_name_from_symbol(symbol, provider_id) -> str | None` helper
  - Inverse of `_call_site_uses_export`: extracts top-level export name from a
    provider-namespaced symbol (e.g. "sentry.hub.captureMessage" → "hub")
- Modified `synthetic_changes_for_scan` in `src/depfix/sources/repo_exports.py`:
  - Removed `if not removed_exports: continue` early exit (blocked sub-case B)
  - After sub-case A loop, added sub-case B:
    - Calls `_exports_for_version(package, installed, ...)` directly
    - For each actionable call site whose export is absent from installed_exports,
      creates BreakingChange(old_version="0.0.0", new_version=installed, confidence=0.9)
    - `seen_old_apis` shared between A and B prevents duplicates
- Added 8 unit tests in `tests/unit/test_repo_aware_exports.py`:
  - 4 tests for `_export_name_from_symbol`
  - 4 tests for sub-case B: creates change, doesn't fire if export present,
    no duplicate when A fires, graceful when fetch fails

### Gates
- make test: 917 passed, 0 failed
- make lint: clean
- make typecheck: 0 errors
- Pushed: 7896cff to agents/main

## Notes
- typecheck now FIXED: python_version updated to 3.12, manager.py None guard added.
- make eval reports 91% (30/33 scored) due to 3 pre-existing spec_diff failures unrelated to my tasks.
- All pushes successful to agents/main.
