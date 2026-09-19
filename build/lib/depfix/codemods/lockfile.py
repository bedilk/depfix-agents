"""Conservative package.json dependency-major bumps and optional lock refresh."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from depfix.core.models import BreakingChange

_RANGE = re.compile(r"^(?P<op>[\^~>=<]*)(?:v)?(?P<major>\d+)(?:\.\d+)?(?:\.\d+)?(?:.*)$")
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
