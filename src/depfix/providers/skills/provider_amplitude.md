# Amplitude scan skill

## SDK packages
- npm (browser): `@amplitude/analytics-browser`
- npm (server): `@amplitude/analytics-node`
- npm (legacy): `amplitude-js` (deprecated — successor: `@amplitude/analytics-browser`)
- pypi: `amplitude-analytics`

## Import patterns

### Legacy SDK (amplitude-js v8.x — widely used, flag for migration)
```
import amplitude from 'amplitude-js'
const amplitude = require('amplitude-js')
amplitude.getInstance().init(API_KEY)
```

### New browser SDK (@amplitude/analytics-browser v2.x)
```
import * as amplitude from '@amplitude/analytics-browser'
amplitude.init(API_KEY)
```

### New Node SDK (@amplitude/analytics-node v1.x)
```
import * as amplitude from '@amplitude/analytics-node'
const amplitude = require('@amplitude/analytics-node')
amplitude.init(API_KEY)
```

### Python
```python
from amplitude import Amplitude, BaseEvent, Identify
client = Amplitude('API_KEY')
```

## Call sites (report these)

### Legacy amplitude-js — all removed in new SDK
- `amplitude.getInstance()` — removed; new SDK has no singleton pattern
- `amplitude.getInstance().logEvent(...)` → `amplitude.track(...)`
- `amplitude.getInstance().setUserProperties(...)` → `amplitude.identify(new Identify().set(...))`
- `amplitude.getInstance().clearUserProperties()` → `amplitude.identify(new Identify().clearAll())`
- `amplitude.getInstance().logRevenue(...)` → `amplitude.revenue(new Revenue()...)`
- `amplitude.getInstance().regenerateDeviceId()` → `amplitude.setDeviceId(amplitude.createDeviceId())`
- `amplitude.getInstance().setUserId(...)` → `amplitude.setUserId(...)`

### New SDK method renames (users who migrated package but not calls)
- `amplitude.logEvent(...)` → `amplitude.track(...)`
- `amplitude.setUserProperties(...)` → `amplitude.identify(new Identify().set(...))`

### Old @amplitude/node (deprecated server SDK)
- `new Amplitude(API_KEY)` → use `@amplitude/analytics-node` module-level API
- `client.logEvent({event_type: ...})` → `amplitude.track(...)`

## Where to look first
1. `grep("amplitude-js", "package.json")` — legacy package; always flag for migration.
2. `grep("getInstance()", "")` — dead giveaway for legacy amplitude-js usage.
3. `grep("@amplitude/analytics-browser", "package.json")` — new SDK import.
4. `grep("from amplitude import", "*.py")` or `grep("amplitude-analytics", "requirements.txt")` — Python SDK.
5. Analytics initialization files: `analytics.ts`, `amplitude.ts`, `tracking.js`, `events.ts`.
