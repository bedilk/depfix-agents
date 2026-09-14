"""Tests for safe Postgres schema bootstrapping."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from depfix.storage import db


def _engine_with_tables(
    monkeypatch: pytest.MonkeyPatch,
    tables: list[str],
    *,
    change_event_columns: list[str] | None = None,
) -> MagicMock:
    inspector = MagicMock()
    inspector.get_table_names.return_value = tables
    inspector.get_columns.return_value = [
        {"name": name} for name in (change_event_columns or [])
    ]
    monkeypatch.setattr(db, "inspect", lambda _engine: inspector)
    return MagicMock()


def test_legacy_schema_is_stamped_at_baseline_before_later_migrations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _engine_with_tables(monkeypatch, sorted(db._BASELINE_TABLES))

    assert db._legacy_schema_revision(engine) == "0001"


def test_fully_current_legacy_schema_is_stamped_at_current_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _engine_with_tables(
        monkeypatch,
        sorted({*db._BASELINE_TABLES, "change_attempt"}),
        change_event_columns=["id", "body_url"],
    )

    assert db._legacy_schema_revision(engine) == "0003"


def test_partial_legacy_schema_is_not_stamped(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _engine_with_tables(monkeypatch, ["provider"])

    with pytest.raises(RuntimeError, match="partial pre-Alembic"):
        db._legacy_schema_revision(engine)
