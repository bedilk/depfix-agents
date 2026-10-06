# Python/Ruby Drift Path Test Cases

**Task:** T-9 Gap 4 (HIGH) + Gap 3 (MEDIUM) — draft specific test cases  
**Date:** 2026-10-06  
**Researcher:** researcher agent  
**Goal:** Provide implementable unit test cases covering the Python and Ruby drift code paths
and the untested `dependency_drift_policy` parameters (`scope`, `max_minor_gap`).

---

## Context

From `research/drift-detection-audit.md`:

- **Gap 4 (HIGH):** `dependency_drift_policy` is exercised for Python and Ruby manifests,
  but `build_pypi_dependency_drift_bumps` and `build_ruby_dependency_drift_bumps` are barely
  tested. No test covers the full path through `fix_service._run_dependency_drift` for major
  Python/Ruby drift.

- **Gap 3 (MEDIUM):** `dependency_drift_policy(change, max_minor_gap=N)` and
  `dependency_drift_policy(change, scope="any-minor"|"any")` have **zero test coverage** in
  any ecosystem.

The implementer should add the tests below to their respective files. All test cases use only
the public functions already imported in those files — no new dependencies needed.

---

## 1. New tests for `dependency_drift_policy` — add to `tests/unit/test_pipeline_preverify_manifest.py`

These cover the untested `scope` and `max_minor_gap` parameters.

```python
# ---------------------------------------------------------------------------
# dependency_drift_policy — scope and max_minor_gap gates (Gap 3)
# ---------------------------------------------------------------------------

def _bump_change(old: str, new: str) -> BreakingChange:
    return BreakingChange(
        package="acme-sdk",
        old_version=old,
        new_version=new,
        old_api=f"acme-sdk@{old}",
        new_api=f"acme-sdk@{new}",
        description="Registry version drift",
        migration_guide="",
        kind=ChangeKind.DEPENDENCY_VERSION_BUMP,
        source=ClassificationSource.REGISTRY,
    )


def test_scope_any_minor_declines_single_major_step() -> None:
    # scope="any-minor" blocks ALL cross-major moves — even N→N+1
    assert dependency_drift_policy(_bump_change("2.0.0", "3.0.0"), scope="any-minor") == "declined"


def test_scope_any_minor_allows_same_major_minor_drift() -> None:
    assert dependency_drift_policy(_bump_change("2.1.0", "2.5.0"), scope="any-minor") == "automatic"


def test_scope_any_minor_declines_multi_major_step() -> None:
    assert dependency_drift_policy(_bump_change("1.0.0", "4.0.0"), scope="any-minor") == "declined"


def test_scope_any_allows_multi_major_step() -> None:
    # scope="any" — even a 3-major jump is eligible
    assert dependency_drift_policy(_bump_change("1.0.0", "4.0.0"), scope="any") == "review_pr"


def test_scope_any_with_max_major_gap_zero_still_produces_review_pr_not_automatic() -> None:
    # scope="any" unlocks the *distance* gate, but max_major_gap=0 still routes to review_pr
    assert (
        dependency_drift_policy(_bump_change("1.0.0", "2.0.0"), scope="any", max_major_gap=0)
        == "review_pr"
    )


def test_scope_any_with_max_major_gap_raised_produces_automatic() -> None:
    # If max_major_gap is raised to 1, a single-major drift becomes automatic under scope="any"
    assert (
        dependency_drift_policy(_bump_change("1.0.0", "2.0.0"), scope="any", max_major_gap=1)
        == "automatic"
    )


def test_max_minor_gap_zero_makes_every_minor_step_review_pr() -> None:
    # max_minor_gap=0 means any advance beyond zero minor steps requires review
    assert (
        dependency_drift_policy(_bump_change("1.2.0", "1.3.0"), max_minor_gap=0) == "review_pr"
    )


def test_max_minor_gap_allows_drift_within_limit() -> None:
    # max_minor_gap=3: moving 2 minor versions is within the limit → automatic
    assert (
        dependency_drift_policy(_bump_change("1.2.0", "1.4.0"), max_minor_gap=3) == "automatic"
    )


def test_max_minor_gap_triggers_review_pr_when_exceeded() -> None:
    # max_minor_gap=3: moving 5 minor versions exceeds the limit → review_pr
    assert (
        dependency_drift_policy(_bump_change("1.2.0", "1.7.0"), max_minor_gap=3) == "review_pr"
    )


def test_max_minor_gap_does_not_affect_major_drift() -> None:
    # max_minor_gap only applies when major_gap == 0; for a major drift it has no effect
    # major_gap=1 > max_major_gap=0 → review_pr regardless of max_minor_gap
    assert (
        dependency_drift_policy(_bump_change("1.2.0", "2.0.0"), max_minor_gap=0) == "review_pr"
    )


def test_multi_major_drift_is_declined_under_default_scope() -> None:
    # scope="one-major" (default): 2+ major steps → declined
    assert dependency_drift_policy(_bump_change("1.0.0", "3.0.0")) == "declined"


def test_non_semver_version_is_declined() -> None:
    # Stripe-style dated versions can't be parsed → declined (not silently "automatic")
    assert dependency_drift_policy(_bump_change("2024-09-15", "2025-01-15")) == "declined"
```

