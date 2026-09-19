"""Tests for command-line parsing behaviour."""

from __future__ import annotations

import pytest

from depfix import cli
from depfix.cli import _cmd_pipeline, _scan_location, build_parser
from depfix.config import Settings
from depfix.core.models import BreakingChange, ChangeKind, ClassificationSource
from depfix.providers.loader import ProviderConfigError
from depfix.scanners.models import RepoScanResult


def test_log_format_is_accepted_after_watch_subcommand() -> None:
    args = build_parser().parse_args(["watch", "--once", "--log-format", "json"])

    assert args.command == "watch"
    assert args.once is True
    assert args.log_format == "json"


def test_log_format_is_accepted_before_watch_subcommand() -> None:
    args = build_parser().parse_args(["--log-format", "json", "watch", "--once"])

    assert args.command == "watch"
    assert args.log_format == "json"


def test_scan_accepts_legacy_local_path_package_and_old_api_arguments() -> None:
    args = build_parser().parse_args(
        [
            "scan",
            "--repo",
            "./path/to/checkout",
            "--package",
            "openai",
            "--old-api",
            "openai.Completion",
        ]
    )

    assert _scan_location(args) == ("./path/to/checkout", None)
    assert args.package == "openai"
    assert args.old_api == "openai.Completion"


def test_plan_and_apply_share_the_pipeline_inputs() -> None:
    for command in ("plan", "apply"):
        args = build_parser().parse_args(
            [
                command,
                "acme/widgets",
                "--change-file",
                "change.json",
                "--llm-provider",
                "ollama",
            ]
        )

        assert args.command == command
        assert args.repos == ["acme/widgets"]
        assert args.change_file == ["change.json"]
        assert args.llm_provider == "ollama"


@pytest.mark.parametrize("command", ["doctor", "fix", "pipeline"])
def test_removed_legacy_workflow_commands_are_rejected(command: str, capsys) -> None:
    """Plan/apply are the only public edit-and-PR workflow commands."""
    with pytest.raises(SystemExit) as exc_info:
        cli.main([command])

    assert exc_info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_init_accepts_setup_and_offline_diagnostic_options() -> None:
    args = build_parser().parse_args(
        ["init", "--providers-file", "providers.test.yaml", "--offline"]
    )

    assert args.command == "init"
    assert args.providers_file == "providers.test.yaml"
    assert args.offline is True
    assert not hasattr(args, "repos")
    assert not hasattr(args, "provider")


def test_pr_list_accepts_a_repository() -> None:
    args = build_parser().parse_args(["pr", "list", "--repo", "acme/widgets"])

    assert args.command == "pr"
    assert args.pr_command == "list"
    assert args.repo == "acme/widgets"


def test_explicit_pipeline_repo_bypasses_repo_config_file_gate(monkeypatch) -> None:
    """Naming a repo is an explicit opt-in, unlike a fleet-wide run."""
    settings = Settings(llm_provider="ollama")
    args = build_parser().parse_args(["plan", "acme/widgets", "--provider", "openai"])

    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(
        cli,
        "load_providers_file",
        lambda _path: (_ for _ in ()).throw(ProviderConfigError("stop after setup")),
    )

    assert _cmd_pipeline(args) == 2
    assert settings.pipeline_require_config_file is False


def test_scan_with_auto_detected_changes_targets_all_classified_old_symbols(
    monkeypatch, tmp_path
) -> None:
    """A provider scan joins saved upstream changes to repository usage."""
    providers_file = tmp_path / "providers.yaml"
    providers_file.write_text(
        """providers:
  - id: openai
    sdk_packages: [{name: openai, ecosystem: npm}]
    feeds:
      - kind: fixture_change
        id: test
        old_token: '3.0.0'
        new_token: '4.0.0'
"""
    )
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    change = BreakingChange(
        package="openai",
        old_version="3.0.0",
        new_version="4.0.0",
        old_api="openai.createChatCompletion",
        new_api="openai.chat.completions.create",
        description="migration",
        migration_guide="",
        kind=ChangeKind.METHOD_RENAMED,
        source=ClassificationSource.MANUAL,
    )
    captured = {}
    settings = Settings(providers_file=str(providers_file), llm_provider="ollama")
    args = build_parser().parse_args(
        ["scan", "--path", str(checkout), "--provider", "openai", "--no-save"]
    )

    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(cli, "ensure_changes_detected", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(cli, "all_changes_for_provider", lambda _provider: [change])
    monkeypatch.setattr(cli, "latest_change_for_provider", lambda _provider: (change, 1))
    monkeypatch.setattr(cli, "_print_header", lambda: None)
    monkeypatch.setattr(cli, "_print_scan_result", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli, "_cmd_eval", lambda _args: 0)

    def capture_scan(_path, target, **_kwargs):
        captured["symbols"] = target.symbols
        return RepoScanResult(repo_full_name="local", commit_sha="test")

    monkeypatch.setattr(cli, "scan_path", capture_scan)

    assert cli._cmd_scan(args) == 0
    assert captured["symbols"] == ("openai.createChatCompletion",)


def test_scan_evaluates_after_detecting_and_scanning(monkeypatch, tmp_path) -> None:
    """The optional regression corpus is the final scan workflow phase."""
    providers_file = tmp_path / "providers.yaml"
    providers_file.write_text(
        """providers:
  - id: openai
    sdk_packages: [{name: openai, ecosystem: npm}]
    feeds:
      - kind: fixture_change
        id: test
        old_token: '3.0.0'
        new_token: '4.0.0'
"""
    )
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    args = build_parser().parse_args(
        ["scan", "--path", str(checkout), "--provider", "openai", "--no-save"]
    )
    settings = Settings(providers_file=str(providers_file), llm_provider="ollama")
    phases: list[str] = []

    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    monkeypatch.setattr(
        cli,
        "ensure_changes_detected",
        lambda *_args, **_kwargs: phases.append("detect") or 0,
    )
    monkeypatch.setattr(cli, "all_changes_for_provider", lambda _provider: [])
    monkeypatch.setattr(cli, "latest_change_for_provider", lambda _provider: (None, None))
    monkeypatch.setattr(cli, "_print_header", lambda: None)
    monkeypatch.setattr(cli, "_print_scan_result", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        cli,
        "scan_path",
        lambda *_args, **_kwargs: phases.append("scan") or RepoScanResult(
            repo_full_name="local", commit_sha="test"
        ),
    )
    monkeypatch.setattr(cli, "_cmd_eval", lambda _args: phases.append("evaluate") or 0)

    assert cli._cmd_scan(args) == 0
    assert phases == ["detect", "scan", "evaluate"]
