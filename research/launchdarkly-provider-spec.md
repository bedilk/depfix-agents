# LaunchDarkly Provider Implementation Spec

**Status:** Ready for implementer  
**Date:** 2026-10-06  
**Researcher:** researcher agent  
**Source tasks:** T-8 (priority ranking — beyond top-10), proactive work round 18  
**Priority:** ~32M npm/month total across all packages; Python 9.4M/month; critical infrastructure (feature flags) with 1-2 major breaking changes per SDK per year

---

## Overview

LaunchDarkly is the leading feature flag management platform. Its SDKs are embedded in critical production paths — every `variation()` call is a synchronous code path. Users who fall behind on upgrades face two distinct risks:

1. **Breaking API changes** — especially the v7 (Node.js) / v8 (Python) "Contexts" migration, which removed multiple top-level methods
2. **Package renames** — `launchdarkly-node-server-sdk` → `@launchdarkly/node-server-sdk` (2023), `launchdarkly-js-client-sdk` → `@launchdarkly/js-client-sdk` (2026)

depfix can detect all removed/renamed call sites from the Contexts migration, plus the package renames.

---

## Download Counts (verified 2026-10-06)

| Package | Ecosystem | Monthly downloads | Latest version |
|---|---|---|---|
| `@launchdarkly/node-server-sdk` | npm | **11,097,081** | v9.14.2 |
| `launchdarkly-js-client-sdk` | npm | **10,744,569** | v3.9.6 |
| `launchdarkly-react-client-sdk` | npm | **6,280,269** | v3.x |
| `launchdarkly-node-server-sdk` | npm | **1,816,945** | v7.0.4 (EOL) |
| `@launchdarkly/js-client-sdk` | npm | **1,757,780** | v3.x (new) |
| `launchdarkly-server-sdk` | pypi | **9,377,739** | v9.18.0 |
| `launchdarkly-server-sdk` | rubygems | 29.8M total downloads | v8.18.0 |

**Total npm/month (all packages):** ~31.7M  
**Combined npm + pypi/month:** ~41M

**Verification commands:**
```bash
curl -s "https://api.npmjs.org/downloads/point/last-month/@launchdarkly%2Fnode-server-sdk"
# {"downloads":11097081,...}

curl -s "https://api.npmjs.org/downloads/point/last-month/launchdarkly-js-client-sdk"
# {"downloads":10744569,...}

curl -s "https://pypistats.org/api/packages/launchdarkly-server-sdk/recent"
# {"data":{"last_month":9377739,...}}
```

---

## Critical Python Import Note

The PyPI package is **`launchdarkly-server-sdk`** but the Python import module is **`ldclient`**:

```python
# Installed via: pip install launchdarkly-server-sdk
import ldclient                          # module name is ldclient, NOT launchdarkly_server_sdk
from ldclient import Config, Context
```

This is identical to the `sentry-sdk` → `sentry_sdk` pattern that was already studied (T-2). The scanner's `_python_import_regexes("launchdarkly-server-sdk")` would generate `launchdarkly_server_sdk` patterns, which are **wrong**. The skill file must explicitly specify `ldclient` as the Python module name, or the providers.yaml entry needs a `python_module_override: ldclient` field.

Check how `sentry-sdk` handles this in `providers.yaml` and `src/depfix/scanners/` before implementing.

---

## SDK Package History and Version Scheme

### Node.js Server SDK
- **v5.x** → **v6.0.0** (2021-06-17): Deprecated removals, Node.js compatibility update
- **v6.x** → **v7.0.0** (2022-12-07): **Contexts migration** — major API surface change
- **v7.0.2** (2023-06-28): Package renamed; `launchdarkly-node-server-sdk` published final EOL release pointing to new package
- **@launchdarkly/node-server-sdk v8.0.0** (2023-06-26): TypeScript rewrite, same Contexts API
- **v9.x** (2023–present): Active development, currently v9.14.2

### Python Server SDK
- **v7.x** → **v8.0.0** (2022-12-30): **Contexts migration** (parallel to Node.js v7)
- **v8.x** → **v9.0.0**: Continued active development, currently v9.18.0
- **v9.15.0** (2026-02-10): Python 3.9 support dropped (marked as breaking in changelog)

### JS Browser SDK
- **launchdarkly-js-client-sdk v3.9.1** (2026-04-06): Package renamed to `@launchdarkly/js-client-sdk`; all future releases on new name

---

## Breaking Changes — Node.js SDK (v6 → v7)

