"""Decide whether a breaking change is one a team cannot skip, and by when.

A *forced* migration is one where staying put stops working: a security
advisory, something removed from the provider's live API, or a change whose
text states a sunset date. Everything else (version drift, SDK renames, an
undated deprecation) is optional and can wait.

Pure and deterministic: no LLM, no network, no stored state. Urgency is derived
from fields a ``BreakingChange`` already carries, so it works on every change
already in the database.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from depfix.core.models import REMOVAL_KINDS, BreakingChange, ChangeKind, ClassificationSource


class ForcedReason(StrEnum):
    SECURITY = "security"
    DEADLINE = "deadline"
    LIVE_API_REMOVAL = "live_api_removal"


@dataclass(frozen=True)
class Urgency:
    """Why (and by when) a change must be handled. ``reason is None`` = optional."""

    reason: ForcedReason | None = None
    deadline: date | None = None
    days_left: int | None = None
    severity: str | None = None

    @property
    def forced(self) -> bool:
        return self.reason is not None

    @property
    def overdue(self) -> bool:
        return self.days_left is not None and self.days_left < 0

    @property
    def why(self) -> str:
        """One short human-readable phrase for tables and PR bodies."""
        if self.reason is ForcedReason.SECURITY:
            return f"security advisory ({self.severity})" if self.severity else "security advisory"
        if self.reason is ForcedReason.LIVE_API_REMOVAL:
            return "removed from the provider's live API"
        if self.reason is ForcedReason.DEADLINE:
            return "provider announced a sunset date"
        return "optional"

    @property
    def when(self) -> str:
        """The deadline as text: a date with days left, ``now``, or a dash."""
        if self.deadline is not None and self.days_left is not None:
            if self.days_left < 0:
                return f"{self.deadline.isoformat()} (overdue by {-self.days_left} day(s))"
            if self.days_left == 0:
                return f"{self.deadline.isoformat()} (today)"
            return f"{self.deadline.isoformat()} ({self.days_left} day(s) left)"
        return "now" if self.forced else "—"


_MONTHS = {
    name: number
    for number, names in enumerate(
        (
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ),
        start=1,
    )
    for name in names
}
_MONTH = r"(?P<month>" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?"
_DATE_PATTERNS = (
    re.compile(r"\b(?P<year>20\d{2})[-/](?P<m>\d{1,2})[-/](?P<day>\d{1,2})\b"),
    re.compile(
        rf"\b{_MONTH}\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?,?\s+(?P<year>20\d{{2}})\b", re.IGNORECASE
    ),
    re.compile(
        rf"\b(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+{_MONTH},?\s+(?P<year>20\d{{2}})\b", re.IGNORECASE
    ),
    # "March 2027" with no day: the first of the month, the earliest it can bite.
    re.compile(rf"\b{_MONTH},?\s+(?P<year>20\d{{2}})\b", re.IGNORECASE),
)

# Words that mean "stops working". A bare "deprecated on <date>" is when the
# warning started, not when the thing is switched off, so it is not a cue.
_CUE = re.compile(
    r"sunset|end[- ]of[- ]life|\beol\b|\bremov(?:ed|al|e)\b|retir(?:ed|ement|e)\b|shut(?:s|ting)?\s?down"
    r"|discontinu|decommission|turned? off|switched? off|deadline|stops? working|cease"
    r"|no longer (?:be )?(?:supported|available|accepted|work)",
    re.IGNORECASE,
)
_CUE_REACH = 100  # max characters between a cue and the date it refers to
_HTTP_OPERATION = re.compile(r"^(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+/")


def _dates_in(text: str) -> list[tuple[int, int, date]]:
    """Every parseable date in ``text`` as ``(start, end, date)``, non-overlapping."""
    found: list[tuple[int, int, date]] = []
    for pattern in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            if any(match.start() < end and start < match.end() for start, end, _ in found):
                continue
            groups = match.groupdict()
            month = int(groups["m"]) if groups.get("m") else _MONTHS[groups["month"].lower()]
            try:
                parsed = date(int(groups["year"]), month, int(groups.get("day") or 1))
            except ValueError:
                continue
            found.append((match.start(), match.end(), parsed))
    return found


def find_deadline(text: str | None) -> date | None:
    """The earliest date in ``text`` that a "stops working" phrase points at.

    Each cue claims its nearest date, so "deprecated on 2024-01-01 and will be
    removed on 2027-01-15" yields 2027-01-15, not the deprecation date.
    """
    if not text:
        return None
    dates = _dates_in(text)
    if not dates:
        return None
    claimed: list[date] = []
    for cue in _CUE.finditer(text):
        nearest: tuple[int, date] | None = None
        for start, end, parsed in dates:
            gap = start - cue.end() if start >= cue.end() else cue.start() - end
            if 0 <= gap <= _CUE_REACH and (nearest is None or gap < nearest[0]):
                nearest = (gap, parsed)
        if nearest is not None:
            claimed.append(nearest[1])
    return min(claimed) if claimed else None


def assess_urgency(change: BreakingChange, *, today: date | None = None) -> Urgency:
    """Classify ``change`` as forced or optional, with a deadline when one is stated."""
    today = today or date.today()
    deadline = find_deadline(
        " \n ".join(t for t in (change.description, change.evidence, change.migration_guide) if t)
    )
    days_left = (deadline - today).days if deadline is not None else None

    if change.kind is ChangeKind.SECURITY_ADVISORY:
        return Urgency(ForcedReason.SECURITY, deadline, days_left, change.advisory_severity)
    if deadline is not None:
        return Urgency(ForcedReason.DEADLINE, deadline, days_left)
    # A removed HTTP operation, field or parameter is gone from the provider's
    # hosted API, so callers break whatever SDK version they pin. A removed SDK
    # export carries the same SPEC_DIFF source but only bites on upgrade, which
    # a team can postpone, so the HTTP-operation shape of old_api is the test.
    if (
        change.kind in REMOVAL_KINDS
        and change.source is ClassificationSource.SPEC_DIFF
        and _HTTP_OPERATION.match(change.old_api)
    ):
        return Urgency(ForcedReason.LIVE_API_REMOVAL)
    return Urgency()


def urgency_sort_key(change: BreakingChange, *, today: date | None = None) -> tuple[int, date]:
    """Sort key: forced before optional, then earliest deadline first.

    Forced changes without a date (advisories, live removals) sort as due today.
    """
    today = today or date.today()
    urgency = assess_urgency(change, today=today)
    if not urgency.forced:
        return (1, date.max)
    return (0, urgency.deadline or today)
