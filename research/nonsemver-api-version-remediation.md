# Non-Semver API Version Remediation Plan

**Task origin:** Proactive follow-up to T-9 Gap 1 (HIGH)  
**Date:** 2026-10-05  
**Researcher:** researcher agent (round 6)

---

## Problem Statement

Stripe and similar providers use dated API versions (`"2024-10-01"`, `"2025-01-15"`) rather than
semver. depfix has infrastructure for detecting these (`api_version_pin` call sites,
`ApiVersionLiteralCodemod`, `changelog_html` source, `api_version_scheme: dated` in providers.yaml)
but the **symbol-matching chain is broken**: a classified `API_VERSION_BUMP` change never reaches
ACTIONABLE, so `ApiVersionLiteralCodemod` never runs and no PR is opened.

T-9 documented this as "version unresolved" display-only, but the real impact is more severe:
even when the fix codemod is ready, the scan-match pipeline rejects the change as `NO_CALL_SITES`.

---

## Infrastructure That Already Exists (Not the Problem)

| Component | File | What it does |
|---|---|---|
| `api_version_scheme: dated` | `providers.yaml:40` | Marks Stripe as a dated-scheme provider |
| `ProviderSpec.api_version_scheme` | `providers/models.py:31` | Stores scheme in memory |
| `CallSiteKind.API_VERSION_PIN` | `scanners/models.py:29` | Kind for detected dated pins |
| `_version_pin_re` + scanner | `scanners/callsites.py:133–682` | Detects `apiVersion: "2024-..."` literals |
| `callsites.py:678` | scanner | Emits `symbol="stripe.<api_version_pin>"` |
| `ApiVersionLiteralCodemod` | `codemods/config_literal.py:11` | Rewrites dated literal in code |
| `ChangelogHtmlSource` | `sources/changelog_html.py` | Polls Stripe changelog for new dates |
| `ChangeKind.API_VERSION_BUMP` | `core/models.py:52` | The kind for API version advances |

Everything is in place. The bug is in the symbol-matching chain.

---

## Root Cause: Symbol Matching Chain is Broken for Dated `old_api`

### Call-site symbol produced by scanner

`scanners/callsites.py:678`:
```python
symbol=f"{target.provider_id}.<api_version_pin>",
# → "stripe.<api_version_pin>"
```

### Symbols extracted from a classified `API_VERSION_BUMP` change

A Stripe changelog event classified by the LLM produces a `BreakingChange`:
```python
BreakingChange(
    kind=ChangeKind.API_VERSION_BUMP,
    old_api="2024-09-15",    # dated string — NOT a dotted symbol
    new_api="2025-01-15",
    ...
)
```

`scanners/repo.py:103` → `symbols_for_change("stripe", change)`:
1. Calls `add_api_symbol("2024-09-15", add)` (line 122)
2. → `_qualify_symbol("stripe", "2024-09-15", allow_bare_identifier=False)` (line 115)
3. `_qualify_symbol` (line 170–198): `"2024-09-15"` does not start with `"stripe."`, is not `"stripe"`, 
   `_looks_like_member_path("2024-09-15")` is False (contains `-`, not a valid dotted JS path),
   `allow_bare_identifier=False` → returns **`None`**
4. Symbol is rejected. `symbols_for_change` returns **`()`** (empty tuple).

### Match result

`scanners/matching.py:55–67` → `assess_scan_change`:
```python
# Not DEPENDENCY_VERSION_BUMP, so needs call-site matching:
symbols = symbols_for_change(...)  # → ()
exact = tuple(s for s in result.actionable_sites if _site_matches_exact(s, ()))  # → ()
suffix = tuple(...)  # → ()
# No replacement symbols either (new_api="2025-01-15" → also returns ())
return ScanChangeAssessment(change, ScanMatchStatus.NO_CALL_SITES, "...")
```

**Result:** `api_version_pin` sites in the repo are detected but never matched to the
`API_VERSION_BUMP` change. `ApiVersionLiteralCodemod` never runs. No PR.

---

## Secondary Gap: `drift_summary` shows "version unresolved" for Stripe

`scanners/drift_summary.py:70`:
```python
parsed = [(parse_semver(version), version) for version in versions if parse_semver(version)]
```
`parse_semver("2025-01-15")` → `None` → filtered out. `feed_version = ""`.

`drift_summary._decision(current="2020-08-27", feed="")` → `"version unresolved"`.

**Impact:** Display-only. The planning pipeline uses `ScanChangeAssessment`, not `drift_summary`.
But operators reading the scan report can't tell if the repo's Stripe API version is stale.

---

## Fix 1 (CRITICAL): Wire `API_VERSION_BUMP` to `api_version_pin` sites

**File:** `src/depfix/scanners/repo.py`  
**Function:** `symbols_for_change` (line 103) or `add_api_symbol` (line 146)

