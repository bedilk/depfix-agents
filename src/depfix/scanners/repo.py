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
from collections.abc import Callable, Iterable
from dataclasses import replace
from pathlib import Path

from depfix.clone import Checkout, CloneService
from depfix.core.models import BreakingChange
from depfix.ecosystems import registry as ecosystems_registry
from depfix.gh import GitHubAppAuth
from depfix.providers.models import ProviderSpec
from depfix.scanners.callsites import CallSiteScanner
from depfix.scanners.manifest import scan_manifests
from depfix.scanners.models import DeclaredDependency, RepoScanResult, ScanTarget

logger = logging.getLogger(__name__)

# Both names delegate to depfix.ecosystems -- the single authority on
# which ecosystems exist and which support the full fix pipeline.
# ``typescript`` stays in SUPPORTED_ECOSYSTEMS for callers that still pass
# it explicitly; detection itself folds TS markers into "javascript".
SUPPORTED_ECOSYSTEMS = frozenset(ecosystems_registry.fixable_ids()) | {"typescript"}


def detect_repo_ecosystem(root: Path) -> str:
    """Return the dominant root ecosystem, or ``unknown`` when unmarked."""
    return ecosystems_registry.detect(root)


def build_scan_target(provider: ProviderSpec, change: BreakingChange | None = None) -> ScanTarget:
    """Build a :class:`ScanTarget` from a provider, optionally narrowed to
    the symbols implicated by one ``change``.

    Narrowing to a specific change is how "does this repo still call the
    removed v3 moderations endpoint" avoids flooding the report with every
    other unrelated call the repo makes against the same provider.
    """
    symbols = symbols_for_change(provider.id, change) if change is not None else ()
    return ScanTarget(
        provider_id=provider.id,
        sdk_packages=tuple(pkg.name for pkg in provider.sdk_packages),
        api_base_urls=provider.api_base_urls,
        call_site_anchors=provider.call_site_anchors,
        symbols=symbols,
        sdk_package_refs=tuple((pkg.name, pkg.ecosystem) for pkg in provider.sdk_packages),
    )


def build_scan_target_for_changes(
    provider: ProviderSpec, changes: Iterable[BreakingChange]
) -> ScanTarget:
    """Build one discovery target for every classified change of a provider.

    ``scan`` is the seam where upstream changes and repository usage meet. A
    normal provider scan must therefore look for the old symbols of *all*
    currently classified migrations, not only broad provider anchors. The
    returned target remains a single scanner interface; callers do not need
    to loop or know how migration symbols are normalized.
    """
    symbols: list[str] = []
    for change in changes:
        for symbol in symbols_for_change(provider.id, change):
            if symbol not in symbols:
                symbols.append(symbol)
    return replace(build_scan_target(provider), symbols=tuple(symbols))


def symbols_for_change(provider_id: str, change: BreakingChange) -> tuple[str, ...]:
    """Mine the dotted symbols a change is actually about.

    ``call_site_hints`` is trusted as-is -- it exists specifically for this.
    ``old_api`` is used more cautiously: it's free text meant for humans
    (``"openai.createModeration()"``, or occasionally prose), so it's only
    taken when it looks like a bare dotted symbol once a trailing call
    ``(...)`` is stripped -- anything with whitespace or other punctuation
    left over is prose, not a symbol, and is dropped rather than guessed at.
    """
    symbols: list[str] = []

    def add(raw: str, *, allow_bare: bool) -> None:
        symbol = _qualify_symbol(provider_id, raw, allow_bare_identifier=allow_bare)
        if symbol is not None and symbol not in symbols:
            symbols.append(symbol)

    for hint in change.call_site_hints:
        add(hint, allow_bare=True)

    add_api_symbol(change.old_api, add)

    return tuple(symbols)


def symbols_for_api(provider_id: str, api: str) -> tuple[str, ...]:
    """Normalize one documented API symbol into the scanner namespace."""
    symbols: list[str] = []

    def add(raw: str, *, allow_bare: bool) -> None:
        symbol = _qualify_symbol(provider_id, raw, allow_bare_identifier=allow_bare)
        if symbol is not None and symbol not in symbols:
            symbols.append(symbol)

    add_api_symbol(api, add)
    return tuple(symbols)


def add_api_symbol(api: str, add: Callable[..., None]) -> None:
    """Remove a call suffix before handing one documented API to ``add``."""
    candidate = api.strip()
    if candidate.endswith(")"):
        candidate = candidate.split("(", 1)[0].strip()
    add(candidate, allow_bare=False)


# Private compatibility alias for older internal callers/tests. New code uses
# the public helper above so the matcher and scanner share one normalization
# rule.
_symbols_from_change = symbols_for_change


_DOTTED_SYMBOL_RE = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+")
_BARE_IDENTIFIER_RE = re.compile(r"[A-Za-z_]\w*")


def _looks_like_dotted_symbol(text: str) -> bool:
    """Does ``text`` look like a bare dotted identifier chain, e.g.
    ``openai.moderations.create`` -- no whitespace, no stray punctuation?"""
    return bool(_DOTTED_SYMBOL_RE.fullmatch(text))


def _qualify_symbol(provider_id: str, raw: str, *, allow_bare_identifier: bool) -> str | None:
    """Return a scanner-namespace symbol or reject free-form prose."""
    text = raw.strip()
    if not text:
        return None
    if _looks_like_dotted_symbol(text):
        head = text.split(".", 1)[0]
        return text if not provider_id or head == provider_id else f"{provider_id}.{text}"
    if allow_bare_identifier and provider_id and _BARE_IDENTIFIER_RE.fullmatch(text):
        return f"{provider_id}.{text}"
    return None


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


