"""SQLAlchemy persistence for depfix."""

from depfix.storage.attempt_store import (
    attempts_for_repo,
    get_change_attempt,
    record_change_attempt,
    touch_no_call_sites,
)
from depfix.storage.db import get_engine, init_schema, session_scope
from depfix.storage.fix_store import latest_fix_run, record_fix_run, record_pull_request
from depfix.storage.schema import (
    AttemptStatus,
    Base,
    BreakingChangeRow,
    CallSiteRow,
    ChangeAttemptRow,
    ChangeEventRow,
    FeedState,
    FileFixRow,
    FixRunRow,
    Provider,
    PullRequestRow,
    RepoRow,
    RepoScanRow,
    SpecChangeRow,
    TestRunRow,
)

__all__ = [
    "AttemptStatus",
    "Base",
    "BreakingChangeRow",
    "CallSiteRow",
    "ChangeAttemptRow",
    "ChangeEventRow",
    "FeedState",
    "FileFixRow",
    "FixRunRow",
    "Provider",
    "PullRequestRow",
    "RepoRow",
    "RepoScanRow",
    "SpecChangeRow",
    "TestRunRow",
    "attempts_for_repo",
    "get_change_attempt",
    "get_engine",
    "init_schema",
    "latest_fix_run",
    "record_change_attempt",
    "record_fix_run",
    "record_pull_request",
    "session_scope",
    "touch_no_call_sites",
]
