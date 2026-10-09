# Intercom Provider Implementation Spec

**Date**: 2026-10-09  
**Researcher**: researcher (claude-sonnet-4-6-1m)  
**Priority**: Medium-High — 9.2M combined npm/month (7.2M browser + 2M server)

---

## 1. Package inventory

| Package | Ecosystem | Latest | Downloads/month | Module import name |
|---------|-----------|--------|-----------------|-------------------|
| `intercom-client` | npm | 7.0.4 | ~2.0M | `Client` (v3–v5), `IntercomClient` (v6+) |
| `@intercom/messenger-js-sdk` | npm | 0.0.20 | ~7.2M | `Intercom`, `boot`, `shutdown`, etc. |
| `python-intercom` | pypi | 5.0.1 | ~249K | `intercom` |

**Note**: `@intercom/messenger-js-sdk` is still pre-1.0 (beta) — no major breaking changes yet;
all releases are 0.0.x. Depfix can watch it but skip it for fix generation until 1.0.

---

## 2. Feed strategy

No confirmed public OpenAPI spec. Recommended feeds:
- `npm_dist_tag` for `intercom-client` (primary)
- `github_release` from `https://github.com/intercom/intercom-node` (changelog)
- `pypi_dist_tag` for `python-intercom`
- `npm_dist_tag` for `@intercom/messenger-js-sdk` (watch-only until 1.0)

---

## 3. Breaking changes by version

### `intercom-client` — Server-side Node.js/TypeScript SDK

#### v2.x → v3.x (January 2022) — TypeScript rewrite

The SDK was rewritten in TypeScript. The import pattern changed fundamentally:

```js
// Before (v2)
const Intercom = require('intercom-client');
const client = new Intercom.Client({ token: 'my_token' });

// After (v3)
import { Client } from 'intercom-client';
const client = new Client({ tokenAuth: { token: 'my_token' } });
```

Depfix-detectable patterns:
- `Intercom.Client` → `{ Client }` from `intercom-client` (import restructure)
- `new Intercom.Client(...)` → `new Client(...)`

#### v5.x → v6.x (December 2024) — Fern-generated SDK rewrite

The highest-impact migration. Same pattern as Square v40 (Fern migration) and Cloudflare v3.

```ts
// Before (v3–v5)
import { Client } from 'intercom-client';
const client = new Client({ tokenAuth: { token: 'my_token' } });
client.useRequestOpts({ timeout: 5000 });  // Axios-style global config

// After (v6)
import { IntercomClient } from 'intercom-client';
const client = new IntercomClient({ token: 'my_token' });  // no tokenAuth wrapper
// Per-call options instead of global:
await client.contacts.find({ contact_id }, { timeoutInSeconds: 5 });
```

Key breaking changes in v6:
1. **`Client` → `IntercomClient`** — class rename, every instantiation breaks
2. **`{ tokenAuth: { token } }` → `{ token }`** — auth shape change, every constructor call breaks
3. **`client.useRequestOpts(...)` removed** — global Axios config replaced by per-call `RequestOptions`
4. **`IntercomError` is the new error class** — replaces generic errors
5. **Types namespace**: `import { Intercom } from "intercom-client"` (types-only namespace, separate from class)

Depfix-detectable call sites for v5→v6:
- `new Client({` → `new IntercomClient({`
- `.useRequestOpts(` — removed, no replacement (per-call options instead)
- `{ tokenAuth:` — constructor option removed

#### v6.x → v7.x (January 2026) — API v2.14

Fern regeneration only. No client-surface breaking changes. Method hierarchy unchanged.
`client.<resource>.<verb>()` pattern fully preserved.

### `python-intercom` — Python SDK

v3→v5 changes require separate investigation (no CHANGELOG found). Major releases on PyPI:
3.0, 4.0.0, 5.0.1. Import pattern: `from intercom.client import Client` (v3+).

```python
# Pattern (v3+)
from intercom.client import Client
client = Client(personal_access_token='my_token')
```

---

## 4. providers.yaml entry

