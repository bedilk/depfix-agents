# Progress Log — for Bedil's review

*Last updated: 2026-09-17 (Tohir + Claude). Bedil: add your comments in the section at the bottom, or comment on the PR.*

## What has been done so far

### 1. Repo pulled and audited (2026-09-17)
- Cloned `bedilk/dependency_check` to the shared workspace (clone needed HTTP/1.1 + larger postBuffer — GitHub kept resetting the connection; note for CI/remote environments).
- Full ship-readiness audit of the codebase (staff-engineer level, every module read). Verdict: **the pipeline is real and well-engineered** — watch → classify → scan → fix → verify → PR all work end-to-end as a CLI; the verify/attribution/confidence-tier design and the plan/apply artifact flow are above-Alpha quality. But it is CLI+cron only, single-tenant, JS/TS only, and has a set of trust/hygiene gaps listed below.

### 2. Market, competitor and pricing research (5 parallel research passes, web-sourced, late-2026 data)
Full findings in [`docs/research/BUSINESS_ASSESSMENT.md`](research/BUSINESS_ASSESSMENT.md). Headlines:

- **Closest shipped analog:** EdgeBit (YC) — built nearly this pipeline for JS/TS, **acquired by FOSSA Sept 2025** ~1 year after a $3.1M seed. Both prior exits in the niche (Dependabot → GitHub, Renovate → Mend) were modest feature acquisitions.
- **Commoditization clock:** GitHub shipped "assign Dependabot alerts to an AI agent that fixes and iterates on tests" in **April 2026**, bundled. AWS Transform added npm migrations in 2026.
- **BUT — the broader "all-services-in" vision is unclaimed whitespace:** nobody chains watch-third-party-API-specs → classify → find call sites → auto-fix → **verified** PR. Unified-API cos (Merge, Apideck) sell "integrations never break" but only for interchangeable vendors; SDK-gen cos got absorbed (Stainless → Anthropic May 2026, liblab → Postman Nov 2025); API-diff tooling is provider-side or dead (Optic → Atlassian → shelved). Closest OSS analog (`mendapi`) has 1 star and no test verification.
- **Why the whitespace is empty (our four hard problems):** most vendors publish no OpenAPI spec; raw REST calls are nearly invisible to static scanning; runtime-built calls need a traffic component eventually; and **customer tests usually mock external APIs, so "tests still pass" can prove nothing** — this last one is our headline claim, so it's ours to solve.
- **Pricing recommendation:** per-repo tiers at launch ($49–250/repo/mo), outcome-based per-merged-fix later ($25–100/fix), Moderne-style contracts ($150–400K/yr) for large fleets. JS/TS wedge SAM ≈ $250M–1.5B/yr.
- **Honest verdict:** not a $100B category (the whole wedge is sub-$2B revenue). Realistic best case today: $5–30M acqui-hire or a $1–20M-ARR niche SaaS; the "all-services-in" framing raises the ceiling **only if** the verification problem gets solved. The corpus of labeled breaking changes + real merge outcomes is the asset that appreciates either way.

### 3. Findings that need fixing in this repo (from the audit)
- [ ] **Secret redaction missing:** `fixers/gemini.py` sends entire file contents to Gemini; docs promise "never send secret material to the LLM" — code doesn't enforce it.
- [ ] README documents `.github/workflows/ci.yml` — **no `.github/` directory exists**.
- [ ] `.env.example` referenced by README but absent.
- [ ] `changes.txt` (6,362-line raw chat transcript) and real run artifacts in `output/` are committed at repo root.
- [ ] `pyproject.toml` Homepage/Issues URLs are placeholders (`your-org`).
- [ ] Name collision: unrelated OSS project `agent0ai/depfix` (Aug 2026) uses the same name.
- [ ] Only 2 of 20 providers (openai, stripe) have OpenAPI spec feeds — the rest ride version-bump signals.
- [ ] No visibility without psql — needs a `depfix status` command.
- [ ] Sandbox is process-level; container-grade isolation is a post-MVP enterprise item.

### 4. Plan agreed
Timeline compressed to **3 days to MVP + test** — see [`docs/MVP_3DAY_PLAN.md`](MVP_3DAY_PLAN.md). One wedge (OpenAI SDK), one metric (KEPT rate under real test verification), one deliverable (recorded end-to-end run + 2–3 real repos + numbers).

## Decisions needed from Bedil
1. `GOOGLE_API_KEY` available, or Ollama-only for the MVP?
2. GitHub App (APP_ID + private key) — exists, or local-path testing this week?
3. Rename: agree it's needed before anything public? Name ideas welcome.
4. Anything in the assessment you disagree with — argue in the comments below.

---

## Bedil's comments

*(write here)*
