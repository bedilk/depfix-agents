# HubSpot Provider Implementation Spec

**Status:** Ready for implementer  
**Date:** 2026-10-06  
**Researcher:** researcher agent  
**Source tasks:** T-8 (priority ranking — #5 by volume, ranked #4 in recommended add order after Resend/Cloudflare/Plaid)  
**Priority:** 6.3M npm downloads/month; ongoing v1/v2→v3 API migration, ~2 major SDK versions/year

---

## Overview

HubSpot is the dominant CRM for SMB and mid-market, with an API spanning CRM (contacts, companies, deals), CMS, Marketing, and Events. The official `@hubspot/api-client` npm package is at v14 and has shipped 6 major versions in ~3 years. Each major brings method renames, API restructuring across product namespaces, and parameter signature changes.

| Field | Value |
|---|---|
| npm package | `@hubspot/api-client` |
| pypi package | `hubspot-api-client` |
| npm downloads/month | **6,273,605** (verified 2026-10-04) |
| npm latest | 14.0.1 |
| pypi latest | 12.0.0 (mirrors JS, slightly behind) |
| OpenAPI spec | None public (API catalog endpoint 404; no git repo found) |
| GitHub SDK repo (JS) | HubSpot/hubspot-api-nodejs |
| GitHub SDK repo (Python) | HubSpot/hubspot-api-python |
| api_version_scheme | `semver` |
| Feed types | `github_release`, `ts_exports_diff` |

---

## Breaking change history

Major versions (confirmed from GitHub releases):

| Version | Date | Breaking changes |
|---|---|---|
| v14.0.0 | 2026-06-30 | Node.js minimum raised 18→22; `node-fetch` replaced with native `fetch` |
| v13.0.0 | 2025-05-20 | `cms.blogs.blogPostsApi` methods split into `basicApi`/`batchApi`/`multiLanguageApi`; `events.send.customEventDataApi` → `basicApi`; `files.filesApi.archiveGDPR()` → `_delete()`; `updateProperties()` renamed to `updatePropertiesRecursively()` in foldersApi; multiple marketing.events namespace restructures |
| v12.0.0 | 2024-09-23 | CRM GDPR API removed; `crm.companies.GDPRApi` removed; CMS HubDB response types changed; `cms.source_code.sourceCodeExtractApi` removed; `doAsync()`/`getAsyncStatus()` replace `ExtractApi.extractByPath()` |
| v11.0.0 | 2024-02-13 | CRM associations v4: `objectId`/`toObjectId` changed from `number` to `string` across `archive`, `create`, `createDefault`, `getPage` methods |
| v10.0.0 | 2023-09-25 | `cms.sourceCode.contentApi.get()` → `download()`; `replace()` → `createOrUpdate()`; `marketing.events` method moves from `marketingEventsExternalApi` to `basicApi`; parameter reordering in `auditLogs.getPage()` |
| v9.0.0 | 2023-06-08 | CRM pipeline stage API restructuring |

**Rate:** ~2 major SDK versions/year, each with substantial method moves and renames.

---

## providers.yaml entry

Insert after the `sendgrid` entry (currently at line 415):

```yaml
- id: hubspot
  name: HubSpot API Client
  api_version_scheme: semver
  sdk_packages:
  - name: '@hubspot/api-client'
    ecosystem: npm
  - name: hubspot-api-client
    ecosystem: pypi
  feeds:
  - kind: npm_dist_tag
    package: '@hubspot/api-client'
    dist_tag: latest
    github_repo: HubSpot/hubspot-api-nodejs
  - kind: pypi_dist_tag
    package: hubspot-api-client
    github_repo: HubSpot/hubspot-api-python
  - kind: github_release
    repo: HubSpot/hubspot-api-nodejs
  - kind: security_advisory
    package: '@hubspot/api-client'
    ecosystem: npm
  - kind: security_advisory
    package: hubspot-api-client
    ecosystem: pypi
  - kind: ts_exports_diff
    package: '@hubspot/api-client'
```

---

## Skill file: src/depfix/providers/skills/provider_hubspot.md

```markdown
# HubSpot scan skill

## SDK packages
- npm: `@hubspot/api-client`
- pypi: `hubspot-api-client`

## Import patterns

### JavaScript / TypeScript
```
import { Client } from '@hubspot/api-client'
const { Client } = require('@hubspot/api-client')
const hubspot = require('@hubspot/api-client')
import hubspotClient from '@hubspot/api-client'
```

### Python
```
import hubspot
from hubspot import HubSpot
from hubspot.crm.contacts import ApiClient
```

## Call sites (report these)

### CRM — most commonly broken across major versions
- `hubspotClient.crm.contacts.basicApi.getById(contactId, ...)`
- `hubspotClient.crm.contacts.basicApi.create(...)`
- `hubspotClient.crm.contacts.batchApi.read(...)`
- `hubspotClient.crm.companies.basicApi.getById(companyId, ...)`
- `hubspotClient.crm.deals.basicApi.getById(dealId, ...)`
- `hubspotClient.crm.associations.v4.basicApi.archive(objectType, objectId, ...)` — objectId changed number→string in v11
- `hubspotClient.crm.associations.v4.basicApi.create(objectType, objectId, ...)` — objectId changed number→string in v11

### CMS — restructured in v13
- `hubspotClient.cms.blogs.blogPostsApi.archive(...)` — moved to `basicApi` in v13
- `hubspotClient.cms.blogs.blogPostsApi.create(...)` — moved to `basicApi` in v13
- `hubspotClient.cms.blogs.blogPostsApi.archiveBatch(...)` — renamed `archive` in `batchApi` in v13
- `hubspotClient.cms.sourceCode.contentApi.get(...)` — renamed `download()` in v10
- `hubspotClient.cms.sourceCode.contentApi.replace(...)` — renamed `createOrUpdate()` in v10
- `hubspotClient.cms.source_code.sourceCodeExtractApi.extractByPath(...)` — removed in v12

### Marketing / Events
- `hubspotClient.marketing.events.basicApi.cancel(...)` — moved to `changePropertyApi` in v13
- `hubspotClient.marketing.events.basicApi.complete(...)` — moved to `changePropertyApi` in v13
- `hubspotClient.marketing.events.participantStateApi` — renamed `retrieveParticipantStateApi` in v13
- `hubspotClient.events.send.customEventDataApi` — renamed `basicApi` in v13

### Files
- `hubspotClient.files.filesApi.archiveGDPR(...)` — renamed `_delete()` in v13
- `hubspotClient.files.foldersApi.updateProperties(...)` — renamed `updatePropertiesRecursively()` in v13

## Where to look first
1. `grep("@hubspot/api-client", "package.json")` — scoped name is distinctive.
2. `grep("hubspot-api-client", "requirements.txt")` — Python package.
3. CRM code: `crm/`, `contacts/`, `deals/`, `integrations/hubspot*.ts`.
4. HubSpot client instantiation: `new Client({ accessToken: ... })` or `new Client({ apiKey: ... })`.
5. API method calls follow namespace pattern: `client.<product>.<resource>Api.<method>()`.
```

---

## Key scan patterns for implementer

The HubSpot SDK uses a deeply nested namespace pattern:

```
client.<product>.<resource>Api.<method>()
```

Products: `crm`, `cms`, `marketing`, `events`, `files`, `automation`, `conversations`

Resources under `crm`: `contacts`, `companies`, `deals`, `tickets`, `quotes`, `lineItems`, `objects`, `associations`, `pipelines`, `properties`

The most common call sites are:
- `client.crm.contacts.basicApi.create/getById/update/archive`
- `client.crm.companies.basicApi.create/getById`
- `client.crm.deals.basicApi.create/getById`
- `client.crm.associations.v4.basicApi.*` (broke in v11 with number→string)

---

## Seed repo recommendation

Create `bedilk/seed-hubspot` containing:

```typescript
// src/hubspot.ts
import { Client } from '@hubspot/api-client';

const hubspotClient = new Client({ accessToken: process.env.HUBSPOT_ACCESS_TOKEN });

export async function getContact(contactId: string) {
  return hubspotClient.crm.contacts.basicApi.getById(contactId, ['email', 'firstname', 'lastname']);
}

export async function createDeal(properties: Record<string, string>) {
  return hubspotClient.crm.deals.basicApi.create({ properties });
}

export async function associateObjects(
  objectType: string,
  objectId: number,          // v10/v11-era: number (will break in v11)
  toObjectType: string,
  toObjectId: number,
) {
  return hubspotClient.crm.associations.v4.basicApi.createDefault(
    objectType, objectId, toObjectType, toObjectId
  );
}

export async function getBlogPost(blogPostId: string) {
  return hubspotClient.cms.blogs.blogPostsApi.getById(blogPostId); // moved to basicApi in v13
}
```

```
// package.json: "@hubspot/api-client": "^10.0.0"  (intentionally behind v14)
```

Expected scan: 4 call-sites, drift v10→v14 detected, plan covers associations type change + blogPostsApi moves.

---

## Implementation checklist for implementer

1. **Add providers.yaml entry** — paste the YAML block above after the `sendgrid` entry (line ~449)
2. **Create skill file** — `src/depfix/providers/skills/provider_hubspot.md` from the template above
3. **Update test_provider_count** — increment N by 1 in tests/test_providers.py
4. **run make test** — must pass (unit tests, no LLM)
5. **Optionally create seed repo** — `bedilk/seed-hubspot` with the above fixture

---

## Verification commands

```bash
# Confirm npm download volume
curl -s "https://api.npmjs.org/downloads/point/last-month/@hubspot/api-client"
# Expected: {"downloads":6273605,...}

# Confirm npm latest version
curl -s "https://registry.npmjs.org/@hubspot/api-client/latest" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['version'])"
# Expected: 14.0.1 (or newer)

# Confirm pypi latest
curl -s "https://pypi.org/pypi/hubspot-api-client/json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['info']['version'])"
# Expected: 12.0.0 (or newer)

# Count breaking changes in v13 release notes
curl -s "https://api.github.com/repos/HubSpot/hubspot-api-nodejs/releases/tags/13.0.0" | python3 -c "import sys,json; r=json.load(sys.stdin); print(len(r['body'].split('\n')), 'lines in v13 release notes')"
# Expected: 100+ lines (substantial restructuring)

# After adding to providers.yaml, smoke test:
bash scripts/test_pipeline.sh hubspot:bedilk/seed-hubspot
```

---

## Feed notes (no OpenAPI spec)

HubSpot does **not** publish a public OpenAPI spec. The `api.hubspot.com/api-catalog-public/v1/apis` endpoint returns 404; no public git repo with specs was found. The `ts_exports_diff` feed is the most reliable signal for method-level changes in the TypeScript SDK.

The `github_release` feed gives the human-readable breaking change list (release notes are well-structured with clear "## Breaking Changes" or product headings). A changelog_html feed from `https://developers.hubspot.com/changelog` could be added in the future but the developer docs changelog focuses on REST API changes rather than SDK-level method changes.

**Recommended feed priority:** `ts_exports_diff` (catches method renames) + `github_release` (gives human-readable context for LLM fix generation).

---

*Verified data:*
- *npm downloads: 2026-10-04 via npmjs.com API*
- *npm latest: 14.0.1 (2026-07-01)*
- *pypi latest: 12.0.0*
- *Breaking change details: GitHub releases via api.github.com (v10–v14 confirmed)*
- *No OpenAPI spec: confirmed 404 on api.hubspot.com/api-catalog-public/v1/apis and no public spec repo found*
