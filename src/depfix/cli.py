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
* ``depfix scan (--repo OWNER/NAME | --path DIR) --provider ID`` — find SDK
  call sites in a local checkout or a repo cloned via the GitHub App.
* ``depfix fix (--repo OWNER/NAME | --path DIR) --provider ID (--change-file
  ... | --from-event ID)`` — scan, generate + write fixes for every
  actionable call site, and (unless ``--no-verify``) confirm each one
  against the repo's own test suite.
* ``depfix repos`` — list repos visible to the configured GitHub App
  installation(s), useful before pointing ``scan``/``fix`` at one.

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
from depfix.apply import EditVerdict, FileEdit, WorkspaceEditor
from depfix.classify import (
    Classifier,
    GeminiCompleter,
    LLMCompleter,
    OllamaCompleter,
    classify_pending,
)
from depfix.clone import CloneError, CloneService
from depfix.config import get_settings
from depfix.core.models import AgentResult, BreakingChange, ChangeKind, ClassificationSource
from depfix.core.pipeline import FixPipeline, FixPipelineResult
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
from depfix.gh import GitHubAppAuth, GitHubAppError
from depfix.providers.loader import ProviderConfigError, load_providers_file
from depfix.scanners import (
    CallSiteScanner,
    MatchConfidence,
    RepoScanResult,
    build_scan_target,
    record_scan,
    scan_checkout,
    scan_path,
    scan_repo,
)
from depfix.sources.factory import SourceDeps
from depfix.sources.models import Severity
from depfix.storage import BreakingChangeRow, init_schema, record_fix_run, session_scope
from depfix.validators.javascript import FixValidator
from depfix.verify import Verifier
from depfix.watcher.runner import Watcher, WatchOutcome

console = Console()
logger = logging.getLogger(__name__)

_RUN_COMMANDS = {"run", "watch", "classify", "eval", "scan", "fix", "repos"}
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


def _load_optional_breaking_change(args: argparse.Namespace) -> BreakingChange | None:
    """Like ``_load_breaking_change``, but for a `scan` invocation where
    narrowing to one breaking change's symbols is optional -- a plain
    ``depfix scan --provider X`` with neither flag scans for every symbol
    the provider declares."""
    if not args.change_file and args.from_event is None:
        return None
    return _load_breaking_change(args)


def _build_gh_auth(settings) -> GitHubAppAuth | None:
    """Build a ``GitHubAppAuth`` from settings, or ``None`` if the App isn't
    configured -- callers turn that into an actionable CLI error rather than
    letting a blank app_id/private_key fail deep inside a JWT-signing call."""
    if not settings.github_app_id:
        return None
    private_key = settings.github_app_private_key
    if not private_key and settings.github_app_private_key_path:
        private_key = Path(settings.github_app_private_key_path).read_text(encoding="utf-8")
    if not private_key:
        return None
    return GitHubAppAuth(app_id=settings.github_app_id, private_key=private_key)


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


_CONFIDENCE_STYLE = {
    MatchConfidence.HIGH: "[green]high[/green]",
    MatchConfidence.MEDIUM: "[yellow]medium[/yellow]",
    MatchConfidence.LOW: "[dim]low[/dim]",
}


def _print_scan_result(result: RepoScanResult, *, show_low: bool) -> None:
    sites = result.call_sites if show_low else result.actionable_sites

    table = Table(title=f"Call Sites — {result.repo_full_name or '(local)'}")
    table.add_column("File", style="cyan")
    table.add_column("Line", justify="right")
    table.add_column("Kind")
    table.add_column("Confidence")
    table.add_column("Symbol")
    for site in sorted(sites, key=lambda s: (s.filepath, s.line_number)):
        table.add_row(
            site.filepath,
            str(site.line_number),
            site.kind.value,
            _CONFIDENCE_STYLE.get(site.confidence, site.confidence.value),
            site.symbol,
        )
    console.print(table)
    console.print(
        f"[dim]files scanned:[/dim] {result.files_scanned}  "
        f"[dim]call sites:[/dim] {len(result.call_sites)} "
        f"({len(result.actionable_sites)} actionable)  "
        f"[dim]commit:[/dim] {result.commit_sha or '?'}\n"
    )

    if result.manifest_matches:
        console.print("[bold]Manifest matches:[/bold]")
        for match in result.manifest_matches:
            console.print(f"  {match}")
        console.print()

    for err in result.errors:
        console.print(f"  [yellow]{err}[/yellow]")


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


