"""Bundled, canonical migration records for historical SDK breaks."""

from __future__ import annotations

from pathlib import Path


def canonical_providers_file() -> str | None:
    """Return the bundled migration catalog path when package data is present."""
    candidate = Path(__file__).with_name("canonical_migrations.yaml")
    return str(candidate) if candidate.is_file() else None
