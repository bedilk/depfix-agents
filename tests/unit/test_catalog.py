"""Regression coverage for automatic historical migration discovery."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from depfix.core import shortcuts
from depfix.storage import db as db_module
from depfix.storage.schema import Base, FeedState, Provider


@pytest.fixture
def in_memory_db(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "_engine", engine)
    monkeypatch.setattr(
        db_module, "_session_factory", sessionmaker(bind=engine, expire_on_commit=False)
    )


class _NoopDeps:
    """Catalog fixture feeds do not use HTTP or registry clients."""

    def __enter__(self) -> _NoopDeps:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def test_catalog_creates_openai_migration_when_upstream_has_no_event(
    in_memory_db: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`plan --provider openai` can find a historical v3-to-v4 migration."""
    providers_file = tmp_path / "providers.yaml"
    providers_file.write_text(
        """providers:
  - id: openai
    sdk_packages: [{name: openai, ecosystem: npm}]
    feeds:
      - kind: fixture_change
        id: already-baselined-upstream
        old_token: "3.2.1"
        new_token: "4.0.1"
        spec_changes:
          - kind: operation_id_changed
            severity: breaking
            subject: openai.createChatCompletion
            after: openai.chat.completions.create
""",
        encoding="utf-8",
    )
    with db_module.session_scope() as session:
        session.add(Provider(id="openai", name="OpenAI"))
        session.add(
            FeedState(
                provider_id="openai",
                feed_key="fixture_change:already-baselined-upstream",
                kind="fixture_change",
                last_token="4.0.1",
            )
        )
    monkeypatch.setattr(shortcuts.SourceDeps, "from_settings", lambda: _NoopDeps())

    created = shortcuts.ensure_changes_detected("openai", providers_file=str(providers_file))
    change, change_id = shortcuts.latest_change_for_provider("openai")

    assert created == 6
    assert change_id is not None
    assert change is not None

    all_changes = shortcuts.all_changes_for_provider("openai")
    assert {change.old_api for change in all_changes} == {
        "openai.createChatCompletion",
        "openai.createCompletion",
        "openai.createEmbedding",
        "openai.createModeration",
        "openai.createImage",
        "openai.createEdit",
    }
    chat_change = next(item for item in all_changes if item.old_api == "openai.createChatCompletion")
    assert chat_change.new_api == "openai.chat.completions.create"
    assert "Configuration" in chat_change.description
    assert "OpenAIApi" in chat_change.description
