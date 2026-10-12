"""Unit tests for repo-version-aware TypeScript export diff.

All external I/O (npm registry, tarball fetching) is mocked — no live network.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from depfix.core.models import ChangeKind, ClassificationSource
from depfix.scanners.matching import ScanMatchStatus, assess_scan_change
from depfix.scanners.models import (
    CallSite,
    CallSiteKind,
    DeclaredDependency,
    MatchConfidence,
    RepoScanResult,
)
from depfix.sources.repo_exports import (
    _call_site_uses_export,
    _export_name_from_symbol,
    _installed_version_for,
    synthetic_changes_for_scan,
)

# ─── helpers ──────────────────────────────────────────────────────────────────


def _dep(
    *,
    package: str = "@sentry/node",
    resolved_version: str | None = "6.19.7",
) -> DeclaredDependency:
    return DeclaredDependency(
        package=package,
        manifest_path="package.json",
        declared_range=f"^{resolved_version}" if resolved_version else "^6.0.0",
        resolved_version=resolved_version,
        source="package-lock.json",
    )


def _site(
    *,
    symbol: str = "sentry.startTransaction",
    provider_id: str = "sentry",
) -> CallSite:
    return CallSite(
        filepath="src/tracing.js",
        line_number=5,
        column=0,
        line_content=f"{symbol}({{}})",
        kind=CallSiteKind.METHOD_CALL,
        confidence=MatchConfidence.HIGH,
        symbol=symbol,
        provider_id=provider_id,
    )


def _scan(
    *,
    symbol: str = "sentry.startTransaction",
    package: str = "@sentry/node",
    resolved_version: str | None = "6.19.7",
) -> RepoScanResult:
    return RepoScanResult(
        repo_full_name="acme/app",
        commit_sha="abc123",
        dependencies=[_dep(package=package, resolved_version=resolved_version)],
        call_sites=[_site(symbol=symbol)],
    )


# ─── _call_site_uses_export ───────────────────────────────────────────────────


def test_call_site_uses_export_exact_match() -> None:
    assert _call_site_uses_export("sentry.startTransaction", "sentry", "startTransaction")


def test_call_site_uses_export_member_prefix() -> None:
    # hub is an export; captureMessage is a method on it
    assert _call_site_uses_export("sentry.hub.captureMessage", "sentry", "hub")


def test_call_site_uses_export_wrong_provider() -> None:
    assert not _call_site_uses_export("stripe.createPaymentIntent", "sentry", "createPaymentIntent")


def test_call_site_uses_export_partial_name_no_match() -> None:
    # "startTransactionLong" shares a prefix with "startTransaction" but must not match
    assert not _call_site_uses_export("sentry.startTransactionLong", "sentry", "startTransaction")


def test_call_site_uses_export_no_provider_prefix() -> None:
    assert not _call_site_uses_export("startTransaction", "sentry", "startTransaction")


# ─── _installed_version_for ──────────────────────────────────────────────────


def test_installed_version_for_returns_resolved() -> None:
    result = _scan(resolved_version="10.75.3")
    assert _installed_version_for(result, "@sentry/node") == "10.75.3"


def test_installed_version_for_missing_package_returns_none() -> None:
    result = _scan()
    assert _installed_version_for(result, "@stripe/stripe-js") is None


def test_installed_version_for_unresolved_returns_none() -> None:
    result = _scan(resolved_version=None)
    assert _installed_version_for(result, "@sentry/node") is None


# ─── synthetic_changes_for_scan ──────────────────────────────────────────────


def test_no_installed_version_returns_empty() -> None:
    result = _scan(resolved_version=None)
    http, npm = MagicMock(), MagicMock()

    changes = synthetic_changes_for_scan(
        result, provider_id="sentry", npm_packages=["@sentry/node"], http=http, npm=npm
    )

    assert changes == []
    http.get.assert_not_called()


def test_no_matching_callsites_returns_empty() -> None:
    # call site uses captureException, removed exports are startTransaction/configureScope
    result = _scan(symbol="sentry.captureException")

    with (
        patch(
            "depfix.sources.repo_exports.repo_version_exports_diff",
            return_value=("11.6.0", {"startTransaction", "configureScope"}),
        ),
        patch(
            "depfix.sources.repo_exports._exports_for_version",
            return_value={
                "captureException",
                "startTransaction",
                "configureScope",
            },  # installed has all three
        ),
    ):
        changes = synthetic_changes_for_scan(
            result,
            provider_id="sentry",
            npm_packages=["@sentry/node"],
            http=MagicMock(),
            npm=MagicMock(),
        )

    assert changes == []


def test_matching_callsite_creates_synthetic_change() -> None:
    result = _scan(symbol="sentry.startTransaction")

    with (
        patch(
            "depfix.sources.repo_exports.repo_version_exports_diff",
            return_value=("11.6.0", {"startTransaction", "configureScope"}),
        ),
        patch(
            "depfix.sources.repo_exports._exports_for_version",
            return_value={"startTransaction", "configureScope"},
        ),
    ):
        changes = synthetic_changes_for_scan(
            result,
            provider_id="sentry",
            npm_packages=["@sentry/node"],
            http=MagicMock(),
            npm=MagicMock(),
        )

    assert len(changes) == 1
    ch = changes[0]
    assert ch.old_api == "sentry.startTransaction"
    assert ch.new_api == ""
    assert ch.kind is ChangeKind.METHOD_REMOVED
    assert ch.source is ClassificationSource.SPEC_DIFF
    assert ch.old_version == "6.19.7"
    assert ch.new_version == "11.6.0"
    assert ch.provider_id == "sentry"
    assert ch.package == "@sentry/node"
    assert ch.confidence == 1.0


def test_multiple_callsites_for_same_export_produces_one_change() -> None:
    result = RepoScanResult(
        repo_full_name="acme/app",
        commit_sha="abc",
        dependencies=[_dep()],
        call_sites=[
            _site(symbol="sentry.startTransaction"),
            _site(symbol="sentry.startTransaction"),
        ],
    )

    with (
        patch(
            "depfix.sources.repo_exports.repo_version_exports_diff",
            return_value=("11.6.0", {"startTransaction"}),
        ),
        patch(
            "depfix.sources.repo_exports._exports_for_version",
            return_value={"startTransaction"},
        ),
    ):
        changes = synthetic_changes_for_scan(
            result,
            provider_id="sentry",
            npm_packages=["@sentry/node"],
            http=MagicMock(),
            npm=MagicMock(),
        )

    assert len(changes) == 1  # deduplicated on old_api


def test_multiple_removed_exports_each_matched_produces_multiple_changes() -> None:
    result = RepoScanResult(
        repo_full_name="acme/app",
        commit_sha="abc",
        dependencies=[_dep()],
        call_sites=[
            _site(symbol="sentry.startTransaction"),
            _site(symbol="sentry.configureScope"),
        ],
    )

    with (
        patch(
            "depfix.sources.repo_exports.repo_version_exports_diff",
            return_value=("11.6.0", {"startTransaction", "configureScope"}),
        ),
        patch(
            "depfix.sources.repo_exports._exports_for_version",
            return_value={"startTransaction", "configureScope"},
        ),
    ):
        changes = synthetic_changes_for_scan(
            result,
            provider_id="sentry",
            npm_packages=["@sentry/node"],
            http=MagicMock(),
            npm=MagicMock(),
        )

    old_apis = {ch.old_api for ch in changes}
    assert old_apis == {"sentry.startTransaction", "sentry.configureScope"}


def test_synthetic_change_is_actionable_via_assess_scan_change() -> None:
    """The key integration: a synthetic change makes assess_scan_change return ACTIONABLE."""
    result = _scan(
        symbol="sentry.startTransaction",
        package="@sentry/node",
        resolved_version="6.19.7",
    )

    with (
        patch(
            "depfix.sources.repo_exports.repo_version_exports_diff",
            return_value=("11.6.0", {"startTransaction"}),
        ),
        patch(
            "depfix.sources.repo_exports._exports_for_version",
            return_value={"startTransaction"},
        ),
    ):
        changes = synthetic_changes_for_scan(
            result,
            provider_id="sentry",
            npm_packages=["@sentry/node"],
            http=MagicMock(),
            npm=MagicMock(),
        )

    assert len(changes) == 1
    assessment = assess_scan_change(result, changes[0], provider_id="sentry")
    assert assessment.status is ScanMatchStatus.ACTIONABLE
    assert len(assessment.matched_sites) == 1


def test_empty_removed_exports_returns_empty_changes() -> None:
    result = _scan()

    with (
        patch(
            "depfix.sources.repo_exports.repo_version_exports_diff",
            return_value=("11.6.0", set()),  # no removals
        ),
        patch(
            "depfix.sources.repo_exports._exports_for_version",
            return_value={"startTransaction"},  # startTransaction present in installed
        ),
    ):
        changes = synthetic_changes_for_scan(
            result,
            provider_id="sentry",
            npm_packages=["@sentry/node"],
            http=MagicMock(),
            npm=MagicMock(),
        )

    assert changes == []


def test_diff_returns_none_skips_gracefully() -> None:
    result = _scan()

    with patch(
        "depfix.sources.repo_exports.repo_version_exports_diff",
        return_value=None,  # network error or already latest
    ):
        changes = synthetic_changes_for_scan(
            result,
            provider_id="sentry",
            npm_packages=["@sentry/node"],
            http=MagicMock(),
            npm=MagicMock(),
        )

    assert changes == []


# ─── _export_name_from_symbol ─────────────────────────────────────────────────


def test_export_name_from_symbol_top_level() -> None:
    assert _export_name_from_symbol("sentry.startTransaction", "sentry") == "startTransaction"


def test_export_name_from_symbol_nested() -> None:
    # "hub" is the top-level export; captureMessage is a method on it
    assert _export_name_from_symbol("sentry.hub.captureMessage", "sentry") == "hub"


def test_export_name_from_symbol_wrong_provider() -> None:
    assert _export_name_from_symbol("stripe.createPaymentIntent", "sentry") is None


def test_export_name_from_symbol_no_prefix() -> None:
    assert _export_name_from_symbol("startTransaction", "sentry") is None


# ─── sub-case B ───────────────────────────────────────────────────────────────


def test_subcaseB_callsite_absent_from_installed_creates_change() -> None:
    """Covers the sentry v6-app scenario: startTransaction removed in v8,
    repo lockfile is v10, code still calls startTransaction."""
    result = _scan(symbol="sentry.startTransaction", resolved_version="10.75.3")

    with (
        patch(
            "depfix.sources.repo_exports.repo_version_exports_diff",
            return_value=("11.6.0", set()),  # empty removed set — sub-case A finds nothing
        ),
        patch(
            "depfix.sources.repo_exports._exports_for_version",
            return_value={"captureException", "addBreadcrumb"},  # no startTransaction
        ),
    ):
        changes = synthetic_changes_for_scan(
            result,
            provider_id="sentry",
            npm_packages=["@sentry/node"],
            http=MagicMock(),
            npm=MagicMock(),
        )

    assert len(changes) == 1
    ch = changes[0]
    assert ch.old_api == "sentry.startTransaction"
    assert ch.kind is ChangeKind.METHOD_REMOVED
    assert ch.old_version == "0.0.0"
    assert ch.new_version == "10.75.3"
    assert ch.confidence == pytest.approx(0.9)
    assert ch.source is ClassificationSource.SPEC_DIFF


def test_subcaseB_export_present_in_installed_no_change() -> None:
    """When the installed version exports the called symbol, sub-case B must not fire."""
    result = _scan(symbol="sentry.captureException", resolved_version="10.75.3")

    with (
        patch(
            "depfix.sources.repo_exports.repo_version_exports_diff",
            return_value=("11.6.0", set()),
        ),
        patch(
            "depfix.sources.repo_exports._exports_for_version",
            return_value={"captureException", "addBreadcrumb"},
        ),
    ):
        changes = synthetic_changes_for_scan(
            result,
            provider_id="sentry",
            npm_packages=["@sentry/node"],
            http=MagicMock(),
            npm=MagicMock(),
        )

    assert changes == []


def test_subcaseB_no_duplicate_when_subcaseA_already_created_change() -> None:
    """Sub-case A and B should not both fire for the same old_api."""
    result = _scan(symbol="sentry.startTransaction", resolved_version="10.75.3")

    # Sub-case A: startTransaction IS in removed_exports (fires sub-case A)
    # Sub-case B: startTransaction absent from installed (would fire sub-case B)
    # Only one change must be produced.
    with (
        patch(
            "depfix.sources.repo_exports.repo_version_exports_diff",
            return_value=("11.6.0", {"startTransaction"}),
        ),
        patch(
            "depfix.sources.repo_exports._exports_for_version",
            return_value=set(),  # startTransaction absent from installed too
        ),
    ):
        changes = synthetic_changes_for_scan(
            result,
            provider_id="sentry",
            npm_packages=["@sentry/node"],
            http=MagicMock(),
            npm=MagicMock(),
        )

    assert len(changes) == 1
    # Sub-case A fires first, so old_version should be installed version not 0.0.0
    assert changes[0].old_version == "10.75.3"


def test_subcaseB_installed_exports_fetch_fails_skips_gracefully() -> None:
    """When _exports_for_version returns None for installed version, sub-case B is skipped."""
    result = _scan(symbol="sentry.startTransaction", resolved_version="10.75.3")

    with (
        patch(
            "depfix.sources.repo_exports.repo_version_exports_diff",
            return_value=("11.6.0", set()),
        ),
        patch(
            "depfix.sources.repo_exports._exports_for_version",
            return_value=None,  # fetch failed
        ),
    ):
        changes = synthetic_changes_for_scan(
            result,
            provider_id="sentry",
            npm_packages=["@sentry/node"],
            http=MagicMock(),
            npm=MagicMock(),
        )

    assert changes == []
