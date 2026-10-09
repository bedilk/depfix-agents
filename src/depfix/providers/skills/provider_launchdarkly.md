# LaunchDarkly Provider Skill

LaunchDarkly is a feature flag management platform. Its SDK wraps every flag evaluation
in your application. Upgrading across major versions — especially v6→v7 (Node.js) and
v7→v8 (Python) — requires removing the `alias()` call and several deprecated config options.

## SDK packages
- npm (current): `@launchdarkly/node-server-sdk`
- npm (legacy, EOL): `launchdarkly-node-server-sdk`
- npm (browser legacy): `launchdarkly-js-client-sdk`
- npm (browser current): `@launchdarkly/js-client-sdk`
- npm (React): `launchdarkly-react-client-sdk`
- pypi: `launchdarkly-server-sdk` (imports as `ldclient` — NOT `launchdarkly_server_sdk`)
- rubygems: `launchdarkly-server-sdk`

## Import patterns

### JavaScript/TypeScript
```
require('launchdarkly-node-server-sdk')   // legacy, EOL at v7
require('@launchdarkly/node-server-sdk')  // current, v8+
require('launchdarkly-js-client-sdk')     // browser legacy
require('@launchdarkly/js-client-sdk')    // browser current
require('launchdarkly-react-client-sdk')  // React
import * as ld from '@launchdarkly/node-server-sdk'
```

### Python (IMPORTANT: module name is `ldclient`, not `launchdarkly_server_sdk`)
```python
import ldclient
from ldclient import Config, Context, LDClient
from ldclient.evaluation import EvaluationDetail
from ldclient.flag import ...   # REMOVED in v8 — this is the old pattern
```

### Ruby
```ruby
require 'launchdarkly-server-sdk'
```

## Call sites (report these)

### Node.js — REMOVED in v7 (Contexts migration)
- `client.getUser()` — REMOVED; use `client.getContext()`
- `client.alias(newUser, previousUser)` — REMOVED; no replacement (REPORT_ONLY)
- `ld.init(sdkKey, { inlineUsersInEvents: true })` — REMOVED config key
- `ld.init(sdkKey, { privateAttributeNames: [...] })` — RENAMED to `privateAttributes`
- `ld.init(sdkKey, { userKeysCapacity: N })` — DEPRECATED; use `contextKeysCapacity`
- `ld.init(sdkKey, { userKeysFlushInterval: N })` — DEPRECATED; use `contextKeysFlushInterval`

### Python — REMOVED in v8 (Contexts migration)
- `ldclient.get().alias(new_user, prev_user)` — REMOVED; no replacement (REPORT_ONLY)
- `ldclient.Config(sdk_key, inline_users_in_events=True)` — REMOVED config kwarg
- `from ldclient.flag import EvaluationDetail` — REMOVED module; use `from ldclient.evaluation import`
- `import ldclient.flag` — REMOVED module; use `ldclient.evaluation`

### Package renames (flag for migration)
- `require('launchdarkly-node-server-sdk')` → `require('@launchdarkly/node-server-sdk')`
- `require('launchdarkly-js-client-sdk')` → `require('@launchdarkly/js-client-sdk')`

## Where to look first
1. `grep("launchdarkly", "package.json")` — covers both old and new package names.
2. `grep("import ldclient", "")` or `grep("from ldclient import", "")` — Python usage.
3. Feature flag evaluation: `client.variation(` — these are in every feature-gated code path.
4. `require 'launchdarkly-server-sdk'` — Ruby entry.

## Breaking-change context

### Node.js v6 → v7 (Contexts migration, 2022-12-07)
| Old symbol | Status | New symbol |
|---|---|---|
| `client.getUser()` | REMOVED | `client.getContext()` |
| `client.alias()` | REMOVED | — (alias not needed in context model) |
| `options.inlineUsersInEvents` | REMOVED | — |
| `options.privateAttributeNames` | RENAMED | `options.privateAttributes` |
| `options.userKeysCapacity` | DEPRECATED | `options.contextKeysCapacity` |

### Node.js package rename (2023-06-28)
`launchdarkly-node-server-sdk` v7.0.2 → final EOL release pointing to `@launchdarkly/node-server-sdk`.
API surface is identical; only package location changed.

### Python v7 → v8 (Contexts migration, 2022-12-30)
| Old symbol | Status | New symbol |
|---|---|---|
| `client.alias()` | REMOVED | — |
| `Config(inline_users_in_events=...)` | REMOVED | — |
| `from ldclient.flag import ...` | REMOVED | `from ldclient.evaluation import ...` |

### Python v9.15.0 (2026-02-10) — Python 3.9 dropped
Python 3.9 support removed. Runtime failure on Python 3.9 codebases.

### JS Browser SDK rename (2026-04-06)
`launchdarkly-js-client-sdk` v3.9.1 → new releases on `@launchdarkly/js-client-sdk`.

## Anchors (fallback signals)
- Env vars: `LAUNCHDARKLY_SDK_KEY`, `LD_SDK_KEY`
- Init pattern: `ld.init(sdkKey, ...)` or `LDClient.init(sdkKey, ...)`
- Python: `ldclient.set_config(ldclient.Config(sdk_key, ...))`