def _npm_package_names(target: ScanTarget) -> list[str]:
    """The target's npm-ecosystem packages -- all of ``sdk_packages`` when no
    per-package ecosystem refs were provided (legacy callers/tests)."""
    if not target.sdk_package_refs:
        return list(target.sdk_packages)
    names = []
    for name, registry_name in target.sdk_package_refs:
        spec = ecosystems_registry.ecosystem_for_registry(registry_name)
        if spec is not None and spec.id == "javascript":
            names.append(name)
    return names


def scan_checkout(
    checkout: Checkout,
    target: ScanTarget,
    *,
    repo_full_name: str = "",
    scanner: CallSiteScanner | None = None,
    change: BreakingChange | None = None,
    judge: object | None = None,
    prepare_package_manager_runtime: bool = False,
    package_manager_timeout: float = 90.0,
) -> RepoScanResult:
    """Scan an already-acquired checkout for manifests + call sites.

    Dispatches on the checkout's detected ecosystem: JavaScript keeps the
    binding-aware :class:`CallSiteScanner` + npm lockfile resolution;
    every other known ecosystem goes through the generic import scanner
    and its own manifest parsers (:mod:`depfix.ecosystems`). An unknown
    ecosystem still runs the JS scanner -- the historical behavior, and
    the right conservative default for polyglot or unmarked trees.

    ``scanner`` lets a caller (e.g. the CLI, wiring in ``scan_max_file_bytes``/
    ``scan_max_files`` from :class:`depfix.config.Settings`) supply a
    pre-configured :class:`CallSiteScanner`; a default is constructed when
    omitted so tests and simple callers don't have to.
    """
    ecosystem_id = ecosystems_registry.detect(checkout.path)
    spec = ecosystems_registry.get(ecosystem_id)
    dependencies: list[DeclaredDependency] = []
    preparation: object | None = None

    if prepare_package_manager_runtime and (spec is None or spec.id == "javascript"):
        from depfix.verify.manager import prepare_package_manager

        preparation = prepare_package_manager(checkout.path, timeout=package_manager_timeout)

    if spec is not None and spec.id != "javascript":
        from depfix.ecosystems.callsites import GenericImportScanner, packages_for_spec

        call_site_result = GenericImportScanner(spec).scan(checkout.path, target)
        if spec.scan_dependencies is not None:
            packages = packages_for_spec(target, spec)
            for declaration in spec.scan_dependencies(checkout.path, packages):
                dependencies.append(
                    DeclaredDependency(
                        package=declaration.package,
                        manifest_path=declaration.manifest_path,
                        declared_range=declaration.declared_version,
                        resolved_version=declaration.resolved_version,
                        source=declaration.source,
                    )
                )
    else:
        manifest_scan = scan_manifests(checkout.path, _npm_package_names(target))
        call_site_result = (scanner or CallSiteScanner()).scan(checkout.path, target)
        dependencies = [
            DeclaredDependency(
                package=match.package,
                manifest_path=match.manifest_path,
                declared_range=match.declared_range,
                resolved_version=match.resolved_version,
                source=match.source,
            )
            for match in manifest_scan.matches
        ]

    if judge is not None and change is not None and call_site_result.call_sites:
        call_site_result.call_sites = judge.judge(change, call_site_result.call_sites, checkout.path)

    manifest_matches = [
        f"{dependency.package}@{dependency.resolved_version or dependency.declared_range or '?'} "
        f"({dependency.source}, {dependency.manifest_path})"
        for dependency in dependencies
    ]

    return RepoScanResult(
        repo_full_name=repo_full_name,
        commit_sha=_current_commit_sha(checkout.path),
        call_sites=call_site_result.call_sites,
        manifest_matches=manifest_matches,
        dependencies=dependencies,
        files_scanned=call_site_result.files_scanned,
        errors=call_site_result.errors,
        package_manager_preparation=preparation,
    )


def scan_path(
    path: str | Path,
    target: ScanTarget,
    *,
    repo_full_name: str = "",
    scanner: CallSiteScanner | None = None,
    change: BreakingChange | None = None,
    judge: object | None = None,
    prepare_package_manager_runtime: bool = False,
    package_manager_timeout: float = 90.0,
) -> RepoScanResult:
    """Scan a local directory directly, with no clone/GitHub App involved."""
    checkout = CloneService().local(path)
    return scan_checkout(
        checkout, target, repo_full_name=repo_full_name, scanner=scanner, change=change, judge=judge,
        prepare_package_manager_runtime=prepare_package_manager_runtime,
        package_manager_timeout=package_manager_timeout,
    )


def scan_repo(
    owner: str,
    repo: str,
    target: ScanTarget,
    *,
    gh_auth: GitHubAppAuth,
    clone_service: CloneService,
    ref: str | None = None,
    scanner: CallSiteScanner | None = None,
    change: BreakingChange | None = None,
    judge: object | None = None,
    prepare_package_manager_runtime: bool = False,
    package_manager_timeout: float = 90.0,
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
        return scan_checkout(
            checkout, target, repo_full_name=f"{owner}/{repo}", scanner=scanner, change=change, judge=judge,
            prepare_package_manager_runtime=prepare_package_manager_runtime,
            package_manager_timeout=package_manager_timeout,
        )
    finally:
        clone_service.cleanup(checkout)
