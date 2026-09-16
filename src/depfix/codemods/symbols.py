
"""Parsing the ``old_api`` / ``new_api`` fields of a breaking change.

These fields come from changelogs, release notes and model extraction, so
they arrive dirty: ``"openai.createChatCompletion()"``, ``"call
openai.createChatCompletion"``, ``"createChatCompletion -> chat.completions
.create"``. A codemod may only act on input it can parse into an
unambiguous dotted symbol; anything else must produce ``None`` so the
change falls through to the language model, which can cope with prose.

Refusing to guess here is what keeps the codemod layer trustworthy. A rule
that "does its best" with a malformed symbol is a rule that rewrites the
wrong identifier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["RenamePaths", "normalize_api", "rename_paths"]

_DOTTED = re.compile(r"^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$")
_TRAILING_CALL = re.compile(r"\s*\([^()]*\)\s*$")


def normalize_api(raw: str) -> str | None:
    """Return ``raw`` as a bare dotted symbol, or ``None`` if it isn't one.

    Strips a trailing argument list and surrounding punctuation, then
    requires the remainder to be a plain dotted identifier chain. Prose,
    signatures with nested parens, and anything containing whitespace are
    rejected rather than salvaged.
    """
    if not raw:
        return None
    candidate = raw.strip().strip("`\"'")
    candidate = _TRAILING_CALL.sub("", candidate)
    candidate = candidate.rstrip("().;,")
    candidate = candidate.lstrip(".")
    if not candidate or not _DOTTED.match(candidate):
        return None
    return candidate


@dataclass(frozen=True, slots=True)
class RenamePaths:
    """A namespace-preserving rename, split into the parts a codemod needs."""

    #: The shared leading segment, e.g. ``openai``. Not rewritten -- it names
    #: the receiver, which in real code is a local variable with any name.
    namespace: str
    #: Everything after the namespace, before: ``createChatCompletion``.
    old_path: str
    #: Everything after the namespace, after: ``chat.completions.create``.
    new_path: str


def rename_paths(old_api: str, new_api: str) -> RenamePaths | None:
    """Split a rename into namespace + old path + new path, or ``None``.

    Returns ``None`` unless both symbols parse, share a first segment, and
    each has at least two segments. The shared-namespace requirement is what
    makes the rewrite safe: it means we are renaming a *member* of a known
    object, so the receiver in the source can be matched structurally
    instead of by name. ``a.b`` -> ``c.d`` is a different, much harder
    change and is left to the model.
    """
    old = normalize_api(old_api)
    new = normalize_api(new_api)
    if old is None or new is None:
        return None
    old_parts = old.split(".")
    new_parts = new.split(".")
    if len(old_parts) < 2 or len(new_parts) < 2:
        return None
    if old_parts[0] != new_parts[0]:
        return None
    old_path = ".".join(old_parts[1:])
    new_path = ".".join(new_parts[1:])
    if old_path == new_path:
        return None
    return RenamePaths(namespace=old_parts[0], old_path=old_path, new_path=new_path)
