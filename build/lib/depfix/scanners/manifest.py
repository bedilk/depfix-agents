"""npm manifest + lockfile scanning.

Resolves what version of a tracked SDK package a repo actually has, so the
call-site scanner can report "this repo's lockfile resolves openai to 4.1.0
but the call sites below still look like the v3 API" instead of guessing
from source code alone.

**Lockfile-first.** ``package-lock.json`` carries the *resolved* version --
what actually got installed -- which is the only thing that answers "is
this repo affected" with certainty. A semver range in ``package.json``
(``^3.0.0``) is a three-valued (yes/no/unknown) fallback when there is no
lockfile to resolve against.

**npm only.** ``yarn.lock``/``pnpm-lock.yaml`` are explicitly out of scope
here -- different formats, different week.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_SKIP_DIRS = {"node_modules", ".git", "dist", "build", "coverage", ".next", "__pycache__"}


@dataclass(frozen=True)
class DependencyMatch:
    """One tracked SDK package found in one manifest/lockfile pair."""

    package: str
    manifest_path: str
    declared_range: str | None  # what package.json says, e.g. "^4.0.0"
    resolved_version: str | None  # what the lockfile actually resolved to, if present
    source: str  # "lockfile" | "range"


@dataclass
class ManifestScan:
    """Everything found scanning one checkout's manifests for tracked SDKs."""

    manifests_found: list[str] = field(default_factory=list)
    matches: list[DependencyMatch] = field(default_factory=list)


def find_manifests(root: Path) -> list[Path]:
    """Find every ``package.json`` under ``root``.

    Monorepo-aware (walks workspace subdirectories) but skips
    ``node_modules`` and friends -- a vendored copy of the SDK inside
    ``node_modules`` is not "this repo declaring a dependency".
    """
    found: list[Path] = []
    for path in root.rglob("package.json"):
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        found.append(path)
    return sorted(found)


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("failed to parse %s: %s", path, exc)
        return None


def _declared_ranges(manifest: dict) -> dict[str, str]:
    ranges: dict[str, str] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        section = manifest.get(key) or {}
        for name, spec in section.items():
            if isinstance(spec, str):
                ranges.setdefault(name, spec)
    return ranges


def _resolve_from_lockfile_v1(lock: dict, package: str) -> str | None:
    """v1 lockfiles nest resolved deps recursively under ``dependencies``."""

    def _walk(deps: dict) -> str | None:
        if package in deps:
            version = deps[package].get("version")
            if version:
                return str(version)
        for entry in deps.values():
            nested = entry.get("dependencies")
            if nested:
                found = _walk(nested)
                if found:
                    return found
        return None

    return _walk(lock.get("dependencies") or {})


def _resolve_from_lockfile_v2plus(lock: dict, package: str) -> str | None:
    """v2/v3 lockfiles flatten every install into ``packages``, keyed by a
    ``node_modules`` path (``node_modules/foo``, or a nested workspace
    path like ``packages/api/node_modules/foo``)."""
    packages = lock.get("packages") or {}
    candidates = [
        key
        for key in packages
        if key == f"node_modules/{package}" or key.endswith(f"/node_modules/{package}")
    ]
    # Prefer the shallowest (most top-level) install for a stable answer
    # when the same package is hoisted at more than one depth.
    candidates.sort(key=lambda k: k.count("node_modules"))
    for key in candidates:
        version = packages[key].get("version")
        if version:
            return str(version)
    return None


def _resolve_from_lockfile(lock: dict, package: str) -> str | None:
    lockfile_version = int(lock.get("lockfileVersion", 1) or 1)
    if lockfile_version >= 2:
        resolved = _resolve_from_lockfile_v2plus(lock, package)
        if resolved:
            return resolved
    return _resolve_from_lockfile_v1(lock, package)


def scan_manifests(root: Path, sdk_packages: list[str]) -> ManifestScan:
    """Scan every ``package.json`` under ``root`` for ``sdk_packages``,
    resolving actual installed versions via a sibling ``package-lock.json``
    when one exists."""
    scan = ManifestScan()
    for manifest_path in find_manifests(root):
        manifest = _load_json(manifest_path)
        if manifest is None:
            continue
        scan.manifests_found.append(str(manifest_path))

        ranges = _declared_ranges(manifest)
        wanted = [pkg for pkg in sdk_packages if pkg in ranges]
        if not wanted:
            continue

        lock_path = manifest_path.parent / "package-lock.json"
        lock = _load_json(lock_path) if lock_path.exists() else None

        for package in wanted:
            resolved = _resolve_from_lockfile(lock, package) if lock else None
            scan.matches.append(
                DependencyMatch(
                    package=package,
                    manifest_path=str(manifest_path),
                    declared_range=ranges[package],
                    resolved_version=resolved,
                    source="lockfile" if resolved else "range",
                )
            )
    return scan


_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)")


def _parse_semver(text: str) -> tuple[int, int, int] | None:
    match = _SEMVER_RE.match(text.strip())
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def affects_version(resolved_version: str, old_version: str, new_version: str) -> bool | None:
    """Is ``resolved_version`` on the "old", pre-breaking-change side of the
    ``old_version -> new_version`` boundary?

    Returns ``None`` (unknown) rather than guessing when any of the inputs
    isn't parseable as plain semver -- silently guessing "no" would hide a
    real match, and guessing "yes" would spam call sites in unaffected
    repos.
    """
    resolved = _parse_semver(resolved_version)
    new = _parse_semver(new_version)
    if resolved is None or new is None:
        return None
    return resolved < new


def range_allows_major(range_spec: str, major: int) -> bool | None:
    """Could this semver *range* (not a resolved version) ever resolve to
    the given major version?

    Three-valued on purpose: a declared range like ``^3.0.0`` clearly
    cannot resolve to major ``4`` (``False``); ``>=3.0.0`` clearly can
    (``True``); ``latest`` / ``*`` / a git URL / workspace protocol is
    ``None`` -- "can't tell from the range alone, check the lockfile".
    """
    spec = range_spec.strip()
    if not spec or spec in {"*", "latest", "x"}:
        return None
    if spec.startswith(("git+", "http://", "https://", "file:", "workspace:", "link:")):
        return None

    if "||" in spec:
        results = [range_allows_major(part, major) for part in spec.split("||")]
        if any(r is True for r in results):
            return True
        if all(r is False for r in results):
            return False
        return None

    if " - " in spec:
        low, high = (p.strip() for p in spec.split(" - ", 1))
        low_v, high_v = _parse_semver(low), _parse_semver(high)
        if low_v is None or high_v is None:
            return None
        return low_v[0] <= major <= high_v[0]

    parts = spec.split()
    if len(parts) > 1:
        # Multiple space-separated constraints in one range spec -- too
        # ambiguous to reason about safely; defer to the lockfile.
        return None

    match = re.match(r"^([~^>=<]*)(\d+)", parts[0] if parts else spec)
    if not match:
        return None
    operator, base_major = match.group(1), int(match.group(2))

    if operator in ("", "=", "^", "~"):
        # ^ and ~ both pin the major for a >=1.0.0 base, which covers every
        # SDK package this scanner cares about.
        return major == base_major
    if operator in (">=", ">"):
        return major >= base_major
    if operator in ("<=", "<"):
        return major <= base_major
    return None
