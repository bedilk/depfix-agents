"""The Week 6/7 fleet orchestrator: unattended scan -> fix -> verify -> PR
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

Week 7 hardening on top of the Week 6 shape:

- Disabled providers (``ProviderSpec.enabled=False``) are filtered out of
  the known-provider set at construction time, not just skipped later --
  a disabled provider must behave as fully unknown to the orchestrator.
- Each ``(repo, change)`` pair gets its own DB transaction (one
  ``session_scope()`` per change), not one long-lived session for the
  whole repo -- a failure on change 5 can no longer leave change 6's
  session in a half-committed state, and a slow clone/fix/verify/PR round
  trip for one change no longer holds a transaction open for every other
  change behind it.
- A repo's ``.depfix.yml`` ``paths`` filter is applied to the scan result
  *before* the fix pipeline runs, not just to the already-fixed edits
  right before opening a PR -- an out-of-scope file no longer costs an
  LLM call just to have its result discarded.
- A single Postgres advisory lock (see :mod:`depfix.storage.lock`) and an
  optional wall-clock budget (see :mod:`depfix.orchestrator.budget`) keep
  two overlapping cron ticks from racing each other and keep one run from
  running past its window. That same budget also tracks cumulative LLM
  spend (``Settings.pipeline_max_cost_usd_per_run``), so a run can stop
  early on either ceiling, not just the clock.
- A ``no_pr`` override forces every repo's *effective* open-PR decision to
  ``False`` for one run, independent of ``dry_run`` and of what that
  repo's own ``.depfix.yml`` says -- the middle rung of the onboarding
  rehearsal ladder (``--dry-run`` -> ``--no-pr`` -> ``draft_pr: true`` ->
  live).
"""

from __future__ import annotations

