# Auth0 Provider Implementation Spec

**Status:** Ready for implementer  
**Date:** 2026-10-06  
**Researcher:** researcher agent  
**Source tasks:** Proactive work round 20 (beyond T-8 top-10 + LaunchDarkly + Amplitude)  
**Priority:** ~28M npm/month total; Python 6.6M/month; auth is critical-path infrastructure with 5 major SDK versions in 4 years (3 in 2025–2026)

---

## Overview

Auth0 (acquired by Okta in 2021) is the dominant identity/authentication platform for web and mobile apps.
Its SDKs sit in critical-path code: every login, token verification, and user management call routes through them.

Auth0 ships major breaking changes rapidly — 5 major versions of the Node.js SDK in 4 years (v3 Dec 2022,
v4 Sep 2023, v5 Sep 2025, v6 Jul 2026, v7 Sep 2026) — and does so in minor versions too (v7.1.0 had
breaking changes 3 days after v7.0.0). The Python SDK mirrors this cadence.

depfix is especially valuable here because:
1. **High churn**: 5 major Node.js SDK versions in 4 years (avg > 1 major/year)
2. **Minor-version breaks**: v7.1.0 (Node), v2.25.0 (@auth0/auth0-spa-js), v5.2.0 / v5.5.0 / v5.7.0 / v5.8.0 (Python) all shipped breaking changes outside major bumps
3. **Authentication API removal** (v7): a single import `{ AuthenticationClient }` from `'auth0'` across thousands of apps
4. **Python runtime breaks**: Python 3.8 dropped in v5.2.0; Python 3.9 dropped in v5.5.0 — runtime failures on deploy, not at code time

---

## Download Counts (verified 2026-10-06)

| Package | Ecosystem | Monthly downloads | Latest version |
|---|---|---|---|
| `@auth0/auth0-spa-js` | npm | **9,732,694** | v2.28.2 |
| `auth0` | npm | **8,227,915** | v7.3.0 |
| `@auth0/auth0-react` | npm | **5,928,153** | v2.28.2 |
| `@auth0/nextjs-auth0` | npm | **3,423,071** | v4.x |
| `auth0-js` | npm | **962,429** | v9.x (legacy, deprecated) |
| `auth0-python` | pypi | **6,629,233** | v6.7.0 |

**Total npm/month (key packages):** ~28.3M  
**Combined npm + pypi/month:** ~34.9M

**Verification commands:**
```bash
curl -s "https://api.npmjs.org/downloads/point/last-month/auth0"
# {"downloads":8227915,...}

curl -s "https://api.npmjs.org/downloads/point/last-month/@auth0%2Fauth0-spa-js"
# {"downloads":9732694,...}

curl -s "https://pypistats.org/api/packages/auth0-python/recent"
# {"data":{"last_month":6629233,...}}
```

---

## SDK Package History and Version Scheme

### Node.js Management SDK (`auth0`)
| Version | Date | Key change |
|---|---|---|
| v2.x | 2016–2022 | Long-running legacy version |
| v3.0.0 | 2022-12-22 | ES modules + TypeScript rewrite |
| v4.0.0 | 2023-09-14 | Management API improvements |
| v5.0.0 | 2025-09-17 | Full Fern-generated rewrite; sub-client architecture; Node.js >=20.19 required |
| v6.0.0 | 2026-07-15 | Type splits (ConnectionAttributeIdentifier → 3 types); federatedConnectionsTokensets removed |
| v7.0.0 | 2026-09-09 | `AuthenticationClient` entirely removed from main entrypoint → `@auth0/auth0-auth-js` |
| v7.1.0 | 2026-09-11 | ⚠️ Breaking in minor: `organizationTemplates` sub-client removed; ConnectionStrategyEnum values renamed |

**Version scheme:** semver, but minor versions can contain breaking changes (documented; not rare)

### Node.js SPA SDK (`@auth0/auth0-spa-js`)
| Version | Date | Key change |
|---|---|---|
| v1.x | 2019–2022 | Initial SPA SDK |
| v2.0.0 | 2022-09 | Major rewrite; `getTokenSilently` API changed |
| v2.25.0 | 2026-09-14 | ⚠️ Breaking in minor: `getTokenSilently()` return type widened to `string \| undefined` |

### React SDK (`@auth0/auth0-react`)
Tracks `@auth0/auth0-spa-js`. v2.25.0 (2026-09-14) broke `getAccessTokenSilently()` return type to
`Promise<string \| undefined>`.

