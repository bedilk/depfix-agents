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
