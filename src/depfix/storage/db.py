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

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from depfix.config import get_settings
from depfix.storage.schema import Base

logger = logging.getLogger(__name__)


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


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
    """Create all tables if they do not already exist.

    Cheap idempotent call — safe to invoke on every poller start-up until
    Alembic lands (see docs/decisions.md). ``create_all`` only creates
    missing *tables*, though — it will not add a column to a table that
    already exists, so the Week 2 ``classified_at`` column on the
    pre-existing ``change_event`` table needs its own idempotent ALTER.
    """
    engine = get_engine()
    Base.metadata.create_all(engine)
    _ensure_classified_at_column(engine)


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
