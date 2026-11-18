"""Tests for depfix.obs.telemetry -- opt-in usage telemetry."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sentry_sdk.transport import Transport

from depfix.obs.telemetry import (
    flush,
    init_telemetry,
    is_enabled,
    payload,
    record_drift,
    record_fix,
    record_plan,
    record_pr,
    record_scan,
    reset,
    summary,
)


@pytest.fixture(autouse=True)
def _clean_telemetry():
    """Reset telemetry state before and after every test."""
    reset()
    yield
    reset()


# ------------------------------------------------------------------
# Disabled by default
# ------------------------------------------------------------------


class TestDisabledByDefault:
    def test_not_enabled_after_reset(self):
        assert is_enabled() is False

    def test_record_scan_noop_when_disabled(self):
        record_scan("stripe", "acme/web", 100, 20, 5)
        assert summary() == "(no telemetry recorded)"

    def test_record_drift_noop_when_disabled(self):
        record_drift("stripe", "stripe-python", "2.0", "4.0", "multi-major")
        assert summary() == "(no telemetry recorded)"

    def test_record_fix_noop_when_disabled(self):
        record_fix("stripe", 3, "codemod")
        assert summary() == "(no telemetry recorded)"

    def test_record_pr_noop_when_disabled(self):
        record_pr("stripe", "acme/web", 2)
        assert summary() == "(no telemetry recorded)"

    def test_record_plan_noop_when_disabled(self):
        record_plan("stripe", "acme/web", 4, 1)
        assert summary() == "(no telemetry recorded)"


# ------------------------------------------------------------------
# Counters when enabled
# ------------------------------------------------------------------


class TestCountersWhenEnabled:
    @pytest.fixture(autouse=True)
    def _enable(self):
        init_telemetry(enabled=True)

    def test_scan_increments(self):
        record_scan("stripe", "acme/web", 100, 20, 5)
        assert is_enabled() is True
        text = summary()
        assert "scans" in text
        assert "files_scanned" in text

    def test_multiple_scans_accumulate(self):
        record_scan("stripe", "acme/web", 100, 20, 5)
        record_scan("twilio", "acme/api", 50, 10, 3)
        text = summary()
        # scans should be 2
        assert "2" in text

    def test_drift_counter(self):
        record_drift("stripe", "stripe-python", "2.0", "4.0", "multi-major")
        record_drift("stripe", "stripe-node", "9.0", "12.0", "multi-major")
        text = summary()
        assert "drift_observations" in text

    def test_fix_counter_codemod(self):
        record_fix("stripe", 3, "codemod")
        text = summary()
        assert "fixes" in text
        assert "fixes_codemod" in text

    def test_fix_counter_llm(self):
        record_fix("stripe", 2, "llm")
        text = summary()
        assert "fixes_llm" in text

    def test_pr_counter(self):
        record_pr("stripe", "acme/web", 2)
        text = summary()
        assert "prs" in text

    def test_plan_counter(self):
        record_plan("stripe", "acme/web", 4, 1)
        text = summary()
        assert "plans" in text
        assert "edits_kept" in text
        assert "edits_reverted" in text


# ------------------------------------------------------------------
# Summary format
# ------------------------------------------------------------------


class TestSummary:
    def test_empty_summary(self):
        assert summary() == "(no telemetry recorded)"

    def test_summary_format(self):
        init_telemetry(enabled=True)
        record_scan("stripe", "acme/web", 50, 10, 3)
        record_fix("stripe", 2, "llm")
        text = summary()
        lines = text.strip().split("\n")
        # Each line should have a key and a number
        for line in lines:
            parts = line.split()
            assert len(parts) == 2, f"Unexpected line format: {line!r}"
            assert parts[1].isdigit(), f"Expected a count: {line!r}"

    def test_summary_sorted_keys(self):
        init_telemetry(enabled=True)
        record_scan("stripe", "acme/web", 50, 10, 3)
        record_drift("stripe", "stripe-python", "2.0", "4.0", "major")
        record_fix("stripe", 2, "llm")
        record_plan("stripe", "acme/web", 3, 0)
        record_pr("stripe", "acme/web", 1)
        text = summary()
        keys = [line.split()[0] for line in text.strip().split("\n")]
        counter_keys = [k for k in keys if not k.startswith("unique_")]
        assert counter_keys == sorted(counter_keys)
        assert keys[-2:] == ["unique_repos", "unique_providers"]


# ------------------------------------------------------------------
# init_telemetry env var
# ------------------------------------------------------------------


class TestInitFromEnv:
    @pytest.mark.parametrize("val", ["true", "1", "yes", "True", "YES"])
    def test_truthy_values(self, val: str):
        with patch.dict("os.environ", {"DEPFIX_TELEMETRY": val}):
            init_telemetry()
            assert is_enabled() is True

    @pytest.mark.parametrize("val", ["false", "0", "no", ""])
    def test_falsy_values(self, val: str):
        with patch.dict("os.environ", {"DEPFIX_TELEMETRY": val}):
            init_telemetry()
            assert is_enabled() is False

    def test_missing_env_var(self):
        with patch.dict("os.environ", {}, clear=True):
            init_telemetry()
            assert is_enabled() is False


# ------------------------------------------------------------------
# Config field
# ------------------------------------------------------------------


class TestConfigField:
    def test_telemetry_enabled_defaults_false(self):
        from depfix.config import Settings

        s = Settings()
        assert s.telemetry_enabled is False


# ------------------------------------------------------------------
# Safety: exceptions in telemetry never propagate
# ------------------------------------------------------------------


class TestSafety:
    def test_flush_never_raises_when_sentry_missing(self):
        init_telemetry(enabled=True, dsn="https://k@o0.ingest.sentry.io/0")
        record_scan("stripe", "acme/web", 50, 10, 3)
        with patch.dict("sys.modules", {"sentry_sdk": None}):
            assert flush("scan") is False


# ------------------------------------------------------------------
# Sending: one anonymous event per command
# ------------------------------------------------------------------

_DSN = "https://key@o0.ingest.sentry.io/0"


class _ListTransport(Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.events: list = []

    def capture_envelope(self, envelope):
        event = envelope.get_event()
        if event is not None:
            self.events.append(event)


class TestFlush:
    def _capture(self, command: str = "scan") -> list:
        transport = _ListTransport()
        assert flush(command, transport=transport) is True
        return transport.events

    def test_sends_one_event_with_counters(self):
        init_telemetry(enabled=True, dsn=_DSN)
        record_scan("openai", "acme/web", 100, 20, 5)
        record_drift("openai", "openai", "3.3.0", "4.0.0", "actionable")
        sent = self._capture()
        assert len(sent) == 1
        event = sent[0]
        assert event["message"] == "depfix.usage"
        usage = event["contexts"]["depfix_usage"]
        assert usage["command"] == "scan"
        assert usage["counters"]["scans"] == 1
        assert usage["counters"]["call_sites_found"] == 20
        assert usage["counters"]["drift_observations"] == 1
        assert usage["providers"] == ["openai"]
        assert event["tags"]["scans"] == "1"

    def test_repo_names_are_hashed(self):
        init_telemetry(enabled=True, dsn=_DSN)
        record_scan("openai", "acme/secret-repo", 1, 1, 1)
        record_scan("openai", "acme/secret-repo", 1, 1, 1)
        sent = self._capture()
        assert "acme/secret-repo" not in repr(sent[0])
        assert len(sent[0]["contexts"]["depfix_usage"]["repo_hashes"]) == 1

    def test_no_hostname_leaks(self):
        import socket

        init_telemetry(enabled=True, dsn=_DSN)
        record_pr("openai", "acme/web", 1)
        sent = self._capture("apply")
        assert sent[0].get("server_name") == "depfix"
        assert socket.gethostname() not in repr(sent[0])

    def test_noop_when_disabled(self):
        init_telemetry(enabled=False, dsn=_DSN)
        record_scan("openai", "acme/web", 1, 1, 1)
        assert flush("scan", transport=lambda e: None) is False

    def test_noop_without_dsn(self):
        with patch.dict("os.environ", {}, clear=True):
            init_telemetry(enabled=True)
        record_scan("openai", "acme/web", 1, 1, 1)
        assert flush("scan", transport=lambda e: None) is False

    def test_noop_when_nothing_recorded(self):
        init_telemetry(enabled=True, dsn=_DSN)
        assert flush("report", transport=lambda e: None) is False

    def test_dsn_from_env(self):
        with patch.dict("os.environ", {"DEPFIX_TELEMETRY_DSN": _DSN}):
            init_telemetry(enabled=True)
        record_scan("openai", "acme/web", 1, 1, 1)
        assert len(self._capture()) == 1

    def test_payload_unique_counts(self):
        init_telemetry(enabled=True, dsn=_DSN)
        record_scan("openai", "a/one", 1, 1, 1)
        record_scan("stripe", "a/two", 1, 1, 1)
        data = payload("scan")
        assert len(data["repo_hashes"]) == 2
        assert data["providers"] == ["openai", "stripe"]
