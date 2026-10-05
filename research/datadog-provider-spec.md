# Datadog Provider Implementation Spec

**Status:** Ready for implementer  
**Date:** 2026-10-06  
**Researcher:** researcher agent  
**Source tasks:** T-7 (provider candidates), T-8 (priority ranking)  
**Priority:** #3 uncovered provider — 12.7M npm downloads/month

---

## Overview

Datadog is the dominant monitoring, APM, and observability platform. The `@datadog/datadog-api-client` SDK wraps the Datadog management API — used by teams managing monitors, dashboards, logs, metrics, synthetics, incidents, SLOs, and security rules programmatically.

The SDK is auto-generated from Datadog's internal OpenAPI specifications via their `api-clients-generation-pipeline`. This means every API surface change (endpoint additions, renames, removals) ships in a corresponding SDK release. The SDK has shipped **64 minor releases** since v1.0, with consistent `Removed` and `Changed` sections that represent breaking changes. Additionally, **v2 of the SDK (now in Preview)** will split the monolithic client into per-product packages — the largest upcoming breaking change.

| Field | Value |
|---|---|
| npm package | `@datadog/datadog-api-client` |
| pypi package | `datadog-api-client` |
| npm downloads/month | **12,710,481** (verified 2026-10-04) |
| npm latest | 1.64.0 (2026-09-24) |
| pypi latest | 2.61.0 (2026-09-24) |
| GitHub SDK (TS) | DataDog/datadog-api-client-typescript |
| GitHub SDK (Python) | DataDog/datadog-api-client-python |
| OpenAPI spec | None public (internal generation pipeline) |
| CHANGELOG (TS) | `https://raw.githubusercontent.com/DataDog/datadog-api-client-typescript/master/CHANGELOG.md` |
| CHANGELOG (Python) | `https://raw.githubusercontent.com/DataDog/datadog-api-client-python/master/CHANGELOG.md` |
| api_version_scheme | `semver` |

---

## Datadog API surface (from SDK inspection)

The SDK exposes two major API namespaces — `v1` (legacy/stable) and `v2` (modern/evolving):

### TypeScript import pattern
```typescript
import { client, v1, v2 } from '@datadog/datadog-api-client';

const configuration = client.createConfiguration();

// v1 API (monitors, dashboards, hosts, logs)
const monitorsApi = new v1.MonitorsApi(configuration);
const dashboardsApi = new v1.DashboardsApi(configuration);
const logsApi = new v1.LogsApi(configuration);

// v2 API (metrics, incidents, security, users, spans)
const metricsApi = new v2.MetricsApi(configuration);
const incidentsApi = new v2.IncidentsApi(configuration);
const securityApi = new v2.SecurityMonitoringApi(configuration);
```

### Python import pattern
```python
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v1.api.monitors_api import MonitorsApi
from datadog_api_client.v2.api.metrics_api import MetricsApi
from datadog_api_client.v1.model.monitor import Monitor
```

### Authentication
Default: `DD_API_KEY` and `DD_APP_KEY` environment variables.  
Explicit:
```typescript
const configuration = client.createConfiguration({
  authMethods: { apiKeyAuth: "<API KEY>", appKeyAuth: "<APPLICATION KEY>" }
});
```

---

## providers.yaml entry

Add after the `astro` entry (currently the last entry):

```yaml
- id: datadog
  name: Datadog
  api_version_scheme: semver
  api_base_urls:
  - https://api.datadoghq.com
  - https://api.datadoghq.eu
  - https://api.us3.datadoghq.com
  - https://api.us5.datadoghq.com
  sdk_packages:
  - name: "@datadog/datadog-api-client"
    ecosystem: npm
  - name: datadog-api-client
    ecosystem: pypi
  feeds:
  - kind: npm_dist_tag
    package: "@datadog/datadog-api-client"
    dist_tag: latest
    github_repo: DataDog/datadog-api-client-typescript
  - kind: pypi_dist_tag
    package: datadog-api-client
    github_repo: DataDog/datadog-api-client-python
  - kind: github_release
    repo: DataDog/datadog-api-client-typescript
  - kind: github_release
    repo: DataDog/datadog-api-client-python
  - kind: security_advisory
    package: "@datadog/datadog-api-client"
    ecosystem: npm
  - kind: security_advisory
    package: datadog-api-client
    ecosystem: pypi
  - kind: ts_exports_diff
    package: "@datadog/datadog-api-client"
```

**No `openapi_spec` feed:** Datadog does not publish a public OpenAPI spec URL. The SDK is generated from an internal spec. Use `github_release` and `ts_exports_diff` feeds.

**No rubygems entry:** No official Datadog API client ruby gem (the `dogapi` gem is deprecated and unmaintained). Skip.

---

## Skill file: src/depfix/providers/skills/provider_datadog.md

