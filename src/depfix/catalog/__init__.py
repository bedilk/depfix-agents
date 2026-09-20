"""Repository-observed, feed-compared migration records."""

from __future__ import annotations

from pathlib import Path

from depfix.catalog.learned import record_detected_usage

__all__ = ["canonical_providers_file", "record_detected_usage"]


def canonical_providers_file() -> str | None:
    """Return the bundled migration catalog path when package data is present."""
    candidate = Path(__file__).with_name("canonical_migrations.yaml")
    return str(candidate) if candidate.is_file() else None
