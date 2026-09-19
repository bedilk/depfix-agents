"""Shared, deterministic shortcuts for the streamlined CLI workflow.

The public CLI can ask for a provider without making callers manually stitch
together ``watch``, ``classify``, and a database lookup. This module keeps
that sequence at one seam so scan and plan select changes consistently.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from depfix.catalog import canonical_providers_file
from depfix.classify import Classifier, breaking_change_from_row, classify_pending
from depfix.core.models import BreakingChange
from depfix.providers.loader import load_providers_file
from depfix.sources.factory import SourceDeps
from depfix.storage import BreakingChangeRow, init_schema, session_scope
from depfix.watcher.runner import Watcher

logger = logging.getLogger(__name__)


def ensure_changes_detected(provider_id: str, *, providers_file: str) -> int:
    """Persist one provider's new or canonical historical migrations.

    Upstream feeds always run first. If they emit nothing and there is no
    classified record yet, a bundled catalog supplies known historical SDK
    migrations that a first poll cannot observe.
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
        summary = classify_pending(session, Classifier(None), provider_id=provider_id)
    logger.info(
        "classify: %d processed, %d breaking change(s) created for %s",
        summary.events_processed,
        summary.changes_created,
        provider_id,
    )
    if summary.changes_created:
        return summary.changes_created

    with session_scope() as session:
        existing = session.scalar(
            select(BreakingChangeRow.id)
            .where(BreakingChangeRow.provider_id == provider_id)
            .limit(1)
        )
    if existing is not None:
        return 0

    catalog_file = canonical_providers_file()
    if catalog_file is None:
        return 0
    catalog_providers = load_providers_file(catalog_file)
    catalog_target = [provider for provider in catalog_providers if provider.id == provider_id]
    if not catalog_target:
        return 0

    logger.info("upstream feeds found no new events for %s; using migration catalog", provider_id)
    with SourceDeps.from_settings() as deps:
        outcome = Watcher(deps=deps, dry_run=False).run_once(catalog_target)
    logger.info(
        "catalog watch: %d feed(s), %d event(s) for %s",
        outcome.feeds_polled,
        len(outcome.events),
        provider_id,
    )
    with session_scope() as session:
        summary = classify_pending(session, Classifier(None), provider_id=provider_id)
    logger.info(
        "catalog classify: %d processed, %d breaking change(s) created for %s",
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
