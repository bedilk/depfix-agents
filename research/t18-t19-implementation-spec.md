# T-18 + T-19 Implementation Spec: Fix Pipeline for METHOD_REMOVED Changes

> **Code baseline (added 2026-10-12):** line numbers in this document refer to
> `dependency_check` branch `fix/migrate-agent-changes` (PR #10), not `main`. On `main`,
> `repo_exports.py` and `_augment_with_repo_exports` do not exist, and runner.py lines shift
> by about 97 (e.g. `is_method_removal` short-circuit: branch :991 vs main :894;
> `_report_removal`: :1418 vs :1321). Verify with
> `git grep -n is_method_removal origin/fix/migrate-agent-changes -- src/depfix/orchestrator/runner.py`.

## Problem Statement

`depfix plan` produces 0 fix PRs for API removals because METHOD_REMOVED changes are
universally blocked at four independent checkpoints. T-17 identified 3 root causes;
this spec maps those to exact code changes in `dependency_check/src/`.

## Architecture Overview

```
scan → classify → BreakingChange(METHOD_REMOVED, package="sentry", new_api="") → DB
                                                                    ↑ wrong     ↑ empty
plan → load changes → _process_change_body
       │                 ├─ runner.py:991 is_method_removal → REPORT_ONLY  ← BLOCK 1
       │                 └─ build_upgrade_plan
       │                      └─ upgrade.py:140 is_method_removal → skip  ← BLOCK 2
       └─ run_fix_for_change
              └─ fix_service.py:201 is_method_removal → empty result     ← BLOCK 3
```

## Fix 1: Package Recovery for ts_exports Events (T-18, HIGHEST PRIORITY)

### Problem
`classifier.py:40` sets `package = event.provider_id` ("sentry") when `event.raw` is empty.
`event.raw` IS populated during initial poll (ts_exports.py:166: `raw={"package": self.package}`)
but is NOT persisted to DB (ChangeEventRow has no `raw` column). On re-read, `raw={}`.

The dist-tag path (classifier.py:89-99) already recovers `package` from `feed_key` for
NPM_DIST_TAG/PYPI_DIST_TAG/RUBYGEMS_DIST_TAG events. The SAME pattern is needed for
TS_EXPORTS_DIFF events.

### Feed key format
- ts_exports: `ts_exports:@sentry/node` (ts_exports.py:96)
- spec_changes pointer: `@sentry/node#startTransaction` (ts_exports.py:134)

### File: `src/depfix/classify/classifier.py`
### Location: lines 39-40

### Current code
```python
def classify(self, event: ChangeEvent) -> ClassifyOutcome:
    package = str(event.raw.get("package") or event.provider_id)
```

### Proposed change
```python
def classify(self, event: ChangeEvent) -> ClassifyOutcome:
    package = str(event.raw.get("package") or event.provider_id)

    # Recover the actual npm/pypi package name from feed_key when
    # event.raw is empty (raw is not persisted to DB).
    if not event.raw.get("package"):
        if event.feed_key.startswith("ts_exports:"):
            package = event.feed_key.removeprefix("ts_exports:")
        elif event.feed_key.startswith("openapi:"):
            package = event.feed_key.removeprefix("openapi:").split(":", 1)[0]
```

### Impact
All 477 sentry METHOD_REMOVED records would have `package="@sentry/node"` instead of "sentry".
`build_upgrade_plan` filter at upgrade.py:137 (`relevant`) would then include these changes.

### Test cases
1. TS_EXPORTS_DIFF event with `raw={}`, `feed_key="ts_exports:@sentry/node"` → `package="@sentry/node"`
2. TS_EXPORTS_DIFF event with `raw={"package":"@sentry/node"}` → `package="@sentry/node"` (unchanged)
3. NPM_DIST_TAG event → existing recovery at lines 89-99 still works (unchanged)
4. Event with no recognized feed_key prefix → falls back to `provider_id` (unchanged)

---

## Fix 2: Allow METHOD_REMOVED in Upgrade Plan (T-18)

### Problem
`upgrade.py:140` unconditionally skips METHOD_REMOVED from upgrade migrations:
```python
if is_method_removal(change):
    continue
```
This means even if a DEPENDENCY_VERSION_BUMP exists, the upgrade plan has 0 migrations → `has_source_work=False` → manifest-only PR.

### Key insight
The upgrade plan already has `plan.removals` (line 158) which collects removal notices. But these
are informational only — they don't enter the fix pipeline.

METHOD_REMOVED with a skill-file-enriched `migration_guide` CAN be fixed by the LLM. The LLM
prompt at bedrock.py:159-168 includes `migration_guide` and `new_api`. If populated, the LLM
can generate correct fixes.

### File: `src/depfix/core/upgrade.py`
### Location: lines 140-141

### Current code
```python
if is_method_removal(change):
    continue
```

### Option A: Conditionally allow removals with replacement info
```python
if is_method_removal(change) and not change.new_api:
    continue
```

### Option B: Allow all removals (let downstream handle)
Remove lines 140-141 entirely. The `assess_scan_change` at line 152 already filters to
ACTIONABLE sites, and `_report_removal` handles the "no replacement" case.

### Recommendation: Option B
Removing the gate is simpler and more forward-compatible. The downstream code at
runner.py:991 and fix_service.py:201 provides the real policy. Removals that reach
`build_upgrade_plan` should be included as migrations so the upgrade PR includes
both the version bump AND the call-site fixes.

### Test cases
1. DEPENDENCY_VERSION_BUMP + METHOD_REMOVED with matching call sites → both in upgrade migrations
2. METHOD_REMOVED with no matching call sites → `assess_scan_change` returns NO_CALL_SITES → excluded
3. Existing non-removal change types → unchanged behavior

---

## Fix 3: Allow METHOD_REMOVED in Orchestrator (T-19, MOST COMPLEX)

### Problem
`runner.py:991-1000` short-circuits ALL METHOD_REMOVED to `_report_removal` (REPORT_ONLY):
```python
if is_method_removal(change):
    return self._report_removal(...)
```

### Key design decision
The original reason for REPORT_ONLY: a removed API with no known replacement can't be
automatically fixed. The LLM would get `new_api=""` and `migration_guide=""`, producing
bad guesses.

### Solution: Enrich BreakingChange with skill file content before the fix pipeline

The provider skill files (e.g., `src/depfix/providers/skills/provider_sentry.md`) contain
exact replacement mappings:
```
| Old API (v7) | New API (v8+) |
| `startTransaction()` | `startSpan()` / `startInactiveSpan()` |
| `captureException(err, { contexts })` | `captureException(err)` |
```

**Approach**: Before the METHOD_REMOVED check at runner.py:991, look up the provider's skill
file. If it contains a replacement for `change.old_api`, enrich the BreakingChange with
`new_api` and `migration_guide` from the skill file, then let it through to the fix pipeline.

### File: `src/depfix/orchestrator/runner.py`
### Location: lines 991-1000

### Proposed change

Add a new method `_enrich_removal_with_skill` and modify the METHOD_REMOVED gate:

```python
# At line ~991, replace the unconditional gate:
if is_method_removal(change):
    enriched = self._enrich_removal_with_skill(change)
    if enriched is None:
        # No replacement info available — report only
        return self._report_removal(
            session, outcome, change, scan_result,
            repo_full_name=repo_full_name,
            current_ref_sha=current_ref_sha,
            suppressed_call_sites=suppressed_call_sites,
        )
    change = enriched  # Use enriched change with new_api + migration_guide
```

The `_enrich_removal_with_skill` method:
```python
def _enrich_removal_with_skill(self, change: BreakingChange) -> BreakingChange | None:
    """Try to find replacement info for a removed API from the provider's skill file."""
    import re
    from pathlib import Path

    skills_dir = Path(__file__).resolve().parent.parent / "providers" / "skills"
    skill_path = skills_dir / f"provider_{change.provider_id}.md"
    if not skill_path.is_file():
        return None

    skill_content = skill_path.read_text(encoding="utf-8")

    # Extract the symbol name from old_api (e.g., "sentry.startTransaction" → "startTransaction")
    symbol = change.old_api.rsplit(".", 1)[-1] if "." in change.old_api else change.old_api

    # Look for the symbol in the skill file's migration tables or text
    if symbol not in skill_content:
        return None

    # The skill file content serves as the migration guide for the LLM
    return dataclasses.replace(
        change,
        migration_guide=f"Provider skill file for {change.provider_id}:\n\n{skill_content}",
    )
```

### Impact
- `startTransaction` → found in provider_sentry.md → enriched with migration_guide → enters fix pipeline
- Unknown removals (internal SDK symbols) → not in skill file → REPORT_ONLY (unchanged)
- This naturally filters the 477 sentry METHOD_REMOVED down to ~6-8 that have known replacements

### Test cases
1. METHOD_REMOVED with symbol in skill file → enriched, enters fix pipeline
2. METHOD_REMOVED with symbol NOT in skill file → REPORT_ONLY (unchanged)
3. METHOD_REMOVED for provider with no skill file → REPORT_ONLY (unchanged)
4. Non-METHOD_REMOVED change → bypasses this code entirely (unchanged)

---

## Fix 4: Allow METHOD_REMOVED in Fix Service (T-19)

### Problem
`fix_service.py:201-217` is a second gate that returns an empty result for METHOD_REMOVED.
Even if runner.py passes the change through, fix_service blocks it.

### File: `src/depfix/core/fix_service.py`
### Location: lines 201-217

### Current code
```python
if is_method_removal(change):
    result = FixPipelineResult(...)  # empty, 0 edits, 0 usages fixed
    return FixServiceResult(result, [], ...)
```

### Proposed change
Only bail when the change has no migration context:
```python
if is_method_removal(change) and not change.migration_guide:
    result = FixPipelineResult(...)  # empty
    return FixServiceResult(result, [], ...)
```

### Impact
METHOD_REMOVED changes enriched by Fix 3 (with `migration_guide` populated) will proceed
to the LLM fix pipeline. Unenriched removals still return the empty result.

### Test cases
1. METHOD_REMOVED with `migration_guide=""` → empty result (unchanged)
2. METHOD_REMOVED with `migration_guide="<skill content>"` → proceeds to fix pipeline
3. Non-METHOD_REMOVED → unchanged

---

## Fix 5: Drift Capture in Plan (T-19, OPTIONAL)

### Problem
`depfix plan` never calls `capture_repository_dependency_drift`. Without a prior `depfix scan`,
no DEPENDENCY_VERSION_BUMP record exists in the DB, so the upgrade plan can't find the drift change.

### Current architecture
- `depfix scan` → `cli.py:1275` → `capture_repository_dependency_drift`
- `depfix plan` → `cli.py:1908-2090` → does NOT capture drift

### Assessment
This may be intentional: `scan` detects drift, `plan` plans fixes from prior scan data.
The existing flow `scan → plan → apply` works IF scan is run first.

### Recommendation
Document that `depfix scan` must precede `depfix plan` in the pipeline. Alternatively, add
drift capture in the orchestrator's `_prescan_providers` at runner.py:~630, where the scan
result already contains installed dependency versions.

This is lower priority than Fixes 1-4 and can be a separate follow-up.

---

## Implementation Order

1. **Fix 1** (classifier.py package recovery) — prerequisite for everything else. Without correct
   package names, build_upgrade_plan excludes all METHOD_REMOVED.
2. **Fix 2** (upgrade.py gate removal) — allows METHOD_REMOVED into upgrade migrations.
3. **Fix 4** (fix_service.py conditional gate) — allows enriched METHOD_REMOVED through fix pipeline.
4. **Fix 3** (runner.py skill enrichment) — the main logic that enriches removals with skill content.
   This is last because it depends on the downstream gates (Fixes 2+4) being open.

## Files Changed

| File | Lines | Change |
|---|---|---|
| `src/depfix/classify/classifier.py` | 39-40 | Add ts_exports feed_key recovery |
| `src/depfix/core/upgrade.py` | 140-141 | Remove METHOD_REMOVED gate |
| `src/depfix/core/fix_service.py` | 201-217 | Conditional gate (check migration_guide) |
| `src/depfix/orchestrator/runner.py` | 991-1000 | Skill enrichment + conditional gate |

## Expected End State

After all 4 fixes:
```
bedilk/depfix-test-sentry-v6-app:
  - depfix scan → 31 actionable call sites, @sentry/node@10.75.3
  - depfix plan →
    - DEPENDENCY_VERSION_BUMP: @sentry/node@10.75.3 → 11.6.0
    - METHOD_REMOVED: sentry.startTransaction → enriched with skill file → LLM fix
    - METHOD_REMOVED: sentry.captureException → enriched with skill file → LLM fix
    - Upgrade PR: version bump + source code migrations + removal notices
  - depfix apply → PR opened on GitHub with:
    - package.json: @sentry/node@10.75.3 → 11.6.0
    - src/performance.js: startTransaction → startSpan
    - src/performance.js: captureException context fix
```

## Verification

1. `make test` passes (no existing tests broken)
2. New unit tests for package recovery, upgrade gate, fix_service gate, skill enrichment
3. Integration test: `depfix scan --path <sentry-test-repo> && depfix plan` produces non-zero PRs
4. LLM fix output includes correct migration (startTransaction → startSpan)