import contextlib
import dataclasses
import logging
from collections.abc import Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from depfix.apply.models import EditVerdict, FileEdit
from depfix.apply.workspace import WorkspaceEditor
from depfix.clone import Checkout, CloneService
from depfix.config import Settings
from depfix.core.fix_service import FixServiceResult, run_fix_for_change
from depfix.core.models import BreakingChange
from depfix.core.pipeline import FixPipelineResult
from depfix.verify.confidence import ConfidenceTier
from depfix.fixers.gemini import FixGenerator
from depfix.fixers.ollama import OllamaFixGenerator
from depfix.gh import (
    BRANCH_PREFIX,
    BranchWriter,
    GitHubAppAuth,
    GitHubAppError,
    PullRequest,
    branch_name_for,
    build_pr_body,
    open_pull_request,
    pr_title_for,
)
from depfix.obs.logging import log_context
from depfix.orchestrator.budget import RunBudget
from depfix.orchestrator.models import ChangeOutcome, OrchestratorOutcome, RepoOutcome
from depfix.orchestrator.plan import PlanArtifact
from depfix.orchestrator.policy import SkipReason, decide
from depfix.providers.models import ProviderSpec
from depfix.repoconfig.loader import RepoConfigError, parse_repo_config
from depfix.repoconfig.models import SUPPORTED_VERSION, RepoConfig
from depfix.scanners import CallSiteScanner, build_scan_target, scan_checkout, upsert_repo
from depfix.scanners.models import RepoScanResult
from depfix.storage import (
    AttemptStatus,
    ChangeAttemptRow,
    attempts_for_repo,
    get_engine,
    init_schema,
    record_change_attempt,
    record_fix_run,
    record_pull_request,
    session_scope,
    touch_no_call_sites,
)
from depfix.storage.lock import advisory_lock

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
        dry_run: bool = False,
        no_pr: bool = False,
        use_lock: bool = True,
        max_duration_seconds: float | None = None,
        max_cost_usd: float | None = None,
        plan_artifacts: dict[tuple[str, str], PlanArtifact] | None = None,
    ) -> None:
        self._settings = settings
        self._gh_auth = gh_auth
        self._clone_service = clone_service
        # Disabled providers are dropped here, not just skipped later --
        # `known_provider_ids` (what `decide()` treats as "capable of
        # acting on") must never include them.
        self._providers = {p.id: p for p in providers if p.enabled}
        self._known_provider_ids = frozenset(self._providers)
        self._fixer_factory = fixer_factory
        self._force = force
        self._dry_run = dry_run
        self._no_pr = no_pr
        self._use_lock = use_lock
        self._max_duration_seconds = max_duration_seconds
        self._max_cost_usd = max_cost_usd
        self._plan_artifacts = plan_artifacts or {}
        self._budget = RunBudget(None)  # replaced at the top of every run()

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
        outcome = OrchestratorOutcome(run_id=uuid4().hex)
        engine = get_engine()
        lock_ctx = advisory_lock(engine) if self._use_lock else contextlib.nullcontext(True)

        with log_context(run_id=outcome.run_id), lock_ctx as acquired:
            if not acquired:
                outcome.locked = False
                return outcome

            self._budget = RunBudget(
                self._max_duration_seconds,
                (
                    self._settings.pipeline_max_cost_usd_per_run
                    if self._max_cost_usd is None
                    else self._max_cost_usd
                ),
            )
            for repo_full_name in repo_full_names:
                if self._budget.expired:
                    logger.warning("max-duration budget exhausted; stopping run early")
                    outcome.stopped_early = True
                    break
                try:
                    outcome.repos.append(self._run_repo(repo_full_name, changes))
                except Exception as exc:
                    logger.exception("repo %s failed", repo_full_name)
                    outcome.repos.append(RepoOutcome(repo_full_name=repo_full_name, error=str(exc)))
        return outcome

    def _run_repo(self, repo_full_name: str, changes: list[BreakingChange]) -> RepoOutcome:
        with log_context(repo=repo_full_name):
            return self._run_repo_body(repo_full_name, changes)

    def _run_repo_body(self, repo_full_name: str, changes: list[BreakingChange]) -> RepoOutcome:
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
            # Dry runs and --no-pr runs never create a PR, so they must not
            # require the GitHub App's Pull requests permission merely to
            # inspect the open-PR cap. The same applies to a repository that
            # explicitly opted out of PR creation in .depfix.yml.
            should_inspect_prs = not self._dry_run and not self._no_pr and repo_config.open_pr
            open_prs = (
                self._gh_auth.list_open_pull_requests(owner, name, base=base_branch)
                if should_inspect_prs
                else []
            )
        except GitHubAppError as exc:
            return RepoOutcome(repo_full_name=repo_full_name, error=str(exc))
        open_pr_count = sum(1 for pr in open_prs if pr.head_branch.startswith(BRANCH_PREFIX))

        with session_scope() as session:
            upsert_repo(
                session,
                full_name=repo_full_name,
                owner=owner,
                name=name,
                installation_id=installation.id,
                default_branch=base_branch,
            )
            attempts = attempts_for_repo(session, repo_id=repo_full_name)

        change_outcomes: list[ChangeOutcome] = []
        changes_processed = 0
        stopped_early = False

        for change in changes:
            if self._budget.expired:
                stopped_early = True
                break

            attempt = attempts.get(change.dedupe_key)
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
            # One transaction per change -- a failure (or crash) while
            # processing this change commits or rolls back only this
            # change's own ledger write, never a prior change's already
            # -committed work in the same repo.
            with session_scope() as session:
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
                    attempt=attempt,
                )
            change_outcomes.append(change_outcome)
            self._budget.record_cost(change_outcome.cost_usd)
            if change_outcome.attempt_status == AttemptStatus.PR_OPENED:
                open_pr_count += 1

        if stopped_early:
            logger.warning(
                "max-duration budget exhausted mid-repo for %s; %d/%d changes considered",
                repo_full_name,
                changes_processed,
                len(changes),
            )

        return RepoOutcome(
            repo_full_name=repo_full_name, changes=change_outcomes, open_pr_count=open_pr_count
        )

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
        attempt: ChangeAttemptRow | None,
    ) -> ChangeOutcome:
        """Scan, fix, verify, and (if configured) open a PR for one
        ``(repo, change)`` pair -- isolated so one change's bug can't cost
        the rest of this repo's run its results (see :meth:`_run_repo`).

        Under ``dry_run``, every branch below still runs the real
        scan/fix/verify pipeline (so the reported outcome reflects what
        would really happen) but skips every DB write, branch commit, and
        PR creation -- ``planned=True`` on the returned outcome marks it as
        a prediction, not a completed action.
        """
        # `attempt.attempts_used` counts attempts already recorded for this
        # change; +1 names *this* attempt, so log lines read "attempt 1" on
        # a change's first try, not "attempt 0".
        attempt_number = (attempt.attempts_used if attempt else 0) + 1
        with log_context(dedupe_key=change.dedupe_key, attempt=attempt_number):
            return self._process_change_body(
                session,
                owner=owner,
                name=name,
                repo_full_name=repo_full_name,
                installation_id=installation_id,
                change=change,
                repo_config=repo_config,
                base_branch=base_branch,
                current_ref_sha=current_ref_sha,
            )

    def _process_change_body(
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

            # Repo-scoped path filter applies *before* any fix is
            # generated -- an out-of-scope file shouldn't cost an LLM call
            # just to have its edit discarded later.
            before_actionable = len(scan_result.actionable_sites)
            scan_result = dataclasses.replace(
                scan_result,
                call_sites=[
                    site for site in scan_result.call_sites if repo_config.paths.allows(site.filepath)
                ],
            )
            suppressed_call_sites = before_actionable - len(scan_result.actionable_sites)

            if not scan_result.actionable_sites:
                if not self._dry_run:
                    touch_no_call_sites(
                        session,
                        repo_id=repo_full_name,
                        dedupe_key=change.dedupe_key,
                        ref_sha=current_ref_sha,
                    )
                outcome.attempt_status = AttemptStatus.NO_CALL_SITES
                outcome.suppressed_call_sites = suppressed_call_sites
                outcome.detail = (
                    "no actionable call sites"
                    if not suppressed_call_sites
                    else f"no actionable call sites after paths filter ({suppressed_call_sites} suppressed)"
                )
                outcome.planned = self._dry_run
                return outcome

            artifact = self._plan_artifacts.get((repo_full_name, change.dedupe_key))
            plan_digest = ""
            if artifact is not None:
                if artifact.base_sha != current_ref_sha:
                    raise ValueError(
                        "plan artifact is stale: repository HEAD changed since plan; run plan again"
                    )
                plan_digest = artifact.digest
                fix_service_result = self._apply_plan_artifact(checkout, scan_result, change, artifact)
            else:
                fix_service_result = self._run_fix_pipeline(checkout, scan_result, change, repo_config)
            fix_result = fix_service_result.pipeline_result
            outcome.cost_usd = fix_result.total_cost
            outcome.suppressed_call_sites = suppressed_call_sites

            committable = fix_service_result.committable
            if self._dry_run:
                if not committable:
                    from depfix.core.explain import format_rejections

                    outcome.attempt_status = AttemptStatus.NO_KEPT_EDITS
                    outcome.detail = format_rejections(fix_result)
                    outcome.planned = True
                    return outcome
                outcome.attempt_status = (
                    AttemptStatus.PR_OPENED if repo_config.open_pr else AttemptStatus.FIXED_NO_PR
                )
                outcome.plan_artifact = PlanArtifact.from_result(
                    repo_full_name, current_ref_sha, fix_result
                )
                paths = ", ".join(edit.relpath for edit in committable)
                outcome.detail = f"[dry-run] verified {len(committable)} file(s): {paths}"
                outcome.planned = True
                return outcome

            # --no-pr forces this decision to False for the whole run,
            # regardless of what this repo's own .depfix.yml says -- see
            # `self._no_pr`.
            effective_open_pr = repo_config.open_pr and not self._no_pr
            if effective_open_pr:
                if not committable:
                    from depfix.core.explain import format_rejections

                    detail = format_rejections(fix_result)
                    record_change_attempt(
                        session,
                        repo_id=repo_full_name,
                        dedupe_key=change.dedupe_key,
                        status=AttemptStatus.NO_KEPT_EDITS,
                        last_error=detail,
                        ref_sha=current_ref_sha,
                    )
                    outcome.attempt_status = AttemptStatus.NO_KEPT_EDITS
                    outcome.detail = detail
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
                    escalated=fix_service_result.escalated,
                    plan_digest=plan_digest,
                )
                # Bound for the rest of this change's log lines -- e.g. the
                # ledger writes below -- now that a PR actually exists to
                # point at.
                with log_context(pr_url=pr.html_url):
                    run_row = record_fix_run(
                        session,
                        repo_full_name=repo_full_name,
                        owner=owner,
                        name=name,
                        result=fix_result,
                        installation_id=installation_id,
                        default_branch=base_branch,
                        escalated=fix_service_result.escalated,
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
                escalated=fix_service_result.escalated,
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
            if not self._dry_run:
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
            outcome.planned = self._dry_run
            return outcome
        finally:
            if checkout is not None:
                self._clone_service.cleanup(checkout)

    def _apply_plan_artifact(
        self, checkout: Checkout, scan_result: RepoScanResult, change: BreakingChange, artifact: PlanArtifact
    ) -> FixServiceResult:
        editor = WorkspaceEditor(checkout)
        edits: list[FileEdit] = []
        for planned in artifact.edits:
            path = checkout.path / planned.relpath
            actual = path.read_text(encoding="utf-8")
            if actual != planned.original_content:
                raise ValueError(f"plan artifact is stale: {planned.relpath} no longer matches its planned base")
            edit = editor.write_fix(
                planned.relpath, planned.fixed_content,
                confidence=planned.confidence, usages_fixed=planned.usages_fixed,
            )
            edits.append(dataclasses.replace(edit, verdict=EditVerdict.KEPT, diff=planned.diff))
        result = FixPipelineResult(
            repo_full_name=scan_result.repo_full_name, breaking_change=change,
            files_scanned=scan_result.files_scanned, files_affected=len(edits), edits=tuple(edits),
            total_usages_fixed=sum(e.usages_fixed for e in edits), total_cost=0.0, total_tokens=0,
            duration_ms=0, verification=None,
        )
        return FixServiceResult(pipeline_result=result, committable=edits, verify_required=True)

    def _run_fix_pipeline(
        self,
        checkout: Checkout,
        scan_result: RepoScanResult,
        change: BreakingChange,
        repo_config: RepoConfig,
    ) -> FixServiceResult:
        fixer = self._fixer_factory()
        return run_fix_for_change(
            checkout=checkout,
            scan_result=scan_result,
            change=change,
            settings=self._settings,
            repo_config=repo_config,
            fixer=fixer,
        )

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
        escalated: bool = False,
        plan_digest: str = "",
    ) -> PullRequest:
        write_token = self._gh_auth.installation_token(
            installation_id,
            repositories=(name,),
            permissions={"contents": "write", "pull_requests": "write"},
        )
        head_branch = branch_name_for(change)
        with BranchWriter(
            write_token.token, owner, name, api_url=self._settings.github_api_url
        ) as writer:
            writer.commit_edits(
                branch=head_branch,
                base_branch=base_branch,
                message=f"depfix: migrate {change.old_api} -> {change.replacement}",
                edits=edits,
            )
        confidence_floor = ConfidenceTier(self._settings.draft_below_confidence)
        auto_draft = not fix_result.confidence.at_least(confidence_floor)
        pr = open_pull_request(
            owner=owner,
            repo=name,
            token=write_token.token,
            head_branch=head_branch,
            base_branch=base_branch,
            title=pr_title_for(change),
            body=build_pr_body(
                change,
                fix_result,
                edits=edits,
                escalated=escalated,
                plan_digest=plan_digest,
            ),
            draft=draft or auto_draft,
            api_url=self._settings.github_api_url,
        )
        from depfix.gh import apply_pr_labels

        apply_pr_labels(
            owner=owner,
            repo=name,
            pr_number=pr.number,
            labels=[f"depfix:confidence={fix_result.confidence.value}"],
            token=write_token.token,
            api_url=self._settings.github_api_url,
        )
        return pr
