"""Repository-observed, feed-compared migration records."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from depfix.catalog.learned import record_detected_usage

if TYPE_CHECKING:
    from depfix.config import Settings

__all__ = ["canonical_providers_file", "record_detected_usage", "repository_observations_file"]


def canonical_providers_file() -> str | None:
    """Return the bundled, review-owned migration catalog path when present."""
    candidate = Path(__file__).with_name("canonical_migrations.yaml")
    return str(candidate) if candidate.is_file() else None


def repository_observations_file(settings: "Settings | None" = None) -> str:
    """Return the local (gitignored) file that scan observations are written to.

    Scan results contain local absolute paths and repo-specific metadata that
    must never be committed to the packaged catalog. This always points to a
    ``.depfix/`` path that is covered by ``.gitignore``.
    """
    from depfix.config import get_settings

    return (settings or get_settings()).repository_observations_file