---

## 2. New tests for Ruby `build_ruby_dependency_drift_bumps` — new file `tests/unit/test_ruby_manifests.py`

No tests exist for this function at all. The file `src/depfix/ecosystems/ruby_manifests.py`
exports `build_ruby_dependency_drift_bumps` and `_rewrite_gemfile`.

```python
"""Unit tests for the Ruby dependency-drift Gemfile writer."""

from __future__ import annotations

from pathlib import Path

from depfix.core.models import BreakingChange, ChangeKind, ClassificationSource
from depfix.ecosystems.ruby_manifests import build_ruby_dependency_drift_bumps


def _drift(package: str, old: str, new: str) -> BreakingChange:
    return BreakingChange(
        package=package,
        old_version=old,
        new_version=new,
        old_api=f"{package}@{old}",
        new_api=f"{package}@{new}",
        description="Registry version drift",
        migration_guide="",
        kind=ChangeKind.DEPENDENCY_VERSION_BUMP,
        source=ClassificationSource.REGISTRY,
    )


def _only(bumps: list):
    assert len(bumps) == 1, bumps
    return bumps[0]


def test_bumps_a_pessimistic_constraint(tmp_path: Path) -> None:
    (tmp_path / "Gemfile").write_text(
        "source 'https://rubygems.org'\ngem 'sentry-ruby', '~> 7.0'\n"
    )

    bump = _only(build_ruby_dependency_drift_bumps(tmp_path, _drift("sentry-ruby", "7.0.0", "7.3.0")))

    assert bump.manifest_relpath == "Gemfile"
    assert bump.new_spec == "~> 7.3.0"
    assert "gem 'sentry-ruby', '~> 7.3.0'" in bump.fixed_content


def test_bumps_an_exact_pin(tmp_path: Path) -> None:
    (tmp_path / "Gemfile").write_text("gem 'stripe', '5.1.0'\n")

    bump = _only(build_ruby_dependency_drift_bumps(tmp_path, _drift("stripe", "5.1.0", "5.3.0")))

    assert "gem 'stripe', '~> 5.3.0'" in bump.fixed_content


def test_bumps_a_gte_constraint(tmp_path: Path) -> None:
    (tmp_path / "Gemfile").write_text("gem 'openai', '>= 3.0', '< 4.0'\n")

    bump = _only(build_ruby_dependency_drift_bumps(tmp_path, _drift("openai", "3.0.0", "3.5.0")))

    assert bump.new_spec == "~> 3.5.0"


def test_leaves_unrelated_gems_alone(tmp_path: Path) -> None:
    (tmp_path / "Gemfile").write_text("gem 'rails', '~> 7.0'\ngem 'stripe', '~> 5.1'\n")

    bumps = build_ruby_dependency_drift_bumps(tmp_path, _drift("stripe", "5.1.0", "5.3.0"))

    assert len(bumps) == 1
    assert "gem 'rails', '~> 7.0'" in bumps[0].fixed_content


def test_major_drift_returns_empty(tmp_path: Path) -> None:
    # build_ruby_dependency_drift_bumps short-circuits on major drift (policy != automatic)
    (tmp_path / "Gemfile").write_text("gem 'sentry-ruby', '~> 7.0'\n")

    assert build_ruby_dependency_drift_bumps(tmp_path, _drift("sentry-ruby", "7.0.0", "8.0.0")) == []


def test_multi_major_drift_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "Gemfile").write_text("gem 'stripe', '~> 5.0'\n")

    assert build_ruby_dependency_drift_bumps(tmp_path, _drift("stripe", "5.0.0", "8.0.0")) == []


def test_no_gemfile_returns_empty(tmp_path: Path) -> None:
    assert build_ruby_dependency_drift_bumps(tmp_path, _drift("stripe", "5.0.0", "5.3.0")) == []


def test_gem_without_version_constraint_is_not_rewritten(tmp_path: Path) -> None:
    # A gem line with no version — no constraint to rewrite
    (tmp_path / "Gemfile").write_text("gem 'stripe'\n")

    assert build_ruby_dependency_drift_bumps(tmp_path, _drift("stripe", "5.0.0", "5.3.0")) == []


def test_skips_gemfile_in_vendor(tmp_path: Path) -> None:
    (tmp_path / "Gemfile").write_text("gem 'stripe', '~> 5.0'\n")
    vendor_gemfile = tmp_path / "vendor" / "cache"
    vendor_gemfile.mkdir(parents=True)
    (vendor_gemfile / "Gemfile").write_text("gem 'stripe', '~> 4.0'\n")

    bumps = build_ruby_dependency_drift_bumps(tmp_path, _drift("stripe", "5.0.0", "5.3.0"))

    assert len(bumps) == 1
    assert bumps[0].manifest_relpath == "Gemfile"


def test_manifest_major_mismatch_skips_bump(tmp_path: Path) -> None:
    # Gemfile declares major 4, but drift record is for major 5 — skip to avoid wrong update
    (tmp_path / "Gemfile").write_text("gem 'stripe', '~> 4.0'\n")

    assert build_ruby_dependency_drift_bumps(tmp_path, _drift("stripe", "5.0.0", "5.3.0")) == []
```

