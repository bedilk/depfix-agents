# Fix Verification Revert Analysis: Why startTransaction/getCurrentHub Get REVERTED

## Summary

The T-19 dry-run on `bedilk/depfix-test-sentry-v6-app` demonstrates that the METHOD_REMOVED
gate fixes work correctly: `startTransaction` and `getCurrentHub` reach fix-generation (while
16 no-replacement removals correctly stay `report_only`). However, both generated fixes are
**REVERTED** by the verification pipeline, resulting in `no_kept_edits`.

This document traces the exact verification path to identify the root cause.

## Evidence Source

- Dry-run log: `/tmp/t19_plan_dryrun.log` (2090 lines, from 2026-10-12 12:46)
- Test repo: `bedilk/depfix-test-sentry-v6-app` (`@sentry/node@10.75.3`)

## Dry-Run Results Summary

| Change | Files Fixed | Verdict | Outcome |
|--------|-------------|---------|---------|
| @sentry/node 10.75.3→11.6.0 (drift) | package.json, package-lock.json | would process | Version bump PR planned |
| sentry.startTransaction (METHOD_REMOVED) | src/performance.js, src/tracing.js | REVERTED | no_kept_edits |
| sentry.getCurrentHub (METHOD_REMOVED) | src/tracing.js | REVERTED | no_kept_edits |
| 16 other removals (no replacement) | — | report_only | Correctly skipped by T-19 gate |

## Root Cause Analysis

### Factor 1: Change Ratio Validator Rejects performance.js

**File:** `src/depfix/validators/javascript.py:74-82`
**Threshold:** 50% change ratio, minimum 8 lines

The LLM fix for `performance.js` triggers a validation warning:
```
depfix.validators.javascript - WARNING - Large change ratio detected: 69.23%
```

`performance.js` has 38 lines. The `startTransaction → startSpan` migration requires converting
from imperative (tx.finish(), tx.setStatus()) to callback pattern (Sentry.startSpan(opts, cb)),
fundamentally restructuring both functions. 69% of lines change — well above the 50% threshold.

**Effect:** The edit is written to disk but marked `SUSPECT` (not `APPLIED`):
```python
# workspace.py:161-165
verdict = EditVerdict.SUSPECT if validation is not None and not validation.is_valid else EditVerdict.APPLIED
```

`SUSPECT` is in `ON_DISK_VERDICTS`, so verification still runs on it. But if verification
can't upgrade it to `KEPT`, the edit stays `SUSPECT` → filtered by `committable_edits()`.

### Factor 2: npm ci Fails for Impact Check Clones

**Log evidence (lines 66-68):**
```
12:46:51.016 - verify.impact - impact check: installing current dependencies for @sentry/node
12:46:51.017 - verify.manager - installing dependencies: npm ci --ignore-scripts (cwd=.../dqv50uj5)
12:46:51.428 - orchestrator.runner - generating and verifying a fix for a49fb6c59168
```

Only 0.41 seconds between `npm ci` start and the fix pipeline's "generating and verifying".
The impact check is BLOCKING (sequential with fix pipeline in `_process_change_body`), so it
must return in <0.41 seconds. This means `npm ci` fails immediately.

**Confirmed by summary output (line 88):**
```
impact check skipped: baseline install failed (install error)
```

The impact check's `install_dependencies()` uses `frozen=True` (default) → `npm ci`
(`manager.py:248`). When npm ci fails, impact check returns early (`impact.py:141-145`).

### Factor 3: Verification Install (frozen=False → npm install)

The fix pipeline creates its Verifier with `frozen_install=False` (`fix_service.py:587`).
This means verification's `install_dependencies()` uses `npm install` (not `npm ci`).

**For version drift:** The log confirms this works:
```
12:46:31 - verify.manager - installing dependencies: npm install --ignore-scripts  ← frozen=False
12:46:33 - verify.runner - running tests: npm test  ← baseline
12:46:35 - verify.runner - running tests: npm test  ← after-fix
```

**For method_removed (startTransaction):** The log shows a SECOND `npm ci` at line 75:
```
12:46:56.093 - verify.manager - installing dependencies: npm ci --ignore-scripts (cwd=.../dqv50uj5)
```

This `npm ci` (not `npm install`) is inconsistent with `frozen_install=False`. Two hypotheses:
1. This is from the impact check's second install step (which uses `frozen=False` → should be `npm install`)
2. This is from a fallback path in `_decide_without_tests` where install is retried

**Critical observation:** No `running tests` entries appear for the startTransaction or
getCurrentHub changes. The version drift change has two explicit test run log entries, but
the method_removed changes have zero. This strongly suggests the test suite NEVER RUNS for
these changes.

### Factor 4: _decide_without_tests Fallback → Smoke Check Fails

When tests can't run (install failure, no test script, etc.), the verification path is:

```
_decide_without_tests()
  → JavaScript ecosystem → try tsc --noEmit
    → If tsc not usable (plain .js, no tsconfig) → suspect()
      → Try characterization (single-file only)
      → Per-file smoke check: node -e "try { require('./path'); } catch(e) { exit(1) }"
        → If require fails → editor.revert(relpath) → REVERTED
```

