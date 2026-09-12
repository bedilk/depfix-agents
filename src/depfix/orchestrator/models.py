"""Result types for one fleet-orchestrator run.

Mirrors :mod:`depfix.watcher.runner`'s ``FeedReport``/``WatchOutcome``
shape: a flat, serialization-friendly report per unit of work (here, per
``(repo, change)`` pair and per repo), plus a top-level container with a
couple of derived properties for the CLI to summarize.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from depfix.orchestrator.policy import SkipReason
from depfix.storage.schema import AttemptStatus


@dataclass
class ChangeOutcome:
    """What happened when the orchestrator considered one breaking change
    against one repo. Exactly one of ``skip_reason``/``attempt_status`` is
    set: a skip never reaches the point of deciding an ``AttemptStatus``,
    and vice versa.
    """

    dedupe_key: str
    package: str
    old_api: str
    skip_reason: SkipReason | None = None
    attempt_status: AttemptStatus | None = None
    detail: str = ""
    pr_url: str = ""
    #: ``True`` when this outcome describes what the orchestrator *would*
    #: have done under ``--dry-run``, rather than something it actually did
    #: -- no ledger row was written and no branch/PR was created for it.
    planned: bool = False
    #: ``FixPipelineResult.total_cost`` for this change, or 0.0 if no fix
    #: pipeline ran (skipped, or no actionable call sites).
    cost_usd: float = 0.0
    #: Actionable call sites this repo's ``.depfix.yml`` ``paths`` filter
    #: excluded before the fix pipeline ever ran on them -- distinct from
    #: "zero call sites found at all" so a report can tell "nothing to fix"
    #: apart from "found things, but they're out of scope for this repo".
    suppressed_call_sites: int = 0

    @property
    def skipped(self) -> bool:
        return self.skip_reason is not None

    @property
    def is_failure(self) -> bool:
        return self.attempt_status == AttemptStatus.FAILED


@dataclass
class RepoOutcome:
    """What happened for one repo across every breaking change considered.

    ``skip_reason`` is set when the *whole repo* was skipped before any
    per-change check ran (no installation, no ``.depfix.yml``, or an
    invalid one) -- in that case ``changes`` is always empty. ``error`` is
    set when something unexpected blew up outside any single change's own
    try/except (see :meth:`depfix.orchestrator.runner.Orchestrator._run_repo`),
    so one repo's bug can never cost the rest of the fleet run its results.
    """

    repo_full_name: str
    skip_reason: SkipReason | None = None
    changes: list[ChangeOutcome] = field(default_factory=list)
    error: str = ""
    #: Open depfix-authored PR count for this repo as of the *end* of this
    #: repo's run (i.e. after any PRs this run itself opened) -- useful for
    #: a report to explain why later changes hit MAX_OPEN_PRS_REACHED.
    open_pr_count: int = 0

    @property
    def skipped(self) -> bool:
        return self.skip_reason is not None

    @property
    def is_failure(self) -> bool:
        return bool(self.error)

    @property
    def failed_changes(self) -> list[ChangeOutcome]:
        return [c for c in self.changes if c.is_failure]

    @property
    def prs_opened(self) -> list[ChangeOutcome]:
        return [c for c in self.changes if c.attempt_status == AttemptStatus.PR_OPENED]


@dataclass
class OrchestratorOutcome:
    """Everything produced by one :meth:`Orchestrator.run` call, across
    every repo it considered."""

    #: Opaque id for this run, threaded through structured log lines (see
    #: :mod:`depfix.obs.logging`) so every log line and every outcome
    #: printed from the same ``depfix pipeline`` invocation can be
    #: correlated after the fact.
    run_id: str = ""
    repos: list[RepoOutcome] = field(default_factory=list)
    #: ``False`` if the run never started at all because another
    #: orchestrator process already held the advisory lock (see
    #: :mod:`depfix.storage.lock`) -- in that case ``repos`` is always empty.
    locked: bool = True
    #: ``True`` if ``--max-duration`` (see :mod:`depfix.orchestrator.budget`)
    #: elapsed before every requested repo could be processed -- the repos
    #: that *did* run are still complete and correct, this just means the
    #: batch wasn't exhaustive.
    stopped_early: bool = False

    @property
    def failures(self) -> list[RepoOutcome]:
        return [r for r in self.repos if r.is_failure]

    @property
    def prs_opened(self) -> int:
        return sum(len(r.prs_opened) for r in self.repos)

    @property
    def changes_failed(self) -> int:
        return sum(len(r.failed_changes) for r in self.repos)

    @property
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for r in self.repos for c in r.changes)
