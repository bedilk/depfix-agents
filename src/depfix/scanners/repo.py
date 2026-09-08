"""Orchestrates one repo scan: acquire a checkout, run the manifest and
call-site scanners against it, and assemble a :class:`RepoScanResult`.

This is the seam between "how do we get the code" (:mod:`depfix.clone`,
:mod:`depfix.gh`) and "what do we do with it" (:mod:`depfix.scanners.manifest`,
:mod:`depfix.scanners.callsites`) -- callers that already have a checkout
(tests, a CLI pointed at a local directory) use :func:`scan_checkout` /
:func:`scan_path` directly and never touch GitHub App auth at all.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path

from depfix.clone import Checkout, CloneService
from depfix.core.models import BreakingChange
from depfix.gh import GitHubAppAuth
from depfix.providers.models import ProviderSpec
from depfix.scanners.callsites import CallSiteScanner
from depfix.scanners.manifest import scan_manifests
from depfix.scanners.models import RepoScanResult, ScanTarget

logger = logging.getLogger(__name__)


def build_scan_target(provider: ProviderSpec, change: BreakingChange | None = None) -> ScanTarget:
    """Build a :class:`ScanTarget` from a provider, optionally narrowed to
    the symbols implicated by one ``change``.

    Narrowing to a specific change is how "does this repo still call the
    removed v3 moderations endpoint" avoids flooding the report with every
    other unrelated call the repo makes against the same provider.
    """
    symbols = _symbols_from_change(change) if change is not None else ()
    return ScanTarget(
        provider_id=provider.id,
        sdk_packages=tuple(pkg.name for pkg in provider.sdk_packages),
        api_base_urls=provider.api_base_urls,
        call_site_anchors=provider.call_site_anchors,
        symbols=symbols,
    )


def _symbols_from_change(change: BreakingChange) -> tuple[str, ...]:
    """Mine the dotted symbols a change is actually about.

    ``call_site_hints`` is trusted as-is -- it exists specifically for this.
    ``old_api`` is used more cautiously: it's free text meant for humans
    (``"openai.createModeration()"``, or occasionally prose), so it's only
    taken when it looks like a bare dotted symbol once a trailing call
    ``(...)`` is stripped -- anything with whitespace or other punctuation
    left over is prose, not a symbol, and is dropped rather than guessed at.
    """
    symbols: list[str] = list(change.call_site_hints)

    candidate = change.old_api.strip()
    if candidate.endswith(")"):
        candidate = candidate.split("(", 1)[0].strip()
    if candidate and _looks_like_dotted_symbol(candidate) and candidate not in symbols:
        symbols.append(candidate)

    return tuple(symbols)


_DOTTED_SYMBOL_RE = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+")


def _looks_like_dotted_symbol(text: str) -> bool:
    """Does ``text`` look like a bare dotted identifier chain, e.g.
    ``openai.moderations.create`` -- no whitespace, no stray punctuation?"""
    return bool(_DOTTED_SYMBOL_RE.fullmatch(text))


def _current_commit_sha(path: Path) -> str:
    """Resolve HEAD for ``path`` -- but only when ``path`` is itself the
    root git finds, not some subdirectory nested inside an unrelated
    ancestor repo.

    ``git -C <path> ...`` walks *up* the filesystem tree to find the
    nearest ``.git`` if ``path`` isn't a repo root itself. A shallow clone
    from :meth:`CloneService.clone` is never affected -- its ``.git`` lives
    right at the checkout path -- but a caller-supplied local directory
    (``depfix scan --path ...``) commonly is *not* a repo root of its own,
    e.g. a fixture directory nested inside this tool's own git checkout.
    Without this check, git would silently report the *outer* repo's HEAD
    as if it belonged to the scanned code -- misleading commit metadata
    rather than an obvious error. Requiring the discovered toplevel to
    equal ``path`` catches that case and blanks out the commit instead of
    guessing.
    """
    git_path = shutil.which("git")
    if git_path is None:
        return ""

    try:
        toplevel = subprocess.run(
            [git_path, "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if toplevel.returncode != 0:
        return ""
    if Path(toplevel.stdout.strip()).resolve() != Path(path).resolve():
        return ""

    try:
        result = subprocess.run(
            [git_path, "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def scan_checkout(
    checkout: Checkout,
    target: ScanTarget,
    *,
    repo_full_name: str = "",
    scanner: CallSiteScanner | None = None,
) -> RepoScanResult:
    """Scan an already-acquired checkout for manifests + call sites.

    ``scanner`` lets a caller (e.g. the CLI, wiring in ``scan_max_file_bytes``/
    ``scan_max_files`` from :class:`depfix.config.Settings`) supply a
    pre-configured :class:`CallSiteScanner`; a default is constructed when
    omitted so tests and simple callers don't have to.
    """
    manifest_scan = scan_manifests(checkout.path, list(target.sdk_packages))
    call_site_result = (scanner or CallSiteScanner()).scan(checkout.path, target)

    return RepoScanResult(
        repo_full_name=repo_full_name,
        commit_sha=_current_commit_sha(checkout.path),
        call_sites=call_site_result.call_sites,
        manifest_matches=[
            f"{m.package}@{m.resolved_version or m.declared_range or '?'} "
            f"({m.source}, {m.manifest_path})"
            for m in manifest_scan.matches
        ],
        files_scanned=call_site_result.files_scanned,
        errors=call_site_result.errors,
    )


def scan_path(
    path: str | Path,
    target: ScanTarget,
    *,
    repo_full_name: str = "",
    scanner: CallSiteScanner | None = None,
) -> RepoScanResult:
    """Scan a local directory directly, with no clone/GitHub App involved."""
    checkout = CloneService().local(path)
    return scan_checkout(checkout, target, repo_full_name=repo_full_name, scanner=scanner)


def scan_repo(
    owner: str,
    repo: str,
    target: ScanTarget,
    *,
    gh_auth: GitHubAppAuth,
    clone_service: CloneService,
    ref: str | None = None,
    scanner: CallSiteScanner | None = None,
) -> RepoScanResult:
    """Resolve the App installation for ``owner/repo``, mint a
    least-privilege token, shallow-clone, scan, and clean up -- always,
    even if scanning raises.
    """
    installation = gh_auth.resolve_installation_for_repo(owner, repo)
    token = gh_auth.installation_token(installation.id, repositories=(repo,))
    resolved_ref = ref or gh_auth.default_ref(owner, repo)

    checkout = clone_service.clone(owner, repo, ref=resolved_ref, token=token.token)
    try:
        return scan_checkout(checkout, target, repo_full_name=f"{owner}/{repo}", scanner=scanner)
    finally:
        clone_service.cleanup(checkout)
