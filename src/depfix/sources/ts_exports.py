"""TypeScript exported-symbol diff between two npm versions.

The claim this makes is narrow on purpose. It does **not** diff type
signatures — that needs the TypeScript compiler, a dependency depfix
deliberately doesn't carry (see docs/plan.md's tree-sitter gate). It extracts
the set of *exported names* from a package's ``.d.ts`` files and reports the
ones that vanished between the old and new version.

A removed export is a genuine breaking signal: every ``import { X }`` of it
breaks. Treat a hit as "this symbol is gone, go look," not as a completed
migration. Signature changes, renamed parameters, and widened return types
pass through undetected — the event body says so explicitly.

When an export disappears and a similarly-named one appears in the same
version, we emit an ``OPERATION_ID_CHANGED`` (rename) instead of a plain
removal. The heuristic uses case-insensitive suffix matching and
Levenshtein-like prefix overlap to pair candidates.
"""

from __future__ import annotations

import io
import logging
import re
import tarfile
from typing import Any, ClassVar

import httpx

from depfix.registry.client import NpmRegistryClient, RegistryError
from depfix.sources.base import ChangeSource
from depfix.sources.models import (
    ChangeEvent,
    FeedPoll,
    FeedStateSnapshot,
    Severity,
    SourceKind,
    SpecChange,
    SpecChangeKind,
)
from depfix.sources.semver import is_major_bump

logger = logging.getLogger(__name__)

_MAX_TARBALL_BYTES = 30_000_000

_RENAME_SIMILARITY_THRESHOLD = 0.45

_CAMEL_SPLIT_RE = re.compile(r"[A-Z][a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\b)|[a-z]+|[A-Z]+|\d+")


def _camel_words(name: str) -> list[str]:
    """Split camelCase/PascalCase into lowercase words."""
    return [m.lower() for m in _CAMEL_SPLIT_RE.findall(name)]


def _similarity(old: str, new: str) -> float:
    """Heuristic similarity using camelCase word overlap.

    Compares the sets of camelCase-split words (e.g. "startTransaction" →
    {"start", "transaction"}) and returns Jaccard-like overlap, weighted
    toward shared words at the start of the name.
    """
    if old == new:
        return 1.0
    if old.lower() == new.lower():
        return 0.95

    old_words = _camel_words(old)
    new_words = _camel_words(new)
    if not old_words or not new_words:
        return 0.0

    old_set = set(old_words)
    new_set = set(new_words)
    shared = old_set & new_set
    if not shared:
        return 0.0

    jaccard = len(shared) / len(old_set | new_set)

    prefix_bonus = 0.0
    if old_words[0] == new_words[0]:
        prefix_bonus = 0.15

    return min(jaccard + prefix_bonus, 1.0)


def pair_renames(
    removed: set[str], added: set[str]
) -> tuple[list[tuple[str, str]], set[str]]:
    """Match removed exports to added ones that look like renames.

    Returns (rename_pairs, unmatched_removed). Each pair is (old_name, new_name).
    Greedy best-match: highest similarity wins, no name is used twice.
    """
    if not removed or not added:
        return [], removed

    candidates: list[tuple[float, str, str]] = []
    for old_name in removed:
        for new_name in added:
            sim = _similarity(old_name, new_name)
            if sim >= _RENAME_SIMILARITY_THRESHOLD:
                candidates.append((sim, old_name, new_name))
    candidates.sort(reverse=True)

    paired: list[tuple[str, str]] = []
    used_old: set[str] = set()
    used_new: set[str] = set()
    for _sim, old_name, new_name in candidates:
        if old_name in used_old or new_name in used_new:
            continue
        paired.append((old_name, new_name))
        used_old.add(old_name)
        used_new.add(new_name)

    unmatched = removed - used_old
    return paired, unmatched

_EXPORT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"^\s*export\s+declare\s+"
        r"(?:function|class|const|let|var|enum|abstract\s+class)\s+"
        r"([A-Za-z_$][\w$]*)",
        re.MULTILINE,
    ),
    re.compile(
        r"^\s*export\s+"
        r"(?:interface|type|enum|class|function|const|abstract\s+class)\s+"
        r"([A-Za-z_$][\w$]*)",
        re.MULTILINE,
    ),
    re.compile(
        r"^\s*export\s+default\s+(?:function|class)\s+([A-Za-z_$][\w$]*)",
        re.MULTILINE,
    ),
)
_EXPORT_LIST_RE = re.compile(r"export\s*\{([^}]*)\}", re.DOTALL)


def _names_in_dts(text: str) -> set[str]:
    names: set[str] = set()
    for pattern in _EXPORT_PATTERNS:
        names.update(pattern.findall(text))
    for block in _EXPORT_LIST_RE.findall(text):
        for entry in block.split(","):
            entry = entry.strip()
            if not entry or entry == "default":
                continue
            name = entry.split(" as ")[-1].strip().removeprefix("type ").strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", name):
                names.add(name)
    return names


