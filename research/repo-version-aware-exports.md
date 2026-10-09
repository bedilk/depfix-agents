# T-15 Research: Repo-Version-Aware ts_exports Diff

**Task**: Detect old-API removals across multiple major SDK versions using the
repo's lockfile-resolved version as the baseline, not just the feed's
previous-major comparison.

**Evidence date**: 2026-10-09  
**Researcher**: researcher (claude-sonnet-4-6-1m)

---

## 1. Problem statement (verified)

`depfix scan` correctly finds 31 call sites for `startTransaction`, `configureScope`,
etc. in `bedilk/depfix-test-sentry-v6-app`. `depfix plan` produces 0 PRs. The pipeline
is broken end-to-end for any repo that is **more than one major version behind the
latest SDK**.

### Why plan produces nothing: traced to 4 exact locations

| # | File | Line | Issue |
|---|------|------|-------|
| 1 | `src/depfix/sources/ts_exports.py` | 171–183 | `_previous_major_release()` finds max(versions where major < current_major). For latest=11, this is max(v10.x). The v8 removal of `startTransaction` is never diffed. |
| 2 | `src/depfix/scanners/matching.py` | 43–106 | `assess_scan_change()` requires a pre-existing `BreakingChange` record. With no record for `startTransaction` → returns `NO_CALL_SITES`. |
| 3 | `src/depfix/catalog/learned.py` | 105–145 | `_detected_entry()`: `_match_symbol(symbol, changes, ...)` returns `None` when no classified change covers the symbol → `status: non_actionable`. |
| 4 | `src/depfix/catalog/detections.py` | 135–173 | `build_anchor_detection()` exists but only for agent-discovered anchors, not deterministic scanner output. |

### Concrete evidence from task notes (2026-10-08 manual run)
- `bedilk/depfix-test-sentry-v6-app`: `@sentry/node@10.75.3` in lockfile. Feed compared
  `10.76.1→11.5.0`. `startTransaction` was removed in v8 — already gone from both sides
  of the comparison window. 31 call sites, 0 actionable.
- `bedilk/seed-openai-v3-to-v4`: `createChatCompletion` removed in v4. Feed compared
  `7.30.0→7.30.1`. 1 call site, 0 actionable. (Blocked additionally by `file:./vendor/openai`
  lockfile entry — unresolvable, documented limitation.)

---

## 2. Key existing capability (the escape hatch)

`TsExportsSource._exports_for(version: str)` at **ts_exports.py:185–197** already fetches
exported names from the tarball for **any** npm version:

```python
def _exports_for(self, version: str) -> set[str] | None:
    tarball_url = self._tarball_url(version)
    ...
    return self._names_in_tarball(response.content)
```

`_tarball_url(version)` at ts_exports.py:198–202 constructs the URL deterministically:
```python
def _tarball_url(self, version: str) -> str | None:
    scope_safe = self.package.replace("/", "%2f")
    base = self._npm.base_url
    short = self.package.rsplit("/", 1)[-1]
    return f"{base}/{scope_safe}/-/{short}-{version}.tgz"
```

`_names_in_tarball(blob: bytes)` at ts_exports.py:205–218 is a `@staticmethod` —
callable without a `TsExportsSource` instance.

The piece we need already exists. We just need to call it with the **repo's installed
version** rather than the feed's prior-major version.

---

## 3. Data flow: where the installed version is available

### 3a. After `_scan_checkout_deterministic` (repo.py:475)

At repo.py:527–540 (JS/TS path), `scan_manifests` returns `manifest_scan.matches`, each
with a `resolved_version` (from lockfile). These become `DeclaredDependency` objects in
`result.dependencies`.

For `bedilk/depfix-test-sentry-v6-app`:
```
result.dependencies = [
    DeclaredDependency(package="@sentry/node", resolved_version="10.75.3", ...)
]
```

The resolved version is already in the `RepoScanResult` that comes out of scan.

