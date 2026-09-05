"""npm dist-tag feed: polls the npm registry for a package's dist-tag version."""

from __future__ import annotations

from typing import Any, ClassVar

from depfix.registry.client import (
    NpmRegistryClient,
    PackageNotFoundError,
    RegistryUnavailableError,
)
from depfix.sources.base import ChangeSource
from depfix.sources.models import (
    ChangeEvent,
    FeedPoll,
    FeedStateSnapshot,
    Severity,
    SourceKind,
)
from depfix.sources.semver import is_major_bump


class NpmDistTagSource(ChangeSource):
    kind: ClassVar[SourceKind] = SourceKind.NPM_DIST_TAG

    def __init__(
        self,
        provider_id: str,
        config: dict[str, Any],
        client: NpmRegistryClient,
    ) -> None:
        super().__init__(provider_id, config)
        self.package: str = self._require("package")
        self.dist_tag: str = str(config.get("dist_tag") or "latest")
        self._client = client

    @property
    def feed_key(self) -> str:
        return f"npm:{self.package}:{self.dist_tag}"

    def poll(self, state: FeedStateSnapshot) -> FeedPoll:
        try:
            metadata = self._client.get_package_metadata(self.package)
        except PackageNotFoundError:
            return FeedPoll.missing(f"npm package not found: {self.package}")
        except RegistryUnavailableError as exc:
            return FeedPoll.failure(str(exc))

        version = metadata.dist_tags.get(self.dist_tag)
        if not version:
            return FeedPoll.missing(f"{self.package} has no '{self.dist_tag}' dist-tag")
        if version == state.last_token:
            return FeedPoll.unchanged(token=version)
        if state.last_token is None:
            return FeedPoll.baseline(version)

        severity = (
            Severity.BREAKING if is_major_bump(state.last_token, version) else Severity.UNKNOWN
        )
        event = ChangeEvent(
            provider_id=self.provider_id,
            feed_key=self.feed_key,
            source_kind=self.kind,
            source_url=f"https://www.npmjs.com/package/{self.package}/v/{version}",
            old_token=state.last_token,
            new_token=version,
            title=f"{self.package} {state.last_token} → {version}",
            summary=f"npm dist-tag '{self.dist_tag}' moved",
            body="",  # Week 2 attaches release notes here
            severity=severity,
            raw={"package": self.package, "dist_tag": self.dist_tag},
        )
        return FeedPoll(changed=True, new_token=version, events=[event])
