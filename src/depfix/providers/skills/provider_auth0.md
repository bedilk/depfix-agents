# Auth0 scan skill

## SDK packages
- npm: `auth0` (Management API), `@auth0/auth0-spa-js` (browser SPA),
  `@auth0/auth0-react` (React), `@auth0/nextjs-auth0` (Next.js)
- pypi: `auth0-python`

## Import shapes to look for

### JavaScript / TypeScript (Management SDK)
```
import { ManagementClient, AuthenticationClient } from 'auth0'
import { ManagementClient } from 'auth0'
const { ManagementClient } = require('auth0')
```

### JavaScript / TypeScript (SPA / React SDK)
```
import { useAuth0 } from '@auth0/auth0-react'
import createAuth0Client from '@auth0/auth0-spa-js'
import { Auth0Client } from '@auth0/auth0-spa-js'
```

### Python
```python
from auth0.management import Auth0   # v4 pattern
from auth0 import Auth0              # v5+ pattern
import auth0
```

## Call sites to look for

### Management API (Node.js)
- `new ManagementClient({ domain, clientId, clientSecret })` — management client construction
- `new AuthenticationClient({ domain, clientId, clientSecret })` — auth client (removed v7)
- `new UserInfoClient({ domain })` — user info (removed v7)
- `mgmt.getUsers()` — v4 pattern (renamed `users.list()` in v5)
- `mgmt.actions.getVersions(id)` — v4 pattern (renamed `actions.versions.list(id)` in v5)
- `mgmt.organizations.getMembers({ id })` — v4 pattern (renamed in v5)
- `auth.oauth.clientCredentialsGrant({ audience })` — v6 pattern (removed v7)
- `userInfo.getUserInfo(accessToken)` — v6 pattern (removed v7)

### SPA / React SDK
- `getTokenSilently()` — return type widened to `string | undefined` in v2.25.0
- `getAccessTokenSilently()` — same widening in `@auth0/auth0-react` v2.25.0
- `createAuth0Client({ domain, client_id })` — client construction pattern

### Python Management
- `Auth0(domain=domain, token=token)` / `Auth0(domain=domain, management_api_token=token)`
- `mgmt.users.get_all()` — users list
- `mgmt.connections.get_all()` — connections list

## Where to look first
1. `grep("AUTH0_CLIENT_ID", "")` or `grep("AUTH0_DOMAIN", "")` — canonical env vars.
2. `grep("auth0", "package.json")` or `grep("auth0-python", "requirements.txt")`.
3. Authentication middleware files: `middleware/auth.ts`, `lib/auth.ts`, `utils/auth.ts`.
4. Python: `from auth0.management import Auth0` or `from auth0 import Auth0`.
5. SPA apps: `useAuth0` hook usage in React components.

## Breaking-change context

### auth0 npm v6 → v7 (Sep 2026) — AuthenticationClient removed
The single biggest break affecting all server-side auth flows:
- `AuthenticationClient` entirely removed from `auth0` package → move to `@auth0/auth0-auth-js`
- `UserInfoClient` entirely removed → use `AuthClient.getUserInfo()` from `@auth0/auth0-auth-js`
- `auth.oauth.clientCredentialsGrant({ audience })` → `auth.getTokenByClientCredentials({ audience })`
- `ResponseError`, `FetchError`, `JSONApiResponse` no longer exported from `auth0`
- `domain` must be bare hostname (no `https://` prefix)

### auth0 npm v7.1.0 (minor-version breaking, Sep 2026)
- `client.organizationTemplates` sub-client removed (no replacement)
- `ConnectionStrategyEnum`: 9 values renamed or removed (`asana-mcp`→`asana`, `docusign` removed, etc.)

### auth0 npm v4 → v5 (Sep 2025) — Sub-client architecture
- `mgmt.getUsers()` → `mgmt.users.list()`
- `mgmt.actions.getVersions(id)` → `mgmt.actions.versions.list(id)`
- `mgmt.organizations.getMembers({ id })` → `mgmt.organizations.members.list({ organizationId })`
- Node.js minimum: `^20.19.0 || ^22.12.0 || ^24.0.0`

### @auth0/auth0-spa-js v2.25.0 + @auth0/auth0-react v2.25.0 (minor-version breaking, Sep 2026)
- `getTokenSilently()` return type: `Promise<string>` → `Promise<string | undefined>`
- `getAccessTokenSilently()` return type widened same way

### auth0-python v4 → v5 (Feb 2026) — Hierarchical sub-clients
- Import changed: `from auth0.management import Auth0` → `from auth0 import Auth0`
- Client arg renamed: `token=` → `management_api_token=`
- Sub-client paths: `mgmt.users.get_all()` → `auth0.management.users.get_all()`
- Python minimum: >=3.9.2 (v5.2.0), then >=3.10 (v5.5.0) — runtime failure on old Python

### auth0-python minor-version breaks (2026)
- v5.7.0: `branding.update()` `identifiers` param removed (no replacement — REPORT_ONLY)
- v5.8.0: `clients.update()` type change (`NativeSocialLogin` → `NativeSocialLoginPatch`)
- v6.4.0: `app_type` value `b2b_integration` removed from enum
- v6.5.0: `organization_templates` sub-client removed; 9 provider enum values removed
- v6.7.0: `management.organizations.organization_template` sub-client removed

## REPORT_ONLY changes (no replacement available)
- `auth0.organizationTemplates` sub-client removed (v7.1.0 npm)
- 9 ConnectionStrategyEnum values removed (v7.1.0 npm)
- `branding.update()` identifiers param removed (python v5.7.0)
- `b2b_integration` app_type removed (python v6.4.0)

## Anchors (fallback signals)
- Env vars: `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`, `AUTH0_AUDIENCE`
- Config patterns: `auth0.json`, `.auth0.json`, `AUTH0_ISSUER_BASE_URL`
- Domain patterns: `*.auth0.com`, `*.us.auth0.com`, `*.eu.auth0.com`
