"""Pure policy for the Week 6 fleet orchestrator: decides whether to act on
one ``(repo, breaking change)`` pair, and why not when it shouldn't.

Deliberately side-effect-free -- no DB session, no HTTP client -- every
branch here is covered by ``tests/unit/test_orchestrator_policy.py`` without
touching a database or GitHub. :mod:`depfix.orchestrator.runner` is the
thin, mockable shell that gathers the inputs this module needs and acts on
its verdict.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime, timedelta

from depfix.config import Settings
from depfix.core.models import BreakingChange
from depfix.repoconfig.models import RepoConfig
from depfix.storage.schema import AttemptStatus, ChangeAttemptRow


class SkipReason(enum.StrEnum):
    """Why the orchestrator declined to act on a repo, or on one
    ``(repo, change)`` pair. Ordered the same as the checks in
    :func:`decide` / :meth:`~depfix.orchestrator.runner.Orchestrator._run_repo`.
    """

    # -- whole-repo, resolved before any per-change check runs -------------
    NO_INSTALLATION = "no_installation"
    NO_REPO_CONFIG = "no_repo_config"
    INVALID_REPO_CONFIG = "invalid_repo_config"

    # -- tenant instructions: this repo's own .depfix.yml, never bypassable
    #    by --force ---------------------------------------------------------
    TENANT_IGNORED = "tenant_ignored"
    PIPELINE_DISABLED = "pipeline_disabled"
    PROVIDER_NOT_ALLOWED = "provider_not_allowed"

    # -- capability: can depfix act on this at all --------------------------
    UNKNOWN_PROVIDER = "unknown_provider"

    # -- bookkeeping: --force exists specifically to override these --------
    ALREADY_TERMINAL = "already_terminal"
    MAX_ATTEMPTS_REACHED = "max_attempts_reached"
    COOLDOWN_ACTIVE = "cooldown_active"
    NO_CALL_SITES_UNCHANGED = "no_call_sites_unchanged"
    MAX_OPEN_PRS_REACHED = "max_open_prs_reached"
    MAX_CHANGES_PER_RUN_REACHED = "max_changes_per_run_reached"


def effective_max_changes_per_run(repo_config: RepoConfig, settings: Settings) -> int:
    """A repo's own ``max_changes_per_run`` can only lower the fleet-wide
    ``pipeline_max_changes_per_repo`` cap, never raise it -- see
    :class:`depfix.config.Settings`'s docstring for that field."""
    if repo_config.max_changes_per_run is None:
        return settings.pipeline_max_changes_per_repo
    return min(repo_config.max_changes_per_run, settings.pipeline_max_changes_per_repo)


def decide(
    *,
    repo_config: RepoConfig,
    change: BreakingChange,
    known_provider_ids: frozenset[str],
    attempt: ChangeAttemptRow | None,
    current_ref_sha: str,
    open_pr_count: int,
    changes_processed_this_run: int,
    settings: Settings,
    force: bool = False,
) -> SkipReason | None:
    """``None`` means "go ahead and process this change"; otherwise the
    reason not to.

    Check order is deliberate: tenant instructions (this repo's own
    ``.depfix.yml``) are unconditional and never bypassable by ``force``;
    then a capability check (can depfix even act on this provider at all);
    then bookkeeping (the idempotency ledger, rate limits) which ``force``
    exists specifically to override.
    """
    # -- tenant instructions: never bypassable ------------------------------
    if repo_config.is_ignored(provider_id=change.provider_id, dedupe_key=change.dedupe_key):
        return SkipReason.TENANT_IGNORED
    if not repo_config.enabled:
        return SkipReason.PIPELINE_DISABLED
    if not repo_config.providers.allows(change.provider_id):
        return SkipReason.PROVIDER_NOT_ALLOWED

    # -- capability: can we act on this at all ------------------------------
    if change.provider_id not in known_provider_ids:
        return SkipReason.UNKNOWN_PROVIDER

    # -- bookkeeping: force-bypassable ---------------------------------------
    if not force:
        if attempt is not None and AttemptStatus(attempt.status).is_terminal:
            return SkipReason.ALREADY_TERMINAL
        if attempt is not None and attempt.attempts_used >= settings.pipeline_max_attempts:
            return SkipReason.MAX_ATTEMPTS_REACHED
        if (
            attempt is not None
            and attempt.status == AttemptStatus.NO_CALL_SITES.value
            and current_ref_sha
            and attempt.last_checked_ref_sha == current_ref_sha
        ):
            return SkipReason.NO_CALL_SITES_UNCHANGED
        if attempt is not None and _cooldown_active(attempt, settings):
            return SkipReason.COOLDOWN_ACTIVE
        if open_pr_count >= settings.pipeline_max_open_prs:
            return SkipReason.MAX_OPEN_PRS_REACHED
        if changes_processed_this_run >= effective_max_changes_per_run(repo_config, settings):
            return SkipReason.MAX_CHANGES_PER_RUN_REACHED

    return None


def _cooldown_active(attempt: ChangeAttemptRow, settings: Settings) -> bool:
    """True if ``attempt`` was touched too recently to retry yet -- so a
    flaky failure doesn't get hammered on every cron tick."""
    if settings.pipeline_retry_cooldown_hours <= 0:
        return False
    updated_at = attempt.updated_at
    if updated_at.tzinfo is None:
        # SQLite (the test/dev default DATABASE_URL) doesn't actually
        # persist tzinfo even though the column is DateTime(timezone=True)
        # -- every value this process itself wrote via `_utcnow()` was UTC.
        updated_at = updated_at.replace(tzinfo=UTC)
    elapsed = datetime.now(UTC) - updated_at
    return elapsed < timedelta(hours=settings.pipeline_retry_cooldown_hours)
