# Square Provider Implementation Spec

**Date:** 2026-10-06  
**Researcher:** researcher round 22  
**Priority:** High — payment SDK with highest per-version break frequency observed

---

## Package Facts

| Ecosystem | Package name | Module/import name | Latest version | Downloads/month |
|---|---|---|---|---|
| npm | `square` | `square` | 46.0.0 | ~1.5M |
| pypi | `squareup` | `square` | 46.0.0.20260916 | ~257K |
| Ruby | `square.rb` | `Square` | 47.0.0.20260916 | ~2M total |

**CRITICAL: Python package/module name mismatch.** Package is `squareup`, but it installs as the `square` module. Code uses `from square import Square`, not `from squareup import ...`. This is the same pattern as `sentry-sdk` → `sentry_sdk`. The scanner must recognize `square` in `from square import` as the `squareup` package.

**Why Square is high-value for depfix:**
- ~4-6 major version bumps per year (one per quarterly API version date)
- v40.0.0 (Jan 2025) was a complete SDK overhaul — every single call site changed
- Payment SDK: broken upgrades have direct revenue impact
- ~1.75M npm+pypi downloads/month with 3 ecosystems

---

## Version History (recent)

All major bumps map to Square's quarterly API version dates:

```
v40.0.0 — 2025-01-22 (MAJOR OVERHAUL: Fern migration)
v41.0.0 — 2025-02-20 (API 2025-02-20)
v42.0.0 — 2025-03-19 (API 2025-03-19)
v43.0.0 — 2025-06-18 (API 2025-06-18)
v44.0.0 — 2026-01-22 (API 2026-01-23)
v45.0.1 — 2026-07-14 (API 2026-07-15)
v46.0.0 — 2026-09-15 (API 2026-09-16)
```

~4 major versions/year = highest rate of any provider in depfix.

---

## Breaking Changes (documented)

### 1. v40.0.0 — Complete Fern SDK Migration (Jan 2025) — **HIGHEST IMPACT**

Source: Release notes + npm tarball inspection.

**THE single biggest change:** the entire SDK was regenerated with Fern. Every call site using the old SDK is broken on upgrade.

#### JavaScript/TypeScript

**Old SDK (pre-v40, now `square/legacy`):**
```typescript
import { Client } from 'square';
// OR
const { Client } = require('square');

const client = new Client({
  accessToken: process.env.SQUARE_ACCESS_TOKEN,
  environment: Environment.Sandbox,
});

// Sub-client access: camelCase + "Api" suffix
await client.paymentsApi.createPayment({ ... });
await client.customersApi.createCustomer({ ... });
await client.ordersApi.createOrder({ ... });
await client.catalogApi.upsertCatalogObject({ ... });
await client.inventoryApi.batchChangeInventory({ ... });
await client.invoicesApi.createInvoice({ ... });
await client.loyaltyApi.createLoyaltyAccount({ ... });
await client.locationCustomAttributesApi.listLocationCustomAttributeDefinitions();
await client.bookingCustomAttributesApi.listBookingCustomAttributeDefinitions();
await client.giftCardActivitiesApi.createGiftCardActivity({ ... });
```

**New SDK (v40+, from `square`):**
```typescript
import { SquareClient, SquareEnvironment } from 'square';

const client = new SquareClient({
  token: process.env.SQUARE_TOKEN,          // NOTE: accessToken → token
  environment: SquareEnvironment.Sandbox,   // NOTE: Environment → SquareEnvironment
});

// Sub-client access: NO "Api" suffix, different resource grouping
await client.payments.create({ ... });
await client.customers.create({ ... });
await client.orders.create({ ... });
await client.catalog.upsertObject({ ... });
await client.inventory.batchChange({ ... });
await client.invoices.create({ ... });
await client.loyalty.createAccount({ ... });
await client.locations.customAttributes.listDefinitions();  // nested!
await client.bookings.customAttributes.listDefinitions();   // nested!
await client.giftCards.activities.create({ ... });          // nested!
```

**Summary of v40 renames:**
| Old (pre-v40) | New (v40+) |
|---|---|
| `Client` (from `square`) | `SquareClient` (from `square`) |
| `Environment` | `SquareEnvironment` |
| `ApiError` | `SquareError` |
| `client.paymentsApi` | `client.payments` |
| `client.customersApi` | `client.customers` |
| `client.ordersApi` | `client.orders` |
| `client.catalogApi` | `client.catalog` |
| `client.inventoryApi` | `client.inventory` |
| `client.invoicesApi` | `client.invoices` |
| `client.locationsApi` | `client.locations` |
| `client.loyaltyApi` | `client.loyalty` |
| `client.subscriptionsApi` | `client.subscriptions` |
| `client.teamApi` | `client.team` |
| `client.terminalApi` | `client.terminal` |
| `client.checkoutApi` | `client.checkout` |
| `client.giftCardActivitiesApi` | `client.giftCards.activities` |
| `client.locationCustomAttributesApi` | `client.locations.customAttributes` |
| `client.bookingCustomAttributesApi` | `client.bookings.customAttributes` |
| `new Client({ accessToken })` | `new SquareClient({ token })` |