---

## 3. Additional Python manifest tests — add to `tests/unit/test_pypi_manifests.py`

The existing tests cover the happy path and major-drift rejection. Missing cases:

```python
def test_multi_major_pypi_drift_returns_empty(tmp_path: Path) -> None:
    # scope="one-major" default: 1.x → 3.x is declined by dependency_drift_policy → []
    (tmp_path / "requirements.txt").write_text("openai==1.2.0\n")

    assert build_pypi_dependency_drift_bumps(tmp_path, _drift("openai", "1.2.0", "3.0.0")) == []


def test_requirements_dev_txt_is_also_bumped(tmp_path: Path) -> None:
    (tmp_path / "requirements-dev.txt").write_text("openai==1.2.0\n")

    bump = _only(build_pypi_dependency_drift_bumps(tmp_path, _drift("openai", "1.2.0", "1.4.3")))

    assert bump.manifest_relpath == "requirements-dev.txt"
    assert "openai==1.4.3" in bump.fixed_content


def test_requirements_txt_and_pyproject_both_bumped(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("openai==1.2.0\n")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["openai>=1.0,<2"]\n'
    )

    bumps = build_pypi_dependency_drift_bumps(tmp_path, _drift("openai", "1.2.0", "1.4.3"))

    relpaths = {b.manifest_relpath for b in bumps}
    assert "requirements.txt" in relpaths
    assert "pyproject.toml" in relpaths
```

---

## 4. Fix_service Python major drift through the service — add to `tests/unit/test_pipeline_preverify_manifest.py`

The existing `test_pypi_dependency_drift_uses_the_fix_service_without_call_sites` covers only
same-major drift. The major-drift path through fix_service is untested.

