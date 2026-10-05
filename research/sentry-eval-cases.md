# Sentry v7→v8 Eval Cases Research

**Task:** T-4 research subtask  
**Date:** 2026-10-05  
**Sources:** 
- `depfix.db` breaking_change table (sentry provider, v7.119.0→v8.0.0)
- Seed repo plan artifacts (`.depfix/plans/bedilk__seed-sentry-v7-v8.json`)
- `tests/fixtures/` existing fixture structure (openai_v3_project, ruby_sentry_project)
- `src/depfix/evals/corpus/` YAML format (call-sites.yaml, openai-node-v4-fixes.yaml)
- depfix-test-sentry-v6-app scan (31 JS call sites, @sentry/node 10.75.3→11.4.0)

---

## Eval YAML Format Summary

Two categories are needed:

**`call_sites`** — deterministic, no LLM, tests `CallSiteScanner`:
```yaml
- id: <slug>
  category: call_sites
  verified: false          # flip to true after running make eval manually
  description: >
    <what the case tests>
  fixture: <fixture_dir>   # must exist under tests/fixtures/
  provider_id: sentry
  sdk_packages: ["@sentry/node"]
  symbols: ["sentry.startTransaction"]  # optional: narrow to one symbol
  expected_call_sites:
    - symbol_contains: "startTransaction"
      kind: method_call
      file_contains: "perf.js"
      min_confidence: medium
```

**`fix_generation`** — requires LLM, tests `FixGenerator`:
```yaml
- id: <slug>
  category: fix_generation
  verified: false
  description: >
    <what the case tests>
  fixture: <fixture_dir>
  target_file: src/perf.js
  breaking_change:
    package: "@sentry/node"
    old_version: "7.119.0"
    new_version: "8.0.0"
    old_api: "sentry.startTransaction"
    new_api: "sentry.startSpan"
    description: ...
    migration_guide: ...
    kind: method_renamed
    source: manual
    provider_id: sentry
    confidence: 0.9
    examples:
      - - |     # [before, after] pair
          const tx = Sentry.startTransaction({ name: 'my-task', op: 'task' });
        - |
          Sentry.startSpan({ name: 'my-task', op: 'task' }, (span) => { ... });
  fix_assertion:
    must_contain: ["startSpan"]
    must_not_contain: ["startTransaction"]
    max_changed_line_ratio: 0.6
```

**Fixture structure** needed: `tests/fixtures/sentry_v7_project/`
```
tests/fixtures/sentry_v7_project/
  package.json            # "@sentry/node": "^7.119.0"
  src/
    setup.js              # Sentry.init + integrations (old class-based)
    perf.js               # startTransaction + startChild
    hub.js                # getCurrentHub + configureScope
    breadcrumbs.js        # addBreadcrumb + withScope
    handlers.js           # Handlers.requestHandler + Handlers.errorHandler
```

---

## 10 Sentry v7→v8 API Changes for Eval Cases

### Change 1: `startTransaction` → `startSpan`
**Kind:** `method_renamed`  
**DB evidence:** breaking_change id=4379, source=llm_synthesis  
**Seed plan:** `bedilk__seed-sentry-v7-v8.json` step `startTransaction → startSpan`

```javascript
// BEFORE (v7)
const transaction = Sentry.startTransaction({ name: 'process-request', op: 'http.request' });
transaction.setStatus('ok');
transaction.finish();

// AFTER (v8)
Sentry.startSpan({ name: 'process-request', op: 'http.request' }, (span) => {
  span.setStatus({ code: 1 }); // OTEL SpanStatusCode.OK
  // span auto-finishes when callback returns
});
```

**Eval case type:** `call_sites` (detect `Sentry.startTransaction` calls) + `fix_generation`  
**Call-site symbol to detect:** `sentry.startTransaction`  
**fixture file:** `src/perf.js`

---

### Change 2: `getCurrentHub()` → `getCurrentScope()`
**Kind:** `method_renamed`  
**DB evidence:** breaking_change id=4380, source=llm_synthesis

```javascript
// BEFORE (v7)
const hub = Sentry.getCurrentHub();
hub.configureScope((scope) => {
  scope.setTag('region', 'us-east-1');
});

// AFTER (v8)
const scope = Sentry.getCurrentScope();
scope.setTag('region', 'us-east-1');
```

