# Plaid Provider Implementation Spec

**Status:** Ready for implementer  
**Date:** 2026-10-06  
**Researcher:** researcher agent  
**Source tasks:** T-7 (provider candidates), T-8 (priority ranking)  
**Priority:** #6 overall by volume / #1 by breaking-change frequency (8–12 major bumps/year)

---

## Overview

Plaid is the dominant financial data API for consumer fintech. Codebases using Plaid connect bank accounts, retrieve transactions, verify identity, and move money. The SDK is **auto-generated monthly from an OpenAPI spec** — each generation that includes breaking changes results in a new major version.

| Field | Value |
|---|---|
| npm package | `plaid` |
| pypi package | `plaid-python` |
| rubygems gem | `plaid` |
| npm downloads/month | **4,701,373** (verified 2026-10-04) |
| rubygems total downloads | **24,742,704** |
| npm latest | v47.0.0 |
| pypi latest | v45.0.0 |
| rubygems latest | v52.0.0 |
| OpenAPI spec | `https://raw.githubusercontent.com/plaid/plaid-openapi/master/2020-09-14.yml` |
| Spec OpenAPI version | 3.0.0 |
| Spec URL status | **200 OK** (verified 2026-10-06) |
| API base URLs | `https://production.plaid.com`, `https://sandbox.plaid.com` |
| API version header | `Plaid-Version: 2020-09-14` (fixed, date-based — not bumped per release) |
| GitHub SDK repos | plaid/plaid-node, plaid/plaid-python, plaid/plaid-ruby |
| api_version_scheme | `semver` (SDK versions are semver; the API date header never changes) |

---

## The Plaid versioning model (critical for depfix)

Plaid's API has **two independent version dimensions:**

1. **API date version** (`2020-09-14`) — the request header `Plaid-Version`. This is fixed across all current SDKs and never changes. It is not detected by drift detection.

2. **SDK version** (v47, v45, v52...) — true semver. Each major version bump corresponds to a breaking change in the generated SDK (removed endpoints, renamed types, changed field nullability, enum value renames). The SDK generates a new major every ~1–4 weeks when the OpenAPI spec has breaking changes.

**Why this matters for depfix:** `api_version_scheme: semver` is correct. The SDK version is the actionable signal. depfix should watch `npm_dist_tag` + `pypi_dist_tag` + `rubygems_dist_tag` for major bumps, plus `github_release` for changelog-based `[BREAKING]` annotations.

The `ts_exports_diff` feed also applies: removed endpoints appear as removed TypeScript exports (`linkDeliveryCreate`, `linkDeliveryGet`, etc.).

---

## providers.yaml entry

Add after the `astro` entry (currently the last entry):

```yaml
- id: plaid
  name: Plaid
  api_version_scheme: semver
  api_base_urls:
  - https://production.plaid.com
  - https://sandbox.plaid.com
  sdk_packages:
  - name: plaid
    ecosystem: npm
  - name: plaid-python
    ecosystem: pypi
  - name: plaid
    ecosystem: rubygems
  feeds:
  - kind: npm_dist_tag
    package: plaid
    dist_tag: latest
    github_repo: plaid/plaid-node
  - kind: pypi_dist_tag
    package: plaid-python
    github_repo: plaid/plaid-python
  - kind: rubygems_dist_tag
    gem: plaid
    github_repo: plaid/plaid-ruby
  - kind: github_release
    repo: plaid/plaid-node
  - kind: github_release
    repo: plaid/plaid-python
  - kind: openapi_spec
    url: https://raw.githubusercontent.com/plaid/plaid-openapi/master/2020-09-14.yml
  - kind: security_advisory
    package: plaid
    ecosystem: npm
  - kind: security_advisory
    package: plaid-python
    ecosystem: pypi
  - kind: ts_exports_diff
    package: plaid
```

---

## Skill file: src/depfix/providers/skills/provider_plaid.md

```markdown
# Plaid scan skill

## SDK packages
- npm: `plaid`
- pypi: `plaid-python`
- rubygems: `plaid`

## Import shapes to look for

### JavaScript / TypeScript
```
import { Configuration, PlaidApi, PlaidEnvironments } from 'plaid'
const { Configuration, PlaidApi, PlaidEnvironments } = require('plaid')
import { PlaidApi } from 'plaid'
```

Client construction:
```typescript
const configuration = new Configuration({
  basePath: PlaidEnvironments.production,
  baseOptions: {
    headers: {
      'PLAID-CLIENT-ID': CLIENT_ID,
      'PLAID-SECRET': SECRET,
    },
  },
});
const client = new PlaidApi(configuration);
```

### Python
```python
import plaid
from plaid.api import plaid_api
from plaid.model.<ModelName> import <ModelName>

