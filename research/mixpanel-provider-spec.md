# Mixpanel Provider Implementation Spec

**Status:** Ready for implementer  
**Date:** 2026-10-06  
**Researcher:** researcher agent  
**Source tasks:** T-8 (priority ranking — #7 candidate by volume), proactive work round 15  
**Priority:** 5.4M npm/month for server-side `mixpanel` + 10.5M npm/month for `mixpanel-browser`; ubiquitous event analytics SDK in SaaS and consumer products

---

## Overview

Mixpanel is one of the most widely used product analytics platforms. Its SDK instruments every `track`, `identify`, `people.set`, and `alias` call in a codebase. There are two distinct npm packages:

| Package | Use case | npm/month | Current version |
|---|---|---|---|
| `mixpanel` | Server-side Node.js | 5,406,248 | v0.24.0 |
| `mixpanel-browser` | Client-side browser | 10,519,651 | v2.83.0 |
| `mixpanel` (pypi) | Python (server) | ~1M (rate limited at time of check) | v5.4.0 |
| `mixpanel-ruby` (rubygems) | Ruby (server) | 22,268,331 total downloads | v3.4.0 |

**depfix opportunity:** Three active SDK ecosystems with documented breaking changes every 1–2 major versions. The Python v5 upgrade is a notable breaking change (Python 2/3.x compatibility dropped). The browser SDK ships behavioral breaking changes in minor versions (UTM persistence, `track_charge` removal).

| Field | Value |
|---|---|
| npm (server, Node.js) | `mixpanel` |
| npm (browser) | `mixpanel-browser` |
| pypi | `mixpanel` |
| rubygems | `mixpanel-ruby` |
| npm (server) downloads/month | **5,406,248** |
| npm (browser) downloads/month | **10,519,651** |
| rubygems total downloads | **22,268,331** |
| OpenAPI spec | **None** |
| GitHub (Node.js) | `mixpanel/mixpanel-node` |
| GitHub (browser) | `mixpanel/mixpanel-js` |
| GitHub (Python) | `mixpanel/mixpanel-python` |
| GitHub (Ruby) | `mixpanel/mixpanel-ruby` |
| api_version_scheme | `semver` |
| Feed types | `npm_dist_tag`, `pypi_dist_tag`, `rubygems_dist_tag`, `github_release`, `ts_exports_diff` |

---

## Breaking Change History

### `mixpanel` npm (server-side Node.js SDK)

| Version | Date | Breaking Changes |
|---|---|---|
| v0.18.0 | 2023-09-12 | **Removed long-deprecated `Client` initializer**. Codebases using `new Mixpanel.Client(token, options)` must migrate to `Mixpanel.init(token, options)`. |

The `Client` constructor was deprecated many versions prior; v0.18.0 is the actual removal. Any codebase still using the old `Client` form will throw a runtime error after upgrade.

### `mixpanel-browser` (browser SDK)

| Version | Date | Breaking Changes |
|---|---|---|
| v2.65.0 | 2025-05-20 | **`mixpanel.people.track_charge()` is now a no-op.** Only prints a console error; no profile property is set and no network call is made. Mixpanel Revenue analysis UI was replaced by a newer suite. Codebases calling `track_charge()` silently stop recording revenue. |
| v2.56.0 | 2024-11-12 | **`record_inline_images` config option removed** (session recording). Codebases setting this option get no warning and the option is silently ignored. |
| v2.51.0 | 2024-05-30 | **UTM parameters no longer persisted as superproperties by default.** Codebases relying on `$initial_utm_source`, `$initial_utm_campaign`, etc. being automatically added to user profiles will lose that data unless they set `{stop_utm_persistence: false}` in init options. This is a silent behavioral breaking change. |
| v2.45.0 | 2022-02-18 | **In-app notifications API removed** (after 1.5-year deprecation). The SDK no longer calls the `/decide` endpoint. Any code checking Mixpanel's notification campaigns will stop working. |

### Python SDK (`mixpanel` pypi)

| Version | Date | Breaking Changes |
|---|---|---|
| v5.0.0 | 2025-11-04 | **Python minimum version bumped to >=3.9** (was `>=2.7, !=3.4.*`). Codebases running Python 2.7, 3.5, 3.6, 3.7, or 3.8 cannot upgrade to v5.x. Feature flags API added as new top-level functionality. |
| v4.11.0 | 2025-08-25 | Deprecated Python 2.7 and EOL 3.x versions in metadata; migrated to `pyproject.toml`. |

### Ruby SDK (`mixpanel-ruby` rubygems)

| Version | Date | Breaking Changes |
|---|---|---|
| v3.0.0 | 2026-01-05 | **Feature flags provider added** (additive — no API removals). Codebases need to add the `MIXPANEL_PROJECT_TOKEN` flag to use the new feature. |
| v2.3.1 | 2025-12-09 | **Event timestamps now sent in milliseconds** (previously seconds). Codebases that manually compare timestamps from Mixpanel API responses against local time calculations will need to divide by 1000. |

---

## providers.yaml Block

```yaml
- id: mixpanel
  name: Mixpanel Analytics SDK
  api_version_scheme: semver
  sdk_packages:
  - name: mixpanel
    ecosystem: npm
  - name: mixpanel-browser
    ecosystem: npm
  - name: mixpanel
    ecosystem: pypi
  - name: mixpanel-ruby
    ecosystem: rubygems
  feeds:
  - kind: npm_dist_tag
    package: mixpanel
    dist_tag: latest
    github_repo: mixpanel/mixpanel-node
  - kind: npm_dist_tag
    package: mixpanel-browser
    dist_tag: latest
    github_repo: mixpanel/mixpanel-js
  - kind: pypi_dist_tag
    package: mixpanel
    github_repo: mixpanel/mixpanel-python
  - kind: rubygems_dist_tag
    gem: mixpanel-ruby
    github_repo: mixpanel/mixpanel-ruby
  - kind: github_release
    repo: mixpanel/mixpanel-node
  - kind: github_release
    repo: mixpanel/mixpanel-js
  - kind: security_advisory
    package: mixpanel
    ecosystem: npm
  - kind: security_advisory
    package: mixpanel-browser
    ecosystem: npm
  - kind: security_advisory
    package: mixpanel
    ecosystem: pypi
  - kind: ts_exports_diff
    package: mixpanel-browser
```

---

## Skill File: `provider_mixpanel.md`

```markdown
# Mixpanel scan skill

## SDK packages
- npm (server-side): `mixpanel`
- npm (browser): `mixpanel-browser`
- pypi: `mixpanel`
- rubygems: `mixpanel-ruby`

## Import patterns

### Node.js (server-side)
```
const Mixpanel = require('mixpanel')
const mixpanel = Mixpanel.init('TOKEN')
import Mixpanel from 'mixpanel'
```

### Browser
```
import mixpanel from 'mixpanel-browser'
const { mixpanel } = require('mixpanel-browser')
mixpanel.init('TOKEN', { ... })
```

### Python
```python
import mixpanel
from mixpanel import Mixpanel
mp = Mixpanel('TOKEN')
```

### Ruby
```ruby
require 'mixpanel-ruby'
tracker = Mixpanel::Tracker.new('TOKEN')
```

## Call sites (report these)
### Server-side Node.js
- `Mixpanel.init(...)` — initialization
- `mixpanel.track(...)` — event tracking
- `mixpanel.identify(...)`, `mixpanel.alias(...)`
- `mixpanel.people.set(...)`, `mixpanel.people.set_once(...)`
- `mixpanel.people.track_charge(...)` — REMOVED in v2.65.0 (browser) — flag as no-op
- `new Mixpanel.Client(...)` — REMOVED in v0.18.0 — flag for migration to Mixpanel.init()

### Browser
- `mixpanel.init(...)` — check for `stop_utm_persistence` option
- `mixpanel.track(...)`, `mixpanel.identify(...)`, `mixpanel.alias(...)`
- `mixpanel.people.track_charge(...)` — REMOVED in v2.65.0
- Init option `record_inline_images` — REMOVED in v2.56.0
- Init option `stop_utm_persistence` — changed behavior in v2.51.0

## Where to look first
1. `grep("require('mixpanel", "")` or `grep("from 'mixpanel", "")` — package name is plain `mixpanel`.
2. `grep("Mixpanel.init", "")` or `grep("mixpanel.init", "")` — initialization is in one file.
3. `package.json`/`Gemfile` — check whether `mixpanel` or `mixpanel-browser` is present.
4. For Python: `grep("from mixpanel import", "")` or `grep("import mixpanel", "")`.
```

---

## Known Breaking Change Entries for Corpus

### BC-1: `Client` constructor removed in Node.js SDK v0.18.0

```yaml
change_type: REMOVED
old_symbol: Mixpanel.Client
description: "Long-deprecated `new Mixpanel.Client(token, options)` initializer removed in v0.18.0. Use `Mixpanel.init(token, options)` instead."
source: github_release
provider: mixpanel
since_version: "0.18.0"
```

### BC-2: `mixpanel.people.track_charge()` now a no-op (browser v2.65.0)

```yaml
change_type: REMOVED
old_symbol: mixpanel.people.track_charge
description: "`mixpanel.people.track_charge()` is now a no-op in v2.65.0 — only prints a console error. Mixpanel Revenue analysis removed from the platform. Call sites should be removed or replaced."
source: github_release
provider: mixpanel
since_version: "2.65.0"
```

### BC-3: `record_inline_images` config option removed (browser v2.56.0)

```yaml
change_type: REMOVED
old_symbol: record_inline_images
description: "Session recording configuration option `record_inline_images` removed in v2.56.0 due to buggy behavior in the rrweb library. Silently ignored if present."
source: github_release
provider: mixpanel
since_version: "2.56.0"
```

### BC-4: UTM parameters no longer persisted by default (browser v2.51.0)

```yaml
change_type: CHANGED
old_symbol: stop_utm_persistence
description: "UTM parameters (`$initial_utm_source`, `$initial_utm_campaign`, etc.) are no longer persisted as superproperties by default since v2.51.0. Opt in to old behavior with `{stop_utm_persistence: false}` in mixpanel.init()."
source: github_release
provider: mixpanel
since_version: "2.51.0"
```

### BC-5: Python minimum version raised to 3.9 (pypi v5.0.0)

```yaml
change_type: CHANGED
old_symbol: python_requires
description: "Python minimum version raised to >=3.9 in mixpanel v5.0.0 (was >=2.7). Codebases on Python 2.7 or 3.5–3.8 cannot upgrade to v5.x."
source: github_release
provider: mixpanel
since_version: "5.0.0"
```

### BC-6: Ruby timestamps now in milliseconds (mixpanel-ruby v2.3.1)

```yaml
change_type: CHANGED
old_symbol: Mixpanel::Tracker#track
description: "Event and people-update timestamps are now sent in milliseconds (previously seconds) in mixpanel-ruby v2.3.1. Code comparing Mixpanel API timestamps against local time values must divide by 1000."
source: github_release
provider: mixpanel
since_version: "2.3.1"
```

---

## Seed Repo Fixture

**Suggested fixture:** `bedilk/seed-mixpanel-browser-v2`

```
# package.json
{
  "dependencies": {
    "mixpanel-browser": "^2.50.0"
  }
}

# analytics.js — uses removed track_charge and old UTM behavior
import mixpanel from 'mixpanel-browser'

mixpanel.init('TOKEN', {
  stop_utm_persistence: true,    // removed default behavior
  record_inline_images: true,    // removed option
})

mixpanel.track('Page Viewed', { page: 'home' })

// Revenue tracking — becomes no-op in v2.65.0
mixpanel.people.track_charge(29.99, {
  $time: new Date()
})
```

**Expected depfix output:**
- Version drift: `mixpanel-browser` 2.50.x → 2.83.x (minor bump)
- 3 call sites flagged: `record_inline_images` (removed), `track_charge` (no-op), UTM behavior change
- Fix: remove `record_inline_images`, remove `track_charge` call, add comment about UTM change

---

## Implementer Checklist

1. `providers.yaml`: Add the entry above. Note both `mixpanel` (npm, server) and `mixpanel-browser` (npm, browser) as SDK packages.
2. Create `src/depfix/providers/skills/provider_mixpanel.md` with the skill file content above.
3. Run `make test` — provider count assertion will need updating (currently 27+N → 28+N).
4. No OpenAPI spec available — use `github_release` + `ts_exports_diff` feeds.
5. Optional: Add `research/mixpanel-provider-spec.md` to `evidence_paths`.

---

## Scan Detection Strategy

Key challenge: the npm package `mixpanel` (server) is a plain unscoped name, identical to the pypi package name. The scanner must distinguish ecosystems by file context:

1. **Detect `mixpanel` in Node.js** — `require('mixpanel')` or `import ... from 'mixpanel'` in `.js/.ts` files, AND `"mixpanel"` in `package.json` dependencies.
2. **Detect `mixpanel-browser`** — `import mixpanel from 'mixpanel-browser'` or `"mixpanel-browser"` in `package.json`. Typically in frontend components.
3. **Python**: `import mixpanel` or `from mixpanel import Mixpanel` in `.py` files, AND `mixpanel` in `requirements.txt`/`Pipfile`.
4. **Ruby**: `require 'mixpanel-ruby'` in `.rb` files, AND `gem 'mixpanel-ruby'` in `Gemfile`.

---

## Download Count Verification

```bash
curl -s "https://api.npmjs.org/downloads/point/last-month/mixpanel"
# {"downloads":5406248,"start":"2026-09-05","end":"2026-10-04","package":"mixpanel"}

curl -s "https://api.npmjs.org/downloads/point/last-month/mixpanel-browser"
# {"downloads":10519651,"start":"2026-09-05","end":"2026-10-04","package":"mixpanel-browser"}

curl -s "https://rubygems.org/api/v1/gems/mixpanel-ruby.json" | jq .downloads
# 22268331
```

---

*Recommended add priority: #7 after Resend, Cloudflare, Datadog, Plaid, HubSpot, Shopify (research/top-providers-by-breakage.md)*  
*See: research/resend-provider-spec.md, research/cloudflare-provider-spec.md, research/datadog-provider-spec.md, research/plaid-provider-spec.md, research/hubspot-provider-spec.md, research/shopify-provider-spec.md*
