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

### v48.0.0 (npm) — Remove linkDelivery + enum removals + TypeScript nullable
- **[BREAKING]** Remove `/link_delivery/create` and `/link_delivery/get`. `linkDeliveryCreate` /
  `link_delivery_create` and `linkDeliveryGet` / `link_delivery_get` removed from client.
  Replacement: `/link/token/create` with `hosted_link`.
- **[BREAKING]** Remove `charge card` and `installment` account subtype enum values.
- **[BREAKING for TypeScript]** `street` on `AddressData` now permits `null` (was `string`).

### v47.0.0 (npm) — Protect API renames
- **[BREAKING]** `paynote` enum value → `seamlessach` for `/processor/token/create`.
- **[BREAKING]** `is_taken` moves from nested `cash_advance` to top-level in protect endpoint.
- **[BREAKING]** `protect_session_id` → `device_session_id`.

### v44.0.0 (npm) — CRA interface replacements
- **[BREAKING]** `CraCheckReportCreate*Options` replaces separate per-product options interfaces.
- **[BREAKING]** `ProductsTerminateReasonCode` unified; sub-type enums removed.
- **[BREAKING]** `StudentRepaymentPlanType.InterestOnly` serialization: `"interest-only"` → `"interest only"`.

### v43.0.0 (npm) — Core removals
- **[BREAKING]** Remove `/item/handle_fraud_report` endpoint and models.
- **[BREAKING]** `Recaptcha_RequiredError.http_code`: `string` → `integer`.
- **[BREAKING]** `/cra/check_report/verification/pdf/get`: `report_requested` → `reports_requested` array.

### v42.0.0 (npm) — Transactions / Investments
- **[BREAKING]** Remove deprecated `recurrence` field from `Enrichments`.
- **[BREAKING]** Investment account responses use `InvestmentAccount` instead of `AccountBase`.

### v9.0.0→v10.0.0 — Full SDK regeneration (historical)
- `new plaid.Client(...)` → `new PlaidApi(configuration)` — complete rewrite.

## Anchors (fallback signals)
- Headers: `PLAID-CLIENT-ID`, `PLAID-SECRET`, `Plaid-Version`
- Env vars: `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV`
- SDK pattern: `from plaid.model.` (Python) — highly specific to plaid-python
- TypeScript: `PlaidEnvironments.production`, `PlaidEnvironments.sandbox`
