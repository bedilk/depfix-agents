# Twilio scan skill

## SDK packages
- npm: `twilio` (v6.1.2, ~27M/month)
- pypi: `twilio` (v9.11.2, ~20M/month)
- rubygems: `twilio-ruby`

## Import patterns (JS/TS)

```
const twilio = require('twilio')
const client = require('twilio')(accountSid, authToken)
import twilio from 'twilio'
const Twilio = require('twilio')
```

## Construction & bindings

```javascript
const client = twilio(accountSid, authToken)
const client = new twilio.Twilio(accountSid, authToken)
```

Binding names: `client`, `twilioClient`.

## Import patterns (Python)

```python
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
from twilio.twiml.messaging_response import MessagingResponse
from twilio.jwt.access_token import AccessToken
```

## Call sites (report these)
- `client.messages.create(...)` — SMS/MMS send
- `client.calls.create(...)` — programmatic calls
- `client.studio.v1.flows(...).executions.create(...)` — Studio flows
- `client.verify.v2.services(...).verifications.create(...)` — Verify
- `client.taskrouter.v1.workspaces(...).workers(...).cumulativeStatistics()` — TaskRouter stats
- `token.to_jwt(...)` — JWT access tokens
- `new AccessToken(...)`, `new VoiceGrant(...)`, `new ConversationsGrant(...)` (v3/v7 — flag it)
- TwiML methods: `say.ssmlEmphasis(...)`, `say.ssmlBreak(...)` (v3/v7 — flag these)

## Where to look first
1. `grep("require\\(['\"]twilio['\"]\\)|from twilio", "")` — the package name is distinctive.
2. Follow the binding to find `client.messages`, `client.calls`, `client.verify` usages.
3. `grep("AccessToken|VoiceGrant|ConversationsGrant|IpMessagingGrant", "")` — JWT grant usages.

## Key breaking changes by version

### Node.js v3→v4 (Jan 2023)
- **`IpMessagingGrant` removed** — use `VoiceGrant` instead (REPORT_ONLY if no replacement)
- **`ConversationsGrant` deprecated** — use `VoiceGrant`
- **Node.js minimum raised to 14** (dropped <14 support)
- **TwiML SSML method renames** — `say.ssmlEmphasis("x")` → `say.emphasis("x")`, same for `ssmlBreak`→`break_`, `ssmlLang`→`lang`, `ssmlP`→`p`, `ssmlPhoneme`→`phoneme`, `ssmlProsody`→`prosody`, `ssmlS`→`s`, `ssmlSayAs`→`sayAs`, `ssmlSub`→`sub`, `ssmlW`→`w`
- **TwiML Refer method** — `refer.referSip()` → `refer.sip()`
- **TaskRouter Workers Stats API** — `workers('WK...').cumulativeStatistics()` → `workers.cumulativeStatistics()` (WorkerSid param removed)
- **AccessToken** — `identity` now required in options object
- **Type change** — `subresourceUris` and `links` properties: `object` → `Record<string, string>`

### Node.js v4→v5 (Mar 2024)
- SDK auto-generated from OpenAPI; no documented public API breaking changes
- Adds `application/json` request body support

### Node.js v5→v6 (Apr 2026)
- **Node.js minimum raised to 20** (dropped <20 support)
- No changes to the SDK's public JavaScript API

### Python v6→v7 (Sep 2021)
- **Python 2.7, 3.4, 3.5 support dropped**
- **`compat.py` removals** — `from twilio.compat import urlencode` → `from urllib.parse import urlencode`
- **`token.to_jwt(algorithm=...)` removed** — algorithm override no longer accepted
- **PyJWT upgraded to >=2.0.0** — may break if pinned to PyJWT 1.x

### Python v7→v8 (Apr 2023)
- **Python 3.6 dropped** (3.7+ required)
- **`IpMessagingGrant` removed** — same as Node.js v4
- **TwiML SSML method renames** — same pattern as Node.js v4: `say.ssml_emphasis("x")` → `say.emphasis("x")`
- **Module rename** — `twilio.rest.api.v2010.account.available_phone_number` → `twilio.rest.api.v2010.account.available_phone_number_country`
- **TaskRouter Workers Stats** — `workers('WK...').cumulative_statistics()` → `workers.cumulative_statistics()`
- **`_properties` dict removed** — do not depend on `instance._properties` (internal)

### Python v8→v9 (Feb 2024)
- SDK auto-generated from OpenAPI; no documented public API breaking changes

## Do NOT
- Do not flag `twilio(...)` as a removal if it appears with two string arguments — that is the normal client constructor call (account SID + auth token).
- Do not report `IpMessagingGrant` as an error unless the file imports and uses it (it was a JWT token grant, not a core messaging API).
- TwiML SSML method renames are only breakages when the code actually calls the old `ssmlXxx()` form — new code that already uses `emphasis()/break_()` is fine.