Source: https://raw.githubusercontent.com/launchdarkly/node-server-sdk/main/CHANGELOG.md, `## [7.0.0]` section

### 1. `LDClient.getUser()` removed → `LDClient.getContext()`

```javascript
// BEFORE (v6.x) — REMOVED in v7
const user = client.getUser();

// AFTER (v7+)
const context = client.getContext();
```

**depfix classification:** `REMOVED` symbol `getUser`, replacement `getContext`

### 2. `client.alias()` removed

```javascript
// BEFORE (v6.x) — REMOVED in v7
client.alias(newUser, previousUser);

// AFTER (v7+) — alias events not needed in new context model
// DELETE the line entirely
```

**depfix classification:** `REMOVED` symbol `alias`, no replacement (`REPORT_ONLY`)

### 3. `inlineUsersInEvents` config option removed

```javascript
// BEFORE (v6.x) — REMOVED in v7
const client = ld.init(sdkKey, {
  inlineUsersInEvents: true   // ← not relevant in context model
});

// AFTER (v7+) — remove the option
const client = ld.init(sdkKey, {});
```

**depfix classification:** `REMOVED` config key `inlineUsersInEvents`, no replacement

### 4. `privateAttributeNames` → `privateAttributes` in LDOptions

```javascript
// BEFORE (v6.x) — REMOVED in v7
const client = ld.init(sdkKey, {
  privateAttributeNames: ['email', 'name']
});

// AFTER (v7+)
const client = ld.init(sdkKey, {
  privateAttributes: ['email', 'name']
});
```

**depfix classification:** `RENAMED` `privateAttributeNames` → `privateAttributes`

### 5. `userKeysCapacity` / `userKeysFlushInterval` deprecated (v7), removal expected in v8+

```javascript
// Deprecated in v7 — use context equivalents
userKeysCapacity: 1000       → contextKeysCapacity: 1000
userKeysFlushInterval: 300   → contextKeysFlushInterval: 300
```

**depfix classification:** `DEPRECATED` / `RENAMED`

---

## Breaking Changes — Python SDK (v7 → v8)

Source: https://raw.githubusercontent.com/launchdarkly/python-server-sdk/main/CHANGELOG.md, `## [8.0.0]` section

### 1. `client.alias()` removed

```python
# BEFORE (v7.x) — REMOVED in v8
client.alias(new_user, previous_user)

# AFTER (v8+) — alias events not needed
# DELETE the line
```

**depfix classification:** `REMOVED` symbol `alias`, no replacement (`REPORT_ONLY`)

### 2. `inline_users_in_events` config option removed

```python
# BEFORE (v7.x) — REMOVED in v8
import ldclient
ldclient.set_config(ldclient.Config(
    sdk_key,
    inline_users_in_events=True   # ← removed
))

# AFTER (v8+)
ldclient.set_config(ldclient.Config(sdk_key))
```

**depfix classification:** `REMOVED` config kwarg `inline_users_in_events`

### 3. `ldclient.flag` module removed

```python
# BEFORE (v7.x) — REMOVED in v8 (was deprecated since v5)
from ldclient.flag import EvaluationDetail
from ldclient import flag

# AFTER (v8+)
from ldclient.evaluation import EvaluationDetail
```

**depfix classification:** `REMOVED` module `ldclient.flag`, replacement `ldclient.evaluation`

### 4. Minimum Python version raised to 3.7 (v8), then 3.9 dropped in v9.15.0

```
v8.0.0: minimum Python = 3.7 (was 2.7/3.x in v7)
v9.15.0: Python 3.9 support dropped
```

**depfix classification:** `ENV_REQUIREMENT_CHANGE` (informational, no symbol fix possible)

---

## Package Rename Breaking Change

### Node.js: `launchdarkly-node-server-sdk` → `@launchdarkly/node-server-sdk`

```bash
# package.json BEFORE
"launchdarkly-node-server-sdk": "^7.0.0"

# package.json AFTER
"@launchdarkly/node-server-sdk": "^9.0.0"
```

```javascript
// import BEFORE
const ld = require('launchdarkly-node-server-sdk');

// import AFTER
const ld = require('@launchdarkly/node-server-sdk');
```

The API surface of `@launchdarkly/node-server-sdk` v8+ is identical to `launchdarkly-node-server-sdk` v7 (same Contexts model). The rename is purely a package location change.

**depfix classification:** `PACKAGE_RENAMED` old=`launchdarkly-node-server-sdk` new=`@launchdarkly/node-server-sdk`

