"""Parsers turning a test runner's raw output into :class:`~depfix.verify.models.TestCase`\\ s.

Structured parsers (Jest/Vitest JSON, Mocha JSON, Node's TAP) come first
and are preferred whenever the repo's configured reporter produces one --
they give stable per-test identities, which is what
:mod:`depfix.verify.attribution` needs to blame a specific file for a
specific new failure. :func:`parse_fallback` exists for everything else
(a compound `"test": "eslint && jest"` script, a custom reporter, output
we failed to parse) and can only recover aggregate pass/fail *counts*,
which :mod:`depfix.verify.verifier` treats as a signal to degrade to
"SUSPECT the whole edit" rather than trust a specific attribution.
"""

from __future__ import annotations

import json
import re

from depfix.verify.models import TestCase, TestFramework, TestStatus


def parse_jest_json(raw: str) -> list[TestCase]:
    """Parse Jest's ``--json`` reporter output. Vitest's ``--reporter=json``
    output is shape-compatible with Jest's, so :data:`parse_vitest_json` is
    just an alias below rather than a second implementation."""
    data = json.loads(raw)
    cases: list[TestCase] = []
    for suite in data.get("testResults", []):
        file = suite.get("name", "") or suite.get("testFilePath", "")
        for result in suite.get("assertionResults", []):
            status_str = result.get("status", "failed")
            status = _JEST_STATUS_MAP.get(status_str, TestStatus.FAILED)
            title = result.get("fullName") or result.get("title") or "<unnamed>"
            message = "\n".join(result.get("failureMessages", []) or [])
            cases.append(TestCase(name=title, file=file, status=status, message=message))
    return cases


_JEST_STATUS_MAP = {
    "passed": TestStatus.PASSED,
    "failed": TestStatus.FAILED,
    "pending": TestStatus.SKIPPED,
    "skipped": TestStatus.SKIPPED,
    "todo": TestStatus.SKIPPED,
}

#: Vitest's JSON reporter is jest-compatible in shape.
parse_vitest_json = parse_jest_json


def parse_vitest_verbose(raw: str) -> list[TestCase]:
    """Best-effort parser for Vitest's default Unicode reporter."""
    cases: list[TestCase] = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith(("✓", "√")):
            cases.append(TestCase(name=line.lstrip("✓√ ").strip(), status=TestStatus.PASSED))
        elif line.startswith(("×", "✕")):
            cases.append(TestCase(name=line.lstrip("×✕ ").strip(), status=TestStatus.FAILED))
    return cases


def parse_mocha_json(raw: str) -> list[TestCase]:
    """Parse Mocha's ``--reporter json`` output. Mocha's JSON has no notion
    of "skipped as distinct from pending" in the flat pass/fail lists, so
    anything not in ``passes``/``failures`` is treated as SKIPPED."""
    data = json.loads(raw)
    cases: list[TestCase] = []
    seen: set[tuple[str, str]] = set()

    for entry in data.get("passes", []):
        name, file = _mocha_identity(entry)
        cases.append(TestCase(name=name, file=file, status=TestStatus.PASSED))
        seen.add((name, file))

    for entry in data.get("failures", []):
        name, file = _mocha_identity(entry)
        message = entry.get("err", {}).get("message", "") if isinstance(entry.get("err"), dict) else ""
        cases.append(TestCase(name=name, file=file, status=TestStatus.FAILED, message=message))
        seen.add((name, file))

    for entry in data.get("pending", []):
        name, file = _mocha_identity(entry)
        if (name, file) in seen:
            continue
        cases.append(TestCase(name=name, file=file, status=TestStatus.SKIPPED))

    return cases


def _mocha_identity(entry: dict) -> tuple[str, str]:
    name = entry.get("fullTitle") or entry.get("title") or "<unnamed>"
    file = entry.get("file", "") or ""
    return name, file


#: Matches Node's ``--test`` TAP output lines like ``ok 1 - some test name``
#: or ``not ok 2 - some other test name``.
_TAP_LINE_RE = re.compile(r"^(?P<ok>ok|not ok)\s+\d+\s+-\s+(?P<name>.+?)\s*$")
#: TAP diagnostics sometimes carry a ``# file:`` hint via YAML-ish blocks;
#: this is best-effort only, absence just means ``file=""``.
_TAP_FILE_HINT_RE = re.compile(r"^\s*file:\s*(?P<file>.+?)\s*$")


