# Cross-Repo Migration Gap

**Date:** 2026-10-10 (last verified: 2026-10-10, re-verified: 2026-10-10)
**Author:** researcher

## Summary

The migration gap documented in the initial round 30 analysis has been **substantially resolved**.
Most work from depfix-agents has been migrated to dependency_check. Only one item remains open.

## Current Gap Status (re-verified 2026-10-10)

| Item | Round-30 Status | Current Status |
|---|---|---|
| providers.yaml (40 providers) | 15 MISSING | **RESOLVED** — 40 providers present |
| Provider skill files (43 files) | 32 MISSING | **RESOLVED** — 43 files present |
| sentry_v8_callsites.yaml (T-4) | MISSING | **RESOLVED** — present |
| ruby_callsites.yaml (T-5) | MISSING | **RESOLVED** — present |
| repo_exports.py (T-15 module) | MISSING | **RESOLVED** — present |
| test_repo_aware_exports.py (T-15 tests) | MISSING | **RESOLVED** — present |
| test_ecosystems_ruby_runtime.py | MISSING | **RESOLVED** — present |
| tests/fixtures/sentry_v7_project/ | MISSING | **RESOLVED** — present |
| tests/fixtures/ruby_*_project/ (4 dirs) | MISSING | **RESOLVED** — present |
| runner.py `_augment_with_repo_exports` | MISSING | **OPEN — still missing** |

## Remaining Gap: T-15 Orchestrator Integration

`repo_exports.py` is present in dependency_check but is never called. The orchestrator
integration (`_augment_with_repo_exports` method and its call site) was accepted in
depfix-agents but never migrated.

### What needs to be added to dependency_check's runner.py

**Step 1 — Add method `_augment_with_repo_exports`** (after `_prescan_providers`, before `_match_filter_and_cap`):

Exact source: `depfix-agents/src/depfix/orchestrator/runner.py` lines 776–866.
Add this method verbatim to `dependency_check/src/depfix/orchestrator/runner.py` in the same relative position.

**Step 2 — Add the call in `_run_repo_body`**:

In `dependency_check/src/depfix/orchestrator/runner.py`, after `_prescan_providers(...)` returns
(around line 392, after the `if` block that calls `_prescan_providers`), insert:

```python
        # Augment with repo-version-aware synthetic changes from TypeScript
        # export diffs. These cover removals that span more than one major
        # version and are therefore invisible to the feed-level ts_exports diff.
        ordered = self._augment_with_repo_exports(ordered, repo_full_name, current_ref_sha)
```

The call goes BEFORE the existing "Relevance filter" comment and `_match_filter_and_cap` call.

### Exact insertion point in dependency_check runner.py (lines 388–402)

```python
                    current_ref_sha=current_ref_sha,
                    provider_ids=list(needs_scan_providers),
                    repo_config=repo_config,
                )

        # ← INSERT 4-line augment block here

        # Relevance filter: keep only changes whose old_api matches a call
        ordered, no_call_site_changes = self._match_filter_and_cap(
```

### Verification command

```bash
grep "_augment_with_repo_exports" /Users/bedil_karimov/Documents/dependency_check/src/depfix/orchestrator/runner.py
# → should return 2 lines after the fix (the call + the def)
```

## Impact of Remaining Gap

T-15 feature goal: when a repo's lockfile resolves an old npm version, synthesize
BreakingChange records for exports removed between that installed version and latest.
Without `_augment_with_repo_exports` being called, `repo_exports.py` is dead code and
`bedilk/depfix-test-sentry-v6-app` still won't show `startTransaction` as actionable.

## Commands to Re-verify

```bash
# Providers
grep -c "^  name:" /Users/bedil_karimov/Documents/dependency_check/providers.yaml
# → 40

# Skill files
ls /Users/bedil_karimov/Documents/dependency_check/src/depfix/providers/skills/ | wc -l
# → 43

# T-15 integration (still missing)
grep "_augment_with_repo_exports" /Users/bedil_karimov/Documents/dependency_check/src/depfix/orchestrator/runner.py
# → (empty)

# Eval corpus
ls /Users/bedil_karimov/Documents/dependency_check/src/depfix/evals/corpus/
# → includes ruby_callsites.yaml and sentry_v8_callsites.yaml
```
