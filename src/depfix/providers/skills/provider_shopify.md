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
```python
import shopify
from shopify import Session
from shopify import Product
```

## Call sites (report these)

### SDK initialization — config changes across major versions
- `shopifyApi({ apiVersion: ApiVersion.October22 })` — removed in v13 (any pre-2024-10 enum)
- `shopifyApi({ apiVersion: '2022-10' })` — sunset API version as string literal
- `shopifyApi({ ..., customShopDomains: [...] })` — `customShopDomains` removed in v13

### Removed ApiVersion enum values (v13.0.0)
- `ApiVersion.October22`, `ApiVersion.January23`, `ApiVersion.April23`, `ApiVersion.July23`
- `ApiVersion.October23`, `ApiVersion.January24`, `ApiVersion.April24`, `ApiVersion.July24`

### Webhooks — broke in v13 and v14
- Webhook handler with `subTopic` as 6th param — removed in v14
- `const { eventId, resourceId } = await shopify.webhooks.validate(...)` — fields removed in v15
- `shopify.webhooks.addHandlers({ ..., callback: async (topic, shop, body, webhookId, apiVersion, subTopic) => ... })`

### REST resources
- `const { Product } = shopify.rest` — REST resource access pattern
- `new shopify.rest.Product()` — Python REST resource instantiation

## Where to look first
1. `grep("@shopify/shopify-api", "package.json")` — exact package name.
2. `grep("shopifyApi({", "**/*.ts")` — init call with config object.
3. `grep("ApiVersion\.", "**/*.ts")` — enum value usage for API version.
4. Webhook handlers: functions with `subTopic` as 6th param.
5. Python: `grep("import shopify", "**/*.py")` or `grep("ShopifyAPI", "requirements.txt")`.

## Breaking-change context

### v15.0.0 (2026-09-17) — events webhook delivery fields removed
- `eventId` and `resourceId` removed from events webhook delivery types
- `shopify-event-id` and `shopify-resource-id` headers no longer read

### v14.0.0 (2026-08-10) — Node.js 20→22, subTopic removed
- Node.js minimum raised from 20 to 22
- `subTopic` param removed from all webhook handlers (was deprecated since API `2024-04`)
- `ResponseErrors.graphQLErrors` typed `any[]` → `GraphQLError[]`
- `RequestOptions` fields made `readonly`

### v13.0.0 (2026-03-11) — API version enum pruning + webhook restructure
- `customShopDomains` config param removed (use `domainTransformations`)
- `SHOP_CUSTOM_DOMAIN` env var support dropped
- API version enum values for 2022-10 through 2024-07 removed
- `WebhookFields` refactored to discriminated union on `webhookType` (no longer has `webhookId` field)

### Admin API quarterly version sunsets
Shopify uses quarterly dated API versions (`2024-01`, `2024-07`, `2025-01`, …). Versions are
sunset after ~1 year. When a version is sunset, the SDK removes the corresponding `ApiVersion`
enum value in the next major release. Codebases hardcoding old enum values get TypeScript compile
errors on SDK upgrade.

## Anchors (fallback signals)
- Env vars: `SHOPIFY_API_KEY`, `SHOPIFY_API_SECRET`, `SHOPIFY_APP_URL`
- Config patterns: `shopifyApi({`, `apiVersion:`, `ApiVersion.`
- Shop domain patterns: `*.myshopify.com`
