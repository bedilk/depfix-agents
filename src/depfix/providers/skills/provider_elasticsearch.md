# Elasticsearch Clients scan skill

## SDK packages
- npm: `@elastic/elasticsearch` (JavaScript — primary)
- pypi: `elasticsearch` (Python — primary)
- rubygems: `elasticsearch` (Ruby)

## Import patterns

### JavaScript / TypeScript
```javascript
import { Client } from '@elastic/elasticsearch';
const { Client } = require('@elastic/elasticsearch');
```

Client construction:
```javascript
const client = new Client({ node: 'http://localhost:9200' });
const client = new Client({ cloud: { id: cloudId }, auth: { apiKey } });
```

### Python
```python
from elasticsearch import Elasticsearch, AsyncElasticsearch
from elasticsearch import helpers

client = Elasticsearch("http://localhost:9200")
client = Elasticsearch(cloud_id=cloud_id, api_key=api_key)
```

## Call sites to look for
- `await client.index({ index, document })` — index a document
- `await client.search({ index, query: { ... } })` — search
- `await client.get({ index, id })` — get document
- `await client.delete({ index, id })` — delete document
- `await client.bulk({ operations })` — bulk operations (v8 shape)
- `helpers.bulk(client, operations)` — helper for bulk

## Legacy v7 patterns (flag these)
- `await client.index({ index, type: '_doc', body: { ... } })` — `type` and `body` removed in v8
- `await client.search({ index, body: { query: { ... } } })` — `body` wrapper removed in v8
- `await client.get({ index, type: '_doc', id })` — `type` removed in v8
- `await client.bulk({ body: [...] })` — `body` replaced by `operations` in v8

## v7 → v8 key breaking changes
- **`body` parameter removed** from all request methods — params moved to top-level
- `type` parameter removed everywhere (types deprecated in ES 7, removed in 8)
- `index()` method: `body: {field: val}` → `document: {field: val}`
- `search()` method: `body: { query }` → `query: { ... }` at top level
- `bulk()` method: `body: [...]` → `operations: [...]`
- Response type changed: `body` property removed, data directly on response object
- TypeScript generics improved — type-safe document shapes

## Where to look first
1. `grep("@elastic/elasticsearch", "package.json")` — package presence
2. `grep("new Client\b", "")` — Elasticsearch client constructor
3. `grep("client\.search\|client\.index\|client\.bulk", "")` — primary call sites
4. `grep("body:", "")` combined with ES context — detect v7 `body` parameter pattern

## Anchors (fallback signals)
- Environment variables: `ELASTICSEARCH_URL`, `ELASTIC_CLOUD_ID`, `ELASTICSEARCH_API_KEY`
- URL: `localhost:9200`, `*.elastic.co`, `*.es.io`

## Common wrapper patterns
- `lib/elasticsearch.ts` — singleton client
- `services/search.ts` — search service wrapping the client

## Feeds
- npm: `@elastic/elasticsearch` package, dist-tag `latest`
- pypi: `elasticsearch` project
- github releases: `elastic/elasticsearch-js`
- openapi: `https://raw.githubusercontent.com/elastic/elasticsearch-specification/main/output/openapi/elasticsearch-openapi.json`

## What "breaking" means for Elasticsearch SDK
- v7→v8 `body` parameter removal (affects every single call site)
- `type` parameter removal
- Response shape changes (body wrapper removed)
- Node.js / Python minimum version bumps
- Cloud authentication API changes
