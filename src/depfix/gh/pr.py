"""Opens (or reuses) a PR for a depfix branch, with a body that links back
to the breaking change's real evidence fields -- no invented metadata, just
what's already on :class:`~depfix.core.models.BreakingChange` and
:class:`~depfix.core.pipeline.FixPipelineResult`.
"""

from __future__ import annotations

import logging

import httpx

from depfix.apply.models import EditVerdict, FileEdit
from depfix.core.models import BreakingChange
from depfix.core.pipeline import FixPipelineResult
from depfix.gh.app import GitHubAppError
from depfix.gh.models import PullRequest

logger = logging.getLogger(__name__)

DEFAULT_GITHUB_API_URL = "https://api.github.com"


def pr_title_for(change: BreakingChange) -> str:
    """Short, informative title -- same "old -> new" shape used elsewhere
    (e.g. commit messages), so a PR list and a commit log read the same
    way."""
    return f"depfix: migrate {change.old_api} -> {change.replacement}"


def build_pr_body(
    change: BreakingChange, result: FixPipelineResult, *, edits: list[FileEdit] | None = None
) -> str:
    """Markdown PR body: change summary, migration guide, source evidence
    (when present), a per-file table of edits, and the verification
    summary -- every field used here is real, read directly off ``change``
    and ``result``.

    ``edits`` defaults to ``result.edits`` (every candidate edit, including
    ones that were reverted or never committed) for backward compatibility,
    but callers that already filtered down to the actually-committable set
    (see :func:`committable_edits`) should pass that same list here --
    otherwise the "Files changed" table lists files the PR doesn't actually
    touch.
    """
    if edits is None:
        edits = list(result.edits)
    lines = [
        f"## {change.package}: `{change.old_api}` -> `{change.replacement}`",
        "",
        f"- **Package:** {change.package} ({change.old_version} -> {change.new_version})",
        f"- **Kind:** {change.kind.value}",
        f"- **Description:** {change.description}",
    ]
    if change.migration_guide:
        lines += ["", "### Migration guide", "", change.migration_guide]
    if change.evidence:
        lines += ["", "### Evidence", "", f"> {change.evidence}"]
    if change.source_url:
        lines += ["", f"Source: {change.source_url}"]

    lines += ["", "### Files changed", "", "| File | Verdict | Usages fixed |", "| --- | --- | --- |"]
    for edit in edits:
        lines.append(f"| `{edit.relpath}` | {edit.verdict.value} | {edit.usages_fixed} |")

    verification = result.verification
    lines += ["", "### Verification"]
    if verification is None or not verification.ran:
        reason = verification.skipped_reason if verification is not None else "not configured"
        lines.append(f"Test-suite verification did not run ({reason}).")
    else:
        lines.append(f"New test failures introduced: {verification.new_failure_count}.")

    lines.append("")
    lines.append("_Opened automatically by [depfix](https://github.com/)._")
    return "\n".join(lines)


def kept_edits(result: FixPipelineResult) -> list[FileEdit]:
    """Only test-confirmed edits belong in a PR -- ``SUSPECT`` edits never
    ran against the real test suite (or failed to), so they stay out."""
    return [edit for edit in result.edits if edit.verdict == EditVerdict.KEPT]


def committable_edits(result: FixPipelineResult, *, allow_unverified: bool = False) -> list[FileEdit]:
    """Edits safe to push to a branch.

    Defaults to the same test-confirmed-only set as :func:`kept_edits`. When
    ``allow_unverified=True`` (a repo with ``verify: false`` in its
    ``.depfix.yml`` -- see :mod:`depfix.repoconfig`, which has no test suite
    to confirm against), ``APPLIED`` edits are committable too since they
    were never run through :class:`~depfix.verify.verifier.Verifier` in the
    first place. ``SUSPECT`` edits are excluded either way -- a fix whose
    syntax couldn't even be validated has no business in a PR.
    """
    verdicts = {EditVerdict.KEPT, EditVerdict.APPLIED} if allow_unverified else {EditVerdict.KEPT}
    return [edit for edit in result.edits if edit.verdict in verdicts]


def open_pull_request(
    *,
    owner: str,
    repo: str,
    token: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str,
    draft: bool = False,
    api_url: str = DEFAULT_GITHUB_API_URL,
    http_timeout: float = 20.0,
    client: httpx.Client | None = None,
) -> PullRequest:
    """Open a PR from ``head_branch`` onto ``base_branch``. If one already
    exists for that head/base (GitHub returns 422), look it up and return it
    with ``already_existed=True`` instead of failing -- idempotent re-runs
    for the same deterministic branch (see :func:`depfix.gh.branch.branch_name_for`)
    shouldn't error just because a previous run already opened the PR.
    """
    api_url = api_url.rstrip("/")
    owned_client = client is None
    http_client = client or httpx.Client(timeout=http_timeout)
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        resp = http_client.post(
            f"{api_url}/repos/{owner}/{repo}/pulls",
            headers=headers,
            json={
                "title": title,
                "body": body,
                "head": head_branch,
                "base": base_branch,
                "draft": draft,
            },
        )
        if resp.status_code == 422:
            existing = http_client.get(
                f"{api_url}/repos/{owner}/{repo}/pulls",
                headers=headers,
                params={"head": f"{owner}:{head_branch}", "base": base_branch, "state": "open"},
            )
            _raise_for_status(existing)
            results = existing.json()
            if not results:
                raise GitHubAppError(
                    f"GitHub rejected PR creation for {head_branch} -> {base_branch} as "
                    f"unprocessable (422), but no existing open PR was found: {resp.text[:300]}"
                )
            return _pull_request_from_dict(results[0], already_existed=True)
        _raise_for_status(resp)
        return _pull_request_from_dict(resp.json(), already_existed=False)
    finally:
        if owned_client:
            http_client.close()


def _pull_request_from_dict(item: dict, *, already_existed: bool) -> PullRequest:
    return PullRequest(
        number=item["number"],
        html_url=item["html_url"],
        head_branch=item["head"]["ref"],
        base_branch=item["base"]["ref"],
        already_existed=already_existed,
    )


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code == 401:
        raise GitHubAppError(
            f"GitHub rejected the token (401 Unauthorized) for {resp.request.url}."
        )
    if resp.status_code == 404:
        raise GitHubAppError(f"GitHub resource not found: {resp.request.url}")
    if resp.status_code == 422:
        raise GitHubAppError(f"GitHub rejected the request as unprocessable (422): {resp.text[:300]}")
    if resp.status_code >= 400:
        raise GitHubAppError(f"GitHub API error {resp.status_code}: {resp.text[:300]}")
