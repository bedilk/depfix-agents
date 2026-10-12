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

bugsnag.configure(api_key="...")
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
- `bugsnag({ apiKey: ... })` — OLD factory call; removed in v7; use `Bugsnag.start({ apiKey: ... })`
- `bugsnagClient.notify(...)` — OLD instance call; prefer static `Bugsnag.notify(...)` from v7
- `new BugsnagPluginReact(React)` — pass no args in v7+
- `Bugsnag.getPlugin('react')` assigned directly — needs `.createErrorBoundary(React)` suffix from v7.1+
- Config key `notifyReleaseStages` — renamed to `enabledReleaseStages` in v7
- Config key `autoNotify` — renamed to `autoDetectErrors` in v7

### JS/TS v7 patterns (upgrade needed to v8+)
- `breadcrumb.metadata.request` — field renamed to `url`+`method` in v8 network breadcrumbs
- Partial `endpoints` config (only `notify` set) — silently drops all events+sessions in v8+

### Active call sites (all versions)
- `Bugsnag.start(...)` — initialization; check config options for deprecated keys
- `Bugsnag.notify(...)` — error reporting
- `Bugsnag.leaveBreadcrumb(...)` — manual breadcrumbs
- `Bugsnag.setUser(...)`, `Bugsnag.setContext(...)`
- `Bugsnag.addMetadata(...)`, `Bugsnag.getMetadata(...)`, `Bugsnag.clearMetadata(...)`
- `Bugsnag.startSession()`, `Bugsnag.pauseSession()`, `Bugsnag.resumeSession()`

## Where to look first
1. `grep("@bugsnag/", "")` — scoped package name finds both `@bugsnag/js` and `@bugsnag/node`.
2. `Bugsnag.start(...)` is almost always in a single setup file (`bugsnag.ts`, `instrumentation.ts`).
3. For v6 detection: grep for `bugsnag({` or `bugsnag(apiKey` — the old factory call pattern.
4. For React plugin: grep for `BugsnagPluginReact` — usage pattern distinguishes v7.0 from v7.1+.

## Breaking-change context

### v8.x → v9.x (2026-09-22) — React Native focus, no JS/Node API breaks
v9 is focused on React Native New Architecture (RN 0.84+) and Electron resilience. Core
browser and Node.js API is unchanged from v8.

### v7.x → v8.x (2024-08-29) — Node 12 minimum, breadcrumb field rename
- Node.js minimum raised to v12.17.0
- Network breadcrumb metadata: `request` field → `url` + `method` (silent undefined otherwise)
- Partial `endpoints` config: now drops ALL events+sessions if either endpoint missing
- `replaceState`/`pushState` no longer create new sessions (SPA session count drops)
- Uncaught exceptions in `plugin-contextualize` callbacks now terminate the process

### v6.x → v7.x — Full API rewrite (factory → static interface)
- `bugsnag(opts)` factory function removed → `Bugsnag.start(opts)` static interface
- `notifyReleaseStages` → `enabledReleaseStages` (silently ignored if not renamed)
- `autoNotify` → `autoDetectErrors` (silently ignored if not renamed)
- `new BugsnagPluginReact(React)` → `new BugsnagPluginReact()` (no React arg)
- `Bugsnag.getPlugin('react')` now returns plugin object; call `.createErrorBoundary(React)`

### Python SDK (`bugsnag` pypi)
Stable since v4.0.0. `bugsnag.configure()`, `bugsnag.notify()`, `bugsnag.before_notify()` unchanged.
Python 2 dropped in v4. Current minimum: Python >=3.5.

### Ruby SDK (`bugsnag` rubygems)
At v6.30.0. v6 series is very stable; no breaking changes since v5→v6.
v6.29.0 added Ruby 4 support.

## Anchors (fallback signals)
- Env vars: `BUGSNAG_API_KEY`
- Config patterns: `Bugsnag.start({`, `bugsnag.configure(api_key=`
- Init file patterns: `instrumentation.ts`, `bugsnag.ts`, `bugsnag.rb`
