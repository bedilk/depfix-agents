# T-17: Why `depfix plan` Produces 0 PRs After Scan Finds Call Sites

## Executive Summary

Three independent issues combine to prevent any PR from being generated. When all three are fixed, the pipeline can produce fix PRs for API call-site drift.

| # | Issue | Impact | Fix complexity |
|---|---|---|---|
| 1 | METHOD_REMOVED → REPORT_ONLY | All ts_exports-derived changes produce report-only outcomes, never fix PRs | Medium |
| 2 | No multi-major BreakingChange records | Removals older than one major (e.g., v6→v8) never appear in DB | Fixed by T-15 |
| 3 | `depfix plan` never captures drift | Without prior `depfix scan`, no DEPENDENCY_VERSION_BUMP exists | Medium |

## 1. Data Flow: scan output → BreakingChange → assess_scan_change → plan filtering

### `depfix scan` path (creates the data):

```
depfix scan --repo bedilk/depfix-test-sentry-v6-app --provider sentry
  │
  ├─ ensure_changes_detected("sentry")
  │    ├─ Watcher.run_once() → polls feeds, sets baselines
  │    │   └─ ts_exports_diff: downloads @sentry/node@10.76.1 vs @11.5.0
  │    │      → 477 SpecChange rows (EXPORT_REMOVED)
  │    │
  │    └─ classify_pending() → reads events from DB
  │       ├─ event.raw is NOT persisted (no column on ChangeEventRow)
  │       ├─ package = event.raw.get("package") or event.provider_id → "sentry" ← BUG
  │       └─ classify_spec_changes(package="sentry") → 477 BreakingChange(METHOD_REMOVED)
  │
  ├─ scan_checkout() → 31 actionable call sites (startTransaction, captureException, etc.)
  │
  └─ capture_repository_dependency_drift()
       ├─ installed=10.75.3, feed latest=11.6.0
       └─ creates DEPENDENCY_VERSION_BUMP: @sentry/node@10.75.3 → 11.6.0
```

### `depfix plan` path (consumes the data):

```
depfix plan --repo bedilk/depfix-test-sentry-v6-app --provider sentry
  │
  ├─ _load_pipeline_changes()
  │    ├─ Loads 477 METHOD_REMOVED (package="sentry")       ← all pass kind filter
  │    └─ Loads 1 DEPENDENCY_VERSION_BUMP (package="@sentry/node") ← only if prior scan ran
  │
  ├─ Orchestrator._run_repo_body()
  │    │
  │    ├─ _prescan_providers() → scans repo, populates _scan_cache
  │    │    Result: 31 actionable sites, dep @sentry/node@10.75.3
  │    │
  │    ├─ _augment_with_repo_exports()        [T-15 code, IS wired up]
  │    │    ├─ Downloads @sentry/node@10.75.3 exports and @11.6.0 exports
  │    │    ├─ Sub-case A: removed = v10_exports - v11_exports → synthetic BCs
  │    │    └─ Sub-case B: call sites using exports absent from v10 → synthetic BCs
  │    │    Result: synthetic BreakingChange(METHOD_REMOVED) added
  │    │
  │    ├─ _match_filter_and_cap()
  │    │    For each change: assess_scan_change(scan_result, change)
  │    │    ├─ change_applies(): package "sentry" vs dep "@sentry/node" → UNKNOWN (no match)
  │    │    │                    UNKNOWN doesn't block, continues to call-site check
  │    │    ├─ DEPENDENCY_VERSION_BUMP → ACTIONABLE (version behind)
  │    │    ├─ METHOD_REMOVED with matching call site → ACTIONABLE
  │    │    └─ METHOD_REMOVED with no matching call site → NO_CALL_SITES
  │    │    Result: ~6 ACTIONABLE, ~471 NO_CALL_SITES
  │    │
  │    └─ Per-change processing (_process_change_body)
  │         │
  │         ├─ DEPENDENCY_VERSION_BUMP:
  │         │    is_method_removal? → False
  │         │    build_upgrade_plan():
  │         │      relevant = [c for c if not c.package or c.package == "@sentry/node"]
  │         │      → 477 MRs have package="sentry" ≠ "@sentry/node" → EXCLUDED  ← BUG
  │         │      → is_method_removal(change) → continue                       ← EXCLUDED
  │         │      migrations = [] → has_source_work = False
  │         │    Falls through to manifest-only drift
  │         │    _plan_drift() → plan artifact with manifest bump
  │         │    Result: ✅ PR (manifest-only version bump, draft review)
  │         │
  │         └─ METHOD_REMOVED (all 477 + synthetics from T-15):
  │              is_method_removal? → True
  │              → _report_removal() → REPORT_ONLY
  │              Result: ❌ No PR, information only
```

