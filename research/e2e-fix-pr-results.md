# T-20: End-to-End Fix-PR Results (3 repos)

**Date:** 2026-10-12 13:14–13:21 CEST
**Branch:** `fix/t19-plan-pr-gate` @ `bb562a3` (dependency_check)
**Method:** `depfix init && depfix scan --repo <repo> --provider <provider> && depfix plan <repo> --provider <provider> && depfix apply [--dry-run] <repo> --provider <provider>`
**Raw logs:** `dependency_check/.local/t20/*.log` (not committed — local scratch)

## Prerequisites performed (per T-18 receipt / T-20 task notes)

1. Backed up `depfix.db` → `dependency_check/.local/backups/depfix.db.pre-t20-20261012T131411` (8.5MB).
2. Deleted 477 stale `breaking_change` rows with `package='sentry', kind='method_removed'` (confirmed count via `sqlite3 depfix.db "SELECT package, kind, COUNT(*) ... "` before deleting).
3. Reset `classified_at = NULL` on the 2 `ts_exports:@sentry/node` `change_event` rows (ids 29, 125) so they re-classify with the correct package (`@sentry/node`, not `sentry`).
4. Checked out `fix/t19-plan-pr-gate` (origin HEAD `bb562a3`, newer than the `0e9db45` cited in the task — includes an additional `ci: fix pre-existing CI gaps` commit). Found uncommitted WIP on the prior branch (`fix/t18-multi-major-removals`: edits to `classifier.py`, `runner.py`, 10 `provider_*.md` skill files, `repo_exports.py`, `test_repo_aware_exports.py`) blocking the checkout — did not discard it; `git stash push` with a descriptive message before switching branches, left recoverable.
5. `depfix init --offline --keep-state` — clean preflight (providers.yaml 40/40 enabled, db reachable, LLM/GitHub App checks skipped only because of `--offline`).

## Repo 1: bedilk/depfix-test-sentry-v6-app (sentry) — version drift + API drift

| Stage | Result |
|---|---|
| `scan` | 31 actionable call sites across 8 files (e.g. `src/performance.js`, `src/tracing.js`, `src/sentry.js`). Exit 1 — but the non-zero exit is the built-in post-scan eval-corpus regression gate (91% < 100% `--fail-under`), **not a scan failure**; same 3 pre-existing spec_diff gaps tester has reported since 2026-10-05 (multi-op removal, new-required-field, response-shape-via-type). |
| `plan` | Exit 0. Drift `@sentry/node 10.75.3 → 11.6.0` (major, PR planned). 8 `report_only` removed-symbol findings (no replacement available, correctly left as information-only). 2 removed symbols **with known replacements** (`sentry.startTransaction`→`startSpan`, `sentry.getCurrentHub`) reached fix-generation, LLM produced edits, but verification reverted both (`no_kept_edits` — "this fix was rolled back by verification"). 1 PR planned (version bump only). Cost $0.0186. |
| `apply --dry-run` | Exit 0. Same outcome predicted: 1 PR, 1 failed change (the two reverted API fixes count as "1 failed change" in the summary), $0.0128. |
| `apply` (real) | Exit 0. **Real PR opened: https://github.com/bedilk/depfix-test-sentry-v6-app/pull/1** — `depfix: migrate @sentry/node@10.75.3 -> @sentry/node@11.6.0`, draft, state OPEN, mergeable. Diff: `package.json` (20+/20-), `package-lock.json` (5179+/4800-). Body correctly flags "MAJOR VERSION REVIEW... requires human approval", confidence `low`, verification "disabled; only a syntax check ran" (because dependency install failed for verification, see below). One unrelated change (`Node.js` entry) failed with `plan artifact is stale: repository HEAD changed since plan; run plan again` — benign re-evaluation artifact, not the repo's actual fix. |

**Verdict:** Version-drift PR pipeline works end-to-end and opened a real, correctly-labeled draft PR. **API call-site fix generation works (correct symbol routing, correct replacement code generated) but the fix is never kept** — this is the exact T-23 gap (stale lockfile in the test repo → frozen `npm ci` fails during verification → verifier reverts unconditionally since the original file "fails" identically). Confirmed independently here, consistent with T-23's root-cause report (`research/t23-verification-rollback.md`).

## Repo 2: bedilk/depfix-test-openai-v3-chat (openai) — version drift only

