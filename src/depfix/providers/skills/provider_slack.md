# Slack Web API SDK scan skill

## SDK packages
- npm: `@slack/web-api` (REST client — primary)
- npm: `@slack/bolt` (app framework — Bolt)
- npm: `@slack/socket-mode` (socket mode client)
- pypi: `slack-sdk` (Python SDK — module name: `slack_sdk`)
- pypi: `slack-bolt` (Python Bolt framework)

## Import patterns

### JavaScript / TypeScript
```javascript
import { WebClient } from '@slack/web-api';
const { WebClient } = require('@slack/web-api');

// Bolt app framework
import { App } from '@slack/bolt';
const { App } = require('@slack/bolt');
```

Client construction:
```javascript
const client = new WebClient(process.env.SLACK_BOT_TOKEN);
const client = new WebClient(token, { logLevel: LogLevel.DEBUG });

// Bolt
const app = new App({ token, signingSecret });
```

### Python
```python
from slack_sdk import WebClient  # module: slack_sdk (package: slack-sdk)
from slack_sdk.web import WebClient
from slack_bolt import App

client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
```

Note: Python package is `slack-sdk` but the module is `slack_sdk` (no hyphen).

## Call sites to look for
- `client.chat.postMessage({ channel, text })` — send message
- `client.chat.update({ channel, ts, text })` — update message
- `client.conversations.list()` — list channels
- `client.users.info({ user })` — user info
- `client.files.upload({ channels, file })` — file upload (v6 change!)
- `client.views.open({ trigger_id, view })` — modals
- `app.message('hello', async ({message, say}) => ...)` — Bolt event handling
- `app.action('button_click', async ({ack, body}) => ...)` — Bolt action handling

## v5 → v6 key breaking changes
- `client.files.upload()` deprecated → replaced with `client.files.getUploadURLExternal()` + `client.files.completeUploadExternal()` (two-step)
- Old: `await client.files.upload({ channels: [channelId], content: '...' })`
- New: requires calling `getUploadURLExternal()` then `completeUploadExternal()`

## Legacy patterns (flag these)
- `@slack/client` package → replaced by `@slack/web-api` (old package, deprecated)
- `{ WebClient } from '@slack/client'` → `{ WebClient } from '@slack/web-api'`
- `client.files.upload({ channels, file, content })` → two-step in v6+

## Where to look first
1. `grep("@slack/web-api\|@slack/bolt", "package.json")` — package presence
2. `grep("new WebClient\|WebClient(", "")` — client constructor
3. `grep("client.chat.postMessage", "")` — primary call site
4. Bolt apps: `app.message(`, `app.action(`, `app.event(`
5. Common locations: `lib/slack.ts`, `listeners/`, `handlers/`

## Anchors (fallback signals)
- Environment variables: `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `SLACK_APP_TOKEN`
- URL: `slack.com/api/`

## Common wrapper patterns
- `lib/slack.ts` singleton `WebClient` export
- Bolt app often in `app.ts` or `index.ts`
- Middleware for token resolution in multi-workspace apps

## Feeds
- npm: `@slack/web-api` package, dist-tag `latest`
- pypi: `slack-sdk` project
- github releases: `slackapi/node-slack-sdk`
- openapi: `https://raw.githubusercontent.com/slackapi/slack-api-specs/master/web-api/slack_web_openapi_v2.json`

## What "breaking" means for Slack SDK
- File upload API change (v6 — two-step upload)
- Method parameter shape changes
- Event type renames in the Slack API itself (reflected in SDK types)
- Socket mode / event API versioning
- Python module path changes between major versions
