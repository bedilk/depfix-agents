# Twilio Provider Implementation Spec

**Research date:** 2026-10-09  
**Status:** providers.yaml entry exists; skill file written this round  
**Priority:** High — ~47M combined downloads/month (npm 27M + pypi 20M)

---

## Download Volumes (verified 2026-10-09)

| Package | Ecosystem | Latest | Downloads/month |
|---------|-----------|--------|-----------------|
| `twilio` | npm | 6.1.2 | 27,256,874 |
| `twilio` | pypi | 9.11.2 | ~19,597,269 |
| `twilio-ruby` | rubygems | — | — |

Combined: **~47M/month** — highest among all unimplemented skill files.

---

## Package/Module Name

| Ecosystem | Install name | Import name |
|-----------|-------------|-------------|
| npm | `twilio` | `twilio` (no mismatch) |
| pypi | `twilio` | `twilio` (no mismatch) |
| rubygems | `twilio-ruby` | `twilio-ruby` |

No import mismatch (unlike `sentry-sdk`/`sentry_sdk` or `plaid`/`plaid`).

---

## Providers.yaml Entry (already present)

The `twilio` provider is already in providers.yaml with 7 feeds:
- `npm_dist_tag` (twilio)
- `pypi_dist_tag` (twilio)
- `github_release` (twilio/twilio-node)
- `security_advisory` (npm + pypi)
- `openapi_spec` — https://raw.githubusercontent.com/twilio/twilio-oai/main/spec/yaml/twilio_api_v2010.yaml
- `changelog_html`
- `ts_exports_diff`

---

## Breaking Changes by Version

### Node.js (npm: `twilio`)

**v3→v4 (Jan 2023) — HIGH VALUE for detection**

| Old API | New API | Kind |
|---------|---------|------|
| `IpMessagingGrant` | removed (no replacement) | REPORT_ONLY |
| `ConversationsGrant` | deprecated → use `VoiceGrant` | method_removed |
| `say.ssmlEmphasis("x")` | `say.emphasis("x")` | method_renamed |
| `say.ssmlBreak()` | `say.break_()` | method_renamed |
| `say.ssmlLang()` | `say.lang()` | method_renamed |
| `refer.referSip()` | `refer.sip()` | method_renamed |
| `workers('WK...').cumulativeStatistics()` | `workers.cumulativeStatistics()` | signature_changed |
| `AccessToken({...})` without `identity` | requires `identity` in options | signature_changed |
| Node.js < 14 | requires Node.js ≥ 14 | runtime_constraint |

**v4→v5 (Mar 2024)** — SDK rewritten as auto-generated (OpenAPI). No user-facing API changes. `application/json` body support added (additive).

**v5→v6 (Apr 2026) — CURRENT MAJOR**

| Breaking change | Kind |
|-----------------|------|
| Node.js < 20 no longer supported | runtime_constraint |

### Python (pypi: `twilio`)

**v6→v7 (Sep 2021)**

| Old API | New API | Kind |
|---------|---------|------|
| `from twilio.compat import urlencode` | `from urllib.parse import urlencode` | module_removed |
| `token.to_jwt(algorithm='HS512')` | `token.to_jwt()` | signature_changed |
| `from twilio.jwt import compat` | removed | module_removed |
| Python 2.7, 3.4, 3.5 | requires Python ≥ 3.7 | runtime_constraint |

**v7→v8 (Apr 2023) — HIGH VALUE for detection**

| Old API | New API | Kind |
|---------|---------|------|
| `IpMessagingGrant` | removed | REPORT_ONLY |
| `say.ssml_emphasis("x")` | `say.emphasis("x")` | method_renamed |
| `say.ssml_break()` | `say.break_()` | method_renamed |
| `available_phone_number` module | `available_phone_number_country` | module_renamed |
| `workers('WK...').cumulative_statistics()` | `workers.cumulative_statistics()` | signature_changed |
| Python 3.6 | requires Python ≥ 3.7 | runtime_constraint |

**v8→v9 (Feb 2024)** — SDK rewritten as auto-generated (OpenAPI). No user-facing API changes.

---

## providers.yaml Skill Reference

The entry should reference: `skills/provider_twilio.md`

```yaml
  skill_file: provider_twilio.md
```

Add this field to the existing twilio entry.

---

## Skill File

Written: `src/depfix/providers/skills/provider_twilio.md`

Key patterns documented:
- `require('twilio')` / `from twilio.rest import Client`
- `twilio(accountSid, authToken)` constructor pattern
- JWT grant classes: `AccessToken`, `VoiceGrant`, `IpMessagingGrant` (v3/v7 — broken)
- TwiML SSML old methods (`ssmlEmphasis`, `ssmlBreak`) — renamed in v4/v8
- TaskRouter stats call chaining (WorkerSid removed from stats API)

---

## Feed Strategy

The OpenAPI spec at `twilio_api_v2010.yaml` covers the REST API surface (v2010 voice/SMS/messaging). 
Key limitation: TwiML SDK methods (`VoiceResponse`, `MessagingResponse`) are not in the OpenAPI spec — 
they're generated from a separate TwiML spec. Breaking changes in TwiML methods must be caught via
`ts_exports_diff` or `github_release` feeds.

The `ts_exports_diff` feed should detect method removals (`IpMessagingGrant`, `ConversationsGrant`)
and renames (`ssmlEmphasis` → `emphasis`) at the TypeScript type level.

---

## Seed Repo Fixture

A minimal seed repo for Twilio testing should contain:

**package.json:**
```json
{
  "dependencies": { "twilio": "^3.84.0" }
}
```

**index.js:**
```javascript
const twilio = require('twilio');
const client = twilio(process.env.TWILIO_SID, process.env.TWILIO_TOKEN);

// v3 JWT grant — IpMessagingGrant removed in v4
const AccessToken = twilio.jwt.AccessToken;
const grant = new AccessToken.IpMessagingGrant({ serviceSid: 'IS...' });

// v3 TwiML SSML — renamed in v4
const VoiceResponse = twilio.twiml.VoiceResponse;
const response = new VoiceResponse();
const say = response.say('Hello');
say.ssmlEmphasis('world');
```

---

## Implementer Checklist

- [x] providers.yaml entry exists with all feeds
- [ ] Add `skill_file: provider_twilio.md` to providers.yaml twilio entry
- [x] `src/depfix/providers/skills/provider_twilio.md` written
- [ ] Eval cases for `IpMessagingGrant` removal (v4 call_sites + fix_generation)
- [ ] Eval cases for TwiML SSML method renames (v4/v8)
- [ ] Seed repo fixture: `bedilk/seed-twilio-v3-v4`
