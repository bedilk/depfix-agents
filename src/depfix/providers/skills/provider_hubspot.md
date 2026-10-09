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
