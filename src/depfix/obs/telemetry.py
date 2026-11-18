"""Opt-in anonymous telemetry for depfix usage metrics.

Disabled by default. Enable with DEPFIX_TELEMETRY=true.

Counters accumulate in-process and are sent as ONE Sentry event per command
(``flush``) through a dedicated client, so they never mix with the user's own
Sentry error reporting. Repo names are sent only as truncated SHA-256 hashes;
no code, paths, hostnames, or tokens leave the machine.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections import defaultdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sentry_sdk.transport import Transport

logger = logging.getLogger(__name__)

# Sentry project that receives depfix usage events. Overridable with
# DEPFIX_TELEMETRY_DSN; telemetry stays silent when both are empty.
DEFAULT_TELEMETRY_DSN = ""

_enabled: bool = False
_dsn: str = ""
_counters: dict[str, int] = defaultdict(int)
_repos: set[str] = set()
_providers: set[str] = set()


def init_telemetry(enabled: bool | None = None, dsn: str | None = None) -> None:
    """Activate or deactivate telemetry for this process.

    When *enabled* is ``None`` the ``DEPFIX_TELEMETRY`` env var is read
    (``1``, ``true`` or ``yes`` enables it).
    """
    global _enabled, _dsn
    if enabled is None:
        enabled = os.environ.get("DEPFIX_TELEMETRY", "").lower() in {"1", "true", "yes"}
    _enabled = enabled
    _dsn = dsn or os.environ.get("DEPFIX_TELEMETRY_DSN", "") or DEFAULT_TELEMETRY_DSN
    if _enabled:
        logger.debug("depfix telemetry enabled (dsn configured: %s)", bool(_dsn))


def is_enabled() -> bool:
    return _enabled


def _repo_hash(repo_name: str) -> str:
    return hashlib.sha256(repo_name.encode()).hexdigest()[:16]


def _touch(provider_id: str, repo_name: str | None = None) -> None:
    if provider_id:
        _providers.add(provider_id)
    if repo_name:
        _repos.add(_repo_hash(repo_name))


# ------------------------------------------------------------------
# Recording helpers -- silent no-ops when telemetry is off.
# ------------------------------------------------------------------


def record_scan(
    provider_id: str,
    repo_name: str,
    files_scanned: int,
    call_sites_found: int,
    actionable_sites: int,
) -> None:
    if not _enabled:
        return
    _touch(provider_id, repo_name)
    _counters["scans"] += 1
    _counters["files_scanned"] += files_scanned
    _counters["call_sites_found"] += call_sites_found
    _counters["actionable_sites"] += actionable_sites


def record_drift(
    provider_id: str,
    package_name: str,
    repo_version: str,
    latest_version: str,
    gap_kind: str,
) -> None:
    if not _enabled:
        return
    _touch(provider_id)
    _counters["drift_observations"] += 1


def record_fix(provider_id: str, files_edited: int, strategy: str) -> None:
    """Record a fix application. *strategy* is ``"manifest"`` (version bump only) or ``"llm"``."""
    if not _enabled:
        return
    _touch(provider_id)
    _counters["fixes"] += 1
    _counters["files_edited"] += files_edited
    _counters[f"fixes_{strategy}"] += 1


def record_pr(provider_id: str, repo_name: str, changes_count: int) -> None:
    """Record a pull request being opened."""
    if not _enabled:
        return
    _touch(provider_id, repo_name)
    _counters["prs_opened"] += 1


def record_plan(provider_id: str, repo_name: str, edits_kept: int, edits_reverted: int) -> None:
    """Record a planned PR artifact (plan or apply)."""
    if not _enabled:
        return
    _touch(provider_id, repo_name)
    _counters["plans"] += 1
    _counters["edits_kept"] += edits_kept
    _counters["edits_reverted"] += edits_reverted


# ------------------------------------------------------------------
# Sending
# ------------------------------------------------------------------


def payload(command: str) -> dict[str, object]:
    """The anonymous usage payload for this process."""
    from depfix import __version__

    return {
        "command": command,
        "depfix_version": __version__,
        "counters": dict(_counters),
        "repo_hashes": sorted(_repos),
        "providers": sorted(_providers),
    }


def flush(command: str, *, transport: Transport | None = None) -> bool:
    """Send one usage event for this command. Returns True if an event was sent.

    Never raises: a telemetry failure must not change the command's outcome.
    """
    if not _enabled or not _dsn or not _counters:
        return False
    try:
        import sentry_sdk

        data = payload(command)
        client = sentry_sdk.Client(
            dsn=_dsn,
            transport=transport,
            default_integrations=False,
            auto_enabling_integrations=False,
            send_default_pii=False,
            server_name="depfix",
            release=f"depfix@{data['depfix_version']}",
        )
        event: Any = {
            "message": "depfix.usage",
            "level": "info",
            "tags": {"command": command, **{k: str(v) for k, v in _counters.items()}},
            "contexts": {"depfix_usage": data},
        }
        client.capture_event(event)
        client.flush(timeout=2.0)
        client.close(timeout=2.0)
        return True
    except Exception:
        logger.debug("telemetry: flush failed", exc_info=True)
        return False


def summary() -> str:
    """Formatted counters (for debugging / local inspection)."""
    if not _counters:
        return "(no telemetry recorded)"
    lines = [f"{key:<30} {_counters[key]}" for key in sorted(_counters)]
    lines.append(f"{'unique_repos':<30} {len(_repos)}")
    lines.append(f"{'unique_providers':<30} {len(_providers)}")
    return "\n".join(lines)


def reset() -> None:
    """Clear all state (for tests)."""
    global _enabled, _dsn
    _enabled = False
    _dsn = ""
    _counters.clear()
    _repos.clear()
    _providers.clear()
