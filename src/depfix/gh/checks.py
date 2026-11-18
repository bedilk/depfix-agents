"""GitHub Checks API — create check runs with file-level annotations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from depfix.gh.app import GitHubAppError
from depfix.gh.pr import DEFAULT_GITHUB_API_URL
from depfix.scanners.models import MatchConfidence, RepoScanResult

if TYPE_CHECKING:
    from depfix.scanners.matching import ScanChangeAssessment

logger = logging.getLogger(__name__)

_MAX_ANNOTATIONS_PER_REQUEST = 50


def annotations_from_scan(
    result: RepoScanResult,
    assessments: list[ScanChangeAssessment],
) -> list[dict]:
    """Map call sites to GitHub Check annotation dicts."""
    annotations: list[dict] = []
    for site in result.call_sites:
        level = (
            "warning"
            if site.confidence in (MatchConfidence.HIGH, MatchConfidence.MEDIUM)
            else "notice"
        )
        message = f"{site.symbol} ({site.kind.value})"
        if site.evidence:
            message += f" — {site.evidence}"
        annotations.append(
            {
                "path": site.filepath,
                "start_line": site.line_number,
                "end_line": site.line_number,
                "annotation_level": level,
                "message": message,
                "title": f"depfix: {site.kind.value}",
            }
        )
    return annotations


def create_check_run(
    *,
    owner: str,
    repo: str,
    name: str,
    head_sha: str,
    token: str,
    status: str = "completed",
    conclusion: str = "neutral",
    title: str = "",
    summary: str = "",
    annotations: list[dict] | None = None,
    api_url: str = DEFAULT_GITHUB_API_URL,
    http_timeout: float = 20.0,
    client: httpx.Client | None = None,
) -> dict:
    """Create a GitHub Check Run, batching annotations in groups of 50."""
    api_url = api_url.rstrip("/")
    owned_client = client is None
    http_client = client or httpx.Client(timeout=http_timeout)
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    all_annotations = annotations or []
    first_batch = all_annotations[:_MAX_ANNOTATIONS_PER_REQUEST]

    try:
        resp = http_client.post(
            f"{api_url}/repos/{owner}/{repo}/check-runs",
            headers=headers,
            json={
                "name": name,
                "head_sha": head_sha,
                "status": status,
                "conclusion": conclusion,
                "output": {
                    "title": title,
                    "summary": summary,
                    "annotations": first_batch,
                },
            },
        )
        _raise_for_status(resp)
        check_run = resp.json()
        check_run_id = check_run["id"]

        remaining = all_annotations[_MAX_ANNOTATIONS_PER_REQUEST:]
        while remaining:
            batch = remaining[:_MAX_ANNOTATIONS_PER_REQUEST]
            remaining = remaining[_MAX_ANNOTATIONS_PER_REQUEST:]
            patch_resp = http_client.patch(
                f"{api_url}/repos/{owner}/{repo}/check-runs/{check_run_id}",
                headers=headers,
                json={
                    "output": {
                        "title": title,
                        "summary": summary,
                        "annotations": batch,
                    },
                },
            )
            _raise_for_status(patch_resp)

        return check_run
    finally:
        if owned_client:
            http_client.close()


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code == 401:
        raise GitHubAppError(
            f"GitHub rejected the token (401 Unauthorized) for {resp.request.url}."
        )
    if resp.status_code >= 400:
        raise GitHubAppError(f"GitHub API error {resp.status_code}: {resp.text[:300]}")
