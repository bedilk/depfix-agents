"""Executes eval cases against the real classify/fixer pipeline.

Deliberately bypasses ``DependencyFixAgent`` for the ``fix_generation``
category and calls ``FixGenerator``/``FixValidator`` directly: the agent
orchestrates a whole-codebase run (scan -> fix every file -> write diffs),
whereas an eval case is "does this one fixture file get fixed correctly" —
the agent's file-discovery and diff-writing steps would just be overhead and
extra failure surface unrelated to what's being scored.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

from depfix.classify.llm import LLMCompleter
from depfix.classify.notes import NotesClassifier
from depfix.classify.spec_rules import classify_spec_changes
from depfix.core.models import BreakingChange, ChangeKind, ClassificationSource
from depfix.evals.models import CaseResult, EvalCase, EvalCategory, EvalReport
from depfix.evals.scoring import score_classification, score_fix
from depfix.scanners.base import CodebaseScanner, build_pattern_for_api
from depfix.sources.openapi_diff import diff_specs
from depfix.validators.javascript import FixValidator

logger = logging.getLogger(__name__)


class FixGeneratorLike(Protocol):
    def generate_fix(self, file_usage: Any, breaking_change: BreakingChange) -> Any: ...


def _breaking_change_from_dict(data: dict[str, Any]) -> BreakingChange:
    payload = dict(data)
    if "kind" in payload:
        payload["kind"] = ChangeKind(payload["kind"])
    if "source" in payload:
        payload["source"] = ClassificationSource(payload["source"])
    return BreakingChange(**payload)


class EvalRunner:
    def __init__(
        self,
        *,
        completer: LLMCompleter | None = None,
        fixer: FixGeneratorLike | None = None,
        fixtures_dir: Path | None = None,
    ) -> None:
        self._completer = completer
        self._fixer = fixer
        self._fixtures_dir = fixtures_dir or (
            Path(__file__).resolve().parents[3] / "tests" / "fixtures"
        )
        self._scanner = CodebaseScanner(context_lines=5)
        self._validator = FixValidator()

    def run(self, cases: list[EvalCase], *, use_llm: bool) -> EvalReport:
        report = EvalReport()
        for case in cases:
            if case.requires_llm and not use_llm:
                report.cases.append(
                    CaseResult(
                        case_id=case.id,
                        category=case.category,
                        passed=False,
                        verified=case.verified,
                        detail="skipped: requires an LLM and --no-llm was set",
                        skipped=True,
                    )
                )
                continue
            report.cases.append(self._run_case(case))
        return report

    def _run_case(self, case: EvalCase) -> CaseResult:
        try:
            if case.category is EvalCategory.SPEC_DIFF:
                return self._run_spec_diff(case)
            if case.category is EvalCategory.RELEASE_NOTES:
                return self._run_release_notes(case)
            if case.category is EvalCategory.FIX_GENERATION:
                return self._run_fix(case)
        except Exception as exc:
            logger.exception("eval case %s raised", case.id)
            return CaseResult(
                case_id=case.id,
                category=case.category,
                passed=False,
                verified=case.verified,
                detail=f"raised {type(exc).__name__}: {exc}",
            )
        raise AssertionError(f"unhandled eval category: {case.category}")  # pragma: no cover

    def _run_spec_diff(self, case: EvalCase) -> CaseResult:
        changes = diff_specs(case.old_spec or {}, case.new_spec or {})
        actual = classify_spec_changes(
            changes,
            package=case.package,
            old_version=case.old_version,
            new_version=case.new_version,
            provider_id=case.package,
            source_url=None,
        )
        passed, detail = score_classification(case.expected_changes, actual)
        return CaseResult(case.id, case.category, passed, case.verified, detail)

    def _run_release_notes(self, case: EvalCase) -> CaseResult:
        if self._completer is None:
            return CaseResult(
                case.id, case.category, False, case.verified, "no LLM completer configured"
            )
        classifier = NotesClassifier(self._completer)
        actual = classifier.classify(
            case.release_notes_body,
            package=case.package,
            old_version=case.old_version,
            new_version=case.new_version,
            provider_id=case.package,
        )
        passed, detail = score_classification(case.expected_changes, actual)
        return CaseResult(case.id, case.category, passed, case.verified, detail)

    def _run_fix(self, case: EvalCase) -> CaseResult:
        if self._fixer is None:
            return CaseResult(case.id, case.category, False, case.verified, "no fixer configured")
        if not case.breaking_change or not case.fixture or not case.target_file:
            return CaseResult(
                case.id,
                case.category,
                False,
                case.verified,
                "case is missing breaking_change/fixture/target_file",
            )

        change = _breaking_change_from_dict(case.breaking_change)
        fixture_dir = self._fixtures_dir / case.fixture
        target_path = fixture_dir / case.target_file
        if not target_path.exists():
            return CaseResult(
                case.id, case.category, False, case.verified, f"fixture not found: {target_path}"
            )

        patterns = build_pattern_for_api(change.old_api, change.package)
        file_usages = self._scanner.scan_codebase(str(fixture_dir), patterns)
        file_usage = next(
            (fu for fu in file_usages if fu.filepath.endswith(case.target_file)), None
        )
        if file_usage is None:
            return CaseResult(
                case.id,
                case.category,
                False,
                case.verified,
                "scanner found no usages of old_api in target_file",
            )

        fixed_code, _confidence, llm_call = self._fixer.generate_fix(file_usage, change)
        validation = self._validator.validate(
            file_usage.file_content, fixed_code, file_usage.filepath
        )
        cost = llm_call.cost_estimate

        if not validation.is_valid:
            return CaseResult(
                case.id,
                case.category,
                False,
                case.verified,
                f"validation failed: {validation.error_message}",
                cost=cost,
            )

        if case.fix_assertion is None:
            return CaseResult(
                case.id, case.category, True, case.verified, "no fix assertions", cost=cost
            )

        passed, detail = score_fix(case.fix_assertion, file_usage.file_content, fixed_code)
        return CaseResult(case.id, case.category, passed, case.verified, detail, cost=cost)


def save_report(report: EvalReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [{**asdict(c), "category": c.category.value} for c in report.cases]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_report(path: Path) -> EvalReport:
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases = [
        CaseResult(
            case_id=item["case_id"],
            category=EvalCategory(item["category"]),
            passed=item["passed"],
            verified=item["verified"],
            detail=item.get("detail", ""),
            cost=item.get("cost", 0.0),
            skipped=item.get("skipped", False),
        )
        for item in raw
    ]
    return EvalReport(cases=cases)
