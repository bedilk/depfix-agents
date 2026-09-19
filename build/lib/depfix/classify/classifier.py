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
from depfix.sources.models import ChangeEvent

logger = logging.getLogger(__name__)


class Classifier:
    def __init__(
        self, completer: LLMCompleter | None = None, *, min_confidence: float = 0.5
    ) -> None:
        self._notes = (
            NotesClassifier(completer, min_confidence=min_confidence) if completer else None
        )

    def classify(self, event: ChangeEvent) -> ClassifyOutcome:
        package = event.provider_id

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
            # No spec_changes and nothing to read either -- there is no
            # signal here to classify, terminal (not an error to retry, and
            # not a trusted "zero changes" verdict either).
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
        return ClassifyOutcome(changes=changes)
