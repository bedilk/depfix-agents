

"""Orchestrates evidence-based verification of candidate fixes.

The core comparison is baseline-vs-after-fix by test *identity*, not by
pass/fail count -- a repo with 3 pre-existing failing tests and a fix that
introduces a 4th distinct failure must not be reported as "still 3
failures, looks fine" just because some other flaky test happened to start
passing in the same run. See :class:`depfix.verify.models.TestRunResult`.

Week 7: the test suite is no longer the *only* oracle. Every path that used
to dead-end at "mark everything SUSPECT" -- no test script, install
failure, unparseable reporter output, crashed run -- now falls through to
:mod:`depfix.verify.typecheck`, which applies the identical
baseline-vs-after discipline to ``tsc --noEmit`` diagnostics. Each terminal
path records which oracle actually decided, as a
:class:`depfix.verify.confidence.ConfidenceTier`, so a caller can open a
draft PR for weak evidence instead of throwing the fix away.

``skipped_reason`` keeps its original meaning throughout: *why the repo's
own tests did not decide*. It is not overwritten by typecheck outcomes --
those live in ``typecheck_baseline``/``typecheck_after``.
"""

from __future__ import annotations

import dataclasses
import logging

from depfix.apply.models import EditVerdict, FileEdit
from depfix.apply.workspace import WorkspaceEditor
from depfix.core.models import BreakingChange
from depfix.verify.attribution import AttributionResult, attribute_failures
from depfix.verify.characterize import CharacterizationReport, Characterizer
from depfix.verify.confidence import ConfidenceTier
from depfix.verify.manager import InstallResult, install_dependencies
from depfix.verify.models import TestRunResult
from depfix.verify.runner import has_test_script, run_tests
from depfix.verify.sandbox import DEFAULT_MAX_OUTPUT_BYTES
from depfix.verify.typecheck import TypecheckResult, new_diagnostics, run_typecheck

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class VerificationReport:
    """Outcome of one :meth:`Verifier.verify` call."""

    ran: bool
    #: Why the *repo's own test suite* did not settle the verdicts. Empty
    #: when tests ran and were trusted. Never carries typecheck detail --
    #: see ``typecheck_after``.
    skipped_reason: str = ""
    install: InstallResult | None = None
    baseline: TestRunResult | None = None
    after_fix: TestRunResult | None = None
    edits: tuple[FileEdit, ...] = ()
    attribution: AttributionResult | None = None
    typecheck_baseline: TypecheckResult | None = None
    typecheck_after: TypecheckResult | None = None
    #: Which oracle actually decided these verdicts.
    tier: ConfidenceTier = ConfidenceTier.NONE
    #: One line naming that oracle, for the PR body and CLI.
    tier_reason: str = ""
    characterization: CharacterizationReport | None = None

    @property
    def new_failure_count(self) -> int:
        if self.baseline is None or self.after_fix is None:
            return 0
        return len(self.after_fix.failed_identities - self.baseline.failed_identities)

    @property
    def typechecked(self) -> bool:
        return self.typecheck_after is not None and self.typecheck_after.usable

    @property
    def new_diagnostics(self) -> tuple:
        if self.typecheck_baseline is None or self.typecheck_after is None:
            return ()
        return new_diagnostics(self.typecheck_baseline, self.typecheck_after)


