# Pinecone Provider Implementation Spec

**Status:** Ready for implementer  
**Date:** 2026-10-09  
**Researcher:** researcher agent  
**Source tasks:** T-8 follow-on, proactive provider expansion  
**Priority:** #next — 7.5M combined downloads/month, highest major-version churn of any provider researched (9 npm majors in 3 years)

---

## Overview

Pinecone is the leading managed vector database, used in virtually every RAG/AI application stack. It sits alongside OpenAI, Anthropic, and LangChain — all already in providers.yaml. Pinecone ships ~3 npm major versions per year, making it one of the highest-churn providers depfix can cover.

| Field | Value |
|---|---|
| npm package | `@pinecone-database/pinecone` |
| pypi package | `pinecone` |
| npm downloads/month | **3,575,897** (verified 2026-10-09) |
| pypi downloads/month | **3,879,257** (verified 2026-10-09, pypistats) |
| npm latest | 9.0.0 |
| pypi latest | 10.0.0 |
| npm major versions | 9 (v1.0.0 Sep 2023 → v9.0.0 Sep 2026) |
| pypi major versions | 10 (v1 → v10.0.0 Sep 2026) |
| breaking changes/year | ~3 npm, ~2-3 pypi (all confirmed from release notes) |
| OpenAPI spec | Not publicly accessible (requires API key auth at api.pinecone.io/openapi.json) |
| Feeds | github_release + ts_exports_diff |
| GitHub (npm) | github.com/pinecone-io/pinecone-ts-client |
| GitHub (pypi) | github.com/pinecone-io/pinecone-python-client |
| Python module name | `pinecone` (same as package name — no import mismatch) |

**Previously:** `pinecone-client` (PyPI) and `@pinecone-io/client` (npm) — both deprecated since 2023. Only `pinecone` / `@pinecone-database/pinecone` matter for new code.

---

## npm Major Version Timeline

| Version | Date | Breaking Changes |
|---|---|---|
| v1.0.0 | 2023-09-07 | First stable release (replaced @pinecone-io/client) |
| v2.0.0 | 2024-01-16 | `createIndex()` spec argument restructured (serverless) |
| v3.0.0 | 2024-07-19 | API version `2024-07`; Inference API added |
| v4.0.0 | 2024-10-23 | Rerank and Import endpoints added; internal changes |
| v5.0.0 | 2025-02-15 | API version `2025-01`; sparse index support |
| v6.0.0 | 2025-05-10 | API version `2025-04`; namespace methods added |
| v7.0.0 | 2026-01-31 | **MAJOR API REDESIGN**: index targeting, object-shaped args |
| v8.0.0 | 2026-06-16 | Assistant file ops now async (return `Operation`) |
| v9.0.0 | 2026-09-09 | Node.js 22+; preview docs graduate to main client |

---

## Python Major Version Timeline

| Version | Date | Breaking Changes |
|---|---|---|
| v5.0.0 | 2024-07-31 | `openapi_config` removed |
| v6.0.0 | 2025-02-07 | Plugins removed (baked in), Python 3.8 dropped |
| v7.0.0 | 2025-05-20 | Package rename `pinecone-client` → `pinecone` (since v5.1.0) |
| v8.0.0 | 2025-11-18 | **Python 3.9 dropped** (requires 3.10+) |
| v9.0.0 | 2026-05-04 | **Total rewrite**: plugin-assistant retired, grpc extras removed |
| v10.0.0 | 2026-09-03 | Python 3.10+; preview document ops graduate to main |

---

## Confirmed Breaking Changes (depfix-detectable)

### BC-1: npm v7.0.0 — Index Targeting API Change (HIGH IMPACT)
**Affects:** ALL code that creates a Pinecone index client

```typescript
// OLD (v6): string argument
const index = pc.index('my-index');
const index = pc.index('my-index', 'https://host.svc.pinecone.io');

// NEW (v7): object-shaped argument (string was deprecated, removed in v8)
const index = pc.index({ name: 'my-index' });
const index = pc.index({ host: indexModel.host });  // preferred
```

- `old_api: pinecone.Pinecone.index`
- `new_api: pinecone.Pinecone.index`  (signature change only)
- `kind: METHOD_SIGNATURE_CHANGED`
- `old_version: "6.1.4"`, `new_version: "7.0.0"`
- **Every single index access call in the codebase is affected.** This is the v7 primary breaking change.