**Option A — simplest, least invasive:** Add a special case in `add_api_symbol`:
```python
_DATED_API_VERSION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:-[\w.]+)?$")

def add_api_symbol(api: str, add: Callable[..., None]) -> None:
    candidate = api.strip()
    if candidate.endswith(")"):
        candidate = candidate.split("(", 1)[0].strip()
    # Dated API version strings are not member-path symbols; they match the
    # synthetic <api_version_pin> symbol that the call-site scanner emits.
    if _DATED_API_VERSION_RE.match(candidate):
        add(f"<api_version_pin>", allow_bare=True)
        return
    add(candidate, allow_bare=False)
```

This relies on `_qualify_symbol` treating `"<api_version_pin>"` as a bare identifier with
`allow_bare=True`, producing `"stripe.<api_version_pin>"` — matching the scanner's symbol exactly.

**Option B — more explicit:** in `symbols_for_change`, detect the `API_VERSION_BUMP` kind directly:
```python
def symbols_for_change(provider_id: str, change: BreakingChange) -> tuple[str, ...]:
    symbols: list[str] = []

    def add(raw: str, *, allow_bare: bool) -> None:
        symbol = _qualify_symbol(provider_id, raw, allow_bare_identifier=allow_bare)
        if symbol is not None and symbol not in symbols:
            symbols.append(symbol)

    for hint in change.call_site_hints:
        add(hint, allow_bare=True)

    # API_VERSION_BUMP with a dated old_api matches the <api_version_pin> synthetic symbol.
    if change.kind == ChangeKind.API_VERSION_BUMP and _DATED_API_VERSION_RE.match(change.old_api.strip()):
        add(f"<api_version_pin>", allow_bare=True)
    else:
        add_api_symbol(change.old_api, add)
    ...
```

**Recommendation:** Option B is safer. It's conditional on `kind=API_VERSION_BUMP` so it never
affects other change kinds. Also, `ChangeKind` import is already available in `repo.py` (imported
via `BreakingChange`).

**Import to add:** `from depfix.core.models import ChangeKind` (if not already present)

**Tests to add** (in `tests/unit/test_repo_symbols.py` or existing repo-symbols test file):
```python
def test_api_version_bump_dated_old_api_maps_to_version_pin_symbol():
    from depfix.core.models import BreakingChange, ChangeKind
    from depfix.scanners.repo import symbols_for_change
    change = BreakingChange(
        package="stripe", old_version="2024-09-15", new_version="2025-01-15",
        old_api="2024-09-15", new_api="2025-01-15",
        description="...", migration_guide="...", kind=ChangeKind.API_VERSION_BUMP,
    )
    assert symbols_for_change("stripe", change) == ("stripe.<api_version_pin>",)

def test_api_version_bump_dated_symbol_matches_api_version_pin_callsite():
    from depfix.scanners.matching import _site_matches_exact
    from depfix.scanners.models import CallSite, CallSiteKind, MatchConfidence
    site = CallSite(
        file_path="stripeClient.js", line_number=5, column=0,
        line_content='new Stripe(key, { apiVersion: "2024-09-15" })',
        symbol="stripe.<api_version_pin>", kind=CallSiteKind.API_VERSION_PIN,
        confidence=MatchConfidence.MEDIUM, provider_id="stripe",
    )
    assert _site_matches_exact(site, ("stripe.<api_version_pin>",))
```

---

## Fix 2 (MEDIUM): `drift_summary` comparisons for dated versions

**File:** `src/depfix/scanners/drift_summary.py`  
**Function:** `_highest_feed_version` (line 68), `_decision` (line 76), `_risk` (line 93)

Add `_parse_dated_version` alongside `parse_semver` (YYYY-MM-DD dates sort correctly as ISO strings):

```python
_DATED_VERSION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:-[\w.]+)?$")

def _parse_dated_version(value: str) -> str | None:
    """Return value if it's a dated API version (sorts correctly as a string), else None."""
    return value.strip() if _DATED_VERSION_RE.match(value.strip()) else None

def _highest_feed_version(assessments: list[ScanChangeAssessment]) -> str:
    versions = [a.change.new_version for a in assessments]
    # Prefer semver; fall back to dated-version string comparison.
    semver_parsed = [(parse_semver(v), v) for v in versions if parse_semver(v)]
    if semver_parsed:
        return max(semver_parsed, key=lambda item: item[0])[1]
    dated = [v for v in versions if _parse_dated_version(v)]
    if dated:
        return max(dated)  # ISO date string max is correct for YYYY-MM-DD
    return ""
```

Update `_decision` and `_risk` to also handle dated current/feed:
```python
def _decision(current: str, feed: str, assessments: list[ScanChangeAssessment]) -> str:
    current_semver, feed_semver = parse_semver(current), parse_semver(feed)
    if current_semver is None or feed_semver is None:
        # Try dated comparison for providers like Stripe.
        current_dated, feed_dated = _parse_dated_version(current), _parse_dated_version(feed)
        if current_dated and feed_dated:
            if current_dated < feed_dated:
                if any(a.status is ScanMatchStatus.ACTIONABLE for a in assessments):
                    return "actionable"
                return "dated-version drift"
            return "current or newer"
        return "version unresolved"
    # ... existing semver logic unchanged
```

