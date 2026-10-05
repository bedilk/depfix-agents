# New Provider Candidates with Public OpenAPI Specs

**Task:** T-7 — Find 3 new providers with public OpenAPI specs not yet in providers.yaml  
**Date:** 2026-10-05  
**Researcher:** researcher agent

---

## Existing Providers (already in providers.yaml)

27 providers already covered: openai, stripe, anthropic, supabase, vercel-ai, sentry, prisma, clerk,
langchain, aws-s3, firebase, twilio, sendgrid, octokit, slack, discord, mongodb, redis, posthog,
algolia, google-cloud, elasticsearch, postgresql, kafka, rabbitmq, mysql, astro.

---

## Candidate 1: Resend

**What it is:** Modern email API for developers — the dominant new-generation alternative to SendGrid.

| Field | Value |
|---|---|
| npm package | `resend` |
| pypi package | `resend` |
| rubygems gem | `resend` |
| npm downloads/month | **48,786,757** (2026-09-05 → 2026-10-04) |
| rubygems total downloads | 1,244,433 |
| pypi latest version | 2.49.1 |
| OpenAPI spec URL | `https://raw.githubusercontent.com/resend/resend-openapi/main/resend.yaml` |
| Spec version | OpenAPI 3.1.2 |
| Spec URL status | **200 OK** (verified 2026-10-05) |
| GitHub SDK repo | resend/resend-node |
| Latest release | v6.32.0 |

**OpenAPI spec content (verified):**
```yaml
openapi: 3.1.2
info:
  title: Resend
  version: 1.5.1
  description: 'Resend is the email platform for developers.'
```

**Breaking-change pattern:** Resend ships minor-version updates frequently (v6.28→v6.32 in recent weeks). SDK is actively developed. Resend's API is stable at v1 but the SDK wrapping layer changes frequently. The `resend` npm package has ~49M downloads/month, making it one of the highest-volume developer SDKs not covered by depfix.

**Candidate test repo:** `bedilk/seed-resend` (or any repo with `import { Resend } from 'resend'`)

**Rationale:** Highest npm download count of any uncovered provider. Developers migrating from SendGrid to Resend hit SDK shape changes. The public OpenAPI spec is well-maintained and actively updated alongside SDK releases.

---

## Candidate 2: Cloudflare

**What it is:** CDN, DNS, Workers, and API platform — the `cloudflare` SDK wraps Cloudflare's management API.

| Field | Value |
|---|---|
| npm package | `cloudflare` |
| pypi package | `cloudflare` |
| rubygems gem | `cloudflare-ruby` (limited: v0.5.0, 1,903 downloads) |
| npm downloads/month | **12,855,815** (2026-09-05 → 2026-10-04) |
| pypi latest version | 5.9.0 |
| OpenAPI spec URL | `https://raw.githubusercontent.com/cloudflare/api-schemas/main/openapi.yaml` |
| Spec version | OpenAPI 3.0.3 |
| Spec URL status | **200 OK** (verified 2026-10-05) |
| GitHub SDK repo | cloudflare/cloudflare-typescript |
| Latest release | v7.3.0 (2026-10-02) |

**OpenAPI spec content (verified):**
```yaml
openapi: 3.0.3
info:
  description: |-
    Welcome to Cloudflare's API documentation site. ...
```

**Breaking-change pattern (confirmed from releases):**
- v7.0.0 released 2026-07-09: "This is a major release" with full API restructuring
- v7.1.0 released 2026-08-17: **Breaking change in a minor release** — `cloudforceOne.threatEvents.indicatorTypes` renamed
- v7.2.0 released 2026-09-25: More changes
- v7.3.0 released 2026-10-02: Latest

Cloudflare ships breaking changes in minor versions, making automatic scanning particularly valuable. The SDK uses a Stainless-generated pattern (same as Anthropic/OpenAI), so depfix's existing `ts_exports_diff` feed type would work directly.

