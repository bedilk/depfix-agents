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

mp = Mixpanel("TOKEN")
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
- `mixpanel.people.track_charge(...)` — REMOVED in browser v2.65.0 — flag as no-op
- `new Mixpanel.Client(...)` — REMOVED in Node.js v0.18.0 — migrate to `Mixpanel.init()`

### Browser
- `mixpanel.init(...)` — check for `stop_utm_persistence` option
- `mixpanel.track(...)`, `mixpanel.identify(...)`, `mixpanel.alias(...)`
- `mixpanel.people.track_charge(...)` — REMOVED in v2.65.0
- Init option `record_inline_images` — REMOVED in v2.56.0
- Init option `stop_utm_persistence` — behavior changed in v2.51.0

## Where to look first
1. `grep("require('mixpanel", "")` or `grep("from 'mixpanel", "")` — package name is plain `mixpanel`.
2. `grep("Mixpanel.init", "")` or `grep("mixpanel.init", "")` — initialization is in one file.
3. `package.json`/`Gemfile` — check whether `mixpanel` or `mixpanel-browser` is present.
4. For Python: `grep("from mixpanel import", "")` or `grep("import mixpanel", "")`.
