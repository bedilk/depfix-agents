"""Value objects for the Week 4 test-verification subsystem.

A :class:`Verifier` (see :mod:`depfix.verify.verifier`) runs a repo's own
test suite twice -- once on the pre-fix tree, once with candidate fixes
applied -- and diffs the two :class:`TestRunResult`\\ s by test *identity*
(not by pass/fail count) to decide whether a fix introduced a regression.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class TestStatus(StrEnum):
    """Outcome of one test case in one run."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TestFramework(StrEnum):
    """Test framework detected for a checkout -- determines which reporter
    flags :mod:`depfix.verify.runner` passes and which parser in
    :mod:`depfix.verify.parsers` is used to read the results back."""

    JEST = "jest"
    VITEST = "vitest"
    MOCHA = "mocha"
    NODE_TEST = "node_test"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TestCase:
    """One test case's outcome, identified well enough to compare across
    two separate runs of the same suite."""

    name: str
    file: str = ""
    status: TestStatus = TestStatus.FAILED
    message: str = ""

    @property
    def identity(self) -> str:
        """Stable key used to match this case against the same case in a
        different run. Prefixing with ``file`` (when known) avoids
        collisions between identically-named tests in different files --
        bare ``name`` is the fallback for parsers that can't recover a
        file (e.g. Mocha's flat JSON, the regex fallback)."""
        return f"{self.file}::{self.name}" if self.file else self.name


@dataclass
class TestRunResult:
    """Everything observed from running a repo's test command once.

    ``used_fallback_parser`` matters as much as the results themselves:
    the regex fallback (see :func:`depfix.verify.parsers.parse_fallback`)
    can only report aggregate pass/fail *counts*, not stable per-test
    identities, so a diff against a fallback-parsed run cannot be trusted
    to say *which* test newly failed -- only *that* something changed. A
    :class:`~depfix.verify.verifier.Verifier` treats any run with this flag
    set as "degraded" and falls back to marking touched files SUSPECT
    rather than attributing individual regressions.
    """

    framework: TestFramework
    command: tuple[str, ...] = ()
    exit_code: int = 0
    duration_ms: float = 0.0
    cases: list[TestCase] = field(default_factory=list)
    parse_error: str = ""
    used_fallback_parser: bool = False
    timed_out: bool = False
    raw_output_tail: str = ""

    @property
    def crashed(self) -> bool:
        """True if the run produced nothing usable -- timed out, or exited
        non-zero with zero parsed cases and a parse error. A run with
        parsed cases (even failing ones) did not "crash", it just has
        failures -- that's the normal, comparable case."""
        if self.timed_out:
            return True
        return self.exit_code != 0 and not self.cases and bool(self.parse_error)

    @property
    def failed_cases(self) -> list[TestCase]:
        return [c for c in self.cases if c.status == TestStatus.FAILED]

    @property
    def failed_identities(self) -> frozenset[str]:
        return frozenset(c.identity for c in self.failed_cases)
