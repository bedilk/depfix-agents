# Segment (Twilio Segment) Provider Implementation Spec

**Status:** Ready for implementer  
**Date:** 2026-10-06  
**Researcher:** researcher agent  
**Source tasks:** T-8 (priority ranking — #4 candidate by volume), proactive work round 13  
**Priority:** 10.5M npm/month for `@segment/analytics-node` + 2.7M/month still on old `analytics-node`; 3.4M/month pypi `segment-analytics-python` + 1.5M/month still on old `analytics-python`; widely used in mid-to-large companies as the standard CDP

---

## Overview

Segment (now Twilio Segment) is the dominant Customer Data Platform (CDP). Its analytics SDKs instrument every `track`, `identify`, `page`, and `group` call in a codebase. Two SDK generations exist simultaneously:

| Generation | npm | pypi | status |
|---|---|---|---|
| Old (pre-2023) | `analytics-node` v6.2.0 | `analytics-python` v1.4.post1 | Not deprecated on npm/pypi but unmaintained |
| New (current) | `@segment/analytics-node` v3.1.0 | `segment-analytics-python` v2.4.0 | Actively maintained |

The migration from old to new packages is itself a breaking change: different package names, different import patterns, different constructor signatures, different Node.js/Python version requirements. Many codebases (2.7M/month npm, 1.5M/month pypi) are still on the old packages.

**depfix opportunity:** Detect codebases on `analytics-node` v6 and flag the package rename migration. Track breaking changes in `@segment/analytics-node` v1→v2→v3 for codebases already on the new package.

| Field | Value |
|---|---|
| npm (new, Node.js) | `@segment/analytics-node` |
| npm (old, Node.js) | `analytics-node` |
| npm (browser) | `@segment/analytics-next` |
| pypi (new) | `segment-analytics-python` |
| pypi (old) | `analytics-python` |
| rubygems | `analytics-ruby` |
| npm downloads/month | **10,541,521** (`@segment/analytics-node`) + **2,677,936** (`analytics-node`) + **8,328,751** (`@segment/analytics-next`) |
| pypi downloads/month | **3,444,016** (`segment-analytics-python`) + **1,507,499** (`analytics-python`) |
| rubygems total downloads | **45,202,450** (`analytics-ruby`) |
| OpenAPI spec | None |
| GitHub monorepo | `segmentio/analytics-next` |
| GitHub old Node.js repo | `segmentio/analytics-node` (archived) |
| api_version_scheme | `semver` |
| Feed types | `npm_dist_tag`, `pypi_dist_tag`, `github_release`, `ts_exports_diff` |

---

## Breaking Change History

### `@segment/analytics-node` (new scoped package)

| Version | Date | Breaking Changes |
|---|---|---|
| v3.0.0 | 2026-03-04 | **Removed `node-fetch` dependency** in favor of native `globalThis.fetch` (available since Node 18, but package now requires >=20). Any custom `httpClient` wrappers around `node-fetch` break. |
| v2.3.0 | 2025-07-09 | **Node.js minimum raised to ^20** across all packages (was >=18 for v2.0.0). Codebases on Node 18 must upgrade runtime. |
| v2.0.0 | 2024-01-29 | **Removed Node.js 14 and 16 support** (both EOL). Requires Node.js >=18. |
| v1.2.0 | 2024-01-08 | `maxEventsInBatch` **deprecated** (removed in v2) in favor of `flushAt`; config objects using `maxEventsInBatch` need updating. |

### `analytics-node` → `@segment/analytics-node` migration (the key breaking change)

The old `analytics-node` (unscoped) reached v6.2.0 in 2022 and is now unmaintained. The new `@segment/analytics-node` is a ground-up rewrite with incompatible API:

| Old (`analytics-node` v6) | New (`@segment/analytics-node` v1+) |
|---|---|
| `const Analytics = require('analytics-node')` | `import { Analytics } from '@segment/analytics-node'` |
| `new Analytics(writeKey, options)` | `new Analytics({ writeKey: '...' })` |
| `analytics.flush(callback)` | `analytics.flush()` returns Promise |
| Callback-based API throughout | Promise-based API throughout |
| Node.js >=12 | Node.js >=20 (as of v3) |

### `@segment/analytics-next` (browser SDK)

| Version | Date | Breaking Changes |
|---|---|---|
| v1.84.3 | 2026-09-11 | Removed `resolveAnonymousIdConflicts` opt-in option (added in v1.84.2); behavior is now always-on default. Codebases setting `resolveAnonymousIdConflicts: false` will silently change behavior. |

### Python SDK

The pypi package renamed from `analytics-python` to `segment-analytics-python`:

| Old (`analytics-python` v1) | New (`segment-analytics-python` v2) |
|---|---|
| `import analytics` | `from segment.analytics import Client` |
| Global `analytics.write_key = 'xxx'` | `client = Client(write_key='xxx')` |
| Python >=3.6 | Python >=3.9 (v2.4.0) |

---

## providers.yaml Block

```yaml
- id: segment
  name: Twilio Segment SDK (analytics-node + analytics-next)
  api_version_scheme: semver
  sdk_packages:
  - name: "@segment/analytics-node"
    ecosystem: npm
  - name: analytics-node
    ecosystem: npm
  - name: "@segment/analytics-next"
    ecosystem: npm
  - name: segment-analytics-python
    ecosystem: pypi
  - name: analytics-python
    ecosystem: pypi
  - name: analytics-ruby
    ecosystem: rubygems
  feeds:
  - kind: npm_dist_tag
    package: "@segment/analytics-node"
    dist_tag: latest
    github_repo: segmentio/analytics-next
  - kind: npm_dist_tag
    package: "@segment/analytics-next"
    dist_tag: latest
    github_repo: segmentio/analytics-next
  - kind: pypi_dist_tag
    package: segment-analytics-python
    github_repo: segmentio/analytics-python
  - kind: github_release
    repo: segmentio/analytics-next
  - kind: security_advisory
    package: "@segment/analytics-node"
    ecosystem: npm
  - kind: security_advisory
    package: segment-analytics-python
    ecosystem: pypi
  - kind: ts_exports_diff
    package: "@segment/analytics-node"
```

---

## Skill File: `provider_segment.md`

```markdown
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
- `analytics.track(...)`, `analytics.identify(...)`, `analytics.page(...)`, `analytics.group(...)`, `analytics.screen(...)`, `analytics.alias(...)`
- `analytics.flush(...)` — version-sensitive (Promise vs callback)
- `httpConfig` option usage

### Old analytics-node (flag for migration)
- `new Analytics(writeKey, ...)` — old positional constructor
- `analytics.flush(callback)` — old callback-based flush

### Browser analytics-next
- `AnalyticsBrowser.load({ writeKey: ... })`
- `analytics.track(...)`, `analytics.identify(...)`, `analytics.page(...)`

## Where to look first
1. `grep("@segment/analytics", "")` or `grep("analytics-node", "")` — package names are distinctive.
2. Analytics init is usually in a single file (`analytics.ts`, `segment.ts`, `tracking.ts`, `telemetry.ts`).
3. `package.json` — check for `"analytics-node"` (old) vs `"@segment/analytics-node"` (new) to identify which generation is in use.
```

---

## Known Breaking Change Entries for Corpus

These are the highest-confidence breaking changes depfix should understand:

### BC-1: `analytics-node` → `@segment/analytics-node` package rename

```yaml
change_type: RENAMED
old_symbol: analytics-node
new_symbol: "@segment/analytics-node"
description: "Legacy `analytics-node` package replaced by `@segment/analytics-node`. Different constructor signature: new Analytics(writeKey) → new Analytics({ writeKey })."
source: github_release
provider: segment
since_version: "1.0.0"
```

### BC-2: `maxEventsInBatch` config option removed

```yaml
change_type: REMOVED
old_symbol: maxEventsInBatch
description: "Config option `maxEventsInBatch` removed in v2.0.0; use `flushAt` instead."
source: github_release
provider: segment
since_version: "2.0.0"
```

### BC-3: Node.js minimum raised to v20 (v3.0.0)

```yaml
change_type: CHANGED
old_symbol: node-fetch
description: "In v3.0.0, `node-fetch` dependency removed in favor of native globalThis.fetch. Node.js >=20 required. Custom httpClient wrappers around node-fetch break."
source: github_release
provider: segment
since_version: "3.0.0"
```

### BC-4: Python `analytics-python` → `segment-analytics-python`

```yaml
change_type: RENAMED
old_symbol: analytics-python
new_symbol: segment-analytics-python
description: "Legacy `analytics-python` package replaced by `segment-analytics-python`. API changed from global `analytics.write_key = 'x'` to `Client(write_key='x')`."
source: github_release
provider: segment
since_version: "2.0.0"
```

---

## Seed Repo Fixture

**Suggested fixture:** `bedilk/seed-segment-v6-to-v3`

```
# package.json (old)
{
  "dependencies": {
    "analytics-node": "^6.0.0"
  }
}

# analytics.js (old pattern — should be flagged)
const Analytics = require('analytics-node')
const analytics = new Analytics(process.env.SEGMENT_WRITE_KEY)

analytics.track({
  userId: 'user123',
  event: 'Button Clicked',
  properties: { plan: 'free' }
})

analytics.flush(function(err, batch) {
  console.log('Flushed, batch', batch.batch)
})
```

**Expected depfix output:**
- Version drift: `analytics-node` 6.x detected, `@segment/analytics-node` 3.x available (package rename)
- 3 call sites flagged: `new Analytics(writeKey)`, `analytics.track(...)`, `analytics.flush(callback)`
- Fix: migrate constructor to `new Analytics({ writeKey: ... })`, flush to return Promise

---

## Implementer Checklist

1. `providers.yaml`: Add the entry above. Note both `analytics-node` (old) and `@segment/analytics-node` (new) as SDK packages.
2. Create `src/depfix/providers/skills/provider_segment.md` with the skill file content above.
3. Run `make test` — provider count assertion will need updating (currently 27 → 28).
4. Optional: Add `research/segment-provider-spec.md` to `evidence_paths`.

---

## Scan Detection Strategy

The key challenge is detecting both the old and new packages. The scanner must:

1. **Detect `analytics-node` (old)** — pattern: `require('analytics-node')` or `from analytics import` (Python). Flag as: "legacy Segment SDK — migrate to `@segment/analytics-node`".

2. **Detect `@segment/analytics-node` (new)** — pattern: `from '@segment/analytics-node'`. Scan for version drift and breaking API changes.

3. **Multi-package consideration:** A codebase in mid-migration may import BOTH `analytics-node` AND `@segment/analytics-node`. depfix should report both and not deduplicate.

4. **Browser vs Node.js:** `@segment/analytics-next` is browser-side. Its call sites are typically in frontend components (`analytics.track('Button Clicked', { ... })`). These are separate from Node.js backend usage.

---

## Download Count Verification

Commands run to verify download counts (2026-09-05 to 2026-10-04):

```bash
curl -s "https://api.npmjs.org/downloads/point/last-month/@segment/analytics-node"
# {"downloads":10541521}

curl -s "https://api.npmjs.org/downloads/point/last-month/analytics-node"
# {"downloads":2677936}

curl -s "https://api.npmjs.org/downloads/point/last-month/@segment/analytics-next"
# {"downloads":8328751}

curl -s "https://pypistats.org/api/packages/segment-analytics-python/recent"
# {"data":{"last_month":3444016}}

curl -s "https://pypistats.org/api/packages/analytics-python/recent"
# last_month: 1507499
```

---

*Recommended add priority: #4 after Resend, Cloudflare, Datadog (research/top-providers-by-breakage.md)*  
*See: research/resend-provider-spec.md, research/cloudflare-provider-spec.md, research/datadog-provider-spec.md*
