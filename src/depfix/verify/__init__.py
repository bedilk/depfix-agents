"""Week 4 test-based verification of candidate fixes.

:class:`Verifier` runs a checkout's own test suite before and after a
batch of fixes is applied, comparing results by test identity to decide
whether each fix should be kept, reverted, or left SUSPECT (unconfirmed).
"""

from depfix.verify.attribution import AttributionResult, attribute_failures
from depfix.verify.confidence import ConfidenceTier
from depfix.verify.characterize import CharacterizationReport, Characterizer, Probe
from depfix.verify.manager import InstallResult, detect_package_manager, install_dependencies
from depfix.verify.models import TestCase, TestFramework, TestRunResult, TestStatus
from depfix.verify.runner import detect_framework, has_test_script, run_tests
from depfix.verify.typecheck import Diagnostic, TypecheckResult, has_typescript, new_diagnostics, run_typecheck
from depfix.verify.verifier import VerificationReport, Verifier

__all__ = [
    "ConfidenceTier",
    "CharacterizationReport",
    "Characterizer",
    "Probe",
    "Diagnostic",
    "TypecheckResult",
    "has_typescript",
    "new_diagnostics",
    "run_typecheck",
    "AttributionResult",
    "InstallResult",
    "TestCase",
    "TestFramework",
    "TestRunResult",
    "TestStatus",
    "VerificationReport",
    "Verifier",
    "attribute_failures",
    "detect_framework",
    "detect_package_manager",
    "has_test_script",
    "install_dependencies",
    "run_tests",
]
