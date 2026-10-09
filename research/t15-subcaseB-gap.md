# T-15 Gap: Sub-case B — Call Site Uses API Absent from Installed Version

**Date**: 2026-10-09  
**Researcher**: researcher (claude-sonnet-4-6-1m)  
**Status**: BLOCKER for T-15 acceptance on `bedilk/depfix-test-sentry-v6-app`

---

## Problem

The T-15 implementation in `src/depfix/sources/repo_exports.py` computes:

```python
removed = installed_exports - latest_exports
```

This correctly handles **sub-case A**: API exists in installed version but is removed in latest.
Example: repo has `@stripe/stripe-js@3.0.0`, `chargeCreate` removed in v4. installed exports it, latest doesn't → synthetic change created. ✓

However, it **misses sub-case B**: API is absent from the installed version because it was removed in an earlier major.

### Concrete failure: `bedilk/depfix-test-sentry-v6-app`

| Variable | Value |
|---|---|
| Installed version | `@sentry/node@10.75.3` (from lockfile) |
| Latest version | `11.6.0` |
| Call site | `sentry.startTransaction` |
| When removed | sentry v8.0.0 |

`startTransaction` is absent from `@sentry/node@10.75.3` because it was removed two major versions earlier (v8). Therefore:

```python
installed_exports = exports_for_version("@sentry/node", "10.75.3")  # no startTransaction
latest_exports    = exports_for_version("@sentry/node", "11.6.0")   # no startTransaction
removed = installed_exports - latest_exports  # = {} (empty set!)
```

No synthetic change is created. `sentry.startTransaction` remains non-actionable. T-15 acceptance test **fails**.

This gap was in the original research spec (`research/repo-version-aware-exports.md`) and was carried into the implementation unchanged.

---

## Fix

Add a second pass in `synthetic_changes_for_scan` after the `removed = installed - latest` diff:

**For each actionable call site whose exported name is absent from `installed_exports`:**
→ The code references a dead API (removed before the installed version)
→ Create a synthetic BreakingChange

```python
# Sub-case B: call site uses an export absent from the installed version.
# This means the API was removed BEFORE the installed version — the code is
# calling a ghost API that hasn't existed since some earlier major.
for site in result.actionable_sites:
    export_name = _export_name_from_symbol(site.symbol, provider_id)
    if export_name is None:
        continue
    old_api = f"{provider_id}.{export_name}"
    if old_api in seen_old_apis:
        continue
    if installed_exports is not None and export_name not in installed_exports:
        changes.append(
            BreakingChange(
                package=package,
                old_version="0.0.0",        # removed before installed; exact version unknown
                new_version=installed_version,
                old_api=old_api,
                new_api="",
                description=(
                    f"{export_name} is not exported by {package}@{installed_version}; "
                    f"it was removed in an earlier major version"
                ),
                migration_guide="",
                kind=ChangeKind.METHOD_REMOVED,
                source=ClassificationSource.SPEC_DIFF,
                provider_id=provider_id,
                confidence=0.9,
            )
        )
        seen_old_apis.add(old_api)
```

Where `_export_name_from_symbol` is the inverse of `_call_site_uses_export`:

```python
def _export_name_from_symbol(symbol: str, provider_id: str) -> str | None:
    prefix = f"{provider_id}."
    if not symbol.startswith(prefix):
        return None
    after = symbol[len(prefix):]
    return after.split(".")[0]  # first segment only: "hub.captureMessage" → "hub"
```

---

## Where to add this

File: `src/depfix/sources/repo_exports.py`

In `synthetic_changes_for_scan`, after the existing loop over `removed_exports` (line ~151),
add the sub-case B loop. Both loops share the same `seen_old_apis` set to prevent duplicates
(sub-case A and B can't both trigger for the same `old_api`).

---

## Updated test needed

Add to `tests/unit/test_repo_aware_exports.py`:

```python
def test_subcaseB_callsite_absent_from_installed_creates_change() -> None:
    """Covers the sentry v6-app scenario: startTransaction removed in v8,
    repo lockfile is v10, code still calls startTransaction."""
    # installed=v10: startTransaction absent; latest=v11: also absent
    result = _scan(symbol="sentry.startTransaction", resolved_version="10.75.3")

    with patch(
        "depfix.sources.repo_exports.repo_version_exports_diff",
        return_value=("11.6.0", set()),  # empty removed set — sub-case A finds nothing
    ), patch(
        "depfix.sources.repo_exports._exports_for_version",
        return_value={"captureException", "addBreadcrumb"},  # no startTransaction
    ):
        changes = synthetic_changes_for_scan(
            result,
            provider_id="sentry",
            npm_packages=["@sentry/node"],
            http=MagicMock(),
            npm=MagicMock(),
        )

    assert len(changes) == 1
    ch = changes[0]
    assert ch.old_api == "sentry.startTransaction"
    assert ch.kind is ChangeKind.METHOD_REMOVED
    assert ch.new_version == "10.75.3"   # removed before installed version
    assert ch.confidence == pytest.approx(0.9)
```

---

## False-positive risk

Low. The scanner only generates call sites for provider-namespaced symbols (e.g., `sentry.X`),
and these are matched against the provider's npm packages. If `X` is genuinely never exported
(e.g., a typo or internal stub), the scanner wouldn't have found the call site in the first
place — scan confidence guards already filter out low-quality matches.

---

## Summary

| Sub-case | Scenario | Current impl | After fix |
|---|---|---|---|
| A | API in installed, removed in latest | ✓ Works | ✓ Works |
| B | API absent from installed (removed earlier) | ✗ Missed | ✓ Works |

The sentry v6 test repo (`bedilk/depfix-test-sentry-v6-app`) requires sub-case B.
`sentry.startTransaction` will only become actionable after this fix is applied.
