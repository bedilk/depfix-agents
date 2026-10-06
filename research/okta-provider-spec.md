# Okta Provider Implementation Spec

**Status:** Ready for implementer  
**Date:** 2026-10-06  
**Researcher:** researcher agent  
**Source tasks:** Proactive work round 21 (continuation of provider spec series)  
**Priority:** ~5.3M npm/month + 864K pypi/month; enterprise-IAM critical-path; 7 major auth-js versions and 8 major sdk-nodejs versions since 2018 — consistent ~1 major/year cadence

---

## Overview

Okta is the dominant enterprise Identity and Access Management (IAM) platform. Note: this spec covers
**Okta's own SDKs** (`@okta/okta-auth-js`, `@okta/okta-sdk-nodejs`), not the Auth0 brand — Auth0 was
acquired by Okta in 2021 but ships under separate packages. The Auth0 spec is in `research/auth0-provider-spec.md`.

Okta has two distinct SDK lines that serve different purposes:
1. **`@okta/okta-auth-js`** (3.4M/month) — browser + Node.js auth flow SDK: sign-in, PKCE, token management, IDX protocol
2. **`@okta/okta-sdk-nodejs`** (1.9M/month) — management API SDK: create users, groups, applications, sessions

depfix is especially valuable here because:
1. **Consistent major version cadence**: 7 auth-js majors since 2018, 8 sdk-nodejs majors since 2019 (~1/year each)
2. **v7 sdk-nodejs: the GIANT migration**: entire API shape changed from `client.getUser(id)` to
   `client.userApi.getUser({userId: id})` — every single management call site is broken; this migration alone
   affects every enterprise app that auto-upgrades
3. **v8 auth-js**: `idx.proceed` now requires `step` parameter — breaks any IDX flow app silently at runtime
4. **Token decode behavior change** (v8 auth-js): `getAccessToken()` no longer returns decoded claims by default —
   apps that read `oktaAuth.getAccessToken().claims` crash with a runtime TypeError
5. **OpenAPI spec is public**: `okta-management-openapi-spec` repo has versioned YAML releases (3.4MB spec) —
   enables full `openapi_spec` diff feed

---

## Download Counts (verified 2026-10-06)

| Package | Ecosystem | Monthly downloads | Latest version |
|---|---|---|---|
| `@okta/okta-auth-js` | npm | **3,448,242** | v8.0.1 |
| `@okta/okta-sdk-nodejs` | npm | **1,881,949** | v8.2.0 |
| `@okta/oidc-middleware` | npm | **73,659** | legacy |
| `okta` | pypi | **864,197** | v3.4.6 |
| `omniauth-okta` | rubygems | 5,095,807 total | v2.0.0 |
| `oktakit` | rubygems | 5,657,070 total | v1.0.0 |

**Total npm/month (primary packages):** ~5.3M  
**Combined npm + pypi/month:** ~6.2M

**Verification commands:**
```bash
curl -s "https://api.npmjs.org/downloads/point/last-month/@okta/okta-auth-js"
# {"downloads":3448242,...}

curl -s "https://api.npmjs.org/downloads/point/last-month/@okta/okta-sdk-nodejs"
# {"downloads":1881949,...}

curl -s "https://pypistats.org/api/packages/okta/recent"
# {"data":{"last_month":864197},...}
```

---

## SDK Package History and Version Scheme

### Auth SDK (`@okta/okta-auth-js`)

| Version | Date | Key breaking change |
|---|---|---|
| v2.0.0 | 2018-08 | initial public major |
| v3.0.0 | 2020-03 | — |
| v4.0.0 | 2020-08 | — |
| v5.0.0 | 2021-04 | `token.value` removed; `isPending` removed from `AuthState`; `OktaAuth.start/stop` lifecycle |
| v6.0.0 | 2022-01 | `userAgent` field removed; `clearTokensAfterRedirect` → `clearTokensBeforeRedirect`; `introspect` renamed; `IdxFeature` enum changed number→string |
| v7.0.0 | 2022-09 | legacy PKCE/OAuth storage removed; `shouldProceedWithEmailAuthenticator` removed |
| v8.0.0 | 2026-03 | Node >=20 required; `cross-fetch` removed (native fetch); access tokens not decoded by default; `idx.proceed` requires `step` param |