### Net result:
- **With prior `depfix scan`**: 1 manifest-only drift PR + many REPORT_ONLY
- **Without prior `depfix scan`**: 0 PRs (all METHOD_REMOVED → REPORT_ONLY)

## 2. Why No BreakingChange Records Exist for Multi-Major Jumps

### The ts_exports_diff limitation

`TsExportsSource.poll()` at `dependency_check/src/depfix/sources/ts_exports.py:98-168`:

```
First poll: old_token = _previous_major_release(versions, latest)
            → highest stable version with a LOWER major than latest
            → only looks back ONE major
Subsequent: old_token = last polled version (state.last_token)
```

For `@sentry/node` with latest = v11.6.0:
- `_previous_major_release()` finds highest v10.x.y → v10.76.1
- Diff: v10.76.1 → v11.5.0 → 477 removals (all internal SDK symbols)
- Removals from v6→v7, v7→v8, v8→v9, v9→v10 are **invisible**

### What startTransaction illustrates

- `startTransaction` was the primary Sentry tracing API in v6/v7
- Removed in v8 (replaced by `startSpan` via OpenTelemetry integration)
- NOT in the v10→v11 diff (already gone in v10)
- The test repo calls `startTransaction` at `src/performance.js:5,19`
- No BreakingChange record exists for it in the DB

### T-15 repo_exports.py closes this gap

`dependency_check/src/depfix/sources/repo_exports.py:96-224`:
- **Sub-case A** (`installed_exports - latest_exports`): catches exports removed since the repo's installed version
- **Sub-case B** (`call site uses export absent from installed version`): catches ghost APIs (removed before the installed version)
- Both produce `BreakingChange(kind=METHOD_REMOVED, new_api="")`