configuration = plaid.Configuration(
    host=plaid.Environment.Production,
    api_key={
        'clientId': client_id,
        'secret': secret,
    }
)
api_client = plaid.ApiClient(configuration)
client = plaid_api.PlaidApi(api_client)
```

### Ruby
```ruby
require 'plaid'
configuration = Plaid::Configuration.new
api_client = Plaid::ApiClient.new(configuration)
client = Plaid::PlaidApi.new(api_client)
```

## Call sites to look for

### Authentication & Item management
- `client.linkTokenCreate(...)` / `client.link_token_create(...)` — Link token creation (most common)
- `client.itemPublicTokenExchange(...)` / `client.item_public_token_exchange(...)` — exchange Link token for access token
- `client.itemGet(...)` / `client.item_get(...)`
- `client.itemRemove(...)` / `client.item_remove(...)`

### Transactions (highest usage product)
- `client.transactionsGet(...)` / `client.transactions_get(...)` — legacy transactions endpoint
- `client.transactionsSync(...)` / `client.transactions_sync(...)` — modern sync endpoint
- `client.transactionsEnrich(...)` / `client.transactions_enrich(...)`

### Auth & Account data
- `client.authGet(...)` / `client.auth_get(...)` — bank account numbers
- `client.accountsGet(...)` / `client.accounts_get(...)` — account balances
- `client.accountsBalanceGet(...)` / `client.accounts_balance_get(...)`

### Identity & Verification
- `client.identityGet(...)` / `client.identity_get(...)`
- `client.identityVerificationCreate(...)` / `client.identity_verification_create(...)`

### Payments & Transfer
- `client.transferCreate(...)` / `client.transfer_create(...)`
- `client.transferAuthorizationCreate(...)` / `client.transfer_authorization_create(...)`
- `client.processorTokenCreate(...)` / `client.processor_token_create(...)`

## Where to look first
1. `grep("PLAID_CLIENT_ID", "")` or `grep("PLAID_SECRET", "")` — the canonical env vars.
2. `grep("plaid", "package.json")` or `grep("plaid-python", "requirements.txt")`.
3. Link integration entry points: look for files containing `PlaidLink`, `usePlaidLink`, or `onSuccess`.
4. In Python: `from plaid.api import plaid_api` or `from plaid.model.` — the generated model imports.
5. In Ruby: `require 'plaid'` followed by `Plaid::PlaidApi.new(...)`.

## Breaking-change context

### The Plaid versioning model
The Plaid SDK is **auto-generated from an OpenAPI spec** on a monthly cadence. Each time the
underlying API schema has breaking changes, the SDK ships a new major version. Breaking changes
arrive as: removed endpoints, renamed enum values, changed field nullability (especially TypeScript),
and added required fields.

The API date header (`Plaid-Version: 2020-09-14`) is **fixed** — all SDK versions above v10 use
this same date. The SDK version (not the date) is the semver signal.

### v48.0.0 (npm) / v45.0.0 (pypi) — OAS 2020-09-14_1.762.0
- **[BREAKING]** Remove `/link_delivery/create` and `/link_delivery/get`. `linkDeliveryCreate` /
  `link_delivery_create` and `linkDeliveryGet` / `link_delivery_get` removed from client.
  Replacement: `/link/token/create` with `hosted_link`.
- **[BREAKING]** Remove `charge card` and `installment` account subtype enum values.
  Remove `fund fee`, `loan payment`, `rebalance` investment transaction subtype enum values.
- **[BREAKING]** `CHECK_REPORT_FAILED` and `USER_CHECK_REPORT_FAILED` webhook models now require
  `error`, `repairable_items`, `failed_products` — empty lists returned as `[]`, not omitted.
- **[BREAKING for TypeScript]** `street` on `AddressData` (and variants) now permits `null`.
  Previously typed as `string`; now `string | null`. TypeScript codebases will get compile errors.

### v47.0.0 (npm) — OAS 2020-09-14_1.740.1
- **[BREAKING]** `/processor/token/create`: `paynote` enum value → `seamlessach`.
- **[BREAKING]** `/protect/compute`: generic model names removed; use client-scoped models.
- **[BREAKING]** `/protect/cash_advance/decision/create`: `is_taken` moves from nested
  `cash_advance` object to top-level request; `cash_advance` schema renamed; new required fields.
- **[BREAKING]** `/protect/event/send`: `protect_session_id` → `device_session_id`.

### v44.0.0 (npm) — OAS 2020-09-14_1.706.1
- **[BREAKING]** Multiple CRA schema interface replacements (`CraCheckReportCreate*Options` replaces
  separate per-product options interfaces).
- **[BREAKING]** `ProductsTerminateReasonCode` unified; `ItemProductsTerminateReasonCode` and
  `UserProductsTerminateReasonCode` removed.
- **[BREAKING]** Several models gained required fields (`BankTransferEvent.receiver_details`,
  `CreditSessionDocumentIncomeResult.num_i20s_uploaded`, etc.).
- **[BREAKING]** `StudentRepaymentPlanType.InterestOnly` serialization: `"interest-only"` → `"interest only"`.

### v43.0.0 (npm) — OAS 2020-09-14_1.698.7
- **[BREAKING]** Remove `/item/handle_fraud_report` endpoint and models (was never wired up).
- **[BREAKING]** `Recaptcha_RequiredError.http_code`: `string` → `integer`.
- **[BREAKING]** `/cra/check_report/verification/pdf/get`: `report_requested` → `reports_requested` array.
- **[BREAKING]** Remove `protect_results` from `LinkSessionResults`.

### v42.0.0 (npm) — OAS 2020-09-14_1.686.0
- **[BREAKING]** Remove deprecated `recurrence` field from `Enrichments` in `/transactions/enrich` response.
- **[BREAKING]** Investment account responses now use `InvestmentAccount` instead of `AccountBase`.
- **[BREAKING]** `CraPartnerInsightsPrism` is now nullable.

### Historical pattern (pre-v40)
- Earlier major versions removed entire product endpoints as products graduated from beta or sunset.
- The `plaidClient` class was renamed to `PlaidApi` in a major version (v9→v10 region).
- Python: before v9.0.0, the package was a completely different client with `plaid.Client(...)` construction.

## Anchors (fallback signals)
- Headers: `PLAID-CLIENT-ID`, `PLAID-SECRET`, `Plaid-Version`
- Env vars: `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV`
- SDK pattern: `from plaid.model.` (Python) — highly specific to plaid-python
- TypeScript: `PlaidEnvironments.production`, `PlaidEnvironments.sandbox`
```

