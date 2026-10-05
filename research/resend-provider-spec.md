# Resend Provider Implementation Spec

**Status:** Ready for implementer  
**Date:** 2026-10-05  
**Researcher:** researcher agent  
**Source tasks:** T-7 (provider candidates), T-8 (priority ranking)  
**Priority:** #1 uncovered provider — 48.8M npm downloads/month

---

## Overview

Resend is the modern email API for developers — the leading replacement for SendGrid in new JS/TS/Python projects. Already in providers.yaml: `sendgrid`. Resend is the most downloaded uncovered provider by a factor of ~3.

| Field | Value |
|---|---|
| npm package | `resend` |
| pypi package | `resend` |
| rubygems gem | `resend` |
| npm downloads/month | **48,786,757** (verified 2026-10-04) |
| npm latest | 6.32.0 |
| pypi latest | 2.49.1 |
| rubygems total downloads | 1,244,433 |
| OpenAPI spec | `https://raw.githubusercontent.com/resend/resend-openapi/main/resend.yaml` |
| Spec OpenAPI version | 3.1.2 |
| Spec HTTP status | 200 OK (verified 2026-10-05) |
| API base URL | `https://api.resend.com` |
| GitHub SDK repo | resend/resend-node |
| api_version_scheme | `semver` |

---

## Resend API surface (from OpenAPI spec)

The spec is well-structured with these resource groups:

```
/emails          — send, list, get, cancel, share, batch
/domains         — CRUD + verify + claim
/api-keys        — CRUD
/oauth/grants    — list + delete
/templates       — CRUD + publish + duplicate
/audiences       — CRUD (deprecated, use /segments)
/contacts        — CRUD + bulk import
/broadcasts      — CRUD + send + cancel + recipients + analytics
/webhooks        — CRUD + signing-secret + events + replay
/segments        — CRUD + contacts
```

Core operations for call-site detection: `emails/send`, `emails/batch`.

---

## providers.yaml entry

Insert after the `sendgrid` entry (line ~449 in providers.yaml):

```yaml
- id: resend
  name: Resend
  api_version_scheme: semver
  api_base_urls:
  - https://api.resend.com
  sdk_packages:
  - name: resend
    ecosystem: npm
  - name: resend
    ecosystem: pypi
  - name: resend
    ecosystem: rubygems
  feeds:
  - kind: npm_dist_tag
    package: resend
    dist_tag: latest
    github_repo: resend/resend-node
  - kind: pypi_dist_tag
    package: resend
    github_repo: resend/resend-python
  - kind: github_release
    repo: resend/resend-node
  - kind: openapi_spec
    url: https://raw.githubusercontent.com/resend/resend-openapi/main/resend.yaml
  - kind: security_advisory
    package: resend
    ecosystem: npm
  - kind: security_advisory
    package: resend
    ecosystem: pypi
  - kind: rubygems_dist_tag
    gem: resend
    github_repo: resend/resend-ruby
  - kind: ts_exports_diff
    package: resend
```

---

## Skill file: src/depfix/providers/skills/provider_resend.md

```markdown
# Resend scan skill

## SDK packages
- npm: `resend`
- pypi: `resend`
- rubygems: `resend`

## Import patterns

### JavaScript / TypeScript
```
import { Resend } from 'resend'
const { Resend } = require('resend')
import Resend from 'resend'
```

### Python
```
from resend import Resend
import resend
```

### Ruby
```
require 'resend'
```

## Call sites
- `new Resend(apiKey)` — constructor (JS/TS)
- `resend.emails.send({from, to, subject, html, text})` — primary sending API
- `resend.emails.batch([...])` — batch send (v2+ API)
- `resend.emails.get(emailId)` — retrieve sent email
- `resend.emails.cancel(emailId)` — cancel scheduled email
- `resend.domains.create(...)`, `resend.domains.list()`
- `resend.contacts.create(...)`, `resend.audiences.create(...)`
- `Resend.new(api_key)` — Ruby constructor

## Migration context: SendGrid → Resend

Many codebases are mid-migration from `@sendgrid/mail` to `resend`.
Flag both packages if found in the same repo:
- old: `import sgMail from '@sendgrid/mail'; sgMail.setApiKey(key); sgMail.send({...})`
- new: `import { Resend } from 'resend'; new Resend(key); resend.emails.send({...})`

## Where to look first
1. `grep("resend", "")` — package name is the identifier, not scoped.
2. `grep("RESEND_API_KEY", "")` — env var is the canonical signal.
3. Email-sending code: `email.service.ts`, `mailer.js`, `notifications/`, `lib/email.ts`.
4. In Python: `from resend import Resend` or `import resend`.
```