def parse_tap(raw: str) -> list[TestCase]:
    """Parse the TAP dialect emitted by ``node --test``."""
    cases: list[TestCase] = []
    current_file = ""
    for line in raw.splitlines():
        file_hint = _TAP_FILE_HINT_RE.match(line)
        if file_hint:
            current_file = file_hint.group("file")
            continue
        match = _TAP_LINE_RE.match(line)
        if not match:
            continue
        status = TestStatus.PASSED if match.group("ok") == "ok" else TestStatus.FAILED
        cases.append(TestCase(name=match.group("name"), file=current_file, status=status))
    return cases


#: Best-effort aggregate counters for the human-readable default reporters
#: of Jest/Vitest/Mocha, e.g. "Tests: 2 failed, 8 passed, 10 total" (Jest)
#: or "10 passing (1s)" / "2 failing" (Mocha).
_COUNT_PATTERNS: tuple[tuple[TestStatus, re.Pattern[str]], ...] = (
    (TestStatus.FAILED, re.compile(r"(?P<n>\d+)\s+failing")),
    (TestStatus.FAILED, re.compile(r"Tests:.*?(?P<n>\d+)\s+failed")),
    (TestStatus.PASSED, re.compile(r"(?P<n>\d+)\s+passing")),
    (TestStatus.PASSED, re.compile(r"Tests:.*?(?P<n>\d+)\s+passed")),
)


def parse_fallback(raw: str) -> list[TestCase]:
    """Recover only aggregate pass/fail *counts* from unrecognized output,
    as synthetic ``<aggregate {status} #N>`` cases.

    These synthetic identities are NOT stable across runs in the way real
    test identities are -- two different tests that happen to produce the
    same failure count in two different runs are indistinguishable here.
    Callers (:mod:`depfix.verify.verifier`) must treat any comparison
    involving fallback-parsed results as degraded, not as a reliable
    per-test diff. See :class:`depfix.verify.models.TestRunResult`.
    """
    cases: list[TestCase] = []
    counted: dict[TestStatus, int] = {}
    for status, pattern in _COUNT_PATTERNS:
        if status in counted:
            continue
        match = pattern.search(raw)
        if match:
            counted[status] = int(match.group("n"))

    for status, count in counted.items():
        for i in range(count):
            cases.append(TestCase(name=f"<aggregate {status.value} #{i}>", status=status))
    return cases


def parse_output(
    framework: TestFramework, stdout: str, stderr: str
) -> tuple[list[TestCase], str, bool]:
    """Dispatch to the structured parser for ``framework``, falling back to
    :func:`parse_fallback` (over the combined stdout+stderr) if the
    structured parse raises or yields nothing.

    Returns ``(cases, parse_error, used_fallback_parser)``.
    """
    parser = _STRUCTURED_PARSERS.get(framework)
    combined = stdout if stdout.strip() else stderr

    if parser is not None:
        try:
            cases = parser(stdout) if stdout.strip() else parser(stderr)
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
            fallback_cases = parse_fallback(stdout + "\n" + stderr)
            return fallback_cases, f"structured parse failed: {exc}", True
        if cases:
            return cases, "", False
        # Structured parser ran clean but found nothing -- fall through to
        # the aggregate fallback rather than silently reporting "0 tests".

    if framework in (TestFramework.VITEST, TestFramework.UNKNOWN):
        vitest_cases = parse_vitest_verbose(combined)
        if vitest_cases:
            return vitest_cases, "", True
    fallback_cases = parse_fallback(combined)
    error = "" if fallback_cases else "no recognizable test output"
    return fallback_cases, error, True


_STRUCTURED_PARSERS = {
    TestFramework.JEST: parse_jest_json,
    TestFramework.VITEST: parse_vitest_json,
    TestFramework.MOCHA: parse_mocha_json,
    TestFramework.NODE_TEST: parse_tap,
}
