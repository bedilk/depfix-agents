# Version Drift Detection Audit: Minor vs Major Completeness

**Task:** T-9 — Audit version drift detection, minor vs major classification  
**Date:** 2026-10-05  
**Researcher:** researcher agent  
**Goal:** Document how depfix detects minor vs major drift, which code paths handle each, test coverage, and gaps

---

## 1. Architecture Overview

Version drift flows through 6 layers. Each layer is listed with its file and key function:

```
Feed event (registry version change)
  → semver.py:drift_risk() / is_major_bump()      — classify the move
  → classifier.py:Classifier.classify()            — produce DEPENDENCY_VERSION_BUMP
  → applicability.py:change_applies()             — does this repo's version apply?
  → matching.py:assess_scan_change()              — ACTIONABLE or VERSION_NOT_AFFECTED?
  → lockfile.py:dependency_drift_policy()          — automatic / review_pr / declined?
  → drift_summary.py:summarize_dependency_drift()  — report label for display
```

---

## 2. How Minor vs Major Drift Is Detected

### Layer 1: semver.py — The Core Classification

**File:** `src/depfix/sources/semver.py`

Two functions classify a version move:

**`is_major_bump(old, new)` (line 27):**
```python
def is_major_bump(old: str | None, new: str | None) -> bool:
    o, n = parse_semver(old), parse_semver(new)
    if o is None or n is None:
        return False
    return n[0] > o[0]
```
Used by all feed sources (npm_dist_tag, pypi_dist_tag, rubygems_dist_tag, github_release, ts_exports, changelog_file) to set `Severity.BREAKING` on major moves, `Severity.UNKNOWN` on minor/patch.

**`drift_risk(old, new)` (line 50):**
```python
def drift_risk(old: str | None, new: str | None) -> str:
    o, n = parse_semver(old), parse_semver(new)
    if o is None or n is None or n <= o:
        return ""
    gap = n[0] - o[0]
    if gap == 0:
        return "patch-minor"
    if gap == 1:
        return "major"
    return "multi-major"
```
Returns:
- `"patch-minor"` — same major, any minor/patch advance (no distinction between minor and patch)
- `"major"` — exactly one major step (N → N+1)
- `"multi-major"` — two or more major steps (N → N+2+)
- `""` — not a forward move, unparseable, or equal

**Gap:** `drift_risk` does not distinguish minor from patch moves. Both 1.2.0→1.3.0 and 1.2.0→1.2.1 return `"patch-minor"`. The policy layer cannot differentiate them from the label alone — it must re-parse old/new.

### Layer 2: classifier.py — Producing DEPENDENCY_VERSION_BUMP

**File:** `src/depfix/classify/classifier.py:100-119`

For any registry feed event (npm, pypi, rubygems), a `BreakingChange` of kind `DEPENDENCY_VERSION_BUMP` is created, carrying the raw `old_version` and `new_version` strings. No minor/major distinction is made here — the classifier passes both to downstream layers that re-parse.

### Layer 3: applicability.py — Does This Repo's Version Apply?

**File:** `src/depfix/scanners/applicability.py:43-97`

`_decide_one(dep, change)` logic for `DEPENDENCY_VERSION_BUMP`:

**With resolved lockfile version:**
- If `resolved[0] != new[0]`: returns `APPLIES` with "requires human review" — this is the **major drift** path
- If `affects_version(resolved, old, new)` is True: returns `APPLIES` — this is the **minor/patch drift** path
- If False: returns `NOT_AFFECTED`