### JS Browser: `launchdarkly-js-client-sdk` → `@launchdarkly/js-client-sdk`

This rename was announced in v3.9.1 (April 2026). The old package continues to receive patch releases for now, but new features only land in the scoped package.

---

## providers.yaml Entry

```yaml
- id: launchdarkly
  name: LaunchDarkly
  api_version_scheme: semver
  sdk_packages:
  - name: '@launchdarkly/node-server-sdk'
    ecosystem: npm
  - name: launchdarkly-node-server-sdk
    ecosystem: npm
  - name: launchdarkly-js-client-sdk
    ecosystem: npm
  - name: '@launchdarkly/js-client-sdk'
    ecosystem: npm
  - name: launchdarkly-react-client-sdk
    ecosystem: npm
  - name: launchdarkly-server-sdk
    ecosystem: pypi
    python_module: ldclient
  - name: launchdarkly-server-sdk
    ecosystem: rubygems
  feeds:
  - kind: npm_dist_tag
    package: '@launchdarkly/node-server-sdk'
    dist_tag: latest
    github_repo: launchdarkly/js-core
  - kind: npm_dist_tag
    package: launchdarkly-node-server-sdk
    dist_tag: latest
    github_repo: launchdarkly/node-server-sdk
  - kind: pypi_dist_tag
    package: launchdarkly-server-sdk
    github_repo: launchdarkly/python-server-sdk
  - kind: github_release
    repo: launchdarkly/js-core
  - kind: github_release
    repo: launchdarkly/python-server-sdk
  - kind: rubygems_dist_tag
    gem: launchdarkly-server-sdk
  - kind: ts_exports_diff
    package: '@launchdarkly/node-server-sdk'
```

> **Note:** If `python_module` is not a valid field, the implementer must add this field to the providers.yaml schema and the Python scanner's `_python_import_regexes()` to handle the package → module name override. See how `sentry-sdk` (package) → `sentry_sdk` (module) is handled as precedent.

---

## Skill File: `src/depfix/providers/skills/provider_launchdarkly.md`

### Template

```markdown
# LaunchDarkly Provider Skill

LaunchDarkly is a feature flag management platform. Its SDK wraps every flag evaluation
in your application. Upgrading across major versions — especially v6→v7 (Node.js) and
v7→v8 (Python) — requires removing the `alias()` call and several deprecated config options.

## Scanner Hints

**JavaScript/TypeScript import patterns:**
- `require('launchdarkly-node-server-sdk')` (legacy, EOL at v7)
- `require('@launchdarkly/node-server-sdk')` (current, v8+)
- `require('launchdarkly-js-client-sdk')` (browser legacy)
- `require('@launchdarkly/js-client-sdk')` (browser current)
- `require('launchdarkly-react-client-sdk')` (React)
- `import * as ld from '@launchdarkly/node-server-sdk'`

**Python import patterns (package `launchdarkly-server-sdk`, module `ldclient`):**
- `import ldclient`
- `from ldclient import Config, Context, LDClient`
- `from ldclient.evaluation import EvaluationDetail`
- `from ldclient.flag import ...`  ← this is the REMOVED pattern (v8)

**Ruby import patterns (gem `launchdarkly-server-sdk`):**
- `require 'launchdarkly-server-sdk'`

## Known Breaking Changes

### Node.js v6 → v7 (Contexts migration, 2022-12-07)

| Old symbol | Status | New symbol | Notes |
|---|---|---|---|
| `client.getUser()` | REMOVED | `client.getContext()` | Returns LDContext instead of LDUser |
| `client.alias()` | REMOVED | — | Alias events not needed in context model |
| `options.inlineUsersInEvents` | REMOVED | — | Not relevant in context model |
| `options.privateAttributeNames` | RENAMED | `options.privateAttributes` | Now supports attribute references |
| `options.userKeysCapacity` | DEPRECATED | `options.contextKeysCapacity` | |
| `options.userKeysFlushInterval` | DEPRECATED | `options.contextKeysFlushInterval` | |

### Python v7 → v8 (Contexts migration, 2022-12-30)

| Old symbol | Status | New symbol | Notes |
|---|---|---|---|
| `client.alias()` | REMOVED | — | Alias events not needed |
| `Config(inline_users_in_events=...)` | REMOVED | — | Config kwarg removed |
| `from ldclient.flag import ...` | REMOVED | `from ldclient.evaluation import ...` | Module moved |
| `import ldclient.flag` | REMOVED | `import ldclient.evaluation` | Module removed |

### Package Renames (depfix should detect both old and new)

| Old package | New package | When |
|---|---|---|
| `launchdarkly-node-server-sdk` | `@launchdarkly/node-server-sdk` | v7.0.2 / 2023-06-28 |
| `launchdarkly-js-client-sdk` | `@launchdarkly/js-client-sdk` | v3.9.1 / 2026-04-06 |

## Fix Templates

### Node.js: `getUser()` → `getContext()`

```javascript
// BEFORE
const user = client.getUser();
// AFTER
const context = client.getContext();
```

### Node.js: Remove `alias()` call

```javascript
// BEFORE — DELETE this line
client.alias(newUser, previousUser);
// AFTER — line removed, no replacement needed
```

### Node.js: `privateAttributeNames` → `privateAttributes`

```javascript
// BEFORE
{ privateAttributeNames: ['email'] }
// AFTER
{ privateAttributes: ['email'] }
```

### Python: Remove `alias()` call

```python
# BEFORE — DELETE this line
ldclient.get().alias(new_user, previous_user)
# AFTER — no replacement
```

### Python: `ldclient.flag` → `ldclient.evaluation`

```python
# BEFORE
from ldclient.flag import EvaluationDetail
# AFTER
from ldclient.evaluation import EvaluationDetail
```
```

