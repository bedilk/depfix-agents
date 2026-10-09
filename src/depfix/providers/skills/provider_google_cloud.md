# Google Cloud Client Libraries scan skill

## SDK packages
- npm: `@google-cloud/storage` (Cloud Storage — primary)
- npm: `@google-cloud/bigquery` (BigQuery)
- npm: `@google-cloud/pubsub` (Pub/Sub)
- npm: `@google-cloud/firestore` (Firestore Admin)
- pypi: `google-cloud-storage` (Cloud Storage)
- pypi: `google-cloud-bigquery` (BigQuery)
- pypi: `google-cloud-pubsub` (Pub/Sub)

## Import patterns

### JavaScript / TypeScript
```javascript
import { Storage } from '@google-cloud/storage';
const { Storage } = require('@google-cloud/storage');
import { BigQuery } from '@google-cloud/bigquery';
```

Client construction:
```javascript
const storage = new Storage({ projectId });
const storage = new Storage({ projectId, keyFilename: '/path/to/key.json' });
const storage = new Storage(); // ADC (Application Default Credentials)
```

### Python
```python
from google.cloud import storage
from google.cloud import bigquery
from google.cloud import pubsub_v1

client = storage.Client(project='my-project')
client = storage.Client()  # ADC
```

## Call sites to look for

### Cloud Storage (primary tracked service)
- `storage.bucket('bucket-name')` — bucket reference
- `bucket.file('object-name')` — file reference
- `await file.save(data, options)` — upload
- `await file.download()` — download
- `await bucket.upload('local-path', options)` — upload from file
- `await file.getSignedUrl({ action: 'read', expires: ... })` — signed URL

### BigQuery
- `const dataset = bigquery.dataset('name')`
- `const [rows] = await bigquery.query({ query: sql })`
- `const [job] = await table.insert(rows)` — streaming insert

### Pub/Sub
- `pubsub.topic('name').publish(data)` — publish message
- `pubsub.subscription('name').on('message', callback)` — subscribe

## Where to look first
1. `grep("@google-cloud/", "package.json")` — package presence
2. `grep("new Storage\b", "")` — Storage constructor
3. `grep("storage.bucket\|gcs.bucket", "")` — bucket calls
4. Common locations: `lib/gcs.ts`, `utils/storage.ts`, `services/gcloud.ts`

## Anchors (fallback signals)
- Environment variables: `GOOGLE_CLOUD_PROJECT`, `GCLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS`
- `google-cloud` in package.json, `google.cloud` in Python imports

## Feeds
- npm: `@google-cloud/storage` package, dist-tag `latest`
- pypi: `google-cloud-storage` project
- github releases: `googleapis/nodejs-storage`
- openapi: `https://raw.githubusercontent.com/googleapis/googleapis/master/google/storage/v2/storage.yaml`

## What "breaking" means for Google Cloud
- Node.js minimum version bumps (separate per library)
- Python minimum version bumps
- Authentication API changes (ADC vs explicit credentials)
- Breaking parameter changes in upload/download methods
- Signed URL API shape changes
- Streaming vs non-streaming response changes
