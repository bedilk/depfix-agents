"""Scrub credential-shaped text out of anything that is about to reach a
language model.

Two rules keep this from being a liability of its own:

**Never remove code.** A redaction that deletes a line, or that eats an
``apiVersion: "2023-10-16"`` literal, breaks the very migration it was
protecting. Every pattern here replaces only the *value* and preserves the
surrounding syntax, so a redacted file still parses and the model can still
see the shape of the call it has to rewrite.

**Shape, not cleverness.** We match well-known credential prefixes
(``sk-``, ``ghp_``, ``AKIA``...) and quoted values assigned to
secret-sounding identifiers. We deliberately do *not* run a general entropy
detector: it flags hashes, minified code and base64 fixtures, and a fixer
that keeps mangling legitimate constants is a fixer people turn off.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PLACEHOLDER = "<REDACTED>"

#: Credential formats with a distinctive, publicly documented prefix. These
#: are matched anywhere in the text -- a leaked key is a leaked key whether
#: it sits in a string literal, a comment, or a committed .env fixture.
_TOKEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),  # OpenAI
    re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}"),  # Stripe secret
    re.compile(r"\brk_(?:live|test)_[A-Za-z0-9]{16,}"),  # Stripe restricted
    re.compile(r"\bwhsec_[A-Za-z0-9]{16,}"),  # Stripe webhook
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),  # GitHub
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),  # Slack
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # AWS access key id
    re.compile(r"\bASIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"),  # Google API key
    re.compile(r"\bey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWT
    re.compile(
        r"-----BEGIN[^-\n]{0,40}PRIVATE KEY-----.*?-----END[^-\n]{0,40}PRIVATE KEY-----",
        re.DOTALL,
    ),
)

#: Identifier fragments that mean "this value is a credential". Deliberately
#: excludes bare ``api`` (so ``apiVersion``/``apiBase`` survive) and bare
#: ``key`` (so ``keyBy``/``objectKey`` survive).
_SECRET_NAME = (  # nosec B105
    r"(?:api[_-]?key|apikey|secret|token|password|passwd|credential|"
    r"private[_-]?key|access[_-]?key|client[_-]?secret|auth[_-]?token|authorization)"
)

#: ``apiKey: "sk-..."`` / ``apiKey = 'x'`` -- keeps the quotes and the key.
_ASSIGNED_LITERAL = re.compile(
    rf"""(?i)(?P<lead>\b\w*{_SECRET_NAME}\w*\b\s*[:=]\s*)(?P<q>['"`])(?P<value>[^'"`\n]{{6,}})(?P=q)"""
)

#: ``OPENAI_API_KEY=sk-...`` in a committed .env-shaped file.
_ENV_LINE = re.compile(
    rf"(?im)^(?P<lead>\s*(?:export\s+)?\w*{_SECRET_NAME}\w*\s*=\s*)(?P<value>[^\s#\n]{{6,}})\s*$"
)

#: ``Authorization: Bearer <token>`` in a header literal or a raw request.
_BEARER = re.compile(r"(?i)(?P<lead>\bBearer\s+)(?P<value>[A-Za-z0-9._~+/=-]{12,})")

#: Values that are obviously placeholders already -- redacting them adds
#: noise and hides useful context from the model.
_SAFE_VALUES = frozenset(
    {
        PLACEHOLDER.lower(),
        "changeme",
        "your-api-key",
        "your_api_key",
        "xxx",
        "todo",
        "undefined",
        "null",
        "none",
        "",
    }
)


@dataclass(frozen=True)
class RedactionResult:
    text: str
    count: int

    @property
    def redacted(self) -> bool:
        return self.count > 0


def _is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in _SAFE_VALUES:
        return True
    # `process.env.X`, `${SECRET}`, `config.get("x")` -- indirections, not secrets.
    return lowered.startswith(("process.env", "${", "os.environ", "env.", "config."))


def redact_secrets(text: str) -> RedactionResult:
    """Return ``text`` with credential values replaced by ``<REDACTED>``."""
    if not text:
        return RedactionResult(text, 0)

    count = 0
    out = text

    for pattern in _TOKEN_PATTERNS:
        out, hits = pattern.subn(PLACEHOLDER, out)
        count += hits

    def _replace_value(match: re.Match[str]) -> str:
        nonlocal count
        if _is_placeholder(match.group("value")):
            return match.group(0)
        count += 1
        quote = match.groupdict().get("q", "")
        return f"{match.group('lead')}{quote}{PLACEHOLDER}{quote}"

    out = _ASSIGNED_LITERAL.sub(_replace_value, out)
    out = _ENV_LINE.sub(_replace_value, out)
    out = _BEARER.sub(_replace_value, out)
    return RedactionResult(out, count)


def redact_for_prompt(text: str, *, enabled: bool = True) -> str:
    """Convenience wrapper for prompt builders: returns the scrubbed text."""
    return redact_secrets(text).text if enabled else text
