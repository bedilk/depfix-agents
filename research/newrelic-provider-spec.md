# New Relic Provider Implementation Spec

**Status:** Ready for implementer  
**Date:** 2026-10-06  
**Researcher:** researcher agent  
**Source tasks:** T-8 (priority ranking — #9 candidate by volume), proactive work round 17  
**Priority:** 5.0M npm/month for Node.js agent + Python agent at v13.6.1; breaking changes on every major version

---

## Overview

New Relic is an APM (Application Performance Monitoring) agent SDK. Unlike REST SDK providers (Stripe, OpenAI), New Relic instruments your code passively — users load the agent at startup with `require('newrelic')` or `import 'newrelic'` at the top of their entry file. However, depfix can still detect upgrade-breaking patterns because:

1. **Custom instrumentation API** (`newrelic.startSegment`, `newrelic.instrument`, `shim.*`) is called directly in user code
2. **Config key renames** happen across major versions and can be detected in `newrelic.js` / `newrelic.cjs`
3. **Deprecated helper packages** (`@newrelic/apollo-server-plugin`, `@newrelic/next`) appear in `package.json` and import statements
4. **ESM loader flag** changes between major versions affect `package.json` scripts and Dockerfiles

| Package | Ecosystem | Monthly downloads | Latest |
|---|---|---|---|
| `newrelic` | npm | **5,039,685** | v14.5.1 |
| `newrelic` | pypi | ~2M/month (est.) | v13.6.1 |

**Download count verification (2026-09-05 → 2026-10-04):**
```bash
curl -s "https://api.npmjs.org/downloads/point/last-month/newrelic"
# {"downloads":5039685,"start":"2026-09-05","end":"2026-10-04","package":"newrelic"}
```

**Major version cadence:** 14 major npm versions since v1 (v1.0.0 through v14.0.0), approximately 1–2 per year since v8. Each major drops an EOL Node.js version and removes deprecated APIs. The Node.js agent is at v14 while the Python agent is at v13, indicating roughly parallel cadence.

| Field | Value |
|---|---|
| GitHub (Node) | `newrelic/node-newrelic` |
| GitHub (Python) | `newrelic/newrelic-python-agent` |
| OpenAPI spec | **None** — agent instrumentation, not a REST API client |
| api_version_scheme | `semver` |
| NEWS.md | `https://raw.githubusercontent.com/newrelic/node-newrelic/main/NEWS.md` (200 OK, confirmed) |

---

## Depfix Fit: Agent SDK vs REST SDK

New Relic differs from REST SDKs like Stripe or OpenAI in one key way: the agent runs passively without explicit API calls in business logic. However, three categories of user code ARE grep-detectable and DO break on upgrades:

### Category 1: Custom instrumentation API calls (most valuable)
```js
newrelic.startSegment(name, record, handler, args)
newrelic.startWebTransaction(url, handle)
newrelic.startBackgroundTransaction(name, group, handle)
newrelic.recordCustomEvent(eventType, attributes)
newrelic.addCustomAttribute(key, value)  // v4+; was addCustomParameter() before v4
newrelic.noticeError(error, attrs, expected)
newrelic.createDistributedTracePayload()   // REMOVED v14 (CAT removal)
newrelic.acceptDistributedTracePayload(payload)  // REMOVED v14
shim.handleCATHeaders(headers)             // RENAMED v11 → shim.handleMqTracingHeaders
shim.argsToArray(args)                     // REMOVED v14
```

### Category 2: Deprecated companion packages in package.json
```json
"@newrelic/apollo-server-plugin": "*"   // REMOVED v14 (built into agent)
"@newrelic/next": "*"                    // REMOVED v12 (built into agent)
```

### Category 3: ESM startup flag (detectable in scripts/Dockerfile)
```json
// v10 pattern (breaks in v11+):
"start": "node --loader newrelic/esm-loader.mjs app.mjs"
// v11+ correct pattern:
"start": "node --experimental-loader newrelic/esm-loader.mjs -r newrelic app.mjs"
```

---

## Breaking Change History (v10–v14)

All breaking changes below are sourced from NEWS.md at `newrelic/node-newrelic` (verified via curl, 2026-10-06).

### v10.0.0 (2023-04-19)

#### 1. `record_sql` default changed to `obfuscated`

```diff
# newrelic.js (config)
- # default was `off`
+ // After v10: default is now `obfuscated`
transaction_tracer: {
  record_sql: 'obfuscated'  // now the default; was 'off'
}
```

**Impact:** SQL queries that were previously not captured will now appear (obfuscated) in New Relic traces. Apps with PII in SQL that relied on the `off` default will unintentionally expose obfuscated SQL. Must explicitly set `record_sql: 'off'` to restore old behavior.

#### 2. Route parameters attribute renamed

Route parameters (e.g., `:id` in `/users/:id`) moved from `request.parameters.id` to `request.parameters.route.id`. Query parameters remain at `request.parameters.id`. APM dashboard NRQL queries using the old attribute name silently return no data after upgrade.

#### 3. `WebFrameworkShim.captureUrlParams` removed

```diff
- shim.captureUrlParams(request, params)  // removed in v10
+ // use agent's automatic route parameter capture instead
```

---

### v11.0.0 (2023-08-28)

#### 1. Node.js 14 dropped (min: Node 16)

Any project running Node.js 14 cannot upgrade to v11+. Detectable via `engines.node` in `package.json`.

#### 2. ESM loader invocation changed

```diff
- node --loader newrelic/esm-loader.mjs app.mjs
+ node --experimental-loader newrelic/esm-loader.mjs -r newrelic app.mjs
```

The old `--loader newrelic/esm-loader.mjs` pattern (without `-r newrelic`) causes the agent to not fully initialize in v11+. Instruments load but the API object (`newrelic.*` calls) is unavailable.

#### 3. `config.esm.custom_instrumentation_entrypoint` removed

```diff
// newrelic.js
- esm: {
-   custom_instrumentation_entrypoint: './custom-instrumentation.mjs'
- }
```

Custom ESM instrumentation entrypoints must now be registered using the standard `newrelic.instrument*` API with `{ isEsm: true }`:

```js
newrelic.instrument({ moduleName: 'my-lib', isEsm: true, onRequire: registerInstrumentation })
```

#### 4. `shim.handleCATHeaders` renamed to `shim.handleMqTracingHeaders`

```diff
- shim.handleCATHeaders(headers, segment, domainBoundary)
+ shim.handleMqTracingHeaders(headers, segment, domainBoundary)
```

Same signature; rename only. Any custom instrumentation using `shim.handleCATHeaders` throws `TypeError: shim.handleCATHeaders is not a function` at runtime.

#### 5. `onResolved` hook removed for custom instrumentation

```diff
- newrelic.instrument('my-module', { onResolved: handler })
+ newrelic.instrument('my-module', { onRequire: handler })
```

`onResolved` was used to instrument modules before they were required. It's removed in favor of `onRequire`. Code using `onResolved` silently stops instrumenting the target module.

---

### v12.0.0 (2024-07-31)

#### 1. Node.js 16 dropped (min: Node 18)

#### 2. Legacy context manager removed

The legacy context manager (`config.feature_flag.legacy_context_manager: true`) is no longer available. Any app that relied on this to work around AsyncLocalStorage compatibility issues needs alternative solutions.

#### 3. `@newrelic/next` companion package no longer needed

```diff
// next.config.js — no longer needed in v12+:
- const { withNRExperimentalEdgeRuntime } = require('@newrelic/next')
```

Next.js instrumentation is now built directly into the agent. Loading `@newrelic/next` alongside v12+ may cause double instrumentation. Apps should remove the package.

#### 4. MongoDB v2/v3 instrumentation dropped

Applications using `mongodb` driver v2 or v3 will not be instrumented after upgrading the New Relic agent to v12+. They must upgrade `mongodb` to v4+ or lose APM visibility.

---

### v13.0.0 (2025-07-23)

#### 1. Node.js 18 dropped (min: Node 20)

#### 2. Framework minimum version bumps

| Framework | Old min | New min |
|---|---|---|
| `fastify` | 2.x | 3.0.0 |
| `pino` | 7.x | 8.0.0 |
| `koa-router` | 11.x | 12.0.0 |

Apps that pin these frameworks below the new minimums lose New Relic instrumentation (no errors, no tracing) after upgrading to v13+.

---

### v14.0.0 (2026-05-18)

#### 1. Node.js 20 dropped (min: Node 22)

#### 2. Cross Application Tracing (CAT) removed entirely

```diff
- newrelic.createDistributedTracePayload()
- newrelic.acceptDistributedTracePayload(payload)
// Both throw TypeError: not a function in v14+
```

CAT was the legacy distributed tracing mechanism before W3C TraceContext / Distributed Tracing was added. Any code that calls these methods crashes at runtime after upgrade. These are common in message queue consumers and microservice boundaries.

#### 3. `shim.argsToArray` removed

```diff
- shim.argsToArray(arguments)
// Throws TypeError in v14+
```

A helper for custom instrumentation shimming. Code using it fails at runtime.

#### 4. `shim.prefixRouteParameters` removed

```diff
- shim.prefixRouteParameters(params, prefix)
// Removed — logic now runs automatically at transaction end
```

#### 5. `@newrelic/apollo-server-plugin` no longer needed

```diff
// Apollo Server setup — remove this in v14+:
- const newrelicPlugin = require('@newrelic/apollo-server-plugin')
- const server = new ApolloServer({ plugins: [newrelicPlugin] })
+ const server = new ApolloServer({ ... })  // agent instruments automatically
```

Loading the plugin in v14+ causes double instrumentation, which corrupts trace data.

#### 6. `koa-route` / `koa-router` instrumentation removed

Applications using `koa-route` (not `koa-router`) or older `koa-router` versions lose all routing-level instrumentation after v14 upgrade. Transactions still start but get generic names (`/GET/*`).

#### 7. `config.distributed_tracing.exclude_newrelic_header` default changed to `true`

```diff
// newrelic.js
distributed_tracing: {
-  exclude_newrelic_header: false  // was the default
+  exclude_newrelic_header: true   // v14 default
}
```

Apps that rely on New Relic-proprietary `newrelic` distributed trace headers (instead of W3C `traceparent`/`tracestate`) will lose trace continuity across services after v14 upgrade unless they explicitly set this to `false`.

---

## providers.yaml Block

```yaml
- id: newrelic
  name: New Relic APM
  api_version_scheme: semver
  sdk_packages:
  - name: newrelic
    ecosystem: npm
  - name: newrelic
    ecosystem: pypi
  feeds:
  - kind: npm_dist_tag
    package: newrelic
    dist_tag: latest
    github_repo: newrelic/node-newrelic
  - kind: pypi_dist_tag
    package: newrelic
    github_repo: newrelic/newrelic-python-agent
  - kind: github_release
    repo: newrelic/node-newrelic
  - kind: security_advisory
    package: newrelic
    ecosystem: npm
  - kind: security_advisory
    package: newrelic
    ecosystem: pypi
  - kind: ts_exports_diff
    package: newrelic
```

---

## Skill File: `provider_newrelic.md`

```markdown
# New Relic APM scan skill

## SDK packages
- npm: `newrelic` (Node.js agent)
- pypi: `newrelic` (Python agent)

## Import patterns

### Node.js / TypeScript
```js
// Must be first require/import — before any other module
require('newrelic')
import 'newrelic'
const newrelic = require('newrelic')
import newrelic from 'newrelic'
```

### Python
```python
import newrelic.agent
newrelic.agent.initialize('newrelic.ini')
newrelic.agent.register_application()
```

## Call sites (report these)

### Custom instrumentation API (all versions)
- `newrelic.startSegment(name, record, handler, args)` — custom trace segments
- `newrelic.startWebTransaction(url, handle)` — manual web transactions
- `newrelic.startBackgroundTransaction(name, group, handle)` — background jobs
- `newrelic.endTransaction()` — explicit transaction end
- `newrelic.recordCustomEvent(eventType, attributes)` — custom events
- `newrelic.addCustomAttribute(key, value)` — custom attributes (v4+; was `addCustomParameter` before v4)
- `newrelic.noticeError(error, attrs, expected)` — explicit error capture
- `newrelic.setTransactionName(name)` — rename current transaction
- `newrelic.getBrowserTimingHeader()` — real user monitoring injection

### REMOVED APIs (flag with REPORT_ONLY)
- `newrelic.createDistributedTracePayload()` — REMOVED in v14 (CAT removal)
- `newrelic.acceptDistributedTracePayload(payload)` — REMOVED in v14 (CAT removal)
- `newrelic.addCustomParameter(key, value)` — REMOVED in v8 (use `addCustomAttribute`)
- `shim.handleCATHeaders(...)` — RENAMED v11 → `shim.handleMqTracingHeaders`
- `shim.argsToArray(...)` — REMOVED v14
- `shim.prefixRouteParameters(...)` — REMOVED v14
- Config `config.esm.custom_instrumentation_entrypoint` — REMOVED v11

### Deprecated companion package imports (flag for removal)
- `require('@newrelic/apollo-server-plugin')` — built into agent v14+; causes double instrumentation
- `require('@newrelic/next')` — built into agent v12+; causes double instrumentation

## Where to look first
1. `grep("require('newrelic')", "")` or `grep("import 'newrelic'", "")` — entry file initialization.
2. `grep("createDistributedTracePayload\|acceptDistributedTracePayload", "")` — CAT APIs removed in v14.
3. `grep("@newrelic/apollo-server-plugin\|@newrelic/next", "")` — companion packages to remove in v12/v14.
4. `grep("shim.argsToArray\|shim.handleCATHeaders", "")` — custom instrumentation using removed shim methods.
5. Check `package.json` scripts for old ESM loader flag: `--loader newrelic/esm-loader.mjs` without `-r newrelic`.
```

---

## Known Breaking Change Entries for Corpus

### BC-1: `createDistributedTracePayload` / `acceptDistributedTracePayload` removed (v14)

```yaml
change_type: REMOVED
old_symbol: createDistributedTracePayload
description: "newrelic.createDistributedTracePayload() and newrelic.acceptDistributedTracePayload() removed in v14.0.0 (CAT removal). These methods throw TypeError at runtime. Replace with W3C TraceContext (newrelic.startWebTransaction + W3C headers). Source: NEWS.md v14.0.0."
source: github_release
provider: newrelic
since_version: "14.0.0"
```

### BC-2: `@newrelic/apollo-server-plugin` causes double instrumentation (v14)

```yaml
change_type: REMOVED
old_symbol: "@newrelic/apollo-server-plugin"
description: "@newrelic/apollo-server-plugin is built into the agent in v14.0.0. Loading it alongside v14+ corrupts trace data through double instrumentation. Remove the plugin from ApolloServer plugins array. Source: NEWS.md v14.0.0."
source: github_release
provider: newrelic
since_version: "14.0.0"
```

### BC-3: `shim.argsToArray` removed (v14)

```yaml
change_type: REMOVED
old_symbol: shim.argsToArray
description: "shim.argsToArray() removed in v14.0.0. Custom instrumentation code calling this method throws TypeError at runtime. Remove the call — modern JS rest parameters (...args) achieve the same goal. Source: NEWS.md v14.0.0."
source: github_release
provider: newrelic
since_version: "14.0.0"
```

### BC-4: `shim.handleCATHeaders` renamed to `shim.handleMqTracingHeaders` (v11)

```yaml
change_type: CHANGED
old_symbol: shim.handleCATHeaders
new_symbol: shim.handleMqTracingHeaders
description: "shim.handleCATHeaders() renamed to shim.handleMqTracingHeaders() in v11.0.0. Signature is identical; only the name changed. Code calling the old name throws TypeError: not a function at runtime. Source: NEWS.md v11.0.0."
source: github_release
provider: newrelic
since_version: "11.0.0"
```

### BC-5: `@newrelic/next` causes double instrumentation (v12)

```yaml
change_type: REMOVED
old_symbol: "@newrelic/next"
description: "@newrelic/next instrumentation built into agent in v12.0.0. Loading the companion package alongside v12+ causes double instrumentation (duplicate spans, wrong transaction names). Remove require('@newrelic/next') from next.config.js. Source: NEWS.md v12.0.0."
source: github_release
provider: newrelic
since_version: "12.0.0"
```

### BC-6: ESM loader invocation changed (v11)

```yaml
change_type: CHANGED
old_symbol: "--loader newrelic/esm-loader.mjs"
description: "ESM startup flag changed in v11.0.0: `node --loader newrelic/esm-loader.mjs app.mjs` must become `node --experimental-loader newrelic/esm-loader.mjs -r newrelic app.mjs`. Without the -r flag, the newrelic API object is undefined and all newrelic.* calls throw TypeError. Source: NEWS.md v11.0.0."
source: github_release
provider: newrelic
since_version: "11.0.0"
```

### BC-7: `config.distributed_tracing.exclude_newrelic_header` default changed (v14)

```yaml
change_type: CHANGED
old_symbol: "distributed_tracing.exclude_newrelic_header"
description: "config.distributed_tracing.exclude_newrelic_header default changed from false to true in v14.0.0. Services that pass New Relic-proprietary `newrelic` headers across microservices lose trace continuity after upgrade unless they add `exclude_newrelic_header: false` to newrelic.js. Source: NEWS.md v14.0.0."
source: github_release
provider: newrelic
since_version: "14.0.0"
```

---

## Seed Repo Fixture

**Suggested fixture:** `bedilk/seed-newrelic-v11-patterns`

```
# package.json
{
  "name": "newrelic-v11-patterns",
  "dependencies": {
    "newrelic": "^11.23.0",
    "@newrelic/apollo-server-plugin": "^3.0.0"
  },
  "scripts": {
    "start": "node --loader newrelic/esm-loader.mjs -r newrelic app.mjs"
  }
}

# app.js — uses APIs removed in v14
const newrelic = require('newrelic')

// CAT API — removed in v14
function forwardRequest(req, outgoingHeaders) {
  const payload = newrelic.createDistributedTracePayload()
  if (payload) {
    outgoingHeaders['X-NewRelic-Payload'] = payload.text()
  }
}

function receiveRequest(incomingHeaders) {
  const payload = incomingHeaders['X-NewRelic-Payload']
  if (payload) {
    newrelic.acceptDistributedTracePayload(payload)
  }
}

// Custom attribute (old name — removed in v8, use addCustomAttribute)
newrelic.addCustomParameter('userId', req.user.id)  // removed in v8

// apollo.js — companion package removed in v14
const newrelicPlugin = require('@newrelic/apollo-server-plugin')
const server = new ApolloServer({
  plugins: [newrelicPlugin]  // double instrumentation in v14+
})
```

**Expected depfix output (v11.x → v14.x upgrade):**
- Version drift: `newrelic` 11.23.x → 14.5.1 (major bump ×3)
- 4 call sites flagged:
  1. `createDistributedTracePayload()` — REMOVED in v14
  2. `acceptDistributedTracePayload()` — REMOVED in v14
  3. `@newrelic/apollo-server-plugin` import — built-in in v14, remove
  4. `addCustomParameter()` — REMOVED in v8, use `addCustomAttribute`

---

## Implementer Checklist

1. `providers.yaml`: Add the entry above. Note: both npm and pypi packages are named `newrelic` — scanner must distinguish by file context (`.js`/`.ts` vs `.py`).
2. Create `src/depfix/providers/skills/provider_newrelic.md` with the skill file content above.
3. Run `make test` — provider count assertion will need updating.
4. No OpenAPI spec. Use `github_release` + `ts_exports_diff` + `npm_dist_tag` + `pypi_dist_tag` feeds.
5. **Name collision:** npm `newrelic` and pypi `newrelic` have the same unscoped package name. Scanner must use file extension + manifest context to disambiguate.
6. **Agent-first pattern:** `require('newrelic')` almost always appears alone on the first line of the entry file. The import itself is the call site for version drift detection — even if no custom instrumentation APIs are used.
7. **Key depfix value:** `createDistributedTracePayload` / `acceptDistributedTracePayload` calls in message queue consumers are the highest-value detection — they're silent runtime errors that only surface when a distributed trace is actually followed.

---

## Scanner Detection Notes

**The `require('newrelic')` pattern is unusual:** Most Node.js apps load New Relic as the very first line with no variable assignment (`require('newrelic')`). The scanner should match this standalone require as a call site.

**Custom instrumentation files:** New Relic custom instrumentation is often in dedicated files named `newrelic-instrumentation.js`, `instrumentation.js`, or registered via `--require`. These are secondary call sites.

**Python agent:** The Python agent uses a different initialization pattern (`newrelic.agent.initialize('newrelic.ini')` + `newrelic.agent.register_application()`). The scan should detect both the `newrelic.ini` config file and the `import newrelic.agent` pattern.

---

## Feed Strategy

No public OpenAPI spec. Use:
- `github_release` on `newrelic/node-newrelic` — excellent structured release notes with `⚠ BREAKING CHANGES` section in every major
- `ts_exports_diff` on `newrelic` npm package — TypeScript types track public API surface
- `npm_dist_tag` for version polling
- `pypi_dist_tag` for Python version polling
- NEWS.md at `https://raw.githubusercontent.com/newrelic/node-newrelic/main/NEWS.md` is machine-parseable

---

## Comparison with Other Agent-Type Providers

The only other agent-type provider already in providers.yaml is Sentry. New Relic's integration model is:

| | Sentry | New Relic |
|---|---|---|
| Init pattern | `Sentry.init({...})` | `require('newrelic')` (bare) |
| Custom API calls | Many (`captureException`, `addBreadcrumb`, etc.) | Fewer (`startSegment`, `noticeError`, etc.) |
| Config location | JS code | `newrelic.js` config file |
| OpenAPI spec | Yes (management API) | No |
| Breaking change type | API renames + removed methods | API removals + Node.js version drops |

Sentry is a slightly better fit for depfix's scan model because users call `Sentry.*` methods extensively. New Relic's value is more in detecting: (a) removed distributed tracing APIs that only fail at request-time, (b) companion package conflicts (`@newrelic/apollo-server-plugin`), and (c) ESM loader flag changes.

---

*Recommended add priority: #9 after Resend, Cloudflare, Datadog, Plaid, HubSpot, Shopify, Segment, Mixpanel, Bugsnag*  
*See: research/bugsnag-provider-spec.md for the #8 spec and the format reference*
