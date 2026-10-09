# Algolia JavaScript Client scan skill

## SDK packages
- npm: `algoliasearch` (JavaScript — primary)
- npm: `@algolia/client-search` (lower-level v5 client)
- npm: `react-instantsearch` (React UI)

## Import patterns

### JavaScript / TypeScript — v5 (current, 2024)
```javascript
import { algoliasearch } from 'algoliasearch';      // named export in v5!
const { algoliasearch } = require('algoliasearch');
```

Client construction:
```javascript
const client = algoliasearch(appId, apiKey);
```

### JavaScript / TypeScript — v4 (legacy, flag these)
```javascript
import algoliasearch from 'algoliasearch';           // default export in v4
const algoliasearch = require('algoliasearch');
```

Client construction:
```javascript
const client = algoliasearch(appId, apiKey);         // same shape
const index = client.initIndex('indexName');          // v4 only!
```

## Call sites to look for

### v5 canonical
- `const client = algoliasearch(appId, apiKey)`
- `await client.search({ requests: [{ indexName, query }] })` — multi-index search
- `await client.searchSingleIndex({ indexName, searchParams: { query } })` — single index
- `await client.saveObject({ indexName, body })` — index object
- `await client.deleteObject({ indexName, objectID })` — delete object
- `await client.setSettings({ indexName, indexSettings })` — configure index

### v4 patterns (flag these)
- `const index = client.initIndex('indexName')` — `initIndex` REMOVED in v5
- `await index.search(query, searchOptions)` — index-level search, REMOVED in v5
- `await index.saveObject(object)` — index-level save, REMOVED in v5
- `await index.deleteObject(objectID)` — index-level delete, REMOVED in v5
- `await index.setSettings(settings)` — index-level settings, REMOVED in v5
- `await client.copyIndex(from, to)` — renamed/restructured in v5
- `client.search([{ indexName, query, params }])` — v4 multi-search → different in v5

## v4 → v5 key breaking changes (2024)
- **`client.initIndex()` removed entirely** — the most impactful change; affects every search call
- All operations moved to client-level with `indexName` parameter
- Import changed: default export → named export (`import algoliasearch from ...` → `import { algoliasearch } from ...`)
- Search response shape changed: `result.hits` shape differs; `nbPages` vs `nbHits` pagination
- `client.search()` multi-index signature changed: `{ requests: [...] }` shape
- Async/callback API streamlined
- `MultipleQueriesQuery` type renamed to `SearchMethodParams`

## Where to look first
1. `grep("algoliasearch", "package.json")` — package presence
2. `grep("client.initIndex\|index\.search\|index\.saveObject", "")` — detect v4 patterns
3. `grep("algoliasearch(", "")` — constructor call
4. Common locations: `lib/algolia.ts`, `utils/search.ts`, `services/search.ts`

## Anchors (fallback signals)
- Environment variables: `ALGOLIA_APP_ID`, `ALGOLIA_API_KEY`, `NEXT_PUBLIC_ALGOLIA_*`

## Common wrapper patterns
- `lib/algolia.ts` — singleton client + index exports
- React: `InstantSearch` component from `react-instantsearch` wrapping the client

## Feeds
- npm: `algoliasearch` package, dist-tag `latest`
- github releases: `algolia/algoliasearch-client-javascript`
- openapi: `https://raw.githubusercontent.com/algolia/api-clients-automation/main/specs/bundled/search.yml`

## What "breaking" means for Algolia
- `initIndex()` removal (v5 — affects every index operation)
- Import shape change (default → named export)
- Search response shape changes
- Index-level methods moving to client-level with `indexName` parameter
- Rate limiting / batching API changes
