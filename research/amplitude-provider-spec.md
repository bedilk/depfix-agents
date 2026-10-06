# Amplitude Provider Implementation Spec

**Status:** Ready for implementer  
**Date:** 2026-10-06  
**Researcher:** researcher agent  
**Source tasks:** T-8 (priority ranking), proactive work round 19  
**Priority:** ~22M combined npm+pypi downloads/month; dominant analytics SDK with a mass package-rename migration still in progress (1.1M/month still on legacy `amplitude-js`)

---

## Overview

Amplitude is the leading product analytics platform. Its SDKs appear in nearly every web application that tracks user events. The two most valuable depfix use cases are:

1. **Package rename detection**: `amplitude-js` → `@amplitude/analytics-browser` (2022). Over 1.1M downloads/month still happen on the old package. This is the single highest-value intervention depfix can make for Amplitude users.
2. **API method renames**: The new SDK replaced `logEvent()` → `track()`, `logRevenue()` → `revenue()`, `setUserProperties()` → `identify()` with Identify class. Every codebase that migrated the package name still has old API calls that now throw.

---

## Download Counts (verified 2026-10-06)

| Package | Ecosystem | Monthly downloads | Latest version |
|---|---|---|---|
| `@amplitude/analytics-browser` | npm | **10,157,146** | v2.47.2 |
| `amplitude-analytics` | pypi | **7,325,032** | v1.2.3 |
| `@amplitude/analytics-node` | npm | **4,439,911** | v1.5.76 |
| `amplitude-js` | npm (legacy) | **1,145,277** | v8.21.10 |
| `@amplitude/analytics-react-native` | npm | **923,430** | v1.x |
| `amplitude-api` | rubygems | 3,689,860 total | v0.4.2 |

**Total npm/month (all packages):** ~16.7M  
**Combined npm + pypi/month:** ~22M

**Verification commands:**
```bash
curl -s "https://api.npmjs.org/downloads/point/last-month/@amplitude%2Fanalytics-browser"
# {"downloads":10157146,...}

curl -s "https://api.npmjs.org/downloads/point/last-month/amplitude-js"
# {"downloads":1145277,...}

curl -s "https://pypistats.org/api/packages/amplitude-analytics/recent"
# {"data":{"last_month":7325032,...}}
```

---

## Ecosystem Notes

### JavaScript (npm)
Two distinct SDK generations co-exist:

**Legacy SDK (still widely used):**
- Package: `amplitude-js` (v8.21.10, last feature release 2022, still getting security patches)
- Import: `import amplitude from 'amplitude-js'`
- Usage pattern: `amplitude.getInstance().init(API_KEY)` / `amplitude.getInstance().logEvent(name, props)`

**New SDK (current):**
- Package: `@amplitude/analytics-browser` (browser), `@amplitude/analytics-node` (server)
- Import: `import * as amplitude from '@amplitude/analytics-browser'`
- Usage pattern: `amplitude.init(API_KEY)` / `amplitude.track(name, props)`

### Python
- Package: `amplitude-analytics` (v1.2.3) — the official Amplitude Python SDK
- Import: `from amplitude import Amplitude, BaseEvent, Identify`
- No Python module name mismatch — `amplitude-analytics` imports as `amplitude`

### Ruby
- `amplitude-api` (v0.4.2, 3.69M total downloads) — third-party gem, minimal Amplitude support
- Low priority; Ruby coverage adds marginal value here

---

## Critical Breaking Changes

### 1. Package rename: `amplitude-js` → `@amplitude/analytics-browser` (2022)

The biggest migration in Amplitude's history. The entire API was redesigned.

**Old (amplitude-js v8.x):**
```javascript
import amplitude from 'amplitude-js';
amplitude.getInstance().init('API_KEY', null, { includeReferrer: true });
amplitude.getInstance().logEvent('Button Clicked', { color: 'red' });
amplitude.getInstance().setUserId('user@example.com');
amplitude.getInstance().setUserProperties({ plan: 'premium' });
amplitude.getInstance().clearUserProperties();
amplitude.getInstance().logRevenue(9.99, 1, 'prod_123');
amplitude.getInstance().regenerateDeviceId();
```

