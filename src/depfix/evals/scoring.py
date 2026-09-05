"""Scoring functions — pure, no I/O, so they're trivially unit-testable."""

from __future__ import annotations

from dataclasses import dataclass

from depfix.core.models import BreakingChange
from depfix.evals.models import EvalReport, ExpectedChange, FixAssertion


def score_classification(
    expected: list[ExpectedChange], actual: list[BreakingChange]
) -> tuple[bool, str]:
    """Greedy one-to-one match: each expected change consumes at most one
    actual change, so a classifier that returns the same change five times
    cannot make five expectations pass."""
    if not expected:
        return True, "no expected changes"

    remaining = list(actual)
    misses: list[str] = []
    for exp in expected:
        match = next(
            (
                a
                for a in remaining
                if a.kind.value == exp.kind
                and exp.old_api_contains.lower() in a.old_api.lower()
                and a.confidence >= exp.min_confidence
            ),
            None,
        )
        if match is None:
            misses.append(f"kind={exp.kind!r} old_api~={exp.old_api_contains!r}")
        else:
            remaining.remove(match)

    if misses:
        return False, "unmatched expectations: " + "; ".join(misses)
    return True, f"matched {len(expected)}/{len(expected)} expected change(s)"


def score_fix(assertion: FixAssertion, original: str, fixed: str) -> tuple[bool, str]:
    """Property-based check on generated-fix output rather than exact-match,
    which measures formatting luck, not whether the migration is correct."""
    for needle in assertion.must_contain:
        if needle not in fixed:
            return False, f"missing required substring: {needle!r}"
    for needle in assertion.must_not_contain:
        if needle in fixed:
            return False, f"contains forbidden substring: {needle!r}"

    if assertion.max_changed_line_ratio is not None:
        orig_lines = set(original.splitlines())
        fixed_lines = set(fixed.splitlines())
        changed = len(orig_lines.symmetric_difference(fixed_lines))
        denom = max(len(original.splitlines()), 1)
        ratio = changed / denom
        if ratio > assertion.max_changed_line_ratio:
            return False, (
                f"changed-line ratio {ratio:.2f} exceeds max {assertion.max_changed_line_ratio:.2f}"
            )

    return True, "fix assertions satisfied"


@dataclass(frozen=True)
class Regression:
    case_id: str
    was_passing: bool
    now_passing: bool


def compare_reports(baseline: EvalReport, candidate: EvalReport) -> list[Regression]:
    """Per-case regressions — an *improved* aggregate pass rate can still
    hide one specific case that flipped from pass to fail. Only that
    direction is reported; a fail -> pass flip is never a regression."""
    baseline_by_id = {c.case_id: c.passed for c in baseline.scored_cases}
    regressions: list[Regression] = []
    for case in candidate.scored_cases:
        was = baseline_by_id.get(case.case_id)
        if was is True and not case.passed:
            regressions.append(
                Regression(case_id=case.case_id, was_passing=True, now_passing=False)
            )
    return regressions
