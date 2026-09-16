"""Selecting and running codemods.

The registry is ordered by specificity so a rule that understands one
library's whole migration beats a generic pattern that only understands the
rename. It is also the isolation boundary: a codemod that raises is
converted into a decline, because a bug in a deterministic rule must
degrade to "the model handles this file", never to a crashed run.
"""

from __future__ import annotations

import logging

from depfix.codemods.base import Codemod, CodemodResult
from depfix.codemods.javascript import (
    MethodRenameCodemod,
    OpenAIV4ConstructorCodemod,
    OpenAIV4MethodCodemod,
)
from depfix.core.models import BreakingChange

logger = logging.getLogger(__name__)

__all__ = ["CodemodRegistry"]


def _default_codemods() -> list[Codemod]:
    return [
        OpenAIV4ConstructorCodemod(),
        OpenAIV4MethodCodemod(),
        MethodRenameCodemod(),
    ]


class CodemodRegistry:
    """Holds the available rules and picks one per change."""

    def __init__(self, codemods: list[Codemod] | None = None) -> None:
        pool = list(_default_codemods() if codemods is None else codemods)
        self._codemods = sorted(pool, key=lambda c: c.specificity, reverse=True)

    @property
    def codemods(self) -> tuple[Codemod, ...]:
        return tuple(self._codemods)

    def select(self, change: BreakingChange) -> Codemod | None:
        """The most specific rule that claims ``change``, or ``None``."""
        for codemod in self._codemods:
            try:
                if codemod.claims(change):
                    return codemod
            except Exception:  # noqa: BLE001 - a broken claim() must not end the run
                logger.exception("codemod %s raised in claims(); ignoring it", codemod.id)
        return None

    def apply(
        self, relpath: str, source: str, change: BreakingChange
    ) -> CodemodResult | None:
        """Run the selected rule against one file.

        ``None`` means no rule claimed this change at all, which is the
        normal case for arbitrary libraries and simply means the language
        model does the work.
        """
        codemod = self.select(change)
        if codemod is None:
            return None
        try:
            result = codemod.apply(source, change)
        except Exception as exc:  # noqa: BLE001 - degrade to a decline, never crash
            logger.exception("codemod %s raised on %s", codemod.id, relpath)
            return CodemodResult.decline(
                codemod.id, f"the rule raised {type(exc).__name__} (this is a depfix bug)"
            )
        if result.changed and result.source is None:
            logger.error("codemod %s reported a change with no source", codemod.id)
            return CodemodResult.decline(
                codemod.id, "the rule reported a change but returned no source (depfix bug)"
            )
        return result