---

## Seed Repo Fixture

For testing, a minimal seed repo that depfix can scan:

**`bedilk/seed-launchdarkly-v6-to-v7`** would contain:

```javascript
// package.json
{
  "dependencies": {
    "launchdarkly-node-server-sdk": "^6.4.3"
  }
}
```

```javascript
// index.js
const ld = require('launchdarkly-node-server-sdk');
const client = ld.init(process.env.LD_SDK_KEY);

async function run() {
  await client.waitForInitialization();

  // Call sites depfix should detect:
  const user = client.getUser();           // REMOVED in v7
  client.alias(newUser, previousUser);     // REMOVED in v7

  const flagValue = client.variation('my-flag', { key: 'user-123' }, false);
  client.close();
}
```

Expected scan result: 2 call sites, both actionable. Plan: fix `getUser()` → `getContext()`, flag `alias()` as REPORT_ONLY.

---

## Implementer Checklist

1. **Check Python module override mechanism**: Does `providers.yaml` support a `python_module:` field? If not, add support in `_python_import_regexes()`. Precedent: `sentry-sdk` package → `sentry_sdk` module.

2. **Add providers.yaml entry** using the YAML block above.

3. **Write `src/depfix/providers/skills/provider_launchdarkly.md`** using the template above.

4. **Add test case** in `tests/` covering:
   - `_python_import_regexes("launchdarkly-server-sdk")` generates patterns that match `import ldclient` (not `launchdarkly_server_sdk`)
   - Scanner detects `client.alias(` as a call site when the LaunchDarkly package is imported

5. **Verify provider count test** passes (`test_provider_count` or equivalent in T-1's baseline).

6. **Run `make test`** — should pass with 893+ tests.

7. **Consider creating seed repo** `bedilk/seed-launchdarkly-v6-to-v7` for integration testing.

---

## Breaking Change Frequency

| Transition | Node.js | Python | Impact |
|---|---|---|---|
| v5→v6 | 2021-06-17 | 2021-xx | Deprecated removals |
| v6→v7 | 2022-12-07 | — | **Contexts migration (HIGH)** |
| v7→v8 | — | 2022-12-30 | **Contexts migration (HIGH)** |
| v8→v9 | 2023-xx | — | Ongoing |
| Python 3.9 drop | — | v9.15.0 (2026-02-10) | Runtime requirement |

**Estimated breaking changes per year:** 1-2 SDK-level majors + occasional Python version floor raises. The Contexts migration (2022) was a one-time large migration affecting all users — depfix would have provided maximum value there.

---

## Why LaunchDarkly Is High Priority

1. **~41M combined downloads/month** — larger than several providers already in providers.yaml
2. **Critical production path** — every feature flag evaluation calls the SDK synchronously; a broken upgrade can disable entire features
3. **The Contexts migration (2022) affected every single user** — `alias()` was removed, config options were renamed — exactly the kind of change depfix is built for
4. **Active SDK development** — LaunchDarkly ships regularly (current Node.js SDK had 113 npm releases), making depfix's "watch" pipeline continuously valuable
5. **Multi-ecosystem** — npm (server + browser + React), Python, Ruby — three ecosystems in one provider entry