### 3b. `Orchestrator._prescan_providers` (runner.py:675)

After `scan_checkout(...)` returns a `RepoScanResult`, the orchestrator stores it in
`self._scan_cache[(repo_full_name, provider_id, commit_sha)]`. The `dependencies` field
is present here.

### 3c. `Orchestrator._run_repo_body` change pipeline (runner.py:354)

The `ordered` list of `BreakingChange` objects is built at line 354, pre-scanned at
line 379, then filtered at line 397:

```python
ordered = sorted(changes, key=...)
needs_scan_providers = {c.provider_id for c in ordered ...}
if needs_scan_providers:
    self._prescan_providers(...)                    # ← scan_cache populated here
ordered, no_call_site_changes = self._match_filter_and_cap(ordered, ...)  # ← filter here
```

**The synthetic changes must be appended to `ordered` AFTER `_prescan_providers`
(when scan_cache is populated) and BEFORE `_match_filter_and_cap` (where they are
filtered).**

---

## 4. Recommended implementation

### 4a. New module: `src/depfix/scanners/version_exports.py`

```python
"""Synthesize BreakingChange records from repo-lockfile-vs-latest export diff.

Called from the orchestrator after pre-scan so the standard plan/apply pipeline
can act on symbols removed across multiple major SDK versions.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from depfix.core.models import BreakingChange, ChangeKind, ClassificationSource
from depfix.registry.client import NpmRegistryClient, RegistryError
from depfix.sources.semver import parse_semver
from depfix.sources.ts_exports import TsExportsSource

if TYPE_CHECKING:
    from depfix.scanners.models import RepoScanResult

logger = logging.getLogger(__name__)


def synthesize_version_aware_changes(
    result: "RepoScanResult",
    *,
    provider_id: str,
    npm_packages: list[str],
    npm: NpmRegistryClient,
    http: httpx.Client,
) -> list[BreakingChange]:
    """Compare installed-version exports vs latest-version exports for every
    resolved npm package in result.dependencies.

    For each symbol that (a) exists in the installed version, (b) is absent from
    the latest version, and (c) appears in an actionable call site, produce a
    synthetic BreakingChange(kind=METHOD_REMOVED) so plan can act on it.

    Returns an empty list on any network failure — caller continues unaffected.
    """
    if not npm_packages or not result.dependencies:
        return []

    resolved: dict[str, str] = {}
    for dep in result.dependencies:
        if dep.package in npm_packages and dep.resolved_version:
            parsed = parse_semver(dep.resolved_version)
            if parsed is not None:
                resolved[dep.package] = dep.resolved_version

    if not resolved:
        return []

    observed_suffixes: set[str] = set()
    for site in result.actionable_sites:
        sym = site.symbol
        # Symbols are "provider_id.method" or "provider_id.Namespace.method"
        if sym.startswith(f"{provider_id}."):
            observed_suffixes.add(sym[len(provider_id) + 1:])

    if not observed_suffixes:
        return []

    changes: list[BreakingChange] = []

    for package, installed_version in resolved.items():
        try:
            metadata = npm.get_package_metadata(package)
        except RegistryError as exc:
            logger.debug("version_exports: registry error for %s: %s", package, exc)
            continue

        latest = metadata.dist_tags.get("latest")
        if not latest:
            continue

        installed_parsed = parse_semver(installed_version)
        latest_parsed = parse_semver(latest)
        if installed_parsed is None or latest_parsed is None:
            continue
        if installed_parsed >= latest_parsed:
            continue  # already up to date

        # Use TsExportsSource's tarball-based export extraction
        source = TsExportsSource(provider_id, {"package": package}, http, npm)
        installed_exports = source._exports_for(installed_version)
        latest_exports = source._exports_for(latest)
        if installed_exports is None or latest_exports is None:
            logger.debug(
                "version_exports: could not fetch exports for %s %s or %s",
                package, installed_version, latest,
            )
            continue

        removed = installed_exports - latest_exports

        for name in sorted(removed):
            if name not in observed_suffixes:
                continue
            try:
                change = BreakingChange(
                    package=package,
                    old_version=installed_version,
                    new_version=latest,
                    old_api=f"{provider_id}.{name}",
                    new_api="",
                    description=(
                        f"{package} export `{name}` present in {installed_version} "
                        f"but absent from {latest} (repo-version-aware diff)"
                    ),
                    migration_guide="",
                    kind=ChangeKind.METHOD_REMOVED,
                    source=ClassificationSource.SPEC_DIFF,
                    provider_id=provider_id,
                    confidence=1.0,
                )
                changes.append(change)
                logger.info(
                    "version_exports: %s.%s removed (%s→%s) — synthetic change for %s",
                    provider_id, name, installed_version, latest,
                    result.repo_full_name or "local",
                )
            except (ValueError, TypeError) as exc:
                logger.debug("version_exports: skipping %s.%s: %s", provider_id, name, exc)

    return changes
```