### BC-2: npm v7.0.0 — Object-Shaped Data Plane Arguments (HIGH IMPACT)
**Affects:** All code calling upsert, query, fetch, delete on index

```typescript
// OLD: positional array
await index.upsert(records);
await index.upsertRecords(records);

// NEW: object with records key
await index.upsert({ records });
await index.upsert({ records, namespace: 'ns1' });
```

- `old_api: pinecone.Index.upsert`
- `kind: METHOD_SIGNATURE_CHANGED`
- `old_version: "6.1.4"`, `new_version: "7.0.0"`

### BC-3: npm v7.0.0 — `configureIndex()` Signature Change
```typescript
// OLD: (indexName, patchRequest)
await pc.configureIndex('my-index', { replicas: 2 });

// NEW: object-shaped
await pc.configureIndex({ name: 'my-index', podReplicas: 2 });
```

- `old_api: pinecone.Pinecone.configureIndex`
- `kind: METHOD_SIGNATURE_CHANGED`
- `old_version: "6.1.4"`, `new_version: "7.0.0"`

### BC-4: npm v8.0.0 — Assistant File Operations Now Async
```typescript
// OLD (v7): uploadFile returned void or File object
await assistant.uploadFile({ path: 'doc.pdf' });

// NEW (v8): returns Operation, must poll
const op = await assistant.uploadFile({ path: 'doc.pdf' });
await op.poll();
```

- `old_api: pinecone.Assistant.uploadFile`
- `new_api: pinecone.Assistant.uploadFile`  (return type changed)
- `kind: RETURN_TYPE_CHANGED`
- `old_version: "7.2.0"`, `new_version: "8.0.0"`

### BC-5: npm v9.0.0 — Node.js 22+ Required
- Drops Node 18 and 20 support
- `kind: RUNTIME_REQUIREMENT` → treat as REPORT_ONLY
- Detection: package.json engines field or node version CI config

### BC-6: Python v6.0.0 — Plugin Packages Removed
```python
# OLD: required separate plugin install
pip install pinecone pinecone-plugin-records pinecone-plugin-inference
import pinecone
pinecone.install_plugin(...)  # from plugin

# NEW: baked in, plugins cause exception if present
pip install pinecone  # only
# Using pinecone-plugin-records with v6+ raises: "Please uninstall pinecone-plugin-records"
```

- `old_api: pinecone.install_plugin` → REPORT_ONLY (no direct fix possible)
- `kind: METHOD_REMOVED`
- `old_version: "5.4.2"`, `new_version: "6.0.0"`

