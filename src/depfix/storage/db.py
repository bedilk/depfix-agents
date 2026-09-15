"""SQLAlchemy engine and session lifecycle for depfix.

Engine construction is lazy and cached: the first call to :func:`get_engine`
reads ``DATABASE_URL`` from :class:`depfix.config.Settings`. Tests point
``DATABASE_URL`` at a temporary SQLite file (or monkey-patch the module-level
``_engine`` / ``_session_factory``).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from depfix.config import get_settings
from depfix.storage.schema import Base

logger = logging.getLogger(__name__)


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None

# Tables created by ``0001_baseline``.  depfix created these directly with
# ``Base.metadata.create_all`` before it adopted Alembic, so a running
# pre-Alembic deployment has tables but no ``alembic_version`` record.
_BASELINE_TABLES = frozenset(
    {
        "provider",
        "feed_state",
        "change_event",
        "spec_change",
        "breaking_change",
        "repo",
        "repo_scan",
        "call_site",
        "fix_run",
        "file_fix",
        "test_run",
        "pull_request",
    }
)


def get_engine() -> Engine:
    """Return the process-wide engine, building it on first use."""
    global _engine, _session_factory
    if _engine is None:
        url = get_settings().database_url
        _engine = create_engine(url, future=True)
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
        logger.debug("SQLAlchemy engine created (driver=%s)", _engine.dialect.name)
    return _engine


def init_schema() -> None:
    """Bring the schema up to date. Cheap and idempotent — safe to invoke
    on every poller/orchestrator start-up.

    SQLite (dev/test) keeps the original ``create_all`` shortcut: there's
    no shared server whose schema needs versioning, and every test's
    in-memory database is thrown away at the end of the test anyway.
    Postgres (production) instead runs the real Alembic migrations in
    ``depfix.migrations`` up to ``head`` — see :func:`_upgrade_to_head`.

    ``_ensure_classified_at_column`` runs after either path as a defensive
    no-op ALTER: it's what pre-Alembic Postgres deployments relied on to
    pick up the Week 2 ``classified_at`` column, and stays harmless (``ADD
    COLUMN IF NOT EXISTS``) now that the baseline migration also creates
    that column on fresh databases.
    """
    engine = get_engine()
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
    else:
        _upgrade_to_head(engine)
    _ensure_classified_at_column(engine)


def _upgrade_to_head(engine: Engine) -> None:
    """Run ``depfix.migrations`` up to ``head`` against a Postgres database.

    Builds an in-memory Alembic ``Config`` rather than reading
    ``alembic.ini`` from disk — the orchestrator may be running from
    inside the Docker image, which only ships ``src/`` (see the
    Dockerfile), not the repo root. ``script_location`` is resolved
    relative to this file instead, so it works the same way whether this
    runs from a checked-out repo or an installed package. ``env.py``
    itself ignores whatever URL (if any) ends up on this ``Config`` and
    always reads ``Settings.database_url`` directly, so there's no second
    "which database" value to keep in sync.
    """
    from alembic import command
    from alembic.config import Config

    migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
    cfg = Config()
    cfg.set_main_option("script_location", str(migrations_dir))
    legacy_revision = _legacy_schema_revision(engine)
    if legacy_revision is not None:
        logger.warning(
            "detected pre-Alembic depfix schema; stamping revision %s before upgrade",
            legacy_revision,
        )
        command.stamp(cfg, legacy_revision)
    logger.info("running Alembic migrations to head against %s", engine.url.render_as_string())
    command.upgrade(cfg, "head")


def _legacy_schema_revision(engine: Engine) -> str | None:
    """Return the revision represented by a complete pre-Alembic schema.

    ``None`` means either a fresh database (which Alembic should migrate from
    scratch) or one which is already versioned.  A partially-created legacy
    schema is unsafe to stamp: it requires operator review rather than risking
    data loss or claiming migrations that were never applied.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "alembic_version" in tables:
        return None

    present_baseline_tables = tables & _BASELINE_TABLES
    if not present_baseline_tables:
        return None

    missing_baseline_tables = _BASELINE_TABLES - tables
    if missing_baseline_tables:
        missing = ", ".join(sorted(missing_baseline_tables))
        raise RuntimeError(
            "Detected a partial pre-Alembic depfix schema. Refusing to stamp it; "
            f"missing baseline tables: {missing}. Restore the schema or migrate it manually."
        )

    if "change_attempt" not in tables:
        return "0001"

    change_event_columns = {column["name"] for column in inspector.get_columns("change_event")}
    return "0003" if "body_url" in change_event_columns else "0002"


def _ensure_classified_at_column(engine: Engine) -> None:
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(change_event)")}
            if "classified_at" not in columns:
                conn.exec_driver_sql("ALTER TABLE change_event ADD COLUMN classified_at DATETIME")
        else:
            conn.exec_driver_sql(
                "ALTER TABLE change_event ADD COLUMN IF NOT EXISTS classified_at TIMESTAMPTZ"
            )


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""
    get_engine()  # ensure factory is built
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