**Version scheme:** semver, consistent major-per-year cadence

### Management SDK (`@okta/okta-sdk-nodejs`)

| Version | Date | Key breaking change |
|---|---|---|
| v2.0.0 | 2019-04 | initial public major |
| v3.0.0 | 2019-10 | — |
| v4.0.0 | 2020-07 | — |
| v5.0.0 | 2021-07 | Node 10 dropped; method signature changes for several resources |
| v6.0.0 | 2021-11 | some Client method signatures changed; enum-like modules introduced |
| v7.0.0 | 2023-04 | **FULL OPENAPI-GENERATOR MIGRATION**: `client.getUser(id)` → `client.userApi.getUser({userId:id})`; model CRUD methods removed; all methods now on scoped API clients |
| v8.0.0 | 2026-02 | `_from`→`fromAddress`, `to`→`toAddress` property renames; minimum Node.js 14; 15 new API clients added |

### Python SDK (`okta`)

| Version | Date | Key breaking change |
|---|---|---|
| v1.0.0 | 2020-10 | initial |
| v2.0.0 | 2021-07 | `sign_on_mode` type standardized to `ApplicationSignOnMode` (was inconsistent string/enum) |
| v3.0.0 | 2025-11 | upgraded to OAS 3.0; Python >=3.10 required |

**Python module name:** `okta` — pip install `okta`, import as `from okta.client import Client` (no mismatch)

---

## Breaking Changes Suitable for Depfix Eval Cases

### High-confidence call-site detectable changes

**1. `@okta/okta-sdk-nodejs` v7: Method dispatch migration (HIGHEST VALUE)**

Every single management call site changes. Before v7 each method was on the `Client` instance directly:
```javascript
// v6 and earlier
const user = await client.getUser('ausmvdt5xg8wRVI1d0g3');
await user.deactivate();
await client.listUsers();
await client.createGroup({ profile: { name: 'Sales' } });
const session = await client.createSession({ sessionToken: 'xxx' });
```

After v7 (openapi-generator), all methods are on scoped sub-clients:
```javascript
// v7+
const user = await client.userApi.getUser({ userId: 'ausmvdt5xg8wRVI1d0g3' });
await client.userApi.deactivateUser({ userId: user.id });
const users = client.userApi.listUsers();
await client.groupApi.createGroup({ group: { profile: { name: 'Sales' } } });
const session = await client.sessionApi.createSession({ createSessionRequest: { sessionToken: 'xxx' } });
```

Depfix detection: any `client.getUser(`, `client.listUsers(`, `client.createUser(`, `client.createGroup(`,
`client.createSession(`, `client.createApplication(`, `user.deactivate(`, `user.activate(`,
`user.resetPassword(` etc. — all of these are v6-era patterns, broken in v7.

Change type: `REMOVED` (method moved to sub-client)  
Source: GitHub release `okta-sdk-nodejs-7.0.0` (2023-04-05)  
Commit: `#373` — Uses openapi-generator for creating SDK

**2. `@okta/okta-sdk-nodejs` v8: Property renames**

```javascript
// v7 (broken in v8)
emailTestAddresses: { _from: 'sender@example.com', to: 'recipient@example.com' }

// v8 required
emailTestAddresses: { fromAddress: 'sender@example.com', toAddress: 'recipient@example.com' }
```

Depfix detection: `_from:` key in email config objects, `emailTestAddresses` usage  
Change type: `CHANGED` (property rename)

**3. `@okta/okta-auth-js` v8: `idx.proceed` now requires `step`**

```javascript
// v7 and earlier (step was optional)
await authClient.idx.proceed({ username: 'user@example.com', password: 'pass' });

// v8 required
await authClient.idx.proceed({ step: 'identify', username: 'user@example.com', password: 'pass' });
```

Depfix detection: `idx.proceed({` without `step:` — call sites using IDX flows  
Change type: `CHANGED` (parameter added as required)

