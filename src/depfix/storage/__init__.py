"""SQLAlchemy persistence for depfix."""

from depfix.storage.db import get_engine, init_schema, session_scope
from depfix.storage.fix_store import latest_fix_run, record_fix_run
from depfix.storage.schema import (
    Base,
    BreakingChangeRow,
    CallSiteRow,
    ChangeEventRow,
    FeedState,
    FileFixRow,
    FixRunRow,
    Provider,
    RepoRow,
    RepoScanRow,
    SpecChangeRow,
    TestRunRow,
)

__all__ = [
    "Base",
    "BreakingChangeRow",
    "CallSiteRow",
    "ChangeEventRow",
    "FeedState",
    "FileFixRow",
    "FixRunRow",
    "Provider",
    "RepoRow",
    "RepoScanRow",
    "SpecChangeRow",
    "TestRunRow",
    "get_engine",
    "init_schema",
    "session_scope",
]
