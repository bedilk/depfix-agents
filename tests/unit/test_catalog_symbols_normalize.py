"""Every catalog migration must normalize to at least one scanner symbol.

This is the guard that would have caught the hyphenated-provider bug before
$14 of LLM spend: ``google-cloud.bucket.setCorsConfiguration`` used to
normalize to ``None``, so ``symbols_for_change`` returned ``()`` and every
GCS/vercel-ai/aws-s3 change was ``NO_CALL_SITES`` by construction.

Deterministic, no LLM, no clone.
"""

from __future__ import annotations

import pytest

from depfix.catalog import canonical_providers_file
from depfix.classify.spec_rules import classify_spec_changes
from depfix.core.models import ChangeKind
from depfix.providers.loader import load_providers_file
from depfix.scanners.repo import symbols_for_change
from depfix.sources.models import Severity, SpecChange, SpecChangeKind

_NON_SYMBOL_KINDS = {ChangeKind.DEPENDENCY_VERSION_BUMP, ChangeKind.SECURITY_ADVISORY}


def _catalog_changes():
    path = canonical_providers_file()
    if path is None:
        return
    for provider in load_providers_file(path):
        for feed in provider.feeds:
            spec_changes_raw = feed.config.get("spec_changes") or []
            parsed = []
            for item in spec_changes_raw:
                if not isinstance(item, dict) or not item.get("kind"):
                    continue
                try:
                    parsed.append(SpecChange(
                        kind=SpecChangeKind(item["kind"]),
                        severity=Severity(item.get("severity", "breaking")),
                        subject=item["subject"],
                        pointer=item.get("pointer", item["subject"]),
                        detail=item.get("detail", ""),
                        direction=item.get("direction", "n/a"),
                        before=item.get("before"),
                        after=item.get("after"),
                    ))
                except (ValueError, KeyError):
                    pass  # skip unknown kinds (e.g. param_renamed not in SpecChangeKind)
            if not parsed:
                continue
            for change in classify_spec_changes(
                parsed,
                package=provider.id,
                old_version=str(feed.config.get("old_token", "")),
                new_version=str(feed.config.get("new_token", "")),
                provider_id=provider.id,
                source_url=None,
            ):
                yield provider.id, change


def test_every_catalog_change_yields_at_least_one_scanner_symbol() -> None:
    failures = []
    for provider_id, change in _catalog_changes():
        if change.kind in _NON_SYMBOL_KINDS:
            continue
        syms = symbols_for_change(provider_id, change)
        if not syms:
            failures.append(f"{provider_id}: {change.old_api!r} → no scanner symbol")
    assert not failures, "catalog entries that normalize to nothing:\n" + "\n".join(failures)
