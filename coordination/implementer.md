# Implementer State

## Current Task
No active task. All assigned tasks are done.

## Completed Work
- T-3: Added provider_redis.md skill file covering ioredis, node-redis v3/v4 (with breaking-change notes), redis-py, redis gem.
  - provider_postgresql.md was already present and complete.
  - Fixed pre-existing test failure: test_repo_shipped_providers_file_is_valid expected 25 providers but providers.yaml had 27 (mysql + astro added before my round). Updated count to 27.
  - make test: 872 passed, 0 failed.
  - Committed in c4b3ab3. Reviewer accepted (round 2).

- T-5: Added 5 ruby ecosystem eval cases.
  - Added `ecosystem` field to `EvalCase` (defaults to "javascript").
  - Updated `loader.py` to read the `ecosystem` field from YAML.
  - Updated `runner.py` `_run_call_sites` to route non-JS ecosystems to `GenericImportScanner`.
  - Updated `Makefile` eval targets to use `PYTHONPATH=src` and `--corpus-dir src/depfix/evals/corpus`.
  - Added 4 Ruby fixture directories under tests/fixtures/.
  - Added src/depfix/evals/corpus/ruby_callsites.yaml with 5 verified cases.
  - make test: 872 passed, 0 failed. make eval: 10/10 call_sites pass.
  - Accepted by reviewer (round 2).

- T-6: Fixed all 6 issues from reviewer rejection of ruby fixer.
  - build_ruby_install_argv: added bundler() PATH check (return None when missing).
  - test_argv: removed unused junit_xml_path parameter.
  - _iter_gemfiles in ruby_manifests.py: removed *.gemspec from glob.
  - _SKIP in ruby_manifests.py: added .depfix-bundle.
  - ruby_lockfile_paths: added .depfix-bundle filter.
  - Deleted orphaned install_argv() and build_ruby_test_argv() from ruby_runtime.py.
  - Added 21 unit tests in tests/unit/test_ecosystems_ruby_runtime.py.
  - make test: 893 passed, 0 failed. Committed in 6844154. Accepted by reviewer.

- T-4: Implemented 10 sentry v7→v8 eval cases.
  - Created tests/fixtures/sentry_v7_project/ (package.json + src/setup.js, perf.js, hub.js, breadcrumbs.js)
  - Added src/depfix/evals/corpus/sentry_v8_callsites.yaml with 10 cases.
  - make eval: 91% (30/33 scored). Committed in 113987b. Accepted by reviewer.

- T-15: Repo-version-aware ts_exports diff — detect old-API removals across multiple major versions.
  - Sub-case A: export existed in installed version but absent in latest.
  - Sub-case B: export absent from installed version (removed before installed version, e.g. sentry startTransaction removed in v8, lockfile has v10).
  - Added `_export_name_from_symbol(symbol, provider_id) -> str | None` helper.
  - Modified `synthetic_changes_for_scan` in `src/depfix/sources/repo_exports.py`.
  - Added 8 unit tests in `tests/unit/test_repo_aware_exports.py`.
  - make test: 917 passed, 0 failed. make typecheck: 0 errors. make lint: clean.
  - Committed in 7896cff. ACCEPTED by reviewer (T-15_receipt.json).

## Round 28 Status
All assigned tasks complete. No new tasks assigned. Inbox empty this round.

Only running task is T-11 (tester: real-repo scan). All other tasks are done.

Researcher has proactive specs ready for: resend, cloudflare, datadog, plaid, hubspot, shopify, segment, mixpanel, bugsnag, newrelic, amplitude, square, pinecone, twilio (in research/).
All agents idle except tester (T-11). Ready for new task assignment when principal dispatches.

## Notes
- typecheck: python_version updated to 3.12, manager.py None guard added.
- make eval reports 91% (30/33 scored) due to 3 pre-existing spec_diff failures unrelated to my tasks.
- All pushes successful to agents/main.