**4. `@okta/okta-auth-js` v5: `token.value` removed**

```javascript
// v4 and earlier
const tokenValue = token.value;  // string

// v5 — token.value no longer exists; use token.accessToken or token.idToken
const tokenValue = token.accessToken;
```

Depfix detection: `.value` access on Okta token objects  
Change type: `REMOVED` (property removal)

**5. `@okta/okta-auth-js` v6: `clearTokensAfterRedirect` renamed**

```javascript
// v5 and earlier
await oktaAuth.signOut({ clearTokensAfterRedirect: true });

// v6
await oktaAuth.signOut({ clearTokensBeforeRedirect: true });  // semantics changed too
```

Depfix detection: `clearTokensAfterRedirect` in signOut options  
Change type: `CHANGED` (option renamed; semantics inverted)

**6. `@okta/okta-auth-js` v6: `introspect` method renamed**

```javascript
// v5 — directly on instance  
await authClient.introspect(token);

// v6 renamed
await authClient.introspectAuthn(token);  // or tx.introspect() still works
```

Depfix detection: `authClient.introspect(` call sites  
Change type: `CHANGED` (method renamed)

**7. `@okta/okta-auth-js` v8: access token decoding removed by default**

```javascript
// v7 and earlier — getAccessToken() returned decoded JWT claims
const claims = oktaAuth.getAccessToken();  // was object with .sub, .groups, etc.

// v8 — now returns raw JWT string by default
// apps reading .sub, .groups, .exp etc. crash with TypeError
const claims = oktaAuth.getAccessToken();  // now a string like "eyJhbGc..."
```

Depfix detection: `getAccessToken()` followed by property access (`.sub`, `.groups`, `.exp`, `.claims`)  
Change type: `CHANGED` (return type changed)

**8. `okta` Python v3: Python >=3.10 requirement**

Source: PyPI `okta` v3.0.0 (2025-11-06)  
Depfix detection: runtime requirement change — limited detection (ecosystem constraint check)  
Change type: `CHANGED` (runtime requirement raised)

---

## Import Patterns

### JavaScript/TypeScript
```javascript
// @okta/okta-auth-js
import { OktaAuth } from '@okta/okta-auth-js';
const { OktaAuth } = require('@okta/okta-auth-js');

// @okta/okta-sdk-nodejs  
import { Client } from '@okta/okta-sdk-nodejs';
const { Client } = require('@okta/okta-sdk-nodejs');
const okta = require('@okta/okta-sdk-nodejs');

// @okta/oidc-middleware (legacy)
const { ExpressOIDC } = require('@okta/oidc-middleware');
```

### Python
```python
from okta.client import Client as OktaClient
import okta
from okta import UserProfile, PasswordCredential, CreateUserRequest
```

---

## Key Call Sites to Detect

```
# sdk-nodejs v6→v7 patterns (all broken in v7)
client.getUser(
client.listUsers(
client.createUser(
client.updateUser(
client.deactivateUser(
client.listGroups(
client.createGroup(
client.createApplication(
client.createSession(
user.deactivate(
user.activate(
user.resetPassword(
user.expirePassword(
group.addUser(
group.removeUser(
application.activateUser(
application.deactivateUser(

# sdk-nodejs v7→v8 property renames
_from:
emailTestAddresses.*to:

# auth-js v7→v8 patterns
idx.proceed({
getAccessToken().
.clearTokensAfterRedirect

# auth-js v5 removals
token.value

# auth-js v6 renames
.introspect(
.isPending
```

---

## providers.yaml YAML Block

