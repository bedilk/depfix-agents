# T-18 + T-19 Implementation Spec: Fix Pipeline for METHOD_REMOVED Changes

> **Code baseline:** `dependency_check` branch `main` at commit `722c263` (2026-10-12).
> All line numbers verified against this commit. `repo_exports.py` does NOT exist on main.

## Problem Statement

`depfix plan` produces 0 fix PRs for API removals because METHOD_REMOVED changes are
universally blocked at three independent checkpoints. T-17 identified root causes;
this spec maps those to exact code changes in `dependency_check/src/`.

## Current State (verified 2026-10-12)

### Fix 1: Package Recovery — ALREADY DONE ✓

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

### Three Remaining Blocks

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

## Fix 2: Allow METHOD_REMOVED with Replacement Info in Upgrade Plan (T-18)

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

1. **Prerequisite**: Add migration table to `provider_sentry.md` (needed for test case)
2. **Fix 2** (upgrade.py:140) — conditional gate on `new_api`. Smallest change, testable alone.
3. **Fix 3** (runner.py:894) — skill enrichment method + conditional gate. The core logic.
4. **Fix 4** (fix_service.py:201) — conditional gate on `migration_guide`. Enables the fix pipeline.

Fixes 2-4 are independent in code but must all be present for the pipeline to work end-to-end.
Order above is recommended for reviewability (each commit adds one gate change).

## Files Changed

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
T-18/T-19 do NOT depend on repo_exports.py — the ts_exports source already
produces METHOD_REMOVED BreakingChanges from feed polling. repo_exports.py
adds a second path (scan-time detection) that can be wired up separately.