```yaml
- id: intercom
  display_name: Intercom
  sdk_packages:
    - name: intercom-client
      ecosystem: npm
    - name: "@intercom/messenger-js-sdk"
      ecosystem: npm
    - name: python-intercom
      ecosystem: pypi
  feeds:
    - type: npm_dist_tag
      package: intercom-client
    - type: npm_dist_tag
      package: "@intercom/messenger-js-sdk"
    - type: pypi_dist_tag
      package: python-intercom
    - type: github_release
      repo: intercom/intercom-node
  breaking_changes:
    - package: intercom-client
      old_version: "5.0.0"
      new_version: "6.0.0"
      old_api: "intercom.Client"
      new_api: "intercom.IntercomClient"
      description: "Client class renamed to IntercomClient in the Fern-generated v6 rewrite"
      kind: class_renamed
      source: spec_diff
    - package: intercom-client
      old_version: "5.0.0"
      new_version: "6.0.0"
      old_api: "intercom.Client.useRequestOpts"
      new_api: ""
      description: "Client.useRequestOpts removed; use per-call RequestOptions instead"
      kind: method_removed
      source: spec_diff
```

---

## 5. Skill file outline (`provider_intercom.md`)

Key sections:
- **Identity**: `intercom-client` npm + `@intercom/messenger-js-sdk` + `python-intercom`
- **Import patterns**:
  - v3–v5: `import { Client } from 'intercom-client'` → `client.*`
  - v6+: `import { IntercomClient } from 'intercom-client'` → `client.*`
- **v5→v6 constructor migration**: remove `tokenAuth` wrapper, rename `Client` → `IntercomClient`
- **Removed APIs**: `useRequestOpts` (no equivalent, per-call options only)
- **Error handling**: `IntercomError` now from `intercom-client`, not generic Error

---

## 6. Eval cases (3 highest-value)

### Case 1: Client class rename (v5→v6)
```yaml
description: Client renamed to IntercomClient in v6 Fern rewrite
call_site: "new Client({ tokenAuth: { token: process.env.INTERCOM_TOKEN } })"
provider: intercom
old_version: "5.0.0"
new_version: "6.0.0"
old_api: "intercom.Client"
expected_fix: "new IntercomClient({ token: process.env.INTERCOM_TOKEN })"
```

### Case 2: useRequestOpts removal (v5→v6)
```yaml
description: client.useRequestOpts removed in v6; no direct replacement
call_site: "client.useRequestOpts({ timeout: 5000 })"
provider: intercom
old_api: "intercom.Client.useRequestOpts"
kind: REPORT_ONLY
```

### Case 3: Legacy require → named import (v2→v3)
```yaml
description: CJS require pattern replaced by named ESM import in v3 TypeScript rewrite
call_site: "const Intercom = require('intercom-client')"
provider: intercom
old_version: "2.0.0"
new_version: "3.0.0"
expected_fix: "import { Client } from 'intercom-client'"
```

---

## 7. Seed repo suggestion

`bedilk/seed-intercom-v5-to-v6` — a Node.js project with:
- `package.json`: `"intercom-client": "^5.0.0"`
- Source using old `Client` + `tokenAuth` constructor pattern
- Covers the high-value `Client` → `IntercomClient` migration

---

## 8. Implementation priority

**Recommended add order**: After okta and square (which have specs written but not implemented).
The 7.2M downloads/month on `@intercom/messenger-js-sdk` is notable but the package is pre-1.0 and stable — depfix value is medium until it hits 1.0 and breaking changes arrive.

The `intercom-client` v5→v6 Fern migration (same class as Square v40, Cloudflare v3) is the
high-value detection target: every `.Client` instantiation in user code breaks silently.

---

## 9. Implementer checklist

- [ ] Add providers.yaml entry (above YAML block)
- [ ] Create `src/depfix/providers/skills/provider_intercom.md`
- [ ] Update provider count assertion in `tests/unit/test_provider_loader.py`
- [ ] (Optional) Add 3 eval cases to `src/depfix/evals/corpus/intercom_callsites.yaml`
- [ ] Run `make test` — expect 0 failures