```markdown
# Datadog scan skill

## SDK packages
- npm: `@datadog/datadog-api-client`
- pypi: `datadog-api-client`

## Import shapes to look for

### JavaScript / TypeScript
```
import { client, v1, v2 } from '@datadog/datadog-api-client'
const { client, v1, v2 } = require('@datadog/datadog-api-client')
import { client } from '@datadog/datadog-api-client'
```

Client construction:
```typescript
const configuration = client.createConfiguration();
const configuration = client.createConfiguration({
  authMethods: { apiKeyAuth: "...", appKeyAuth: "..." }
});
```

### Python
```python
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v1.api.monitors_api import MonitorsApi
from datadog_api_client.v2.api.metrics_api import MetricsApi
import datadog_api_client
```

## Call sites to look for

### Monitoring (v1, most common)
- `new v1.MonitorsApi(configuration)` — create, get, list, update, delete monitors
- `new v1.DashboardsApi(configuration)` — dashboard CRUD
- `new v1.SyntheticsApi(configuration)` — synthetic test management
- `new v1.DowntimesApi(configuration)` — schedule downtime windows

### Logs & Metrics (v1/v2)
- `new v1.LogsApi(configuration)` — log search (legacy)
- `new v2.LogsApi(configuration)` — log search (modern)
- `new v2.MetricsApi(configuration)` — metrics ingestion, query
- `new v2.SpansApi(configuration)` — APM trace/span queries

### Incidents & Security (v2)
- `new v2.IncidentsApi(configuration)` — incident lifecycle management
- `new v2.SecurityMonitoringApi(configuration)` — SIEM rules and signals
- `new v2.UsersApi(configuration)` — user and team management
- `new v2.RolesApi(configuration)` — RBAC role management

### Service Level Objectives
- `new v1.ServiceLevelObjectivesApi(configuration)` — SLO CRUD
- `new v2.ServiceLevelObjectivesApi(configuration)` — SLO corrections

## Where to look first
1. `grep("DD_API_KEY", "")` — the canonical env var for Datadog auth.
2. `grep("DD_APP_KEY", "")` — required alongside DD_API_KEY.
3. `grep("datadog-api-client", "package.json")` or `grep("datadog-api-client", "requirements.txt")`.
4. Infrastructure scripts: `scripts/monitoring/`, `ops/monitors/`, `infra/datadog/`.
5. CI/CD pipelines: `.github/workflows/*.yml` often contain Datadog monitor management steps.
6. Python: `from datadog_api_client import` or `from datadog_api_client.v1.api` / `.v2.api`.

## Breaking-change context

### v2 SDK Preview — UPCOMING MAJOR BREAKING CHANGE
The next major version (`v2`) of `@datadog/datadog-api-client` **splits the monolithic package** into
logically grouped per-product packages. See MIGRATION.md on the `v2` branch. This will break all
`import { v1, v2 } from '@datadog/datadog-api-client'` call sites. When this ships, depfix should
flag it immediately — every Datadog user will need a migration.

### v1.64.0 / v2.61.0 (2026-09-24) — field removals
- Removed `queried_tags_window_seconds` and `related_asset_tags` fields
- Removed `actor_handle` and `actor_type` from CSM ownership feedback request
- Deprecated POST `/incidents/cases/page` endpoint

### v1.63.0 / v2.60.0 (2026-09-02) — tag policy renames + Python min version
- **Python 3.10 minimum required** (`v2.60.0` Security section) — breaks Python 3.8/3.9 codebases
- Renamed "Tag Policies" to "Tag Rules" with new endpoint: `/api/v2/governance/tag_rules`
  (old: `/api/v2/governance/tag_policies`)

### v1.61.0 / v2.58.0 (2026-08-05) — enum casing
- **Uppercased automation rule trigger and action type enum values** — TypeScript callers using
  string enums like `"trigger"` would break; updated to `"TRIGGER"` shape.
- Removed deprecated incident services APIs at `/api/v2/services`
- Removed deprecated incident teams endpoints

### v1.57.0 / v2.54.x (2026-04-24) — PAT field renames
- Renamed `pat_uuid` to `pat_id`
- Removed `alias` field from Personal Access Token (PAT) spec

### Unstable endpoints pattern
Datadog marks new endpoints as "unstable" and requires opt-in:
```typescript
configuration.unstableOperations["v2.listLogs"] = true
```
When endpoints graduate from unstable to stable, the API shape may change — depfix should
watch for these graduations in the CHANGELOG `Changed` / `Removed` sections.

## Anchors (fallback signals)
- URL: `api.datadoghq.com` or `api.datadoghq.eu`
- Env vars: `DD_API_KEY`, `DD_APP_KEY`, `DATADOG_API_KEY`, `DATADOG_APP_KEY`
- Config patterns: `.datadog.yaml`, `datadog.json`, `datadog-ci.json`
```

---

## Known breaking changes

| Version (TS/Python) | Date | Breaking change |
|---|---|---|
| v2 preview (upcoming) | TBD | **Monolithic split**: `@datadog/datadog-api-client` → per-product packages. All current call sites break. |
| v1.64.0 / v2.61.0 | 2026-09-24 | Removed `queried_tags_window_seconds`, `related_asset_tags`; removed CSM ownership fields |
| v1.63.0 / v2.60.0 | 2026-09-02 | Python 3.10 minimum; Tag Policies renamed to Tag Rules at new endpoint |
| v1.61.0 / v2.58.0 | 2026-08-05 | Uppercase enum values for automation rule triggers; removed `/api/v2/services` |
| v1.57.0 | 2026-04-24 | `pat_uuid` → `pat_id`; `alias` field removed from PAT spec |
| v1.55.0 | 2026-04-16 | Removed deprecated incident teams endpoints |

**Breaking change pattern:** Every minor release of this SDK ships at least one `Removed` or `Changed`
item that alters the public API surface. These are not major version bumps — standard SemVer tooling
will not warn users. This is the same pattern as Cloudflare and makes depfix valuable.

---

## Seed repo recommendation

To test the Datadog scanner, create `bedilk/seed-datadog` containing:

```typescript
// src/monitors.ts
import { client, v1, v2 } from '@datadog/datadog-api-client';

const configuration = client.createConfiguration();

const monitorsApi = new v1.MonitorsApi(configuration);
const metricsApi = new v2.MetricsApi(configuration);
const incidentsApi = new v2.IncidentsApi(configuration);

export async function createMonitor(name: string, query: string) {
  return monitorsApi.createMonitor({
    body: { name, type: 'metric alert', query }
  });
}

export async function queryMetrics(from: number, to: number, query: string) {
  return metricsApi.queryMetrics({ from, to, query });
}

export async function listIncidents() {
  return incidentsApi.listIncidents();
}
```

```
// package.json: "@datadog/datadog-api-client": "^1.60.0"  (intentionally behind 1.64.0)
```

Expected scan output: 3+ call-sites, drift v1.60→v1.64 detected, plan with field-removal context.

---

## Implementation checklist for implementer

1. **Add providers.yaml entry** — paste the YAML block above at the end of providers.yaml (after `astro`)
2. **Create skill file** — `src/depfix/providers/skills/provider_datadog.md` from the template above
3. **Update provider count test** — `tests/unit/test_provider_loader.py` has `assert len(enabled) == N`; increment N by 1
4. **Run make test** — must pass (unit tests, no LLM)
5. **Optionally create seed repo** — `bedilk/seed-datadog` with the above fixture
6. **Note on v2 SDK preview** — when the monolithic split ships, a new breaking change entry will be needed; watch the `v2` branch of DataDog/datadog-api-client-typescript

---

## Why no public OpenAPI spec URL

Datadog generates its client SDKs from an internal OpenAPI specification via `api-clients-generation-pipeline`. The CHANGELOG confirms: "client code, feature files, and test data are generated from Datadog's public OpenAPI specifications by internal tooling." However, the spec itself is not published at a stable public URL. The `ts_exports_diff` feed type will cover TypeScript export shape changes, and `github_release` covers annotated removals/renames.

---

## Verification commands

```bash
# Check npm downloads/month
curl -s "https://api.npmjs.org/downloads/point/last-month/@datadog/datadog-api-client"
# Expected: {"downloads":~12710481,...}

# Check npm latest version
curl -s "https://registry.npmjs.org/@datadog/datadog-api-client/latest" | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['version'])"
# Expected: 1.64.0 (or newer)

# Check pypi latest version
curl -s "https://pypi.org/pypi/datadog-api-client/json" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['info']['version'])"
# Expected: 2.61.0 (or newer)

# Verify CHANGELOG is reachable
curl -s -o /dev/null -w "%{http_code}" \
  "https://raw.githubusercontent.com/DataDog/datadog-api-client-typescript/master/CHANGELOG.md"
# Expected: 200

# After adding to providers.yaml, smoke test:
bash scripts/test_pipeline.sh datadog:bedilk/seed-datadog
```

---

## Why Datadog next (after resend and cloudflare)

1. **Volume**: 12.7M npm downloads/month — 3rd highest uncovered provider (within 0.2M of cloudflare)
2. **Enterprise footprint**: Every SRE/platform engineering team using Datadog has automation scripts that use this SDK. Breaking changes cause real production incidents.
3. **Constant churn**: 64 minor releases in v1, each with `Removed` and `Changed` sections. Standard SemVer update tooling won't warn on these.
4. **v2 upcoming breakage**: The monolithic-to-per-product split (v2 branch, in Preview) will affect 100% of current call sites when it ships — depfix can be ready to flag it immediately.
5. **Python SDK is active**: pypi at v2.61.0, Python 3.10+ requirement added in v2.60.0 — a breaking change for Python 3.8/3.9 users that depfix can detect via version drift.
6. **No rubygems gap**: The absence of an official Ruby gem means depfix only needs npm + pypi, reducing implementation complexity.

---

*npm/pypi versions verified 2026-10-06. CHANGELOG confirmed reachable at 200 OK. No public OpenAPI spec URL — use github_release + ts_exports_diff feeds.*
