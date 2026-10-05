# Shopify Provider Implementation Spec

**Status:** Ready for implementer  
**Date:** 2026-10-06  
**Researcher:** researcher agent  
**Source tasks:** T-8 (priority ranking — #10 candidate by breakage), proactive work round 12  
**Priority:** ~2.5M npm downloads/month for `@shopify/shopify-api`; 3 major versions shipped in 2026 alone (~6/year); the most break-heavy SDK depfix doesn't yet cover in the e-commerce space

---

## Overview

Shopify is the world's largest e-commerce platform. The official `@shopify/shopify-api` npm package powers authentication, webhook validation, API client construction, and session management for Shopify App partners. The underlying Admin API uses **quarterly dated versioning** (YYYY-MM, e.g. `2024-01`, `2024-07`) — Shopify sunsets API versions after ~1 year, forcing apps to bump their `apiVersion` config. Independently, the SDK itself uses SemVer and has shipped 3 major breaking versions in 2026 alone, each removing deprecated features, raising Node.js minimums, and restructuring webhook handling types.

| Field | Value |
|---|---|
| npm package | `@shopify/shopify-api` |
| pypi package | `ShopifyAPI` |
| npm downloads/month | **2,491,984** (`@shopify/shopify-api`); 2,657,446 (`@shopify/admin-api-client`) |
| pypi downloads/month | ~761,774 (`ShopifyAPI`) |
| npm latest | 15.0.0 (2026-09-17) |
| pypi latest | 12.7.0 |
| OpenAPI spec | None public |
| GitHub SDK repo | Shopify/shopify-app-js (monorepo) |
| GitHub Python repo | Shopify/shopify_python_api |
| api_version_scheme | `semver` (SDK uses SemVer; Admin API dated versions are a config param inside the SDK) |
| Feed types | `ts_exports_diff`, `github_release` |

---

## Breaking change history (SDK — `@shopify/shopify-api`)

Confirmed from GitHub releases in `Shopify/shopify-app-js`:

| Version | Date | Breaking changes |
|---|---|---|
| v15.0.0 | 2026-09-17 | `eventId` and `resourceId` removed from events webhook delivery types; `shopify-event-id`/`shopify-resource-id` headers no longer read |
| v14.0.0 | 2026-08-10 | Node.js minimum raised 20→22; `subTopic` param removed from all webhook handlers (deprecated since API `2024-04`, removed in `2024-07`); `ResponseErrors.graphQLErrors` typed `any[]`→`GraphQLError[]`; `RequestOptions` fields made `readonly` |
| v13.0.0 | 2026-03-11 | `customShopDomains` config param removed (use `domainTransformations`); `SHOP_CUSTOM_DOMAIN` env var support dropped; API version enum values for 2022-10 through 2024-07 removed; `WebhookFields` refactored to discriminated union on `webhookType` (no longer has a single `webhookId` field) |
| v12.0.0 | 2025 | (prior major — not checked in this run) |
| v11.0.0 | 2025 | (prior major — not checked in this run) |

**Rate:** At least 3 major SDK versions in 2026, ~4–6 major versions/year. High break density relative to npm download volume.

---

## Admin API versioning note

Shopify's Admin API itself uses quarterly dated versions (`2024-01`, `2024-04`, `2024-07`, `2024-10`, `2025-01`, `2025-04`, …). Shopify sunsets each version approximately 1 year after release. Users set this via:

```typescript
shopifyApi({
  apiVersion: ApiVersion.January25,  // '2025-01'
  // ...
})
```

When an API version is sunset, the SDK *removes the enum value and REST resource directory* for that version (as happened in v13.0.0 for 2022-10 through 2024-07). This is a depfix-detectable pattern:
- The SDK ships a new major that drops old `ApiVersion` enum values
- Users referencing e.g. `ApiVersion.October22` get a TypeScript compile error
- depfix can detect the drift and generate a fix pointing to the current supported version

This is similar to the Stripe `api_version_pin` use case but surfaced through SDK enum values rather than a string literal.

---

## providers.yaml entry

Append after the `astro` entry (currently at line 878):

```yaml
- id: shopify
  name: Shopify API
  api_version_scheme: semver
  sdk_packages:
  - name: '@shopify/shopify-api'
    ecosystem: npm
  - name: ShopifyAPI
    ecosystem: pypi
  feeds:
  - kind: npm_dist_tag
    package: '@shopify/shopify-api'
    dist_tag: latest
    github_repo: Shopify/shopify-app-js
  - kind: pypi_dist_tag
    package: ShopifyAPI
    github_repo: Shopify/shopify_python_api
  - kind: github_release
    repo: Shopify/shopify-app-js
  - kind: security_advisory
    package: '@shopify/shopify-api'
    ecosystem: npm
  - kind: security_advisory
    package: ShopifyAPI
    ecosystem: pypi
  - kind: ts_exports_diff
    package: '@shopify/shopify-api'
```

---

## Skill file: src/depfix/providers/skills/provider_shopify.md

```markdown
# Shopify scan skill

## SDK packages
- npm: `@shopify/shopify-api`
- pypi: `ShopifyAPI`

## Import patterns

### JavaScript / TypeScript
```
import { shopifyApi, ApiVersion } from '@shopify/shopify-api'
const { shopifyApi } = require('@shopify/shopify-api')
import shopify from '@shopify/shopify-api'
```

### Python
```
import shopify
from shopify import Session
from shopify import Product
```

## Call sites (report these)

### SDK initialization — config changes across major versions
- `shopifyApi({ apiVersion: ..., customShopDomains: [...] })` — `customShopDomains` removed in v13, use `domainTransformations`
- `shopifyApi({ apiVersion: ApiVersion.October22 })` — enum values pre-2024-10 removed in v13
- `shopifyApi({ apiVersion: '2022-10' })` — string literal for a sunset API version

### Webhooks — broke in v13 and v14
- `async function handler(topic, shop, body, webhookId, apiVersion, subTopic)` — `subTopic` removed in v14
- `shopify.webhooks.validate({ rawBody, rawRequest })` — return type changed to discriminated union in v13
- `const { eventId, resourceId } = await shopify.webhooks.validate(...)` — fields removed from events deliveries in v15
- `shopify.webhooks.addHandlers({ ... handler: async (topic, shop, body, webhookId, apiVersion, subTopic) => ... })`

### API version enum (removed values in v13)
- `ApiVersion.October22`     — removed in v13
- `ApiVersion.January23`     — removed in v13
- `ApiVersion.April23`       — removed in v13
- `ApiVersion.July23`        — removed in v13
- `ApiVersion.October23`     — removed in v13
- `ApiVersion.January24`     — removed in v13
- `ApiVersion.April24`       — removed in v13 (deprecated in 2024-07 API)
- `ApiVersion.July24`        — removed in v13

### REST resources (deprecated pattern, still common in older apps)
- `const { Product } = shopify.rest` — REST resource access pattern
- `new session.ShopifyAPI.Product()` — Python REST resource instantiation

## Where to look first
1. `grep("@shopify/shopify-api", "package.json")` — exact package name.
2. `grep("shopifyApi({", "**/*.ts")` — init call with config object.
3. `grep("ApiVersion\.", "**/*.ts")` — enum value usage for API version.
4. Webhook handlers: functions with `subTopic` as 6th param.
5. Python: `grep("import shopify", "**/*.py")` or `grep("ShopifyAPI", "requirements.txt")`.
```

---

## Key scan patterns for implementer

The SDK init pattern `shopifyApi({...})` is the primary entry point. The config object contains:
- `apiVersion` — an `ApiVersion` enum value or YYYY-MM string literal
- `customShopDomains` — removed in v13 (replaced by `domainTransformations`)

Webhook handler signatures evolved across major versions:
```typescript
// v12 and earlier (6 params including subTopic)
handler: async (topic: string, shop: string, body: string, webhookId: string, apiVersion: string, subTopic: string) => void

// v13/v14 (subTopic removed — 5 params)
handler: async (topic: string, shop: string, body: string, webhookId: string, apiVersion: string) => void

// v13+ validate() return changed to discriminated union
const {topic, webhookType, webhookId} = await shopify.webhooks.validate(...)
// For events deliveries in v15: no eventId/resourceId fields
```

The Python library is simpler — it wraps the REST API directly. Python breaking changes are typically API version changes rather than deep structural SDK changes.

---

## Seed repo recommendation

Create `bedilk/seed-shopify` containing:

```typescript
// src/shopify.ts
import { shopifyApi, ApiVersion } from '@shopify/shopify-api';

const shopify = shopifyApi({
  apiKey: process.env.SHOPIFY_API_KEY!,
  apiSecretKey: process.env.SHOPIFY_API_SECRET!,
  scopes: ['read_products'],
  hostName: process.env.HOST!,
  apiVersion: ApiVersion.October23,          // removed in v13 → should be January25 or later
  customShopDomains: ['myshops.io'],         // removed in v13 → use domainTransformations
  isEmbeddedApp: true,
});

// Webhook handler with subTopic as 6th param (removed in v14)
shopify.webhooks.addHandlers({
  PRODUCTS_CREATE: {
    deliveryMethod: 'http',
    callbackUrl: '/webhooks',
    callback: async (
      topic: string,
      shop: string,
      body: string,
      webhookId: string,
      apiVersion: string,
      subTopic: string,          // ← removed in v14
    ) => {
      console.log(`SubTopic: ${subTopic}`);
    },
  },
});

// Event delivery reading eventId/resourceId (removed in v15)
shopify.webhooks.addHandlers({
  COLLECTIONS_UPDATE: {
    deliveryMethod: 'events',
    callbackUrl: '/events',
    callback: async (_topic, _shop, _body, _webhookId, _apiVersion) => {
      // eventId and resourceId are gone in v15
    },
  },
});
```

```
// package.json: "@shopify/shopify-api": "^12.0.0"  (intentionally behind v15)
```

Expected scan: 3 call-sites, drift v12→v15 detected, plan covers `ApiVersion.October23` removal + `customShopDomains` removal + `subTopic` parameter removal.

---

## Implementation checklist for implementer

1. **Add providers.yaml entry** — paste the YAML block above after the `astro` entry (line ~878–912)
2. **Create skill file** — `src/depfix/providers/skills/provider_shopify.md` from the template above
3. **Update test_provider_count** — increment N by 1 in tests/test_providers.py
4. **run make test** — must pass (unit tests, no LLM)
5. **Optionally create seed repo** — `bedilk/seed-shopify` with the above fixture

---

## Verification commands

```bash
# Confirm npm download volume
curl -s "https://api.npmjs.org/downloads/point/last-month/@shopify/shopify-api"
# Expected: {"downloads":~2491984,...}

# Confirm npm latest version
curl -s "https://registry.npmjs.org/@shopify/shopify-api/latest" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['version'])"
# Expected: 15.0.0 (or newer)

# Confirm pypi latest
curl -s "https://pypi.org/pypi/ShopifyAPI/json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['info']['version'])"
# Expected: 12.7.0 (or newer)

# Confirm GitHub repo and major releases
curl -s "https://api.github.com/repos/Shopify/shopify-app-js/releases?per_page=20" | python3 -c "
import sys, json
releases = json.load(sys.stdin)
major = [r for r in releases if '@shopify/shopify-api@' in r['tag_name'] and '.0.0' in r['tag_name']]
for r in major[:5]: print(f\"{r['tag_name']}: {r['published_at'][:10]}\")
"
# Expected: 15.0.0, 14.0.0, 13.0.0 listed

# After adding to providers.yaml, smoke test:
bash scripts/test_pipeline.sh shopify:bedilk/seed-shopify
```

---

## Feed notes (no public OpenAPI spec)

Shopify does **not** publish a public OpenAPI spec for the Admin API at a known stable URL. The developer docs at `shopify.dev` do not expose a machine-readable spec JSON. The `Shopify/shopify-api-specs` GitHub repo does not exist (404 confirmed).

The primary signals for breaking changes are:
1. **`ts_exports_diff`** — catches method/type renames, removed exports, function signature changes in the TypeScript SDK
2. **`github_release`** — the monorepo's releases have detailed `### Major Changes` sections with migration guides

The quarterly Admin API version sunsets are best tracked by watching `ApiVersion` enum value removals in `ts_exports_diff` output and the "Removed support for older API versions" section in release notes.

---

## Priority context

Shopify sits at the intersection of two high-value depfix use cases:
1. **High break rate**: 3 major SDK versions in 2026 (6 months), ~6/year — one of the highest rates of any major SDK
2. **Unique Admin API version pinning**: When apps hardcode `ApiVersion.October23` and that enum is removed, it causes a TypeScript compile error — a textbook depfix use case
3. **Large partner ecosystem**: 1M+ Shopify app developers who all depend on this SDK

Shopify is particularly valuable because the API version pin pattern (`ApiVersion.October23`) is visually similar to the Stripe dated version use case, but surfaced through TypeScript enum removals rather than string literals. This validates and extends the `api_version_pin` concept to enum-based versioning.

---

*Verified data:*
- *npm downloads: 2026-10-06 via npmjs.com API*
- *npm latest: 15.0.0 (2026-09-17)*
- *pypi latest: 12.7.0*
- *pypi downloads: ~761,774/month via pypistats.org*
- *Breaking change details: GitHub releases via api.github.com (v13–v15 confirmed)*
- *No public OpenAPI spec: confirmed 404 on Shopify/shopify-api-specs GitHub repo*
- *GitHub repo: git+https://github.com/Shopify/shopify-app-js.git (confirmed via npm registry metadata)*
