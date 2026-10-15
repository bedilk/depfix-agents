# depfix

**Dependabot for APIs.** When a provider ships a breaking change, depfix scans your codebase, finds every affected call-site, generates verified fixes, and opens a pull request.

[![CI](https://github.com/bedilk/depfix-agents/actions/workflows/ci.yml/badge.svg)](https://github.com/bedilk/depfix-agents/actions)
[![PyPI version](https://img.shields.io/pypi/v/depfix-ai.svg)](https://pypi.org/project/depfix-ai/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Source%20Available-orange.svg)](LICENSE)

```bash
pip install depfix-ai
```

---

## The Problem

Over 30% of service downtime traces back to external API/package changes going unnoticed. Breaking changes ship without warning. Changelogs don't get read. Teams discover the breakage in production.

**Dependabot bumps version numbers. depfix fixes your code.**

```
[ Traditional Dependency Bumper ]
  package.json: openai@3.x  -->  openai@4.x  --> Runtime errors everywhere

[ depfix ]
  1. Detects the breaking change from provider feeds
  2. Scans your codebase for every affected call-site
  3. Generates LLM-verified code fixes
  4. Runs your test suite before and after
  5. Opens a ready-to-merge PR
```

## How It Works

```
watch --> scan --> plan --> apply --> PR
```

| Step | What Happens |
|------|-------------|
| **Watch** | Polls 27+ provider feeds (npm, PyPI, GitHub releases, OpenAPI diffs) for new versions and classified breaking changes |
| **Scan** | Clones your repo, traces imports to actual API usage, finds every call-site with confidence scoring (HIGH/MEDIUM/LOW) |
| **Plan** | Matches breaking changes to detected call-sites, generates LLM-written fixes, runs your test suite to verify each fix |
| **Apply** | Applies verified fixes, composes version bump + API migration into one PR |

## Quick Start

### Installation

```bash
pip install depfix-ai
```

> **Note:** The PyPI package name is `depfix-ai`. The CLI command is `depfix`.

### Basic Usage

```bash
# Initialize local database and provider feeds
depfix init

# Scan a repo for breaking changes against a specific provider
depfix scan --repo your-org/your-app --provider openai

# Generate a fix plan (no PR yet)
depfix plan your-org/your-app --provider stripe

# Apply fixes and open a PR
depfix apply your-org/your-app --provider sentry
```

### Full Pipeline (Single Command)

```bash
# Run the full pipeline: scan + plan + apply
bash scripts/test_pipeline.sh openai:your-org/your-app
```

## Supported Providers

27+ providers out of the box. depfix auto-discovers new providers from npm, PyPI, and RubyGems.

| Category | Providers |
|----------|-----------|
| **AI/ML** | OpenAI, Anthropic, Google Cloud AI, LangChain, Vercel AI SDK |
| **Payments** | Stripe |
| **Auth** | Clerk, Supabase, Auth0 |
| **Databases** | MongoDB, Redis, PostgreSQL, MySQL, Prisma, Elasticsearch |
| **Observability** | Sentry, PostHog, Datadog, New Relic |
| **Messaging** | Twilio, SendGrid, Slack, Discord |
| **Cloud** | AWS S3, Firebase, Google Cloud, Cloudflare |
| **Other** | Algolia, Kafka, RabbitMQ, Astro, Octokit |

## Supported Ecosystems

| Ecosystem | Scan | Fix | Verify |
|-----------|:----:|:---:|:------:|
| JavaScript / TypeScript (npm) | Yes | Yes | Yes |
| Python (PyPI) | Yes | Yes | Yes |
| Ruby (RubyGems) | Yes | Yes | Yes |
| Go | Yes | -- | -- |
| Java, Kotlin, Rust, PHP, C#, Swift | Yes | -- | -- |

## What Makes depfix Different

- **Call-site detection, not just version numbers.** depfix traces imports to actual API usage across your codebase. It finds the exact lines that break.
- **Verified fixes.** Every generated fix runs your test suite before and after. Broken fixes never reach a PR.
- **Deterministic where possible.** OpenAPI diffs and semver comparisons don't need an LLM. Only actual code rewrites use one.
- **Version drift + API migration in one PR.** depfix composes package.json version bumps with code-level fixes into a single, reviewable pull request.
- **Honest confidence scoring.** Every finding has a confidence level (HIGH/MEDIUM/LOW). depfix doesn't guess.

## GitHub Action

Add to `.github/workflows/depfix.yml`:

```yaml
name: depfix
on:
  schedule:
    - cron: '0 8 * * 1'  # every Monday at 8am
  workflow_dispatch:

jobs:
  depfix:
    runs-on: ubuntu-latest
    steps:
      - uses: bedilk/depfix-agents@main
        with:
          provider: openai,stripe,sentry
          mode: apply
          api-key: ${{ secrets.GOOGLE_API_KEY }}
```

## CLI Reference

```bash
depfix init                                        # set up local database and integrations
depfix watch --once                                # poll feeds for new changes
depfix scan --repo org/app --provider stripe       # find affected call-sites
depfix plan org/app --provider stripe              # generate verified fixes
depfix apply org/app --provider stripe             # open a PR with the fixes
depfix eval --no-llm                               # run deterministic test corpus
```

## Configuration

All config is via environment variables or `.env` file:

| Variable | Purpose |
|----------|---------|
| `GOOGLE_API_KEY` | Google Generative AI key (for Gemini) |
| `LLM_PROVIDER` | `gemini`, `bedrock`, or `ollama` |
| `GITHUB_APP_ID` | GitHub App for remote repo scanning |
| `GITHUB_APP_PRIVATE_KEY` | Private key for the GitHub App |
| `DATABASE_URL` | SQLite (default) or Postgres connection string |

See [.env.example](.env.example) for the full list.

## Self-Hosted

```bash
git clone https://github.com/bedilk/depfix-agents
cd depfix-agents
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # edit with your keys
depfix init
```

Docker:

```bash
docker compose up -d --build
docker compose exec app depfix scan --repo org/app --provider openai
```

## Testing

```bash
make test        # 893 unit tests, no network, no LLM
make lint        # ruff check + format
make typecheck   # mypy strict
make eval        # deterministic eval corpus (CI gate, 91%+)
```

## Architecture

```
src/depfix/
  cli.py              # CLI entry point (watch, scan, plan, apply)
  orchestrator/       # Pipeline runner, policy engine, upgrade plans
  scanners/           # Call-site detection, version applicability
  fixers/             # LLM-powered code rewriting
  classify/           # Breaking change classification from spec diffs
  core/               # Domain models, agent, change feeds
  storage/            # SQLAlchemy schema, migrations
  gh/                 # GitHub App integration, PR creation
```

## Built By

**Bedil Karimov** and **Tohir Saidzoda**

We spent a year working with 50+ API vendors. The pattern was consistent: API communication is broken. Breaking changes ship with little warning. Useful features quietly launch and go unnoticed.

The infrastructure for automated code changes exists now. What was missing is the application layer connecting API providers to their customers' codebases. That's depfix.

## License

Source Available - see [LICENSE](LICENSE) for details.
