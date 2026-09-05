"""Value objects for the classify layer."""

from __future__ import annotations

from dataclasses import dataclass, field

from depfix.core.models import BreakingChange


@dataclass
class ClassifyOutcome:
    """Result of classifying one ``ChangeEvent``.

    ``changes`` and ``errors`` are independent: a spec-diff event with zero
    structural deltas above additive severity is a *successful* classification
    of zero changes, not an error.
    """

    changes: list[BreakingChange] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors
