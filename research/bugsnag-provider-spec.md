# Bugsnag Provider Implementation Spec

**Status:** Ready for implementer  
**Date:** 2026-10-06  
**Researcher:** researcher agent  
**Source tasks:** T-8 (priority ranking — #8 candidate by volume), proactive work round 16  
**Priority:** ~15M total npm/month across three JS packages; ubiquitous error monitoring SDK in production web, Node.js, React Native, and Electron apps

---

## Overview

Bugsnag is one of the most widely deployed error monitoring SDKs. Every `Bugsnag.notify()`, `Bugsnag.start()`, and `Bugsnag.leaveBreadcrumb()` call is a depfix-detectable call site. The JS SDK ships as a monorepo with three coordinated packages that share a single version scheme.

| Package | Use case | npm/month | Latest version |
|---|---|---|---|
| `@bugsnag/js` | Universal (Node + browser, auto-selects) | 5,243,754 | v9.0.0 |
| `@bugsnag/node` | Node.js only (server-side) | 5,318,423 | v9.0.0 |
| `@bugsnag/browser` | Browser only (client-side) | 5,261,739 | v9.0.0 |
| `bugsnag` (pypi) | Python | ~400K/month | v4.9.2 |
| `bugsnag` (rubygems) | Ruby/Rails | 67,761,681 total | v6.30.0 |

**Download count verification (2026-09-05 → 2026-10-04):**
```bash
curl -s "https://api.npmjs.org/downloads/point/last-month/@bugsnag/js"
# {"downloads":5243754,...}
curl -s "https://api.npmjs.org/downloads/point/last-month/@bugsnag/node"
# {"downloads":5318423,...}
curl -s "https://api.npmjs.org/downloads/point/last-month/@bugsnag/browser"
# {"downloads":5261739,...}
curl -s "https://rubygems.org/api/v1/gems/bugsnag.json"
# {"downloads":67761681,"version":"6.30.0",...}
```

**depfix opportunity:** The JS SDK has shipped two major breaking-change versions (v6→v7, v7→v8) with documented API renames that affect every Bugsnag user. A third major (v9.0.0, released 2026-09-22) just shipped. Many production apps are still on v7 or v6 patterns, making the `Bugsnag.start()` and option-rename migrations actionable today.

| Field | Value |
|---|---|
| GitHub (JS) | `bugsnag/bugsnag-js` |
| GitHub (Python) | `bugsnag/bugsnag-python` |
| GitHub (Ruby) | `bugsnag/bugsnag-ruby` |
| OpenAPI spec | **None** (SDK-based notifier, no REST management API spec) |
| api_version_scheme | `semver` |
| UPGRADING.md | `https://raw.githubusercontent.com/bugsnag/bugsnag-js/main/UPGRADING.md` (200 OK, confirmed) |

---

## Breaking Change History

All breaking changes below are sourced from the official `UPGRADING.md` at `bugsnag/bugsnag-js` (verified via curl).

### v6.x → v7.x (JS SDK, 2019)

The v6→v7 transition was a full API rewrite. Key changes:

#### 1. Initialization API changed

```diff
- import bugsnag from '@bugsnag/js'
+ import Bugsnag from '@bugsnag/js'

- const bugsnagClient = bugsnag({ apiKey: 'KEY' })
+ Bugsnag.start({ apiKey: 'KEY' })
```

Any codebase calling the `bugsnag(opts)` factory function throws a TypeError after upgrade: `bugsnag is not a function`.

#### 2. Options renamed

| Old option | New option |
|---|---|
| `notifyReleaseStages` | `enabledReleaseStages` |
| `autoNotify` | `autoDetectErrors` |
| `autoBreadcrumbsEnabled` | removed (use `enabledBreadcrumbTypes`) |

#### 3. React plugin API changed

```diff
- import BugsnagPluginReact from '@bugsnag/plugin-react'
- Bugsnag.start({ plugins: [new BugsnagPluginReact(React)] })
- const ErrorBoundary = Bugsnag.getPlugin('react')
+ Bugsnag.start({ plugins: [new BugsnagPluginReact()] })
+ const ErrorBoundary = Bugsnag.getPlugin('react').createErrorBoundary(React)
```

`Bugsnag.getPlugin('react')` now returns an object with a `createErrorBoundary()` method, not the ErrorBoundary component directly. TypeScript codebases that assigned the result to a React component type fail to compile.

---

### v7.0 → v7.1 (TypeScript types breaking change)

`Bugsnag.getPlugin('react')` changed its return type from `any` to a plugin interface. TypeScript code like:

```typescript
// Was fine in v7.0 (return type was `any`):
const ErrorBoundary = Bugsnag.getPlugin('react')
```

Now fails to compile because `ErrorBoundary` has no JSX type. Fix:

```typescript
const ErrorBoundary = Bugsnag.getPlugin('react')!.createErrorBoundary(React)
```

---

### v7.x → v8.x (JS SDK, 2024-08-29)

Source: `UPGRADING.md` section "7.x to 8.x", verified 2026-10-06.

#### 1. Node.js minimum version raised

Minimum Node.js: **v12.17.0** (was v10 or lower). Any project running Node 10/11 cannot upgrade.

#### 2. Network breadcrumb metadata field renamed

```diff
// Before v8, network breadcrumb metadata:
- { request: "GET https://example.com/api" }
// After v8:
+ { url: "https://example.com/api", method: "GET" }
```

Code that reads `breadcrumb.metadata.request` to extract URL or method will silently receive `undefined` after upgrade.

#### 3. `plugin-contextualize` behavior change

Previously, unhandled errors within a `plugin-contextualize` callback were caught by Bugsnag and the Node process did not terminate. From v8, uncaught exceptions in contextualize callbacks terminate the Node process (matching normal Node.js behavior). Code that relies on the old error-swallowing behavior will see new process crashes in production.

#### 4. Session counting changed for SPAs

`replaceState` and `pushState` no longer create new sessions. Sessions are now created on full page loads only. Analytics dashboards will show a drop in session counts after upgrade — this is not a bug but a behavioral breaking change.

#### 5. Endpoint validation tightened

If only one endpoint (either `notify` or `sessions`) is set in config, v8 now sends **neither** events nor sessions. Previously, setting only `notify` would still send events. On-premise Bugsnag deployments with partial endpoint configs silently stop reporting errors after upgrade.

---

### v8.x → v9.x (JS SDK, 2026-09-22)

v9.0.0 is primarily focused on React Native (New Architecture / React Native 0.84+) and Electron delivery resilience. The core browser and Node.js API is unchanged from v8. No JS/Node API breaking changes confirmed.

---

### Python SDK (`bugsnag` pypi)

| Version | Date | Change |
|---|---|---|
| v4.0.0 | ~2021 | Python 2 dropped; `bugsnag.configure(api_key=...)` required (was optional in older versions) |
| v4.9.2 | current | Python >=3.5 required |

The Python SDK API is stable: `bugsnag.configure()`, `bugsnag.notify()`, `bugsnag.before_notify()` patterns have not changed substantially since v4.

---

### Ruby SDK (`bugsnag` rubygems)

Currently at **v6.30.0** (latest). The v6 gem series has been very stable — all v6.26–v6.30 releases are enhancements and bugfixes, no breaking changes. v6.29.0 added Ruby 4 support. The last major breaking change was the v5→v6 series.

---

## providers.yaml Block

```yaml
- id: bugsnag
  name: Bugsnag Error Monitoring
  api_version_scheme: semver
  sdk_packages:
  - name: '@bugsnag/js'
    ecosystem: npm
  - name: '@bugsnag/node'
    ecosystem: npm
  - name: '@bugsnag/browser'
    ecosystem: npm
  - name: bugsnag
    ecosystem: pypi
  - name: bugsnag
    ecosystem: rubygems
  feeds:
  - kind: npm_dist_tag
    package: '@bugsnag/js'
    dist_tag: latest
    github_repo: bugsnag/bugsnag-js
  - kind: npm_dist_tag
    package: '@bugsnag/node'
    dist_tag: latest
    github_repo: bugsnag/bugsnag-js
  - kind: pypi_dist_tag
    package: bugsnag
    github_repo: bugsnag/bugsnag-python
  - kind: rubygems_dist_tag
    gem: bugsnag
    github_repo: bugsnag/bugsnag-ruby
  - kind: github_release
    repo: bugsnag/bugsnag-js
  - kind: security_advisory
    package: '@bugsnag/js'
    ecosystem: npm
  - kind: security_advisory
    package: '@bugsnag/node'
    ecosystem: npm
  - kind: security_advisory
    package: bugsnag
    ecosystem: pypi
  - kind: ts_exports_diff
    package: '@bugsnag/js'
  - kind: ts_exports_diff
    package: '@bugsnag/node'
```

---

## Skill File: `provider_bugsnag.md`

```markdown
# Bugsnag scan skill

## SDK packages
- npm (universal): `@bugsnag/js`
- npm (Node.js): `@bugsnag/node`
- npm (browser): `@bugsnag/browser`
- pypi: `bugsnag`
- rubygems: `bugsnag`

## Import patterns

### Node.js / TypeScript
```
import Bugsnag from '@bugsnag/js'
import Bugsnag from '@bugsnag/node'
const Bugsnag = require('@bugsnag/js')
const Bugsnag = require('@bugsnag/node')
```

### Browser
```
import Bugsnag from '@bugsnag/js'
import Bugsnag from '@bugsnag/browser'
```

### Python
```python
import bugsnag
bugsnag.configure(api_key='...')
bugsnag.notify(exception)
```

### Ruby
```ruby
require 'bugsnag'
Bugsnag.configure { |c| c.api_key = '...' }
Bugsnag.notify(exception)
```

## Call sites (report these)

### JS/TS v6 patterns (upgrade needed to v7+)
- `bugsnag({ apiKey: ... })` — OLD factory call, removed in v7. Use `Bugsnag.start({ apiKey: ... })`
- `bugsnagClient.notify(...)` — OLD instance call; prefer static `Bugsnag.notify(...)` from v7
- `new BugsnagPluginReact(React)` — OLD React plugin; pass no args in v7+
- `Bugsnag.getPlugin('react')` assigned directly — needs `.createErrorBoundary(React)` suffix from v7.1+
- Config key `notifyReleaseStages` — renamed to `enabledReleaseStages` in v7
- Config key `autoNotify` — renamed to `autoDetectErrors` in v7

### JS/TS v7 patterns (upgrade needed to v8+)
- `req.bugsnag.notify(...)` / `ctx.bugsnag.notify(...)` — still works but prefer static `Bugsnag.notify()` in v8+
- `breadcrumb.metadata.request` — field renamed to `url`+`method` in v8 network breadcrumbs
- Partial `endpoints` config (only `notify` set) — will send nothing in v8+; must set both `notify` and `sessions`

### Active call sites (all versions)
- `Bugsnag.start(...)` — initialization; check config options for deprecated keys
- `Bugsnag.notify(...)` — error reporting
- `Bugsnag.leaveBreadcrumb(...)` — manual breadcrumbs
- `Bugsnag.setUser(...)`, `Bugsnag.setContext(...)`
- `Bugsnag.addMetadata(...)`, `Bugsnag.getMetadata(...)`, `Bugsnag.clearMetadata(...)`
- `Bugsnag.startSession()`, `Bugsnag.pauseSession()`, `Bugsnag.resumeSession()`

## Where to look first
1. `grep("@bugsnag/", "")` — the scoped package name is distinctive; one grep finds both `@bugsnag/js` and `@bugsnag/node`.
2. `Bugsnag.start(...)` is almost always in a single setup file (`instrumentation.ts`, `bugsnag.ts`, `server.ts`).
3. For v6 detection: grep for `bugsnag({` or `bugsnag(apiKey` — the old factory call pattern.
4. For React plugin: grep for `BugsnagPluginReact` — its usage pattern distinguishes v7.0 from v7.1+.
```

---

## Known Breaking Change Entries for Corpus

### BC-1: v6 `bugsnag(opts)` factory removed in v7

```yaml
change_type: REMOVED
old_symbol: bugsnag
description: "v6 factory function `const client = bugsnag(opts)` removed in v7. Migrate to static interface: `Bugsnag.start(opts)`. Source: UPGRADING.md."
source: github_release
provider: bugsnag
since_version: "7.0.0"
```

### BC-2: `notifyReleaseStages` option renamed to `enabledReleaseStages`

```yaml
change_type: CHANGED
old_symbol: notifyReleaseStages
description: "Config option `notifyReleaseStages` renamed to `enabledReleaseStages` in v7. The old key is silently ignored, causing Bugsnag to report errors in all environments including development. Source: UPGRADING.md."
source: github_release
provider: bugsnag
since_version: "7.0.0"
```

### BC-3: `autoNotify` renamed to `autoDetectErrors`

```yaml
change_type: CHANGED
old_symbol: autoNotify
description: "Config option `autoNotify: false` renamed to `autoDetectErrors: false` in v7. Codebases that set `autoNotify: false` to disable automatic error detection will silently re-enable it after upgrading to v7+. Source: UPGRADING.md."
source: github_release
provider: bugsnag
since_version: "7.0.0"
```

### BC-4: React plugin: `BugsnagPluginReact(React)` → `BugsnagPluginReact()` + `createErrorBoundary(React)`

```yaml
change_type: CHANGED
old_symbol: BugsnagPluginReact
description: "React plugin API changed in v7.1: `new BugsnagPluginReact(React)` → `new BugsnagPluginReact()`, and `Bugsnag.getPlugin('react')` now returns a plugin object with `createErrorBoundary(React)` method rather than the ErrorBoundary component directly. TypeScript compile error otherwise. Source: UPGRADING.md."
source: github_release
provider: bugsnag
since_version: "7.1.0"
```

### BC-5: Network breadcrumb `request` field → `url` + `method` (v8)

```yaml
change_type: CHANGED
old_symbol: breadcrumb.metadata.request
description: "Network breadcrumb metadata field `request` (containing 'METHOD url' string) replaced by two separate fields `url` and `method` in v8.0.0. Code reading `breadcrumb.metadata.request` receives undefined after upgrade. Source: UPGRADING.md."
source: github_release
provider: bugsnag
since_version: "8.0.0"
```

### BC-6: Endpoint validation: partial config silently drops all events (v8)

```yaml
change_type: CHANGED
old_symbol: endpoints
description: "As of v8.0.0, if only one custom endpoint is set (e.g. only `notify` but not `sessions`), Bugsnag sends neither events nor sessions. Previously only sessions were dropped. On-premise deployments with partial `endpoints` config silently stop reporting errors after upgrade. Source: UPGRADING.md."
source: github_release
provider: bugsnag
since_version: "8.0.0"
```

### BC-7: Node.js minimum version raised to v12.17.0 (v8)

```yaml
change_type: CHANGED
old_symbol: node_version_requirement
description: "Minimum Node.js version raised to v12.17.0 in @bugsnag/js v8.0.0. Projects running Node 10 or 11 cannot upgrade. Source: UPGRADING.md."
source: github_release
provider: bugsnag
since_version: "8.0.0"
```

---

## Seed Repo Fixture

**Suggested fixture:** `bedilk/seed-bugsnag-v7-patterns`

```
# package.json
{
  "dependencies": {
    "@bugsnag/js": "^7.22.0",
    "@bugsnag/plugin-react": "^7.22.0",
    "react": "^18.2.0"
  }
}

# instrumentation.ts — uses v7.0 patterns with v7.1 breaking point
import bugsnagJs from '@bugsnag/js'
import BugsnagPluginReact from '@bugsnag/plugin-react'
import React from 'react'

// OLD v6 factory still present (bad code still out there)
// const client = bugsnagJs('MY_API_KEY')  // removed in v7

// v7 init but with deprecated option names
bugsnagJs.start({
  apiKey: 'MY_API_KEY',
  notifyReleaseStages: ['production', 'staging'],  // renamed to enabledReleaseStages
  autoNotify: false,                               // renamed to autoDetectErrors
  plugins: [new BugsnagPluginReact(React)],        // v7.0 form — needs createErrorBoundary in v7.1+
  endpoints: { notify: 'https://notify.internal.example.com' }  // partial config — drops all in v8
})

// v7.0 React plugin usage that breaks in v7.1+
const ErrorBoundary = bugsnagJs.getPlugin('react')

export { ErrorBoundary }
```

**Expected depfix output:**
- Version drift: `@bugsnag/js` 7.22.x → 9.0.0 (major bump)
- 4 call sites flagged: `notifyReleaseStages` (renamed), `autoNotify` (renamed), `BugsnagPluginReact(React)` (changed), partial `endpoints` config (v8 behavior change)
- Fix: rename option keys, update plugin initialization, add `sessions` endpoint

---

## Implementer Checklist

1. `providers.yaml`: Add the entry above. All three npm packages (`@bugsnag/js`, `@bugsnag/node`, `@bugsnag/browser`) version together — one providers.yaml entry covers all three.
2. Create `src/depfix/providers/skills/provider_bugsnag.md` with the skill file content above.
3. Run `make test` — provider count assertion will need updating.
4. No OpenAPI spec available — use `github_release` + `ts_exports_diff` feeds.
5. The `bugsnag` gem and pypi package share the same name (`bugsnag`) — scanner must distinguish ecosystems by file context (Gemfile vs requirements.txt).
6. Note: `@bugsnag/js` is a meta-package that exports either `@bugsnag/browser` or `@bugsnag/node` based on environment. Projects import from any of the three — scanner should match all three.

---

## Scanner Detection Notes

**Name collision:** The pypi package `bugsnag` and rubygems package `bugsnag` have the same unscoped name. The scanner must distinguish:
- Python: `import bugsnag` or `from bugsnag import ...` in `.py` files + `bugsnag` in `requirements.txt`
- Ruby: `require 'bugsnag'` in `.rb` files + `gem 'bugsnag'` in `Gemfile`

**JS package diversity:** Many apps import from `@bugsnag/js` but some server-only apps use `@bugsnag/node` directly. Framework-specific packages like `@bugsnag/plugin-express`, `@bugsnag/plugin-react`, `@bugsnag/plugin-vue` are all part of the same versioned monorepo.

---

## Feed Strategy

No public OpenAPI spec. Use:
- `github_release` on `bugsnag/bugsnag-js` — well-structured releases with "Breaking changes" section markers
- `ts_exports_diff` on `@bugsnag/js` and `@bugsnag/node` — strong TypeScript types; exports diff will catch API surface removals
- `npm_dist_tag` for version polling
- `rubygems_dist_tag` for Ruby version polling

---

*Recommended add priority: #8 after Resend, Cloudflare, Datadog, Plaid, HubSpot, Shopify, Segment, Mixpanel (research/top-providers-by-breakage.md)*  
*See: research/resend-provider-spec.md, research/cloudflare-provider-spec.md, research/datadog-provider-spec.md, research/plaid-provider-spec.md, research/hubspot-provider-spec.md, research/shopify-provider-spec.md, research/segment-provider-spec.md, research/mixpanel-provider-spec.md*