### BC-7: Python v8.0.0 — Python 3.9 Dropped
- `minimum_python: "3.10"` (was 3.9)
- REPORT_ONLY (can't auto-fix runtime version)
- `old_version: "7.3.0"`, `new_version: "8.0.0"`

### BC-8: Python v9.0.0 — `pinecone-plugin-assistant` Retired
```python
# OLD: separate package required
pip install pinecone pinecone-plugin-assistant
from pinecone_plugin_assistant import Assistant  # does not exist in v9

# NEW: built into core
pc = Pinecone(api_key=...)
pc.assistant.create_assistant(...)
```

- `old_api: pinecone_plugin_assistant.Assistant`
- `new_api: pinecone.Pinecone.assistant`
- `kind: TYPE_REMOVED` (the plugin package itself is gone)
- `old_version: "8.1.2"`, `new_version: "9.0.0"`
- Detection: `import pinecone_plugin_assistant` in any Python file

### BC-9: Python v9.0.0 — `PineconeGRPC` / grpc extras Retired
```python
# OLD: separate grpc extras and class
pip install "pinecone[grpc]"
from pinecone.grpc import PineconeGRPC

# NEW: standard Pinecone client handles gRPC automatically
from pinecone import Pinecone
pc = Pinecone(api_key=...)  # gRPC available without extras
```

- `old_api: pinecone.grpc.PineconeGRPC`
- `new_api: pinecone.Pinecone`
- `kind: TYPE_REMOVED`
- `old_version: "8.1.2"`, `new_version: "9.0.0"`

---

## providers.yaml Entry

Insert after the `amplitude` entry:

```yaml
- id: pinecone
  name: Pinecone
  api_version_scheme: semver
  api_base_urls:
  - https://api.pinecone.io
  sdk_packages:
  - name: "@pinecone-database/pinecone"
    ecosystem: npm
  - name: pinecone
    ecosystem: pypi
  feeds:
  - kind: npm_dist_tag
    package: "@pinecone-database/pinecone"
    dist_tag: latest
    github_repo: pinecone-io/pinecone-ts-client
  - kind: ts_exports_diff
    package: "@pinecone-database/pinecone"
  - kind: pypi_dist_tag
    package: pinecone
    github_repo: pinecone-io/pinecone-python-client
  - kind: github_release
    repo: pinecone-io/pinecone-ts-client
  - kind: github_release
    repo: pinecone-io/pinecone-python-client
  skills:
  - src/depfix/providers/skills/provider_pinecone.md
```

---

## Skill File: `src/depfix/providers/skills/provider_pinecone.md`

```markdown
# Pinecone scan skill

## SDK packages
- npm: `@pinecone-database/pinecone`
- pypi: `pinecone`
- **Deprecated (ignore):** `pinecone-client` (PyPI), `@pinecone-io/client` (npm)

## Import patterns

### TypeScript/JavaScript
```
import { Pinecone } from '@pinecone-database/pinecone'
const { Pinecone } = require('@pinecone-database/pinecone')
```

### Python
```
from pinecone import Pinecone
import pinecone
```

Also flag (deprecated plugin patterns):
```
import pinecone_plugin_assistant
from pinecone.grpc import PineconeGRPC
```

## Call sites
- `new Pinecone({ apiKey })` — constructor
- `pc.index('name')` — index accessor (v7+: `pc.index({name:'...'})`), primary access pattern
- `pc.createIndex(...)` — control plane
- `pc.configureIndex(...)` — v7 signature changed
- `index.upsert(...)` — data plane, v7 signature changed
- `index.query(...)` — data plane
- `index.fetch(...)` — data plane
- `assistant.uploadFile(...)` — v8 now returns Operation
- `pc.assistant` — v9+ built-in assistant
- `Pinecone(api_key=...)` — Python constructor
- `pc.Index(name)` — Python index accessor (capital I in older versions)

## Where to look first
1. `grep("@pinecone-database/pinecone", "")` — the scoped package is distinctive
2. `grep("pinecone_plugin_", "")` — plugin imports indicate old pattern
3. `pc.index(` followed by string arg — BC-1 pattern, very common
4. `from pinecone import Pinecone` in any Python file using AI/RAG patterns
5. `PineconeGRPC` — BC-9 removal pattern

## Version drift policy
- Major gap: any version delta where old major < 7 and new major >= 7 (BC-1 through BC-3)
- Major gap: old major < 8 and new major >= 8 (BC-4, Assistant async)
- any-minor: watch for BC-5 (Node.js 22+) and BC-8 (Python 3.9 drop)
```

---

## Seed Repo Candidate

No current bedilk fork for Pinecone. Suggested fixture repo: create `bedilk/seed-pinecone-v6-to-v9` with:

```typescript
// package.json: "@pinecone-database/pinecone": "^6.1.4"

import { Pinecone } from '@pinecone-database/pinecone';
const pc = new Pinecone({ apiKey: process.env.PINECONE_API_KEY });

// BC-1: string arg to pc.index() — removed in v8
const index = pc.index('my-index');

// BC-2: positional array to upsert — removed in v7
await index.upsert([{ id: '1', values: [0.1, 0.2, 0.3] }]);
```

---

## Implementer Checklist

- [ ] Add providers.yaml entry (above)
- [ ] Create `src/depfix/providers/skills/provider_pinecone.md` (above)
- [ ] Verify `make test` still passes (provider count test will need +1)
- [ ] Breaking changes BC-1 through BC-4 are the highest-value for eval cases
- [ ] Python BC-8 (`pinecone_plugin_assistant` detection) is high-value for RAG stacks
- [ ] No OpenAPI feed available — github_release + ts_exports_diff only

---

## Priority Assessment

Pinecone sits in every AI/RAG stack alongside OpenAI and Anthropic (already supported). It ships major versions ~3×/year. The v7 API redesign (BC-1: `pc.index('name')`) affects literally every Pinecone call-site in every codebase — the highest per-change impact of any provider researched. Adding Pinecone now means depfix can offer a complete AI-stack upgrade path: OpenAI + Anthropic + Pinecone in a single scan.