```python
def test_pypi_major_drift_produces_no_committed_edit(tmp_path: Path) -> None:
    """For Python major drift, the manifest writer returns [] — no file is touched."""
    root = tmp_path / "checkout"
    root.mkdir()
    (root / "requirements.txt").write_text("acme-sdk==1.2.0\n")
    change = BreakingChange(
        package="acme-sdk",
        old_version="1.2.0",
        new_version="2.0.0",
        old_api="acme-sdk@1.2.0",
        new_api="acme-sdk@2.0.0",
        description="Registry version drift",
        migration_guide="",
        kind=ChangeKind.DEPENDENCY_VERSION_BUMP,
        source=ClassificationSource.REGISTRY,
    )
    scan = RepoScanResult(repo_full_name="acme/widgets", commit_sha="abc")

    result = run_fix_for_change(
        checkout=Checkout(path=root, is_temporary=False),
        scan_result=scan,
        change=change,
        settings=Settings(verify_enabled=False),
        repo_config=RepoConfig(version=SUPPORTED_VERSION, verify=False),
        fixer=_FakeFixer(),
    )

    # Major drift: policy is review_pr, manifest writer returns [], so no edit committed
    assert result.committable == []
    # requirements.txt must NOT be altered
    assert "acme-sdk==1.2.0" in (root / "requirements.txt").read_text()


def test_ruby_minor_drift_uses_fix_service_without_call_sites(tmp_path: Path) -> None:
    """Same-major Ruby drift is committed as a Gemfile rewrite."""
    root = tmp_path / "checkout"
    root.mkdir()
    (root / "Gemfile").write_text("gem 'acme-sdk', '~> 1.2'\n")
    change = BreakingChange(
        package="acme-sdk",
        old_version="1.2.0",
        new_version="1.4.0",
        old_api="acme-sdk@1.2.0",
        new_api="acme-sdk@1.4.0",
        description="Registry version drift",
        migration_guide="",
        kind=ChangeKind.DEPENDENCY_VERSION_BUMP,
        source=ClassificationSource.REGISTRY,
    )
    scan = RepoScanResult(repo_full_name="acme/widgets", commit_sha="abc")

    result = run_fix_for_change(
        checkout=Checkout(path=root, is_temporary=False),
        scan_result=scan,
        change=change,
        settings=Settings(verify_enabled=False),
        repo_config=RepoConfig(version=SUPPORTED_VERSION, verify=False),
        fixer=_FakeFixer(),
    )

    assert len(result.committable) == 1
    assert result.committable[0].relpath == "Gemfile"
    assert "~> 1.4.0" in (root / "Gemfile").read_text()


def test_ruby_major_drift_produces_no_committed_edit(tmp_path: Path) -> None:
    """For Ruby major drift, manifest writer returns [] — nothing committed."""
    root = tmp_path / "checkout"
    root.mkdir()
    (root / "Gemfile").write_text("gem 'acme-sdk', '~> 1.2'\n")
    change = BreakingChange(
        package="acme-sdk",
        old_version="1.2.0",
        new_version="2.0.0",
        old_api="acme-sdk@1.2.0",
        new_api="acme-sdk@2.0.0",
        description="Registry version drift",
        migration_guide="",
        kind=ChangeKind.DEPENDENCY_VERSION_BUMP,
        source=ClassificationSource.REGISTRY,
    )
    scan = RepoScanResult(repo_full_name="acme/widgets", commit_sha="abc")

    result = run_fix_for_change(
        checkout=Checkout(path=root, is_temporary=False),
        scan_result=scan,
        change=change,
        settings=Settings(verify_enabled=False),
        repo_config=RepoConfig(version=SUPPORTED_VERSION, verify=False),
        fixer=_FakeFixer(),
    )

    assert result.committable == []
    assert "~> 1.2" in (root / "Gemfile").read_text()
```

---

## 5. Bug: Python/Ruby manifest writers ignore Settings drift parameters

**File:** `src/depfix/ecosystems/pypi_manifests.py:88`,
          `src/depfix/ecosystems/ruby_manifests.py:46`

Both functions call `dependency_drift_policy(change)` with **default** parameters,
ignoring the `max_major_gap`, `max_minor_gap`, and `scope` from `Settings`.

The fix_service (lines 333-338) correctly passes `settings.drift_*` to `dependency_drift_policy`
for its own policy gate. But then the manifest writers are called unconditionally and re-run
the policy check with defaults, possibly contradicting the service-level decision.