**Eval case type:** `call_sites` + `fix_generation`  
**Call-site symbol:** `sentry.getCurrentHub`  
**fixture file:** `src/hub.js`

---

### Change 3: `configureScope(callback)` → `withScope(callback)`
**Kind:** `method_renamed`  
**Source:** v8 migration guide; also appears as `sentry.getCurrentHub.configureScope` in depfix-test-sentry-v6-app scan (DB scan_id=149)

```javascript
// BEFORE (v7)
Sentry.configureScope((scope) => {
  scope.setUser({ id: userId });
  scope.setTag('subscription', plan);
});

// AFTER (v8)
Sentry.withScope((scope) => {
  scope.setUser({ id: userId });
  scope.setTag('subscription', plan);
  Sentry.captureException(err);
});
```

Note: `withScope` in v7 was for isolated scopes; in v8 it replaces `configureScope` for mutation
of the current isolation scope.

**Eval case type:** `call_sites` + `fix_generation`  
**Call-site symbol:** `sentry.configureScope`  
**fixture file:** `src/hub.js`

---

### Change 4: `Integrations.Http` (class) → `httpIntegration()` (function)
**Kind:** `method_renamed`  
**Seed repo evidence:** `bedilk__seed-sentry-v7-v8.json` — the only confirmed fix in the seed

```javascript
// BEFORE (v7)
Sentry.init({
  integrations: [new Sentry.Integrations.Http({ tracing: true })],
});

// AFTER (v8)
Sentry.init({
  integrations: [Sentry.httpIntegration({ tracing: true })],
});
```

**Eval case type:** `call_sites` + `fix_generation`  
**Call-site symbol:** `sentry.Integrations.Http`  
**fixture file:** `src/setup.js`

---

### Change 5: `Integrations.Express` (class) → `expressIntegration()` (function)
**Kind:** `method_renamed`  
**Source:** Parallel to Integrations.Http removal; same pattern in sentry-v6-app (`new Sentry.ExpressInstrumentation()`)

```javascript
// BEFORE (v7)
Sentry.init({
  integrations: [new Sentry.Integrations.Express({ app })],
});

// AFTER (v8)
Sentry.init({
  integrations: [Sentry.expressIntegration({ app })],
});
```

**Eval case type:** `call_sites` + `fix_generation`  
**Call-site symbol:** `sentry.Integrations.Express`  
**fixture file:** `src/setup.js`

---

### Change 6: `Handlers.requestHandler()` → `setupExpressErrorHandler()` / `expressIntegration()`
**Kind:** `method_renamed`  
**DB evidence:** sentry.setupExpressErrorHandler in depfix-test-sentry-v6-app call sites (scan_id=149)

```javascript
// BEFORE (v7)
app.use(Sentry.Handlers.requestHandler());
app.use(Sentry.Handlers.tracingHandler());
// ... routes ...
app.use(Sentry.Handlers.errorHandler());

// AFTER (v8)
// requestHandler/tracingHandler replaced by expressIntegration() in init
Sentry.init({ integrations: [Sentry.expressIntegration({ app })] });
// ... routes ...
Sentry.setupExpressErrorHandler(app);
```

**Eval case type:** `call_sites` (detect `Sentry.Handlers.requestHandler`)  
**Call-site symbol:** `sentry.Handlers.requestHandler`  
**fixture file:** `src/handlers.js`

---

### Change 7: `transaction.startChild()` → nested `startSpan()`
**Kind:** `method_renamed`  
**Source:** Sentry v8 spans API; spans are now OTel-based with no `startChild` method

```javascript
// BEFORE (v7)
const tx = Sentry.startTransaction({ name: 'checkout', op: 'process' });
const child = tx.startChild({ op: 'db.query', description: 'SELECT items' });
child.finish();
tx.finish();

// AFTER (v8)
Sentry.startSpan({ name: 'checkout', op: 'process' }, () => {
  Sentry.startSpan({ op: 'db.query', description: 'SELECT items' }, () => {
    // db work
  });
});
```

