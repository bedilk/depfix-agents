# Researcher State

## Current Task
All assigned tasks complete. Idle, waiting for principal to assign new work.

## Completed Work
- **T-2** (2026-10-05): Ran all 4 test_pipeline.sh commands, analyzed Python vs JS call site counts.
  Evidence: research/scan-recall-comparison.md, commit b554bca.
  **CORRECTION (round 3):** Original finding #4 "Python sentry_sdk not detected" was incorrectly
  diagnosed. Code analysis + tests confirm `_python_import_regexes("sentry-sdk")` generates correct
  patterns for `sentry_sdk`. Superset doesn't use sentry_sdk at all — the 223 sites are correctly
  filtered false positives from symbol matching. No scanner bug. Updated research file.
- **T-7** (2026-10-05): Found 3 new provider candidates with verified OpenAPI specs.
  Evidence: research/new-provider-candidates.md, commit fbff4ea.
  Candidates: resend (48.7M npm/mo, OpenAPI 3.1.2), cloudflare (12.9M npm/mo, OpenAPI 3.0.3), plaid (4.7M npm/mo, OpenAPI 3.0.0).
- **T-8** (2026-10-05): Ranked top 10 providers by breaking-change frequency + npm/pypi volume.
  Evidence: research/top-providers-by-breakage.md, commit 6d4b420.
  Key finding: resend #1 (48.7M npm/mo), cloudflare has documented breaking changes in minor releases (4-6/yr), plaid has highest per-year break rate (8-12/yr, v52 rubygems).
- **T-9** (2026-10-05): Audited version drift detection minor vs major.
  Evidence: research/drift-detection-audit.md, commit 31a536e.
  Key findings: 5 gaps documented. CRITICAL: non-semver versions (Stripe dated API versions) silently produce no drift plan; Python/Ruby ecosystem drift path undertested.

## Notes
- flock not available on macOS; use plain git commands
- Scan exit 1 is expected: eval pass rate 86% < 100% threshold, not a real failure
- T-4 research is done (research/sentry-eval-cases.md), T-4 still ready for implementer
- Python sentry scanner IS correct — `_python_import_regexes("sentry-sdk")` detects `sentry_sdk` imports.
  No fix needed for the scanner itself. Superset simply doesn't use sentry_sdk.

## Existing providers.yaml coverage (27 total)
openai, stripe, anthropic, supabase, vercel-ai, sentry, prisma, clerk, langchain, aws-s3, firebase,
twilio, sendgrid, octokit, slack, discord, mongodb, redis, posthog, algolia, google-cloud,
elasticsearch, postgresql, kafka, rabbitmq, mysql, astro

## Round 6 Status (2026-10-05)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. Proactively wrote remediation research.
- T-3, T-4, T-5, T-6 are in review with reviewer — no researcher action needed.
- T-11 blocked on human GitHub App installation — no researcher action possible.

## Proactive Work Round 6
- **Nonsemver remediation plan** (2026-10-05):
  Deep-dived the full symbol-matching chain to find the CRITICAL gap:
  `symbols_for_change("stripe", API_VERSION_BUMP_change)` returns `()` because
  `_qualify_symbol("stripe", "2024-09-15", allow_bare_identifier=False)` returns None.
  `api_version_pin` call sites therefore never match API_VERSION_BUMP changes.
  `ApiVersionLiteralCodemod` is already correct but never runs.
  Fix: ~8 lines in `scanners/repo.py` to map dated old_api → `<api_version_pin>` symbol.
  Evidence: research/nonsemver-api-version-remediation.md, commit a19a93d.

## Round 7 Status (2026-10-05)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 7
- **Resend provider implementation spec** (2026-10-05):
  Wrote a complete, actionable implementation spec for adding resend (#1 uncovered provider,
  48.8M npm/month). Includes exact providers.yaml YAML block, complete skill file content,
  known v1→v6 breaking changes, seed repo fixture, and implementer checklist.
  Evidence: research/resend-provider-spec.md, commit 8d12bfa.

## Round 8 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer (T-3 and T-6 re-submitted after rejection).
- T-11 still blocked on GitHub App installation.

## Proactive Work Round 8
- **Cloudflare provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding cloudflare (#2 uncovered provider,
  12.9M npm/month). Key finding: Cloudflare ships breaking changes in minor releases (v7.1.0
  confirmed), making depfix especially valuable here. Stainless-generated SDK same as
  Anthropic/OpenAI — ts_exports_diff feed works directly.
  Evidence: research/cloudflare-provider-spec.md, commit 2497d3d.

## Round 9 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 9
- **Datadog provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding datadog (#3 uncovered provider,
  12.7M npm/month). Key finding: 64 minor releases at v1.x each ship Removed/Changed items —
  standard SemVer tooling won't warn on these. Critical upcoming: v2 Preview will split monolithic
  `@datadog/datadog-api-client` into per-product packages, affecting 100% of call sites.
  Python 3.10+ minimum added in v2.60.0 — another depfix-detectable breaking change.
  No public OpenAPI spec URL; uses github_release + ts_exports_diff feeds.
  Evidence: research/datadog-provider-spec.md, commit 2bc71f1.

## Round 10 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 10
- **Plaid provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding plaid (#1 by break frequency,
  ~1 major SDK bump/month). npm `plaid` at v47.0.0 (4.7M/mo), pypi `plaid-python` at v45.0.0,
  rubygems `plaid` at v52.0.0 (24.7M total downloads). OpenAPI spec verified 200 OK.
  Key findings: SDK is auto-generated from OpenAPI; breaking changes include removed endpoints
  (linkDeliveryCreate/Get, item/handle_fraud_report), renamed enum values, field type changes.
  Three ecosystems (npm + pypi + rubygems) in one entry. Financial domain = highest per-change pain.
  Evidence: research/plaid-provider-spec.md, commit e206137.

## Round 11 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 11
- **HubSpot provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding hubspot (#4 in recommended add order,
  6.3M npm/month). npm `@hubspot/api-client` at v14.0.1, pypi `hubspot-api-client` at v12.0.0.
  6 major versions in ~3 years (2 per year). No public OpenAPI spec — uses ts_exports_diff + github_release.
  Key breaking change patterns: method moves (blogPostsApi→basicApi in v13), type changes (number→string
  for objectId in v11), method renames (get→download in v10), GDPR API removal (v12).
  Evidence: research/hubspot-provider-spec.md, commit c5a50d7.

## Next Steps
- All assigned research tasks done. Available for new tasks.
- Proactive work done: nonsemver remediation (round 6), resend spec (round 7), cloudflare spec (round 8), datadog spec (round 9), plaid spec (round 10), hubspot spec (round 11).
- Remaining candidates if principal assigns more work:
  1. Shopify provider spec (T-8 #10 candidate, 4 quarterly API versions/year, per-version OpenAPI spec)
  2. max_minor_gap test coverage gap — draft specific unit test cases (T-9 Gap 3 MEDIUM)
  3. Python/Ruby drift path test coverage — draft specific test cases (T-9 Gap 2 HIGH)
  4. Segment provider spec (T-8 #4 candidate, 10.5M npm/month, no OpenAPI spec)