### Python SDK (`auth0-python`)
| Version | Date | Key change |
|---|---|---|
| v4.x | 2023–2025 | Previous stable |
| v5.0.0 | 2026-02-04 | Full Fern-generated rewrite; `Auth0` → hierarchical sub-clients |
| v5.2.0 | 2026-03-30 | ⚠️ Breaking in minor: Python 3.8 dropped (Python >=3.9.2 required) |
| v5.5.0 | 2026-05-20 | ⚠️ Breaking in minor: Python 3.9 dropped (Python >=3.10 required) |
| v5.7.0 | 2026-06-10 | ⚠️ Breaking in minor: `branding.update()` `identifiers` param removed |
| v5.8.0 | 2026-06-29 | ⚠️ Breaking in minor: `clients.update()` type change (`NativeSocialLogin` → `NativeSocialLoginPatch`) |
| v6.0.0 | 2026-07-15 | `ConnectionAttributeIdentifier` split into 3 types |
| v6.4.0 | 2026-09-02 | ⚠️ Breaking in minor: `app_type` `b2b_integration` removed |
| v6.5.0 | 2026-09-11 | ⚠️ Breaking in minor: organization_templates client removed; 9 provider enum values removed |
| v6.7.0 | 2026-09-30 | ⚠️ Breaking in minor: `management.organizations.organization_template` sub-client removed |

**Breaking changes per year (Node.js):** ~4–6 major + 2–4 minor-but-breaking  
**Breaking changes per year (Python):** similar cadence; minor-version breaks are frequent  

---

## Key Breaking Changes (Actionable for depfix)

### 1. AuthenticationClient removed — v7 (Node.js, 2026-09-09)

**This is the highest-impact single change across all 28M npm downloads/month.**

```typescript
// BEFORE (v4, v5, v6):
import { AuthenticationClient, ManagementClient } from 'auth0';
const auth = new AuthenticationClient({ domain, clientId, clientSecret });
const tokens = await auth.oauth.clientCredentialsGrant({ audience });

// AFTER (v7):
import { ManagementClient } from 'auth0';             // ManagementClient stays
import { AuthClient } from '@auth0/auth0-auth-js';    // NEW package
const auth = new AuthClient({ domain, clientId, clientSecret });
const tokens = await auth.getTokenByClientCredentials({ audience });
```

**Detection:** import of `{ AuthenticationClient }` from `'auth0'`  
**Fix classification:** `FUNCTION_RENAME` (AuthenticationClient → AuthClient in @auth0/auth0-auth-js) + package add  
**Impact:** Any server-side app doing OAuth flows with `auth0` v4/v5/v6 is broken on v7 upgrade

### 2. UserInfoClient removed — v7 (Node.js, 2026-09-09)

```typescript
// BEFORE (v6):
import { UserInfoClient } from 'auth0';
const userInfo = new UserInfoClient({ domain });
const profile = await userInfo.getUserInfo(accessToken);

// AFTER (v7):
import { AuthClient } from '@auth0/auth0-auth-js';
const auth = new AuthClient({ domain, clientId, clientSecret });
const profile = await auth.getUserInfo(accessToken);
```

**Detection:** import of `{ UserInfoClient }` from `'auth0'`  
**Fix classification:** `FUNCTION_RENAME`

### 3. getTokenSilently return type — v2.25.0 (spa-js, 2026-09-14)

```typescript
// BEFORE (v2.24.x): returns Promise<string>
const token: string = await getTokenSilently();
if (token.length > 0) { ... }   // safe

// AFTER (v2.25.0): returns Promise<string | undefined>
const token = await getTokenSilently();
// TS error if used directly as string without null check
```

**Detection:** call to `getTokenSilently()` without null guard  
**Fix classification:** `PARAMETER_REMOVED` (semantics change)  
**Note:** This is a TypeScript-only breaking change; runtime behavior is unchanged for callers that already handle errors.

### 4. Sub-client architecture migration — v4→v5 (Node.js, 2025-09)

The Management API moved to sub-clients with consistent naming:

```typescript
// BEFORE (v4):
await client.actions.getVersions(actionId);
await client.getUsers();
await client.organizations.getMembers({ id: orgId });
await client.organizations.getMemberRoles({ id: orgId, user_id: userId });

// AFTER (v5):
await client.actions.versions.list(actionId);   // sub-client + renamed
await client.users.list();                       // consistent list()
await client.organizations.members.list({ organizationId: orgId });
await client.organizations.members.roles.list({ organizationId: orgId, userId });
```

