# Implementer State

## Current Task
T-18 ACCEPTED by reviewer (coordination/review/T-18_receipt.json). No task currently
running/owner=implementer. T-19 is status=ready/owner=null with both deps (T-17, T-18)
satisfied — eligible for dispatch, but not self-starting it; waiting for principal to
assign per task-driven protocol. Idle.

## Status check (2026-10-12, post-T-18 acceptance)
Read AGENTS.md, TASKS.json, inbox per startup protocol. TASKS.json already shows T-18
status=done (reviewer accepted, commit 5205b82 / PR #11). One stale inbox message from
principal (ts 22:08:14, pre-acceptance) asking me to confirm commit-gate.sh was run for
5205b82 and paste make test/lint/typecheck results, since .local/push-history.log was
empty. Replied: scripts/commit-gate.sh is a depfix-agents-repo-local script (cds to
depfix-agents root, disables push to origin for dependency_check) — it was never
applicable to dependency_check commits, and dependency_check has no .local dir /
commit-gate script of its own. For T-18 I ran make test/lint/typecheck manually in
dependency_check and pushed via git/gh per AGENTS.md push rules; reviewer's receipt
tests_run field independently confirms identical results (921 passed, lint clean,
typecheck clean) from their own re-run on 5205b82. Acked the message, sent a status
reply + flagged the receipt's non-blocking caveat (477 stale package=sentry
breaking_change rows in depfix.db need classified_at reset before T-20) to principal
for whoever picks up T-20. Not touching T-19 until principal assigns it — current
owner is null, status is ready (not running/owner=implementer).

## IMPORTANT: concurrency protocol (effective 2026-10-11 ~22:02 UTC)
Principal confirmed multiple implementer-loop processes run concurrently against the
SAME dependency_check working directory (no worktree isolation). I personally hit this
live while working T-18: my uncommitted classifier.py/test_classifier.py edits were
swept up and committed/pushed by a concurrent process under its own commit message
before my own `git commit` ran (content identical, message different — confirmed via
`git show --stat` + diff comparison). No work was lost, but it means two instances can
do the same task redundantly and whichever flock-protected commit lands first wins.
**From now on: wrap every git-mutating command in dependency_check (checkout, add,
commit, push) with `flock /Users/bedil_karimov/Documents/depfix-agents/.local/git.lock`,
and run `git branch --show-current` immediately before any commit** — per principal's
directive (inbox messages ffeaf01f.../13bb7efb...).

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

## Current Status (last checked 2026-10-12)
T-18 done, submitted for review: dependency_check PR #11
(https://github.com/bedilk/dependency_check/pull/11), commit 5205b82 on branch
fix/t18-multi-major-removals, base fix/migrate-agent-changes (stacked on #10).

T-18 finding: the multi-major removal *detection* acceptance criteria was already
satisfied by T-15's repo_exports.py (merged into PR #10, not main). The actual gap
was Fix 1 from research/t18-t19-implementation-spec.md: classifier.py set
package=provider_id ("sentry") instead of the real npm package ("@sentry/node") for
persisted ts_exports events, since event.raw isn't persisted to ChangeEventRow.
Generalized the existing NPM/PYPI/RUBYGEMS_DIST_TAG-only feed_key recovery into
_package_from_feed_key(), now applied for all four prefixes (npm:/ts_exports:/pypi:/
rubygems:) unconditionally at the top of classify(). Added 2 unit tests. make test
921 passed, make lint clean, make typecheck clean, make eval 91% (30/33, baseline,
no regression). Did NOT touch upgrade.py/fix_service.py/runner.py gates (T-19 scope
per principal 2026-10-11 23:59 CEST — gate on replacement info, don't remove outright).

Scoping note for whoever picks up T-19: it depends on both T-17 and T-18. T-18's
PR #11 is stacked on #10 (fix/migrate-agent-changes) since repo_exports.py and the
package-recovery fix both live there, not on main. Merge order matters: #10 then #11
then whatever T-19 branches from (should branch from fix/t18-multi-major-removals,
not main, to pick up both).

Hit the documented concurrent-agent git race again (see "IMPORTANT" note below) while
this session was stashing/unstashing changes: a concurrent process force-reset the
local fix/t18-multi-major-removals branch to fix/migrate-agent-changes' tip mid-session.
Landed in my favor this time (same commit I needed as a base) but the hazard is still
unaddressed — always verify `git branch --show-current` immediately before every
commit, not just at session start.

## Previous Status (2026-10-11)
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

- T-18: Fixed classifier.py package-recovery bug (T-17 root cause #2). Generalized the
  DIST_TAG-only feed_key package recovery into `_package_from_feed_key()`, applied at
  the top of `Classifier.classify()` for every feed_key prefix carrying a real package
  identity (npm, ts_exports, pypi, rubygems) — including the scan-bootstrap
  `:repo:<key>:installed:<v>` suffix. Fixes the "sentry" vs "@sentry/node" mismatch that
  made build_upgrade_plan's package filter exclude every ts_exports-derived
  METHOD_REMOVED record (including T-15's multi-major synthetic changes from
  repo_exports.py, which already does the installed-vs-latest compare via
  `_exports_for()` — that mechanism needed no further change for T-18's acceptance).
  Added/confirmed unit tests in tests/unit/test_classifier.py covering npm/pypi/rubygems/
  ts_exports feed-key recovery and the scan-bootstrap suffix case.
  make test: 921 passed, 0 failed. make lint/typecheck: clean.
  Branch fix/t18-multi-major-removals (based on fix/migrate-agent-changes, PR #10, since
  it needs repo_exports.py which isn't on main yet). Committed 5205b82, pushed, PR:
  https://github.com/bedilk/dependency_check/pull/11. TASKS.json already moved to
  status=review/owner=reviewer by the time I checked (concurrent process — see note
  above); sent the missing review_request to reviewer and a status update to principal.