def _cmd_scan(args: argparse.Namespace) -> int:
    settings = get_settings()

    if bool(args.repo) == bool(args.path):
        console.print("[red]Error: pass exactly one of --repo OWNER/NAME or --path DIR[/red]")
        return 2
    if args.repo and "/" not in args.repo:
        console.print("[red]Error: --repo must be OWNER/NAME[/red]")
        return 2

    providers_file = args.providers_file or settings.providers_file
    try:
        providers = load_providers_file(providers_file)
    except (FileNotFoundError, ProviderConfigError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        return 2

    provider = next((p for p in providers if p.id == args.provider), None)
    if provider is None:
        known = ", ".join(sorted(p.id for p in providers))
        console.print(f"[red]Error: unknown provider id {args.provider!r} (known: {known})[/red]")
        return 2

    try:
        change = _load_optional_breaking_change(args)
    except (FileNotFoundError, ValueError, LookupError, json.JSONDecodeError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        return 2

    target = build_scan_target(provider, change)
    scanner = CallSiteScanner(
        max_file_bytes=settings.scan_max_file_bytes, max_files=settings.scan_max_files
    )

    _print_header()

    owner = name = ""
    gh_auth: GitHubAppAuth | None = None
    try:
        if args.path:
            repo_full_name = str(Path(args.path).resolve())
            result = scan_path(args.path, target, repo_full_name=repo_full_name, scanner=scanner)
        else:
            owner, name = args.repo.split("/", 1)
            gh_auth = _build_gh_auth(settings)
            if gh_auth is None:
                console.print(
                    "[red]Error: GitHub App not configured. Set GITHUB_APP_ID and either "
                    "GITHUB_APP_PRIVATE_KEY or GITHUB_APP_PRIVATE_KEY_PATH.[/red]"
                )
                return 2
            clone_service = CloneService(
                clone_dir=settings.clone_dir or None,
                timeout=settings.clone_timeout,
                max_repo_mb=settings.clone_max_repo_mb,
            )
            repo_full_name = f"{owner}/{name}"
            result = scan_repo(
                owner,
                name,
                target,
                gh_auth=gh_auth,
                clone_service=clone_service,
                ref=args.ref,
                scanner=scanner,
            )
    except (CloneError, GitHubAppError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        return 1
    finally:
        if gh_auth is not None:
            gh_auth.close()

    _print_scan_result(result, show_low=args.show_low)

    if not args.no_save:
        init_schema()
        with session_scope() as session:
            record_scan(
                session,
                repo_full_name=repo_full_name,
                owner=owner or "local",
                name=name or Path(args.path).name,
                result=result,
                provider_id=provider.id,
            )
        console.print(f"[dim]saved scan to database ({repo_full_name})[/dim]\n")

    return 0


_VERDICT_STYLE = {
    EditVerdict.APPLIED: "green",
    EditVerdict.KEPT: "green",
    EditVerdict.SUSPECT: "yellow",
    EditVerdict.REVERTED: "red",
    EditVerdict.SKIPPED: "dim",
}


def _print_fix_result(result: FixPipelineResult) -> None:
    table = Table(title="Fix Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("Files Scanned", str(result.files_scanned))
    table.add_row("Files Affected", str(result.files_affected))
    table.add_row("Total Usages Fixed", str(result.total_usages_fixed))
    table.add_row("Total Cost", f"${result.total_cost:.4f}")
    table.add_row("Total Tokens", str(result.total_tokens))
    table.add_row("Duration", f"{result.duration_ms}ms")

    verification = result.verification
    if verification is not None:
        table.add_row(
            "Verified", "yes" if verification.ran else f"no ({verification.skipped_reason})"
        )
        if verification.ran and verification.baseline is not None:
            table.add_row("New Test Failures", str(verification.new_failure_count))
    console.print(table)
    console.print()

    if result.edits:
        console.print("[bold]File Details:[/bold]")
        for edit in result.edits:
            style = _VERDICT_STYLE[edit.verdict]
            console.print(
                f"  [{style}]{edit.verdict.value:>8}[/{style}] [cyan]{edit.relpath}[/cyan] - "
                f"{edit.usages_fixed} usages - confidence: {edit.confidence:.2f}"
            )
            if edit.error_message:
                console.print(f"      [red]{edit.error_message}[/red]")
    console.print()


def _print_fix_diffs(result: FixPipelineResult, show_full: bool) -> None:
    console.print("[bold]Generated Diffs:[/bold]\n")
    for edit in result.edits:
        if not edit.diff:
            continue
        console.print(f"[cyan]{edit.relpath}[/cyan]")
        if show_full:
            console.print(Syntax(edit.diff, "diff", theme="monokai", line_numbers=True))
        else:
            lines = edit.diff.split("\n")
            preview = "\n".join(lines[:30])
            console.print(Syntax(preview, "diff", theme="monokai"))
            if len(lines) > 30:
                console.print(f"[dim]... ({len(lines) - 30} more lines)[/dim]")
        console.print()


def _write_fix_diffs(edits: list[FileEdit], output_dir: str) -> None:
    """Write each on-disk edit's diff as ``output_dir/<flattened-relpath>.patch``
    -- same convention as :meth:`depfix.core.agent.DependencyFixAgent._write_diffs`,
    so ``git apply {output}/*.patch`` works identically for both commands."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    for edit in edits:
        if not edit.diff:
            continue
        safe_name = edit.relpath.replace("/", "_").replace("\\", "_")
        (output_path / f"{safe_name}.patch").write_text(edit.diff)


def _cmd_fix(args: argparse.Namespace) -> int:
    settings = get_settings()
    api_key = args.api_key or settings.google_api_key
    model = args.model or settings.gemini_model
    llm_provider = args.llm_provider or settings.llm_provider
    ollama_model = args.ollama_model or settings.ollama_model

    if llm_provider == "gemini" and not api_key:
        console.print("[red]Error: GOOGLE_API_KEY not set. Use --api-key or .env[/red]")
        return 2

    if bool(args.repo) == bool(args.path):
        console.print("[red]Error: pass exactly one of --repo OWNER/NAME or --path DIR[/red]")
        return 2
    if args.repo and "/" not in args.repo:
        console.print("[red]Error: --repo must be OWNER/NAME[/red]")
        return 2

    providers_file = args.providers_file or settings.providers_file
    try:
        providers = load_providers_file(providers_file)
    except (FileNotFoundError, ProviderConfigError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        return 2

    provider = next((p for p in providers if p.id == args.provider), None)
    if provider is None:
        known = ", ".join(sorted(p.id for p in providers))
        console.print(f"[red]Error: unknown provider id {args.provider!r} (known: {known})[/red]")
        return 2

    try:
        breaking = _load_breaking_change(args)
    except (FileNotFoundError, ValueError, LookupError, json.JSONDecodeError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        return 2

    if llm_provider == "gemini":
        fixer = FixGenerator(api_key=api_key, model=model)
    else:
        fixer = OllamaFixGenerator(
            model=ollama_model, base_url=settings.ollama_base_url, timeout=settings.ollama_timeout
        )

    target = build_scan_target(provider, breaking)
    scanner = CallSiteScanner(
        max_file_bytes=settings.scan_max_file_bytes, max_files=settings.scan_max_files
    )

    _print_header()
    _print_breaking_change(breaking)
    if llm_provider == "ollama":
        console.print(f"[dim]Using provider: ollama  model: {ollama_model}[/dim]\n")
    else:
        console.print(f"[dim]Using provider: gemini  model: {model}[/dim]\n")

    clone_service = CloneService(
        clone_dir=settings.clone_dir or None,
        timeout=settings.clone_timeout,
        max_repo_mb=settings.clone_max_repo_mb,
    )

    owner = name = ""
    repo_full_name = ""
    gh_auth: GitHubAppAuth | None = None
    checkout = None
    result: FixPipelineResult | None = None
    try:
        if args.path:
            owner, name = "local", Path(args.path).name
            repo_full_name = str(Path(args.path).resolve())
            checkout = clone_service.copy_local(args.path)
        else:
            owner, name = args.repo.split("/", 1)
            gh_auth = _build_gh_auth(settings)
            if gh_auth is None:
                console.print(
                    "[red]Error: GitHub App not configured. Set GITHUB_APP_ID and either "
                    "GITHUB_APP_PRIVATE_KEY or GITHUB_APP_PRIVATE_KEY_PATH.[/red]"
                )
                return 2
            installation = gh_auth.resolve_installation_for_repo(owner, name)
            token = gh_auth.installation_token(installation.id, repositories=(name,))
            resolved_ref = args.ref or gh_auth.default_ref(owner, name)
            checkout = clone_service.clone(owner, name, ref=resolved_ref, token=token.token)
            repo_full_name = f"{owner}/{name}"

        scan_result = scan_checkout(
            checkout, target, repo_full_name=repo_full_name, scanner=scanner
        )
        if not scan_result.actionable_sites:
            console.print("[yellow]No actionable call sites found for this change.[/yellow]")
            return 0

        editor = WorkspaceEditor(checkout)
        verifier: Verifier | None = None
        if not args.no_verify and settings.verify_enabled:
            verifier = Verifier(
                editor,
                install_timeout=settings.verify_install_timeout,
                test_timeout=settings.verify_test_timeout,
                ignore_scripts=settings.verify_ignore_scripts,
                max_output_bytes=settings.verify_max_output_bytes,
            )

        pipeline = FixPipeline(
            fixer,
            validator=FixValidator(use_ast_validation=settings.fix_validate_syntax),
            verifier=verifier,
        )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Fixing and verifying...", total=None)
            result = pipeline.run(scan_result, breaking, editor)
            progress.update(task, completed=True)
    except (CloneError, GitHubAppError) as exc:
        console.print(f"[red]Error: {exc}[/red]")
        return 1
    except Exception as e:  # noqa: BLE001 - surfaced to the user, then re-logged with a traceback
        console.print(f"[red]Fix pipeline failed: {e}[/red]")
        logger.exception("Fix pipeline crashed")
        return 1
    finally:
        if gh_auth is not None:
            gh_auth.close()
        if checkout is not None:
            clone_service.cleanup(checkout)

    assert result is not None
    console.print()
    _print_fix_result(result)
    if args.show_diffs:
        _print_fix_diffs(result, show_full=True)

    output = args.output or settings.output_dir
    if result.applied_edits:
        _write_fix_diffs(result.applied_edits, output)
        console.print(
            f"[green]Diffs written to: {output}[/green]\n"
            f"[dim]Apply with: git apply {output}/*.patch[/dim]"
        )

    if not args.no_save:
        init_schema()
        with session_scope() as session:
            record_fix_run(
                session,
                repo_full_name=repo_full_name,
                owner=owner,
                name=name,
                result=result,
            )
        console.print(f"[dim]saved fix run to database ({repo_full_name})[/dim]")

    if result.reverted_edits or result.suspect_edits:
        return 1
    return 0


def _cmd_repos(args: argparse.Namespace) -> int:
    settings = get_settings()
    gh_auth = _build_gh_auth(settings)
    if gh_auth is None:
        console.print(
            "[red]Error: GitHub App not configured. Set GITHUB_APP_ID and either "
            "GITHUB_APP_PRIVATE_KEY or GITHUB_APP_PRIVATE_KEY_PATH.[/red]"
        )
        return 2

    _print_header()
    try:
        installations = gh_auth.list_installations()
        if args.installation is not None:
            installations = [i for i in installations if i.id == args.installation]
            if not installations:
                console.print(f"[red]Error: no installation with id={args.installation}[/red]")
                return 2

        table = Table(title="GitHub App Installations & Repos")
        table.add_column("Installation", style="cyan")
        table.add_column("Account Type")
        table.add_column("Repo")
        table.add_column("Default Branch")
        table.add_column("Private", justify="center")

        for installation in installations:
            repos = gh_auth.list_repositories(installation.id)
            if not repos:
                table.add_row(
                    installation.account_login,
                    installation.account_type,
                    "[dim](none)[/dim]",
                    "",
                    "",
                )
                continue
            for repo in repos:
                table.add_row(
                    installation.account_login,
                    installation.account_type,
                    repo.full_name,
                    repo.default_branch,
                    "yes" if repo.private else "no",
                )
        console.print(table)
    except GitHubAppError as exc:
        console.print(f"[red]Error: {exc}[/red]")
        return 1
    finally:
        gh_auth.close()
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

    # -- scan -------------------------------------------------------------------
    scan_p = sub.add_parser("scan", help="Find SDK call sites in a local checkout or a cloned repo")
    scan_p.add_argument(
        "--repo",
        type=str,
        default=None,
        metavar="OWNER/NAME",
        help="Remote repo to clone via the GitHub App and scan",
    )
    scan_p.add_argument(
        "--path", type=str, default=None, help="Local directory to scan instead of cloning"
    )
    scan_p.add_argument(
        "--ref",
        type=str,
        default=None,
        help="Branch/tag/sha to clone (only with --repo; default: the repo's default branch)",
    )
    scan_p.add_argument(
        "--provider", type=str, required=True, help="Provider id from providers.yaml to scan for"
    )
    scan_p.add_argument(
        "--providers-file",
        type=str,
        default=None,
        help="Path to providers.yaml (default: PROVIDERS_FILE env)",
    )
    scan_p.add_argument(
        "--change-file",
        type=str,
        default=None,
        help="Narrow the scan to one BreakingChange's symbols (see `run --change-file`)",
    )
    scan_p.add_argument(
        "--from-event",
        type=int,
        default=None,
        metavar="ID",
        help="Narrow the scan to a breaking_change row's symbols",
    )
    scan_p.add_argument(
        "--no-save", action="store_true", help="Don't persist this scan to the database"
    )
    scan_p.add_argument(
        "--show-low",
        action="store_true",
        help="Also print LOW-confidence (report-only, never auto-fixed) call sites",
    )
    scan_p.add_argument("--log-level", type=str, default=None)

    # -- fix --------------------------------------------------------------------
    fix_p = sub.add_parser(
        "fix", help="Generate, apply, and verify fixes for one breaking change"
    )
    fix_p.add_argument(
        "--repo",
        type=str,
        default=None,
        metavar="OWNER/NAME",
        help="Remote repo to clone via the GitHub App and fix",
    )
    fix_p.add_argument(
        "--path",
        type=str,
        default=None,
        help="Local directory to fix instead of cloning. Never mutated in place -- "
        "fixes are written to a disposable copy; see --output for the diffs.",
    )
    fix_p.add_argument(
        "--ref",
        type=str,
        default=None,
        help="Branch/tag/sha to clone (only with --repo; default: the repo's default branch)",
    )
    fix_p.add_argument(
        "--provider", type=str, required=True, help="Provider id from providers.yaml to scan for"
    )
    fix_p.add_argument(
        "--providers-file",
        type=str,
        default=None,
        help="Path to providers.yaml (default: PROVIDERS_FILE env)",
    )
    fix_p.add_argument(
        "--change-file",
        type=str,
        default=None,
        help="Path to a JSON file with a single BreakingChange (see core.models.BreakingChange)",
    )
    fix_p.add_argument(
        "--from-event",
        type=int,
        default=None,
        metavar="ID",
        help="breaking_change row id, as produced by `depfix classify`",
    )
    fix_p.add_argument(
        "--output", "-o", type=str, default=None, help="Where to write .patch diffs"
    )
    fix_p.add_argument("--show-diffs", action="store_true", help="Print full diffs")
    fix_p.add_argument(
        "--api-key", type=str, default=None, help="Google API key (or set GOOGLE_API_KEY)"
    )
    fix_p.add_argument("--model", type=str, default=None, help="Gemini model name (overrides env)")
    fix_p.add_argument(
        "--llm-provider",
        type=str,
        choices=["gemini", "ollama"],
        default=None,
        help="LLM backend (default: LLM_PROVIDER env, else gemini)",
    )
    fix_p.add_argument(
        "--ollama-model",
        type=str,
        default=None,
        help="Ollama model tag when --llm-provider=ollama (default: qwen2.5-coder:7b)",
    )
    fix_p.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip running the repo's own test suite to confirm each edit",
    )
    fix_p.add_argument(
        "--no-save", action="store_true", help="Don't persist this fix run to the database"
    )
    fix_p.add_argument("--log-level", type=str, default=None)

    # -- repos --------------------------------------------------------------------
    repos_p = sub.add_parser(
        "repos", help="List repos visible to the configured GitHub App installation(s)"
    )
    repos_p.add_argument(
        "--installation",
        type=int,
        default=None,
        metavar="ID",
        help="Only list repos for this installation id",
    )
    repos_p.add_argument("--log-level", type=str, default=None)

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
    if args.command == "scan":
        return _cmd_scan(args)
    if args.command == "fix":
        return _cmd_fix(args)
    if args.command == "repos":
        return _cmd_repos(args)
    return _cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