**Detection:** method calls like `client.getUsers()`, `client.actions.getVersions()`, `client.organizations.getMembers()`  
**Fix classification:** `FUNCTION_RENAME` (high confidence patterns)

### 5. Python sub-client migration — v4→v5 (Python, 2026-02-04)

```python
# BEFORE (auth0-python v4):
from auth0.management import Auth0
mgmt = Auth0(domain=domain, token=token)
users = mgmt.users.get_all()
connections = mgmt.connections.get_all()

# AFTER (auth0-python v5):
from auth0 import Auth0
auth0 = Auth0(domain=domain, management_api_token=token)
users = auth0.management.users.get_all()
connections = auth0.management.connections.get_all()
```

**Detection:** `from auth0.management import Auth0` → replaced with `from auth0 import Auth0`  
**Fix classification:** `IMPORT_CHANGED`

### 6. Python runtime requirement breaks — v5.2.0 and v5.5.0

```python
# v5.2.0: Python 3.8 dropped → requires >=3.9.2
# v5.5.0: Python 3.9 dropped → requires >=3.10
# Manifests as ImportError or install failure, not a code change
```

**Detection:** `python_requires` mismatch (scanner reads Pipfile/requirements.txt + pyproject.toml)  
**Fix classification:** `ENVIRONMENT_CHANGE` (no LLM fix; flag for human review)

---

## providers.yaml Entry

```yaml
- id: auth0
  name: Auth0
  api_version_scheme: semver
  api_base_urls:
  - https://YOUR_DOMAIN.auth0.com
  sdk_packages:
  - name: auth0
    ecosystem: npm
  - name: '@auth0/auth0-spa-js'
    ecosystem: npm
  - name: '@auth0/auth0-react'
    ecosystem: npm
  - name: '@auth0/nextjs-auth0'
    ecosystem: npm
  - name: auth0-python
    ecosystem: pypi
  feeds:
  - kind: npm_dist_tag
    package: auth0
    dist_tag: latest
    github_repo: auth0/node-auth0
  - kind: github_release
    repo: auth0/node-auth0
  - kind: npm_dist_tag
    package: '@auth0/auth0-spa-js'
    dist_tag: latest
    github_repo: auth0/auth0-spa-js
  - kind: npm_dist_tag
    package: '@auth0/auth0-react'
    dist_tag: latest
    github_repo: auth0/auth0-react
  skills:
  - src/depfix/providers/skills/provider_auth0.md
```

**Note:** No single public OpenAPI spec URL — the auth0 SDK is Fern-generated from an internal spec.
Feed should use `github_release` on `auth0/node-auth0` + `npm_dist_tag` on `auth0` package.

**Verify current feed kind options:**
```bash
grep -r "kind:" /Users/bedil_karimov/Documents/depfix-agents/providers.yaml | sort -u
```

---

## Skill File Outline: `src/depfix/providers/skills/provider_auth0.md`

```markdown
# Auth0 Provider Skill

## SDK packages
- npm: `auth0` (Management API), `@auth0/auth0-spa-js` (browser SPA), 
  `@auth0/auth0-react` (React), `@auth0/nextjs-auth0` (Next.js)
- pypi: `auth0-python`

## Python import name
PyPI package `auth0-python` imports as `auth0` (no rename issue — matches package).
```python
from auth0.management import Auth0   # v4 pattern
from auth0 import Auth0              # v5+ pattern
```

## Known breaking change patterns by version

### auth0 npm v4 → v5 (Sep 2025)
- Management sub-clients reorganized: `getUsers()` → `users.list()`, 
  `actions.getVersions(id)` → `actions.versions.list(id)`
- `organizations.getMembers({ id })` → `organizations.members.list({ organizationId })`
- Node.js minimum: `^20.19.0 || ^22.12.0 || ^24.0.0`
- Response data accessed directly; no `.data` wrapper

### auth0 npm v6 → v7 (Sep 2026)
- `AuthenticationClient` removed → `AuthClient` from `@auth0/auth0-auth-js`
- `UserInfoClient` removed → `AuthClient.getUserInfo()` from `@auth0/auth0-auth-js`
- `auth.oauth.clientCredentialsGrant({ audience })` → `auth.getTokenByClientCredentials({ audience })`
- `ResponseError`, `FetchError`, `JSONApiResponse` no longer exported
- `domain` must be bare hostname (no `https://`); throws at construction otherwise

