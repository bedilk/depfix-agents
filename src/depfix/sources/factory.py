"""Feed-kind → source-class wiring, and the dependency bundle sources need."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

from depfix.config import get_settings
from depfix.registry.client import NpmRegistryClient
from depfix.sources.base import ChangeSource, UnsupportedSourceKind
from depfix.sources.fixture_change import FixtureChangeSource
from depfix.sources.github_release import GitHubReleaseSource
from depfix.sources.http import build_http_client
from depfix.sources.models import SourceKind
from depfix.sources.npm_dist_tag import NpmDistTagSource
from depfix.sources.openapi_spec import OpenApiSpecSource


class FeedLike(Protocol):
    """Structural type for a feed declaration.

    ``providers.models.FeedSpec`` satisfies this without inheriting from it.
    Declared as a Protocol so that ``sources`` never imports ``providers``:
    the dependency runs providers → sources, one direction only. Importing
    upward created a circular import via ``sources/__init__.py``.
    """

    @property
    def kind(self) -> SourceKind: ...

    @property
    def config(self) -> dict[str, Any]: ...


@dataclass
class SourceDeps:
    """Everything a source might need. Built once per watch run."""

    http: httpx.Client
    npm: NpmRegistryClient
    spec_cache_dir: Path
    max_spec_bytes: int
    github_api_url: str

    @classmethod
    def from_settings(cls) -> SourceDeps:
        settings = get_settings()
        return cls(
            http=build_http_client(),
            npm=NpmRegistryClient(),
            spec_cache_dir=Path(settings.spec_cache_dir),
            max_spec_bytes=settings.max_spec_bytes,
            github_api_url=settings.github_api_url,
        )

    def close(self) -> None:
        self.http.close()
        self.npm.close()

    def __enter__(self) -> SourceDeps:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def build_source(provider_id: str, feed: FeedLike, deps: SourceDeps) -> ChangeSource:
    if feed.kind is SourceKind.NPM_DIST_TAG:
        return NpmDistTagSource(
            provider_id,
            feed.config,
            deps.npm,
            http=deps.http,
            github_api_url=deps.github_api_url,
        )
    if feed.kind is SourceKind.GITHUB_RELEASE:
        return GitHubReleaseSource(provider_id, feed.config, deps.http, deps.github_api_url)
    if feed.kind is SourceKind.OPENAPI_SPEC:
        return OpenApiSpecSource(
            provider_id,
            feed.config,
            deps.http,
            deps.spec_cache_dir,
            deps.max_spec_bytes,
        )
    if feed.kind is SourceKind.FIXTURE_CHANGE:
        return FixtureChangeSource(provider_id, feed.config)
    raise UnsupportedSourceKind(
        f"feed kind '{feed.kind.value}' is declared but not implemented (Week 2)"
    )
