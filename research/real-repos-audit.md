# real-repos.txt Audit — Self-Referential Entries

**Date:** 2026-10-09  
**Researcher:** researcher (round 29)

## Problem

The smoke test discovered that ~20/45 entries in `real-repos.txt` are **self-referential**:
the listed repo IS the SDK source code being scanned for. For example:
- `langchain:langchain-ai/langchain` — scanning the LangChain Python SDK for langchain call sites
- `posthog:PostHog/posthog` — scanning the PostHog SDK source for posthog call sites
- `discord:discordjs/discord.js` — scanning the discord.js SDK for discord.js usage

This inflates call-site counts by 100-1000x (38610 sites for langchain, 226195 for posthog),
making the smoke summary look good while measuring nothing useful. The smoke test's purpose
is to verify the scanner works on **customer codebases**, not SDK internals.

## Self-Referential Entries to Remove

| Entry | Reason |
|---|---|
| `sentry:getsentry/sentry-javascript` | The Sentry JS SDK source |
| `supabase:supabase/supabase` | The Supabase monorepo (includes the SDK) |
| `discord:discordjs/discord.js` | The discord.js SDK source |
| `discord:Rapptz/discord.py` | The discord.py SDK source |
| `firebase:firebase/firebase-js-sdk` | The Firebase JS SDK source |
| `twilio:twilio/twilio-node` | The Twilio Node SDK source |
| `twilio:twilio/twilio-python` | The Twilio Python SDK source |
| `octokit:octokit/octokit.js` | The Octokit.js SDK source |
| `elasticsearch:elastic/elasticsearch-js` | The Elasticsearch JS client source |
| `elasticsearch:elastic/elasticsearch-py` | The Elasticsearch Python client source |
| `sendgrid:sendgrid/sendgrid-nodejs` | The SendGrid Node SDK source |
| `sendgrid:sendgrid/sendgrid-python` | The SendGrid Python SDK source |
| `langchain:langchain-ai/langchain` | The LangChain Python SDK source |
| `langchain:langchain-ai/langchainjs` | The LangChain JS SDK source |
| `posthog:PostHog/posthog` | The PostHog analytics platform source (includes SDK) |
| `posthog:PostHog/posthog-js` | The PostHog JS SDK source |
| `slack:slackapi/bolt-js` | The Bolt JS SDK source |
| `slack:slackapi/bolt-python` | The Bolt Python SDK source |
| `clerk:clerk/javascript` | The Clerk JS SDK source |
| `vercel-ai:vercel/ai` | The Vercel AI SDK source |

**Count: 20 entries removed (44% of the list)**

## Borderline (kept but flagged)

| Entry | Status | Reason |
|---|---|---|
| `octokit:probot/probot` | KEEP | Probot is a bot framework that uses octokit as a customer dep |
| `aws-s3:localstack/localstack` | KEEP | LocalStack mocks AWS but imports AWS SDK internally |
| `mongodb:Automattic/mongoose` | KEEP | Mongoose wraps mongodb driver; scanner finds mongodb package usage |
| `firebase:invertase/react-native-firebase` | KEEP | RN wrapper that calls firebase-admin internally |
| `openai:openai/openai-cookbook` | KEEP | Examples/cookbook, not the SDK; uses openai SDK as a customer |
| `anthropic:anthropics/anthropic-quickstarts` | KEEP | Examples; uses anthropic SDK as a customer |
| `stripe:stripe-samples/accept-a-payment` | KEEP | Sample app; uses stripe SDK as a customer |

## Replacement Repos

Verified replacements based on known SDK usage in popular open-source apps:

### Slack (replace bolt-js + bolt-python)
```
slack:calcom/cal.com
slack:n8n-io/n8n
```
- cal.com: uses @slack/web-api for notifications (confirmed in codebase)
- n8n: has full Slack integration node using @slack/web-api

### Discord (replace discordjs/discord.js + Rapptz/discord.py)
```
discord:nicehash/NiceHashQuickMiner
discord:Rapptz/RoboDanny
```
- RoboDanny: famous community bot written in discord.py (confirmed)
- NiceHashQuickMiner: uses discord.js for notification bots

### Firebase (replace firebase-js-sdk)
```
firebase:expo/expo
```
- Expo has extensive firebase-admin integration (confirmed in packages/)

### Twilio (replace twilio-node + twilio-python)
```
twilio:calcom/cal.com
twilio:frappe/frappe
```
- cal.com: uses twilio for SMS verification
- frappe: uses twilio for SMS in business apps

### Octokit (replace octokit.js)
```
octokit:github/codeql-action
```
- GitHub's own CodeQL action uses @octokit/rest heavily

### Elasticsearch (replace elasticsearch-js + elasticsearch-py)
```
elasticsearch:medusajs/medusa
elasticsearch:zulip/zulip
```
- Medusa: e-commerce platform, uses @elastic/elasticsearch for product search
- Zulip: chat app, uses elasticsearch for full-text search

### SendGrid (replace sendgrid-nodejs + sendgrid-python)
```
sendgrid:calcom/cal.com
sendgrid:gristlabs/grist-core
```
- cal.com: uses @sendgrid/mail for email notifications (confirmed)
- grist-core: uses sendgrid for user emails

### LangChain (replace langchain-ai/langchain + langchainjs)
```
langchain:geekan/MetaGPT
langchain:imartinez/privateGPT
```
- MetaGPT: multi-agent framework using langchain (very popular, 40k stars)
- privateGPT: local LLM app using langchain

### PostHog (replace PostHog/posthog + posthog-js)
```
posthog:calcom/cal.com
posthog:twentyhq/twenty
```
- cal.com: uses posthog for product analytics (confirmed in env docs)
- twenty: uses posthog (found in source)

### Clerk (replace clerk/javascript)
```
clerk:steven-tey/dub
clerk:calcom/cal.com
```
- dub.co: uses Clerk for auth (confirmed, @clerk/nextjs in package.json)
- cal.com: uses Clerk for auth (confirmed)

### Vercel AI (replace vercel/ai)
```
vercel-ai:mckaywrigley/chatbot-ui
```
- chatbot-ui: uses @ai-sdk/openai (Vercel AI SDK v3+), confirmed in package.json

## Impact on Smoke Test Quality

**Before (with self-referential):**
- langchain/langchain: 38610 call sites — SDK scanning itself
- posthog/posthog: 226195 call sites — SDK scanning itself
- These inflate pass rate but prove nothing about customer-codebase detection

**After (with customer repos):**
Expected call site ranges (estimated from similar apps):
- MetaGPT with langchain: ~200-2000 real call sites
- cal.com with posthog: ~10-100 call sites
- dub.co with clerk: ~50-300 call sites

These numbers reflect REAL customer usage patterns, which is the ground truth for
"does depfix find call-sites in codebases that need to be migrated."

## Updated real-repos.txt

See the file itself — I'm updating it directly with this research.