**New (@amplitude/analytics-browser v2.x):**
```javascript
import * as amplitude from '@amplitude/analytics-browser';
amplitude.init('API_KEY', { defaultTracking: { pageViews: true } });
amplitude.track('Button Clicked', { color: 'red' });
amplitude.setUserId('user@example.com');
const identifyEvent = new amplitude.Identify();
identifyEvent.set('plan', 'premium');
amplitude.identify(identifyEvent);
// clearUserProperties → identifyEvent.clearAll()
const revenue = new amplitude.Revenue().setPrice(9.99).setProductId('prod_123');
amplitude.revenue(revenue);
amplitude.setDeviceId(amplitude.createDeviceId());
```

**Detectable call sites for depfix:**
- `amplitude.getInstance()` — removed, no equivalent singleton
- `amplitude.getInstance().logEvent(` — old pattern → `amplitude.track(`
- `amplitude.getInstance().setUserProperties(` — old pattern → `amplitude.identify(new Identify().set(...))`
- `amplitude.getInstance().clearUserProperties(` → `amplitude.identify(new Identify().clearAll())`
- `amplitude.getInstance().logRevenue(` → `amplitude.revenue(new Revenue()...)`
- `amplitude.getInstance().regenerateDeviceId(` → `amplitude.setDeviceId(amplitude.createDeviceId())`

### 2. Method rename: `logEvent()` → `track()` (within new SDK)

For users who installed `@amplitude/analytics-browser` but have old code patterns:

```javascript
// Old (amplitude-js style imported into new SDK context)
amplitude.logEvent('Page View', { page: '/home' });  // TypeError: not a function

// New
amplitude.track('Page View', { page: '/home' });
```

### 3. setUserProperties() removed — requires Identify class

```javascript
// Old
amplitude.setUserProperties({ plan: 'free', age: 25 });

// New
const identify = new amplitude.Identify();
identify.set('plan', 'free');
identify.set('age', 25);
amplitude.identify(identify);
```

### 4. logRevenue() replaced with Revenue builder pattern

```javascript
// Old
amplitude.logRevenue(9.99, 1, 'prod_abc');

// New
const revenue = new amplitude.Revenue()
  .setPrice(9.99)
  .setQuantity(1)
  .setProductId('prod_abc');
amplitude.revenue(revenue);
```

### 5. Node SDK: server-side tracking API change

**Old (@amplitude/node v1, deprecated):**
```javascript
const { Amplitude } = require('@amplitude/node');
const client = new Amplitude('API_KEY');
client.logEvent({ event_type: 'Sign Up', user_id: 'user@example.com' });
```

**New (@amplitude/analytics-node v1.x):**
```javascript
import * as amplitude from '@amplitude/analytics-node';
amplitude.init('API_KEY');
amplitude.track('Sign Up', undefined, { user_id: 'user@example.com' });
```

**Detectable call sites:**
- `new Amplitude(` (from @amplitude/node) — removed
- `client.logEvent(` (from @amplitude/node) — removed

### 6. Python: `amplitude` legacy → `amplitude-analytics` (2022)

```python
# Old (amplitude-py, unofficial)
import amplitude
amplitude.api_key = 'API_KEY'
amplitude.track(amplitude.Event(user_id='123', event_type='Sign Up'))

# New (amplitude-analytics, official)
from amplitude import Amplitude, BaseEvent
client = Amplitude('API_KEY')
client.track(BaseEvent(event_type='Sign Up', user_id='123'))
```

---

## providers.yaml Entry

