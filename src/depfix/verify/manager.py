"""Package-manager detection and dependency installation for a checkout
about to have its test suite run.

Detection is lockfile-based (not ``package.json``-based) because the
lockfile is what actually determines which client *must* be used --
installing an npm-locked repo with yarn (or vice versa) routinely produces
a different dependency tree than CI would have used.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from depfix.verify.sandbox import DEFAULT_MAX_OUTPUT_BYTES, SandboxResult, run_sandboxed

#: Ordered (lockfile, package_manager) pairs -- first match wins. Order
#: matters only in the pathological case where multiple lockfiles coexist
#: (e.g. a repo mid-migration between package managers); npm is the most
#: conservative default since it's always present with Node.
_LOCKFILE_MANAGERS: tuple[tuple[str, str], ...] = (
    ("bun.lockb", "bun"),
    ("package-lock.json", "npm"),
    ("npm-shrinkwrap.json", "npm"),
    ("yarn.lock", "yarn"),
    ("pnpm-lock.yaml", "pnpm"),
)

DEFAULT_PACKAGE_MANAGER = "npm"


@dataclass
class InstallResult:
    """Outcome of installing a checkout's dependencies."""

    package_manager: str
    sandbox: SandboxResult | None = None
    skipped_reason: str = ""

    @property
    def ok(self) -> bool:
        if self.skipped_reason:
            return False
        return self.sandbox is not None and self.sandbox.ok


def detect_package_manager(root: str | Path) -> str:
    """Return the package manager implied by ``root``'s lockfile, falling
    back to :data:`DEFAULT_PACKAGE_MANAGER` (npm) if none is present."""
    root = Path(root)
    for lockfile, manager in _LOCKFILE_MANAGERS:
        if (root / lockfile).is_file():
            return manager
    return DEFAULT_PACKAGE_MANAGER


def _install_argv(package_manager: str, root: Path, *, ignore_scripts: bool) -> list[str]:
    has_lockfile = any((root / lockfile).is_file() for lockfile, mgr in _LOCKFILE_MANAGERS if mgr == package_manager)

    if package_manager == "bun":
        argv = ["bun", "install"]
        if has_lockfile: argv.append("--frozen-lockfile")
    elif package_manager == "npm":
        argv = ["npm", "ci"] if has_lockfile else ["npm", "install"]
    elif package_manager == "yarn":
        argv = ["yarn", "install"]
        if has_lockfile:
            argv.append("--frozen-lockfile")
    elif package_manager == "pnpm":
        argv = ["pnpm", "install"]
        if has_lockfile:
            argv.append("--frozen-lockfile")
    else:
        argv = ["npm", "install"]

    if ignore_scripts:
        argv.append("--ignore-scripts")
    return argv


def build_install_argv(root: str | Path, *, ignore_scripts: bool, package_manager: str | None = None) -> list[str]:
    """Public entry point for the install command :func:`install_dependencies`
    would run for ``root``, for callers (e.g. :mod:`depfix.codemods.lockfile`)
    that need to regenerate a lockfile without duplicating the detection
    logic and without reaching into this module's private helpers."""
    root = Path(root)
    manager = package_manager or detect_package_manager(root)
    return _install_argv(manager, root, ignore_scripts=ignore_scripts)


def install_dependencies(
    root: str | Path,
    *,
    timeout: float,
    ignore_scripts: bool = True,
    package_manager: str | None = None,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> InstallResult:
    """Install ``root``'s dependencies, defaulting to ``--ignore-scripts``
    so a hostile ``postinstall``/``preinstall`` in a dependency (or the repo
    itself) doesn't get to run arbitrary code as a side effect of merely
    verifying a fix -- at the cost of tests that genuinely need a build
    step (native addons, codegen) failing for reasons unrelated to the fix
    under test. That tradeoff is intentional: see docs/decisions.md.
    """
    root = Path(root)
    if not (root / "package.json").is_file():
        return InstallResult(package_manager="none", skipped_reason="no package.json found")

    from depfix.scanners.workspace import find_workspace_root
    install_root = find_workspace_root(root)
    manager = package_manager or detect_package_manager(install_root)
    argv = _install_argv(manager, install_root, ignore_scripts=ignore_scripts)

    if _which(argv[0]) is None:
        return InstallResult(package_manager=manager, skipped_reason=f"{argv[0]} not found on PATH")

    result = run_sandboxed(argv, cwd=install_root, timeout=timeout, max_output_bytes=max_output_bytes)
    return InstallResult(package_manager=manager, sandbox=result)


def _which(executable: str) -> str | None:
    import shutil

    return shutil.which(executable)