**Eval case type:** `call_sites` (detect `sentry.startTransaction.startChild`)  
**Call-site symbol:** `sentry.startTransaction.startChild`  
**fixture file:** `src/perf.js`

---

### Change 8: `addBreadcrumb` with `level` string → typed `level` values
**Kind:** `param_type_changed`  
**Source:** v8 enforces breadcrumb levels; `data.level` type narrows

```javascript
// BEFORE (v7 — accepted any string level)
Sentry.addBreadcrumb({
  message: 'User clicked checkout',
  category: 'ui.click',
  level: 'info',      // loose string, no IDE autocomplete
  data: { userId: id }
});

// AFTER (v8 — typed severity levels with SeverityLevel enum)
import { SeverityLevel } from '@sentry/node';
Sentry.addBreadcrumb({
  message: 'User clicked checkout',
  category: 'ui.click',
  level: 'info' as SeverityLevel,  // typed, enumerated
  data: { userId: id }
});
```

Note: This is a soft change — runtime behavior unchanged but `Severity` enum was removed in v7 and
`SeverityLevel` is the v7+ canonical type. This case validates detection of `addBreadcrumb` call
sites where `level` is set.

**Eval case type:** `call_sites` (detect `sentry.addBreadcrumb`)  
**Call-site symbol:** `sentry.addBreadcrumb`  
**fixture file:** `src/breadcrumbs.js`

---

### Change 9: `captureException` with `hint` object → typed `ExceptionHint`
**Kind:** `param_type_changed`  
**Source:** v8 tightens the second argument to `captureException`

```javascript
// BEFORE (v7)
Sentry.captureException(err, {
  extra: { requestId: req.id },
  tags: { subsystem: 'checkout' },
  user: { id: userId }
});

// AFTER (v8)
Sentry.withScope((scope) => {
  scope.setExtra('requestId', req.id);
  scope.setTag('subsystem', 'checkout');
  scope.setUser({ id: userId });
  Sentry.captureException(err);
});
```

The second argument to `captureException` in v7 was a `CaptureContext` object; v8 deprecates passing
scope data inline — use `withScope` instead.

**Eval case type:** `call_sites` + `fix_generation`  
**Call-site symbol:** `sentry.captureException`  
**fixture file:** `src/breadcrumbs.js`

---

### Change 10: `Hub` constructor removed → use `getClient()` / `Sentry.getGlobalScope()`
**Kind:** `method_removed`  
**Source:** Hub class was a v7 internal (not officially public API) but many apps instantiated it

```javascript
// BEFORE (v7 — unofficial but common pattern)
const hub = new Sentry.Hub(new Sentry.NodeClient(options));
hub.bindClient(client);
Sentry.makeMain(hub);

// AFTER (v8 — use modular scope API)
Sentry.init(options);
const scope = Sentry.getGlobalScope();
// Hub concept replaced by Scope hierarchy: global, isolation, current
```

**Eval case type:** `call_sites` (detect `sentry.Hub` constructor instantiation)  
**Call-site symbol:** `sentry.Hub`  
**fixture file:** `src/hub.js`

---

## Fixture Files Required

### `tests/fixtures/sentry_v7_project/package.json`
```json
{
  "name": "sentry-v7-fixture",
  "version": "1.0.0",
  "private": true,
  "description": "Eval fixture: app written against @sentry/node v7, used for v7→v8 migration cases.",
  "dependencies": {
    "@sentry/node": "^7.119.0",
    "express": "^4.18.2"
  }
}
```

### `tests/fixtures/sentry_v7_project/src/setup.js`
```javascript
const Sentry = require('@sentry/node');
const express = require('express');
const app = express();

// v7 class-based integrations — all removed in v8
Sentry.init({
  dsn: process.env.SENTRY_DSN,
  tracesSampleRate: 1.0,
  integrations: [
    new Sentry.Integrations.Http({ tracing: true }),
    new Sentry.Integrations.Express({ app }),
  ],
});

// v7 request/error handler middleware
app.use(Sentry.Handlers.requestHandler());
app.use(Sentry.Handlers.tracingHandler());
app.use((err, req, res, next) => Sentry.Handlers.errorHandler()(err, req, res, next));

module.exports = { app };
```

