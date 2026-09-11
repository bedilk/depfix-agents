"""Week 4 fix pipeline: wires the Week 3 scanner's output to the
apply/verify subsystems.

Where :class:`depfix.core.agent.DependencyFixAgent` (Week 1/2) scans a
codebase with a regex pattern and generates fixes in memory,
:class:`FixPipeline` starts from a :class:`~depfix.scanners.models.RepoScanResult`
(the binding-aware call-site scanner's output), writes each candidate fix
in place via :class:`~depfix.apply.workspace.WorkspaceEditor` -- so it's a
real, revertible edit on disk, not just a diff -- and optionally confirms
it against the repo's own test suite via :class:`~depfix.verify.verifier.Verifier`.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from depfix.apply.models import EditVerdict, FileEdit
from depfix.apply.workspace import WorkspaceEditor
from depfix.core.models import BreakingChange, FileUsage
from depfix.fixers.gemini import FixGenerator
from depfix.fixers.ollama import OllamaFixGenerator
from depfix.retry.loop import RetryLoop
from depfix.scanners.models import RepoScanResult
from depfix.validators.javascript import FixValidator
from depfix.verify.verifier import VerificationReport, Verifier

logger = logging.getLogger(__name__)


@dataclass
class FixPipelineResult:
    """Everything produced by one :meth:`FixPipeline.run` call."""

    repo_full_name: str
    breaking_change: BreakingChange
    files_scanned: int
    files_affected: int
    edits: tuple[FileEdit, ...]
    total_usages_fixed: int
    total_cost: float
    total_tokens: int
    duration_ms: int
    verification: VerificationReport | None = None

    @property
    def applied_edits(self) -> list[FileEdit]:
        """Edits whose fixed content is (as far as we know) on disk right
        now -- APPLIED, KEPT, or SUSPECT. See :attr:`FileEdit.is_on_disk`."""
        return [e for e in self.edits if e.is_on_disk]

    @property
    def reverted_edits(self) -> list[FileEdit]:
        return [e for e in self.edits if e.verdict == EditVerdict.REVERTED]

    @property
    def suspect_edits(self) -> list[FileEdit]:
        return [e for e in self.edits if e.verdict == EditVerdict.SUSPECT]


class FixPipeline:
    """Generates and applies fixes for every actionable call site in a
    :class:`RepoScanResult`, against a checkout already opened by ``editor``.

    Not safe to share across threads or reuse across unrelated scans/repos
    for the same reason :class:`WorkspaceEditor` isn't: both track
    per-instance state (a fixer's running cost/token totals, an editor's
    original-bytes cache) scoped to one run.
    """

    def __init__(
        self,
        fixer: FixGenerator | OllamaFixGenerator,
        *,
        validator: FixValidator | None = None,
        verifier: Verifier | None = None,
        retry_loop: RetryLoop | None = None,
    ) -> None:
        self._fixer = fixer
        self._validator = validator or FixValidator()
        self._verifier = verifier
        self._retry_loop = retry_loop

    def run(
        self,
        scan_result: RepoScanResult,
        breaking_change: BreakingChange,
        editor: WorkspaceEditor,
    ) -> FixPipelineResult:
        """Fix every actionable call site ``scan_result`` found, write each
        fix via ``editor``, and -- if this pipeline was built with a
        ``verifier`` -- run the repo's own test suite to settle each edit's
        final verdict.
        """
        start = time.time()
        file_usages = scan_result.to_file_usages(editor.checkout.path)

        edits = [self._fix_one(file_usage, breaking_change, editor) for file_usage in file_usages]

        verification: VerificationReport | None = None
        if self._verifier is not None:
            verification = self._verifier.verify(edits)
            edits = list(verification.edits)

            if self._retry_loop is not None:
                file_usages_by_relpath = {fu.filepath: fu for fu in file_usages}
                edits, verification, rounds_used = self._retry_loop.run(
                    edits, verification, file_usages_by_relpath, breaking_change, editor
                )
                if rounds_used:
                    logger.info(
                        "retry loop used %d round(s) for %s", rounds_used, scan_result.repo_full_name
                    )

        total_usages_fixed = sum(e.usages_fixed for e in edits if e.is_on_disk)

        return FixPipelineResult(
            repo_full_name=scan_result.repo_full_name,
            breaking_change=breaking_change,
            files_scanned=scan_result.files_scanned,
            files_affected=len(file_usages),
            edits=tuple(edits),
            total_usages_fixed=total_usages_fixed,
            total_cost=self._fixer.total_cost,
            total_tokens=self._fixer.total_tokens,
            duration_ms=int((time.time() - start) * 1000),
            verification=verification,
        )

    def _fix_one(
        self, file_usage: FileUsage, breaking_change: BreakingChange, editor: WorkspaceEditor
    ) -> FileEdit:
        """Generate + validate + write one file's fix.

        A generation failure (LLM error, exhausted retries) produces a
        SKIPPED edit rather than propagating -- one bad file must not abort
        fixing the rest of the batch. A *validation* failure, by contrast,
        still gets written to disk as SUSPECT: see
        :class:`depfix.apply.models.EditVerdict`'s docstring for why an
        unconfirmed fix is kept and flagged rather than silently dropped.
        """
        try:
            fixed_code, confidence, _llm_call = self._fixer.generate_fix(
                file_usage, breaking_change
            )
        except Exception as exc:  # noqa: BLE001 - a third-party LLM client's failure modes aren't ours to enumerate
            logger.error("fix generation failed for %s: %s", file_usage.filepath, exc)
            return FileEdit(
                relpath=file_usage.filepath,
                original_content=file_usage.file_content,
                fixed_content=file_usage.file_content,
                diff="",
                verdict=EditVerdict.SKIPPED,
                error_message=f"fix generation failed: {exc}",
            )

        validation = self._validator.validate(
            file_usage.file_content, fixed_code, file_usage.filepath
        )
        usages_fixed = file_usage.usage_count if validation.is_valid else 0

        return editor.write_fix(
            file_usage.filepath,
            fixed_code,
            confidence=confidence,
            usages_fixed=usages_fixed,
            validation=validation,
        )