**Test to add:**
```python
def test_drift_summary_dated_versions_show_actionable_not_unresolved():
    # Verifies that Stripe-style dates don't produce "version unresolved"
    ...
```

---

## Fix 3 (LOW — no current providers.yaml impact): `dependency_drift_policy` with non-semver package releases

`src/depfix/codemods/lockfile.py:145-147`:
```python
old, new = _semver(change.old_version), _semver(change.new_version)
if old is None or new is None or new <= old:
    return "declined"
```

No provider in the current `providers.yaml` uses non-semver npm/pypi/rubygems releases (Stripe's npm
package `stripe@17.x.x` is semver). Skip this fix until a real case appears.

---

## End-to-End Test Case to Add

Once Fix 1 is applied, the following integration test should pass:

```python
def test_stripe_api_version_bump_is_actionable_with_pin_site():
    """API_VERSION_BUMP change + api_version_pin call site → ACTIONABLE."""
    from depfix.scanners.matching import assess_scan_change
    from depfix.scanners.models import RepoScanResult, CallSite, CallSiteKind, MatchConfidence, DeclaredDependency
    from depfix.core.models import BreakingChange, ChangeKind, ClassificationSource

    change = BreakingChange(
        package="stripe", old_version="2024-09-15", new_version="2025-01-15",
        old_api="2024-09-15", new_api="2025-01-15",
        description="Stripe API version bump", migration_guide="Update apiVersion literal",
        kind=ChangeKind.API_VERSION_BUMP, source=ClassificationSource.MANUAL,
        provider_id="stripe",
    )
    pin_site = CallSite(
        file_path="stripeClient.js", line_number=3, column=0,
        line_content='new Stripe(key, { apiVersion: "2024-09-15" })',
        symbol="stripe.<api_version_pin>", kind=CallSiteKind.API_VERSION_PIN,
        confidence=MatchConfidence.MEDIUM, provider_id="stripe",
    )
    dep = DeclaredDependency(package="stripe", declared_range="^17.0.0", manifest_path="package.json")
    result = RepoScanResult(
        repo_full_name="org/repo", call_sites=[pin_site], dependencies=[dep],
        files_scanned=5, ecosystem="javascript",
    )
    assessment = assess_scan_change(result, change, provider_id="stripe")
    assert assessment.status.value == "actionable"
    assert any(s.kind == CallSiteKind.API_VERSION_PIN for s in assessment.matched_sites)
```

---

## `ApiVersionLiteralCodemod` is already correct — no changes needed

`codemods/config_literal.py:16-21`:
```python
def claims(self, change: BreakingChange) -> bool:
    return (
        change.kind == ChangeKind.API_VERSION_BUMP
        and bool(self._date.fullmatch(change.old_api.strip()))
        and bool(self._date.fullmatch(change.new_api.strip()))
    )
```

This already handles dated `old_api`/`new_api`. Once Fix 1 makes the scan match ACTIONABLE,
the codemod will run and replace `apiVersion: "2024-09-15"` with `apiVersion: "2025-01-15"`.

---

## Summary

| Fix | File | Lines | Effort | Risk |
|---|---|---|---|---|
| Fix 1 (CRITICAL): Wire `API_VERSION_BUMP` to `<api_version_pin>` symbol | `scanners/repo.py` | ~8 lines + `_DATED_API_VERSION_RE` | Small | Low (conditional on kind) |
| Fix 2 (MEDIUM): Dated-version comparison in `drift_summary` | `scanners/drift_summary.py` | ~20 lines | Small | Low (display only) |
| Fix 3 (LOW): `dependency_drift_policy` non-semver | `codemods/lockfile.py` | ~5 lines | Small | Skip until real case |

**Minimum viable fix:** Fix 1 only. Fix 2 improves operator visibility; Fix 3 has no current value.

**Key files to modify:**
- `src/depfix/scanners/repo.py` — Fix 1 (the critical one)
- `src/depfix/scanners/drift_summary.py` — Fix 2 (display improvement)

**Tests to add:**
- `tests/unit/test_repo_symbols.py` — 2 new cases for Fix 1
- `tests/unit/test_drift_summary.py` — 1 new case for Fix 2
- Integration test as shown above (in `tests/unit/test_matching.py` or `test_pipeline_*`)

---

*Key source files:*
- `src/depfix/scanners/repo.py:103,170` — `symbols_for_change`, `_qualify_symbol`
- `src/depfix/scanners/matching.py:55–67` — `assess_scan_change`
- `src/depfix/scanners/callsites.py:676–678` — `api_version_pin` symbol production
- `src/depfix/codemods/config_literal.py:11–37` — `ApiVersionLiteralCodemod` (already correct)
- `src/depfix/scanners/drift_summary.py:68–73` — `_highest_feed_version`
- `src/depfix/sources/changelog_html.py` — Stripe changelog event source