### 4b. Changes to `src/depfix/orchestrator/runner.py`

Add a helper method to `Orchestrator`:

```python
def _synthetic_version_changes(
    self,
    scan_result: RepoScanResult,
    provider_id: str,
) -> list[BreakingChange]:
    """Synthesize repo-version-aware export diff changes. Best-effort."""
    from depfix.scanners.version_exports import synthesize_version_aware_changes
    from depfix.sources.factory import SourceDeps

    provider = self._providers.get(provider_id)
    if provider is None:
        return []
    npm_packages = [sdk.name for sdk in provider.sdk_packages if sdk.ecosystem == "npm"]
    if not npm_packages:
        return []
    try:
        with SourceDeps.from_settings() as deps:
            return synthesize_version_aware_changes(
                scan_result,
                provider_id=provider_id,
                npm_packages=npm_packages,
                npm=deps.npm,
                http=deps.http,
            )
    except Exception:
        logger.debug("synthetic version changes failed for %s", provider_id, exc_info=True)
        return []
```

Inject in `_run_repo_body` after `_prescan_providers` and before `_match_filter_and_cap`:

```python
# After: if needs_scan_providers: self._prescan_providers(...)
# Before: ordered, no_call_site_changes = self._match_filter_and_cap(...)

if needs_scan_providers and self._settings.repo_version_aware_exports:
    synthetic: list[BreakingChange] = []
    for provider_id in needs_scan_providers:
        cache_key = (repo_full_name, provider_id, current_ref_sha)
        cached = self._scan_cache.get(cache_key)
        if cached is not None:
            synthetic.extend(self._synthetic_version_changes(cached, provider_id))
    if synthetic:
        ordered = sorted([*ordered, *synthetic], key=lambda c: (
            0 if c.kind is ChangeKind.DEPENDENCY_VERSION_BUMP else 1,
        ))
```

### 4c. New Settings key

Add to `src/depfix/config.py`:

```python
repo_version_aware_exports: bool = True
```

(Default `True` because it is deterministic, low-cost, and high-value. Set `False` to
disable in environments with no npm registry access.)

### 4d. Expose `_exports_for` logic as a public API (optional cleanup)

`TsExportsSource._exports_for` and `_tarball_url` are private. The new function
instantiates a `TsExportsSource` to call them, which works but is slightly awkward.
The implementer may choose to extract `exports_for_package_version(package, version,
*, npm, http) -> set[str] | None` as a public module-level function in
`ts_exports.py`. Not required for correctness.

---

## 5. How assess_scan_change handles the synthetic changes

For a synthetic `BreakingChange(old_api="sentry.startTransaction", kind=METHOD_REMOVED)`:

1. `change_applies(result.dependencies, change)` at applicability.py:103:
   - `relevant = [dep for dep in deps if _same_package(dep.package, "@sentry/node")]`
   - `_decide_one(dep, change)` with `dep.resolved_version="10.75.3"` and
     `change.old_version="10.75.3"`, `change.new_version="11.6.0"`
   - `affects_version("10.75.3", "10.75.3", "11.6.0")` → `True`
   - Returns `Applicability.APPLIES` ✓

