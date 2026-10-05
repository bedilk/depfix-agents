# Cloudflare Provider Implementation Spec

**Status:** Ready for implementer  
**Date:** 2026-10-06  
**Researcher:** researcher agent  
**Source tasks:** T-7 (provider candidates), T-8 (priority ranking)  
**Priority:** #2 uncovered provider — 12.9M npm downloads/month

---

## Overview

Cloudflare is the CDN, DNS, Workers, and API platform. The `cloudflare` SDK wraps the Cloudflare management API — used by teams managing zones, DNS, Workers, R2, KV, Pages, and Firewall rules.

Cloudflare is notable because it ships **breaking changes in minor releases** (confirmed for v7.1.0), making automated scanning particularly valuable. The TypeScript SDK is Stainless-generated — the same code-generation pattern used by Anthropic and OpenAI SDKs already in depfix.

| Field | Value |
|---|---|
| npm package | `cloudflare` |
| pypi package | `cloudflare` |
| rubygems gem | `cloudflare-ruby` (limited: v0.5.0, 1,903 downloads — skip for now) |
| npm downloads/month | **12,855,815** (verified 2026-10-04) |
| npm latest | 7.3.0 |
| pypi latest | 5.9.0 |
| OpenAPI spec | `https://raw.githubusercontent.com/cloudflare/api-schemas/main/openapi.yaml` |
| Spec OpenAPI version | 3.0.3 |
| Spec URL status | **200 OK** (verified 2026-10-05) |
| API base URL | `https://api.cloudflare.com/client/v4` |
| GitHub SDK repo | cloudflare/cloudflare-typescript |
| api_version_scheme | `semver` |

---

## Cloudflare API surface (from OpenAPI spec and SDK inspection)

The SDK is organized by product area. Core namespaces in the TypeScript client:

```
client.zones           — list, get, create, edit, delete zones
client.dns.records     — CRUD for DNS records within a zone
client.workers.scripts — upload, list, delete, get Workers
client.r2.buckets      — create, list, delete R2 buckets
client.kv.namespaces   — create, list, delete KV namespaces
client.pages.projects  — CRUD for Pages projects
client.firewall.rules  — create, list WAF rules
client.waf.packages    — list, get WAF packages
client.cloudforceOne   — threat intelligence (ThreatEvents, etc.)
client.accounts        — account-level management
client.iam             — identity and access management
```

Core operations for call-site detection: `client.zones.list()`, `client.dns.records.*`, `client.workers.scripts.*`, `new Cloudflare({ apiToken })`.

---

## providers.yaml entry

Add after the `astro` entry (currently the last entry, ends at line 912):

```yaml
- id: cloudflare
  name: Cloudflare
  api_version_scheme: semver
  api_base_urls:
  - https://api.cloudflare.com/client/v4
  sdk_packages:
  - name: cloudflare
    ecosystem: npm
  - name: cloudflare
    ecosystem: pypi
  feeds:
  - kind: npm_dist_tag
    package: cloudflare
    dist_tag: latest
    github_repo: cloudflare/cloudflare-typescript
  - kind: pypi_dist_tag
    package: cloudflare
    github_repo: cloudflare/cloudflare-python
  - kind: github_release
    repo: cloudflare/cloudflare-typescript
  - kind: openapi_spec
    url: https://raw.githubusercontent.com/cloudflare/api-schemas/main/openapi.yaml
  - kind: security_advisory
    package: cloudflare
    ecosystem: npm
  - kind: security_advisory
    package: cloudflare
    ecosystem: pypi
  - kind: ts_exports_diff
    package: cloudflare
```

**Note:** rubygems gem `cloudflare-ruby` has only 1,903 total downloads and is unmaintained (v0.5.0). Not worth adding until there is evidence of real usage.

---

## Skill file: src/depfix/providers/skills/provider_cloudflare.md

```markdown
# Cloudflare scan skill

## SDK packages
- npm: `cloudflare`
- pypi: `cloudflare`

## Import shapes to look for

### JavaScript / TypeScript
```
import Cloudflare from 'cloudflare'
const Cloudflare = require('cloudflare')
import { Cloudflare } from 'cloudflare'
```

Client construction:
```typescript
const client = new Cloudflare({ apiToken: process.env.CLOUDFLARE_API_TOKEN });
const client = new Cloudflare({ apiKey: key, email: email }); // legacy key+email auth
```

### Python
```python
import cloudflare
from cloudflare import Cloudflare