```yaml
- id: okta
  name: Okta
  api_version_scheme: semver
  api_base_urls:
  - https://your-org.okta.com/api/v1
  sdk_packages:
  - name: '@okta/okta-auth-js'
    ecosystem: npm
  - name: '@okta/okta-sdk-nodejs'
    ecosystem: npm
  - name: '@okta/oidc-middleware'
    ecosystem: npm
  - name: okta
    ecosystem: pypi
  feeds:
  - kind: npm_dist_tag
    package: '@okta/okta-auth-js'
    dist_tag: latest
    github_repo: okta/okta-auth-js
  - kind: npm_dist_tag
    package: '@okta/okta-sdk-nodejs'
    dist_tag: latest
    github_repo: okta/okta-sdk-nodejs
  - kind: pypi_dist_tag
    package: okta
    github_repo: okta/okta-sdk-python
  - kind: github_release
    repo: okta/okta-auth-js
  - kind: github_release
    repo: okta/okta-sdk-nodejs
  - kind: openapi_spec
    url: https://raw.githubusercontent.com/okta/okta-management-openapi-spec/master/dist/2026.03.0/management-minimal.yaml
  - kind: security_advisory
    package: '@okta/okta-auth-js'
    ecosystem: npm
  - kind: security_advisory
    package: '@okta/okta-sdk-nodejs'
    ecosystem: npm
  - kind: security_advisory
    package: okta
    ecosystem: pypi
  - kind: ts_exports_diff
    package: '@okta/okta-auth-js'
  - kind: ts_exports_diff
    package: '@okta/okta-sdk-nodejs'
```

**Note on OpenAPI spec URL:** Okta uses versioned spec releases (not a `latest` URL). The URL above points to
`2026.03.0` (management-minimal.yaml, 3.4MB, HTTP 200 verified). The implementer should evaluate whether to
pin to a specific version or find if there's a stable `latest` redirect. The spec files use versioned paths
like `dist/2026.03.0/`, `dist/2026.05.1/` — the `2026.05.x` releases renamed the top-level spec file from
`management-minimal.yaml` to `governance-combined-production-reference-minimal.yaml`.

---

## Skill File (`src/depfix/providers/skills/provider_okta.md`)

```markdown
# Okta scan skill

## SDK packages
- npm: `@okta/okta-auth-js`, `@okta/okta-sdk-nodejs`, `@okta/oidc-middleware`
- pypi: `okta`

## Import patterns

```
require('@okta/okta-auth-js')
import { OktaAuth } from '@okta/okta-auth-js'
require('@okta/okta-sdk-nodejs')
import { Client } from '@okta/okta-sdk-nodejs'
from okta.client import Client as OktaClient
import okta
```

## Call sites

**Auth SDK (`@okta/okta-auth-js`):**
- `new OktaAuth({...})` — initialization
- `oktaAuth.signIn(...)`, `oktaAuth.signOut(...)`
- `oktaAuth.token.getWithRedirect(...)`, `oktaAuth.token.parseFromUrl()`
- `oktaAuth.tokenManager.add(...)`, `oktaAuth.tokenManager.get(...)`
- `oktaAuth.idx.proceed({...})` — IDX protocol flow (v8: `step` required)
- `oktaAuth.getAccessToken()`, `oktaAuth.getIdToken()`
- `authClient.session.exists()`, `authClient.session.get()`

**Management SDK (`@okta/okta-sdk-nodejs`) — two API eras:**

v6 era (broken in v7+):
- `client.getUser(id)`, `client.listUsers()`, `client.createUser({...})`
- `user.deactivate()`, `user.activate()`, `user.resetPassword()`
- `client.createGroup({...})`, `client.createSession({...})`
- `client.createApplication({...})`

v7+ era:
- `client.userApi.getUser({userId})`, `client.userApi.listUsers()`
- `client.userApi.deactivateUser({userId})`, `client.userApi.activateUser({userId})`
- `client.groupApi.createGroup({...})`
- `client.sessionApi.createSession({...})`
- `client.applicationApi.createApplication({...})`

## Where to look first
1. Auth setup file: `okta.js`, `auth.ts`, `authConfig.ts`, `sso.ts`
2. Express middleware: files importing `@okta/oidc-middleware`
3. User management scripts: any server-side file with `new Client({...})`
4. IDX flow files: look for `idx.proceed` — if no `step:` property → v7 era, broken in v8
```

---

## Known Breaking Changes for Eval Corpus