| Stage | Result |
|---|---|
| `scan` | 8 actionable call sites (`src/chat.js`, `src/embeddings.js`, etc.) — matches T-12's prior count. Drift: installed `6.49.0` → feed `7.32.0`, decision **`major-gap review`** — "no automatic edit is planned" by design. Exit 1, same pre-existing eval gate, not a regression. |
| `plan` | Exit 0. `0 PR(s), 0 failed change(s), $0.0000 spent`. No LLM calls (nothing reached fix-generation; major-gap review changes aren't offered a fix). |
| `apply --dry-run` | Exit 0, but **1 failed change**: an unrelated classified event `openai openai@3.3.0` (stale PyPI-side classification, unrelated to this repo's actual npm `openai@6.49.0`) errored with `plan artifact is stale: repository HEAD changed since plan; run plan again`. 0 PRs. |
| `apply` (real) | Exit 0. Same: 0 PRs, same 1 failed change on the unrelated `openai@3.3.0` event. **No PR opened** — correct per the major-gap-review decision. |

**Verdict:** Correct behavior — major version gaps are deliberately left report-only, no PR. One minor rough edge: the stale/unrelated `openai@3.3.0` event surfaces a confusing `"plan artifact is stale"` error instead of a clean `no_call_sites`/skip message — cosmetic, didn't affect the real outcome, not investigated further per task scope (report, don't work around).

## Repo 3: bedilk/seed-openai-v3-to-v4 (openai) — vendored dependency

| Stage | Result |
|---|---|
| `scan` | 1 actionable call site (`src/migration.js:6`, `openai.createChatCompletion`) — matches T-10 exactly. Dependency is vendored (`file:./vendor/openai`) → decision **`version unresolved`** (no resolvable semver). **Note:** the first scan attempt's log file was silently overwritten mid-run by what appears to be a concurrent process (another agent instance) also scanning the same repo against the same shared `dependency_check` checkout and writing to the same relative log path — a recurrence of the "multiple concurrent same-role processes" hazard this file has flagged repeatedly since 2026-10-12 00:31. Re-ran with a unique `--log-level DEBUG` + unique filename to get a trustworthy, self-consistent log; that run is what's reported here. |
| `plan` | Exit 0. `0 PR(s), 0 failed change(s), $0.0000 spent` — every symbol is `no_call_sites` except the version-unresolved manifest match, which has nothing committable to plan. |
| `apply --dry-run` | **Exit 2** — `No plan artifact found for bedilk/seed-openai-v3-to-v4. Run first: depfix plan ... --from-event <ID>`. |
| `apply` (real) | **Exit 2**, identical error. **No PR opened**, and apply never even attempts a run. |

**Verdict — real gap, not user error:** `depfix plan` only writes a `PlanArtifact` file to disk when at least one change has committable edits or is an upgrade; a "version unresolved" vendored-dependency outcome produces neither, so no artifact is ever written. `apply <repo> --provider X` (without `--from-event`) then can't discover any plan artifact for that repo and hard-fails with exit 2, even though `plan` itself completed cleanly and reported "0 PRs, nothing to do." A user following the documented `init → scan → plan → apply` happy path hits a confusing hard failure on this entire class of repo (any repo whose only drift is unresolvable/vendored), instead of `apply` also reporting "0 PRs" gracefully like `plan` did. Source: `src/depfix/cli.py:2037-2050`.

## Overall Assessment

| Repo | Scan | Plan | PR opened | Correct? |
|---|---|---|---|---|
| depfix-test-sentry-v6-app | 31 call sites | 1 PR (version bump) | **Yes** — https://github.com/bedilk/depfix-test-sentry-v6-app/pull/1 | Version-bump PR correct and well-labeled. API call-site fixes (startTransaction, getCurrentHub) generated correctly but reverted by verification — known T-23 gap, confirmed again here. |
| depfix-test-openai-v3-chat | 8 call sites | 0 PRs | No (by design — major-gap review) | Correct. |
| seed-openai-v3-to-v4 | 1 call site | 0 PRs | No — `apply` errors (exit 2) before it can even try | `plan` behaves correctly; `apply` has a real usability/correctness gap for the "nothing committable" case. |

**End-to-end pipeline works for the primary case it was built for** (version-drift PR with correct semver comparison, correct GitHub PR, correct draft/major-version labeling). Two gaps surfaced, both already scoped elsewhere or newly found:
1. **Known (T-23):** API call-site fixes are generated correctly but never kept, because the sentry test repo's `npm ci --ignore-scripts` fails during verification (stale lockfile) and the verifier reverts unconditionally rather than comparing against a working baseline. Root cause already documented in `research/t23-verification-rollback.md`; not re-derived here.
2. **New:** `apply` cannot gracefully handle a repo where `plan` found literally nothing committable (vendored/unresolved-version case) — hard exit 2 instead of "0 PRs, nothing to do." Recommend as a follow-up task for implementer: either have `plan` write a no-op/report-only artifact in this case, or have `apply`'s artifact-discovery path treat "no artifact, but plan would legitimately find 0 PRs" the same way `plan` does, instead of erroring.

Did not chase or attempt to fix either gap — out of scope for tester role per AGENTS.md (report exactly what happened, no interpretation beyond root-cause pointers already requested by the task).
