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

    # --- Observability --------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    environment: Literal["development", "staging", "production", "test"] = "development"
    sentry_dsn: str = Field(default="")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance (env loaded once per process)."""
    return Settings()
