# Anthropic scan skill

## SDK packages
- npm: `@anthropic-ai/sdk`
- pypi: `anthropic`
- rubygems: `anthropic`

## Import patterns

### JavaScript / TypeScript
```javascript
import Anthropic from '@anthropic-ai/sdk';          // ESM default
const Anthropic = require('@anthropic-ai/sdk');     // CJS
import { Anthropic } from '@anthropic-ai/sdk';      // named import
```

Client construction:
```javascript
const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
const client = new Anthropic(); // reads ANTHROPIC_API_KEY from env
```

### Python
```python
import anthropic
from anthropic import Anthropic
from anthropic import AsyncAnthropic
```

Client construction:
```python
client = Anthropic()
client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
```

## Call sites to look for (current canonical)
- `client.messages.create({model, max_tokens, messages})`
- `client.messages.stream(...)` — streaming variant
- `client.beta.tools.messages.create(...)` — legacy tools endpoint (pre-v0.20)

## Legacy call sites (flag these)
- `client.completions.create(...)` — v0.x legacy, removed in v0.20
- `client.messages.create({stream: true})` — old streaming pattern
- `stream.on('text', ...)` — pre-v0.20 streaming event API

## Streaming API change (v0.20 → v0.131)
The `fixture_change` in providers.yaml documents this migration:
- Old: `const stream = client.messages.create({..., stream: true})`, iterate raw events
- New: `const stream = client.messages.stream({model, max_tokens, messages})`
  - `await stream.finalMessage()` — wait for complete response
  - `for await (const event of stream)` — iterate incremental events

If you find `.stream({stream: true})` or `.create({stream: true})` call sites, flag them.

## Where to look first
1. `grep("@anthropic-ai/sdk", "")` or `grep("anthropic", "requirements")` — package presence
2. `grep("client.messages.create", "")` — primary call site
3. `grep("Anthropic(", "")` — constructor call
4. Often in `lib/anthropic.ts`, `utils/ai.ts`, `services/llm.ts`, or `app/api/` route handlers

## Anchors (fallback signals)
- URL: `api.anthropic.com`
- Header: `x-api-key` (combined with `anthropic.com` context)
- Model strings: `claude-opus-*`, `claude-sonnet-*`, `claude-haiku-*`, `claude-3-*`, `claude-2.*`

## Common wrapper patterns
- `lib/anthropic.ts` — singleton client export
- `utils/claude.ts` — wrapper around messages.create
- One hop is expected — downgrade to `medium` confidence, don't reject

## Feeds
- npm: `@anthropic-ai/sdk` package, dist-tag `latest`
- pypi: `anthropic` project
- github releases: `anthropics/anthropic-sdk-typescript`, `anthropics/anthropic-sdk-python`
- openapi: `https://raw.githubusercontent.com/anthropics/anthropic-sdk-python/main/api.json`

## What "breaking" means for Anthropic
- Streaming API shape changes (v0.20 migration documented above)
- New required parameters on `messages.create` (e.g., `max_tokens` was already required)
- Model deprecation (claude-2, claude-instant-1 series)
- Beta endpoint graduation or removal (`client.beta.*`)
- Python minimum version bumps (3.7+ required since v0.10)
