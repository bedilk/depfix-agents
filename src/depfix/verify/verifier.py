"""Orchestrates test-based verification of candidate fixes.

The core comparison is baseline-vs-after-fix by test *identity*, not by
pass/fail count -- a repo with 3 pre-existing failing tests and a fix that
introduces a 4th distinct failure must not be reported as "still 3
failures, looks fine" just because some other flaky test happened to start
passing in the same run. See :class:`depfix.verify.models.TestRunResult`.
"""

from __future__ import annotations

import dataclasses
import logging

from depfix.apply.models import EditVerdict, FileEdit
from depfix.apply.workspace import WorkspaceEditor
from depfix.verify.attribution import AttributionResult, attribute_failures
from depfix.verify.manager import InstallResult, install_dependencies
from depfix.verify.models import TestRunResult
from depfix.verify.runner import has_test_script, run_tests
from depfix.verify.sandbox import DEFAULT_MAX_OUTPUT_BYTES

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class VerificationReport:
    """Outcome of one :meth:`Verifier.verify` call."""

    ran: bool
    skipped_reason: str = ""
    install: InstallResult | None = None
    baseline: TestRunResult | None = None
    after_fix: TestRunResult | None = None
    edits: tuple[FileEdit, ...] = ()
    attribution: AttributionResult | None = None

    @property
    def new_failure_count(self) -> int:
        if self.baseline is None or self.after_fix is None:
            return 0
        return len(self.after_fix.failed_identities - self.baseline.failed_identities)


class Verifier:
    """Runs a checkout's real test suite before/after a batch of candidate
    fixes to decide, per file, whether to keep or revert it.

    Not safe to share across threads or reuse across unrelated fix
    batches -- it drives ``editor`` (see :class:`WorkspaceEditor`)'s
    revert/reapply cycle directly and assumes exclusive ownership of the
    checkout for the duration of :meth:`verify`.
    """

    def __init__(
        self,
        editor: WorkspaceEditor,
        *,
        install_timeout: float = 300.0,
        test_timeout: float = 300.0,
        ignore_scripts: bool = True,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    ) -> None:
        self._editor = editor
        self._install_timeout = install_timeout
        self._test_timeout = test_timeout
        self._ignore_scripts = ignore_scripts
        self._max_output_bytes = max_output_bytes

    def verify(self, edits: list[FileEdit]) -> VerificationReport:
        """Run baseline and after-fix test suites and settle each on-disk
        edit's verdict to :attr:`EditVerdict.KEPT`, :attr:`EditVerdict.REVERTED`,
        or :attr:`EditVerdict.SUSPECT`.

        Edits not currently on disk (``SKIPPED``/already ``REVERTED``) pass
        through unchanged -- there's nothing on the filesystem for a test
        run to confirm or deny about them.
        """
        on_disk = [e for e in edits if e.is_on_disk]
        if not on_disk:
            return VerificationReport(ran=False, skipped_reason="no on-disk edits to verify", edits=tuple(edits))

        root = self._editor.checkout.path

        if not has_test_script(root):
            settled = tuple(self._mark_suspect(e) for e in edits)
            return VerificationReport(ran=False, skipped_reason="repo has no test script", edits=settled)

        install = install_dependencies(
            root,
            timeout=self._install_timeout,
            ignore_scripts=self._ignore_scripts,
            max_output_bytes=self._max_output_bytes,
        )
        if not install.ok:
            settled = tuple(self._mark_suspect(e) for e in edits)
            reason = install.skipped_reason or "dependency install failed"
            return VerificationReport(ran=False, skipped_reason=reason, install=install, edits=settled)

        touched_relpaths = tuple(e.relpath for e in on_disk)

        for relpath in touched_relpaths:
            self._editor.revert(relpath)
        baseline = run_tests(
            root,
            timeout=self._test_timeout,
            package_manager=install.package_manager,
            max_output_bytes=self._max_output_bytes,
        )

        edit_by_relpath = {e.relpath: e for e in on_disk}
        for relpath in touched_relpaths:
            self._editor.write_fix(relpath, edit_by_relpath[relpath].fixed_content)
        after_fix = run_tests(
            root,
            timeout=self._test_timeout,
            package_manager=install.package_manager,
            max_output_bytes=self._max_output_bytes,
        )

        if baseline.crashed or after_fix.crashed:
            settled = tuple(self._mark_suspect(e) for e in edits)
            return VerificationReport(
                ran=True,
                skipped_reason="baseline or after-fix run crashed",
                install=install,
                baseline=baseline,
                after_fix=after_fix,
                edits=settled,
            )

        if baseline.used_fallback_parser or after_fix.used_fallback_parser:
            # Aggregate-count-only comparisons can't reliably tell "same
            # failures" from "different failures with the same count" --
            # see parse_fallback's docstring. Don't trust it to decide
            # which file broke; leave everything on disk but unconfirmed.
            settled = tuple(self._mark_suspect(e) for e in edits)
            return VerificationReport(
                ran=True, install=install, baseline=baseline, after_fix=after_fix, edits=settled
            )

        new_failure_identities = after_fix.failed_identities - baseline.failed_identities
        new_failures = [c for c in after_fix.failed_cases if c.identity in new_failure_identities]

        if not new_failures:
            settled = tuple(self._settle(e, EditVerdict.KEPT) for e in edits)
            return VerificationReport(
                ran=True, install=install, baseline=baseline, after_fix=after_fix, edits=settled
            )

        attribution = attribute_failures(
            new_failures, touched_relpaths=touched_relpaths, checkout_root=root
        )

        settled_edits: list[FileEdit] = []
        for edit in edits:
            if not edit.is_on_disk:
                settled_edits.append(edit)
                continue
            if edit.relpath in attribution.by_file:
                self._editor.revert(edit.relpath)
                settled_edits.append(self._settle(edit, EditVerdict.REVERTED))
            elif attribution.unattributed:
                # Some new failure exists that we can't pin on any specific
                # file -- don't clear *this* edit as confirmed-clean while
                # that ambiguity is unresolved.
                settled_edits.append(self._settle(edit, EditVerdict.SUSPECT))
            else:
                settled_edits.append(self._settle(edit, EditVerdict.KEPT))

        return VerificationReport(
            ran=True,
            install=install,
            baseline=baseline,
            after_fix=after_fix,
            edits=tuple(settled_edits),
            attribution=attribution,
        )

    @staticmethod
    def _mark_suspect(edit: FileEdit) -> FileEdit:
        if not edit.is_on_disk:
            return edit
        return Verifier._settle(edit, EditVerdict.SUSPECT)

    @staticmethod
    def _settle(edit: FileEdit, verdict: EditVerdict) -> FileEdit:
        return dataclasses.replace(edit, verdict=verdict)