For `performance.js`: `require()` executes `const Sentry = require("@sentry/node")`.
If node_modules is absent or incomplete (npm ci failed, npm install didn't run):
- `require("@sentry/node")` throws MODULE_NOT_FOUND → exit(1) → smoke FAILS → **REVERTED**

For `tracing.js`: Same pattern — `require("@sentry/node")` fails → **REVERTED**

### Factor 5: Test Mock Mismatch (secondary)

Even if tests DID run, the test repo's mock is interesting:

```javascript
jest.mock("@sentry/node", () => ({
  startSpan: jest.fn((opts, cb) => cb({ setStatus: jest.fn(), setAttribute: jest.fn() })),
  // NO startTransaction mock
  // NO getCurrentHub mock
}));
```

**Baseline:** `withTracing()` calls `Sentry.startTransaction()` → undefined → TypeError
**After fix (startTransaction only):** `withTracing()` calls `Sentry.startSpan()` → works,
BUT also calls `Sentry.getCurrentHub()` → undefined → TypeError (different error)

Test identity is the same ("tracing module > withTracing wraps fn in a span"), so
`new_failures = after_fix.failed - baseline.failed = {}` → no new failures → KEPT.

This means IF tests ran, tracing.js would get KEPT (fixing a preexisting test failure).
But performance.js has NO test coverage → would still go to fallback oracles.

## Verification Pipeline Architecture (for reference)

```
LLM generates fix → Validator (syntax + change ratio)
  → SUSPECT (>50% change) or APPLIED (<50%)
  
Verifier.verify(edits):
  1. has_test_script? (yes — "jest --passWithNoTests")
  2. install_dependencies(frozen=False) → npm install
  3. If install fails → _decide_without_tests:
     a. tsc --noEmit (plain JS → not usable)
     b. suspect() → characterization + smoke check
     c. Smoke: node -e "require('./file')" → needs node_modules
     d. If require fails → REVERTED
  4. If install succeeds → run tests:
     a. Baseline: revert edits, run tests
     b. After-fix: re-apply edits, run tests
     c. Diff failures → attribute to files → KEPT or REVERTED
```

**Key files:**
| Component | Path | Key Lines |
|-----------|------|-----------|
| Change ratio validator | validators/javascript.py | 74-82 |
| Frozen install mapping | verify/manager.py | 236-248 |
| Fix service verifier config | core/fix_service.py | 572-588 |
| Verify main path | verify/verifier.py | 206-357 |
| _decide_without_tests | verify/verifier.py | 529-750 |
| Smoke check (JS) | verify/smoke.py | 44-81 |
| Smoke revert in suspect() | verify/verifier.py | 582-598 |
| Impact check install | verify/impact.py | 133-145 |
| committable_edits filter | gh/pr.py | 377-412 |

## Recommendations for T-20 / Follow-up

### Fix 1: Investigate npm ci failure in clones (HIGH priority)

npm ci fails immediately in impact check clones. This affects ALL repos processed by
`depfix plan`. The version drift path works because the fix pipeline's verifier uses
`npm install` (frozen=False), but if verification falls to _decide_without_tests for
ANY reason, the smoke check needs node_modules to be present.

**Diagnostic:** Add `logger.warning` to `install_dependencies` when npm ci fails, logging
`install.stderr`. Check if package-lock.json exists in the clone dir, and if npm version
is compatible.

### Fix 2: Raise or remove change ratio threshold for API migrations (MEDIUM priority)

The 50% change ratio threshold at `validators/javascript.py:74` is too strict for API
migrations that require structural rewrites (imperative → callback). The `startTransaction →
startSpan` migration necessarily changes 69% of a 38-line file. Options:
- Raise the threshold to 75% or 80%
- Exempt METHOD_REMOVED changes from the ratio check
- Make the threshold configurable per-change-kind

### Fix 3: Ensure npm install runs before smoke check (HIGH priority)

In `_decide_without_tests` → `suspect()`, the smoke check tries `require()` which needs
node_modules. But if the primary install failed, node_modules may not exist. The tsc
fallback at line 654-662 already has a retry install, but `suspect()` does NOT. If the
tsc retry also fails, the smoke check runs without deps.

**Fix:** In `suspect()` (verifier.py:552), check if `resolved_install.ok` is False, and
if so, skip the smoke check entirely (leave as SUSPECT rather than REVERTED). A module
that can't be loaded due to missing deps is not evidence of a bad fix.

### Fix 4: Consider bundling related removals into one fix (LOW priority)

`startTransaction` and `getCurrentHub` are separate breaking changes processed independently.
The LLM fixes `startTransaction` but leaves `getCurrentHub` broken in the same function.
Bundling all removals for the same file into one fix prompt would produce higher-quality
fixes and better test results.

## Test Repo Recommendation

The test repo `bedilk/depfix-test-sentry-v6-app` has a mock that already uses the v8 API
(startSpan) but the source code uses v7 API (startTransaction). This is correct for testing
depfix's detection, but the mock mismatch means the test suite provides IMPERFECT verification
signal — the test already fails in baseline for a different reason than the fix addresses.

Consider adding a test specifically for `profileDbQuery` (from performance.js) to improve
verification coverage.
