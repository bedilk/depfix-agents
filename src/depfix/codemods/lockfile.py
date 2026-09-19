"""Conservative package.json dependency-major bumps and optional lock refresh."""
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
    """Return the safe handling policy for a registry version movement.

    The interface intentionally has only two outcomes.  Callers do not need
    to understand semver parsing or special versions: a major/unparseable
    change needs a vetted API migration; a forward patch/minor update can be
    applied as a verified manifest edit.
    """
    old, new = _semver(change.old_version), _semver(change.new_version)
    if old is None or new is None or new <= old or old[0] != new[0]:
        return "vetted_migration_required"
    return "automatic"


def _replace_range_version(value: str, new_version: str) -> str | None:
    raw = value.strip()
    if not raw or raw in {"*", "x", "latest"} or ":" in raw:
        return None
    match = _RANGE.match(raw)
    if match is None:
        return None
    return f"{match.group('op') or '^'}{new_version}"


def build_dependency_drift_plan(root: Path, change: BreakingChange) -> DriftPlan:
    """Build safe npm manifest edits for a patch/minor registry drift.

    This is deliberately separate from ``build_manifest_bumps``: API
    migrations always move to a new major, whereas a registry drift must
    preserve the declared range operator and never silently cross a major.
    Other ecosystem adapters can share the policy while supplying their own
    manifest writer at this seam.
    """
    if dependency_drift_policy(change) != "automatic":
        return DriftPlan([], [])
    new_version = _semver(change.new_version)
    if new_version is None:
        return DriftPlan([], [])
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
            if current_version[0] != new_version[0]:
                declines.append(
                    f"{path.relative_to(root).as_posix()}: refusing to bump {change.package} {current!r} "
                    f"to {change.new_version} -- that crosses a major boundary and needs a vetted migration"
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


def build_dependency_drift_bumps(root: Path, change: BreakingChange) -> list[ManifestBump]:
    """Retained compatibility seam for callers that only need writable edits."""
    return build_dependency_drift_plan(root, change).bumps


def build_manifest_bumps(root: Path, change: BreakingChange) -> list[ManifestBump]:
    """Build edits for manifests that pin the migrated package below its new major."""
    new_major = _major(change.new_version)
    if new_major is None:
        return []
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


def try_regenerate_lockfile(root: Path, *, timeout: float = 120.0,
                            ignore_scripts: bool = True, max_output_bytes: int = 2_000_000) -> tuple[bool, str]:
    """Refresh a lockfile in a disposable checkout, without lifecycle scripts."""
    import shutil

    from depfix.scanners.workspace import find_workspace_root
    from depfix.verify.manager import build_install_argv
    from depfix.verify.sandbox import run_sandboxed
    install_root = find_workspace_root(root)
    argv = build_install_argv(install_root, ignore_scripts=ignore_scripts)
    if shutil.which(argv[0]) is None:
        return False, f"{argv[0]} not on PATH"
    result = run_sandboxed(argv, cwd=install_root, timeout=timeout, max_output_bytes=max_output_bytes)
    return (True, f"lockfile regenerated via `{' '.join(argv)}`") if result.ok else (
        False, f"lockfile regeneration failed (exit {result.exit_code}): {result.stderr[:200]}")


def lockfile_paths(root: Path) -> list[Path]:
    names = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb"}
    return [path for path in root.rglob("*") if path.is_file() and path.name in names and "node_modules" not in path.parts]
