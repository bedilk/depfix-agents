# depfix

**Dependabot for APIs.** Automatically detects breaking API/SDK changes, finds every affected line in your code, generates fixes, runs your tests, and opens a PR.

[![CI](https://github.com/bedilk/depfix-agents/actions/workflows/ci.yml/badge.svg)](https://github.com/bedilk/depfix-agents/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

---

## The problem

Over 30% of service downtime traces back to external API/package changes going unnoticed. Breaking changes ship with little warning. Changelogs don't get read. Teams discover the breakage in production.

Dependabot bumps version numbers. **depfix fixes your code.**

## How it works

```
watch → scan → plan → apply → PR
```

| Step | What happens |
|------|-------------|
| **Watch** | Polls 27+ provider feeds (npm, PyPI, GitHub releases, OpenAPI diffs) for new versions and breaking changes |
| **Scan** | Clones your repo, finds every call-site using the affected API, detects version drift |
| **Plan** | Generates LLM-written fixes for breaking changes, version bumps for minor drift, runs your test suite to verify |
| **Apply** | Applies the verified fixes and opens a pull request |

## Quick start

```bash
pip install depfix

# Scan a repo for OpenAI breaking changes
depfix scan --repo your-org/your-app --provider openai

# Generate a fix plan (no PR yet)
depfix plan your-org/your-app --provider stripe

# Apply fixes and open a PR
depfix apply your-org/your-app --provider sentry
```

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

## Supported providers

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

## Supported ecosystems

| Ecosystem | Scan | Fix | Verify |
|-----------|------|-----|--------|
| JavaScript/TypeScript (npm) | Yes | Yes | Yes |
| Python (PyPI) | Yes | Yes | Yes |
| Ruby (RubyGems) | Yes | Yes | Yes |
| Go | Yes | -- | -- |
| Java, Kotlin, Rust, PHP, C#, Swift | Yes | -- | -- |

## What makes depfix different

- **Finds call-sites, not just version numbers.** depfix traces imports to actual API usage across your codebase.
- **Verified fixes.** Every generated fix runs your test suite before and after. Broken fixes never reach a PR.
- **Deterministic where possible.** OpenAPI diffs and semver comparisons don't need an LLM. Only actual code rewrites use one.
- **27+ providers.** Not just OpenAI and Stripe. Real coverage across the APIs developers actually use.
- **Honest confidence.** Every finding has a confidence level (HIGH/MEDIUM/LOW). depfix doesn't guess.

## CLI reference

```bash
depfix init                          # set up local database and integrations
depfix watch --once                  # poll feeds for new changes
depfix scan --repo org/app --provider stripe  # find affected call-sites
depfix plan org/app --provider stripe         # generate verified fixes
depfix apply org/app --provider stripe        # open a PR with the fixes
depfix eval --no-llm                          # run deterministic test corpus
```

## Configuration

All config is via environment variables or `.env` file:

| Variable | Purpose |
|----------|---------|
| `GOOGLE_API_KEY` | Google Generative AI key (for Gemini) |
| `LLM_PROVIDER` | `gemini`, `bedrock`, or `ollama` |
| `GITHUB_APP_ID` | GitHub App for remote repo scanning |
| `DATABASE_URL` | SQLite (default) or Postgres DSN |

See [.env.example](.env.example) for the full list.

## Self-hosted

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
make test        # 893 unit tests, no network
make lint        # ruff check
make typecheck   # mypy
make eval        # deterministic eval corpus (CI gate, 91%+)
```

## Built by

**Bedil Karimov** and **Tohir Saidzoda**

We spent a year working with 50+ API vendors. The pattern was consistent: API communication is broken. Breaking changes ship with little warning. Useful features quietly launch and go unnoticed.

The infrastructure for automated code changes exists now. What was missing is the application layer connecting API providers to their customers' codebases. That's depfix.

## License

MIT
