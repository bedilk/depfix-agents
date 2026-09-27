"""Shared, deterministic shortcuts for the streamlined CLI workflow.

The public CLI can ask for a provider without making callers manually stitch
together ``watch``, ``classify``, and a database lookup. This module keeps
that sequence at one seam so scan and plan select changes consistently.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from sqlalchemy import select

from depfix.classify import Classifier, breaking_change_from_row, classify_pending
from depfix.core.models import BreakingChange
from depfix.providers.loader import load_providers_file
from depfix.scanners.manifest import range_allows_major
from depfix.scanners.models import DeclaredDependency
from depfix.sources.factory import SourceDeps
from depfix.sources.models import ChangeEvent, Severity, SourceKind
from depfix.sources.semver import parse_semver
from depfix.storage import BreakingChangeRow, ChangeEventRow, FeedState, init_schema, session_scope
from depfix.watcher.runner import Watcher

logger = logging.getLogger(__name__)


def ensure_changes_detected(
    provider_id: str,
    *,
    providers_file: str,
    completer: object | None = None,
    min_confidence: float = 0.5,
) -> int:
    """Persist one provider's newly observed upstream migrations.

    Repository usage is recorded separately by ``scan``. A bundled catalog
    never injects a migration into this path: only provider feeds can make a
    source usage actionable.
    """
    providers = load_providers_file(providers_file)
    target = [provider for provider in providers if provider.id == provider_id]
    if not target:
        logger.warning("provider %r not found in %s", provider_id, providers_file)
        return 0

    init_schema()
    with SourceDeps.from_settings() as deps:
        outcome = Watcher(deps=deps, dry_run=False).run_once(target)
    logger.info(
        "watch: %d feed(s), %d event(s) for %s",
        outcome.feeds_polled,
        len(outcome.events),
        provider_id,
    )

    with session_scope() as session:
        summary = classify_pending(
            session,
            Classifier(completer, min_confidence=min_confidence),
            provider_id=provider_id,
        )
    logger.info(
        "classify: %d processed, %d breaking change(s) created for %s",
        summary.events_processed,
        summary.changes_created,
        provider_id,
    )
    return summary.changes_created


def latest_change_for_provider(provider_id: str) -> tuple[BreakingChange | None, int | None]:
    """Return the newest classified change and row ID for ``provider_id``."""
    init_schema()
    with session_scope() as session:
        row = session.scalar(
            select(BreakingChangeRow)
            .where(BreakingChangeRow.provider_id == provider_id)
            .order_by(BreakingChangeRow.created_at.desc())
            .limit(1)
        )
        if row is None:
            return None, None
        return breaking_change_from_row(row), row.id


def all_changes_for_provider(provider_id: str) -> list[BreakingChange]:
    """Return every classified migration for one provider, newest first."""
    init_schema()
    with session_scope() as session:
        rows = session.scalars(
            select(BreakingChangeRow)
            .where(BreakingChangeRow.provider_id == provider_id)
            .order_by(BreakingChangeRow.created_at.desc())
        ).all()
        return [breaking_change_from_row(row) for row in rows]


def capture_repository_dependency_drift(
    provider_id: str,
    *,
    repository: str,
    dependencies: list[DeclaredDependency],
    package_ecosystems: Mapping[str, str | Sequence[str]],
) -> int:
    """Persist drift observed *for this repository scan*.

    Feed polling deliberately treats its first observation as a baseline: it
    has no previous upstream version to compare.  A repository scan does have
    an independent old side, however -- the SDK version resolved by that
    repository's lockfile.  This function joins those two observations and
    records a normal registry ``ChangeEvent`` only when they differ.

    The interface is intentionally narrow: callers supply observed
    dependencies and the provider's package/ecosystem mapping; this module
    hides feed-key lookup, idempotency, and deterministic classification.
    It never invents an API migration from a version gap. The downstream
    dependency-drift policy decides whether a detected version update can be
    edited automatically or only proposed as a human-review draft.
    """
    relevant = [dependency for dependency in dependencies if dependency.package in package_ecosystems]
    if not relevant:
        return 0

    init_schema()
    with session_scope() as session:
        states = {
            state.feed_key: state
            for state in session.scalars(
                select(FeedState).where(FeedState.provider_id == provider_id)
            )
        }
        created = 0
        for dependency in relevant:
            ecosystem = _ecosystem_for_dependency(
                dependency, package_ecosystems[dependency.package]
            )
            if ecosystem is None:
                continue
            feed_key, source_kind, source_url = _registry_feed_details(
                dependency.package, ecosystem
            )
            latest = states.get(feed_key)
            if latest is None or not latest.last_token:
                continue
            installed = _observed_version(dependency, latest.last_token)
            if installed is None:
                continue
            if installed == latest.last_token:
                continue

            # A scan's installed version is the old side of this event.  Keep
            # it in the feed key so two repositories with different pinned
            # versions cannot overwrite each other's evidence in the global
            # event table.
            repo_key = hashlib.sha256(repository.encode("utf-8")).hexdigest()[:12]
            event = ChangeEvent(
                provider_id=provider_id,
                feed_key=f"{feed_key}:repo:{repo_key}:installed:{installed}",
                source_kind=source_kind,
                source_url=source_url.format(package=dependency.package, version=latest.last_token),
                old_token=installed,
                new_token=latest.last_token,
                title=f"{dependency.package} {installed} → {latest.last_token}",
                summary=(
                    "Repository lockfile version differs from the latest provider feed "
                    "snapshot"
                ),
                severity=Severity.UNKNOWN,
            )
            if session.scalar(
                select(ChangeEventRow.id).where(ChangeEventRow.dedupe_key == event.dedupe_key)
            ) is not None:
                continue
            session.add(
                ChangeEventRow(
                    provider_id=event.provider_id,
                    feed_key=event.feed_key,
                    source_kind=event.source_kind.value,
                    source_url=event.source_url,
                    old_token=event.old_token,
                    new_token=event.new_token,
                    title=event.title,
                    summary=event.summary,
                    severity=event.severity.value,
                    dedupe_key=event.dedupe_key,
                    detected_at=event.detected_at,
                )
            )
            created += 1

        if not created:
            return 0
        # Registry events classify deterministically and never invoke an LLM.
        classify_pending(session, Classifier(), provider_id=provider_id)
        return created


def _ecosystem_for_dependency(
    dependency: DeclaredDependency,
    configured: str | Sequence[str],
) -> str | None:
    """Choose the registry matching the scanned manifest, never list order.

    A provider can expose identically named npm and PyPI packages (Stripe is
    one example).  The manifest path is the authoritative ecosystem signal;
    choosing the last duplicate package from providers.yaml corrupts the
    resulting drift record and prevents the manifest writer from targeting it.
    """
    choices = (configured,) if isinstance(configured, str) else tuple(configured)
    name = Path(dependency.manifest_path).name
    preferred = (
        "npm" if name == "package.json"
        else "pypi" if name in {"pyproject.toml", "requirements.txt", "Pipfile"}
        else "rubygems" if name in {"Gemfile", "*.gemspec"}
        else None
    )
    if preferred in choices:
        return preferred
    return choices[0] if len(choices) == 1 else None


def _registry_feed_details(package: str, ecosystem: str) -> tuple[str, SourceKind, str]:
    """Return the canonical feed-state key for a supported registry SDK."""
    if ecosystem == "pypi":
        return (f"pypi:{package}", SourceKind.PYPI_DIST_TAG, "https://pypi.org/project/{package}/{version}/")
    if ecosystem in ("rubygems", "gem"):
        return (f"rubygems:{package}", SourceKind.RUBYGEMS_DIST_TAG, "https://rubygems.org/gems/{package}/versions/{version}")
    return (f"npm:{package}:latest", SourceKind.NPM_DIST_TAG, "https://www.npmjs.com/package/{package}/v/{version}")


_EXACT_SEMVER = re.compile(r"^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def _observed_version(dependency: DeclaredDependency, feed_version: str) -> str | None:
    """Return lockfile evidence, or an exact manifest pin when available.

    An exact pin such as ``6.16.0`` is evidence of the installed side of a
    drift comparison even in a repository without a committed lockfile.
    A caret/tilde range is also sufficient when it *cannot* resolve the
    feed's newer major.  Its lower bound is not claimed to be the installed
    patch; it is durable evidence that the repository is on the old major,
    which is enough to create a human-review drift record after fresh init.
    Ranges that could already resolve the feed major remain unknown.
    """
    if dependency.resolved_version:
        return dependency.resolved_version
    declared = dependency.declared_range or ""
    if _EXACT_SEMVER.fullmatch(declared):
        return declared
    feed = parse_semver(feed_version)
    lower_bound = re.fullmatch(r"[~^]?(v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)", declared.strip())
    if feed is None or lower_bound is None:
        return None
    if range_allows_major(declared, feed[0]) is not False:
        return None
    return lower_bound.group(1)