2. `symbols_for_change("sentry", change)` at repo.py:103:
   - `change.old_api = "sentry.startTransaction"` → already provider-qualified
   - `_qualify_symbol("sentry", "sentry.startTransaction", ...)` → `"sentry.startTransaction"` ✓

3. `_site_matches_exact(site, ("sentry.startTransaction",))` at matching.py:119:
   - Call site has `symbol="sentry.startTransaction"` → `True` ✓

4. Result: `ScanMatchStatus.ACTIONABLE` ✓

5. In orchestrator `_process_change_body`:
   - `is_method_removal(change)` → `True` (kind=METHOD_REMOVED)
   - Goes to `_report_removal()` → `AttemptStatus.REPORT_ONLY`
   - Surfaces in the scan report with the list of affected call sites ✓

The change becomes "actionable" (method removal notices appear in plan output). This
satisfies the acceptance criteria: sentry.startTransaction is no longer silently
NO_CALL_SITES — it appears as a documented removal.

---

## 6. Known limitations and boundaries

### 6a. REPORT_ONLY, not auto-fixable

`kind=METHOD_REMOVED` with `new_api=""` triggers the REPORT_ONLY path. The plan
notifies the developer that the symbol was removed but cannot auto-generate a fix
without knowing the replacement. This is correct behaviour:
- The ts_exports diff is structural (symbol gone) but lacks migration intent
- The replacement (if any) is only in the feed's classified `BreakingChange` records

**Enhancement path**: Before creating a synthetic `METHOD_REMOVED`, check the DB for
an existing `BreakingChange` with `provider_id=provider_id` and `old_api` matching
the removed symbol. If found, use that record (which may have `new_api` set) instead
of the synthetic one. This would produce a real fix for known migrations. However,
this is an optional improvement — the base task is to surface the removal, which
REPORT_ONLY achieves.

### 6b. `file:./vendor/openai` lockfile entries

`DeclaredDependency.resolved_version` is `None` when the lockfile records
`file:./vendor/openai`. The function checks `dep.resolved_version is not None` before
proceeding, so this is a hard skip. The `bedilk/seed-openai-v3-to-v4` repo is
unresolvable for this reason. Documented in task notes as a known limitation.

### 6c. Network cost

Fetching two tarballs per (package, installed_version) costs ~2 HTTP requests and
whatever the tarball sizes are (Sentry: ~1MB each). This runs per-repo-per-scan, not
per-change. Cost is bounded by `_MAX_TARBALL_BYTES = 30_000_000` at ts_exports.py:40.

The `synthesize_version_aware_changes` function creates a `TsExportsSource` instance
which shares the same `httpx.Client` from `SourceDeps`. The check `installed_parsed >=
latest_parsed` early-exits for up-to-date repos, so the cost is zero for maintained
codebases.

### 6d. Python/Ruby ecosystems

This implementation covers npm only (JS/TS repos). Python and Ruby ecosystems lack
`.d.ts` files. If Python/Ruby export diff is desired, a separate investigation into
PyPI `.pyi` stub diffs would be needed.

### 6e. Non-removal changes (renamed, param-changed)

Export diff only detects symbols that were **removed** entirely. Renamed methods
still appear in both versions' exports (old name disappeared, new name appeared),
but we don't synthesize `METHOD_RENAMED` changes here because we can't know the
new API from the export list alone. This is a fundamental limitation of the
structural approach — the feed-classified records are the right source for
rename detection.

---

## 7. Test cases for `tests/unit/test_repo_aware_exports.py`

The implementer should write these tests:

### 7.1 Core function: `synthesize_version_aware_changes`