**Concrete failure scenario:**
- `Settings(drift_scope="any", drift_max_major_gap=1)` (allow 1-major step automatically)
- `fix_service` policy gate: `dependency_drift_policy(change, scope="any", max_major_gap=1)` →
  for old=1.0, new=2.0 returns `"automatic"` (major_gap=1 == max_major_gap=1)
- `build_pypi_dependency_drift_bumps(root, change)` calls `dependency_drift_policy(change)`
  with defaults → major_gap=1 > max_major_gap=0 → `"review_pr"` → returns `[]`
- Result: fix_service says automatic, manifest writer returns `[]`, no edit is committed.
  The PR gets created with no `requirements.txt` change.

**Recommended fix:** Thread the relevant policy parameters into the manifest builders, or
pass the pre-computed policy result in, rather than recomputing it with defaults.

**Test case to prove the bug (add to `test_pipeline_preverify_manifest.py`):**

```python
def test_pypi_major_drift_with_raised_max_major_gap_commits_an_edit(tmp_path: Path) -> None:
    """When max_major_gap=1, a one-major PyPI drift should produce an edit, not be silently skipped."""
    root = tmp_path / "checkout"
    root.mkdir()
    (root / "requirements.txt").write_text("acme-sdk==1.2.0\n")
    change = BreakingChange(
        package="acme-sdk",
        old_version="1.2.0",
        new_version="2.0.0",
        old_api="acme-sdk@1.2.0",
        new_api="acme-sdk@2.0.0",
        description="Registry version drift",
        migration_guide="",
        kind=ChangeKind.DEPENDENCY_VERSION_BUMP,
        source=ClassificationSource.REGISTRY,
    )
    scan = RepoScanResult(repo_full_name="acme/widgets", commit_sha="abc")

    result = run_fix_for_change(
        checkout=Checkout(path=root, is_temporary=False),
        scan_result=scan,
        change=change,
        settings=Settings(
            verify_enabled=False,
            drift_max_major_gap=1,   # allow major bumps automatically
            drift_scope="one-major",
        ),
        repo_config=RepoConfig(version=SUPPORTED_VERSION, verify=False),
        fixer=_FakeFixer(),
    )

    # This currently FAILS because build_pypi_dependency_drift_bumps ignores settings params.
    # After the fix, this should return 1 committed edit.
    assert len(result.committable) == 1
    assert "acme-sdk==2.0.0" in (root / "requirements.txt").read_text()
```

---

## Summary of coverage gaps filled by these tests

| Gap | Severity | Test location | Cases |
|---|---|---|---|
| `scope="any-minor"` / `scope="any"` | MEDIUM | test_pipeline_preverify_manifest.py | 6 cases |
| `max_minor_gap` policy gate | MEDIUM | test_pipeline_preverify_manifest.py | 4 cases |
| Multi-major declined under default scope | MEDIUM | test_pipeline_preverify_manifest.py | 1 case |
| Non-semver version declined | HIGH | test_pipeline_preverify_manifest.py | 1 case |
| Ruby `build_ruby_dependency_drift_bumps` | HIGH | tests/unit/test_ruby_manifests.py | 9 cases |
| PyPI `requirements-dev.txt` bump | LOW | test_pypi_manifests.py | 1 case |
| PyPI multi-file bump | LOW | test_pypi_manifests.py | 1 case |
| PyPI multi-major declined | LOW | test_pypi_manifests.py | 1 case |
| Fix_service Python major drift → no edit | HIGH | test_pipeline_preverify_manifest.py | 1 case |
| Fix_service Ruby same-major drift → edit | HIGH | test_pipeline_preverify_manifest.py | 1 case |
| Fix_service Ruby major drift → no edit | HIGH | test_pipeline_preverify_manifest.py | 1 case |
| Bug: manifest writers ignore Settings params | HIGH | test_pipeline_preverify_manifest.py | 1 failing case |

**Total new tests: 28**

*Source files studied:*
- `src/depfix/ecosystems/pypi_manifests.py`
- `src/depfix/ecosystems/ruby_manifests.py`
- `src/depfix/codemods/lockfile.py:122-163`
- `src/depfix/core/fix_service.py:321-438`
- `tests/unit/test_pypi_manifests.py`
- `tests/unit/test_ecosystems_ruby_runtime.py`
- `tests/unit/test_pipeline_preverify_manifest.py`
