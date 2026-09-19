"""Match persisted scan observations to classified upstream changes.

The module is deliberately small at its interface: pass one scan result and
classified changes, receive explainable decisions. It keeps version evidence,
symbol normalization, and confidence filtering out of CLI orchestration.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from depfix.core.models import BreakingChange, ChangeKind
from depfix.scanners.applicability import change_applies
from depfix.scanners.models import CallSite, RepoScanResult
from depfix.scanners.repo import symbols_for_change


class ScanMatchStatus(StrEnum):
    """The result of comparing one classified change with one repo scan."""

    ACTIONABLE = "actionable"
    NO_CALL_SITES = "no_call_sites"
    VERSION_NOT_AFFECTED = "version_not_affected"


@dataclass(frozen=True)
class ScanChangeAssessment:
    """An explainable decision for one ``(repo scan, breaking change)`` pair."""

    change: BreakingChange
    status: ScanMatchStatus
    reason: str
    matched_sites: tuple[CallSite, ...] = ()

    @property
    def is_actionable(self) -> bool:
        return self.status is ScanMatchStatus.ACTIONABLE


def assess_scan_change(
    result: RepoScanResult,
    change: BreakingChange,
    *,
    provider_id: str | None = None,
) -> ScanChangeAssessment:
    """Decide whether a classified change can be planned for this scan.

    Version evidence is checked first. API migrations then require a
    high/medium-confidence call site matching the change's old symbol. A
    dependency version bump is manifest-level and remains actionable when its
    version evidence applies even without a source-level call site.
    """
    applicability = change_applies(result.dependencies, change)
    if applicability.blocks:
        return ScanChangeAssessment(
            change, ScanMatchStatus.VERSION_NOT_AFFECTED, applicability.reason
        )

    if change.kind is ChangeKind.DEPENDENCY_VERSION_BUMP:
        return ScanChangeAssessment(
            change,
            ScanMatchStatus.ACTIONABLE,
            f"dependency version drift: {applicability.reason}",
        )

    symbols = symbols_for_change(provider_id or change.provider_id, change)
    matched = tuple(site for site in result.actionable_sites if _site_matches(site, symbols))
    if matched:
        return ScanChangeAssessment(
            change,
            ScanMatchStatus.ACTIONABLE,
            f"{len(matched)} actionable call site(s) match the old API",
            matched,
        )
    return ScanChangeAssessment(
        change,
        ScanMatchStatus.NO_CALL_SITES,
        "no actionable call sites match the old API",
    )


def assess_scan_changes(
    result: RepoScanResult,
    changes: Iterable[BreakingChange],
    *,
    provider_id: str | None = None,
) -> list[ScanChangeAssessment]:
    """Assess every currently classified change for one provider scan."""
    return [
        assess_scan_change(result, change, provider_id=provider_id) for change in changes
    ]


def _site_matches(site: CallSite, wanted_symbols: tuple[str, ...]) -> bool:
    return any(
        site.symbol == wanted or site.symbol.startswith(f"{wanted}.")
        for wanted in wanted_symbols
    )
