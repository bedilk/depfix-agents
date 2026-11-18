"""Unit tests for forced-migration classification and deadline parsing."""

from __future__ import annotations

from datetime import date

import pytest
from rich.console import Console

from depfix import cli
from depfix.cli import build_parser
from depfix.core.models import BreakingChange, ChangeKind, ClassificationSource
from depfix.core.urgency import ForcedReason, assess_urgency, find_deadline, urgency_sort_key
from depfix.scanners.matching import ScanChangeAssessment, ScanMatchStatus

TODAY = date(2026, 11, 18)


def _change(
    kind: ChangeKind = ChangeKind.METHOD_RENAMED,
    *,
    source: ClassificationSource = ClassificationSource.RELEASE_NOTES,
    description: str = "",
    evidence: str | None = None,
    migration_guide: str = "",
    old_api: str = "stripe.charges.create",
    new_api: str = "stripe.paymentIntents.create",
    severity: str | None = None,
) -> BreakingChange:
    return BreakingChange(
        package="stripe",
        old_version="14.0.0",
        new_version="15.0.0",
        old_api=old_api,
        new_api=new_api,
        description=description,
        migration_guide=migration_guide,
        kind=kind,
        source=source,
        provider_id="stripe",
        evidence=evidence,
        advisory_severity=severity,
    )


# ── find_deadline ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("The v1 endpoint will be removed on 2027-01-15.", date(2027, 1, 15)),
        ("Sunset date: January 15, 2027", date(2027, 1, 15)),
        ("This API reaches end of life on 15 March 2027.", date(2027, 3, 15)),
        ("After Sept. 1st, 2027, the legacy API will no longer be available.", date(2027, 9, 1)),
        ("Support will be discontinued in March 2027.", date(2027, 3, 1)),
        ("Charges API shuts down 2027/06/30", date(2027, 6, 30)),
        # The cue claims its nearest date, not the earlier deprecation date.
        ("Deprecated on 2024-01-01 and will be removed on 2027-01-15.", date(2027, 1, 15)),
        # Two sunsets: the earliest wins.
        ("v1 is retired on 2027-05-01; v2 is retired on 2028-05-01.", date(2027, 5, 1)),
    ],
)
def test_find_deadline_reads_stated_sunset_dates(text: str, expected: date) -> None:
    assert find_deadline(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        None,
        "Renamed createCharge to createPayment.",
        "Released on 2026-10-01.",  # a date, but nothing stops working
        "Deprecated on 2026-10-01.",  # when the warning started, not a shut-off
        "This method will be removed in a future release.",  # a cue, but no date
        "Removed on 2027-02-30.",  # not a real date
        # The cue is too far from the date to refer to it.
        "The old client is removed. " + "x" * 150 + " Published 2026-10-01.",
    ],
)
def test_find_deadline_ignores_text_without_a_dated_shutoff(text: str | None) -> None:
    assert find_deadline(text) is None


# ── assess_urgency ───────────────────────────────────────────────────────────


def test_security_advisory_is_forced_and_due_now() -> None:
    urgency = assess_urgency(
        _change(
            ChangeKind.SECURITY_ADVISORY, source=ClassificationSource.SECURITY, severity="high"
        ),
        today=TODAY,
    )
    assert urgency.reason is ForcedReason.SECURITY
    assert urgency.why == "security advisory (high)"
    assert urgency.when == "now"


def test_stated_sunset_date_is_forced_with_days_left() -> None:
    urgency = assess_urgency(
        _change(evidence="The Charges API will be removed on 2027-01-15."), today=TODAY
    )
    assert urgency.reason is ForcedReason.DEADLINE
    assert urgency.deadline == date(2027, 1, 15)
    assert urgency.days_left == 58
    assert urgency.when == "2027-01-15 (58 day(s) left)"
    assert not urgency.overdue


def test_past_sunset_date_is_overdue() -> None:
    urgency = assess_urgency(_change(description="Sunset on 2026-11-01."), today=TODAY)
    assert urgency.overdue
    assert urgency.when == "2026-11-01 (overdue by 17 day(s))"


def test_deadline_is_read_from_the_migration_guide_too() -> None:
    urgency = assess_urgency(
        _change(migration_guide="Migrate before the 2027-03-01 shutdown."), today=TODAY
    )
    assert urgency.deadline == date(2027, 3, 1)


def test_removal_from_live_api_is_forced_without_a_date() -> None:
    urgency = assess_urgency(
        _change(
            ChangeKind.METHOD_REMOVED,
            source=ClassificationSource.SPEC_DIFF,
            old_api="POST /v1/charges",
            new_api="",
        ),
        today=TODAY,
    )
    assert urgency.reason is ForcedReason.LIVE_API_REMOVAL
    assert urgency.deadline is None
    assert urgency.when == "now"


def test_removed_sdk_export_is_not_forced_even_though_it_is_a_spec_diff() -> None:
    """SDK export diffs share the SPEC_DIFF source but only bite on upgrade."""
    urgency = assess_urgency(
        _change(
            ChangeKind.METHOD_REMOVED,
            source=ClassificationSource.SPEC_DIFF,
            old_api="supabase.uuid",
            new_api="",
        ),
        today=TODAY,
    )
    assert not urgency.forced


