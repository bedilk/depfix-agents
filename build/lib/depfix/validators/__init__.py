"""Fix validators — verify generated patches before writing them out."""

from depfix.validators.javascript import FixValidator, create_unified_diff
from depfix.validators.python import PythonFixValidator


def validator_for_ecosystem(ecosystem_id: str, *, use_ast_validation: bool = True):
    """The syntax validator for a fix-supported ecosystem.

    ``typescript`` maps to the JS validator (detection folds TS into
    javascript, but explicit callers may still pass it). Any other id
    also gets the JS validator -- purely to preserve the historical
    default; ids outside ``ecosystems.fixable_ids()`` never reach fix
    generation at all (gated in ``core.fix_service``), so this fallback
    is never asked to judge non-JS code in practice.
    """
    if ecosystem_id == "python":
        return PythonFixValidator(use_ast_validation=use_ast_validation)
    return FixValidator(use_ast_validation=use_ast_validation)


__all__ = ["FixValidator", "PythonFixValidator", "create_unified_diff", "validator_for_ecosystem"]
