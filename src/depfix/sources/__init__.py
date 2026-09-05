"""Change sources — the detection layer.

One provider owns N feeds; each feed is a ``ChangeSource`` that turns "did
anything move" into ``ChangeEvent``. npm is one kind among several, not the
trunk.
"""

from depfix.sources.base import ChangeSource, UnsupportedSourceKind
from depfix.sources.factory import SourceDeps, build_source
from depfix.sources.github_release import GitHubReleaseSource
from depfix.sources.models import (
    ChangeEvent,
    FeedPoll,
    FeedStateSnapshot,
    Severity,
    SourceKind,
    SpecChange,
    SpecChangeKind,
    max_severity,
)
from depfix.sources.npm_dist_tag import NpmDistTagSource
from depfix.sources.openapi_diff import diff_specs
from depfix.sources.openapi_spec import OpenApiSpecSource

__all__ = [
    "ChangeEvent",
    "ChangeSource",
    "FeedPoll",
    "FeedStateSnapshot",
    "GitHubReleaseSource",
    "NpmDistTagSource",
    "OpenApiSpecSource",
    "Severity",
    "SourceDeps",
    "SourceKind",
    "SpecChange",
    "SpecChangeKind",
    "UnsupportedSourceKind",
    "build_source",
    "diff_specs",
    "max_severity",
]
