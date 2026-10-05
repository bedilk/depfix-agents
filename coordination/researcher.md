# Researcher State

## Current Task
Working on T-8 (rank top 10 providers by breaking-change frequency).
T-7 is done (commit fbff4ea).

## Completed Work
- **T-2** (2026-10-05): Ran all 4 test_pipeline.sh commands, analyzed Python vs JS call site counts.
  Evidence: research/scan-recall-comparison.md, commit b554bca.
  Key finding: Python sentry_sdk gap — scanner detects `sentry.*` but Python apps use `sentry_sdk.*`.
- **T-7** (2026-10-05): Found 3 new provider candidates with verified OpenAPI specs.
  Evidence: research/new-provider-candidates.md, commit fbff4ea.
  Candidates: resend (48.7M npm/mo), cloudflare (12.9M npm/mo), plaid (4.7M npm/mo).

## Notes
- flock not available on macOS; use plain git commands (no parallel commits needed — researcher works serially)
- Scan exit 1 is expected: eval pass rate 86% < 100% threshold, not a real failure
- T-4 research is done (research/sentry-eval-cases.md) but T-4 still needs implementer work
- T-8: rank 10 providers NOT in providers.yaml by breaking-change frequency + npm/pypi downloads

## Existing providers.yaml coverage (27 total)
openai, stripe, anthropic, supabase, vercel-ai, sentry, prisma, clerk, langchain, aws-s3, firebase,
twilio, sendgrid, octokit, slack, discord, mongodb, redis, posthog, algolia, google-cloud,
elasticsearch, postgresql, kafka, rabbitmq, mysql, astro

## Next Steps
1. Complete T-8: rank 10 providers by breaking-change frequency (not in providers.yaml)
2. Optionally T-9: audit version drift detection minor vs major
