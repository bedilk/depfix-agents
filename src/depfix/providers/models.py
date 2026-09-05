"""Provider definitions — the unit of subscription.

``call_site_anchors`` is unused in Week 1. It is declared now because Week 3's
scanner needs it and putting it in the config format today costs nothing,
whereas changing the format later costs every provider entry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from depfix.sources.models import SourceKind


@dataclass(frozen=True)
class FeedSpec:
    kind: SourceKind
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SdkPackage:
    """An SDK that wraps this provider's HTTP API — the Week 3 grep anchor."""

    name: str
    ecosystem: str = "npm"


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    name: str
    feeds: tuple[FeedSpec, ...] = ()
    sdk_packages: tuple[SdkPackage, ...] = ()
    api_version_scheme: str | None = None  # "dated" | "semver" | None
    api_base_urls: tuple[str, ...] = ()  # raw-fetch detection, Week 3
    call_site_anchors: tuple[str, ...] = ()  # Week 3
    enabled: bool = True
