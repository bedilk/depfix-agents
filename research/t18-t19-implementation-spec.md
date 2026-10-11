# T-18 + T-19 Implementation Spec: Fix Pipeline for METHOD_REMOVED Changes

> **Code baseline:** `dependency_check` branch `main` at commit `722c263` (2026-10-12).
> All line numbers verified against this commit. `repo_exports.py` does NOT exist on main.

## Problem Statement

`depfix plan` produces 0 fix PRs for API removals due to TWO independent categories of issues:

**Category A — No BreakingChange records for multi-major jumps (T-18)**:
The ts_exports feed compares adjacent major versions (v10→v11) but the test repo has
APIs removed many majors ago (startTransaction removed in v8). No BreakingChange record
exists in the DB for these old removals.

**Category B — METHOD_REMOVED blocked at three gates (T-19)**:
Even when BreakingChange records exist (from T-18), three independent gates prevent
METHOD_REMOVED from generating fix PRs.

Both categories must be fixed for the pipeline to work end-to-end.

## Current State (verified 2026-10-12)

### Fix 0: Package Recovery — ALREADY DONE ✓

`classifier.py:27-44` already has `_package_from_feed_key()` which handles `ts_exports:`,
`npm:`, `pypi:`, `rubygems:` prefixes. Called at line 67:
```python
package = str(
    event.raw.get("package")
    or _package_from_feed_key(event.feed_key)
    or event.provider_id
)
```
No work needed here.

### Category A: BreakingChange Generation Gap (T-18)

```
ts_exports poll: compares v10.76.1 → v11.5.0 exports
  → 477 EXPORT_REMOVED (symbols removed between v10 and v11)
  → startTransaction NOT in these 477 (removed in v8, absent from both v10 AND v11)
  → No BreakingChange exists for startTransaction
  → depfix plan finds call sites but has nothing to plan against
```

**Solution**: `repo_exports.py` + runner.py wiring already exists on branch
`fix/migrate-agent-changes` (commit 22fba34). Compares the repo's INSTALLED version
exports against LATEST and emits synthetic METHOD_REMOVED for removed symbols.

### Category B: Three Remaining Gates (T-19)

```
scan → classify → BreakingChange(METHOD_REMOVED, package="@sentry/node", new_api="") → DB
                                                         ↑ correct now      ↑ still empty
plan → load changes → _process_change_body
       │                 ├─ runner.py:894 is_method_removal → REPORT_ONLY     ← BLOCK 1
       │                 └─ build_upgrade_plan
       │                      └─ upgrade.py:140 is_method_removal → skip     ← BLOCK 2
       └─ run_fix_for_change
              └─ fix_service.py:201 is_method_removal → empty result         ← BLOCK 3
```

---

## Fix 1: Migrate repo_exports.py to main (T-18, CRITICAL)

### Problem
The ts_exports feed only compares adjacent major versions (v10→v11). For the test repo
`bedilk/depfix-test-sentry-v6-app` with `@sentry/node@10.75.3`:
- `startTransaction` was removed in v8
- It's absent from BOTH v10 and v11 exports
- The v10→v11 diff doesn't show it as removed
- No BreakingChange record exists in the DB

### Solution: Already built, needs migration
Branch `fix/migrate-agent-changes` (commit 22fba34) has:

| File | Lines | Status on main |
|---|---|---|
| `src/depfix/sources/repo_exports.py` | 224 | MISSING |
| `src/depfix/orchestrator/runner.py` additions | +97 | MISSING |
| `tests/unit/test_repo_aware_exports.py` | 437 | MISSING |

### What repo_exports.py does
`synthetic_changes_for_scan(scan_result, provider_id, npm_packages, http, npm)`:
1. Gets the repo's installed version (from scan_result.dependencies)
2. Downloads installed version's exports via `_exports_for(version)` from ts_exports.py
3. Downloads latest version's exports
4. **Sub-case A**: `installed_exports - latest_exports` → symbols removed since installed
5. **Sub-case B**: For each call site using a symbol NOT in installed_exports →
   "ghost" API (removed before the installed version, like startTransaction)
6. Returns `list[BreakingChange]` with `kind=METHOD_REMOVED`

