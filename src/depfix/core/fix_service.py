"""Shared assembly and commit policy for dependency fixes.

The interactive CLI and fleet orchestrator must make the same decision about
unverified edits.  Keeping that rule here prevents the two entry points from
quietly drifting apart.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass

from depfix.agent import FixAgent, make_fix_strategy
from depfix.agent.tools import FixToolset
from depfix.apply.models import EditOrigin, FileEdit
from depfix.apply.workspace import WorkspaceEditor
from depfix.classify.llm import GeminiCompleter, LLMCompleter, OllamaCompleter
from depfix.clone import Checkout
from depfix.codemods import CodemodRegistry
from depfix.config import Settings
from depfix.core.models import BreakingChange, ChangeKind
from depfix.core.pipeline import FixPipeline, FixPipelineResult
from depfix.fixers.gemini import FixGenerator
from depfix.fixers.ollama import OllamaFixGenerator
from depfix.gh.pr import committable_edits
from depfix.repoconfig.models import RepoConfig
from depfix.retry.loop import RetryLoop
from depfix.scanners import CallSiteScanner
from depfix.scanners.models import RepoScanResult
from depfix.validators import validator_for_ecosystem
from depfix.verify import Characterizer, Verifier
from depfix.verify.confidence import ConfidenceTier

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FixServiceResult:
    """A pipeline result plus the edits that may be committed."""

    pipeline_result: FixPipelineResult
    committable: list[FileEdit]
    verify_required: bool
    escalated: bool = False


def build_fix_pipeline(
    *,
    settings: Settings,
    repo_config: RepoConfig,
    fixer: FixGenerator | OllamaFixGenerator | FixAgent,
    editor: WorkspaceEditor,
    max_retries: int | None = None,
    toolset: FixToolset | None = None,
    codemods: CodemodRegistry | None = None,
    characterizer: Characterizer | None = None,
    ecosystem: str = "javascript",
) -> FixPipeline:
    """Build one fix pipeline under the common verification policy."""
    from depfix.codemods import CodemodRegistry as _Registry

    verify_required = repo_config.verify and settings.verify_enabled
    validator = validator_for_ecosystem(
        ecosystem,
        use_ast_validation=settings.fix_validate_syntax,
        checkout_root=editor.checkout.path,
    )
    effective_codemods = codemods
    if effective_codemods is None and settings.codemods_enabled:
        effective_codemods = _Registry()
    verifier = (
        Verifier(
            editor,
            install_timeout=settings.verify_install_timeout,
            test_timeout=settings.verify_test_timeout,
            ignore_scripts=settings.verify_ignore_scripts,
            max_output_bytes=settings.verify_max_output_bytes,
            typecheck_enabled=settings.verify_typecheck_enabled,
            typecheck_timeout=settings.verify_typecheck_timeout,
            characterizer=characterizer,
            ecosystem=ecosystem,
        )
        if verify_required
        else None
    )
    retries = settings.retry_max_rounds if max_retries is None else max_retries
    retry_loop = (
        RetryLoop(fixer, validator, verifier, max_rounds=retries)
        if verifier is not None and retries > 0
        else None
    )
    return FixPipeline(
        fixer,
        validator=validator,
        verifier=verifier,
        retry_loop=retry_loop,
        toolset=toolset,
        codemods=effective_codemods,
    )


def _build_completer_for_characterize(settings: Settings) -> LLMCompleter | None:
    """Build the fixture-only completer for the characterization oracle."""
    if settings.llm_provider == "gemini":
        if not settings.google_api_key:
            return None
        return GeminiCompleter(api_key=settings.google_api_key, model=settings.gemini_model)
    return OllamaCompleter(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        timeout=settings.ollama_timeout,
    )


def _build_fallback_fixer(settings: Settings) -> FixGenerator | OllamaFixGenerator | None:
    """Instantiate the configured stronger fallback model, if any."""
    if not settings.llm_fallback_model:
        return None
    provider = (settings.llm_fallback_provider or settings.llm_provider).strip()
    if provider == "gemini":
        if not settings.google_api_key:
            return None
        return FixGenerator(api_key=settings.google_api_key, model=settings.llm_fallback_model)
    return OllamaFixGenerator(
        model=settings.llm_fallback_model,
        base_url=settings.ollama_base_url,
        timeout=settings.ollama_timeout,
    )


def run_fix_for_change(
    *,
    checkout: Checkout,
    scan_result: RepoScanResult,
    change: BreakingChange,
    settings: Settings,
    repo_config: RepoConfig,
    fixer: FixGenerator | OllamaFixGenerator,
    max_retries: int | None = None,
) -> FixServiceResult:
    """Run a fix, escalating once when the primary has no committable edit."""
    from depfix.ecosystems import fixable_ids
    from depfix.ecosystems import get as get_ecosystem
    from depfix.scanners.repo import detect_repo_ecosystem

    # Dependency drift is not a source-code migration.  It therefore has no
    # call sites to hand to an LLM: make a deterministic manifest edit, then
    # use the same verification and commit policy as every other fix.
    if change.kind is ChangeKind.DEPENDENCY_VERSION_BUMP:
        return _run_dependency_drift(checkout, scan_result, change, settings, repo_config)

    ecosystem = detect_repo_ecosystem(checkout.path)
    if ecosystem == "typescript":
        ecosystem = "javascript"
    if ecosystem not in fixable_ids():
        pretty = ecosystem if ecosystem != "unknown" else "unrecognized"
        spec = get_ecosystem(ecosystem)
        supported = ", ".join(sorted(fixable_ids()))
        note = (
            f"skipped: {spec.display_name} repos are scan-only today -- depfix found the "
            f"call sites above but only generates verified fixes for: {supported}"
            if spec is not None
            else f"skipped: repo ecosystem is {pretty}; depfix generates fixes for: {supported}"
        )
        result = FixPipelineResult(
            repo_full_name=scan_result.repo_full_name,
            breaking_change=change,
            files_scanned=scan_result.files_scanned,
            files_affected=0,
            edits=(), total_usages_fixed=0, total_cost=0.0, total_tokens=0, duration_ms=0,
            codemod_notes=(note,),
        )
        logger.info("skipping %s: unsupported ecosystem %s", change.dedupe_key[:12], pretty)
        return FixServiceResult(result, [], repo_config.verify and settings.verify_enabled)
    verify_required = repo_config.verify and settings.verify_enabled
    characterizer = None
    # The characterization harness is Node/CommonJS-specific
    # (verify/characterize.py); other ecosystems skip straight to their
    # own smoke checks.
    if settings.verify_characterize_enabled and ecosystem == "javascript":
        completer = _build_completer_for_characterize(settings)
        if completer is not None:
            characterizer = Characterizer(
                completer,
                timeout=float(settings.verify_characterize_timeout),
                max_output_bytes=settings.verify_max_output_bytes,
            )

    primary = _run_once(
        checkout=checkout, scan_result=scan_result, change=change, settings=settings,
        repo_config=repo_config, fixer=fixer, max_retries=max_retries,
        characterizer=characterizer, ecosystem=ecosystem,
    )
    if primary.committable:
        return primary

    fallback = _build_fallback_fixer(settings)
    if fallback is None:
        return primary

    logger.info(
        "primary model produced no committable edits for %s; escalating to fallback model %s",
        change.dedupe_key[:12], settings.llm_fallback_model,
    )
    # Restore the checkout explicitly. A new WorkspaceEditor alone would
    # capture the primary's rejected contents as its "original" state.
    restore_editor = WorkspaceEditor(checkout)
    for edit in primary.pipeline_result.edits:
        if edit.is_on_disk:
            restore_editor.write_fix(edit.relpath, edit.original_content)

    escalated = _run_once(
        checkout=checkout, scan_result=scan_result, change=change, settings=settings,
        repo_config=repo_config, fixer=fallback, max_retries=max_retries,
        characterizer=characterizer, ecosystem=ecosystem,
    )
    if escalated.committable:
        return FixServiceResult(
            pipeline_result=escalated.pipeline_result,
            committable=escalated.committable,
            verify_required=verify_required,
            escalated=True,
        )
    return FixServiceResult(
        pipeline_result=primary.pipeline_result,
        committable=[],
        verify_required=verify_required,
        escalated=True,
    )


def _run_dependency_drift(
    checkout: Checkout,
    scan_result: RepoScanResult,
    change: BreakingChange,
    settings: Settings,
    repo_config: RepoConfig,
) -> FixServiceResult:
    """Apply one safe manifest-only dependency update behind the service seam."""
    from depfix.codemods.lockfile import dependency_drift_policy
    from depfix.scanners.repo import detect_repo_ecosystem

    verify_required = repo_config.verify and settings.verify_enabled
    policy = dependency_drift_policy(change)
    ecosystem = detect_repo_ecosystem(checkout.path)
    if ecosystem == "typescript":
        ecosystem = "javascript"

    def report_only(note: str) -> FixServiceResult:
        result = FixPipelineResult(
            repo_full_name=scan_result.repo_full_name, breaking_change=change,
            files_scanned=scan_result.files_scanned, files_affected=0, edits=(),
            total_usages_fixed=0, total_cost=0.0, total_tokens=0, duration_ms=0,
            codemod_notes=(note,),
        )
        return FixServiceResult(result, [], verify_required)

    if policy != "automatic":
        return report_only(
            "major or unparseable dependency drift requires a vetted API migration; "
            "recorded for review but not applied automatically."
        )

    if ecosystem == "javascript":
        from depfix.codemods.lockfile import build_dependency_drift_plan

        plan = build_dependency_drift_plan(checkout.path, change)
        drift_bumps = [
            (
                bump.manifest_relpath, bump.fixed_content, bump.note,
                f"Registry drift: {bump.package} {bump.old_range} -> {bump.new_range} "
                f"in {bump.manifest_relpath}.",
            )
            for bump in plan.bumps
        ]
    elif ecosystem == "python":
        from depfix.ecosystems.pypi_manifests import build_pypi_dependency_drift_bumps

        drift_bumps = [
            (
                bump.manifest_relpath, bump.fixed_content, bump.note,
                f"Registry drift: {bump.package} {bump.old_spec} -> {bump.new_spec} "
                f"in {bump.manifest_relpath}.",
            )
            for bump in build_pypi_dependency_drift_bumps(checkout.path, change)
        ]
    else:
        from depfix.ecosystems import get as get_ecosystem

        spec = get_ecosystem(ecosystem)
        pretty = spec.display_name if spec is not None else (
            ecosystem if ecosystem != "unknown" else "this repository's"
        )
        return report_only(
            f"dependency drift detected for {pretty}; automatic manifest writers are "
            "currently available for npm and PyPI only. This drift is reported for review "
            "until a manifest, lockfile, and verification adapter exists for this ecosystem."
        )

    editor = WorkspaceEditor(checkout)
    edits: list[FileEdit] = []
    notes: list[str] = plan.declines if ecosystem == "javascript" else []
    for relpath, fixed_content, note, trace in drift_bumps:
        edit = editor.write_fix(
            relpath, fixed_content, confidence=1.0,
            origin=EditOrigin.CODEMOD, codemod_id="manifest.dependency-drift",
        )
        if not edit.changed:
            notes.append(f"manifest drift update not written: {relpath}")
            continue
        edits.append(dataclasses.replace(edit, derivation_trace=trace))
        notes.append(note)

    verification = None
    if edits and verify_required:
        verifier = Verifier(
            editor, install_timeout=settings.verify_install_timeout,
            test_timeout=settings.verify_test_timeout,
            ignore_scripts=settings.verify_ignore_scripts,
            max_output_bytes=settings.verify_max_output_bytes,
            typecheck_enabled=settings.verify_typecheck_enabled,
            typecheck_timeout=settings.verify_typecheck_timeout,
            ecosystem=ecosystem,
        )
        verification = verifier.verify(edits, change=change)
        edits = list(verification.edits)

    # Refresh only after verification has kept the manifest edit. Both uv
    # and Poetry lock without installing the project; a failed refresh stays
    # an explicit note rather than making the manifest change unsafe.
    if (
        ecosystem == "python"
        and settings.lockfile_regenerate
        and checkout.is_temporary
        and any(edit.is_on_disk for edit in edits)
    ):
        from depfix.ecosystems.python_lockfile import (
            python_lockfile_paths,
            try_refresh_python_lockfile,
        )

        ok, message = try_refresh_python_lockfile(
            checkout.path, timeout=settings.verify_install_timeout,
        )
        notes.append(message)
        if ok:
            for lockfile in python_lockfile_paths(checkout.path):
                relpath = lockfile.relative_to(checkout.path).as_posix()
                try:
                    content = lockfile.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                lock_edit = editor.write_fix(
                    relpath, content, confidence=1.0,
                    origin=EditOrigin.CODEMOD, codemod_id="manifest.lockfile-regen",
                )
                if not lock_edit.changed:
                    continue
                lock_edit = dataclasses.replace(
                    lock_edit,
                    derivation_trace=f"Lockfile refreshed after manifest drift: {message}.",
                )
                edits.append(lock_edit)

    result = FixPipelineResult(
        repo_full_name=scan_result.repo_full_name, breaking_change=change,
        files_scanned=scan_result.files_scanned, files_affected=len(edits), edits=tuple(edits),
        total_usages_fixed=0, total_cost=0.0, total_tokens=0, duration_ms=0,
        verification=verification, codemod_notes=tuple(notes),
    )
    return FixServiceResult(
        result, committable_edits(result, allow_unverified=not verify_required), verify_required,
    )


def _run_once(
    *,
    checkout: Checkout,
    scan_result: RepoScanResult,
    change: BreakingChange,
    settings: Settings,
    repo_config: RepoConfig,
    fixer: FixGenerator | OllamaFixGenerator,
    max_retries: int | None,
    characterizer: Characterizer | None,
    ecosystem: str = "javascript",
) -> FixServiceResult:
    """Run one isolated primary or fallback fix attempt."""
    editor = WorkspaceEditor(checkout)
    strategy = make_fix_strategy(settings, fixer)
    toolset = (
        FixToolset(
            checkout,
            scanner=CallSiteScanner(
                max_file_bytes=settings.scan_max_file_bytes, max_files=settings.scan_max_files
            ),
            max_file_bytes=settings.scan_max_file_bytes,
        )
        if isinstance(strategy, FixAgent)
        else None
    )
    verify_required = repo_config.verify and settings.verify_enabled
    pipeline = build_fix_pipeline(
        settings=settings,
        repo_config=repo_config,
        fixer=strategy,
        editor=editor,
        max_retries=max_retries,
        toolset=toolset,
        characterizer=characterizer,
        ecosystem=ecosystem,
    )
    result = pipeline.run(scan_result, change, editor)
    committable = committable_edits(result, allow_unverified=not verify_required)
    floor = ConfidenceTier(settings.apply_min_confidence)
    if committable and not result.confidence.at_least(floor):
        logger.info(
            "withholding %d edit(s) for %s: confidence %s is below apply_min_confidence %s",
            len(committable), change.dedupe_key[:12], result.confidence.value, floor.value,
        )
        committable = []
    if committable:
        from depfix.apply.models import EditOrigin, EditVerdict
        from depfix.codemods.lockfile import build_manifest_bumps

        bumped_any = False
        for bump in build_manifest_bumps(checkout.path, change):
            edit = editor.write_fix(bump.manifest_relpath, bump.fixed_content, confidence=1.0, usages_fixed=0)
            if not edit.changed:
                # write_fix declined (e.g. identical content, encoding error,
                # or an I/O failure) -- do not report an untouched/failed
                # manifest as a kept, on-disk fix.
                result = dataclasses.replace(
                    result, codemod_notes=(*result.codemod_notes,
                        f"manifest bump for {bump.manifest_relpath} was not written: "
                        f"{edit.error_message or 'no change on disk'}")
                )
                continue
            edit = dataclasses.replace(
                edit, verdict=EditVerdict.KEPT, origin=EditOrigin.CODEMOD,
                codemod_id="manifest.version-bump",
                derivation_trace=(f"Manifest bump: {bump.package} {bump.old_range} → "
                                  f"{bump.new_range} in {bump.manifest_relpath}."),
            )
            committable.append(edit)
            result = dataclasses.replace(
                result, edits=(*result.edits, edit), codemod_notes=(*result.codemod_notes, bump.note)
            )
            bumped_any = True
        if bumped_any and settings.lockfile_regenerate and checkout.is_temporary:
            from depfix.codemods.lockfile import lockfile_paths, try_regenerate_lockfile

            ok, message = try_regenerate_lockfile(
                checkout.path, timeout=settings.verify_install_timeout,
                ignore_scripts=settings.verify_ignore_scripts,
            )
            if ok:
                for lockfile in lockfile_paths(checkout.path):
                    relpath = lockfile.relative_to(checkout.path).as_posix()
                    try:
                        content = lockfile.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        continue  # binary bun.lockb cannot be represented as a FileEdit
                    edit = editor.write_fix(relpath, content, confidence=1.0, usages_fixed=0)
                    if edit.changed:
                        edit = dataclasses.replace(
                            edit, verdict=EditVerdict.KEPT, origin=EditOrigin.CODEMOD,
                            codemod_id="manifest.lockfile-regen",
                            derivation_trace=f"Lockfile regenerated after manifest bump: {message}.",
                        )
                        committable.append(edit)
                        result = dataclasses.replace(result, edits=(*result.edits, edit),
                            codemod_notes=(*result.codemod_notes, message))
            else:
                result = dataclasses.replace(result, codemod_notes=(*result.codemod_notes,
                    f"lockfile not regenerated: {message}; regenerate it before merging"))
    return FixServiceResult(
        pipeline_result=result,
        committable=committable,
        verify_required=verify_required,
    )
