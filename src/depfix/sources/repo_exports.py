"""Repo-version-aware TypeScript export diff.

When a repository's lockfile resolves an SDK to an older major version,
feed-level ts_exports diffs may not cover the removals (they only diff
consecutive or prev-major → current versions). This module fills that gap by
comparing the *exact installed version's* exports against the *latest version's*
exports and synthesising BreakingChange records for anything removed since the
installed version.

Only meaningful for JavaScript/TypeScript providers with npm packages that
ship .d.ts files.
"""

from __future__ import annotations

import io
import logging
import tarfile

import httpx

from depfix.core.models import BreakingChange, ChangeKind, ClassificationSource
from depfix.registry.client import NpmRegistryClient, RegistryError
from depfix.scanners.models import RepoScanResult
from depfix.sources.ts_exports import _MAX_TARBALL_BYTES, _names_in_dts

logger = logging.getLogger(__name__)


def _tarball_url(package: str, version: str, base_url: str) -> str:
    scope_safe = package.replace("/", "%2f")
    short = package.rsplit("/", 1)[-1]
    return f"{base_url}/{scope_safe}/-/{short}-{version}.tgz"


def _exports_for_version(
    package: str,
    version: str,
    http: httpx.Client,
    npm_base_url: str,
) -> set[str] | None:
    """Download and extract exported names from a package version's .d.ts files."""
    url = _tarball_url(package, version, npm_base_url)
    try:
        response = http.get(url)
        if response.status_code != 200 or len(response.content) > _MAX_TARBALL_BYTES:
            return None
        names: set[str] = set()
        with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile() or not member.name.endswith(".d.ts"):
                    continue
                if member.size > 2_000_000:
                    continue
                handle = tar.extractfile(member)
                if handle is None:
                    continue
                text = handle.read().decode("utf-8", errors="replace")
                names |= _names_in_dts(text)
        return names
    except (httpx.HTTPError, tarfile.TarError, OSError) as exc:
        logger.debug("repo_exports: fetch failed for %s@%s: %s", package, version, exc)
        return None


def _installed_version_for(result: RepoScanResult, package: str) -> str | None:
    """Return the resolved version of ``package`` from the scan result's dependencies."""
    for dep in result.dependencies:
        if dep.package == package and dep.resolved_version:
            return dep.resolved_version
    return None


def _call_site_uses_export(symbol: str, provider_id: str, export_name: str) -> bool:
    """True when ``symbol`` refers to ``export_name`` from ``provider_id``."""
    prefix = f"{provider_id}."
    if not symbol.startswith(prefix):
        return False
    after_provider = symbol[len(prefix):]
    return after_provider == export_name or after_provider.startswith(f"{export_name}.")


def _export_name_from_symbol(symbol: str, provider_id: str) -> str | None:
    """Extract the top-level export name from a provider-namespaced symbol.

    E.g. ``"sentry.hub.captureMessage"`` → ``"hub"``.
    Returns ``None`` when ``symbol`` doesn't start with ``provider_id.``.
    """
    prefix = f"{provider_id}."
    if not symbol.startswith(prefix):
        return None
    after = symbol[len(prefix):]
    return after.split(".")[0]


def repo_version_exports_diff(
    package: str,
    installed_version: str,
    http: httpx.Client,
    npm: NpmRegistryClient,
) -> tuple[str, set[str]] | None:
    """Compare installed and latest exports; return ``(latest_version, removed_names)``.

    Returns ``None`` when either version's exports can't be fetched, when the
    npm registry can't be reached, or when the installed version is already the
    latest.
    """
    try:
        metadata = npm.get_package_metadata(package)
    except RegistryError as exc:
        logger.debug("repo_exports: registry error for %s: %s", package, exc)
        return None

    latest_version = metadata.dist_tags.get("latest")
    if not latest_version:
        return None

    from depfix.sources.semver import parse_semver

    installed_sv = parse_semver(installed_version)
    latest_sv = parse_semver(latest_version)
    if installed_sv is None or latest_sv is None or installed_sv >= latest_sv:
        return None

    installed_exports = _exports_for_version(package, installed_version, http, npm.base_url)
    latest_exports = _exports_for_version(package, latest_version, http, npm.base_url)
    if installed_exports is None or latest_exports is None:
        return None

    removed = installed_exports - latest_exports
    return latest_version, removed


def synthetic_changes_for_scan(
    result: RepoScanResult,
    *,
    provider_id: str,
    npm_packages: list[str],
    http: httpx.Client,
    npm: NpmRegistryClient,
) -> list[BreakingChange]:
    """Synthesise BreakingChange records for exports removed between the repo's
    installed SDK version and the latest published version.

    Only produces changes for export names that appear in ``result``'s actionable
    call sites, so every returned change has concrete call-site evidence.
    """
    changes: list[BreakingChange] = []
    seen_old_apis: set[str] = set()

    for package in npm_packages:
        installed = _installed_version_for(result, package)
        if not installed:
            continue

        diff = repo_version_exports_diff(package, installed, http, npm)
        if diff is None:
            continue

        latest_version, removed_exports = diff

        # Sub-case A: export existed in installed version but is absent in latest.
        for site in result.actionable_sites:
            for export_name in removed_exports:
                old_api = f"{provider_id}.{export_name}"
                if old_api in seen_old_apis:
                    continue
                if _call_site_uses_export(site.symbol, provider_id, export_name):
                    changes.append(
                        BreakingChange(
                            package=package,
                            old_version=installed,
                            new_version=latest_version,
                            old_api=old_api,
                            new_api="",
                            description=(
                                f"{export_name} was exported by {package}@{installed} "
                                f"but is absent from {latest_version}"
                            ),
                            migration_guide="",
                            kind=ChangeKind.METHOD_REMOVED,
                            source=ClassificationSource.SPEC_DIFF,
                            provider_id=provider_id,
                            confidence=1.0,
                        )
                    )
                    seen_old_apis.add(old_api)

        # Sub-case B: call site uses an export absent from the installed version.
        # The API was removed BEFORE the installed version — the code calls a ghost
        # API that has not existed since an earlier major.  We must detect this
        # separately because installed-exports - latest-exports is empty when both
        # versions lack the symbol (e.g. sentry startTransaction: removed in v8,
        # repo lockfile is v10, latest is v11).
        installed_exports = _exports_for_version(package, installed, http, npm.base_url)
        for site in result.actionable_sites:
            b_name: str | None = _export_name_from_symbol(site.symbol, provider_id)
            if b_name is None:
                continue
            old_api = f"{provider_id}.{b_name}"
            if old_api in seen_old_apis:
                continue
            if installed_exports is not None and b_name not in installed_exports:
                changes.append(
                    BreakingChange(
                        package=package,
                        old_version="0.0.0",
                        new_version=installed,
                        old_api=old_api,
                        new_api="",
                        description=(
                            f"{b_name} is not exported by {package}@{installed}; "
                            f"it was removed in an earlier major version"
                        ),
                        migration_guide="",
                        kind=ChangeKind.METHOD_REMOVED,
                        source=ClassificationSource.SPEC_DIFF,
                        provider_id=provider_id,
                        confidence=0.9,
                    )
                )
                seen_old_apis.add(old_api)

    return changes