### runner.py wiring (from branch diff)
**Call site** — add after `_prescan_providers()` at line ~392:
```python
# Augment with repo-version-aware synthetic changes from TypeScript
# export diffs. These cover removals that span more than one major
# version and are therefore invisible to the feed-level ts_exports diff.
ordered = self._augment_with_repo_exports(ordered, repo_full_name, current_ref_sha)
```

**Method** — add `_augment_with_repo_exports` (90 lines) after `_prescan_providers` method
at ~line 773. The full code is on branch `fix/migrate-agent-changes` — can be cherry-picked
or copied verbatim.

### Implementation approach
```bash
cd dependency_check
git checkout fix/t18-multi-major-removals  # already exists, 0 commits
# Cherry-pick the relevant files from fix/migrate-agent-changes:
git checkout fix/migrate-agent-changes -- src/depfix/sources/repo_exports.py
git checkout fix/migrate-agent-changes -- tests/unit/test_repo_aware_exports.py
# Then manually port the runner.py additions (can't cherry-pick a partial file)
```

### Test cases (already written in test_repo_aware_exports.py)
24 tests covering:
- Sub-case A: symbol removed between installed and latest
- Sub-case B: call site uses symbol absent from installed exports (ghost API)
- Edge cases: no npm packages, no scan result, httpx failures, empty exports
- All 24 pass on the branch

---

## Fix 2: Allow METHOD_REMOVED with Replacement Info in Upgrade Plan (T-19)

### File: `src/depfix/core/upgrade.py`
### Location: lines 140-141

### Current code (upgrade.py:140-141)
```python
if is_method_removal(change):
    continue
```

### Proposed change
Per reviewer's T-17 guidance: gate on replacement info being available, not unconditional skip.
```python
if is_method_removal(change) and not change.new_api:
    continue
```

### Rationale
The reviewer explicitly said "gate METHOD_REMOVED entry on replacement info being available
instead of removing the upgrade.py:140 gate outright" (T-17 receipt). This is the minimal
change: only removals with a known replacement enter the upgrade plan.

### Test cases
1. METHOD_REMOVED with `new_api=""` → skipped (unchanged behavior)
2. METHOD_REMOVED with `new_api="startSpan"` → included in upgrade migrations
3. DEPENDENCY_VERSION_BUMP → unchanged (line 138-139 handles it)
4. METHOD_RENAMED → unchanged (never hits this gate)

---

## Fix 3: Allow Enriched METHOD_REMOVED in Orchestrator (T-19)

### File: `src/depfix/orchestrator/runner.py`
### Location: lines 894-903

### Current code (runner.py:894-903)
```python
if is_method_removal(change):
    return self._report_removal(
        session,
        outcome,
        change,
        scan_result,
        repo_full_name=repo_full_name,
        current_ref_sha=current_ref_sha,
        suppressed_call_sites=suppressed_call_sites,
    )
```

### Solution: Enrich METHOD_REMOVED from provider skill files

The provider skill files already contain migration info for many providers.
Verified coverage (2026-10-12):
- discord: 16 migration arrows (→) — `MessageEmbed → EmbedBuilder`, etc.
- auth0: 15 arrows — `AuthenticationClient` removal, method renames
- twilio: 14 arrows — `IpMessagingGrant` removal, SSML renames
- supabase: 13 arrows — `signUp → signUp()`, auth method renames
- aws_s3: 11 arrows — `AWS.S3 → S3Client`, command pattern
- amplitude: 10 arrows — `logEvent → track`, `getInstance` removal
- firebase: 9 arrows — modular API migration
- bugsnag: 9 arrows — `bugsnag(opts) → Bugsnag.start(opts)`
- **sentry: 0 arrows — NEEDS MIGRATION TABLE ADDED** (see prerequisite below)

### Prerequisite: Add migration table to sentry skill file

The sentry skill file (`src/depfix/providers/skills/provider_sentry.md`) currently has
call-site patterns only. Add a migration section:

```markdown
## v7 → v8 key breaking changes
- `Sentry.startTransaction(ctx)` → `Sentry.startSpan({ name, op }, callback)`
- `Sentry.getCurrentHub()` → `Sentry.getCurrentScope()`
- `hub.configureScope(cb)` → `Sentry.getCurrentScope()` (direct access)
- `new Sentry.Integrations.Http(opts)` → `Sentry.httpIntegration(opts)`
- `new Sentry.Integrations.Express(opts)` → removed, auto-instrumented
- `transaction.finish()` → span auto-finishes when callback returns
- `span.setHttpStatus(code)` → `span.setStatus({ code, message })`
```

