"""Persistence for repo scans.

Follows this codebase's existing convention (see ``cli.py``'s
``_load_breaking_change``): plain functions that take an already-open
:class:`~sqlalchemy.orm.Session` and do their work inline, rather than
opening their own transaction -- callers wrap with
``depfix.storage.session_scope()``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from depfix.core.models import BreakingChange
from depfix.scanners.matching import ScanChangeAssessment
from depfix.scanners.models import SCANNER_VERSION, RepoScanResult
from depfix.storage.schema import (
    BreakingChangeRow,
    CallSiteRow,
    RepoRow,
    RepoScanRow,
    ScanChangeMatchRow,
)


def upsert_repo(
    session: Session,
    *,
    full_name: str,
    owner: str,
    name: str,
    installation_id: int | None = None,
    default_branch: str | None = None,
) -> RepoRow:
    """Insert or update the ``repo`` row for ``full_name``.

    Existing ``installation_id``/``default_branch`` are only overwritten
    when a non-``None`` value is passed, so a caller that doesn't know the
    installation (e.g. scanning a local checkout) never clobbers a value a
    previous GitHub App scan already recorded.
    """
    repo = session.get(RepoRow, full_name)
    if repo is None:
        repo = RepoRow(id=full_name, owner=owner, name=name)
        session.add(repo)
    if installation_id is not None:
        repo.installation_id = installation_id
    if default_branch is not None:
        repo.default_branch = default_branch
    return repo


def record_scan(
    session: Session,
    *,
    repo_full_name: str,
    owner: str,
    name: str,
    result: RepoScanResult,
    provider_id: str = "",
    installation_id: int | None = None,
    default_branch: str | None = None,
    change: BreakingChange | None = None,
) -> RepoScanRow:
    """Persist one :class:`RepoScanResult`, creating the parent ``repo`` row
    if this is the first scan of it.

    Every call site is stored, not just the actionable (HIGH/MEDIUM) ones --
    LOW-confidence sites are reported-only for a fixer, but still useful for
    a human reviewing recall/precision, so they belong in the same table.
    """
    from depfix.scanners.severity import severity_from_scan

    scan_severity, scan_evidence = (
        severity_from_scan(change, result.call_sites) if change is not None else (None, None)
    )
    repo = upsert_repo(
        session,
        full_name=repo_full_name,
        owner=owner,
        name=name,
        installation_id=installation_id,
        default_branch=default_branch,
    )

    now = datetime.now(UTC)
    scan = RepoScanRow(
        repo_id=repo.id,
        commit_sha=result.commit_sha,
        scanner_version=result.scanner_version or SCANNER_VERSION,
        provider_id=provider_id,
        files_scanned=result.files_scanned,
        manifest_matches=list(result.manifest_matches),
        errors=list(result.errors),
        scanned_at=now,
    )
    scan.call_sites = [
        CallSiteRow(
            filepath=site.filepath,
            line_number=site.line_number,
            column=site.column,
            line_content=site.line_content,
            kind=site.kind.value,
            confidence=site.confidence.value,
            symbol=site.symbol,
            provider_id=site.provider_id,
            evidence=site.evidence,
            severity=scan_severity.value if site.is_actionable and scan_severity else None,
            severity_evidence=scan_evidence.value if site.is_actionable and scan_evidence else None,
        )
        for site in result.call_sites
    ]
    repo.scans.append(scan)
    repo.last_scanned_at = now
    return scan


def latest_scan(session: Session, repo_full_name: str) -> RepoScanRow | None:
    """The most recent scan of ``repo_full_name``, or ``None`` if it has
    never been scanned."""
    stmt = (
        select(RepoScanRow)
        .where(RepoScanRow.repo_id == repo_full_name)
        .order_by(RepoScanRow.scanned_at.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def record_scan_assessments(
    session: Session,
    *,
    scan: RepoScanRow,
    assessments: list[ScanChangeAssessment],
) -> list[ScanChangeMatchRow]:
    """Persist the upstream-change decisions derived from one repository scan.

    A scan can be compared to a manually supplied change which does not have
    a database row; those decisions remain visible in CLI output but cannot
    be linked safely, so they are intentionally not persisted here.
    """
    if not assessments:
        return []

    dedupe_keys = {assessment.change.dedupe_key for assessment in assessments}
    rows = session.scalars(
        select(BreakingChangeRow).where(BreakingChangeRow.dedupe_key.in_(dedupe_keys))
    ).all()
    rows_by_key = {row.dedupe_key: row for row in rows}

    matches: list[ScanChangeMatchRow] = []
    for assessment in assessments:
        change_row = rows_by_key.get(assessment.change.dedupe_key)
        if change_row is None:
            continue
        match = ScanChangeMatchRow(
            breaking_change_id=change_row.id,
            status=assessment.status.value,
            reason=assessment.reason,
            matched_call_site_count=len(assessment.matched_sites),
            matched_symbols=list(
                dict.fromkeys(site.symbol for site in assessment.matched_sites)
            ),
        )
        scan.change_matches.append(match)
        matches.append(match)
    return matches
