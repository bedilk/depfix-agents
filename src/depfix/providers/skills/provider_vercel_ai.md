# Vercel AI SDK scan skill

## SDK packages
- npm: `ai` (core SDK)
- npm: `@ai-sdk/openai` (OpenAI provider)
- npm: `@ai-sdk/anthropic` (Anthropic provider)
- npm: `@ai-sdk/google` (Google provider)

## Import patterns

### JavaScript / TypeScript
```javascript
import { streamText, generateText, streamUI } from 'ai';
import { openai } from '@ai-sdk/openai';
import { anthropic } from '@ai-sdk/anthropic';
```

Usage:
```javascript
const result = await streamText({ model: openai('gpt-4o'), prompt: '...' });
const { text } = await generateText({ model: anthropic('claude-3-5-sonnet-20241022'), prompt: '...' });
```

## Legacy patterns (pre-v3 / RSC era — flag these)
```javascript
import { OpenAIStream, StreamingTextResponse } from 'ai'; // v2 streaming helpers
import { useChat, useCompletion, useActions, useAIState, useUIState } from 'ai/react'; // v2 RSC hooks
import { createAI, createStreamableUI, createStreamableValue } from 'ai/rsc'; // v2 RSC
```

## Call sites to look for
- `streamText({model, prompt, messages})` — canonical streaming (v3+)
- `generateText({model, prompt})` — non-streaming (v3+)
- `generateObject({model, schema, prompt})` — structured output (v3+)
- `streamObject({model, schema, prompt})` — streaming structured (v3+)
- `embed({model, value})` — embeddings (v3+)

## Legacy v2 call sites (flag these)
- `OpenAIStream(response)` — removed in v3, use streamText instead
- `StreamingTextResponse(stream)` — removed in v3
- `useChat({ api })` — moved to `@ai-sdk/react` in v3 (check import path)
- `createStreamableUI()` — RSC API, not in v3 core
- `useAIState()`, `useUIState()` — v2 RSC hooks

## v2 → v3 key breaking changes
- `OpenAIStream` and `StreamingTextResponse` removed — replace with `streamText`
- Provider model strings moved to provider packages (`@ai-sdk/openai`, etc.)
- `useChat` moved to `@ai-sdk/react` (different import path)
- Middleware/telemetry API shape changed
- `createAI` RSC primitives deprecated

## Where to look first
1. `grep("from 'ai'", "")` — core SDK import
2. `grep("from '@ai-sdk/", "")` — provider import
3. Look in `app/api/chat/route.ts`, `pages/api/`, or `lib/ai.ts`
4. `grep("OpenAIStream\|StreamingTextResponse", "")` — detect legacy v2 patterns

## Anchors (fallback signals)
- Model strings: `'gpt-4o'`, `'claude-3-5-sonnet'` combined with `streamText`/`generateText`
- API route files with `export const maxDuration`

## Common wrapper patterns
- `lib/ai.ts` with a configured model instance
- API route handlers in `app/api/chat/route.ts` pattern

## Feeds
- npm: `ai` package, dist-tag `latest`
- npm: `@ai-sdk/openai` package, dist-tag `latest`
- github releases: `vercel/ai`
- changelog: `https://sdk.vercel.ai/changelog`

## What "breaking" means for Vercel AI SDK
- Removal of streaming helper utilities (`OpenAIStream`, `StreamingTextResponse`)
- Provider API consolidation (model strings moving to provider packages)
- RSC primitives changing or deprecating
- Hook import path changes
- Response shape changes in `streamText`/`generateText` return values
