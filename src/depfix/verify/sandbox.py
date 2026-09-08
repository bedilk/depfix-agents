"""Sandboxed subprocess execution for running an untrusted repo's own
install/test commands.

Everything :mod:`depfix.verify.manager` and :mod:`depfix.verify.runner`
shell out to (``npm ci``, ``npm test``, ...) is code the target repo
controls, not us -- an allowlisted environment (not a denylist), a fixed
argv (never a shell string), a process-group kill on timeout, and an
output byte cap are all here to keep a hostile ``package.json`` script
from doing much beyond wasting CPU time inside its own checkout.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

#: Environment variables passed through to the sandboxed process. Everything
#: else -- credentials, tokens, cloud SDK config, etc. that happen to be set
#: in *our* process environment -- is stripped. An allowlist is used (rather
#: than denylisting known-sensitive names) because we can't enumerate every
#: secret-shaped env var a deployment might set, but we *can* enumerate the
#: handful of things `npm`/`node`/`yarn`/`pnpm` actually need to run.
ENV_ALLOWLIST = frozenset(
    {
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TMPDIR",
        "TEMP",
        "TMP",
        "CI",
        "NODE_ENV",
        "NODE_OPTIONS",
        "NODE_PATH",
        "NPM_CONFIG_CACHE",
        "NPM_CONFIG_REGISTRY",
        "NPM_CONFIG_PREFIX",
        "NPM_CONFIG_USERCONFIG",
        "npm_config_cache",
        "npm_config_registry",
        "YARN_CACHE_FOLDER",
        "PNPM_HOME",
        # Windows equivalents of PATH/HOME/TEMP -- harmless no-ops on POSIX.
        "SystemRoot",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
    }
)

#: Default cap on how much combined stdout/stderr we'll buffer in memory
#: before truncating -- a runaway `console.log` loop in a repo's own test
#: script shouldn't be able to exhaust our process's memory.
DEFAULT_MAX_OUTPUT_BYTES = 2_000_000

_TRUNCATION_NOTICE = "\n...[output truncated by depfix sandbox]...\n"


@dataclass
class SandboxResult:
    """Outcome of one sandboxed subprocess run."""

    argv: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.timed_out and not self.error and self.exit_code == 0


def _sandboxed_env(extra_env: dict[str, str] | None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in ENV_ALLOWLIST}
    if extra_env:
        env.update(extra_env)
    return env


def _truncate(data: bytes, max_bytes: int) -> str:
    if len(data) <= max_bytes:
        return data.decode("utf-8", errors="replace")
    head = data[:max_bytes]
    return head.decode("utf-8", errors="replace") + _TRUNCATION_NOTICE


def _kill_process_group(proc: subprocess.Popen) -> None:
    """Kill the whole process group (not just ``proc`` itself) so a test
    runner's child processes (workers, watchers) don't survive a timeout."""
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_sandboxed(
    argv: list[str] | tuple[str, ...],
    *,
    cwd: str | Path,
    timeout: float,
    extra_env: dict[str, str] | None = None,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> SandboxResult:
    """Run ``argv`` (a fixed arg list, never a shell string) inside ``cwd``
    with an allowlisted environment, killing the whole process group if it
    exceeds ``timeout`` seconds.
    """
    argv = tuple(argv)
    start = time.monotonic() * 1000.0
    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(cwd),
            env=_sandboxed_env(extra_env),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,  # own process group, for killpg on timeout
        )
    except OSError as exc:
        return SandboxResult(
            argv=argv,
            exit_code=-1,
            stdout="",
            stderr="",
            duration_ms=time.monotonic() * 1000.0 - start,
            error=f"could not start {argv[0]}: {exc}",
        )

    try:
        raw_stdout, raw_stderr = proc.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        _kill_process_group(proc)
        raw_stdout, raw_stderr = proc.communicate()
        timed_out = True

    duration_ms = time.monotonic() * 1000.0 - start
    return SandboxResult(
        argv=argv,
        exit_code=proc.returncode if proc.returncode is not None else -1,
        stdout=_truncate(raw_stdout, max_output_bytes),
        stderr=_truncate(raw_stderr, max_output_bytes),
        duration_ms=duration_ms,
        timed_out=timed_out,
    )