class Verifier:
    """Runs a checkout's real test suite -- and, when that can't decide, its
    typechecker -- before/after a batch of candidate fixes, to settle each
    file's verdict.

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
        typecheck_enabled: bool = True,
        typecheck_timeout: float = 300.0,
        characterizer: Characterizer | None = None,
    ) -> None:
        self._editor = editor
        self._install_timeout = install_timeout
        self._test_timeout = test_timeout
        self._ignore_scripts = ignore_scripts
        self._max_output_bytes = max_output_bytes
        self._typecheck_enabled = typecheck_enabled
        self._typecheck_timeout = typecheck_timeout
        self._characterizer = characterizer
        self._change: BreakingChange | None = None

    def verify(
        self, edits: list[FileEdit], *, change: BreakingChange | None = None
    ) -> VerificationReport:
        """Settle each on-disk edit to KEPT / REVERTED / SUSPECT, using the
        strongest oracle that can actually reach a verdict.

        Edits not currently on disk (``SKIPPED``/already ``REVERTED``) pass
        through unchanged -- there's nothing on the filesystem for any
        oracle to confirm or deny about them.
        """
        self._change = change
        on_disk = [e for e in edits if e.is_on_disk]
        if not on_disk:
            return VerificationReport(
                ran=False,
                skipped_reason="no on-disk edits to verify",
                edits=tuple(edits),
                tier=ConfidenceTier.NONE,
                tier_reason="no edits were written to disk",
            )

        root = self._editor.checkout.path

        if not has_test_script(root):
            return self._decide_without_tests(
                edits, on_disk, ran=False, skipped_reason="repo has no test script"
            )

        install = install_dependencies(
            root,
            timeout=self._install_timeout,
            ignore_scripts=self._ignore_scripts,
            max_output_bytes=self._max_output_bytes,
        )
        if not install.ok:
            return self._decide_without_tests(
                edits,
                on_disk,
                ran=False,
                skipped_reason=install.skipped_reason or "dependency install failed",
                install=install,
            )

        touched_relpaths = tuple(e.relpath for e in on_disk)
        edit_by_relpath = {e.relpath: e for e in on_disk}

        baseline = self._run_tests_on_baseline(touched_relpaths, install.package_manager)
        after_fix = self._run_tests_on_fixed(
            touched_relpaths, edit_by_relpath, install.package_manager
        )

        if baseline.crashed or after_fix.crashed:
            return self._decide_without_tests(
                edits,
                on_disk,
                ran=True,
                skipped_reason="baseline or after-fix run crashed",
                install=install,
                baseline=baseline,
                after_fix=after_fix,
            )

        if baseline.used_fallback_parser or after_fix.used_fallback_parser:
            # Aggregate-count-only comparisons can't reliably tell "same
            # failures" from "different failures with the same count" --
            # see parse_fallback's docstring. Don't trust it to decide
            # which file broke; try the typechecker instead.
            return self._decide_without_tests(
                edits,
                on_disk,
                ran=True,
                skipped_reason="",
                install=install,
                baseline=baseline,
                after_fix=after_fix,
            )

        new_failure_identities = after_fix.failed_identities - baseline.failed_identities
        new_failures = [c for c in after_fix.failed_cases if c.identity in new_failure_identities]

        if not new_failures:
            settled = tuple(self._settle(e, EditVerdict.KEPT) for e in edits)
            return VerificationReport(
                ran=True,
                install=install,
                baseline=baseline,
                after_fix=after_fix,
                edits=settled,
                tier=ConfidenceTier.HIGH,
                tier_reason="the repository's own test suite introduced no new failures",
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

        decided_cleanly = all(
            e.verdict != EditVerdict.SUSPECT for e in settled_edits if e.is_on_disk
        )
        return VerificationReport(
            ran=True,
            install=install,
            baseline=baseline,
            after_fix=after_fix,
            edits=tuple(settled_edits),
            attribution=attribution,
            tier=ConfidenceTier.HIGH if decided_cleanly else ConfidenceTier.LOW,
            tier_reason=(
                "the repository's own test suite attributed every new failure to a specific file"
                if decided_cleanly
                else "new test failures could not be attributed to a specific file"
            ),
        )

    # -- test-oracle plumbing --------------------------------------------------

    def _run_tests_on_baseline(
        self, touched_relpaths: tuple[str, ...], package_manager: str
    ) -> TestRunResult:
        for relpath in touched_relpaths:
            self._editor.revert(relpath)
        return run_tests(
            self._editor.checkout.path,
            timeout=self._test_timeout,
            package_manager=package_manager,
            max_output_bytes=self._max_output_bytes,
        )

    def _run_tests_on_fixed(
        self,
        touched_relpaths: tuple[str, ...],
        edit_by_relpath: dict[str, FileEdit],
        package_manager: str,
    ) -> TestRunResult:
        for relpath in touched_relpaths:
            self._editor.write_fix(relpath, edit_by_relpath[relpath].fixed_content)
        return run_tests(
            self._editor.checkout.path,
            timeout=self._test_timeout,
            package_manager=package_manager,
            max_output_bytes=self._max_output_bytes,
        )

    # -- typecheck fallback ----------------------------------------------------

    def _decide_without_tests(
        self,
        edits: list[FileEdit],
        on_disk: list[FileEdit],
        *,
        ran: bool,
        skipped_reason: str,
        install: InstallResult | None = None,
        baseline: TestRunResult | None = None,
        after_fix: TestRunResult | None = None,
    ) -> VerificationReport:
        """The tests didn't decide. Try the typechecker; failing that, leave
        every on-disk edit SUSPECT exactly as before.

        ``skipped_reason`` is passed through untouched -- it explains the
        *test* outcome, and a caller (or a test asserting on it) must not
        see it mutate just because a typecheck was attempted afterwards.
        """
        root = self._editor.checkout.path

        def suspect(
            tier_reason: str,
            *,
            resolved_install: InstallResult | None,
            tc_baseline: TypecheckResult | None = None,
            tc_after: TypecheckResult | None = None,
        ) -> VerificationReport:
            characterization = self._characterize_when_available(on_disk, resolved_install)
            settled = tuple(self._mark_suspect(e) for e in edits)
            tier = ConfidenceTier.LOW
            reason = tier_reason
            if characterization is not None and characterization.confirmed:
                settled = tuple(
                    self._settle(e, EditVerdict.KEPT)
                    if e.relpath == characterization.relpath and e.is_on_disk
                    else e
                    for e in settled
                )
                tier = ConfidenceTier.MEDIUM
                reason = "characterization fixture preserved the pre-migration behaviour"
            return VerificationReport(
                ran=ran,
                skipped_reason=skipped_reason,
                install=resolved_install,
                baseline=baseline,
                after_fix=after_fix,
                edits=settled,
                typecheck_baseline=tc_baseline,
                typecheck_after=tc_after,
                tier=tier,
                tier_reason=reason,
                characterization=characterization,
            )

        if not self._typecheck_enabled:
            return suspect("typecheck verification is disabled", resolved_install=install)

        # `tsc` needs node_modules for the SDK's own .d.ts files, so the
        # "no test script" path has to install even though it never intended
        # to run anything.
        resolved_install = install
        if resolved_install is None:
            resolved_install = install_dependencies(
                root,
                timeout=self._install_timeout,
                ignore_scripts=self._ignore_scripts,
                max_output_bytes=self._max_output_bytes,
            )
        if not resolved_install.ok:
            return suspect(
                f"could not install dependencies for a typecheck "
                f"({resolved_install.skipped_reason or 'install failed'})",
                resolved_install=resolved_install,
            )

        touched_relpaths = tuple(e.relpath for e in on_disk)
        edit_by_relpath = {e.relpath: e for e in on_disk}

        for relpath in touched_relpaths:
            self._editor.revert(relpath)
        tc_baseline = run_typecheck(
            root, timeout=self._typecheck_timeout, max_output_bytes=self._max_output_bytes
        )
        for relpath in touched_relpaths:
            self._editor.write_fix(relpath, edit_by_relpath[relpath].fixed_content)

        if not tc_baseline.usable:
            return suspect(
                f"typecheck unavailable: {tc_baseline.skipped_reason or 'baseline typecheck produced no usable output'}",
                resolved_install=resolved_install,
                tc_baseline=tc_baseline,
            )

        tc_after = run_typecheck(
            root, timeout=self._typecheck_timeout, max_output_bytes=self._max_output_bytes
        )
        if not tc_after.usable:
            return suspect(
                f"typecheck unavailable: {tc_after.skipped_reason or 'after-fix typecheck produced no usable output'}",
                resolved_install=resolved_install,
                tc_baseline=tc_baseline,
                tc_after=tc_after,
            )

        added = new_diagnostics(tc_baseline, tc_after)
        if not added:
            settled = tuple(self._settle(e, EditVerdict.KEPT) for e in edits)
            return VerificationReport(
                ran=ran,
                skipped_reason=skipped_reason,
                install=resolved_install,
                baseline=baseline,
                after_fix=after_fix,
                edits=settled,
                typecheck_baseline=tc_baseline,
                typecheck_after=tc_after,
                tier=ConfidenceTier.MEDIUM,
                tier_reason="`tsc --noEmit` introduced no new diagnostics",
            )

        # Unlike a test failure, a type error names its own file -- so
        # attribution here is exact, and only diagnostics landing outside
        # every touched file are ambiguous.
        blamed = {d.relpath for d in added} & set(touched_relpaths)
        unattributed = [d for d in added if d.relpath not in touched_relpaths]

        settled_edits: list[FileEdit] = []
        for edit in edits:
            if not edit.is_on_disk:
                settled_edits.append(edit)
                continue
            if edit.relpath in blamed:
                self._editor.revert(edit.relpath)
                settled_edits.append(self._settle(edit, EditVerdict.REVERTED))
            elif unattributed:
                settled_edits.append(self._settle(edit, EditVerdict.SUSPECT))
            else:
                settled_edits.append(self._settle(edit, EditVerdict.KEPT))

        return VerificationReport(
            ran=ran,
            skipped_reason=skipped_reason,
            install=resolved_install,
            baseline=baseline,
            after_fix=after_fix,
            edits=tuple(settled_edits),
            typecheck_baseline=tc_baseline,
            typecheck_after=tc_after,
            tier=ConfidenceTier.MEDIUM if not unattributed else ConfidenceTier.LOW,
            tier_reason=(
                f"`tsc --noEmit` attributed {len(added)} new diagnostic(s) to specific file(s)"
                if not unattributed
                else f"`tsc --noEmit` reported {len(added)} new diagnostic(s), "
                f"{len(unattributed)} outside any edited file"
            ),
        )

    def _characterize_when_available(
        self, on_disk: list[FileEdit], install: InstallResult | None
    ) -> CharacterizationReport | None:
        """Try the pre-fix characterization oracle as a last resort.

        It intentionally handles one touched CommonJS file at a time. A
        multi-file migration needs a multi-subject oracle and must remain
        suspect rather than pretending one file's fixture proved the batch.
        """
        if (
            self._characterizer is None
            or self._change is None
            or len(on_disk) != 1
            or install is None
            or not install.ok
        ):
            return None
        edit = on_disk[0]
        if not self._characterizer.supports(edit.relpath):
            return None
        return self._characterizer.characterize(
            root=self._editor.checkout.path,
            relpath=edit.relpath,
            original_source=edit.original_content,
            change=self._change,
            apply_fix=lambda: self._editor.write_fix(edit.relpath, edit.fixed_content),
            revert_fix=lambda: self._editor.revert(edit.relpath),
        )

    @staticmethod
    def _mark_suspect(edit: FileEdit) -> FileEdit:
        if not edit.is_on_disk:
            return edit
        return Verifier._settle(edit, EditVerdict.SUSPECT)

    @staticmethod
    def _settle(edit: FileEdit, verdict: EditVerdict) -> FileEdit:
        return dataclasses.replace(edit, verdict=verdict)
