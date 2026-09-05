"""Fix validators — verify generated patches before writing them out."""

from depfix.validators.javascript import FixValidator, create_unified_diff

__all__ = ["FixValidator", "create_unified_diff"]