### auth0 npm v7.1.0 (minor-version breaking, Sep 2026)
- `client.organizationTemplates` sub-client removed (list/create/get/update/listOrganizations)
- ConnectionStrategyEnum: `asana-mcp`→`asana`, `atlassian-mcp`→`atlassian`, etc.
- 9 enum values removed: docusign, figma, gusto, heroku, intercom, pagerduty, supabase, vercel, xero

### @auth0/auth0-spa-js v2.25.0 + @auth0/auth0-react v2.25.0 (minor-version breaking, Sep 2026)
- `getTokenSilently()` return type widened: `Promise<string>` → `Promise<string | undefined>`
- `getAccessTokenSilently()` return type widened same way (auth0-react wrapper)

### auth0-python v4 → v5 (Feb 2026)
- Hierarchical sub-clients: `auth0.management.users.get_all()` not `mgmt.users.get_all()`
- Import changed: `from auth0.management import Auth0` → `from auth0 import Auth0`
- Python minimum: >=3.9.2 (v5.2.0), then >=3.10 (v5.5.0)

## REPORT_ONLY changes (no replacement available)
- `auth0.organizationTemplates` sub-client removed (v7.1.0) — no replacement
- 9 ConnectionStrategyEnum values removed (v7.1.0) — if used, remove conditionally
- `branding.update()` identifiers param removed (python v5.7.0) — no replacement
```

---

## Seed Repo / Test Fixture

**Existing test repos to check:**
No existing auth0 seed repo in `bedilk/` org. Create `bedilk/seed-auth0-v4-to-v7`.

**Minimum fixture files:**

```
seed-auth0-v4-to-v7/
├── package.json          (auth0: ^4.29.0)
├── src/
│   ├── auth.ts           (uses AuthenticationClient, getUsers, actions.getVersions)
│   └── userinfo.ts       (uses UserInfoClient)
└── requirements.txt      (auth0-python==4.6.0)
```

**Sample call sites for scanner testing:**

```typescript
// src/auth.ts — v4 patterns that break on v5/v6/v7
import { ManagementClient, AuthenticationClient, UserInfoClient } from 'auth0';

const mgmt = new ManagementClient({ domain, clientId, clientSecret });
const auth = new AuthenticationClient({ domain, clientId, clientSecret });
const userInfo = new UserInfoClient({ domain });

// v4 method patterns (renamed in v5):
const users = await mgmt.getUsers();
const versions = await mgmt.actions.getVersions(actionId);
const members = await mgmt.organizations.getMembers({ id: orgId });

// v6 auth patterns (removed in v7):
const tokens = await auth.oauth.clientCredentialsGrant({ audience });
const profile = await userInfo.getUserInfo(accessToken);
```

```python
# app.py — v4 patterns that break on v5
from auth0.management import Auth0

mgmt = Auth0(domain=domain, token=mgmt_token)
users = mgmt.users.get_all()
connections = mgmt.connections.get_all()
```

---

## Implementer Checklist

1. [ ] Add entry to `providers.yaml` (see block above)
2. [ ] Create `src/depfix/providers/skills/provider_auth0.md`
3. [ ] Update provider count test: expected count +1
4. [ ] Verify `make test` passes (893 → 894 passed)
5. [ ] Test scanner against fixture:
   ```bash
   bash scripts/test_pipeline.sh auth0:bedilk/seed-auth0-v4-to-v7
   ```
   Expected: `AuthenticationClient` and `UserInfoClient` imports detected as call sites
6. [ ] Verify `auth0-python` import patterns (`from auth0.management import Auth0`, `from auth0 import Auth0`)
7. [ ] Note: no Python module name mismatch — `auth0-python` installs as `auth0` module (no `launchdarkly-server-sdk`/`ldclient` issue here)

---

## Breaking Change Frequency Summary

| Category | Count (last 12 months) | Impact |
|---|---|---|
| Major version breaks (Node.js) | 3 (v5, v6, v7) | High: full API surface |
| Major version breaks (Python) | 2 (v5, v6) | High: full API surface |
| Minor-version breaks (Node.js) | 1 (v7.1.0) | Medium: specific sub-clients |
| Minor-version breaks (Python) | 5 (v5.2–v6.7) | Medium–High: runtime + API |
| **Total depfix-relevant breaks/year** | **~11** | — |

This is the highest minor-version-break rate of any provider researched so far. Auth0's use of Fern-generated
SDKs means type and sub-client changes ship continuously. The Node.js package's minor-version breaking
changes are explicitly documented in `CHANGELOG.md` with the ⚠️ marker — no guesswork needed.
