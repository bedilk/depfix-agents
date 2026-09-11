"""Persistence glue between stored ``ChangeEvent`` rows and the classifier.

Reconstructs a :class:`depfix.sources.models.ChangeEvent` (with its
``SpecChange`` children) from the ``change_event``/``spec_change`` tables,
runs it through :class:`Classifier`, and idempotently persists the resulting
``BreakingChange`` list as ``BreakingChangeRow`` — stamping ``classified_at``
on the parent event so ``depfix classify`` is safe to re-run on a cron tick
without reprocessing everything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from depfix.classify.classifier import Classifier
from depfix.classify.models import ClassifyOutcome
from depfix.core.models import BreakingChange, ChangeKind, ClassificationSource
from depfix.sources.models import ChangeEvent, Severity, SourceKind, SpecChange, SpecChangeKind
from depfix.storage.schema import BreakingChangeRow, ChangeEventRow, SpecChangeRow


def load_unclassified_events(session: Session, *, limit: int | None = None) -> list[ChangeEventRow]:
    """Return ``change_event`` rows not yet run through the classifier."""
    stmt = (
        select(ChangeEventRow)
        .where(ChangeEventRow.classified_at.is_(None))
        .order_by(ChangeEventRow.detected_at)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt))


def event_from_row(row: ChangeEventRow) -> ChangeEvent:
    """Reconstruct the ``ChangeEvent`` a ``ChangeEventRow`` was persisted from."""
    return ChangeEvent(
        provider_id=row.provider_id,
        feed_key=row.feed_key,
        source_kind=SourceKind(row.source_kind),
        source_url=row.source_url,
        old_token=row.old_token,
        new_token=row.new_token,
        title=row.title or "",
        summary=row.summary or "",
        body=row.body or "",
        severity=Severity(row.severity),
        spec_changes=[_spec_change_from_row(r) for r in row.spec_changes],
        detected_at=row.detected_at,
    )


def _spec_change_from_row(row: SpecChangeRow) -> SpecChange:
    return SpecChange(
        kind=SpecChangeKind(row.kind),
        severity=Severity(row.severity),
        subject=row.subject,
        pointer=row.pointer,
        detail=row.detail or "",
        direction=row.direction,
        before=row.before,
        after=row.after,
    )


def breaking_change_from_row(row: BreakingChangeRow) -> BreakingChange:
    """Reconstruct the ``BreakingChange`` a ``BreakingChangeRow`` was
    persisted from. Shared by ``depfix run``/``fix`` (``--from-event``) and
    the Week 6 fleet orchestrator, which both need to go from a stored row
    back to the dataclass the fix pipeline actually operates on."""
    return BreakingChange(
        package=row.package,
        old_version=row.old_version,
        new_version=row.new_version,
        old_api=row.old_api,
        new_api=row.new_api,
        description=row.description,
        migration_guide=row.migration_guide,
        kind=ChangeKind(row.kind),
        source=ClassificationSource(row.source),
        provider_id=row.provider_id,
        source_url=row.source_url,
        evidence=row.evidence,
        confidence=row.confidence,
        call_site_hints=list(row.call_site_hints),
    )


def persist_classification(
    session: Session, row: ChangeEventRow, outcome: ClassifyOutcome
) -> list[BreakingChangeRow]:
    """Persist ``outcome.changes`` and stamp ``row.classified_at``.

    Idempotent on ``BreakingChange.dedupe_key``: re-running ``depfix
    classify`` on an already-classified event (e.g. after a prompt tweak)
    skips changes it already has a row for instead of duplicating them.
    """
    existing = {
        bc.dedupe_key
        for bc in session.scalars(
            select(BreakingChangeRow).where(BreakingChangeRow.change_event_id == row.id)
        )
    }
    created: list[BreakingChangeRow] = []
    for change in outcome.changes:
        if change.dedupe_key in existing:
            continue
        bc_row = BreakingChangeRow(
            change_event_id=row.id,
            dedupe_key=change.dedupe_key,
            package=change.package,
            old_version=change.old_version,
            new_version=change.new_version,
            old_api=change.old_api,
            new_api=change.new_api,
            description=change.description,
            migration_guide=change.migration_guide,
            kind=change.kind.value,
            source=change.source.value,
            provider_id=change.provider_id,
            source_url=change.source_url,
            evidence=change.evidence,
            confidence=change.confidence,
            call_site_hints=change.call_site_hints,
        )
        session.add(bc_row)
        created.append(bc_row)
        existing.add(change.dedupe_key)
    row.classified_at = datetime.now(tz=UTC)
    return created


@dataclass
class ClassifyRunSummary:
    """What ``classify_pending`` did, for CLI reporting."""

    events_processed: int = 0
    changes_created: int = 0
    errors: list[str] = field(default_factory=list)


def classify_pending(
    session: Session, classifier: Classifier, *, limit: int | None = None
) -> ClassifyRunSummary:
    """Classify every unclassified event and persist the results.

    Events whose classification errors (e.g. release notes with no LLM
    configured) are left with ``classified_at`` unset so a later run — once
    an LLM is available — retries them instead of silently giving up forever.
    """
    summary = ClassifyRunSummary()
    for row in load_unclassified_events(session, limit=limit):
        summary.events_processed += 1
        event = event_from_row(row)
        outcome = classifier.classify(event)
        if outcome.errors:
            summary.errors.extend(f"event {row.id}: {e}" for e in outcome.errors)
            continue
        created = persist_classification(session, row, outcome)
        summary.changes_created += len(created)
    return summary
