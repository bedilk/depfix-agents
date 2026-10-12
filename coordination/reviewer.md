# Reviewer State

## Current Task
2026-10-12 pre-review: T-19 still blocked in TASKS.json but branch fix/t19-plan-pr-gate is at afb64ca (pushed to origin). 6 commits total since T-18 base (5205b82). Inbox empty, no review_request received. Performed full pre-review — code, tests, lint, mypy all pass.

### Pre-review results (938 passed, lint clean, mypy clean)
Checked items:
1. ✅ `_enrich_removal_from_skill` in runner.py — skill-file enrichment logic is correct. Verified against sentry and stripe skill files. 9 unit tests cover: happy path, prose RHS rejection, missing provider, namespace collision, ambiguous multi-match, `new` keyword stripping.
2. ✅ `upgrade.py:140` gate — now `is_method_removal(change) and not change.new_api`. Allows enriched removals into upgrade plan. 2 unit tests confirm.
3. ✅ `fix_service.py:201` gate — same pattern. 2 unit tests confirm: report-only without new_api, fix pipeline with new_api.
4. ✅ `applicability.py` ghost removal — `old_version=="0.0.0"` short-circuits to APPLIES. 2 unit tests cover resolved==new_version and resolved<new_version.
5. ✅ `repo_exports.py` — removed `installed_sv >= latest_sv` guard; changed sub-case B `new_version` from `installed` to `latest_version`. 2 new tests.
6. ✅ installed==latest_version edge (afb64ca) — properly handled by applicability.py ghost check + repo_exports guard removal working together.

### Non-blocking observations
- `if match is None: return None` inside candidates loop: prose RHS short-circuits before checking other lines. Intentionally conservative — if the skill file says migration is non-trivial, decline. Acceptable.
- Double tarball fetch for installed version (line 127 + 197 in repo_exports.py): performance, not correctness. Known from T-15.
- `installed > latest` in repo_version_exports_diff: could produce false-positive sub-case A records. Very rare.
- Ghost removal in declared_range-only path (no resolved_version): would use target_major=0, filtered NOT_AFFECTED. Unlikely since ghost records require an installed version to be created.

### Remaining before formal verdict
- ⬜ Acceptance dry-run on bedilk/depfix-test-sentry-v6-app showing startTransaction fix plan (required by T-19 acceptance criteria)
- ⬜ T-19 status must be set to `review` by implementer
- DB carry-forward: 477 stale sentry/method_removed rows still need reset (T-20 prereq)

## Waiting For
- T-19 (plan fix for fix PRs): blocked in TASKS.json, but branch pushed to origin at afb64ca. No PR opened, no CI runs. Implementer must: complete acceptance dry-run, set status=review.
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
