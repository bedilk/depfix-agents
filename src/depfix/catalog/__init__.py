"""Repository-observed usage records and locally learned migrations."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from depfix.catalog.learned import (
    STATUS_CANDIDATE,
    STATUS_CONFIRMED,
    LearnedMigration,
    load_learned_migrations,
    persist_learned_migrations,
    promote_learned_migration,
    record_detected_usage,
)

if TYPE_CHECKING:
    from depfix.config import Settings

__all__ = [
    "STATUS_CANDIDATE",
    "STATUS_CONFIRMED",
    "LearnedMigration",
    "canonical_providers_file",
    "learned_migrations_file",
    "load_learned_migrations",
    "persist_learned_migrations",
    "promote_learned_migration",
    "record_detected_usage",
    "repository_observations_file",
]


def canonical_providers_file() -> str | None:
    """The bundled, hand-curated migration catalog. Read-only at runtime."""
    candidate = Path(__file__).with_name("canonical_migrations.yaml")
    return str(candidate) if candidate.is_file() else None


def repository_observations_file(settings: "Settings | None" = None) -> str:
    from depfix.config import get_settings

    return (settings or get_settings()).repository_observations_file


def learned_migrations_file(settings: "Settings | None" = None) -> str:
    """Local, gitignored store for migrations learned from feeds/LLM."""
    from depfix.config import get_settings

    return (settings or get_settings()).learned_migrations_file
