"""Top-level classify entry point: pick the right path for a ``ChangeEvent``.

Deterministic spec-diff runs whenever the event carries structural deltas —
no LLM needed, no API key, CI-gatable at 100% pass. The release-notes LLM
path only runs when there is nothing to diff and a completer is configured.
"""

from __future__ import annotations

import logging

from depfix.classify.llm import LLMCompleter
from depfix.classify.models import ClassifyOutcome
from depfix.classify.notes import NotesClassifier
from depfix.classify.spec_rules import classify_spec_changes
from depfix.core.models import BreakingChange, ChangeKind, ClassificationSource
from depfix.sources.models import ChangeEvent, SourceKind

logger = logging.getLogger(__name__)


class Classifier:
    def __init__(
        self, completer: LLMCompleter | None = None, *, min_confidence: float = 0.5,
        synthesize: bool = True,
    ) -> None:
        self._notes = (
            NotesClassifier(completer, min_confidence=min_confidence) if completer else None
        )
        self._synthesizer = None
        if completer is not None and synthesize:
            from depfix.classify.synthesize import MigrationSynthesizer

            self._synthesizer = MigrationSynthesizer(completer)

    def classify(self, event: ChangeEvent) -> ClassifyOutcome:
        package = str(event.raw.get("package") or event.provider_id)

        if event.advisory is not None:
            advisory = event.advisory
            return ClassifyOutcome(changes=[BreakingChange(
                package=advisory.package,
                old_version=str(event.raw.get("version") or advisory.vulnerable_range),
                new_version=advisory.fixed_version or "",
                old_api=f"{advisory.package}@{advisory.vulnerable_range}",
                new_api=(
                    f"{advisory.package}@{advisory.fixed_version}"
                    if advisory.has_fix
                    else f"{advisory.package} (no fix published)"
                ),
                description=f"Security advisory {advisory.advisory_id}: {advisory.summary}",
                migration_guide=(
                    f"Upgrade {advisory.package} to {advisory.fixed_version} or later "
                    "to remediate this vulnerability."
                    if advisory.has_fix
                    else "No fixed version is published yet; monitor the advisory and "
                    "consider a temporary mitigation."
                ),
                kind=ChangeKind.SECURITY_ADVISORY,
                source=ClassificationSource.SECURITY,
                provider_id=event.provider_id,
                source_url=event.source_url,
                evidence=advisory.summary,
                confidence=1.0,
                call_site_hints=list(advisory.affected_symbols),
                advisory_severity=advisory.severity.lower() if advisory.severity else None,
            )])

        # A dist-tag movement is independently useful information even when
        # the release notes are empty.  Record it as *dependency drift*, not
        # as a guessed breaking API change.  The apply policy later permits
        # only safe patch/minor manifest updates unless a separate vetted API
        # migration exists.
        if event.source_kind in (SourceKind.NPM_DIST_TAG, SourceKind.PYPI_DIST_TAG, SourceKind.RUBYGEMS_DIST_TAG) and event.old_token:
            # ``ChangeEventRow`` deliberately stores stable event fields, not
            # the source's arbitrary raw payload. Recover the npm package
            # from its canonical feed key when classifying a persisted event.
            if not event.raw.get("package"):
                if event.feed_key.startswith("npm:"):
                    # Scan-bootstrap events add a repo/version suffix for
                    # idempotency.  Strip it before recovering the ordinary
                    # ``npm:<package>:<dist-tag>`` identity.
                    feed_identity = event.feed_key.removeprefix("npm:").split(":repo:", 1)[0]
                    package = feed_identity.rsplit(":", 1)[0]
                elif event.feed_key.startswith("pypi:"):
                    package = event.feed_key.removeprefix("pypi:").split(":repo:", 1)[0]
                elif event.feed_key.startswith("rubygems:"):
                    package = event.feed_key.removeprefix("rubygems:").split(":repo:", 1)[0]
            return ClassifyOutcome(changes=[BreakingChange(
                package=package,
                old_version=event.old_token,
                new_version=event.new_token,
                old_api=f"{package}@{event.old_token}",
                new_api=f"{package}@{event.new_token}",
                description=f"Dependency drift: {package} {event.old_token} → {event.new_token}",
                migration_guide=("Review release notes before a major upgrade; patch and minor "
                                 "updates can be verified as manifest-only changes."),
                kind=ChangeKind.DEPENDENCY_VERSION_BUMP,
                source=ClassificationSource.REGISTRY,
                provider_id=event.provider_id,
                source_url=event.source_url,
                evidence=(f"{event.source_kind.value} moved from {event.old_token} "
                          f"to {event.new_token}"),
            )])

        if event.spec_changes and event.body.strip() and self._synthesizer is not None:
            result = self._synthesizer.synthesize(event, package=package)
            if result.change is not None:
                return ClassifyOutcome(changes=[result.change], cost=result.cost_usd)
            logger.info("synthesis for %s did not pass gates: %s", package, result.reason)

        if event.spec_changes:
            changes = classify_spec_changes(
                event.spec_changes,
                package=package,
                old_version=event.old_token or "",
                new_version=event.new_token,
                provider_id=event.provider_id,
                source_url=event.source_url,
            )
            return ClassifyOutcome(changes=changes)

        if not event.body.strip():
            return ClassifyOutcome(unclassifiable=True)

        if self._notes is None:
            return ClassifyOutcome(
                errors=["no spec_changes and no LLM configured for the release-notes path"]
            )

        changes = self._notes.classify(
            event.body,
            package=package,
            old_version=event.old_token or "",
            new_version=event.new_token,
            provider_id=event.provider_id,
            source_url=event.source_url,
        )
        return ClassifyOutcome(changes=changes, cost=self._notes.last_cost)
