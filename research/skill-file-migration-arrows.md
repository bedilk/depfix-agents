# Skill File Migration Arrows — Complete Coverage

**Date:** 2026-10-12
**Task:** Proactive — ensure `_enrich_removal_from_skill` (T-19) works for all providers
**Status:** Complete — all 43 providers now have `→` migration arrows

## Context

T-19 introduces `_enrich_removal_from_skill()` in `runner.py` which reads provider skill files
to find replacement info for METHOD_REMOVED changes. It searches for `symbol → replacement`
patterns using regex: `` `?{symbol}\b[^`]*`?\s*→\s*`?([^`\n]+)`? ``

Without migration arrows, METHOD_REMOVED changes remain REPORT_ONLY and produce no fix PRs.

## Before This Work

- 29/43 providers had migration arrows
- **10 providers had ZERO arrows** (completely dark to T-19 enrichment):
  clerk, datadog, google_cloud, mixpanel, mongodb, postgresql, prisma, rabbitmq, sendgrid, stripe

## Critical Gap: mongodb

**T-21 tests Rocket.Chat with mongodb** — without migration arrows, all mongodb METHOD_REMOVED
changes would remain REPORT_ONLY and T-21 would produce 0 fix PRs for mongodb call sites.

## Changes Made

### 1. mongodb (17 arrows)
- v4→v5: `insert/update/remove` → `insertOne/updateOne/deleteOne` (callback removal)
- v4→v5: `count/findAndModify/ensureIndex/mapReduce` → modern equivalents
- v5→v6: `addUser/stats/ssl` options → removed or renamed

### 2. stripe (8 arrows)
- v8→v9: `Stripe(key)` → `new Stripe(key)` (class constructor)
- API deprecations: `charges.create` → `paymentIntents.create`, `subscriptions.del` → `cancel`
- v15: `StripeResource` removed, auto-pagination default, API version bumps

### 3. prisma (12 arrows)
- v4→v5: `$queryRaw` return type change, `$runCommandRaw` signature change
- v5→v6: `NotFoundError` → `PrismaClientKnownRequestError(P2025)`, `Buffer` → `Uint8Array`
- v6→v7: `schema.prisma` → `prisma.config.ts`, `$queryRaw` → `$querySql`

### 4. clerk (13 arrows)
- v4→v5 (Core 2): `authMiddleware()` → `clerkMiddleware()`, redirect helpers moved
- v5→v6: `auth()` → `await auth()` (async), `clerkClient()` → `await clerkClient()`

### 5. sendgrid (7 arrows)
- v6→v7: `send()` return type changed (`[ClientResponse, {}]` → `void`)
- v7→v8: Node.js minimum bumped, axios upgrade

### 6. google_cloud (10 arrows)
- v6→v7 (Storage): `delete()` return type, metadata typing, SSL option renames
- Python v2→v3: constructor param changes

### 7. postgresql (13 arrows)
- pg v8→v9: callback removal, `pg.native` → separate import, concurrent query behavior
- psycopg2→psycopg3: import rename, parameterization changes, `DictCursor` → `dict_row`

### 8. rabbitmq (9 arrows)
- amqplib v0.10→v2.0: heartbeat behavior, Node.js minimum
- pika v0.x→v1.x: argument order swap (`basic_consume`), SSL options, `add_timeout` rename

### 9. datadog (9 arrows)
- v1.57-v1.64: field removals/renames (`pat_uuid` → `pat_id`, enum casing)
- v2 upcoming: monolithic package → per-product split

### 10. mixpanel (6 arrows)
- Node.js: `Client` constructor → `Mixpanel.init()`
- Browser: `track_charge` removed, `record_inline_images` removed
- Python: version minimum bumped

## Verification

Arrow count per provider (post-update, sorted ascending):
```
1: anthropic, cloudflare, kafka, mysql, openai, resend, vercel_ai
2: hubspot, newrelic, posthog, shopify
3: redis
4: algolia, octokit
5: elasticsearch, slack
6: astro, mixpanel
7: plaid, segment, sendgrid
8: launchdarkly, sentry, stripe
9: bugsnag, datadog, firebase, langchain, rabbitmq
10: amplitude, google_cloud
11: aws_s3
12: prisma
13: clerk, postgresql, supabase
14: twilio
15: auth0
16: discord
17: mongodb
```

**Zero providers at 0 arrows.** All 43 providers can now benefit from T-19 enrichment.

## Sources
- [MongoDB Node.js Driver Upgrade Guide](https://www.mongodb.com/docs/drivers/node/current/reference/upgrade/)
- [MongoDB Driver v5 Changes](https://github.com/mongodb/node-mongodb-native/blob/main/etc/notes/CHANGES_5.0.0.md)
- [MongoDB Driver v6 Release](https://github.com/mongodb/node-mongodb-native/releases/tag/v6.0.0)
- [Stripe Node.js Migration Guides](https://github.com/stripe/stripe-node/wiki)
- [Prisma v6 Upgrade Guide](https://www.prisma.io/docs/orm/more/upgrade-guides/upgrading-versions/upgrading-to-prisma-6)
- [Prisma v7 Upgrade Guide](https://www.prisma.io/docs/guides/upgrade-prisma-orm/v7)
- [Clerk v6 Upgrade Guide](https://clerk.com/docs/guides/development/upgrading/upgrade-guides/nextjs-v6)
- [Clerk Core 2 Migration](https://clerk.com/docs/upgrade-guides/core-2/nextjs)
- [SendGrid Node.js Changelog](https://github.com/sendgrid/sendgrid-nodejs/blob/main/CHANGELOG.md)
- [pg v9 Breaking Changes Discussion](https://github.com/brianc/node-postgres/discussions/3598)
- [psycopg2 to psycopg3 Migration](https://www.psycopg.org/psycopg3/docs/basic/from_pg2.html)
- [Google Cloud Storage v7 Release](https://github.com/googleapis/nodejs-storage/releases/tag/v7.0.0)
- [amqplib v2 Release](https://github.com/amqp-node/amqplib/releases)
- [pika Releases](https://github.com/pika/pika/releases)
