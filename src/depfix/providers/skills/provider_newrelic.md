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

newrelic.agent.initialize("newrelic.ini")
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
- `newrelic.addCustomParameter(key, value)` — REMOVED in v8; use `addCustomAttribute`
- `shim.handleCATHeaders(...)` — RENAMED v11 → `shim.handleMqTracingHeaders`
- `shim.argsToArray(...)` — REMOVED v14
- `shim.prefixRouteParameters(...)` — REMOVED v14
- Config `esm.custom_instrumentation_entrypoint` — REMOVED v11

### Deprecated companion package imports (flag for removal)
- `require('@newrelic/apollo-server-plugin')` — built into agent v14+; causes double instrumentation
- `require('@newrelic/next')` — built into agent v12+; causes double instrumentation

## Where to look first
1. `grep("require('newrelic')", "")` or `grep("import 'newrelic'", "")` — entry file initialization.
2. `grep("createDistributedTracePayload\|acceptDistributedTracePayload", "")` — CAT APIs removed in v14.
3. `grep("@newrelic/apollo-server-plugin\|@newrelic/next", "")` — companion packages to remove.
4. `grep("shim.argsToArray\|shim.handleCATHeaders", "")` — removed shim methods.
5. Check `package.json` scripts for old ESM loader flag: `--loader newrelic/esm-loader.mjs` without `-r newrelic`.

## Breaking-change context

### v14.0.0 (2026-05-18) — CAT removed, Node 22 minimum
- Node.js minimum raised to 22 (from 20)
- `createDistributedTracePayload()` and `acceptDistributedTracePayload()` removed — throws TypeError
- `shim.argsToArray()` and `shim.prefixRouteParameters()` removed
- `@newrelic/apollo-server-plugin` built into agent — loading it causes double instrumentation
- `config.distributed_tracing.exclude_newrelic_header` default changed from `false` to `true`

### v13.0.0 (2025-07-23) — Node 20 minimum, framework version bumps
- Node.js minimum raised to 20 (from 18)
- `fastify` minimum: 3.0.0; `pino` minimum: 8.0.0; `koa-router` minimum: 12.0.0
- Apps pinned below these framework versions lose New Relic instrumentation silently

### v12.0.0 (2024-07-31) — Node 18 minimum, legacy context manager removed
- Node.js minimum raised to 18 (from 16)
- Legacy context manager removed (`config.feature_flag.legacy_context_manager`)
- `@newrelic/next` built into agent — loading alongside v12+ causes double instrumentation
- MongoDB v2/v3 instrumentation dropped; must upgrade mongodb to v4+

### v11.0.0 (2023-08-28) — ESM loader + shim rename
- Node.js minimum raised to 16 (from 14)
- ESM loader flag changed: `--loader newrelic/esm-loader.mjs` → `--experimental-loader newrelic/esm-loader.mjs -r newrelic`
- `shim.handleCATHeaders` renamed to `shim.handleMqTracingHeaders`
- `onResolved` hook removed; use `onRequire` in custom instrumentation
- `config.esm.custom_instrumentation_entrypoint` removed

### v10.0.0 (2023-04-19) — record_sql default + route param rename
- `record_sql` default changed from `off` to `obfuscated`
- Route parameters moved from `request.parameters.id` to `request.parameters.route.id`
- `WebFrameworkShim.captureUrlParams` removed

## Anchors (fallback signals)
- Config files: `newrelic.js`, `newrelic.cjs`
- Env vars: `NEW_RELIC_LICENSE_KEY`, `NEW_RELIC_APP_NAME`, `NEW_RELIC_NO_CONFIG_FILE`
- Python: `newrelic.ini` config file in project root
