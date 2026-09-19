"""Codebase scanners — find API usages in source code.

Week 1's ``CodebaseScanner`` (single-file, regex-pattern grep) is unchanged.
Week 3 adds a second, repo-level scanner: manifest resolution
(:mod:`depfix.scanners.manifest`) plus binding-aware call-site matching
(:mod:`depfix.scanners.callsites`), orchestrated by
:mod:`depfix.scanners.repo` and persisted by :mod:`depfix.scanners.store`.
"""

from depfix.scanners.base import CodebaseScanner, build_pattern_for_api
from depfix.scanners.callsites import CallSiteScanner, mask_comments
from depfix.scanners.manifest import (
    DependencyMatch,
    ManifestScan,
    affects_version,
    find_manifests,
    range_allows_major,
    scan_manifests,
)
from depfix.scanners.matching import (
    ScanChangeAssessment,
    ScanMatchStatus,
    assess_scan_change,
    assess_scan_changes,
)
from depfix.scanners.models import (
    SCANNER_VERSION,
    CallSite,
    CallSiteKind,
    DeclaredDependency,
    MatchConfidence,
    RepoScanResult,
    ScanTarget,
    dedupe_call_sites,
)
from depfix.scanners.repo import (
    build_scan_target,
    build_scan_target_for_changes,
    scan_checkout,
    scan_path,
    scan_repo,
)
from depfix.scanners.store import latest_scan, record_scan, record_scan_assessments, upsert_repo

__all__ = [
    "SCANNER_VERSION",
    "CallSite",
    "CallSiteKind",
    "CallSiteScanner",
    "CodebaseScanner",
    "DeclaredDependency",
    "DependencyMatch",
    "ManifestScan",
    "MatchConfidence",
    "RepoScanResult",
    "ScanChangeAssessment",
    "ScanMatchStatus",
    "ScanTarget",
    "affects_version",
    "assess_scan_change",
    "assess_scan_changes",
    "build_pattern_for_api",
    "build_scan_target",
    "build_scan_target_for_changes",
    "dedupe_call_sites",
    "find_manifests",
    "latest_scan",
    "mask_comments",
    "range_allows_major",
    "record_scan",
    "record_scan_assessments",
    "scan_checkout",
    "scan_manifests",
    "scan_path",
    "scan_repo",
    "upsert_repo",
]
