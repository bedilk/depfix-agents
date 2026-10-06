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
