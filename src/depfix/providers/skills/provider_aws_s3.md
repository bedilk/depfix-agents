# AWS SDK for JavaScript (S3) scan skill

## SDK packages
- npm: `@aws-sdk/client-s3` (v3, current)
- npm: `aws-sdk` (v2, legacy — still ~40M downloads/month)
- npm: `@aws-sdk/lib-storage` (multipart upload helper)
- npm: `@aws-sdk/s3-request-presigner` (presigned URLs)

## Import patterns

### JavaScript / TypeScript — v3 (current)
```javascript
import { S3Client, GetObjectCommand, PutObjectCommand, DeleteObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';
import { Upload } from '@aws-sdk/lib-storage';
```

Client construction:
```javascript
const client = new S3Client({ region: 'us-east-1' });
const client = new S3Client({ region, credentials: { accessKeyId, secretAccessKey } });
```

### JavaScript / TypeScript — v2 (legacy, flag these)
```javascript
const AWS = require('aws-sdk');
import AWS from 'aws-sdk';
const s3 = new AWS.S3({ region: 'us-east-1' });
```

## Call sites to look for

### v3 canonical
- `await client.send(new GetObjectCommand({ Bucket, Key }))` — get object
- `await client.send(new PutObjectCommand({ Bucket, Key, Body }))` — put object
- `await client.send(new DeleteObjectCommand({ Bucket, Key }))` — delete
- `await client.send(new ListObjectsV2Command({ Bucket }))` — list
- `await getSignedUrl(client, new GetObjectCommand(...), { expiresIn })` — presigned URL
- `new Upload({ client, params }).done()` — multipart upload

### v2 legacy (flag these — major migration needed)
- `s3.getObject({ Bucket, Key }).promise()` — v2 promise()
- `s3.putObject({ Bucket, Key, Body }).promise()`
- `s3.upload({ Bucket, Key, Body }).promise()` → `new Upload(...)` in v3
- `s3.getSignedUrl('getObject', params)` → `getSignedUrl(client, command)` in v3
- `s3.getSignedUrlPromise('getObject', params)` → presigner package in v3

## v2 → v3 key breaking changes
- Package rename: `aws-sdk` → `@aws-sdk/client-s3` (separate packages per service)
- Client instantiation: `new AWS.S3()` → `new S3Client()`
- Method calling: `s3.getObject(params).promise()` → `client.send(new GetObjectCommand(params))`
- Upload: `s3.upload(params)` → `new Upload({ client, params })`
- Presigned URLs: `s3.getSignedUrl()` → `getSignedUrl()` from `@aws-sdk/s3-request-presigner`
- Pagination: manual `.NextContinuationToken` → `paginateListObjectsV2()` helper
- Response streaming: different stream handling between v2 and v3

## Where to look first
1. `grep("aws-sdk\|@aws-sdk/client-s3", "package.json")` — package presence
2. `grep("new AWS.S3\|new S3Client", "")` — constructor
3. `grep("\.promise()", "")` — v2 usage pattern (`.promise()` is v2-only)
4. Common locations: `lib/s3.ts`, `utils/storage.ts`, `services/upload.ts`

## Anchors (fallback signals)
- Environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET`
- URL: `s3.amazonaws.com`, `s3.{region}.amazonaws.com`

## Common wrapper patterns
- `lib/s3.ts` exporting a singleton `S3Client` instance
- Upload utility wrapping `@aws-sdk/lib-storage`'s `Upload` class

## Feeds
- npm: `@aws-sdk/client-s3` package, dist-tag `latest`
- github releases: `aws/aws-sdk-js-v3`
- smithy spec: `https://raw.githubusercontent.com/aws/aws-sdk-js-v3/main/codegen/sdk-codegen/aws-models/s3.json`

## What "breaking" means for AWS SDK (S3)
- v2→v3 migration is the primary breaking change (different package, different API shape)
- Input/output type changes in command parameters
- Credential provider API changes
- Middleware stack API changes (v3-specific)
- Node.js minimum version bumps
