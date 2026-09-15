"""Shared assembly and commit policy for dependency fixes.

The interactive CLI and fleet orchestrator must make the same decision about
unverified edits.  Keeping that rule here prevents the two entry points from
quietly drifting apart.
"""

from __future__ import annotations

from dataclasses import dataclass

from depfix.agent import FixAgent, make_fix_strategy
from depfix.agent.tools import FixToolset
from depfix.apply.models import FileEdit
from depfix.apply.workspace import WorkspaceEditor
from depfix.clone import Checkout
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
from depfix.verify import Verifier


@dataclass(frozen=True)
class FixServiceResult:
    """A pipeline result plus the edits that may be committed."""

    pipeline_result: FixPipelineResult
    committable: list[FileEdit]
    verify_required: bool


def build_fix_pipeline(
    *,
    settings: Settings,
    repo_config: RepoConfig,
    fixer: FixGenerator | OllamaFixGenerator | FixAgent,
    editor: WorkspaceEditor,
    max_retries: int | None = None,
    toolset: FixToolset | None = None,
) -> FixPipeline:
    """Build one fix pipeline under the common verification policy."""
    verify_required = repo_config.verify and settings.verify_enabled
    validator = FixValidator(use_ast_validation=settings.fix_validate_syntax)
    verifier = (
        Verifier(
            editor,
            install_timeout=settings.verify_install_timeout,
            test_timeout=settings.verify_test_timeout,
            ignore_scripts=settings.verify_ignore_scripts,
            max_output_bytes=settings.verify_max_output_bytes,
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
        fixer, validator=validator, verifier=verifier, retry_loop=retry_loop, toolset=toolset
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
    """Run a fix and apply the single rule for unverified PR eligibility.

    An edit may be committed without tests only when verification was not
    required for this run (``--no-verify`` or ``verify: false``).
    """
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
    )
    result = pipeline.run(scan_result, change, editor)
    return FixServiceResult(
        pipeline_result=result,
        committable=committable_edits(result, allow_unverified=not verify_required),
        verify_required=verify_required,
    )
