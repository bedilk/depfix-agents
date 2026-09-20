"""JavaScript dependency-source edits and lockfile refresh adapters."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from depfix.core.models import BreakingChange

_RANGE = re.compile(r"^(?P<op>[\^~>=<]*)(?:v)?(?P<major>\d+)(?:\.\d+)?(?:\.\d+)?(?:.*)$")
_SEMVER = re.compile(r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:[-+][0-9A-Za-z.-]+)?$")
_SECTIONS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
_SKIP = {"node_modules", ".git", "dist", "build", "coverage", ".next"}


@dataclass(frozen=True)
class ManifestBump:
    manifest_relpath: str
    original_content: str
    fixed_content: str
    package: str
    section: str
    old_range: str
    new_range: str

    @property
    def note(self) -> str:
        return (f"{self.manifest_relpath}: bumped {self.package} {self.section} "
                f"{self.old_range!r} -> {self.new_range!r}; regenerate the lockfile before merging")


@dataclass(frozen=True)
class DriftPlan:
    """Safe manifest edits for a drift update, plus explicit refusals."""

    bumps: list[ManifestBump]
    declines: list[str]


def _major(value: str) -> int | None:
    # Stripe-style dated API versions are not semver package releases.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        return None
    match = _RANGE.match(value.strip())
    return int(match.group("major")) if match else None


def _bump_range(value: str, major: int) -> str | None:
    raw = value.strip()
    if not raw or raw in {"*", "x", "latest"} or ":" in raw:
        return None
    match = _RANGE.match(raw)
    if match is None:
        return None
    return f"{match.group('op') or '^'}{major}.0.0"


def _semver(value: str) -> tuple[int, int, int] | None:
    match = _SEMVER.fullmatch(value.strip())
    if match is None:
        return None
    return tuple(int(match.group(part)) for part in ("major", "minor", "patch"))


def dependency_drift_policy(change: BreakingChange) -> str:
    """Return the review policy for a registry version movement.

    Patch/minor drift is an ordinary verified manifest update. A forward
    major drift becomes a draft review PR candidate; it must still pass the
    normal validation and verification policy before it can be committed.
    """
    old, new = _semver(change.old_version), _semver(change.new_version)
    if old is None or new is None or new <= old:
        return "declined"
    return "automatic" if old[0] == new[0] else "review_pr"


def _replace_range_version(value: str, new_version: str) -> str | None:
    raw = value.strip()
    if not raw or raw in {"*", "x", "latest"} or ":" in raw:
        return None
    match = _RANGE.match(raw)
    if match is None:
        return None
    return f"{match.group('op')}{new_version}"


def build_dependency_drift_plan(root: Path, change: BreakingChange) -> DriftPlan:
    """Build npm edits for a verified drift or draft review PR.

    This is deliberately separate from ``build_manifest_bumps``: API
    migrations always move to a new major, whereas a registry drift preserves
    the declared range operator and targets only the observed old version.
    Other ecosystem adapters can share the policy while supplying their own
    manifest writer at this seam.
    """
    policy = dependency_drift_policy(change)
    if policy == "declined":
        return DriftPlan([], [])
    new_version = _semver(change.new_version)
    if new_version is None:
        return DriftPlan([], [])
    catalog_bumps = _build_pnpm_catalog_bumps(root, change)
    if catalog_bumps:
        # ``catalog:`` is an indirection: the workspace file is the only
        # authoritative manifest. Editing consumers would defeat pnpm's
        # shared-version model and leave the lockfile inconsistent.
        return DriftPlan(catalog_bumps, [])
    bumps: list[ManifestBump] = []
    declines: list[str] = []
    for path in root.rglob("package.json"):
        if any(part in _SKIP for part in path.relative_to(root).parts[:-1]):
            continue
        try:
            original = path.read_text(encoding="utf-8")
            document = json.loads(original)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(document, dict):
            continue
        for section in _SECTIONS:
            dependencies = document.get(section)
            current = dependencies.get(change.package) if isinstance(dependencies, dict) else None
            if not isinstance(current, str):
                continue
            current_version = _semver(current.lstrip("^~<>= "))
            new_range = _replace_range_version(current, change.new_version)
            if current_version is None or new_range is None:
                declines.append(
                    f"{path.relative_to(root).as_posix()}: {change.package} is declared {current!r}, "
                    "which depfix will not rewrite automatically"
                )
                break
            if current_version != _semver(change.old_version):
                continue
            if policy == "automatic" and current_version[0] != new_version[0]:
                declines.append(
                    f"{path.relative_to(root).as_posix()}: refusing to bump {change.package} {current!r} "
                    f"to {change.new_version} -- that crosses a major boundary"
                )
                break
            if new_version <= current_version:
                continue
            dependencies[change.package] = new_range
            indent = 4 if "\n    \"" in original else 2
            fixed = json.dumps(document, indent=indent) + ("\n" if original.endswith("\n") else "")
            bumps.append(ManifestBump(path.relative_to(root).as_posix(), original, fixed,
                                      change.package, section, current, new_range))
            break
    return DriftPlan(bumps, declines)


def _build_pnpm_catalog_bumps(
    root: Path, change: BreakingChange, *, target_version: str | None = None,
) -> list[ManifestBump]:
    """Build format-preserving edits to every pnpm catalog the repo uses.

    pnpm workspaces declare consumers as ``package: catalog:`` and place the
    actual version under the root ``catalog:`` mapping. Named consumers such
    as ``package: catalog:platform`` are owned by ``catalogs.platform``. We
    deliberately edit only that source-of-truth mapping, retaining comments,
    quote style, and unrelated YAML. A monorepo may intentionally use the
    same package through multiple named catalogs, so all explicitly-used
    owning entries are updated together.
    """
    workspace = root / "pnpm-workspace.yaml"
    catalog_names = _pnpm_catalog_consumers(root, change.package)
    if not workspace.is_file() or not catalog_names:
        return []
    try:
        original = workspace.read_text(encoding="utf-8")
    except OSError:
        return []

    fixed = original
    bumped: list[ManifestBump] = []
    for catalog_name in sorted(catalog_names):
        replacement = _replace_pnpm_catalog_entry(
            fixed, change, catalog_name, target_version=target_version,
        )
        if replacement is None:
            continue
        prior, fixed, old_range, new_range = replacement
        bumped.append(ManifestBump(
            "pnpm-workspace.yaml", prior, fixed, change.package,
            "catalog" if not catalog_name else f"catalog:{catalog_name}", old_range, new_range,
        ))
    if not bumped:
        return []
    # WorkspaceEditor needs one edit per physical file. Multiple catalog
    # entries therefore collapse to a single original->final diff.
    return [ManifestBump(
        "pnpm-workspace.yaml", original, fixed, change.package,
        "catalog", bumped[0].old_range,
        bumped[-1].new_range,
    )]


def _replace_pnpm_catalog_entry(
    original: str, change: BreakingChange, catalog_name: str, *, target_version: str | None = None,
) -> tuple[str, str, str, str] | None:
    """Replace one known pnpm catalog entry without reserializing YAML."""

    lines = original.splitlines(keepends=True)
    catalog_indent: int | None = None
    catalogs_indent: int | None = None
    package_pattern = re.compile(
        rf"^(?P<indent>\s*)(?P<quote>['\"]?){re.escape(change.package)}(?P=quote)"
        r"\s*:\s*(?P<value>[^#\r\n]+?)(?P<suffix>\s*(?:#.*)?(?:\r?\n)?)$"
    )
    for index, line in enumerate(lines):
        if catalog_indent is None:
            if catalog_name == "":
                match = re.match(r"^(?P<indent>\s*)catalog\s*:\s*(?:#.*)?(?:\r?\n)?$", line)
                if match:
                    catalog_indent = len(match.group("indent"))
                continue
            match = re.match(r"^(?P<indent>\s*)catalogs\s*:\s*(?:#.*)?(?:\r?\n)?$", line)
            if match:
                catalogs_indent = len(match.group("indent"))
            elif catalogs_indent is not None and line.strip() and len(line) - len(line.lstrip()) <= catalogs_indent:
                break
            elif catalogs_indent is not None:
                named = re.match(
                    rf"^(?P<indent>\s*){re.escape(catalog_name)}\s*:\s*(?:#.*)?(?:\r?\n)?$",
                    line,
                )
                if named and len(named.group("indent")) > catalogs_indent:
                    catalog_indent = len(named.group("indent"))
            continue
        if line.strip() and len(line) - len(line.lstrip()) <= catalog_indent:
            break
        match = package_pattern.match(line)
        if match is None or len(match.group("indent")) <= catalog_indent:
            continue
        current = match.group("value").strip()
        old_version = _semver(change.old_version)
        new_range = _replace_range_version(current, target_version or change.new_version)
        if old_version is None or _semver(current.lstrip("^~<>= ")) != old_version or new_range is None:
            return None
        lines[index] = (
            f"{match.group('indent')}{match.group('quote')}{change.package}"
            f"{match.group('quote')}: {new_range}{match.group('suffix')}"
        )
        fixed = "".join(lines)
        return original, fixed, current, new_range
    return None


def _pnpm_catalog_consumers(root: Path, package: str) -> set[str]:
    """Return catalog names that own *package* in this workspace.

    The empty string represents pnpm's default ``catalog:``. A consumer must
    name a catalog explicitly before its matching ``catalogs.<name>`` entry
    may be edited; this keeps unrelated named catalogs untouched.
    """
    names: set[str] = set()
    for path in root.rglob("package.json"):
        if any(part in _SKIP for part in path.relative_to(root).parts[:-1]):
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for section in _SECTIONS:
            dependencies = document.get(section)
            if not isinstance(dependencies, dict):
                continue
            value = dependencies.get(package)
            if not isinstance(value, str) or not value.startswith("catalog:"):
                continue
            names.add(value.removeprefix("catalog:"))
    return names


def build_dependency_drift_bumps(root: Path, change: BreakingChange) -> list[ManifestBump]:
    """Retained compatibility seam for callers that only need writable edits."""
    return build_dependency_drift_plan(root, change).bumps


def build_manifest_bumps(root: Path, change: BreakingChange) -> list[ManifestBump]:
    """Build edits for manifests that pin the migrated package below its new major."""
    new_major = _major(change.new_version)
    if new_major is None:
        return []
    catalog_bumps = _build_pnpm_catalog_bumps(
        root, change, target_version=f"{new_major}.0.0",
    )
    if catalog_bumps:
        # A source migration in a pnpm workspace must still update the
        # workspace catalog, not the ``catalog:`` placeholder in consumers.
        return catalog_bumps
    bumps: list[ManifestBump] = []
    for path in root.rglob("package.json"):
        if any(part in _SKIP for part in path.relative_to(root).parts[:-1]):
            continue
        try:
            original = path.read_text(encoding="utf-8")
            document = json.loads(original)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(document, dict):
            continue
        for section in _SECTIONS:
            dependencies = document.get(section)
            current = dependencies.get(change.package) if isinstance(dependencies, dict) else None
            if not isinstance(current, str):
                continue
            old_major = _major(current)
            new_range = _bump_range(current, new_major)
            if old_major is None or old_major >= new_major or new_range is None:
                # This section's pin isn't bumpable (unparseable, already
                # current, or no rewritable range) -- a *different* section
                # (e.g. peerDependencies vs dependencies) may still have a
                # bumpable pin for the same package, so keep looking rather
                # than abandoning the whole manifest.
                continue
            dependencies[change.package] = new_range
            indent = 4 if "\n    \"" in original else 2
            fixed = json.dumps(document, indent=indent) + ("\n" if original.endswith("\n") else "")
            bumps.append(ManifestBump(path.relative_to(root).as_posix(), original, fixed,
                                      change.package, section, current, new_range))
            break
    return bumps


def try_refresh_javascript_lockfile(
    root: Path, *, timeout: float = 120.0, max_output_bytes: int = 2_000_000,
) -> tuple[bool, str]:
    """Refresh the lockfile owned by a JavaScript workspace.

    This is deliberately package-manager aware: ``package.json`` and pnpm
    catalog edits both change source-of-truth declarations, while lockfiles
    are generated output. The operation runs only in a disposable checkout,
    uses the repository's declared/cached runtime, and disables lifecycle
    scripts.
    """
    from depfix.scanners.workspace import find_workspace_root
    from depfix.verify.manager import prepare_package_manager
    from depfix.verify.sandbox import run_sandboxed

    workspace = find_workspace_root(root)
    prepared = prepare_package_manager(workspace, timeout=min(timeout, 90.0))
    if not prepared.ready:
        return False, prepared.detail or "JavaScript package-manager runtime unavailable"
    manager = prepared.package_manager
    executable = str(prepared.executable) if prepared.installed else manager
    if manager == "pnpm":
        argv = [executable, "install", "--lockfile-only", "--ignore-scripts"]
    elif manager == "npm":
        argv = [executable, "install", "--package-lock-only", "--ignore-scripts"]
    elif manager == "yarn":
        argv = [executable, "install", "--ignore-scripts"]
        if _manager_major(prepared.version) >= 2:
            argv.append("--mode=update-lockfile")
    elif manager == "bun":
        argv = [executable, "install", "--lockfile-only", "--ignore-scripts"]
    else:
        return False, f"unsupported JavaScript package manager: {manager}"
    result = run_sandboxed(argv, cwd=workspace, timeout=timeout, max_output_bytes=max_output_bytes)
    if not result.ok:
        message = result.error or result.stderr.strip() or f"exit {result.exit_code}"
        return False, f"{manager} lockfile refresh failed: {message[:200]}"
    return True, f"lockfile refreshed via `{' '.join(argv)}`"


def _manager_major(version: str) -> int:
    try:
        return int(version.split(".", 1)[0])
    except ValueError:
        return 0


def try_regenerate_lockfile(
    root: Path, *, timeout: float = 120.0, ignore_scripts: bool = True,
    max_output_bytes: int = 2_000_000,
) -> tuple[bool, str]:
    """Compatibility entry point for callers that need a JS lock refresh.

    ``ignore_scripts`` remains part of the interface for older callers; all
    supported refresh commands already disable lifecycle scripts.
    """
    del ignore_scripts
    return try_refresh_javascript_lockfile(
        root, timeout=timeout, max_output_bytes=max_output_bytes,
    )


def try_refresh_pnpm_lockfile(
    root: Path, *, timeout: float = 120.0, max_output_bytes: int = 2_000_000,
) -> tuple[bool, str]:
    """Backward-compatible alias for the package-manager-aware refresher."""
    return try_refresh_javascript_lockfile(
        root, timeout=timeout, max_output_bytes=max_output_bytes,
    )


def lockfile_paths(root: Path) -> list[Path]:
    names = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb"}
    return [path for path in root.rglob("*") if path.is_file() and path.name in names and "node_modules" not in path.parts]