---

## Known breaking changes summary

| SDK version | Date approx | Scope | Key breaks |
|---|---|---|---|
| v48.0.0 (npm) | 2026-09 | Link + CRA | Remove `linkDeliveryCreate`/`linkDeliveryGet`; enum removals; TypeScript `street` nullable |
| v47.0.0 (npm) | 2026-08 | Protect | `paynote`→`seamlessach`; `is_taken` moved to top-level; `protect_session_id`→`device_session_id` |
| v44.0.0 (npm) | 2026-06 | CRA | Interface replacements; unified enum; new required fields; `"interest-only"` → `"interest only"` |
| v43.0.0 (npm) | 2026-05 | Core | Remove `/item/handle_fraud_report`; field type `string`→`integer`; field rename/arrayification |
| v42.0.0 (npm) | 2026-04 | Transactions, Investments | Remove `recurrence` field; `AccountBase`→`InvestmentAccount` in investment responses |
| v9.0.0→v10.0.0 | ~2021 | All | Full SDK regeneration — `new plaid.Client(...)` → `new PlaidApi(configuration)` |

---

## Seed repo recommendation

Create `bedilk/seed-plaid` with:

```typescript
// src/plaid-client.ts
import { Configuration, PlaidApi, PlaidEnvironments } from 'plaid';
import {
  LinkTokenCreateRequest,
  Products,
  CountryCode,
  ItemPublicTokenExchangeRequest,
  TransactionsGetRequest,
} from 'plaid';

const configuration = new Configuration({
  basePath: PlaidEnvironments.sandbox,
  baseOptions: {
    headers: {
      'PLAID-CLIENT-ID': process.env.PLAID_CLIENT_ID,
      'PLAID-SECRET': process.env.PLAID_SECRET,
    },
  },
});

const client = new PlaidApi(configuration);

export async function createLinkToken(userId: string) {
  const request: LinkTokenCreateRequest = {
    user: { client_user_id: userId },
    client_name: 'My App',
    products: [Products.Transactions],
    country_codes: [CountryCode.Us],
    language: 'en',
  };
  return client.linkTokenCreate(request);
}

export async function exchangeToken(publicToken: string) {
  const request: ItemPublicTokenExchangeRequest = {
    public_token: publicToken,
  };
  return client.itemPublicTokenExchange(request);
}

export async function getTransactions(accessToken: string) {
  const request: TransactionsGetRequest = {
    access_token: accessToken,
    start_date: '2024-01-01',
    end_date: '2024-12-31',
  };
  return client.transactionsGet(request);
}
```

