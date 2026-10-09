# Octokit REST SDK scan skill

## SDK packages
- npm: `@octokit/rest` (REST client — primary)
- npm: `@octokit/core` (base Octokit)
- npm: `octokit` (all-in-one: REST + GraphQL + webhooks)
- npm: `@octokit/graphql` (GraphQL client)
- npm: `@octokit/webhooks` (webhook handling)

## Import patterns

### JavaScript / TypeScript
```javascript
import { Octokit } from '@octokit/rest';
import { Octokit } from 'octokit';            // all-in-one
import { Octokit } from '@octokit/core';       // base class
const { Octokit } = require('@octokit/rest');
```

Client construction:
```javascript
const octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });
const octokit = new Octokit({ auth: `token ${token}` });
```

## Call sites to look for

### Current canonical (v19+)
- `octokit.rest.issues.create({owner, repo, title})` — create issue
- `octokit.rest.pulls.list({owner, repo})` — list PRs
- `octokit.rest.repos.get({owner, repo})` — get repo
- `octokit.rest.users.getAuthenticated()` — authenticated user
- `octokit.paginate(octokit.rest.issues.list, {owner, repo})` — pagination

### Legacy patterns (pre-v17, flag these)
- `octokit.issues.create({...})` — flat method namespace (pre-v17)
- `octokit.pulls.list({...})` — flat namespace
- `octokit.repos.get({...})` — flat namespace
- `octokit.authenticate({ type: 'token', token })` — removed in v16

## v16 → v17 key breaking changes
- All method namespaces moved under `.rest.`: `octokit.issues.*` → `octokit.rest.issues.*`
- `octokit.authenticate()` removed → pass `auth` in constructor instead
- Plugin system restructured

## v17 → v18+ changes
- Constructor: `auth` option unified (no more `token` type prefix)
- `octokit.paginate()` requires explicit endpoint function reference

## Where to look first
1. `grep("@octokit/rest\|@octokit/core", "package.json")` — package presence
2. `grep("new Octokit", "")` — constructor
3. `grep("octokit\.", "")` — method calls
4. Common locations: `lib/github.ts`, `utils/octokit.ts`, `src/github.ts`
5. GitHub Actions bots: `src/bot.ts`, `probot` apps

## Anchors (fallback signals)
- Environment variables: `GITHUB_TOKEN`, `GH_TOKEN`, `GITHUB_APP_PRIVATE_KEY`
- URL: `api.github.com`
- Header: `Authorization: token ...` or `Authorization: Bearer ...` combined with github URL

## Common wrapper patterns
- GitHub Apps often use `probot` which wraps Octokit — check `probot` package too
- `lib/octokit.ts` singleton client
- Probot context: `context.octokit.rest.issues.createComment(...)`

## Feeds
- npm: `@octokit/rest` package, dist-tag `latest`
- github releases: `octokit/rest.js`
- openapi: `https://raw.githubusercontent.com/github/rest-api-description/main/descriptions/api.github.com/api.github.com.json`

## What "breaking" means for Octokit
- Namespace changes (the `.rest.` migration in v17 was the largest)
- Authentication API changes
- Pagination API changes
- GitHub API endpoint deprecations reflected in SDK
- Plugin API shape changes
