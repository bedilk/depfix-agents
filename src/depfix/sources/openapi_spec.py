"""OpenAPI document feed.

State is the sha256 of the raw bytes, not an ETag — providers serving specs
off raw.githubusercontent don't send useful validators, and a content hash is
correct regardless.

The previous document is cached on disk (``SPEC_CACHE_DIR``) rather than in
Postgres: Stripe's spec3.json is ~6 MB and we need the *whole* prior document
to diff, so a blob column would be both large and useless for querying.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, ClassVar

import httpx
import yaml

from depfix.sources.base import ChangeSource
from depfix.sources.models import (
    ChangeEvent,
    FeedPoll,
    FeedStateSnapshot,
    Severity,
    SourceKind,
    max_severity,
)
from depfix.sources.openapi_diff import diff_specs

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(value: str) -> str:
    return _SLUG_RE.sub("-", value).strip("-")[:120] or "feed"


def _dig(doc: dict[str, Any], *keys: str) -> Any:
    cursor: Any = doc
    for key in keys:
        if not isinstance(cursor, dict) or key not in cursor:
            return None
        cursor = cursor[key]
    return cursor


class OpenApiSpecSource(ChangeSource):
    kind: ClassVar[SourceKind] = SourceKind.OPENAPI_SPEC

    def __init__(
        self,
        provider_id: str,
        config: dict[str, Any],
        http: httpx.Client,
        cache_dir: Path,
        max_bytes: int,
    ) -> None:
        super().__init__(provider_id, config)
        self.url: str = self._require("url")
        self._http = http
        self._cache_dir = cache_dir
        self._max_bytes = max_bytes

    @property
    def feed_key(self) -> str:
        return f"openapi:{self.url}"

    def poll(self, state: FeedStateSnapshot) -> FeedPoll:
        try:
            response = self._http.get(self.url)
        except httpx.HTTPError as exc:
            return FeedPoll.failure(f"fetch failed: {exc}")

        if response.status_code == 404:
            return FeedPoll.missing(f"spec URL 404: {self.url}")
        if response.status_code >= 400:
            return FeedPoll.failure(f"HTTP {response.status_code} for {self.url}")

        raw = response.content
        if len(raw) > self._max_bytes:
            return FeedPoll.failure(
                f"spec is {len(raw)} bytes, exceeds MAX_SPEC_BYTES={self._max_bytes}"
            )

        sha = hashlib.sha256(raw).hexdigest()
        if sha == state.last_payload_sha256:
            return FeedPoll.unchanged(token=state.last_token, sha=sha, path=state.last_payload_path)

        try:
            document = self._parse(raw)
        except ValueError as exc:
            return FeedPoll.failure(str(exc))

        version = str(_dig(document, "info", "version") or f"sha-{sha[:12]}")
        cache_path = self._write_cache(sha, document)

        previous = self._load_cache(state.last_payload_path)
        if previous is None:
            logger.info("openapi baseline for %s (%s @ %s)", self.provider_id, self.url, version)
            return FeedPoll.baseline(version, sha=sha, path=str(cache_path))

        changes = diff_specs(previous, document)
        severity = max_severity([c.severity for c in changes])
        breaking = [c for c in changes if c.severity is Severity.BREAKING]

        title = f"{self.provider_id} OpenAPI {state.last_token} → {version}"
        summary = (
            f"{len(changes)} structural change(s), {len(breaking)} breaking"
            if changes
            else "spec bytes changed but no structural delta detected"
        )
        body = "\n".join(c.one_line() for c in changes[:60])

        event = ChangeEvent(
            provider_id=self.provider_id,
            feed_key=self.feed_key,
            source_kind=self.kind,
            source_url=self.url,
            old_token=state.last_token,
            new_token=version,
            title=title,
            summary=summary,
            body=body,
            severity=severity,
            spec_changes=changes,
            raw={"sha256": sha, "change_count": len(changes)},
        )
        return FeedPoll(
            changed=True,
            new_token=version,
            payload_sha256=sha,
            payload_path=str(cache_path),
            events=[event],
        )

    # -- helpers --------------------------------------------------------------

    def _parse(self, raw: bytes) -> dict[str, Any]:
        text = raw.decode("utf-8", errors="replace")
        try:
            document = json.loads(text)
        except json.JSONDecodeError:
            try:
                document = yaml.safe_load(text)
            except yaml.YAMLError as exc:
                raise ValueError(f"spec is neither JSON nor YAML: {exc}") from exc
        if not isinstance(document, dict):
            raise ValueError("spec root is not a mapping")
        return document

    def _feed_dir(self) -> Path:
        return self._cache_dir / _slug(self.provider_id) / _slug(self.feed_key)

    def _write_cache(self, sha: str, document: dict[str, Any]) -> Path:
        directory = self._feed_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{sha}.json"
        # Normalise to JSON on write so reload never re-parses YAML. YAML
        # scalars that look like dates parse to `datetime.date`/`datetime`,
        # which json.dumps rejects — stringify anything JSON can't encode
        # natively (only affects leaf values like `example:` blocks, never
        # the structural shape the differ inspects).
        path.write_text(json.dumps(document, separators=(",", ":"), default=str), encoding="utf-8")
        for stale in directory.glob("*.json"):
            if stale.name != path.name:
                stale.unlink(missing_ok=True)
        return path

    def _load_cache(self, path: str | None) -> dict[str, Any] | None:
        if not path:
            return None
        candidate = Path(path)
        if not candidate.exists():
            logger.warning("cached spec missing at %s — treating as baseline", path)
            return None
        try:
            loaded = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("cached spec unreadable (%s) — treating as baseline", exc)
            return None
        return loaded if isinstance(loaded, dict) else None