```json
// package.json: "plaid": "^43.0.0"   (5 major versions behind current v48)
```

Expected scan output: 3 call-sites (`linkTokenCreate`, `itemPublicTokenExchange`, `transactionsGet`), drift v43→v48 detected (multi-major), plan generated listing all 5 breaking-change versions between them.

---

## Implementation checklist for implementer

1. **Add providers.yaml entry** — paste the YAML block above at the end (after `astro`; or after the cloudflare/datadog entries if those were already added)
2. **Create skill file** — `src/depfix/providers/skills/provider_plaid.md` from the template above
3. **Update provider count test** — `tests/unit/test_provider_loader.py` has `assert len(enabled) == N`; increment N by 1
4. **Verify OpenAPI spec URL** — `curl -s -o /dev/null -w "%{http_code}" "https://raw.githubusercontent.com/plaid/plaid-openapi/master/2020-09-14.yml"` should return `200`
5. **Run make test** — must pass (unit tests, no LLM)
6. **Optionally create seed repo** — `bedilk/seed-plaid` with the above fixture

---

## Verification commands

```bash
# Verify OpenAPI spec URL
curl -s -o /dev/null -w "%{http_code}" \
  "https://raw.githubusercontent.com/plaid/plaid-openapi/master/2020-09-14.yml"
# Expected: 200

# Check npm downloads/month
curl -s "https://api.npmjs.org/downloads/point/last-month/plaid"
# Expected: {"downloads":~4701373,...}

# Check npm latest version
curl -s "https://registry.npmjs.org/plaid/latest" | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['version'])"
# Expected: 47.0.0 (or newer)

# Check pypi latest version
curl -s "https://pypi.org/pypi/plaid-python/json" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(d['info']['version'])"
# Expected: 45.0.0 (or newer)

# Check rubygems latest version
curl -s "https://rubygems.org/api/v1/gems/plaid.json" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(d['version'])"
# Expected: 52.0.0 (or newer)

# After adding to providers.yaml, smoke test:
bash scripts/test_pipeline.sh plaid:bedilk/seed-plaid
```

---

## Why Plaid next (after resend, cloudflare, datadog)

1. **Highest break frequency**: ~1 new major SDK version per month (v43→v48 in 5 months). No other provider on the list comes close.
2. **Financial domain**: Each breaking change in a Plaid integration can prevent users from accessing their bank accounts. The stakes per breaking change are unusually high.
3. **OpenAPI spec**: Auto-generated SDKs from a maintained OpenAPI spec at a stable URL. Easy to wire up `openapi_spec` feed.
4. **Ruby coverage**: The `plaid` gem at v52.0.0 has 24.7M total downloads — the most Ruby-relevant provider not yet in providers.yaml.
5. **Cross-ecosystem**: npm (`plaid`), pypi (`plaid-python`), rubygems (`plaid`) all maintained by Plaid official. Three ecosystems in one entry.
6. **High enterprise usage**: Every consumer fintech startup (Robinhood, Venmo competitors, budgeting apps, lending platforms) uses Plaid. Broad reach.

---

*All URLs verified 2026-10-06. OpenAPI spec at OpenAPI 3.0.0 with full Plaid REST API coverage. SDK is OpenAPI-generated (not Stainless); ts_exports_diff applies for removed endpoint detection. Breaking change data verified against CHANGELOG.md in plaid/plaid-node and plaid/plaid-python.*
