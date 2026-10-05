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

- **25 providers** tracked in `providers.yaml` (stripe, openai, anthropic, sentry, mongodb, supabase,
  vercel-ai, kafka, rabbitmq, and more)
- **3 fix-supported ecosystems**: JavaScript, Python, Ruby (Go is scan-only)
- **Scan pipeline**: detects call-sites, classifies changes, maps API symbols to source locations
- **Plan + Apply**: LLM-generated fixes with test verification
- **Eval corpus**: deterministic test cases for scan accuracy
- **8 seed repos** (`bedilk/seed-*`) for controlled end-to-end testing

## What the Agent Team Is Building

The agent team advances depfix toward production-readiness:
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
