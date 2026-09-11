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

    repos: list[RepoOutcome] = field(default_factory=list)

    @property
    def failures(self) -> list[RepoOutcome]:
        return [r for r in self.repos if r.is_failure]

    @property
    def prs_opened(self) -> int:
        return sum(len(r.prs_opened) for r in self.repos)

    @property
    def changes_failed(self) -> int:
        return sum(len(r.failed_changes) for r in self.repos)
