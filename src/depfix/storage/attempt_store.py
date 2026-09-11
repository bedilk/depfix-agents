"""Idempotency ledger persistence for the Week 6 fleet orchestrator.

Follows the same convention as :mod:`depfix.storage.fix_store`: plain
functions that take an already-open :class:`~sqlalchemy.orm.Session` and do
their work inline -- callers wrap with ``depfix.storage.session_scope()``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from depfix.storage.schema import AttemptStatus, ChangeAttemptRow


def get_change_attempt(
    session: Session, *, repo_id: str, dedupe_key: str
) -> ChangeAttemptRow | None:
    """The ledger row for this ``(repo, change)``, or ``None`` if the
    orchestrator has never attempted it before."""
    stmt = select(ChangeAttemptRow).where(
        ChangeAttemptRow.repo_id == repo_id, ChangeAttemptRow.dedupe_key == dedupe_key
    )
    return session.execute(stmt).scalar_one_or_none()


def record_change_attempt(
    session: Session,
    *,
    repo_id: str,
    dedupe_key: str,
    status: AttemptStatus,
    fix_run_id: int | None = None,
    last_error: str = "",
    ref_sha: str = "",
) -> ChangeAttemptRow:
    """Create or update the ledger row for this ``(repo, change)``,
    incrementing ``attempts_used``.

    Idempotent on ``(repo_id, dedupe_key)`` -- a later run for the same
    change updates the existing row in place rather than inserting a
    duplicate, so "the latest attempt" and "the only row" are one and the
    same.
    """
    row = get_change_attempt(session, repo_id=repo_id, dedupe_key=dedupe_key)
    if row is None:
        row = ChangeAttemptRow(repo_id=repo_id, dedupe_key=dedupe_key, attempts_used=0)
        session.add(row)
    row.status = status.value
    row.attempts_used += 1
    row.fix_run_id = fix_run_id
    row.last_error = last_error
    if ref_sha:
        row.last_checked_ref_sha = ref_sha
    return row


def touch_no_call_sites(
    session: Session, *, repo_id: str, dedupe_key: str, ref_sha: str
) -> ChangeAttemptRow:
    """Record (or refresh) a ``NO_CALL_SITES`` outcome without consuming
    retry budget.

    "This repo has no call sites for this change" is not a failure worth
    counting against a per-change attempt cap -- it just means the next
    check should wait for ``ref_sha`` to change (see
    :attr:`ChangeAttemptRow.last_checked_ref_sha`) rather than re-scanning
    on every cron tick.
    """
    row = get_change_attempt(session, repo_id=repo_id, dedupe_key=dedupe_key)
    if row is None:
        row = ChangeAttemptRow(repo_id=repo_id, dedupe_key=dedupe_key, attempts_used=0)
        session.add(row)
    row.status = AttemptStatus.NO_CALL_SITES.value
    row.last_checked_ref_sha = ref_sha
    return row
