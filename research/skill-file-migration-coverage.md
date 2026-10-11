# Skill File Migration Coverage Audit (2026-10-12)

Audit of provider skill files in `dependency_check/src/depfix/providers/skills/`
to determine which have migration info (→ arrows) that Fix 3 (skill enrichment)
can use to enrich METHOD_REMOVED BreakingChanges.

## Summary

- **29/40** providers have ≥1 migration arrow — Fix 3 works immediately
- **10/40** providers have 0 migration arrows — need enrichment for Fix 3

## Providers with Migration Info (ready for Fix 3)

| Provider | → Count | Key Migrations |
|---|---|---|
| discord | 16 | MessageEmbed→EmbedBuilder, Intents.FLAGS→GatewayIntentBits |
| auth0 | 15 | AuthenticationClient removal, v4→v5 import change |
| twilio | 14 | IpMessagingGrant removal, SSML renames |
| supabase | 13 | signUp/signIn auth method renames |
| aws_s3 | 11 | AWS.S3→S3Client, command pattern |
| amplitude | 10 | logEvent→track, getInstance removal |
| langchain | 9 | ChatOpenAI→ChatOpenAI(model=...) |
| firebase | 9 | v8 compat→v9 modular API |
| bugsnag | 9 | bugsnag(opts)→Bugsnag.start(opts) |
| launchdarkly | 8 | alias() removal, Contexts migration |
| segment | 7 | analytics-node→@segment/analytics-node |
| plaid | 7 | linkDeliveryCreate removal, field renames |
| astro | 6 | config changes |
| slack | 5 | WebClient changes |
| elasticsearch | 5 | body param removed |
| octokit | 4 | method renames |
| algolia | 4 | initIndex→direct methods, import change |
| redis | 3 | createClient changes |
| shopify | 2 | customShopDomains→domainTransformations |
| posthog | 2 | method changes |
| newrelic | 2 | CAT API removals |
| hubspot | 2 | blogPostsApi→basicApi |
| vercel_ai | 1 | streaming changes |
| resend | 1 | API shape |
| openai | 1 | v3→v4 |
| mysql | 1 | connection changes |
| kafka | 1 | consumer changes |
| cloudflare | 1 | SDK changes |
| anthropic | 1 | import change |

## Providers Missing Migration Info (need enrichment)

| Provider | npm/mo | Priority | Notes |
|---|---|---|---|
| **sentry** | 10.5M | **HIGH** — T-18 test case | Eval corpus has migration data; copy to skill |
| stripe | 10.8M | LOW — uses dated API versions, not semver | Different migration pattern |
| mongodb | 3.8M | MEDIUM | v5→v6: MongoClient.connect change |
| prisma | 4.4M | MEDIUM | v4→v5: PrismaClient changes |
| sendgrid | 2.8M | LOW — part of twilio | Twilio skill has 14 arrows |
| datadog | 12.7M | MEDIUM | v1→v2 split into per-product packages |
| mixpanel | 5.4M | LOW | Client constructor changes |
| clerk | 3.2M | LOW | Auth helper changes |
| google_cloud | 1.8M | LOW | Individual service packages |
| postgresql | - | LOW — driver, not API SDK | Connection string changes |
| rabbitmq | - | LOW — driver, not API SDK | Channel API changes |

## Recommendation

1. **Immediate**: Add sentry v7→v8 migration table (T-18 test case prerequisite)
2. **Next**: mongodb, prisma, datadog — high download counts, real breaking changes
3. **Skip**: stripe (dated versions), postgresql/rabbitmq (drivers, not API SDKs)

## Source data

Migration table content for sentry is available in:
- `src/depfix/evals/corpus/sentry_v8_callsites.yaml` (5 migrations with examples)
- `research/sentry-eval-cases.md` (10 documented API changes)
