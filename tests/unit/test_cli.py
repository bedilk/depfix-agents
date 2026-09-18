"""Tests for command-line parsing behaviour."""

from __future__ import annotations

from depfix.cli import _scan_location, build_parser


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


def test_init_accepts_only_local_setup_options() -> None:
    args = build_parser().parse_args(["init", "--providers-file", "providers.test.yaml"])

    assert args.command == "init"
    assert args.providers_file == "providers.test.yaml"
    assert not hasattr(args, "repos")
    assert not hasattr(args, "provider")


def test_pr_list_accepts_a_repository() -> None:
    args = build_parser().parse_args(["pr", "list", "--repo", "acme/widgets"])

    assert args.command == "pr"
    assert args.pr_command == "list"
    assert args.repo == "acme/widgets"