@pytest.mark.parametrize(
    "change",
    [
        # An SDK-level removal only bites when the team chooses to upgrade.
        _change(ChangeKind.METHOD_REMOVED, source=ClassificationSource.LLM_SYNTHESIS, new_api=""),
        _change(ChangeKind.METHOD_RENAMED),
        _change(ChangeKind.METHOD_DEPRECATED, description="Deprecated; use the new client."),
        _change(
            ChangeKind.DEPENDENCY_VERSION_BUMP,
            source=ClassificationSource.REGISTRY,
            old_api="stripe@14.0.0",
            new_api="stripe@15.0.0",
        ),
        # A non-removal spec change (type change) is not a hard stop.
        _change(ChangeKind.PARAM_TYPE_CHANGED, source=ClassificationSource.SPEC_DIFF),
    ],
)
def test_optional_changes_are_not_forced(change: BreakingChange) -> None:
    urgency = assess_urgency(change, today=TODAY)
    assert not urgency.forced
    assert urgency.why == "optional"
    assert urgency.when == "—"


# ── ordering ─────────────────────────────────────────────────────────────────


def test_sort_puts_forced_first_then_earliest_deadline() -> None:
    drift = _change(
        ChangeKind.DEPENDENCY_VERSION_BUMP,
        source=ClassificationSource.REGISTRY,
        old_api="stripe@14.0.0",
        new_api="stripe@15.0.0",
    )
    far = _change(description="Removed on 2027-06-01.", old_api="a")
    near = _change(description="Removed on 2027-01-15.", old_api="b")
    advisory = _change(
        ChangeKind.SECURITY_ADVISORY, source=ClassificationSource.SECURITY, old_api="c"
    )
    overdue = _change(description="Removed on 2026-10-01.", old_api="d")

    ordered = sorted(
        [drift, far, near, advisory, overdue], key=lambda c: urgency_sort_key(c, today=TODAY)
    )
    assert [c.old_api for c in ordered] == ["d", "c", "b", "a", "stripe@14.0.0"]


# ── surfaces: PR body, scan table, CLI flags ─────────────────────────────────


def test_pr_body_states_the_deadline_for_forced_changes() -> None:
    from depfix.core.pipeline import FixPipelineResult
    from depfix.gh.pr import build_pr_body

    def body(change: BreakingChange) -> str:
        result = FixPipelineResult(
            repo_full_name="acme/app",
            breaking_change=change,
            files_scanned=0,
            files_affected=0,
            edits=(),
            total_usages_fixed=0,
            total_cost=0.0,
            total_tokens=0,
            duration_ms=1,
            verification=None,
        )
        return build_pr_body(change, result)

    forced = body(_change(evidence="The Charges API will be removed on 2099-01-15."))
    assert "**Forced migration:** provider announced a sunset date; due 2099-01-15" in forced
    assert "Forced migration" not in body(_change())


def test_forced_table_lists_only_actionable_forced_changes(monkeypatch) -> None:
    recorder = Console(record=True, width=200)
    monkeypatch.setattr(cli, "console", recorder)
    assessments = [
        ScanChangeAssessment(
            _change(description="Removed on 2099-01-15.", old_api="stripe.charges.create"),
            ScanMatchStatus.ACTIONABLE,
            "1 call site",
        ),
        ScanChangeAssessment(  # forced, but this repo does not use it
            _change(description="Removed on 2099-01-15.", old_api="stripe.orders.create"),
            ScanMatchStatus.NO_CALL_SITES,
            "none",
        ),
        ScanChangeAssessment(  # used here, but optional
            _change(old_api="stripe.tokens.create"), ScanMatchStatus.ACTIONABLE, "2 call sites"
        ),
    ]
    assert cli._print_forced_migrations(assessments) == 1
    out = recorder.export_text()
    assert "Forced Migrations" in out
    assert "stripe.charges.create" in out
    assert "2099-01-15" in out
    assert "stripe.orders.create" not in out
    assert "stripe.tokens.create" not in out


def test_forced_table_prints_nothing_when_no_forced_changes(monkeypatch) -> None:
    recorder = Console(record=True, width=200)
    monkeypatch.setattr(cli, "console", recorder)
    assert cli._print_forced_migrations([]) == 0
    assert recorder.export_text() == ""


@pytest.mark.parametrize(
    "argv",
    [
        ["scan", "--path", ".", "--provider", "stripe", "--forced-only"],
        ["plan", "acme/app", "--provider", "stripe", "--forced-only"],
        ["apply", "acme/app", "--forced-only"],
    ],
)
def test_forced_only_flag_is_accepted(argv: list[str]) -> None:
    assert build_parser().parse_args(argv).forced_only is True


def test_forced_only_defaults_to_false() -> None:
    assert build_parser().parse_args(["plan", "acme/app"]).forced_only is False