class TsExportsSource(ChangeSource):
    kind: ClassVar[SourceKind] = SourceKind.TS_EXPORTS_DIFF

    def __init__(
        self,
        provider_id: str,
        config: dict[str, Any],
        http: httpx.Client,
        npm: NpmRegistryClient,
    ) -> None:
        super().__init__(provider_id, config)
        self.package: str = self._require("package")
        self.compare_previous_major: bool = bool(config.get("compare_previous_major", True))
        self._http = http
        self._npm = npm

    @property
    def feed_key(self) -> str:
        return f"ts_exports:{self.package}"

    def poll(self, state: FeedStateSnapshot) -> FeedPoll:
        try:
            metadata = self._npm.get_package_metadata(self.package)
        except RegistryError as exc:
            return FeedPoll.failure(str(exc))

        version = metadata.dist_tags.get("latest")
        if not version:
            return FeedPoll.missing(f"{self.package} has no 'latest' dist-tag")
        if version == state.last_token:
            return FeedPoll.unchanged(token=version)

        old_token = state.last_token
        if old_token is None:
            # First sight: instead of a silent baseline, diff against the last
            # release of the previous major -- where removals actually live.
            old_token = (
                self._previous_major_release(metadata.versions, version)
                if self.compare_previous_major
                else None
            )
            if old_token is None:
                return FeedPoll.baseline(version)

        old_names = self._exports_for(old_token)
        new_names = self._exports_for(version)
        if old_names is None or new_names is None:
            return FeedPoll.baseline(version, path=state.last_payload_path)

        raw_removed = old_names - new_names
        added = new_names - old_names
        rename_pairs, unmatched_removed = pair_renames(raw_removed, added)

        changes: list[SpecChange] = []
        for old_name, new_name in rename_pairs:
            changes.append(
                SpecChange(
                    kind=SpecChangeKind.OPERATION_ID_CHANGED,
                    severity=Severity.BREAKING,
                    subject=f"{self.provider_id}.{old_name}",
                    pointer=f"{self.package}#{old_name}",
                    detail=f"exported symbol renamed: {old_name} → {new_name}",
                    before=old_name,
                    after=f"{self.provider_id}.{new_name}",
                )
            )
        for name in sorted(unmatched_removed):
            changes.append(
                SpecChange(
                    kind=SpecChangeKind.EXPORT_REMOVED,
                    severity=Severity.BREAKING,
                    subject=f"{self.provider_id}.{name}",
                    pointer=f"{self.package}#{name}",
                    detail="exported symbol removed between versions",
                    before=name,
                )
            )
        if not changes and state.last_token is None:
            return FeedPoll.baseline(version)

        n_removed = len(unmatched_removed)
        n_renamed = len(rename_pairs)
        severity = (
            Severity.BREAKING
            if changes
            else (Severity.BREAKING if is_major_bump(old_token, version) else Severity.UNKNOWN)
        )
        parts = []
        if n_renamed:
            parts.append(f"{n_renamed} renamed")
        if n_removed:
            parts.append(f"{n_removed} removed")
        summary = (
            f"exported symbols: {', '.join(parts)}"
            if parts
            else "no exported symbols removed (signature changes are NOT detected)"
        )
        event = ChangeEvent(
            provider_id=self.provider_id,
            feed_key=self.feed_key,
            source_kind=self.kind,
            source_url=f"https://www.npmjs.com/package/{self.package}/v/{version}",
            old_token=old_token,
            new_token=version,
            title=f"{self.package} exports {old_token} → {version}",
            summary=summary,
            body="\n".join(c.one_line() for c in changes[:60]),
            severity=severity,
            spec_changes=changes,
            raw={
                "package": self.package,
                "removed_exports": sorted(unmatched_removed),
                "renamed_exports": [[old, new] for old, new in rename_pairs],
            },
        )
        return FeedPoll(changed=True, new_token=version, events=[event])

    @staticmethod
    def _previous_major_release(versions: list[str], latest: str) -> str | None:
        """Highest stable release with a lower major than ``latest``."""
        from depfix.sources.semver import parse_semver

        current = parse_semver(latest)
        if current is None:
            return None
        candidates = [
            (parsed, v)
            for v in versions
            if "-" not in v and (parsed := parse_semver(v)) is not None and parsed[0] < current[0]
        ]
        return max(candidates)[1] if candidates else None

    def _exports_for(self, version: str) -> set[str] | None:
        tarball_url = self._tarball_url(version)
        if tarball_url is None:
            return None
        try:
            response = self._http.get(tarball_url)
            if response.status_code != 200 or len(response.content) > _MAX_TARBALL_BYTES:
                return None
            return self._names_in_tarball(response.content)
        except (httpx.HTTPError, tarfile.TarError, OSError) as exc:
            logger.debug("ts_exports fetch failed for %s@%s: %s", self.package, version, exc)
            return None

    def _tarball_url(self, version: str) -> str | None:
        scope_safe = self.package.replace("/", "%2f")
        base = self._npm.base_url
        short = self.package.rsplit("/", 1)[-1]
        return f"{base}/{scope_safe}/-/{short}-{version}.tgz"

    @staticmethod
    def _names_in_tarball(blob: bytes) -> set[str]:
        names: set[str] = set()
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
            for member in tar.getmembers():
                if not member.isfile() or not member.name.endswith(".d.ts"):
                    continue
                if member.size > 2_000_000:
                    continue
                handle = tar.extractfile(member)
                if handle is None:
                    continue
                text = handle.read().decode("utf-8", errors="replace")
                names |= _names_in_dts(text)
        return names
