"""Generic import-level call-site scanning for non-JS ecosystems.

The JS scanner (:mod:`depfix.scanners.callsites`) is binding-aware: it
follows what an import is *bound to* and propagates through re-exports.
This scanner is deliberately one notch simpler -- import statements, the
change's dotted symbols, and provider anchors, matched per line after
comment masking -- because that is the level at which ten ecosystems can
be supported honestly today. Confidence encodes exactly that honesty:
import hits carry the spec's ``import_confidence`` (HIGH only where the
pattern derives mechanically from the package name), symbol/anchor hits
are MEDIUM/LOW just as in the JS scanner.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from depfix.ecosystems.base import EcosystemSpec
from depfix.ecosystems.registry import ecosystem_for_registry
from depfix.scanners.models import (
    CallSite,
    CallSiteKind,
    MatchConfidence,
    RepoScanResult,
    ScanTarget,
    dedupe_call_sites,
)

logger = logging.getLogger(__name__)

_DEFAULT_MAX_FILE_BYTES = 1_000_000
_DEFAULT_MAX_FILES = 5_000
_CONTEXT_LINES = 3


def mask_comments(source: str, spec: EcosystemSpec) -> str:
    """Blank out comments (preserving line structure) so a commented-out
    import doesn't become a call site."""
    masked = source
    for open_token, close_token in spec.block_comments:
        pattern = re.compile(
            re.escape(open_token) + r".*?" + re.escape(close_token), re.DOTALL
        )
        masked = pattern.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), masked)
    if spec.line_comments:
        lines = masked.splitlines(keepends=True)
        for i, line in enumerate(lines):
            for prefix in spec.line_comments:
                index = line.find(prefix)
                # Crude string-awareness: a prefix inside quotes is more
                # likely a URL ("https://...") than a comment; skip those.
                if index >= 0 and line[:index].count('"') % 2 == 0 and line[:index].count("'") % 2 == 0:
                    lines[i] = line[:index] + re.sub(r"[^\n]", " ", line[index:])
                    break
        masked = "".join(lines)
    return masked


class GenericImportScanner:
    """Scans one ecosystem's source files for SDK imports, change symbols,
    and provider anchors. Produces the same :class:`RepoScanResult` shape
    as the JS scanner so storage/reporting need no second code path."""

    def __init__(
        self,
        spec: EcosystemSpec,
        *,
        max_file_bytes: int = _DEFAULT_MAX_FILE_BYTES,
        max_files: int = _DEFAULT_MAX_FILES,
    ) -> None:
        self._spec = spec
        self._max_file_bytes = max_file_bytes
        self._max_files = max_files

    def scan(self, root: Path, target: ScanTarget) -> RepoScanResult:
        spec = self._spec
        import_confidence = (
            MatchConfidence.HIGH if spec.import_confidence == "high" else MatchConfidence.MEDIUM
        )
        packages = packages_for_spec(target, spec)
        import_patterns: list[tuple[str, re.Pattern[str]]] = []
        if spec.import_regexes is not None:
            for package in packages:
                for pattern in spec.import_regexes(package):
                    import_patterns.append((package, pattern))

        symbol_patterns = [
            (symbol, re.compile(re.escape(symbol)))
            for symbol in target.symbols
        ]
        anchor_patterns = [
            (anchor, re.compile(re.escape(anchor)))
            for anchor in target.call_site_anchors
        ]

        result = RepoScanResult(repo_full_name="", commit_sha="")
        sites: list[CallSite] = []
        skip = spec.all_skip_dirs()

        files = []
        for path in sorted(root.rglob("*")):
            if len(files) >= self._max_files:
                result.errors.append(f"file cap reached ({self._max_files}); scan truncated")
                break
            if not path.is_file() or path.suffix not in spec.source_extensions:
                continue
            relative = path.relative_to(root)
            if any(part in skip for part in relative.parts[:-1]):
                continue
            files.append(path)

        for path in files:
            try:
                if path.stat().st_size > self._max_file_bytes:
                    continue
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                result.errors.append(f"{path}: {exc}")
                continue
            result.files_scanned += 1
            masked = mask_comments(source, spec)
            relpath = path.relative_to(root).as_posix()
            lines = masked.splitlines()
            raw_lines = source.splitlines()

            for line_number, line in enumerate(lines, start=1):
                for package, pattern in import_patterns:
                    match = pattern.search(line)
                    if match:
                        sites.append(_site(
                            relpath, line_number, match.start(), raw_lines,
                            kind=CallSiteKind.SDK_IMPORT, confidence=import_confidence,
                            symbol=package, provider_id=target.provider_id,
                            evidence=f"{self._spec.display_name} import of {package}",
                        ))
                for symbol, pattern in symbol_patterns:
                    match = pattern.search(line)
                    if match:
                        sites.append(_site(
                            relpath, line_number, match.start(), raw_lines,
                            kind=CallSiteKind.METHOD_CALL, confidence=MatchConfidence.MEDIUM,
                            symbol=symbol, provider_id=target.provider_id,
                            evidence=f"references migrated symbol {symbol}",
                        ))
                for anchor, pattern in anchor_patterns:
                    match = pattern.search(line)
                    if match:
                        sites.append(_site(
                            relpath, line_number, match.start(), raw_lines,
                            kind=CallSiteKind.ANCHOR, confidence=MatchConfidence.LOW,
                            symbol=anchor, provider_id=target.provider_id,
                            evidence=f"matched provider anchor {anchor!r}",
                        ))

        result.call_sites = dedupe_call_sites(sites)
        return result


def packages_for_spec(target: ScanTarget, spec: EcosystemSpec) -> list[str]:
    """The target's SDK packages that belong to this ecosystem.

    ``sdk_package_refs`` carries (name, registry) pairs when the caller
    built the target from a provider; a bare ``sdk_packages`` tuple (older
    callers, tests) is assumed to be all for this ecosystem.
    """
    refs = getattr(target, "sdk_package_refs", ())
    if not refs:
        return list(target.sdk_packages)
    out = []
    for name, registry in refs:
        ref_spec = ecosystem_for_registry(registry)
        if ref_spec is not None and ref_spec.id == spec.id:
            out.append(name)
    return out


def _site(
    relpath: str,
    line_number: int,
    column: int,
    raw_lines: list[str],
    *,
    kind: CallSiteKind,
    confidence: MatchConfidence,
    symbol: str,
    provider_id: str,
    evidence: str,
) -> CallSite:
    index = line_number - 1
    return CallSite(
        filepath=relpath,
        line_number=line_number,
        column=column,
        line_content=raw_lines[index] if index < len(raw_lines) else "",
        kind=kind,
        confidence=confidence,
        symbol=symbol,
        provider_id=provider_id,
        evidence=evidence,
        context_before=tuple(raw_lines[max(0, index - _CONTEXT_LINES):index]),
        context_after=tuple(raw_lines[index + 1:index + 1 + _CONTEXT_LINES]),
    )
