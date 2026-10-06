# Segment scan skill

## SDK packages
- npm (current): `@segment/analytics-node`, `@segment/analytics-next`
- npm (legacy, flag for migration): `analytics-node`
- pypi (current): `segment-analytics-python`
- pypi (legacy, flag for migration): `analytics-python`
- rubygems: `analytics-ruby`

## Import patterns

### Node.js (new scoped package)
```
import { Analytics } from '@segment/analytics-node'
const { Analytics } = require('@segment/analytics-node')
```

### Node.js (old unscoped package — flag as migration target)
```
const Analytics = require('analytics-node')
import Analytics from 'analytics-node'
```

### Browser
```
import { AnalyticsBrowser } from '@segment/analytics-next'
const { AnalyticsBrowser } = require('@segment/analytics-next')
```

### Python (new)
```python
from segment.analytics import Client
import segment.analytics as analytics
```

### Python (old — flag as migration target)
```python
import analytics
from analytics import Client
```

## Call sites (report these)

### New analytics-node
- `new Analytics({ writeKey: ... })` — instantiation
- `analytics.track(...)`, `analytics.identify(...)`, `analytics.page(...)`, `analytics.group(...)`
- `analytics.screen(...)`, `analytics.alias(...)`
- `analytics.flush(...)` — version-sensitive (Promise vs callback)

### Old analytics-node (flag for migration)
- `new Analytics(writeKey, ...)` — old positional constructor
- `analytics.flush(callback)` — old callback-based flush

### Browser analytics-next
- `AnalyticsBrowser.load({ writeKey: ... })`
- `analytics.track(...)`, `analytics.identify(...)`, `analytics.page(...)`

## Where to look first
1. `grep("@segment/analytics", "")` or `grep("analytics-node", "")` — package names are distinctive.
2. Analytics init is usually in a single file (`analytics.ts`, `segment.ts`, `tracking.ts`, `telemetry.ts`).
3. `package.json` — check for `"analytics-node"` (old) vs `"@segment/analytics-node"` (new).

## Breaking-change context

### `analytics-node` → `@segment/analytics-node` (package rename migration)
Legacy `analytics-node` (unscoped, archived) reached v6.2.0 in 2022 and is now unmaintained.
The new `@segment/analytics-node` is a ground-up rewrite with incompatible API:
- Constructor: `new Analytics(writeKey)` → `new Analytics({ writeKey: '...' })`
- Flush: `analytics.flush(callback)` → `analytics.flush()` returns Promise
- Node.js minimum: >=12 → >=20 (as of v3)

### `@segment/analytics-node` v3.0.0 (2026-03-04) — Node 20 + native fetch
- `node-fetch` dependency removed in favor of native `globalThis.fetch`
- Node.js >=20 required (was >=18 for v2.0.0)
- Custom `httpClient` wrappers around `node-fetch` break

### `@segment/analytics-node` v2.3.0 (2025-07-09) — Node 20 minimum
- Node.js minimum raised to ^20 (was >=18 for v2.0.0)

### `@segment/analytics-node` v2.0.0 (2024-01-29) — Node 14/16 dropped
- Node.js 14 and 16 support removed (both EOL)
- `maxEventsInBatch` config option removed; use `flushAt` instead

### `@segment/analytics-next` v1.84.3 (2026-09-11) — minor-version breaking
- `resolveAnonymousIdConflicts` opt-in option removed (behavior now always-on default)
- Codebases setting `resolveAnonymousIdConflicts: false` silently change behavior

### Python: `analytics-python` → `segment-analytics-python` (package rename)
- Import changed: `import analytics` → `from segment.analytics import Client`
- Constructor: global `analytics.write_key = 'xxx'` → `client = Client(write_key='xxx')`
- Python minimum: >=3.9 (v2.4.0)

## Anchors (fallback signals)
- Env vars: `SEGMENT_WRITE_KEY`, `ANALYTICS_WRITE_KEY`
- Init patterns: `new Analytics({` (new), `new Analytics(process.env.` (old positional)
- Config patterns: `writeKey:`, `flushAt:`, `flushInterval:`