**Legacy path available:** `import { Client } from 'square/legacy'` preserves the old API.
Code using `import { Client } from 'square'` (without `/legacy`) gets the new `SquareClient`-style package but `Client` is not exported — it will be `undefined`. This is a silent runtime error.

#### Python

**Old Python SDK (pre-v40):**
```python
from square.client import Client

client = Client(
    access_token=os.environ['SQUARE_ACCESS_TOKEN'],
    environment='sandbox'
)
# Sub-clients: snake_case + "_api" suffix
client.payments_api.create_payment({ ... })
client.customers_api.create_customer({ ... })
client.orders_api.create_order({ ... })
```

**New Python SDK (v40+):**
```python
from square import Square

client = Square(
    token=os.environ.get("SQUARE_TOKEN"),   # NOTE: access_token → token
)
# Sub-clients: NO "_api" suffix
client.payments.create({ ... })
client.customers.create({ ... })
client.orders.create({ ... })
```

**Summary of Python v40 renames:**
| Old (pre-v40) | New (v40+) |
|---|---|
| `from square.client import Client` | `from square import Square` |
| `Client(access_token=...)` | `Square(token=...)` |
| `client.payments_api` | `client.payments` |
| `client.customers_api` | `client.customers` |
| `client.orders_api` | `client.orders` |
| `client.catalog_api` | `client.catalog` |
| `client.inventory_api` | `client.inventory` |

---

### 2. v15.0.0 — Transactions API Removed (Oct 2021)

Source: CHANGELOG.md (from v39.1.1 tag).

Three endpoints permanently removed for API version 2021-10-20+:

| Removed endpoint | Replacement |
|---|---|
| `transactionsApi.charge()` | `paymentsApi.createPayment()` |
| `transactionsApi.createRefund()` | `refundsApi.refundPayment()` |
| `transactionsApi.listRefunds()` | `refundsApi.listPaymentRefunds()` |

Old code still works with Square API versions prior to 2021-10-20 but any new app using the default (latest) API version will get 404s.

---

### 3. Quarterly API Version Breaking Changes

Each major SDK version bump corresponds to a new Square API version date (e.g., 2026-09-16). Each release may include:
- Endpoint retirements (fields marked GA then removed in subsequent cycles)
- Enum value additions that break exhaustive switches
- Response body schema changes

Square's developer changelog for each release: `https://developer.squareup.com/docs/changelog/connect-logs/<YYYY-MM-DD>`

Examples:
- API 2025-09-24: Various field removals in Orders API
- API 2026-07-15: LaborShift changes (see changelog)
- API 2026-09-16: Most recent — details at `https://developer.squareup.com/docs/changelog/connect-logs/2026-09-16`

---

## providers.yaml Entry

```yaml
- name: Square
  api_version_scheme: semver
  api_base_urls:
  - https://connect.squareup.com
  sdk_packages:
  - name: square
    ecosystem: npm
  - name: squareup
    ecosystem: pypi
    import_name: square          # IMPORTANT: package=squareup, module=square
  - name: square.rb
    ecosystem: rubygems
  feeds:
  - kind: npm_dist_tag
    package: square
    dist_tag: latest
    github_repo: square/square-nodejs-sdk
  - kind: pypi_dist_tag
    package: squareup
    github_repo: square/square-python-sdk
  - kind: github_release
    repo: square/square-nodejs-sdk
  breaking_changes:
  - version: "40.0.0"
    title: "Fern SDK migration: Client → SquareClient, accessToken → token, *Api → *"
    description: >
      Complete SDK overhaul. SquareClient replaces Client. All sub-client
      properties lose the 'Api' suffix (paymentsApi → payments). Constructor
      parameter accessToken renamed to token. Legacy path available at
      'square/legacy' for gradual migration.
    classification_source: ts_exports_diff
    symbols:
    - Client                    # removed from main export, now only in square/legacy
    - Environment               # removed, replaced by SquareEnvironment
    - ApiError                  # removed, replaced by SquareError
    - "*.paymentsApi"           # removed, replaced by *.payments
    - "*.customersApi"          # removed, replaced by *.customers
    - "*.ordersApi"             # removed, replaced by *.orders
    ecosystem: [npm, pypi, rubygems]
    report_only: false
  - version: "15.0.0"
    title: "Transactions API endpoints removed (Charge, CreateRefund, ListRefunds)"
    classification_source: github_release
    symbols:
    - "transactionsApi.charge"
    - "transactionsApi.createRefund"
    - "transactionsApi.listRefunds"
    ecosystem: [npm, pypi, rubygems]
    report_only: false
```

---

## Skill File: `provider_square.md`