**Candidate test repo:** Any Cloudflare Workers project using `import Cloudflare from 'cloudflare'`

**Rationale:** 12.9M npm downloads/month, actively ships breaking changes in minor releases (documented above), strong OpenAPI spec maintained in a dedicated `cloudflare/api-schemas` repo, Stainless-generated SDK pattern already familiar to depfix.

---

## Candidate 3: Plaid

**What it is:** Financial data API — the standard for bank account linking and transaction data (used in Venmo, Cash App, many fintech apps).

| Field | Value |
|---|---|
| npm package | `plaid` |
| pypi package | `plaid-python` |
| rubygems gem | `plaid` |
| npm downloads/month | **4,701,373** (2026-09-05 → 2026-10-04) |
| rubygems total downloads | 24,742,704 |
| pypi latest version | 45.0.0 |
| rubygems latest version | 52.0.0 |
| OpenAPI spec URL | `https://raw.githubusercontent.com/plaid/plaid-openapi/master/2020-09-14.yml` |
| Spec version | OpenAPI 3.0.0 |
| Spec URL status | **200 OK** (verified 2026-10-05) |
| GitHub SDK repo | plaid/plaid-node |
| Latest npm version | 9.2.0 |

**OpenAPI spec content (verified):**
```yaml
openapi: 3.0.0
servers:
- description: Production
  url: https://production.plaid.com
- description: Sandbox
```

**Breaking-change pattern:** The pypi package is at v45.0.0 and rubygems at v52.0.0. Plaid versions its SDKs to match API version dates/increments, resulting in extremely frequent major version bumps. GitHub shows v6.0.0→v7.0.0→v9.x.0 transitions recently. Plaid's API is complex (20+ product areas: auth, transactions, investments, identity, etc.) and each product area frequently changes shapes.

**Candidate test repo:** `bedilk/seed-plaid` or `plaid/quickstart` (public example app)

**Rationale:** 4.7M npm downloads/month in a high-value financial domain where breaking changes have real business consequences. Rubygems at v52 and pypi at v45 indicate extremely high breaking-change frequency. The public OpenAPI spec is the source of truth for all Plaid SDKs (they are auto-generated from it), making depfix integration straightforward.

---

## Summary Table

| Provider | npm pkg | npm downloads/month | pypi pkg | OpenAPI spec URL | spec status |
|---|---|---|---|---|---|
| Resend | `resend` | 48,786,757 | `resend` | `https://raw.githubusercontent.com/resend/resend-openapi/main/resend.yaml` | 200 OK |
| Cloudflare | `cloudflare` | 12,855,815 | `cloudflare` | `https://raw.githubusercontent.com/cloudflare/api-schemas/main/openapi.yaml` | 200 OK |
| Plaid | `plaid` | 4,701,373 | `plaid-python` | `https://raw.githubusercontent.com/plaid/plaid-openapi/master/2020-09-14.yml` | 200 OK |

## Recommended Priority

1. **Resend** — highest download count, clean SDK, modern OpenAPI spec, no rubygems coverage gap
2. **Cloudflare** — documented breaking changes in minor releases, Stainless SDK pattern familiar to depfix
3. **Plaid** — lower volume but highest breaking-change frequency, financial domain makes fixes high-stakes

---

*Verification commands:*
```bash
curl -s -o /dev/null -w "%{http_code}" "https://raw.githubusercontent.com/resend/resend-openapi/main/resend.yaml"
curl -s -o /dev/null -w "%{http_code}" "https://raw.githubusercontent.com/cloudflare/api-schemas/main/openapi.yaml"
curl -s -o /dev/null -w "%{http_code}" "https://raw.githubusercontent.com/plaid/plaid-openapi/master/2020-09-14.yml"
curl -s "https://api.npmjs.org/downloads/point/last-month/resend"
curl -s "https://api.npmjs.org/downloads/point/last-month/cloudflare"
curl -s "https://api.npmjs.org/downloads/point/last-month/plaid"
```