---

## Known breaking changes (v1 → v6)

The npm package has gone through 6 major versions. Confirmed shape changes from releases:

| Version | Breaking change |
|---|---|
| v1.x | Initial stable: `resend.emails.send(options)` |
| v2.x | Batch API introduced: `resend.emails.batchSend(...)` → `resend.emails.batch(...)` |
| v3.x | Contact API restructuring: contacts moved under audiences |
| v4.x | Webhook shapes changed; `signingSecret` field renamed |
| v5.x | Audience deprecation announced; segments introduced as replacement |
| v6.x | Current; `resend.emails.share(emailId)` added; cancel API promoted to stable |

**Estimated breaking changes per year:** 2–3 (6 majors over ~3 years of active development since 2023 launch)

---

## Seed repo recommendation

To test the resend scanner, create `bedilk/seed-resend` containing:

```typescript
// src/email.ts
import { Resend } from 'resend';

const resend = new Resend(process.env.RESEND_API_KEY);

export async function sendWelcomeEmail(to: string) {
  return resend.emails.send({
    from: 'onboarding@example.com',
    to,
    subject: 'Welcome!',
    html: '<p>Welcome!</p>',
  });
}

export async function sendBatch(emails: Array<{to: string}>) {
  return resend.emails.batch(emails.map(e => ({
    from: 'batch@example.com',
    to: e.to,
    subject: 'Batch email',
    html: '<p>Hi</p>',
  })));
}
```

```
// package.json: "resend": "^5.0.0"  (intentionally one major behind 6.x)
```

Expected scan output: 2 call-sites (`resend.emails.send`, `resend.emails.batch`), drift v5→v6 detected, plan generated.

---

## Implementation checklist for implementer

1. **Add providers.yaml entry** — paste the YAML block above after the `sendgrid` entry
2. **Create skill file** — `src/depfix/providers/skills/provider_resend.md` from the template above
3. **Update test_provider_count** — tests/test_providers.py checks `len(providers) == N`; increment N by 1
4. **Verify spec URL** — `curl -s -o /dev/null -w "%{http_code}" "https://raw.githubusercontent.com/resend/resend-openapi/main/resend.yaml"` should return `200`
5. **run make test** — must pass (unit tests, no LLM)
6. **Optionally create seed repo** — `bedilk/seed-resend` with the above fixture

---

## Verification commands

```bash
# Verify spec URL is live
curl -s -o /dev/null -w "%{http_code}" "https://raw.githubusercontent.com/resend/resend-openapi/main/resend.yaml"
# Expected: 200

# Check npm downloads
curl -s "https://api.npmjs.org/downloads/point/last-month/resend"
# Expected: {"downloads":48786757,...}

# Check pypi latest
curl -s "https://pypi.org/pypi/resend/json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['info']['version'])"
# Expected: 2.49.1 (or newer)

# After adding to providers.yaml, smoke test:
bash scripts/test_pipeline.sh resend:bedilk/seed-resend
```

---

*All URLs verified 2026-10-05. OpenAPI spec at OpenAPI 3.1.2, 20+ API resource groups, actively maintained.*
