"""Last-resort module-load oracle for CommonJS and ESM JavaScript."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from depfix.verify.sandbox import DEFAULT_MAX_OUTPUT_BYTES, run_sandboxed


@dataclass(frozen=True)
class SmokeResult:
    ran: bool
    passed: bool
    error: str = ""
    skipped_reason: str = ""

def run_smoke_check(root: Path, relpath: str, *, timeout: float = 30, max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES) -> SmokeResult:
    suffix = Path(relpath).suffix
    if suffix == ".py":
        return _run_python_smoke(root, relpath, timeout=timeout, max_output_bytes=max_output_bytes)
    if suffix not in {".js", ".cjs", ".mjs"}:
        return SmokeResult(False, False, skipped_reason="smoke check supports .js/.cjs/.mjs/.py only")
    if shutil.which("node") is None:
        return SmokeResult(False, False, skipped_reason="node not on PATH")
    subject = (root / relpath).resolve()
    if not subject.is_file():
        return SmokeResult(False, False, skipped_reason=f"{relpath} not found")
    if suffix == ".mjs":
        script = (f"import({json.dumps(str(subject))}).then(() => process.exit(0))"
                  ".catch(e => { console.error(e.message); process.exit(1); })")
    else:
        script = f"try {{ require({json.dumps(str(subject))}); }} catch(e) {{ console.error(e.message); process.exit(1); }}"
    result = run_sandboxed(["node", "-e", script], cwd=root, timeout=timeout, max_output_bytes=max_output_bytes)
    if result.timed_out:
        return SmokeResult(True, False, error="smoke check timed out")
    return SmokeResult(True, result.exit_code == 0, error=(result.stderr or result.stdout).strip()[:500])


def _run_python_smoke(root: Path, relpath: str, *, timeout: float, max_output_bytes: int) -> SmokeResult:
    """``py_compile`` the edited file -- syntax-level only, deliberately.

    The JS smoke check actually *loads* the module; importing an edited
    Python module would execute its top-level code against whatever the
    venv happens to contain, which is a heavier, less predictable oracle.
    Compilation catches the "LLM produced non-parsing code" class of
    failure, which is what this last-resort check exists for.
    """
    from depfix.ecosystems.python_runtime import smoke_argv
    from depfix.ecosystems.specs import PYTHON

    argv = smoke_argv(root, relpath)
    if argv is None:
        return SmokeResult(False, False, skipped_reason="python3 not on PATH")
    if not (root / relpath).is_file():
        return SmokeResult(False, False, skipped_reason=f"{relpath} not found")
    result = run_sandboxed(
        argv, cwd=root, timeout=timeout, max_output_bytes=max_output_bytes,
        extra_allowlist=PYTHON.env_allowlist_extra,
    )
    if result.timed_out:
        return SmokeResult(True, False, error="smoke check timed out")
    return SmokeResult(True, result.exit_code == 0, error=(result.stderr or result.stdout).strip()[:500])