Source: Sentry v8 migration guide + eval corpus `sentry_v8_callsites.yaml`.

### Proposed code change (runner.py:894)

Add a method `_enrich_removal_from_skill` and modify the gate:

```python
# Replace lines 894-903
if is_method_removal(change):
    enriched = self._enrich_removal_from_skill(change)
    if enriched is None:
        return self._report_removal(
            session,
            outcome,
            change,
            scan_result,
            repo_full_name=repo_full_name,
            current_ref_sha=current_ref_sha,
            suppressed_call_sites=suppressed_call_sites,
        )
    change = enriched
```

New method (add after `_report_removal` at ~line 1369):

```python
def _enrich_removal_from_skill(self, change: BreakingChange) -> BreakingChange | None:
    """Enrich a METHOD_REMOVED change with migration info from the provider skill file.

    Returns an enriched copy if the removed symbol appears in the skill file's
    migration tables, or None if no replacement info is available.
    """
    import dataclasses
    import re
    from pathlib import Path

    skills_dir = Path(__file__).resolve().parent.parent / "providers" / "skills"
    skill_path = skills_dir / f"provider_{change.provider_id}.md"
    if not skill_path.is_file():
        return None

    content = skill_path.read_text(encoding="utf-8")

    # Extract the bare symbol name from old_api
    # e.g. "sentry.startTransaction" → "startTransaction"
    symbol = change.old_api.rsplit(".", 1)[-1] if "." in change.old_api else change.old_api
    if not symbol or symbol not in content:
        return None

    # Look for "old_symbol" → "new_symbol" pattern in the skill file
    # Handles: `old()` → `new()`, `old` → `new`, old → new
    pattern = rf"`?{re.escape(symbol)}\b[^`]*`?\s*→\s*`?([^`\n]+)`?"
    match = re.search(pattern, content)
    new_api = match.group(1).strip().rstrip("()") if match else ""

    return dataclasses.replace(
        change,
        new_api=new_api or f"(see skill file for {change.provider_id})",
        migration_guide=(
            f"Provider migration guide ({change.provider_id}):\n\n{content}"
        ),
    )
```

### How it works

1. Load skill file for the change's provider
2. Check if the removed symbol name appears in the file
3. Extract replacement API from `→` patterns (e.g., `startTransaction → startSpan`)
4. Set `new_api` to the extracted replacement (or a placeholder)
5. Set `migration_guide` to the full skill file content — the LLM fixer at
   bedrock.py:159-168 renders this into the prompt

### Impact on bedrock.py fixer

The LLM prompt (bedrock.py:159-191) already uses:
- Line 164: `- Old API: {breaking_change.old_api}` — e.g. "sentry.startTransaction"
- Line 165: `- New API: {breaking_change.new_api}` — e.g. "startSpan"
- Line 168: `{breaking_change.migration_guide}` — full skill file with migration tables

The confidence check (bedrock.py:214) uses `new_api.split("(")[0]` to verify the
replacement appears in the fixed code. With `new_api="startSpan"`, this check works correctly.

### Test cases
1. METHOD_REMOVED `sentry.startTransaction` with skill file containing `startTransaction → startSpan`
   → enriched with `new_api="startSpan"`, enters fix pipeline
2. METHOD_REMOVED for symbol NOT in skill file → None → REPORT_ONLY
3. METHOD_REMOVED for provider with no skill file → None → REPORT_ONLY
4. Non-METHOD_REMOVED → bypasses this code entirely

---

## Fix 4: Allow Enriched METHOD_REMOVED in Fix Service (T-19)

### File: `src/depfix/core/fix_service.py`
### Location: lines 201-217

### Current code (fix_service.py:201-217)
```python
if is_method_removal(change):
    result = FixPipelineResult(
        repo_full_name=scan_result.repo_full_name,
        breaking_change=change,
        files_scanned=scan_result.files_scanned,
        files_affected=0,
        edits=(),
        total_usages_fixed=0,
        total_cost=0.0,
        total_tokens=0,
        duration_ms=0,
        codemod_notes=(
            f"{change.old_api} was removed upstream with no replacement; "
            "reported only, no fix generated",
        ),
    )
    return FixServiceResult(result, [], repo_config.verify and settings.verify_enabled)
```

