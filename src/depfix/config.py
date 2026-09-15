"""Application configuration via Pydantic Settings.

All runtime knobs are read from environment variables (loaded from `.env`
when present). CLI flags in :mod:`depfix.cli` override these.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_PACKAGE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Runtime settings for depfix."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",  # variables are read verbatim (e.g. GOOGLE_API_KEY)
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM ------------------------------------------------------------------
    llm_provider: Literal["gemini", "ollama"] = Field(
        default="gemini", description="Which LLM backend to use for `depfix run`"
    )
    google_api_key: str = Field(default="", description="Google Generative AI API key")
    gemini_model: str = Field(default="gemini-2.5-flash", description="Gemini model id")
    llm_max_retries: int = Field(default=3, ge=1, le=10)
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    fix_strategy: Literal["single_shot", "agent"] = Field(
        default="single_shot",
        description="Fix-generation strategy. The tool-assisted agent is opt-in.",
    )
    fix_agent_max_steps: int = Field(
        default=6,
        ge=1,
        le=10,
        description="Maximum read-only tool rounds for one agent-generated file edit.",
    )

    # --- Ollama (local LLM) ---------------------------------------------------
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="qwen2.5-coder:7b")
    ollama_timeout: float = Field(default=120.0, ge=1.0, le=600.0)

    # --- Scanner defaults -----------------------------------------------------
    codebase_path: str = Field(default="./tests/fixtures/openai_v3_project")
    output_dir: str = Field(default="./output/fixes")
    context_lines: int = Field(default=5, ge=0, le=50)

    # --- Infra (Day 3+; present now for docker-compose parity) ----------------
    database_url: str = Field(default="postgresql+psycopg://depfix:depfix@localhost:5432/depfix")
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- npm registry (used by sources.npm_dist_tag feeds) --------------------
    npm_registry_url: str = Field(default="https://registry.npmjs.org")
    npm_request_timeout: float = Field(default=10.0, ge=1.0, le=60.0)

    # --- change sources (Week 1) ----------------------------------------------
    providers_file: str = Field(
        default="providers.yaml", description="YAML list of providers and their feeds"
    )
    http_timeout: float = Field(default=20.0, ge=1.0, le=300.0)
    github_token: str = Field(
        default="",
        description="GitHub PAT. Unauthenticated is 60 req/hr, which two feeds "
        "exhaust in a day of cron ticks; authenticated is 5000.",
    )
    github_api_url: str = Field(default="https://api.github.com")
    spec_cache_dir: str = Field(
        default="./.depfix-cache/specs",
        description="Where previous OpenAPI documents are cached for diffing.",
    )
    max_spec_bytes: int = Field(
        default=32 * 1024 * 1024, ge=1024, description="Reject specs larger than this."
    )

    # --- classification (Week 2) -----------------------------------------------
    classify_min_confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="LLM-derived changes below this confidence are dropped by NotesClassifier.",
    )

    # --- eval harness (Week 2) --------------------------------------------------
    eval_corpus_dir: str = Field(
        default=str(_PACKAGE_DIR / "evals" / "corpus"),
        description="Directory of eval corpus YAML files.",
    )
    eval_results_dir: str = Field(
        default="./.depfix-cache/eval-results",
        description="Where `depfix eval --save` writes JSON reports.",
    )

    # --- GitHub App (Week 3) ----------------------------------------------------
    # Distinct from `github_token` above: that's a PAT used for polling public
    # feeds; this is a GitHub App used to clone and scan a specific installed
    # repo with a short-lived, least-privilege token minted per scan.
    github_app_id: str = Field(default="", description="GitHub App ID (numeric, as a string).")
    github_app_private_key: str = Field(
        default="",
        description="PEM-encoded RSA private key for the GitHub App, inline. "
        "Mutually exclusive with github_app_private_key_path (this one wins if both are set).",
    )
    github_app_private_key_path: str = Field(
        default="",
        description="Path to a .pem file with the GitHub App's private key, "
        "for environments where an inline multi-line env var is awkward.",
    )

    # --- Repo checkout (Week 3) --------------------------------------------------
    clone_dir: str = Field(
        default="", description="Base directory for repo clones. Empty uses the system temp dir."
    )
    clone_timeout: float = Field(default=120.0, ge=1.0, le=600.0)
    clone_max_repo_mb: int = Field(
        default=500, ge=1, description="Reject a clone once its working tree exceeds this size."
    )

    # --- Repo/call-site scanner (Week 3) -----------------------------------------
    scan_max_file_bytes: int = Field(
        default=2_000_000,
        ge=1024,
        description="Skip individual source files larger than this during a repo scan.",
    )
    scan_max_files: int = Field(
        default=20_000,
        ge=1,
        description="Hard cap on files scanned per repo, to bound worst-case scan time.",
    )
    scan_min_recall: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Recall floor for the call_sites eval category. Per docs/plan.md, "
        "falling below this is the trigger to bring in tree-sitter instead of regex.",
    )

    # --- Fix generation + verification (Week 4) ----------------------------------
    fix_validate_syntax: bool = Field(
        default=True,
        description="Run FixValidator's syntax/sanity checks before writing an edit to disk.",
    )
    verify_enabled: bool = Field(
        default=True,
        description="Whether `depfix fix` runs the repo's own test suite to confirm "
        "each edit. Off by default in CI-less environments where no runtime is available.",
    )
    verify_install_timeout: float = Field(
        default=300.0,
        ge=1.0,
        le=1800.0,
        description="Wall-clock cap for `npm ci`/`yarn install`/`pnpm install` before Verifier "
        "gives up and marks the run's edits SUSPECT rather than hanging indefinitely.",
    )
    verify_test_timeout: float = Field(
        default=300.0,
        ge=1.0,
        le=1800.0,
        description="Wall-clock cap for one baseline or after-fix test run.",
    )
    verify_ignore_scripts: bool = Field(
        default=True,
        description="Pass --ignore-scripts to the install command so a hostile repo's "
        "package.json can't run arbitrary code (postinstall, etc.) during verification.",
    )
    verify_max_output_bytes: int = Field(
        default=2_000_000,
        ge=1024,
        description="Truncate captured install/test stdout+stderr past this size, so a "
        "runaway or malicious process can't exhaust memory holding its output.",
    )

    # --- Retry loop (Week 5) ----------------------------------------------------
    retry_max_rounds: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Bounded number of times `depfix fix` re-attempts a SUSPECT/REVERTED "
        "edit by feeding its concrete failure back to the LLM. 0 disables retries.",
    )

    # --- Fleet orchestrator (Week 6) --------------------------------------------
    repo_config_filename: str = Field(
        default=".depfix.yml",
        description="Per-repo opt-in pipeline config file the orchestrator looks for "
        "at the repo root before touching it at all.",
    )
    pipeline_require_config_file: bool = Field(
        default=True,
        description="Refuse to touch a repo that has no repo_config_filename at all. "
        "The whole point of the fleet orchestrator is that it never acts on a repo "
        "that hasn't explicitly opted in.",
    )
    pipeline_max_open_prs: int = Field(
        default=5,
        ge=1,
        description="Per-repo cap on simultaneously open depfix-authored PRs. Once "
        "reached, the orchestrator skips new changes for that repo until one closes.",
    )
    pipeline_max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Per-(repo, change) cap on non-terminal orchestrator attempts "
        "(see AttemptStatus.is_terminal) before it gives up and leaves the change FAILED.",
    )
    pipeline_retry_cooldown_hours: float = Field(
        default=6.0,
        ge=0.0,
        description="Minimum time between two orchestrator attempts at the same "
        "(repo, change), so a flaky failure doesn't get hammered on every cron tick.",
    )
    pipeline_max_changes_per_repo: int = Field(
        default=3,
        ge=1,
        description="Hard cap on how many distinct breaking changes the orchestrator "
        "processes for one repo in a single run, overridable lower (never higher) by "
        "that repo's own .depfix.yml max_changes_per_run.",
    )
    pipeline_max_cost_usd_per_run: float | None = Field(
        default=None,
        ge=0.0,
        description="Wall-clock budget's cost-ceiling counterpart: once this run's "
        "cumulative FixPipelineResult.total_cost crosses this, the orchestrator stops "
        "before the next repo/change the same way an expired --max-duration does. "
        "None (default) means uncapped -- only the --max-duration wall clock applies.",
    )
    pipeline_default_change_limit: int = Field(
        default=50,
        ge=1,
        description="Maximum classified changes considered by a normal fleet run.",
    )
    pipeline_newest_first: bool = Field(
        default=True,
        description="Consider recent breaking changes before historical backlog.",
    )
    pipeline_max_duration_minutes: float | None = Field(
        default=None,
        ge=0.0,
        description="Default fleet-run wall-clock budget in minutes; None is unlimited.",
    )
    pipeline_require_lock: bool = Field(
        default=True,
        description="Require the Postgres advisory lock for live fleet runs.",
    )

    # --- Observability --------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    environment: Literal["development", "staging", "production", "test"] = "development"
    sentry_dsn: str = Field(default="")
    log_format: Literal["text", "json"] = "text"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance (env loaded once per process)."""
    return Settings()
