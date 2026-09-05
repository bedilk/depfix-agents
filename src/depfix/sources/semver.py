"""Minimal semver handling. We only ever need "did the major move".

Deliberately not a dependency — full semver range resolution is a Week 3
concern (matching a repo's declared range), not a detection concern.
"""

from __future__ import annotations

import re

_SEMVER_RE = re.compile(r"^[vV]?(?P<major>\d+)\.(?P<minor>\d+)(?:\.(?P<patch>\d+))?(?:[-+].*)?$")


def parse_semver(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    m = _SEMVER_RE.match(value.strip())
    if not m:
        return None
    return (
        int(m.group("major")),
        int(m.group("minor")),
        int(m.group("patch") or 0),
    )


def is_major_bump(old: str | None, new: str | None) -> bool:
    """True only when both parse and the major component increased."""
    o, n = parse_semver(old), parse_semver(new)
    if o is None or n is None:
        return False
    return n[0] > o[0]
