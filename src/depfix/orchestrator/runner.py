"""The Week 6 fleet orchestrator: unattended scan -> fix -> verify -> PR
across many repos, gated by each repo's own opt-in ``.depfix.yml`` and an
idempotency ledger so cron-driven reruns never reopen a PR or reprocess a
terminal outcome.

Mirrors :mod:`depfix.watcher.runner`'s failure-isolation shape: one bad
repo (or one bad change within a repo) must never cost the rest of the
fleet run its results -- every per-repo and per-change action is wrapped in
its own try/except, producing a failure outcome rather than propagating.
All the actual go/no-go logic lives in the pure :mod:`depfix.orchestrator.policy`;
this module is the thin, mockable shell that gathers the inputs that
``decide()`` needs and acts on its verdict.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from depfix.apply.models import FileEdit
from depfix.apply.workspace import WorkspaceEditor
from depfix.clone import Checkout, CloneService
from depfix.config import Settings
from depfix.core.models import BreakingChange
from depfix.core.pipeline import FixPipeline, FixPipelineResult
from depfix.fixers.gemini import FixGenerator
from depfix.fixers.ollama import OllamaFixGenerator
from depfix.gh import (
    BranchWriter,
    GitHubAppAuth,
    GitHubAppError,
    PullRequest,
    branch_name_for,
    build_pr_body,
    committable_edits,
    open_pull_request,
    pr_title_for,
)
from depfix.orchestrator.models import ChangeOutcome, OrchestratorOutcome, RepoOutcome
from depfix.orchestrator.policy import SkipReason, decide
from depfix.providers.models import ProviderSpec
from depfix.repoconfig.loader import RepoConfigError, parse_repo_config
from depfix.repoconfig.models import SUPPORTED_VERSION, RepoConfig
from depfix.retry.loop import RetryLoop
from depfix.scanners import CallSiteScanner, build_scan_target, scan_checkout, upsert_repo
from depfix.scanners.models import RepoScanResult
from depfix.storage import (
    AttemptStatus,
    get_change_attempt,
    init_schema,
    record_change_attempt,
    record_fix_run,
    record_pull_request,
    session_scope,
    touch_no_call_sites,
)
from depfix.validators.javascript import FixValidator
from depfix.verify import Verifier

logger = logging.getLogger(__name__)


class Orchestrator:
    """Runs the full fleet pipeline for a batch of ``(repo, change)`` pairs.

    ``fixer_factory`` builds one fresh fixer per change (a
    :class:`FixGenerator`/:class:`OllamaFixGenerator` instance keeps its own
    ``llm_calls`` list, so reusing one across changes would mix their
    accounting) -- callers own the choice of provider/model via whatever
    closure they pass in.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        gh_auth: GitHubAppAuth,
        clone_service: CloneService,
        providers: list[ProviderSpec],
        fixer_factory: Callable[[], FixGenerator | OllamaFixGenerator],
        force: bool = False,
    ) -> None:
        self._settings = settings
        self._gh_auth = gh_auth
        self._clone_service = clone_service
        self._providers = {p.id: p for p in providers}
        self._known_provider_ids = frozenset(self._providers)
        self._fixer_factory = fixer_factory
        self._force = force

    def run(
        self, repo_full_names: list[str], changes: list[BreakingChange]
    ) -> OrchestratorOutcome:
        """Process every ``(repo, change)`` pair for this run.

        One bad repo can't cost the rest of the fleet its results: any
        exception that escapes :meth:`_run_repo` itself (as opposed to one
        already caught and turned into a per-change ``FAILED`` outcome by
        :meth:`_process_change`) is caught here and recorded as that repo's
        ``error``.
        """
        init_schema()
        outcome = OrchestratorOutcome()
        for repo_full_name in repo_full_names:
            try:
                outcome.repos.append(self._run_repo(repo_full_name, changes))
            except Exception as exc:
                logger.exception("repo %s failed", repo_full_name)
                outcome.repos.append(RepoOutcome(repo_full_name=repo_full_name, error=str(exc)))
        return outcome

    def _run_repo(self, repo_full_name: str, changes: list[BreakingChange]) -> RepoOutcome:
        owner, _, name = repo_full_name.partition("/")
        if not name:
            return RepoOutcome(
                repo_full_name=repo_full_name, error=f"not OWNER/NAME: {repo_full_name!r}"
            )

        try:
            installation = self._gh_auth.resolve_installation_for_repo(owner, name)
        except GitHubAppError:
            return RepoOutcome(repo_full_name=repo_full_name, skip_reason=SkipReason.NO_INSTALLATION)

        try:
            config_text = self._gh_auth.get_file_contents(
                owner, name, self._settings.repo_config_filename
            )
        except GitHubAppError as exc:
            return RepoOutcome(repo_full_name=repo_full_name, error=str(exc))

        if config_text is None:
            if self._settings.pipeline_require_config_file:
                return RepoOutcome(repo_full_name=repo_full_name, skip_reason=SkipReason.NO_REPO_CONFIG)
            repo_config = RepoConfig(version=SUPPORTED_VERSION)
        else:
            try:
                repo_config = parse_repo_config(
                    config_text,
                    where=f"{repo_full_name}/{self._settings.repo_config_filename}",
                )
            except RepoConfigError as exc:
                return RepoOutcome(
                    repo_full_name=repo_full_name,
                    skip_reason=SkipReason.INVALID_REPO_CONFIG,
                    error=str(exc),
                )

        try:
            base_branch = repo_config.base_branch or self._gh_auth.default_ref(owner, name)
            current_ref_sha = self._gh_auth.ref_sha(owner, name, base_branch)
            open_prs = self._gh_auth.list_open_pull_requests(owner, name, base=base_branch)
        except GitHubAppError as exc:
            return RepoOutcome(repo_full_name=repo_full_name, error=str(exc))
        open_pr_count = sum(1 for pr in open_prs if pr.head_branch.startswith("depfix/"))

        change_outcomes: list[ChangeOutcome] = []
        changes_processed = 0
        with session_scope() as session:
            upsert_repo(
                session,
                full_name=repo_full_name,
                owner=owner,
                name=name,
                installation_id=installation.id,
                default_branch=base_branch,
            )

            for change in changes:
                attempt = get_change_attempt(
                    session, repo_id=repo_full_name, dedupe_key=change.dedupe_key
                )
                skip_reason = decide(
                    repo_config=repo_config,
                    change=change,
                    known_provider_ids=self._known_provider_ids,
                    attempt=attempt,
                    current_ref_sha=current_ref_sha,
                    open_pr_count=open_pr_count,
                    changes_processed_this_run=changes_processed,
                    settings=self._settings,
                    force=self._force,
                )
                if skip_reason is not None:
                    change_outcomes.append(
                        ChangeOutcome(
                            dedupe_key=change.dedupe_key,
                            package=change.package,
                            old_api=change.old_api,
                            skip_reason=skip_reason,
                        )
                    )
                    continue

                changes_processed += 1
                change_outcome = self._process_change(
                    session,
                    owner=owner,
                    name=name,
                    repo_full_name=repo_full_name,
                    installation_id=installation.id,
                    change=change,
                    repo_config=repo_config,
                    base_branch=base_branch,
                    current_ref_sha=current_ref_sha,
                )
                change_outcomes.append(change_outcome)
                if change_outcome.attempt_status == AttemptStatus.PR_OPENED:
                    open_pr_count += 1
                session.commit()

        return RepoOutcome(repo_full_name=repo_full_name, changes=change_outcomes)

    def _process_change(
        self,
        session: Session,
        *,
        owner: str,
        name: str,
        repo_full_name: str,
        installation_id: int,
        change: BreakingChange,
        repo_config: RepoConfig,
        base_branch: str,
        current_ref_sha: str,
    ) -> ChangeOutcome:
        """Scan, fix, verify, and (if configured) open a PR for one
        ``(repo, change)`` pair -- isolated so one change's bug can't cost
        the rest of this repo's run its results (see :meth:`_run_repo`).
        """
        outcome = ChangeOutcome(
            dedupe_key=change.dedupe_key, package=change.package, old_api=change.old_api
        )
        checkout: Checkout | None = None
        try:
            provider = self._providers[change.provider_id]
            target = build_scan_target(provider, change)
            token = self._gh_auth.installation_token(installation_id, repositories=(name,))
            checkout = self._clone_service.clone(owner, name, ref=base_branch, token=token.token)

            scanner = CallSiteScanner(
                max_file_bytes=self._settings.scan_max_file_bytes,
                max_files=self._settings.scan_max_files,
            )
            scan_result = scan_checkout(
                checkout, target, repo_full_name=repo_full_name, scanner=scanner
            )

            if not scan_result.actionable_sites:
                touch_no_call_sites(
                    session,
                    repo_id=repo_full_name,
                    dedupe_key=change.dedupe_key,
                    ref_sha=current_ref_sha,
                )
                outcome.attempt_status = AttemptStatus.NO_CALL_SITES
                outcome.detail = "no actionable call sites"
                return outcome

            fix_result = self._run_fix_pipeline(checkout, scan_result, change, repo_config)

            if repo_config.open_pr:
                committable = [
                    edit
                    for edit in committable_edits(
                        fix_result, allow_unverified=not repo_config.verify
                    )
                    if repo_config.paths.allows(edit.relpath)
                ]
                if not committable:
                    record_change_attempt(
                        session,
                        repo_id=repo_full_name,
                        dedupe_key=change.dedupe_key,
                        status=AttemptStatus.NO_KEPT_EDITS,
                        ref_sha=current_ref_sha,
                    )
                    outcome.attempt_status = AttemptStatus.NO_KEPT_EDITS
                    outcome.detail = "no kept/committable edits"
                    return outcome

                pr = self._open_pr(
                    owner=owner,
                    name=name,
                    installation_id=installation_id,
                    base_branch=base_branch,
                    change=change,
                    fix_result=fix_result,
                    edits=committable,
                    draft=repo_config.draft_pr,
                )
                run_row = record_fix_run(
                    session,
                    repo_full_name=repo_full_name,
                    owner=owner,
                    name=name,
                    result=fix_result,
                    installation_id=installation_id,
                    default_branch=base_branch,
                )
                record_pull_request(session, run_row, pr)
                session.flush()  # assign run_row.id before it's read below
                record_change_attempt(
                    session,
                    repo_id=repo_full_name,
                    dedupe_key=change.dedupe_key,
                    status=AttemptStatus.PR_OPENED,
                    fix_run_id=run_row.id,
                    ref_sha=current_ref_sha,
                )
                outcome.attempt_status = AttemptStatus.PR_OPENED
                outcome.pr_url = pr.html_url
                return outcome

            run_row = record_fix_run(
                session,
                repo_full_name=repo_full_name,
                owner=owner,
                name=name,
                result=fix_result,
                installation_id=installation_id,
                default_branch=base_branch,
            )
            session.flush()  # assign run_row.id before it's read below
            record_change_attempt(
                session,
                repo_id=repo_full_name,
                dedupe_key=change.dedupe_key,
                status=AttemptStatus.FIXED_NO_PR,
                fix_run_id=run_row.id,
                ref_sha=current_ref_sha,
            )
            outcome.attempt_status = AttemptStatus.FIXED_NO_PR
            return outcome
        except Exception as exc:
            logger.exception("processing %s for %s failed", change.dedupe_key, repo_full_name)
            record_change_attempt(
                session,
                repo_id=repo_full_name,
                dedupe_key=change.dedupe_key,
                status=AttemptStatus.FAILED,
                last_error=str(exc),
                ref_sha=current_ref_sha,
            )
            outcome.attempt_status = AttemptStatus.FAILED
            outcome.detail = str(exc)
            return outcome
        finally:
            if checkout is not None:
                self._clone_service.cleanup(checkout)

    def _run_fix_pipeline(
        self,
        checkout: Checkout,
        scan_result: RepoScanResult,
        change: BreakingChange,
        repo_config: RepoConfig,
    ) -> FixPipelineResult:
        editor = WorkspaceEditor(checkout)
        fixer = self._fixer_factory()

        verifier: Verifier | None = None
        if repo_config.verify and self._settings.verify_enabled:
            verifier = Verifier(
                editor,
                install_timeout=self._settings.verify_install_timeout,
                test_timeout=self._settings.verify_test_timeout,
                ignore_scripts=self._settings.verify_ignore_scripts,
                max_output_bytes=self._settings.verify_max_output_bytes,
            )

        retry_loop: RetryLoop | None = None
        if verifier is not None and self._settings.retry_max_rounds > 0:
            retry_loop = RetryLoop(
                fixer,
                FixValidator(use_ast_validation=self._settings.fix_validate_syntax),
                verifier,
                max_rounds=self._settings.retry_max_rounds,
            )

        pipeline = FixPipeline(
            fixer,
            validator=FixValidator(use_ast_validation=self._settings.fix_validate_syntax),
            verifier=verifier,
            retry_loop=retry_loop,
        )
        return pipeline.run(scan_result, change, editor)

    def _open_pr(
        self,
        *,
        owner: str,
        name: str,
        installation_id: int,
        base_branch: str,
        change: BreakingChange,
        fix_result: FixPipelineResult,
        edits: list[FileEdit],
        draft: bool,
    ) -> PullRequest:
        write_token = self._gh_auth.installation_token(
            installation_id,
            repositories=(name,),
            permissions={"contents": "write", "pull_requests": "write"},
        )
        head_branch = branch_name_for(change)
        with BranchWriter(write_token.token, owner, name) as writer:
            writer.commit_edits(
                branch=head_branch,
                base_branch=base_branch,
                message=f"depfix: migrate {change.old_api} -> {change.replacement}",
                edits=edits,
            )
        return open_pull_request(
            owner=owner,
            repo=name,
            token=write_token.token,
            head_branch=head_branch,
            base_branch=base_branch,
            title=pr_title_for(change),
            body=build_pr_body(change, fix_result),
            draft=draft,
        )