```
TC-1: symbol present in installed, absent from latest, matched by call site
  → produces BreakingChange(kind=METHOD_REMOVED, source=SPEC_DIFF)

TC-2: symbol present in installed, absent from latest, NOT in call sites
  → produces nothing (observed_suffixes filter)

TC-3: symbol absent in installed (new in latest)
  → produces nothing (removed = installed - latest, "new" names are ignored)

TC-4: symbol present in both
  → produces nothing

TC-5: resolved_version == latest_version (up to date)
  → produces nothing (early exit on installed_parsed >= latest_parsed)

TC-6: resolved_version is None (file: lockfile entry)
  → produces nothing

TC-7: npm registry returns RegistryError
  → produces nothing, no exception raised

TC-8: _exports_for returns None for installed version
  → produces nothing

TC-9: multiple packages in npm_packages, only one has a resolved dependency
  → processes only the resolved one

TC-10: sentry scenario — @sentry/node 10.x installed, startTransaction in exports,
  absent from latest 11.x, call site exists
  → produces BreakingChange for sentry.startTransaction
```

### 7.2 assess_scan_change integration with synthetic change

```
TC-11: synthetic BreakingChange feeds into assess_scan_change with a matching call site
  → ScanMatchStatus.ACTIONABLE

TC-12: synthetic BreakingChange, call site exists, dep version matches old_version
  → change_applies returns APPLIES

TC-13: synthetic BreakingChange, dep resolved_version > change.new_version (impossible
  but defensive)
  → change_applies returns NOT_AFFECTED
```

### 7.3 Orchestrator integration (integration test, can be mocked)

```
TC-14: Orchestrator._run_repo_body with repo_version_aware_exports=True
  → synthetic changes appear in ordered before _match_filter_and_cap

TC-15: repo_version_aware_exports=False in settings
  → no synthetic changes generated
```

---

## 8. Files to create or modify (implementer checklist)

### Create
- `src/depfix/scanners/version_exports.py` — new module (full code in §4a)
- `tests/unit/test_repo_aware_exports.py` — test cases (§7)

### Modify
- `src/depfix/config.py` — add `repo_version_aware_exports: bool = True`
- `src/depfix/orchestrator/runner.py`:
  - Add `_synthetic_version_changes()` method
  - In `_run_repo_body`: inject synthetic changes after `_prescan_providers`
- (optional) `src/depfix/sources/ts_exports.py`: expose `_exports_for` logic
  as a public module-level function if the direct-instantiation approach feels hacky

### Do NOT modify
- `src/depfix/sources/ts_exports.py:poll()` — keep feed poll stateless
- `src/depfix/scanners/models.py:RepoScanResult` — no new fields needed; synthetic
  changes flow through the existing `changes` list
- `src/depfix/scanners/matching.py` — no changes needed; `assess_scan_change` works
  correctly with synthetic records

---

## 9. Acceptance test commands

```bash
# After implementing, verify sentry v6 app now surfaces startTransaction removal
bash scripts/test_pipeline.sh sentry:bedilk/depfix-test-sentry-v6-app
# Expected: plan output shows sentry.startTransaction in REPORT_ONLY notices
# (no longer 0 PRs with silent NO_CALL_SITES)

# Regression: firecrawl openai scan should still work
bash scripts/test_pipeline.sh openai:bedilk/firecrawl

# Unit tests must pass
make test
```

---

## 10. Summary

The gap is a single missing capability: comparing the **repo's actual installed SDK
version** (from lockfile) against the **latest npm version** when the feed's
previous-major comparison window doesn't cover the full version gap.

The building block exists (`TsExportsSource._exports_for(version)`). The integration
point is clear (`_run_repo_body` after `_prescan_providers`). The data is available
(`result.dependencies[*].resolved_version`). The downstream pipeline requires no
changes — synthetic `BreakingChange(kind=METHOD_REMOVED)` flows through
`assess_scan_change` → `_report_removal` correctly.

Total new code estimate: ~120 lines across 2 new files + ~30 lines modification to
`runner.py`. No schema changes. No new dependencies.
