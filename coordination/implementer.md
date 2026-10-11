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

## Current Status (last checked 2026-10-11)
New mission in TASKS.json: T-17 (researcher, running) -> T-18/T-19 (ready, unowned,
depend on T-17) -> T-20/T-21 (tester) -> T-22 (implementer: open PR for T-18/T-19 changes).
No task currently has status=running/owner=implementer. Not starting T-18 until principal
assigns it (it also depends on T-17 finishing).

Found dependency_check in a broken, uncommitted state: a prior migration of
depfix-agents work (provider skills, eval corpora, repo_exports.py T-15 integration)
had been copied over as untracked files but never committed, and was missing the
corresponding T-6 ruby_runtime fixes -- make test had 10 failures, make lint/typecheck
were also broken on dependency_check main itself (pre-existing, unrelated to the
migration: numpy mypy stub issue + 3 ruff import-sort errors). Fixed all of it, see
"Completed Work" below (branch fix/migrate-agent-changes, PR #10). Messaged principal
and researcher.

IMPORTANT: discovered multiple concurrent agent processes operating on the SAME
dependency_check working directory (not separate worktrees) -- hit a real git race
(a concurrent process checked out a different branch mid-commit, landing my commit on
their branch). Recovered manually, nothing lost, but flagged to principal as a
systemic hazard (dependency_check has no commit lock like depfix-agents' .local/git.lock).
Be careful with branch checkouts in dependency_check until this is addressed -- verify
`git branch --show-current` right before committing, not just at the start.

## Notes
- typecheck: python_version updated to 3.12, manager.py None guard added.
- make eval reports 91% (30/33 scored) due to 3 pre-existing spec_diff failures unrelated to my tasks.
- All pushes successful to agents/main.

- 2026-10-11: Migrated pending work to dependency_check (depfix-agents/research/cross-repo-migration-gap.md
  gap list): 40 provider skill files, sentry_v8/ruby eval corpora, repo_exports.py +
  _augment_with_repo_exports orchestrator wiring, plus the T-6 ruby_runtime/ruby_manifests/
  ruby_lockfile fixes the copied test files needed but hadn't received. Also fixed
  pre-existing, unrelated breakage on dependency_check main: mypy python_version bumped
  to 3.12 + numpy.* ignore-errors override (numpy's PEP 695 stub syntax was failing
  typecheck), and 3 files with ruff import-sort errors (manifests.py, rss.py, parsers.py).
  dependency_check: make test 917 passed, make lint clean, make typecheck clean,
  make eval 91% (30/33, matches known baseline). Committed on fix/migrate-agent-changes,
  pushed to origin, PR: https://github.com/bedilk/dependency_check/pull/10.