**With declared range only (no lockfile):**
- `current_major != new[0]`: returns `APPLIES` with "requires human review" — **major drift** path  
- Otherwise: returns `UNKNOWN` (can't confirm version from range alone)

**Key behavior:** Both minor and major drift return `APPLIES` here. The `APPLIES` status does NOT block — it's the prerequisite for `ACTIONABLE` status in the matching layer.

### Layer 4: matching.py — ACTIONABLE Decision

**File:** `src/depfix/scanners/matching.py:62-67`

```python
if change.kind is ChangeKind.DEPENDENCY_VERSION_BUMP:
    return ScanChangeAssessment(
        change,
        ScanMatchStatus.ACTIONABLE,
        f"dependency version drift: {applicability.reason}",
    )
```

**Critical:** For `DEPENDENCY_VERSION_BUMP`, if applicability doesn't block (`NOT_AFFECTED`), the assessment is immediately `ACTIONABLE` — **no call-site match is required**. Both minor and major drift reach `ACTIONABLE` by this path.

The only path that blocks is if `change_applies()` returns `NOT_AFFECTED`, which happens only when the repo's installed version is already ≥ the feed version.

### Layer 5: lockfile.py:dependency_drift_policy() — The Gate

**File:** `src/depfix/codemods/lockfile.py:122-163`

This is where minor vs major distinction actually gates behavior:

```python
def dependency_drift_policy(
    change: BreakingChange,
    *,
    max_major_gap: int = 0,
    max_minor_gap: int | None = None,
    scope: str = "one-major",
) -> str:
```

**Returns:**
- `"declined"` — not actionable, no PR artifact
- `"review_pr"` — a draft review PR (no auto-merge, needs human)
- `"automatic"` — safe manifest-only update, auto PR

**`scope` gate (checked first):**
- `"one-major"` (default): same-major OR exactly one major step is eligible; 2+ majors → `"declined"`
- `"any-minor"`: only same-major is eligible; ANY major step → `"declined"`
- `"any"`: every forward move is eligible (`depfix scan --anyversion`)

**Within-scope gates (`max_major_gap`, `max_minor_gap`):**
- `major_gap > max_major_gap` → `"review_pr"` (default: 0, so any major step = review_pr unless raised)
- `major_gap == 0 and max_minor_gap is not None and (new[1] - old[1]) > max_minor_gap` → `"review_pr"`

**Defaults with `scope="one-major"`, `max_major_gap=0`, `max_minor_gap=None`:**
| Drift type | Policy |
|---|---|
| Same-major, any minor/patch | `"automatic"` |
| Exactly one major step (N→N+1) | `"review_pr"` |
| Two+ major steps (N→N+2+) | `"declined"` |

**Minor gap gate is disabled by default** (`max_minor_gap=None`). A same-major drift of 50 minor versions gets the same `"automatic"` policy as a 1-minor drift unless `max_minor_gap` is set.

### Layer 6: drift_summary.py — Display Labels

**File:** `src/depfix/scanners/drift_summary.py:76-109`

Used only for display/reporting (not planning decisions):

| Condition | `decision` label | `risk` text |
|---|---|---|
| `current[0] != feed[0]` | `"major-gap review"` | "Major-version gap: review migrations..." |
| Same-major + ACTIONABLE | `"actionable"` | "Feed-proven migration matches..." |
| Same-major, no ACTIONABLE | `"same-major drift"` | "Same-major version drift: review..." |
| No version parse | `"version unresolved"` | "No resolved semver comparison..." |
| current ≥ feed | `"current or newer"` | "No version risk detected..." |

**Important:** `"major-gap review"` fires for **any** cross-major comparison (even 3→4), while the policy layer actually allows 3→4 under default `scope="one-major"`. The display label and the actual plan behavior are misaligned for the N→N+1 case: the drift summary shows "major-gap review" but the plan produces a `review_pr` artifact (not declined).

---

## 3. Code Path Trace: Same-Major Minor Drift (e.g. openai 3.2.0 → 3.5.0)

1. `npm_dist_tag.py`: new version 3.5.0 detected. `is_major_bump("3.2.0", "3.5.0")` → False. `Severity.UNKNOWN`.
2. `classifier.py`: creates `DEPENDENCY_VERSION_BUMP` with old=3.2.0, new=3.5.0.
3. `applicability.py`: `resolved[0] == new[0]` (both 3). `affects_version("3.2.0", "3.2.0", "3.5.0")` → True. Returns `APPLIES`.
4. `matching.py`: `DEPENDENCY_VERSION_BUMP` → `ACTIONABLE`.
5. `dependency_drift_policy`: `major_gap=0`, `max_minor_gap=None` → `"automatic"`.
6. `drift_summary.py`: `current[0] == feed[0]`, has ACTIONABLE assessment → `"actionable"`.

**Result:** Automatic PR artifact for a minor drift. ✓

## 4. Code Path Trace: One-Major Drift (e.g. openai 3.2.0 → 4.0.0)

1. `npm_dist_tag.py`: `is_major_bump("3.2.0", "4.0.0")` → True. `Severity.BREAKING`.
2. `classifier.py`: `DEPENDENCY_VERSION_BUMP` with old=3.2.0, new=4.0.0.
3. `applicability.py`: `resolved[0] (3) != new[0] (4)` → `APPLIES` with "major drift... requires human review".
4. `matching.py`: `DEPENDENCY_VERSION_BUMP` → `ACTIONABLE`.
5. `dependency_drift_policy`: `major_gap=1 > max_major_gap=0` → `"review_pr"`.
6. `drift_summary.py`: `current[0] (3) != feed[0] (4)` → `"major-gap review"`. **Display label says review even though plan is generated.**

**Result:** Draft review PR artifact planned. ✓

## 5. Code Path Trace: Multi-Major Drift (e.g. openai 3.2.0 → 5.0.0)

1. `npm_dist_tag.py`: `is_major_bump("3.2.0", "5.0.0")` → True. `Severity.BREAKING`.
2. `classifier.py`: `DEPENDENCY_VERSION_BUMP` with old=3.2.0, new=5.0.0.
3. `applicability.py`: `resolved[0] (3) != new[0] (5)` → `APPLIES` with "major drift... requires human review".
4. `matching.py`: `DEPENDENCY_VERSION_BUMP` → `ACTIONABLE`.
5. `dependency_drift_policy`: `major_gap=2 > 1` → `"declined"` (scope="one-major").
6. `drift_summary.py`: `"major-gap review"`.

**Result:** Assessment is `ACTIONABLE` but policy declines the plan. The drift is reported but no PR artifact is generated. The `ACTIONABLE` status in matching and the `declined` policy are not contradictory — `ACTIONABLE` means "the version evidence says this repo is affected"; `declined` means "the policy says don't auto-fix this distance". ✓

---

## 6. Test Coverage

### What is tested:

| Test | File | Lines | Coverage |
|---|---|---|---|
| `drift_risk` returns "patch-minor", "major", "multi-major" | `tests/unit/test_detections.py:60-64` | 4 cases | ✓ |
| `test_major_gap_is_report_only_even_when_feed_is_newer` | `tests/unit/test_drift_summary.py:30-38` | drift_summary._decision | ✓ |
| `test_actionable_same_major_drift_is_distinguished` | `tests/unit/test_drift_summary.py:41-48` | same-major actionable | ✓ |
| `test_unresolved_catalog_reference_is_not_compared_as_semver` | `tests/unit/test_drift_summary.py:51-57` | catalog: range edge case | ✓ |
| `test_major_drift_is_a_human_review_candidate` | `tests/unit/test_applicability.py:23-30` | applicability major drift | ✓ |
| `test_missing_version_evidence_does_not_hide_call_sites` | `tests/unit/test_applicability.py:33-38` | null version → UNKNOWN | ✓ |
| `test_minor_dependency_drift_preserves_the_npm_range_operator` | `tests/unit/test_pipeline_preverify_manifest.py:83-103` | minor drift → automatic | ✓ |
| `test_major_dependency_drift_becomes_a_draft_review_candidate` | `tests/unit/test_pipeline_preverify_manifest.py:106-125` | major drift → review_pr | ✓ |
| `test_major_review_preserves_an_exact_manifest_pin` | `tests/unit/test_pipeline_preverify_manifest.py:128+` | pin preservation | ✓ |

### What is NOT tested:

| Gap | Description | Risk |
|---|---|---|
| `drift_risk` patch vs minor | No test distinguishes `1.2.0→1.2.1` (patch) from `1.2.0→1.3.0` (minor). Both return `"patch-minor"`. | LOW (same policy applies to both today) |
| `dependency_drift_policy` with `scope="any-minor"` | No test for the `any-minor` scope that blocks all major drifts. | MEDIUM — if scope="any-minor" is misconfigured, all major drifts silently become declined |
| `dependency_drift_policy` with `scope="any"` | No test for the `--anyversion` path. | LOW |
| `dependency_drift_policy` with `max_minor_gap` set | No test verifies that a same-major drift exceeding `max_minor_gap` becomes `review_pr`. | MEDIUM — `max_minor_gap` is documented but has zero test coverage |
| Multi-major drift → `declined` end-to-end | No test verifies that a 3→5 drift produces no plan artifact. | MEDIUM — multi-major gap can silently pass through if `scope` is misread |
| Non-semver version (e.g. `"2024-10-01"` Stripe dated format) | `parse_semver` returns `None` for dated versions. No test verifies this produces `"version unresolved"` rather than matching incorrectly. | HIGH for Stripe and providers with non-semver versioning |
| Python/Ruby ecosystem drift policy | `dependency_drift_policy` is called for JavaScript. Python (requirements.txt) and Ruby (Gemfile) drift follows a different code path in `fix_service.py:379+` but `dependency_drift_policy` is also called for them. Tests only cover JavaScript manifests. | HIGH — Python/Ruby drift detection is undertested |
| `drift_summary._decision` for "same-major drift" without ACTIONABLE | No test for the `"same-major drift"` (non-actionable) label. | LOW (display only) |

---

## 7. Gaps Where Drift Would Be Missed or Misclassified

### Gap 1: Non-semver versions silently become "version unresolved" (HIGH)
**File:** `src/depfix/sources/semver.py:14`  
`parse_semver()` returns `None` for Stripe-style dated versions like `"2024-10-01"` or pre-release tags like `"2.0.0-beta.1"`. When `parse_semver` returns `None`, `drift_summary._decision` returns `"version unresolved"` and no plan is generated. Similarly, `is_major_bump` returns `False` (line 31: `if o is None or n is None: return False`).

**Effect:** Any provider that uses non-semver versioning (Stripe, Kubernetes, some AWS SDKs) will never produce a drift plan regardless of how far the version has advanced. The drift is silently invisible.

**Evidence:** `drift_risk("2024-10-01", "2025-01-15")` → `""` (empty string, treated as not a forward move).

### Gap 2: `drift_summary._decision` uses highest feed version, not installed version (LOW-MEDIUM)
**File:** `src/depfix/scanners/drift_summary.py:84`
```python
if current_semver[0] != feed_semver[0]:
    return "major-gap review"
```
`feed_semver` is the **highest** version from all feed records (`_highest_feed_version`), not the version in the specific change that triggered ACTIONABLE. A repo at v3.5.0 with a SAME-MAJOR actionable change to v3.8.0, plus an unrelated multi-major feed record at v7.0.0, would show `"major-gap review"` (comparing against v7) even though the actionable change is same-major.

**Effect:** The display label can be misleadingly alarming. The plan itself is still correct — plans are generated per-change, not per-summary row. But operators reading the drift summary may see "major-gap review" for a same-major actionable change.

### Gap 3: `max_minor_gap` config has no test coverage (MEDIUM)
**File:** `src/depfix/codemods/lockfile.py:161`  
`max_minor_gap` can downgrade a large same-major drift to `review_pr`. This is a documented feature (config.py:121-126) with zero test coverage. If misconfigured (e.g. set to 0), every same-major drift becomes a review PR, which would silence the "automatic" category entirely.

### Gap 4: Python/Ruby drift tested only indirectly (HIGH)
Python drift detection (`requirements.txt`, `pyproject.toml`) and Ruby drift (`Gemfile`) go through different manifest-reading code paths than JavaScript (`package.json`). The `dependency_drift_policy` function is called for all ecosystems, but the tests only exercise the JavaScript path. A Python repo might have a different version in `requirements.txt` vs what `pip freeze` shows, and the non-lockfile path in `applicability.py:69-93` (range-only fallback) is barely tested.

### Gap 5: `in_upgrade_window` edge cases untested (LOW)
**File:** `src/depfix/sources/semver.py:35-47`  
`in_upgrade_window(migration_version, installed, target)` is used in `upgrade.py:142` to place API migration changes in a version window. Tests in `test_detections.py` cover `drift_risk` but not `in_upgrade_window`. Edge case: if `migration_version` equals `installed` exactly, `in_upgrade_window` returns `None` (can't place), and the migration falls into `unplaceable`. No test covers this.

---

## 8. Summary

| Category | Status |
|---|---|
| Same-major minor/patch drift detection | ✓ Working, tested |
| Exactly-one-major drift detection | ✓ Working, tested (produces review_pr) |
| Multi-major drift declination | ✓ Working, partially tested |
| `drift_risk` classification (3 tiers) | ✓ Working, tested |
| `dependency_drift_policy` scope gates | ✓ Working, minimal testing |
| `max_minor_gap` policy gate | ✓ Code exists, **zero tests** |
| `scope="any-minor"` / `scope="any"` | ✓ Code exists, **zero tests** |
| Non-semver versions (Stripe, dated) | ⚠️ Silently "version unresolved" — no plan generated |
| Python/Ruby ecosystem drift | ⚠️ Policy function used but ecosystem path untested |
| Display label vs plan alignment | ⚠️ "major-gap review" label for N→N+1 even though plan is generated |

---

*Key source files for version drift detection:*
- `src/depfix/sources/semver.py` — `drift_risk`, `is_major_bump`, `parse_semver`, `in_upgrade_window`
- `src/depfix/codemods/lockfile.py:122-163` — `dependency_drift_policy` (the policy gate)
- `src/depfix/scanners/applicability.py:43-97` — `change_applies` (repo version check)
- `src/depfix/scanners/matching.py:62-67` — ACTIONABLE short-circuit for DEPENDENCY_VERSION_BUMP
- `src/depfix/scanners/drift_summary.py` — display labels (not plan decisions)
- `src/depfix/catalog/detections.py:88` — `drift_risk` stored in learned_migrations.yaml
- `src/depfix/config.py:115-136` — `drift_max_major_gap`, `drift_max_minor_gap`, `drift_scope` config

*Tests:*
- `tests/unit/test_drift_summary.py` — 3 cases for display summary
- `tests/unit/test_applicability.py` — 2 cases for applicability
- `tests/unit/test_detections.py:60-64` — 4 cases for `drift_risk`
- `tests/unit/test_pipeline_preverify_manifest.py:83-125` — 3 cases for `dependency_drift_policy`
