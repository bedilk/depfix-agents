"""Shared assembly and commit policy for dependency fixes.

The interactive CLI and fleet orchestrator must make the same decision about
unverified edits.  Keeping that rule here prevents the two entry points from
quietly drifting apart.
"""

from __future__ import annotations

import logging
import dataclasses
from dataclasses import dataclass

from depfix.agent import FixAgent, make_fix_strategy
from depfix.agent.tools import FixToolset
from depfix.apply.models import FileEdit
from depfix.apply.workspace import WorkspaceEditor
from depfix.clone import Checkout
from depfix.classify.llm import GeminiCompleter, LLMCompleter, OllamaCompleter
from depfix.config import Settings
from depfix.core.models import BreakingChange
from depfix.core.pipeline import FixPipeline, FixPipelineResult
from depfix.fixers.gemini import FixGenerator
from depfix.fixers.ollama import OllamaFixGenerator
from depfix.gh.pr import committable_edits
from depfix.repoconfig.models import RepoConfig
from depfix.retry.loop import RetryLoop
from depfix.scanners import CallSiteScanner
from depfix.scanners.models import RepoScanResult
from depfix.validators.javascript import FixValidator
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
    codemods: "CodemodRegistry | None" = None,
    characterizer: "Characterizer | None" = None,
) -> FixPipeline:
    """Build one fix pipeline under the common verification policy."""
    from depfix.codemods import CodemodRegistry as _Registry

    verify_required = repo_config.verify and settings.verify_enabled
    validator = FixValidator(use_ast_validation=settings.fix_validate_syntax)
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
    from depfix.scanners.repo import SUPPORTED_ECOSYSTEMS, detect_repo_ecosystem

    ecosystem = detect_repo_ecosystem(checkout.path)
    if ecosystem not in SUPPORTED_ECOSYSTEMS:
        pretty = ecosystem if ecosystem != "unknown" else "unrecognized"
        result = FixPipelineResult(
            repo_full_name=scan_result.repo_full_name,
            breaking_change=change,
            files_scanned=scan_result.files_scanned,
            files_affected=0,
            edits=(), total_usages_fixed=0, total_cost=0.0, total_tokens=0, duration_ms=0,
            codemod_notes=(
                f"skipped: repo ecosystem is {pretty}; depfix currently supports JavaScript and TypeScript only",
            ),
        )
        logger.info("skipping %s: unsupported ecosystem %s", change.dedupe_key[:12], pretty)
        return FixServiceResult(result, [], repo_config.verify and settings.verify_enabled)
    verify_required = repo_config.verify and settings.verify_enabled
    characterizer = None
    if settings.verify_characterize_enabled:
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
        characterizer=characterizer,
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
        characterizer=characterizer,
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