**But**: the synthetic changes are also METHOD_REMOVED → same REPORT_ONLY outcome (see issue #1).

## 3. T-15 Code Status in dependency_check

### Present and wired up

| File | Path | Status |
|---|---|---|
| `repo_exports.py` | `src/depfix/sources/repo_exports.py` | ✅ 224 lines, complete |
| `_augment_with_repo_exports` | `src/depfix/orchestrator/runner.py:776-866` | ✅ Called at line 396 |
| `test_repo_aware_exports.py` | `tests/unit/test_repo_aware_exports.py` | ✅ 24 tests pass |

### Why T-15 alone is insufficient

T-15 correctly synthesizes BreakingChange records for cross-major-version removals. However:

1. All synthetic changes have `kind=METHOD_REMOVED` and `new_api=""`
2. `_process_change_body` at `runner.py:991` checks `is_method_removal(change)` first
3. METHOD_REMOVED → `_report_removal()` → `REPORT_ONLY` — no fix, no PR
4. Even `build_upgrade_plan` at `upgrade.py:140-141` excludes METHOD_REMOVED:
   ```python
   if is_method_removal(change):
       continue  # skipped from upgrade migrations
   ```

## 4. Root Cause Summary

### Primary: METHOD_REMOVED → REPORT_ONLY (no fix pipeline runs)

**File**: `dependency_check/src/depfix/orchestrator/runner.py:991-1000`
```python
if is_method_removal(change):
    return self._report_removal(...)  # REPORT_ONLY, no PR
```

Every ts_exports_diff-derived change is METHOD_REMOVED. The fix pipeline never runs for these.

**Why this exists**: A removed symbol with no known replacement (`new_api=""`) can't be automatically fixed by rewriting `oldCall()` → `newCall()`. The pipeline conservatively reports rather than guessing.

**What needs to change**: The fixer has enough context (from skill files, migration guides, release notes) to generate fixes for removed APIs even without a `new_api` field. T-18 should either:
- Make synthetic changes carry `new_api` from skill file knowledge (change kind to METHOD_RENAMED)
- Or allow METHOD_REMOVED to enter the fix pipeline when replacement info is available from other sources

### Secondary: Package name mismatch ("sentry" vs "@sentry/node")

**File**: `dependency_check/src/depfix/classify/classifier.py:40`
```python
package = str(event.raw.get("package") or event.provider_id)
```

`event.raw` is NOT persisted to DB (`ChangeEventRow` has no `raw` column, see `storage/schema.py:102-150`). When events are re-read from DB, `raw` is empty → fallback to `event.provider_id` = `"sentry"`. The correct package `@sentry/node` is lost.

**Impact**: `build_upgrade_plan` filters: `relevant = [c for c if not c.package or c.package == package]`. Since `"sentry" != "@sentry/node"`, all 477 METHOD_REMOVED records are excluded from upgrade plans — even if the METHOD_REMOVED exclusion were removed.

**Fix**: Recover package from `event.feed_key` (e.g., `ts_exports:@sentry/node` → `@sentry/node`) or from `spec_changes[0].pointer` (e.g., `@sentry/node#startTransaction` → `@sentry/node`).

### Tertiary: `depfix plan` never captures drift

**File**: `dependency_check/src/depfix/cli.py:1908-2090`

`_cmd_pipeline` (which handles `plan` and `apply`) does NOT call `capture_repository_dependency_drift`. It only loads pre-existing BreakingChange records from the DB. Drift capture happens in `_cmd_scan` at `cli.py:1275`.

**Impact**: Without a prior `depfix scan` on the specific repo, no DEPENDENCY_VERSION_BUMP record exists. The plan has only METHOD_REMOVED changes → all REPORT_ONLY → 0 PRs.

**Fix**: Either:
- Document that `depfix scan` must run before `depfix plan` (may already be intended)
- Or have the orchestrator capture drift during pre-scan (it has the scan result + dependencies)

## 5. Verified Data: bedilk/depfix-test-sentry-v6-app

```
Repo installed version: @sentry/node@10.75.3  (package.json + lockfile)
Feed latest version:    @sentry/node@11.6.0
Feed ts_exports baseline: 10.76.1 → 11.5.0 (477 METHOD_REMOVED in DB)

Scan results:
  Files scanned:      8
  Total call sites:   31
  Actionable sites:   31
  Key call sites:     sentry.startTransaction (src/performance.js:5,19)
                      sentry.captureException (src/performance.js:10)
                      sentry.setupConnectErrorHandler (src/connect-adapter.js:15)
  Dependencies:       @sentry/node@10.75.3

DB state:
  startTransaction BreakingChange: NONE (removed before v10→v11 window)
  METHOD_REMOVED records:          477 (all v10.76.1→v11.5.0, package="sentry")
  DEPENDENCY_VERSION_BUMP:         0 for this repo (not scanned)
  Total sentry changes:            478
```

## 6. Recommended Fix Order for T-18/T-19

1. **Fix package recovery** (classifier.py:40): Extract package from `event.feed_key` when `event.raw` is empty
2. **Allow METHOD_REMOVED in upgrade plan** (upgrade.py:140): Remove the `is_method_removal → continue` gate, or add a secondary path that uses skill-file context
3. **Have orchestrator capture drift** if not already captured (runner.py): Call `capture_repository_dependency_drift` in `_prescan_providers` or `_augment_with_repo_exports`
4. **Make T-15 synthetic changes carry replacement info** when available from provider skill files