```yaml
- id: amplitude
  name: Amplitude
  api_version_scheme: semver
  sdk_packages:
  - name: '@amplitude/analytics-browser'
    ecosystem: npm
  - name: '@amplitude/analytics-node'
    ecosystem: npm
  - name: amplitude-js
    ecosystem: npm
    deprecated: true
    successor: '@amplitude/analytics-browser'
  - name: amplitude-analytics
    ecosystem: pypi
  feeds:
  - kind: npm_dist_tag
    package: '@amplitude/analytics-browser'
    dist_tag: latest
    github_repo: amplitude/Amplitude-TypeScript
  - kind: npm_dist_tag
    package: '@amplitude/analytics-node'
    dist_tag: latest
    github_repo: amplitude/Amplitude-TypeScript
  - kind: pypi_dist_tag
    package: amplitude-analytics
    github_repo: amplitude/Amplitude-Python
  - kind: github_release
    repo: amplitude/Amplitude-TypeScript
  - kind: security_advisory
    package: '@amplitude/analytics-browser'
    ecosystem: npm
  - kind: ts_exports_diff
    package: '@amplitude/analytics-browser'
  - kind: ts_exports_diff
    package: '@amplitude/analytics-node'
```

---

## Provider Skill File Outline

`src/depfix/providers/skills/provider_amplitude.md`

Key patterns to document:
1. Legacy `amplitude-js` usage — how `getInstance()` singleton worked
2. New module-level API — `amplitude.init()`, `amplitude.track()`, etc.
3. Identify class pattern — `new Identify().set(key, value)`
4. Revenue class pattern — `new Revenue().setPrice(...)`
5. Common migration mistakes — calling `logEvent` on new SDK instance (TypeError silently swallowed in some configurations)
6. Python SDK — `amplitude-analytics` package, `Amplitude` class, `BaseEvent`

---

## Seed Repo Fixture

Create `bedilk/seed-amplitude-legacymigration` with:

**package.json:**
```json
{
  "dependencies": {
    "amplitude-js": "^8.0.0"
  }
}
```

**src/analytics.js:**
```javascript
import amplitude from 'amplitude-js';

export function initAnalytics() {
  amplitude.getInstance().init('YOUR_API_KEY', null, {
    includeReferrer: true,
    includeUtm: true,
  });
}

export function trackEvent(eventName, properties = {}) {
  amplitude.getInstance().logEvent(eventName, properties);
}

export function identifyUser(userId, userProperties = {}) {
  amplitude.getInstance().setUserId(userId);
  amplitude.getInstance().setUserProperties(userProperties);
}

export function trackRevenue(price, quantity, productId) {
  amplitude.getInstance().logRevenue(price, quantity, productId);
}
```

**Expected depfix output:**
- 4 call sites: `getInstance().logEvent`, `getInstance().setUserProperties`, `getInstance().logRevenue`, `getInstance().init`
- Breaking change: `amplitude-js@8` → `@amplitude/analytics-browser@2` — all methods removed
- Fix: rename package + rewrite all 4 call sites to new API

---

## Implementer Checklist

- [ ] Add `amplitude` entry to `providers.yaml` with all packages listed above
- [ ] Create `src/depfix/providers/skills/provider_amplitude.md` modelled on `provider_sentry.md`
- [ ] Add import patterns to scanner: `amplitude.getInstance()`, `import amplitude from 'amplitude-js'`, `import * as amplitude from '@amplitude/analytics-browser'`
- [ ] Add Python patterns: `from amplitude import`, `amplitude.Amplitude(`
- [ ] Add breaking change entries for `logEvent` → `track`, `setUserProperties` → `identify(new Identify())`, `logRevenue` → `revenue(new Revenue())`
- [ ] Consider `deprecated: true` flag on `amplitude-js` package entry — the old SDK is still maintained but Amplitude officially recommends migration
- [ ] `make test` passes after adding provider

---

## Recommended Add Order

Given the 22M/month combined downloads and the large cohort still on legacy `amplitude-js` (1.1M/month), Amplitude ranks as **#3 priority** after Resend and Cloudflare — both already have specs written. The package-rename migration makes this especially valuable: depfix can automatically detect `amplitude-js` usage and generate the full migration to `@amplitude/analytics-browser`.
