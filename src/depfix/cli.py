"""Command-line entry point for depfix.

Exposed as the console script ``depfix`` after ``pip install -e .``.

Subcommands
-----------

* ``depfix run [--change-file ... | --from-event ID]`` — run the LLM fixer
  on a codebase for one breaking change (default).
* ``depfix watch [--providers-file ...]`` — poll every provider's change
  feeds and persist any new ``ChangeEvent``s.
* ``depfix classify`` — turn persisted, unclassified change events into
  ``BreakingChangeRow``s (deterministic spec-diff, or LLM release-notes).
* ``depfix eval [--no-llm]`` — score the classify/fixer pipeline against the
  YAML corpus in ``evals/corpus``.

When invoked without a subcommand (e.g. ``depfix --codebase X``), ``run`` is
assumed for backwards compatibility with the Day 1-2 CLI.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table

from depfix import DependencyFixAgent
from depfix.classify import (
    Classifier,
    GeminiCompleter,
    LLMCompleter,
    OllamaCompleter,
    classify_pending,
)
from depfix.config import get_settings
from depfix.core.models import AgentResult, BreakingChange, ChangeKind, ClassificationSource
from depfix.evals import (
    CorpusError,
    EvalCategory,
    EvalReport,
    EvalRunner,
    compare_reports,
    load_corpus_dir,
    load_report,
    save_report,
)
from depfix.fixers.gemini import FixGenerator
from depfix.fixers.ollama import OllamaFixGenerator
from depfix.providers.loader import ProviderConfigError, load_providers_file
from depfix.sources.factory import SourceDeps
from depfix.sources.models import Severity
from depfix.storage import BreakingChangeRow, init_schema, session_scope
from depfix.watcher.runner import Watcher, WatchOutcome

console = Console()
logger = logging.getLogger(__name__)

_RUN_COMMANDS = {"run", "watch", "classify", "eval"}
_TOP_LEVEL_FLAGS = {"-h", "--help"}


def _breaking_change_from_json(data: dict) -> BreakingChange:
    payload = dict(data)
    if "kind" in payload:
        payload["kind"] = ChangeKind(payload["kind"])
    if "source" in payload:
        payload["source"] = ClassificationSource(payload["source"])
    if "examples" in payload:
        payload["examples"] = [tuple(e) for e in payload["examples"]]
    return BreakingChange(**payload)


def _breaking_change_from_row(row: BreakingChangeRow) -> BreakingChange:
    return BreakingChange(
        package=row.package,
        old_version=row.old_version,
        new_version=row.new_version,
        old_api=row.old_api,
        new_api=row.new_api,
        description=row.description,
        migration_guide=row.migration_guide,
        kind=ChangeKind(row.kind),
        source=ClassificationSource(row.source),
        provider_id=row.provider_id,
        source_url=row.source_url,
        evidence=row.evidence,
        confidence=row.confidence,
        call_site_hints=list(row.call_site_hints),
    )


def _load_breaking_change(args: argparse.Namespace) -> BreakingChange:
    """Resolve the ``BreakingChange`` a `run` invocation should fix.

    There is no hardcoded demo fixture any more (see docs/decisions.md) — the
    caller must point at either a hand-written JSON file or a row that
    ``depfix classify`` already produced.
    """
    if args.change_file:
        data = json.loads(Path(args.change_file).read_text(encoding="utf-8"))
        return _breaking_change_from_json(data)
    if args.from_event is not None:
        with session_scope() as session:
            row = session.get(BreakingChangeRow, args.from_event)
            if row is None:
                raise LookupError(f"no breaking_change row with id={args.from_event}")
            return _breaking_change_from_row(row)
    raise ValueError(
        "no breaking change specified: pass --change-file <path>.json or "
        "--from-event <id> (run `depfix classify` first to populate rows)"
    )


def _build_completer(settings) -> LLMCompleter | None:
    if settings.llm_provider == "gemini":
        if not settings.google_api_key:
            return None
        return GeminiCompleter(api_key=settings.google_api_key, model=settings.gemini_model)
    return OllamaCompleter(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        timeout=settings.ollama_timeout,
    )


def _build_fixer(settings):
    if settings.llm_provider == "gemini":
        if not settings.google_api_key:
            return None
        return FixGenerator(api_key=settings.google_api_key, model=settings.gemini_model)
    return OllamaFixGenerator(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        timeout=settings.ollama_timeout,
    )


def _print_header() -> None:
    console.print(
        Panel.fit(
            "[bold blue]depfix[/bold blue]\n"
            "[dim]Automatically fix breaking dependency changes[/dim]",
            border_style="blue",
        )
    )


def _print_breaking_change(change: BreakingChange) -> None:
    table = Table(title="Breaking Change Details", show_header=False)
    table.add_column("Property", style="cyan")
    table.add_column("Value")
    table.add_row("Package", change.package)
    table.add_row("Version", f"{change.old_version} → {change.new_version}")
    table.add_row("Old API", f"[red]{change.old_api}[/red]")
    table.add_row("New API", f"[green]{change.new_api}[/green]")
    table.add_row("Description", change.description)
    console.print(table)
    console.print()


def _print_results(result: AgentResult) -> None:
    table = Table(title="Fix Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("Files Scanned", str(result.files_scanned))
    table.add_row("Files Affected", str(result.files_affected))
    table.add_row("Total Usages Fixed", str(result.total_usages_fixed))
    rate_color = "green" if result.success_rate == 1.0 else "yellow"
    table.add_row("Success Rate", f"[{rate_color}]{result.success_rate:.0%}[/{rate_color}]")
    table.add_row("Total Cost", f"${result.total_cost:.4f}")
    table.add_row("Total Tokens", str(result.total_tokens))
    table.add_row("Duration", f"{result.duration_ms}ms")
    console.print(table)
    console.print()

    if result.fixes:
        console.print("[bold]File Details:[/bold]")
        for fix in result.fixes:
            status = "✅" if fix.is_successful else "❌"
            color = (
                "green" if fix.confidence >= 0.9 else "yellow" if fix.confidence >= 0.7 else "red"
            )
            console.print(
                f"  {status} [cyan]{fix.filepath}[/cyan] - "
                f"{fix.usages_fixed} usages - "
                f"confidence: [{color}]{fix.confidence:.2f}[/{color}]"
            )
            if not fix.validation.is_valid:
                console.print(f"      [red]Validation error: {fix.validation.error_message}[/red]")
    console.print()


def _print_diffs(result: AgentResult, show_full: bool) -> None:
    console.print("[bold]Generated Diffs:[/bold]\n")
    for fix in result.fixes:
        if not fix.diff:
            continue
        console.print(f"[cyan]{fix.filepath}[/cyan]")
        if show_full:
            console.print(Syntax(fix.diff, "diff", theme="monokai", line_numbers=True))
        else:
            lines = fix.diff.split("\n")
            preview = "\n".join(lines[:30])
            console.print(Syntax(preview, "diff", theme="monokai"))
            if len(lines) > 30:
                console.print(f"[dim]... ({len(lines) - 30} more lines)[/dim]")
        console.print()


_STATUS_STYLE = {
    "changed": "[green]changed[/green]",
    "baseline": "[blue]baseline[/blue]",
    "unchanged": "[dim]unchanged[/dim]",
    "not_found": "[yellow]not found[/yellow]",
    "unsupported": "[yellow]unsupported[/yellow]",
    "failed": "[red]failed[/red]",
    "skipped": "[dim]skipped[/dim]",
}

_SEVERITY_STYLE = {
    Severity.BREAKING: "[red]BREAKING[/red]",
    Severity.POTENTIALLY_BREAKING: "[yellow]potentially breaking[/yellow]",
    Severity.ADDITIVE: "[green]additive[/green]",
    Severity.UNKNOWN: "[dim]unknown[/dim]",
}


def _print_watch_outcome(outcome: WatchOutcome, show_changes: bool) -> None:
    table = Table(title="Change Feeds")
    table.add_column("Provider", style="cyan")
    table.add_column("Feed")
    table.add_column("Status")
    table.add_column("Detail", style="dim")

    for report in outcome.reports:
        table.add_row(
            report.provider_id,
            report.feed_key if report.feed_key != "—" else f"({report.kind})",
            _STATUS_STYLE.get(report.status, report.status),
            report.detail,
        )
    console.print(table)
    console.print(
        f"[dim]feeds={outcome.feeds_polled}  events={len(outcome.events)}  "
        f"breaking={len(outcome.breaking_events)}  "
        f"duplicates={outcome.duplicates}  failed={len(outcome.failures)}[/dim]\n"
    )

    for event in outcome.events:
        console.print(
            Panel.fit(
                f"[bold]{event.title}[/bold]\n"
                f"{_SEVERITY_STYLE.get(event.severity, '?')}  ·  {event.summary}\n"
                f"[dim]{event.source_url or event.feed_key}[/dim]",
                border_style="red" if event.severity is Severity.BREAKING else "yellow",
            )
        )
        if not event.spec_changes:
            continue
        limit = len(event.spec_changes) if show_changes else 12
        for change in event.spec_changes[:limit]:
            console.print(f"  {change.one_line()}")
        remaining = len(event.spec_changes) - limit
        if remaining > 0:
            console.print(f"  [dim]... {remaining} more (use --show-changes)[/dim]")
        console.print()


def _cmd_watch(args: argparse.Namespace) -> int:
    settings = get_settings()
    providers_file = args.providers_file or settings.providers_file

    try:
        providers = load_providers_file(providers_file)
    except (FileNotFoundError, ProviderConfigError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        return 2

    if args.provider:
        wanted = set(args.provider)
        unknown = wanted - {p.id for p in providers}
        if unknown:
            console.print(f"[red]Unknown provider id(s): {', '.join(sorted(unknown))}[/red]")
            return 2
        providers = [p for p in providers if p.id in wanted]

    _print_header()
    feed_count = sum(len(p.feeds) for p in providers)
    console.print(
        f"[dim]Providers:[/dim] {len(providers)}  "
        f"[dim]Feeds:[/dim] {feed_count}  "
        f"[dim]Mode:[/dim] {'dry-run' if args.dry_run else 'persist'}\n"
    )

    try:
        with SourceDeps.from_settings() as deps:
            outcome = Watcher(deps=deps, dry_run=args.dry_run).run_once(providers)
    except Exception as e:
        console.print(f"[red]Watch failed: {e}[/red]")
        logger.exception("Watcher crashed")
        return 1

    _print_watch_outcome(outcome, show_changes=args.show_changes)

    # Exit non-zero only if every feed failed — cron reads non-zero as "page us".
    if outcome.failures and len(outcome.failures) == outcome.feeds_polled:
        return 1
    return 0


def _cmd_classify(args: argparse.Namespace) -> int:
    settings = get_settings()

    completer: LLMCompleter | None = None
    if not args.no_llm:
        completer = _build_completer(settings)
        if completer is None:
            console.print(
                "[yellow]No LLM configured (GOOGLE_API_KEY unset for provider=gemini); "
                "only events with spec_changes will classify. Pass --no-llm to silence "
                "this warning.[/yellow]"
            )

    classifier = Classifier(completer, min_confidence=settings.classify_min_confidence)

    _print_header()
    try:
        init_schema()
        with session_scope() as session:
            summary = classify_pending(session, classifier, limit=args.limit)
    except Exception as e:
        console.print(f"[red]Classify failed: {e}[/red]")
        logger.exception("Classifier crashed")
        return 1

    console.print(
        f"[dim]events processed:[/dim] {summary.events_processed}  "
        f"[dim]breaking changes created:[/dim] {summary.changes_created}  "
        f"[dim]errors:[/dim] {len(summary.errors)}\n"
    )
    for err in summary.errors:
        console.print(f"  [yellow]{err}[/yellow]")
    return 0


def _print_eval_report(report: EvalReport) -> None:
    table = Table(title="Eval Results")
    table.add_column("Category", style="cyan")
    table.add_column("Cases", justify="right")
    table.add_column("Passed", justify="right")
    table.add_column("Skipped", justify="right")
    table.add_column("Unverified", justify="right")

    for category in EvalCategory:
        cases = report.by_category(category)
        if not cases:
            continue
        scored = [c for c in cases if not c.skipped]
        passed = sum(1 for c in scored if c.passed)
        skipped = sum(1 for c in cases if c.skipped)
        unverified = sum(1 for c in cases if not c.verified)
        table.add_row(
            category.value,
            str(len(cases)),
            f"{passed}/{len(scored)}",
            str(skipped),
            str(unverified),
        )
    console.print(table)

    for case in report.failures:
        console.print(f"  [red]FAIL[/red] {case.case_id}: {case.detail}")

    rate_color = (
        "green" if report.pass_rate == 1.0 else "yellow" if report.pass_rate >= 0.8 else "red"
    )
    console.print(
        f"\n[dim]pass rate:[/dim] [{rate_color}]{report.pass_rate:.0%}[/{rate_color}]  "
        f"[dim]cost:[/dim] ${report.total_cost:.4f}\n"
    )


def _cmd_eval(args: argparse.Namespace) -> int:
    settings = get_settings()
    corpus_dir = Path(args.corpus_dir or settings.eval_corpus_dir)

    try:
        cases = load_corpus_dir(corpus_dir)
    except CorpusError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        return 2

    if args.category:
        wanted = set(args.category)
        cases = [c for c in cases if c.category.value in wanted]

    use_llm = not args.no_llm
    completer: LLMCompleter | None = None
    fixer = None
    if use_llm:
        completer = _build_completer(settings)
        fixer = _build_fixer(settings)
        if completer is None:
            console.print(
                "[yellow]No LLM configured (GOOGLE_API_KEY unset); release_notes and "
                "fix_generation cases will be skipped.[/yellow]"
            )
            use_llm = False

    _print_header()
    console.print(f"[dim]Corpus:[/dim] {corpus_dir}  [dim]Cases:[/dim] {len(cases)}\n")

    runner = EvalRunner(completer=completer, fixer=fixer)
    report = runner.run(cases, use_llm=use_llm)

    _print_eval_report(report)

    exit_code = 0
    if report.pass_rate < args.fail_under:
        console.print(
            f"[red]pass rate {report.pass_rate:.0%} is below "
            f"--fail-under {args.fail_under:.0%}[/red]"
        )
        exit_code = 1

    if args.compare:
        baseline = load_report(Path(args.compare))
        regressions = compare_reports(baseline, report)
        if regressions:
            console.print(f"[red]{len(regressions)} regression(s) vs baseline:[/red]")
            for r in regressions:
                console.print(f"  [red]{r.case_id}[/red] was passing, now failing")
            exit_code = 1
        else:
            console.print("[green]No regressions vs baseline.[/green]")

    if args.save:
        save_report(report, Path(args.save))
        console.print(f"[dim]saved report to {args.save}[/dim]")

    return exit_code


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="depfix",
        description="Fix breaking dependency changes with AI",
    )
    sub = p.add_subparsers(dest="command")

    # -- run --------------------------------------------------------------------
    run_p = sub.add_parser("run", help="Run the LLM fixer on a codebase")
    run_p.add_argument("--codebase", "-c", type=str, default=None, help="Path to codebase to fix")
    run_p.add_argument("--output", "-o", type=str, default=None, help="Where to write .patch diffs")
    run_p.add_argument("--show-diffs", action="store_true", help="Print full diffs")
    run_p.add_argument(
        "--change-file",
        type=str,
        default=None,
        help="Path to a JSON file with a single BreakingChange (see core.models.BreakingChange)",
    )
    run_p.add_argument(
        "--from-event",
        type=int,
        default=None,
        metavar="ID",
        help="breaking_change row id, as produced by `depfix classify`",
    )
    run_p.add_argument(
        "--api-key", type=str, default=None, help="Google API key (or set GOOGLE_API_KEY)"
    )
    run_p.add_argument("--model", type=str, default=None, help="Gemini model name (overrides env)")
    run_p.add_argument(
        "--provider",
        type=str,
        choices=["gemini", "ollama"],
        default=None,
        help="LLM backend (default: LLM_PROVIDER env, else gemini)",
    )
    run_p.add_argument(
        "--ollama-model",
        type=str,
        default=None,
        help="Ollama model tag when --provider=ollama (default: qwen2.5-coder:7b)",
    )
    run_p.add_argument("--log-level", type=str, default=None, help="DEBUG/INFO/WARNING/ERROR")

    # -- watch ------------------------------------------------------------------
    watch_p = sub.add_parser(
        "watch", help="Poll every provider's change feeds for breaking changes"
    )
    watch_p.add_argument(
        "--providers-file",
        type=str,
        default=None,
        help="Path to providers.yaml (default: PROVIDERS_FILE env)",
    )
    watch_p.add_argument(
        "--provider",
        action="append",
        default=None,
        metavar="ID",
        help="Only watch this provider id. Repeatable.",
    )
    watch_p.add_argument(
        "--once", action="store_true", help="Single pass and exit (the only mode)."
    )
    watch_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Poll but persist nothing. Every feed reports as a baseline.",
    )
    watch_p.add_argument(
        "--show-changes",
        action="store_true",
        help="Print the full structural change list for each event",
    )
    watch_p.add_argument("--log-level", type=str, default=None)

    # -- classify -----------------------------------------------------------------
    classify_p = sub.add_parser(
        "classify", help="Classify persisted change events into breaking changes"
    )
    classify_p.add_argument(
        "--limit", type=int, default=None, help="Classify at most this many events"
    )
    classify_p.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip the release-notes LLM path; only spec-diff events classify",
    )
    classify_p.add_argument("--log-level", type=str, default=None)

    # -- eval ---------------------------------------------------------------------
    eval_p = sub.add_parser("eval", help="Score the classify/fixer pipeline against the corpus")
    eval_p.add_argument(
        "--corpus-dir",
        type=str,
        default=None,
        help="Directory of *.yaml corpus files (default: EVAL_CORPUS_DIR env)",
    )
    eval_p.add_argument(
        "--category",
        action="append",
        choices=[c.value for c in EvalCategory],
        default=None,
        help="Only run this category. Repeatable.",
    )
    eval_p.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip cases that require an LLM (marks them skipped, not failed)",
    )
    eval_p.add_argument(
        "--fail-under",
        type=float,
        default=1.0,
        help="Exit non-zero if the scored pass rate falls below this (default: 1.0)",
    )
    eval_p.add_argument(
        "--save", type=str, default=None, metavar="PATH", help="Write the JSON report to PATH"
    )
    eval_p.add_argument(
        "--compare",
        type=str,
        default=None,
        metavar="PATH",
        help="Compare against a previously-saved report; exit non-zero on any regression",
    )
    eval_p.add_argument("--log-level", type=str, default=None)

    return p


def _cmd_run(args: argparse.Namespace) -> int:
    settings = get_settings()
    codebase = args.codebase or settings.codebase_path
    output = args.output or settings.output_dir
    api_key = args.api_key or settings.google_api_key
    model = args.model or settings.gemini_model
    provider = args.provider or settings.llm_provider
    ollama_model = args.ollama_model or settings.ollama_model

    if provider == "gemini" and not api_key:
        console.print("[red]Error: GOOGLE_API_KEY not set. Use --api-key or .env[/red]")
        return 2
    if not Path(codebase).exists():
        console.print(f"[red]Error: codebase not found: {codebase}[/red]")
        return 2

    try:
        breaking = _load_breaking_change(args)
    except (FileNotFoundError, ValueError, LookupError, json.JSONDecodeError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        return 2

    _print_header()
    _print_breaking_change(breaking)

    if provider == "ollama":
        console.print(f"[dim]Using provider: ollama  model: {ollama_model}[/dim]\n")
    else:
        console.print(f"[dim]Using provider: gemini  model: {model}[/dim]\n")

    agent = DependencyFixAgent(
        google_api_key=api_key,
        model=model,
        provider=provider,
        ollama_model=ollama_model,
        ollama_base_url=settings.ollama_base_url,
        ollama_timeout=settings.ollama_timeout,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning and fixing...", total=None)
        try:
            result = agent.fix_breaking_change(
                breaking_change=breaking,
                codebase_path=codebase,
                output_dir=output,
            )
        except Exception as e:
            progress.stop()
            console.print(f"[red]Error: {e}[/red]")
            logger.exception("Agent failed")
            return 1
        progress.update(task, completed=True)

    console.print()
    _print_results(result)
    if args.show_diffs:
        _print_diffs(result, show_full=True)
    if result.fixes:
        console.print(
            f"[green]✅ Diffs written to: {output}[/green]\n"
            f"[dim]Apply with: git apply {output}/*.patch[/dim]"
        )
    return 0 if result.success_rate == 1.0 else 1


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)

    # Backwards compatibility: `depfix --codebase X` (no subcommand) → `run`.
    # But keep `-h` / `--help` at the top level so users discover subcommands.
    needs_default = bool(raw) and raw[0] not in _RUN_COMMANDS and raw[0] not in _TOP_LEVEL_FLAGS
    if needs_default:
        raw = ["run", *raw]

    args = build_parser().parse_args(raw)

    logging.basicConfig(
        level=(getattr(args, "log_level", None) or get_settings().log_level).upper(),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if args.command == "watch":
        return _cmd_watch(args)
    if args.command == "classify":
        return _cmd_classify(args)
    if args.command == "eval":
        return _cmd_eval(args)
    return _cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