| id | provider | change_type | old_symbol | new_symbol | version_from | version_to | description |
|---|---|---|---|---|---|---|---|
| okta_sdk_v7_getUser | okta | REMOVED | `client.getUser` | `client.userApi.getUser` | `^6.0.0` | `<8.0.0` | client methods moved to scoped API sub-clients |
| okta_sdk_v7_deactivate | okta | REMOVED | `user.deactivate` | `client.userApi.deactivateUser` | `^6.0.0` | `<8.0.0` | model CRUD methods removed in openapi-generator migration |
| okta_sdk_v8_from_field | okta | CHANGED | `_from` | `fromAddress` | `^7.0.0` | `<9.0.0` | email property renamed _from→fromAddress |
| okta_auth_v8_idx_step | okta | CHANGED | `idx.proceed` | `idx.proceed({step:...})` | `^7.0.0` | `<9.0.0` | step parameter is now required in idx.proceed |
| okta_auth_v5_token_value | okta | REMOVED | `token.value` | `token.accessToken` | `^4.0.0` | `<6.0.0` | token.value removed |
| okta_auth_v6_clearTokens | okta | CHANGED | `clearTokensAfterRedirect` | `clearTokensBeforeRedirect` | `^5.0.0` | `<7.0.0` | signOut option renamed |

---

## Seed Repo

No existing seed repo. Recommended: `bedilk/seed-okta-v6-to-v7`

Example fixture files for the seed:
```javascript
// src/users.js  — demonstrates v6-era patterns (broken in v7)
const okta = require('@okta/okta-sdk-nodejs');
const client = new okta.Client({ orgUrl: 'https://example.okta.com', token: process.env.OKTA_TOKEN });

async function getUser(userId) {
  const user = await client.getUser(userId);      // v6 pattern — broken in v7
  await user.deactivate();                          // v6 pattern — broken in v7
  return user;
}

async function createGroup(name) {
  return client.createGroup({ profile: { name } }); // v6 pattern — broken in v7
}
```

```python
# src/okta_client.py — demonstrates Python usage
from okta.client import Client as OktaClient

async def main():
    config = {'orgUrl': 'https://your-org.okta.com', 'token': 'YOUR_API_TOKEN'}
    async with OktaClient(config) as client:
        users, resp, err = await client.list_users()
```

---

## Implementer Checklist

- [ ] Add `okta` entry to `providers.yaml` (YAML block above)
- [ ] Create `src/depfix/providers/skills/provider_okta.md` (skill content above)
- [ ] Add test: provider `okta` appears in providers list
- [ ] Consider pinning or automating OpenAPI spec URL — versioned path means manual update
      each release quarter; alternative: use only `ts_exports_diff` + `github_release` feeds
- [ ] For eval corpus: add `okta_sdk_v7_getUser` case — this is the highest-value eval case
      (every enterprise app that upgrades sdk-nodejs from v6→v7 hits this)
- [ ] For seed repo: `bedilk/seed-okta-v6-to-v7` with v6-era call patterns

---

## Notes for Depfix Pipeline

- `@okta/okta-sdk-nodejs` v7 is the most depfix-relevant release in this provider's history.
  The openapi-generator migration changed the shape of **every** management call. Any codebase
  still on v6 that bumps to v7 will have every `client.*` call broken.

- Python module name is `okta` — matches pip install name, no import alias mismatch.

- The OpenAPI spec is versioned by quarterly release tags (`2026.03.0`, etc.). Starting in
  `2026.05.x`, Okta changed the spec file structure. The `management-minimal.yaml` file exists
  in all pre-2026.05.x releases; newer releases use `governance-*-minimal.yaml`. The implementer
  may want to track the GitHub releases feed for this spec repo separately.

- `@okta/oidc-middleware` is a legacy package (Express OIDC) — low priority for detection but
  still 74K downloads/month; worth including in sdk_packages for completeness.

- Ruby: `omniauth-okta` (5.1M total) and `oktakit` (5.7M total) have significant historical
  downloads but very low churn. The Okta Ruby Management SDK (`oktakit`) is v1.0.0 and largely
  stable. Not recommended for initial implementation — defer to a future minor update.