### Proposed change
```python
if is_method_removal(change) and not change.migration_guide:
    # ... same empty result ...
```

### Rationale
Gate on `migration_guide` (not `new_api`) because that's what the LLM fixer at
bedrock.py:168 actually uses. An enriched change has `migration_guide` set to the
skill file content; an unenriched change has `migration_guide=""`.

### Test cases
1. METHOD_REMOVED with `migration_guide=""` → empty result (unchanged)
2. METHOD_REMOVED with `migration_guide="<skill content>"` → proceeds to LLM fix pipeline
3. Non-METHOD_REMOVED → unchanged (line 182 handles DEPENDENCY_VERSION_BUMP first)

---

## Implementation Order

### T-18 (BreakingChange generation)
1. **Fix 1**: Migrate repo_exports.py + runner.py wiring + tests from `fix/migrate-agent-changes`
2. Verify: `make test` passes, new unit tests cover multi-major case

### T-19 (Fix pipeline gates)
3. **Prerequisite**: Add migration table to `provider_sentry.md` (needed for test case)
4. **Fix 2** (upgrade.py:140) — conditional gate on `new_api`
5. **Fix 3** (runner.py:894) — skill enrichment method + conditional gate (core logic)
6. **Fix 4** (fix_service.py:201) — conditional gate on `migration_guide`
7. Verify: `make test` passes, integration test produces non-zero migrations

### End-to-end
8. Run `depfix scan --path <sentry-test-repo>` → verify synthetic BreakingChanges created
9. Run `depfix plan` → verify non-zero fix plan with startTransaction migration
10. Run `depfix apply` → verify PR with correct code changes

## Files Changed

### T-18 files (migrate from fix/migrate-agent-changes)
| File | Lines | Change |
|---|---|---|
| `src/depfix/sources/repo_exports.py` | 224 (new) | Installed-vs-latest export diff |
| `src/depfix/orchestrator/runner.py` | 392 + 773 | `_augment_with_repo_exports` call + method |
| `tests/unit/test_repo_aware_exports.py` | 437 (new) | 24 test cases |

### T-19 files (gate changes)
| File | Lines | Change |
|---|---|---|
| `src/depfix/providers/skills/provider_sentry.md` | append | Add v7→v8 migration table |
| `src/depfix/core/upgrade.py` | 140-141 | Conditional gate: `and not change.new_api` |
| `src/depfix/orchestrator/runner.py` | 894-903 + ~1370 | Enrichment method + conditional gate |
| `src/depfix/core/fix_service.py` | 201 | Conditional gate: `and not change.migration_guide` |

## Expected End State

```
bedilk/depfix-test-sentry-v6-app:
  - depfix scan → 31 actionable call sites, @sentry/node@10.75.3
  - depfix plan →
    - DEPENDENCY_VERSION_BUMP: @sentry/node 10.75.3 → latest
    - METHOD_REMOVED: sentry.startTransaction → enriched → new_api="startSpan" → LLM fix
    - Upgrade PR: version bump + source code migration
  - depfix apply → PR opened on GitHub with:
    - package.json: @sentry/node version bump
    - src/perf.js: startTransaction → startSpan migration
```

## Verification

1. `make test` passes (no existing tests broken)
2. New unit tests: upgrade gate, enrichment method, fix_service gate
3. Integration: `depfix scan --path <sentry-test-repo>` → `depfix plan` produces non-zero migrations
4. LLM fix output: startTransaction → startSpan with correct span API usage

## Notes on repo_exports.py

`repo_exports.py` does NOT exist on dependency_check `main`. The T-15 code
(installed→latest export diff) is only on `fix/migrate-agent-changes` branch.

**CRITICAL**: T-18 DEPENDS on repo_exports.py. The ts_exports feed only compares
adjacent major versions (v10→v11), so it CANNOT detect symbols removed in earlier
majors (startTransaction removed in v8). repo_exports.py compares the repo's
INSTALLED version exports against LATEST, catching all cross-major removals.
Without Fix 1, no BreakingChange for startTransaction exists, and the test case fails.

See `git diff main..fix/migrate-agent-changes -- src/depfix/sources/repo_exports.py`
for the exact code to migrate.