### `tests/fixtures/sentry_v7_project/src/perf.js`
```javascript
const Sentry = require('@sentry/node');

// v7 transaction API — replaced by startSpan in v8
function processOrder(orderId) {
  const transaction = Sentry.startTransaction({ name: 'process-order', op: 'task' });
  transaction.setStatus('ok');
  const child = transaction.startChild({ op: 'db.query', description: 'SELECT order' });
  child.finish();
  transaction.finish();
}

module.exports = { processOrder };
```

### `tests/fixtures/sentry_v7_project/src/hub.js`
```javascript
const Sentry = require('@sentry/node');

// v7 hub/scope API
function tagRequest(userId, region) {
  const hub = Sentry.getCurrentHub();
  hub.configureScope((scope) => {
    scope.setTag('region', region);
    scope.setUser({ id: userId });
  });
}

function isolatedCapture(err, context) {
  Sentry.configureScope((scope) => {
    scope.setExtra('context', context);
  });
  Sentry.captureException(err);
}

module.exports = { tagRequest, isolatedCapture };
```

### `tests/fixtures/sentry_v7_project/src/breadcrumbs.js`
```javascript
const Sentry = require('@sentry/node');

function trackAction(action, userId) {
  Sentry.addBreadcrumb({
    message: action,
    category: 'user.action',
    level: 'info',
    data: { userId }
  });
}

function reportError(err, userId, requestId) {
  Sentry.captureException(err, {
    extra: { requestId },
    user: { id: userId },
    tags: { component: 'checkout' }
  });
}

module.exports = { trackAction, reportError };
```

---

## Recommended Eval Cases (10 total)

| # | id | category | fixture | symbol | verified? |
|---|-----|----------|---------|--------|-----------|
| 1 | `sentry-v7-startTransaction-call-sites` | `call_sites` | `sentry_v7_project` | `sentry.startTransaction` | false |
| 2 | `sentry-v7-getCurrentHub-call-sites` | `call_sites` | `sentry_v7_project` | `sentry.getCurrentHub` | false |
| 3 | `sentry-v7-configureScope-call-sites` | `call_sites` | `sentry_v7_project` | `sentry.configureScope` | false |
| 4 | `sentry-v7-integrations-http-call-sites` | `call_sites` | `sentry_v7_project` | `sentry.Integrations.Http` | false |
| 5 | `sentry-v7-handlers-request-call-sites` | `call_sites` | `sentry_v7_project` | `sentry.Handlers.requestHandler` | false |
| 6 | `sentry-v7-startTransaction-fix` | `fix_generation` | `sentry_v7_project` | — | false |
| 7 | `sentry-v7-getCurrentHub-fix` | `fix_generation` | `sentry_v7_project` | — | false |
| 8 | `sentry-v7-integrations-http-fix` | `fix_generation` | `sentry_v7_project` | — | false |
| 9 | `sentry-v7-captureException-fix` | `fix_generation` | `sentry_v7_project` | — | false |
| 10 | `sentry-v7-startChild-call-sites` | `call_sites` | `sentry_v7_project` | `sentry.startTransaction.startChild` | false |

All `verified: false` until `make eval` confirms them passing.

---

## Notes for Implementer

1. **Create fixture first**: `tests/fixtures/sentry_v7_project/` with the 5 files above.
   Do NOT run `npm install` in the fixture — depfix fixtures are synthetic (just the source files).

2. **5 call_sites cases** are deterministic and will pass under `--no-llm`. Run `make eval` after
   adding them to see if they pass before adding the fix_generation cases.

3. **5 fix_generation cases** require LLM. Set `verified: false` for now — they can't be verified
   until a real LLM run confirms. This follows the same pattern as `openai-node-v4-fixes.yaml`.

4. **Breaking changes** for fix_generation cases: use `old_version: "7.119.0"` and
   `new_version: "8.0.0"` (the versions already in the DB at ids 4379, 4380).

5. **The sentry-v6-app fixtures** (`depfix-test-sentry-v6-app`) test v10→v11, not v7→v8.
   The new cases are separate from those.

6. **Provider skill file**: `provider_sentry.md` already lists `sentry.startTransaction` as a
   call site pattern. No changes needed to the skill file for these eval cases.
