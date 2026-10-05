# depfix — What We're Building and Why

## The Problem

API communication is broken. Over the past year, working with 50+ API vendors (mostly early-stage
startups), one pattern is consistent: breaking changes ship with little warning, useful features
quietly launch and go unnoticed, and changelogs don't get read.

At AWS, over 30% of service downtime was due to external API/package changes going unnoticed.

This friction made sense before agentic coding tools existed. Now it doesn't. Tools like Claude Code,
Devin, and Greptile prove developers and enterprises will give codebase access to external tools if
they're valuable. The infrastructure for automated code changes exists. What's missing is the
**application layer connecting API providers to their customers' codebases**.

API providers shouldn't just announce changes — they should apply them.

## The Solution: depfix

depfix watches your repos for breaking provider API/SDK version changes, finds version drifts (both
minor bumps and major breaking changes), locates every affected call-site in your code, generates
version bumps and LLM-written fixes, runs your tests to verify them, and opens a PR — all
automatically.

**Pipeline:** `init → watch → scan → plan → apply`

1. **Watch** — poll provider feeds (npm, pypi, GitHub releases, OpenAPI diffs) for new versions
2. **Scan** — clone the target repo, parse manifests/lockfiles, find every call-site that uses the
   provider's SDK/API. Detect version drift: is the repo behind? By a minor? A major?
3. **Plan** — for each breaking change with affected call-sites, generate a fix using an LLM
   (Bedrock/Gemini). For minor drift, generate a version bump. For major drift with known migration
   paths, generate the code migration. Plan artifacts are immutable.
4. **Apply** — apply the planned fixes, run the repo's own test suite to verify, open a PR with
   the diff, test results, and migration rationale.

This could work as per-provider agents ("install Stripe's update agent") or as a neutral third-party
service tracking changes across vendors — like Dependabot but for APIs.

## What Exists Today

- **27 providers** tracked in `providers.yaml`: openai, stripe, anthropic, supabase, vercel-ai,
  sentry, prisma, clerk, langchain, aws-s3, firebase, twilio, sendgrid, octokit, slack, discord,
  mongodb, redis, posthog, algolia, google-cloud, elasticsearch, postgresql, kafka, rabbitmq,
  mysql, astro
- **3 fix-supported ecosystems**: JavaScript, Python, Ruby (Go is scan-only)
- **Full pipeline working**: init → watch → scan → plan → apply (with LLM-generated fixes)
- **Eval corpus**: deterministic test cases for scan accuracy
- **Test infrastructure**:
  - `make test` — unit tests (no LLM, no network)
  - `make eval` — eval corpus (deterministic, no LLM)
  - `bash scripts/test_pipeline.sh provider:owner/repo` — run scan on a real repo
  - `bash test_all_repos.sh` — run init→scan→plan on 7 real-world repos
  - `depfix pipeline --dry-run --no-pr` — full pipeline without opening PRs

### Test Repos (real-world forks — agents MUST test against these)

| Repo | Provider | What it tests |
|---|---|---|
| `bedilk/probot` | octokit | Real GitHub bot, Octokit SDK usage |
| `bedilk/renovate` | octokit | Large repo, many Octokit call-sites |
| `bedilk/bolt-js` | slack | Slack SDK, real event handlers |
| `bedilk/sentry` | slack | Slack integration inside Sentry |
| `bedilk/AtlantaBot` | discord | Discord.js bot, event-driven |
| `bedilk/guide` | discord | Discord.js documentation site |
| `bedilk/Rocket.Chat` | mongodb | Large app, MongoDB driver throughout |
| `bedilk/firecrawl` | openai, anthropic | Multi-provider AI app |
| `bedilk/superset` | sentry | Large Python app, Sentry SDK |

### E2E Test Repos (purpose-built for depfix)

| Repo | Provider | Difficulty | What it tests |
|---|---|---|---|
| `bedilk/depfix-test-sentry-v6-app` | sentry | Medium | 2 major version drift (@sentry/node@6.19.7) |
| `bedilk/depfix-test-openai-v3-chat` | openai | Medium | Version drift + API method drift (openai@3.3.0) |
| `bedilk/depfix-test-anthropic-callsites` | anthropic | Hard | API method drift only (@anthropic-ai/sdk@0.6.2) |

### Seed Repos (controlled fixtures)

| Repo | Migration |
|---|---|
| `bedilk/seed-openai-v3-to-v4` | OpenAI v3→v4 |
| `bedilk/seed-anthropic-v0-v0x` | Anthropic completions→messages |
| `bedilk/seed-stripe-apiversion` | Stripe API version migration |
| `bedilk/seed-sentry-v7-v8` | Sentry v7→v8 |
| `bedilk/seed-mongodb-v4-v5` | MongoDB v4→v5 |
| `bedilk/seed-supabase-v1-v2` | Supabase v1→v2 |
| `bedilk/seed-vercel-ai-v2-v3` | Vercel AI SDK v2→v3 |
| `bedilk/seed-multi-sdk` | Multi-provider migration |

## What the Agent Team Is Building

The agent team validates and extends depfix toward production-readiness:
- **Test on real repos** — run the pipeline on real-world forks and e2e repos to find what works and what breaks
- **Broader provider coverage** — more providers, better detection accuracy
- **Deeper eval corpus** — more test cases, more ecosystems, more edge cases
- **Higher scan recall** — find call-sites the current scanner misses
- **Hardened fixers** — adversarial review of ecosystem-specific fixers
- **New provider research** — identify high-value providers not yet tracked

---

## Domain Glossary

### Dependency drift
A repository's declared SDK version is behind the version observed from its configured registry feed.
Drift is a dependency-level fact; it does not imply that any particular source call is broken.
Minor drift = patch/minor behind. Major drift = behind by a major version with potential breaking changes.

### Automatic dependency update
A patch or minor dependency drift whose version constraints can be rewritten unambiguously.
Proceeds through the normal verification and PR flow.

### Vetted migration
A documented, provider-specific API migration with a concrete old and new call shape. Major-version
drift is reported and planned, but is only applied when paired with a vetted migration.

### Security advisory
A published record that a specific range of a package's versions has a known vulnerability. Sourced
from a public database (OSV, GitHub Advisory Database). Distinct from drift: drift says "a newer
version exists"; an advisory says "your current version is unsafe."

### Reachability
Whether a repository's own code actually calls the API a change or advisory concerns. An advisory or
breaking change is *reachable* when a scanned call site touches the affected symbol, and *unreachable*
when the package is merely declared but never called in the relevant way.

### Cooldown
A minimum age a newly published version must reach before depfix adopts it. A version published hours
ago may be compromised; the cooldown is a supply-chain safety gate.

### Triage rule
A repository's standing instruction about a class of change: dismiss it, snooze it, or let it proceed.
Rules are proposed (optionally by an LLM) and always confirmed by a human before they suppress anything.
