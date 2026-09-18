"""Multi-ecosystem support -- see :mod:`depfix.ecosystems.base` for the
seam's design and the two support tiers."""

from depfix.ecosystems.base import COMMON_SKIP_DIRS, DependencyDeclaration, EcosystemSpec
from depfix.ecosystems.callsites import GenericImportScanner
from depfix.ecosystems.registry import (
    all_ids,
    detect,
    ecosystem_for_registry,
    fixable_ids,
    get,
)

__all__ = [
    "COMMON_SKIP_DIRS",
    "DependencyDeclaration",
    "EcosystemSpec",
    "GenericImportScanner",
    "all_ids",
    "detect",
    "ecosystem_for_registry",
    "fixable_ids",
    "get",
]