client = Cloudflare(api_token=os.environ.get("CLOUDFLARE_API_TOKEN"))
client = Cloudflare(api_key=key, api_email=email)  # legacy
```

## Call sites to look for

### DNS / Zones (most common)
- `client.zones.list()`, `client.zones.get(zoneId)`
- `client.dns.records.list({ zone_id })`, `client.dns.records.create(...)`, `client.dns.records.update(...)`

### Workers
- `client.workers.scripts.update(name, ...)`, `client.workers.scripts.list(...)`
- `client.workers.routes.create(...)`, `client.workers.domains.list(...)`

### Storage (R2, KV)
- `client.r2.buckets.create(...)`, `client.r2.buckets.list(...)`
- `client.kv.namespaces.create(...)`, `client.kv.namespaces.list(...)`

### Pages
- `client.pages.projects.create(...)`, `client.pages.deployments.create(...)`

### Security
- `client.waf.packages.list(...)`, `client.firewall.rules.create(...)`
- `client.cloudforceOne.threatEvents.create(...)` (v7+ shape)

## Where to look first
1. `grep("CLOUDFLARE_API_TOKEN", "")` — the canonical env var.
2. `grep("cloudflare", "package.json")` or `grep("cloudflare", "requirements.txt")`.
3. DNS/infrastructure scripts: `scripts/dns/`, `infra/`, `deploy/`, `ops/`.
4. Wrangler config: `wrangler.toml` — confirms Workers usage.
5. In Python: `from cloudflare import Cloudflare` or `import cloudflare`.

## Breaking-change context

### v7.0.0 (2026-07-09) — major API restructuring
This was a full-surface reorganization. Methods moved between namespaces.
Common renames in v7:
- Workers API reorganized under `client.workers.*`
- Threat Intelligence moved to `client.cloudforceOne.*`

### v7.1.0 (2026-08-17) — BREAKING CHANGE IN MINOR RELEASE
- `cloudforceOne.threatEvents.indicatorTypes` was renamed/restructured.
- Callers using this path will break on v7.0 → v7.1 upgrade.
- This is the signature risk: Cloudflare ships breaking changes in minors.

### Pre-v4 legacy (< 2023)
- Older codebases may use `require('cloudflare')` with the v2/v3 API shapes.
- Old API used positional arguments and callbacks, not async/await.
- Old: `const cf = new Cloudflare(email, key)` (positional, not object)
- New: `new Cloudflare({ apiToken: ... })`

## Anchors (fallback signals)
- URL: `api.cloudflare.com`
- Env var: `CLOUDFLARE_API_TOKEN` or `CF_API_TOKEN`
- Config file: `wrangler.toml` (Workers), `cloudflare.json`
```

---

## Known breaking changes

| Version | Date | Breaking change |
|---|---|---|
| v7.0.0 | 2026-07-09 | "This is a major release" — full API restructuring across Workers, DNS, Threat Intel namespaces |
| v7.1.0 | 2026-08-17 | **Breaking in minor**: `cloudforceOne.threatEvents.indicatorTypes` renamed |
| v4.0.0 | ~2023 | Full SDK regeneration with Stainless — `new Cloudflare(email, key)` → `new Cloudflare({ apiToken })` |
| v5.0.0 | ~2024 | Initial stable after Stainless migration; various async API changes |

**Key pattern:** Cloudflare ships breaking changes in minor versions (v7.1), not just majors. Standard semver tooling will not warn customers. This makes depfix particularly valuable for Cloudflare users.

---

## Seed repo recommendation

To test the cloudflare scanner, create `bedilk/seed-cloudflare` containing:

```typescript
// src/dns.ts
import Cloudflare from 'cloudflare';

const client = new Cloudflare({ apiToken: process.env.CLOUDFLARE_API_TOKEN });
const ZONE_ID = process.env.CF_ZONE_ID!;

export async function listDnsRecords() {
  return client.dns.records.list({ zone_id: ZONE_ID });
}

export async function createARecord(name: string, content: string) {
  return client.dns.records.create({
    zone_id: ZONE_ID,
    name,
    type: 'A',
    content,
    ttl: 3600,
  });
}

export async function listZones() {
  return client.zones.list();
}
```

```
// package.json: "cloudflare": "^6.0.0"  (intentionally one major behind 7.x)
```

Expected scan output: 3 call-sites (`client.dns.records.list`, `client.dns.records.create`, `client.zones.list`), drift v6→v7 detected, plan generated with v7 breaking change context.

---

## Implementation checklist for implementer

1. **Add providers.yaml entry** — paste the YAML block above at the end of providers.yaml (after `astro`)
2. **Create skill file** — `src/depfix/providers/skills/provider_cloudflare.md` from the template above
3. **Update provider count test** — `tests/unit/test_provider_loader.py` has `assert len(enabled) == N`; increment N by 1
4. **Verify spec URL** — `curl -s -o /dev/null -w "%{http_code}" "https://raw.githubusercontent.com/cloudflare/api-schemas/main/openapi.yaml"` should return `200`
5. **Run make test** — must pass (unit tests, no LLM)
6. **Optionally create seed repo** — `bedilk/seed-cloudflare` with the above fixture

---

## Verification commands

```bash
# Verify OpenAPI spec URL
curl -s -o /dev/null -w "%{http_code}" \
  "https://raw.githubusercontent.com/cloudflare/api-schemas/main/openapi.yaml"
# Expected: 200

# Check npm downloads/month
curl -s "https://api.npmjs.org/downloads/point/last-month/cloudflare"
# Expected: {"downloads":~12855815,...}

# Check npm latest version
curl -s "https://registry.npmjs.org/cloudflare/latest" | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['version'])"
# Expected: 7.3.0 (or newer)

# Check pypi latest version
curl -s "https://pypi.org/pypi/cloudflare/json" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(d['info']['version'])"
# Expected: 5.9.0 (or newer)

# After adding to providers.yaml, smoke test:
bash scripts/test_pipeline.sh cloudflare:bedilk/seed-cloudflare
```

---

## Why Cloudflare next (after resend)

1. **Volume**: 12.9M npm downloads/month — 2nd highest uncovered provider
2. **Pain**: Ships breaking changes in minor releases (v7.1.0 confirmed). Standard SemVer guards don't protect users.
3. **Stainless SDK**: Same generated pattern as Anthropic/OpenAI — depfix already knows how to parse the `ts_exports_diff` output for this SDK shape
4. **OpenAPI spec**: Maintained in a dedicated `cloudflare/api-schemas` repo, clean OpenAPI 3.0.3
5. **Coverage gap**: Cloudflare is the #1 infrastructure API not yet in providers.yaml

---

*All URLs verified 2026-10-05. OpenAPI spec at OpenAPI 3.0.3, extensive API coverage across DNS/Workers/R2/KV/Pages/Security. Stainless-generated SDK, same pattern as existing providers.*