```markdown
# Square scan skill

## SDK packages
- npm: `square`
- pypi: `squareup` (imports as `square` module — NOT `squareup`)
- Ruby: `square.rb`

## ⚠️ Python import mismatch
Package name `squareup` ≠ module name `square`.
Code: `from square import Square` or `from square.client import Client`.
The scanner must map `squareup` → `square` for Python imports.

## Import patterns (new SDK, v40+)

### JavaScript/TypeScript
```
import { SquareClient } from 'square'
import { SquareClient, SquareEnvironment } from 'square'
const { SquareClient } = require('square')
```

### Python
```
from square import Square
from square.client import Client   # legacy (pre-v40)
import square
```

## Two SDK generations exist simultaneously

### Current (v40+): Fern-generated
```typescript
const client = new SquareClient({ token: accessToken });
client.payments.create(...)
client.customers.create(...)
client.orders.create(...)
```

### Legacy (pre-v40): `square/legacy`
```typescript
import { Client } from 'square/legacy';
const client = new Client({ accessToken });
client.paymentsApi.createPayment(...)
client.customersApi.createCustomer(...)
```

Code still importing `import { Client } from 'square'` (not `/legacy`) will get
`Client` as `undefined` — silent runtime failure on upgrade.

## Call sites
### v40+ (current)
- `new SquareClient({ token, environment })`
- `client.payments.create(...)`, `.list(...)`, `.get(...)`, `.cancel(...)`
- `client.customers.create(...)`, `.list(...)`, `.update(...)`
- `client.orders.create(...)`, `.retrieve(...)`, `.update(...)`
- `client.catalog.upsertObject(...)`, `.batchUpsert(...)`, `.listCatalog()`
- `client.inventory.batchChange(...)`, `.retrieveCount(...)`
- `client.team.listJobRoles(...)`, `client.teamMembers.create(...)`

### Pre-v40 legacy (flag these)
- `new Client({ accessToken, environment })`
- `client.paymentsApi.*`, `client.customersApi.*`, `client.ordersApi.*`
- `transactionsApi.charge(...)` — removed in v15; flag as REPORT_ONLY

## Where to look first
1. `grep('square', package.json)` — find the `square` package dependency
2. Entry point files: `app.js`, `server.js`, `routes/payment.js`, `lib/square.js`
3. Checkout/payment flows: look for `createPayment`, `createOrder`, `createCustomer`
4. Constructor patterns: `new SquareClient` or `new Client` with `accessToken`

## Version detection
- v40.0.0+: uses `SquareClient` from main `square` export
- pre-v40: uses `Client` from `square` (now `square/legacy`)
- v15.0.0+: `transactionsApi` methods are dead endpoints
```

---

## Seed Repo Fixture

No existing seed repo for Square. Suggested fixture path: `tests/fixtures/square_v39_project/`

Minimal fixture:
```
tests/fixtures/square_v39_project/
  package.json          # "square": "^39.1.1"
  src/payment.ts        # import { Client } from 'square'; new Client({ accessToken })
  src/customers.ts      # client.customersApi.createCustomer(...)
  src/orders.ts         # client.ordersApi.createOrder(...)
```

Expected scan output:
- 3 call sites detected
- Drift: 39.x → 46.0.0 (major)
- Actionable: yes (v40 migration)
- Symbols detected: `Client` (removed), `customersApi` (renamed), `ordersApi` (renamed)

---

## No Public OpenAPI Spec

Square uses Fern for SDK generation, but the source API definition is not publicly accessible. No OpenAPI spec URL returns 200 OK.

**Feeds to use:** `npm_dist_tag` + `pypi_dist_tag` + `github_release`. The `ts_exports_diff` feed is appropriate for the v40 Fern migration detection since the TypeScript exports changed completely (Client removed, SquareClient added).

---

## Implementer Checklist

1. **providers.yaml**: Add Square entry (template above). Note the `import_name: square` for pypi.
2. **Skill file**: Create `src/depfix/providers/skills/provider_square.md` (content above).
3. **Python scanner**: Confirm `_python_import_regexes("squareup")` generates patterns for both:
   - `from square import ...` (new SDK)
   - `from square.client import Client` (old SDK)
   - `import square`
4. **Provider count test**: Update test that checks provider count.
5. **Eval cases** (optional): Add 2-3 cases for v40 migration in a `square_v40_callsites.yaml`.

---

## Data Sources Verified

- npm registry: `curl https://registry.npmjs.org/square` ✅
- npm downloads: 1,526,415/month (registry.npmjs.org/downloads) ✅
- pypi downloads: 256,685/month (pypistats.org) ✅
- Ruby gem: 2,011,999 total (rubygems.org) ✅
- v40 release notes: "major overhaul of our SDK" (github.com/square/square-nodejs-sdk/releases) ✅
- v40 exports: extracted from `square-40.0.0.tgz` — `SquareClient` exported, `Client` not ✅
- v39 CHANGELOG.md: v15.0.0 Transactions API removal confirmed ✅
- Python SDK README: `from square import Square`, `Square(token=...)` ✅
