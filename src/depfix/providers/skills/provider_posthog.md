# PostHog Node.js SDK scan skill

## SDK packages
- npm: `posthog-node` (Node.js / server-side)
- npm: `posthog-js` (browser / React)
- pypi: `posthog` (Python)

## Import patterns

### JavaScript / TypeScript (Node.js)
```javascript
import { PostHog } from 'posthog-node';
const { PostHog } = require('posthog-node');
```

Client construction:
```javascript
const client = new PostHog(apiKey, { host: 'https://us.posthog.com' });
// or
const client = new PostHog(process.env.POSTHOG_API_KEY);
```

### Python
```python
from posthog import Posthog
import posthog   # functional API

client = Posthog(project_api_key=key, host='https://us.posthog.com')
```

## Call sites to look for
- `client.capture({ distinctId, event, properties })` — track event
- `client.identify({ distinctId, properties })` — identify user
- `client.isFeatureEnabled(flagKey, distinctId)` — feature flags
- `client.getFeatureFlag(flagKey, distinctId)` — get flag value
- `client.groupIdentify({ groupType, groupKey, properties })` — group analytics
- `await client.shutdown()` — graceful shutdown (important: flush on exit)

## Legacy patterns (flag these)
- `posthog.capture('event', { ...properties })` — old functional API (pre-v3 Node)
- `posthog.identify('distinctId', { ...properties })` — old functional API
- PostHog API key passed as `POSTHOG_PROJECT_API_KEY` vs newer `POSTHOG_API_KEY`

## v2 → v3 key breaking changes
- Client class renamed: `PostHogClient` → `PostHog`
- Constructor signature: `new PostHog(apiKey, options)` — `options.host` required for EU customers
- `client.shutdown()` now required for graceful exit (added explicit async shutdown)
- Default host changed to require explicit `host` for non-US

## Where to look first
1. `grep("posthog-node\|posthog-js", "package.json")` — package presence
2. `grep("new PostHog\|PostHog(", "")` — constructor
3. `grep("client.capture\|posthog.capture", "")` — primary call site
4. Common locations: `lib/posthog.ts`, `utils/analytics.ts`, `lib/analytics.ts`

## Anchors (fallback signals)
- Environment variables: `POSTHOG_API_KEY`, `NEXT_PUBLIC_POSTHOG_KEY`, `POSTHOG_HOST`
- URL: `posthog.com`, `us.posthog.com`, `eu.posthog.com`

## Feeds
- npm: `posthog-node` package, dist-tag `latest`
- github releases: `PostHog/posthog-js`
- openapi: `https://app.posthog.com/api/schema/`

## What "breaking" means for PostHog
- Client class renames
- Constructor signature changes
- Feature flag API shape changes
- Shutdown/flush behavior changes
- Region-specific host requirement changes
