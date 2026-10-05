# E2E Repo Test Results (T-12)

**Run date:** 2026-10-05  
**Command:** `bash scripts/test_pipeline.sh sentry:bedilk/depfix-test-sentry-v6-app openai:bedilk/depfix-test-openai-v3-chat anthropic:bedilk/depfix-test-anthropic-callsites`  
**Method:** scan + plan (no apply, no real PR)

## Summary Table

| Repo | Provider | Files | Call Sites | Actionable | Drift From | Drift To | Drift Risk | Artifact | Cost |
|------|----------|-------|------------|------------|------------|----------|------------|---------|------|
| bedilk/depfix-test-sentry-v6-app | sentry | 8 | 31 | 31 | 10.75.3 | 11.4.0 | major-gap review | **Yes** | $0.0506 |
| bedilk/depfix-test-openai-v3-chat | openai | 4 | 8 | 8 | 6.49.0 | 7.28.0 | major-gap review | No | $0.0000 |
| bedilk/depfix-test-anthropic-callsites | anthropic | 3 | 2 | 2 | 0.6.2 | 0.131.0 | actionable | No | $0.0000 |

---

## Repo 1: bedilk/depfix-test-sentry-v6-app (sentry)

### Scan Results
- **Files scanned:** 8
- **Call sites:** 31 (all 31 actionable, high confidence, deterministic — no LLM needed)
- **Drift:** `@sentry/node@10.75.3` → `11.4.0` (major-gap review)
- **API match:** `startTransaction → startSpan` — 13 actionable matches

**Detected call sites (sample):**
| File | Line | Kind | Symbol |
|------|------|------|--------|
| src/performance.js | 5 | method_call | sentry.startTransaction |
| src/performance.js | 9 | method_call | sentry.startTransaction.setStatus |
| src/performance.js | 13 | method_call | sentry.startTransaction.finish |
| src/tracing.js | 7 | method_call | sentry.startTransaction |
| src/tracing.js | 8 | method_call | sentry.getCurrentHub |
| ... | ... | ... | (31 total) |

### Plan Results
- **PRs proposed:** 2 plans (same change proposed twice — duplicate)
  - `depfix: upgrade @sentry/node 10.75.3 → 11.4.0 (1 API migration): 3 file(s) across 2 step(s)`
  - LLM fixes generated for `src/performance.js` ($0.0069) and `src/tracing.js` ($0.0058) using claude-sonnet-4-6
- **REPORT_ONLY findings (8 removed APIs, no replacement):**
  - `sentry.validateOpenTelemetrySetup` (src/instrumentation.js:17)
  - `sentry.setNodeAsyncContextStrategy` (src/instrumentation.js:15)
  - `sentry.setupConnectErrorHandler` (src/connect-adapter.js:15)
  - `sentry.preloadOpenTelemetry` (src/instrumentation.js:14)
  - `sentry.inboundFiltersIntegration` (src/sentry.js:11)
  - `sentry.generateInstrumentOnce` (src/instrumentation.js:6)
  - `sentry.connectIntegration` (src/sentry.js:12)
  - `sentry.SentryContextManager` (src/context.js:4)

### Assessment: **PASS**
The sentry e2e repo is purpose-built for this test and works correctly. The pipeline:
1. Found 31 call sites correctly
2. Identified `startTransaction → startSpan` migration (13 matches)
3. Generated LLM fixes for affected files
4. Correctly flagged REPORT_ONLY APIs (removed, no replacement) without generating PRs for them

The 2 duplicate PRs may indicate a double-plan run — worth investigating whether `--force` in `test_pipeline.sh` triggers the plan twice.

---

## Repo 2: bedilk/depfix-test-openai-v3-chat (openai)

### Scan Results
- **Files scanned:** 4
- **Call sites:** 8 (all actionable, high confidence)
- **Drift:** `openai@6.49.0` → `7.28.0` (major-gap review)

**Detected call sites:**
| File | Line | Symbol |
|------|------|--------|
| src/chat.js | 11 | openai.chat.completions.create |
| src/chat.js | 27 | openai.chat.completions.create |
| src/chat.js | 41 | openai.beta.chat.completions.stream |
| src/chat.js | 51 | openai.beta.chat.completions.stream.finalChatCompletion |

**API matches:**
- `POST /images/generations (string)` change: `version_not_affected` — repo pins openai to 6.49.0 (major 6), change is in major 2 — correct behavior
- `openai@7.27.0 → 7.28.0`: actionable (minor drift)
- Multiple major drift detections: actionable

### Plan Results
- **PRs proposed:** 0
- **Reason:** Drift is `major-gap review` — requires human approval, no automatic fix generated
- **Cost:** $0.0000 (no LLM calls)

### Assessment: **PARTIAL**
Call-site detection is correct (8 sites, all the modern API usage). However no fix is generated because:
- The detected call sites use the **new** API (`openai.chat.completions.create`) not the old one (`openai.createChatCompletion`)
- The breaking change feed doesn't have a symbol match for the detected usage
- Drift is flagged correctly as major-gap requiring review

This repo may be testing the wrong scenario — it already uses the v4+ API style, not the v3 style that would trigger a migration.

---

## Repo 3: bedilk/depfix-test-anthropic-callsites (anthropic)

### Scan Results
- **Files scanned:** 3
- **Call sites:** 2 (all actionable)
- **Drift:** `@anthropic-ai/sdk@0.6.2` → `0.131.0` (actionable)
- No lockfile resolved version (no lockfile)

**API matches:**
- `anthropic.messages.create → anthropic.messages.stream`: `no_call_sites` — the detected call sites don't match this specific API transition

### Plan Results
- **PRs proposed:** 0
- No matching breaking changes for the detected call sites
- **Cost:** $0.0000

### Assessment: **PARTIAL**
The 2 call sites are found correctly. The drift from 0.6.2 → 0.131.0 is detected. However, the specific breaking change in the feed (`messages.create → messages.stream`) doesn't match because the repo's code likely uses `messages.create` in a way that doesn't match the old API pattern tracked.

---

## Overall Assessment

| Repo | Scan | Detection | Fix Generation | Overall |
|------|------|-----------|---------------|---------|
| depfix-test-sentry-v6-app | ✅ 31 call sites | ✅ startTransaction→startSpan matched | ✅ LLM fix generated | **PASS** |
| depfix-test-openai-v3-chat | ✅ 8 call sites | ⚠️ uses new API already | ❌ no fix (no old API) | **PARTIAL** |
| depfix-test-anthropic-callsites | ✅ 2 call sites | ⚠️ drift detected, no symbol match | ❌ no fix | **PARTIAL** |

**Key findings:**
1. The sentry pipeline is the most complete — scan, detect, fix, REPORT_ONLY all work correctly.
2. The openai and anthropic repos may need their test scenarios reviewed — they detect drift correctly but the specific call-site patterns don't trigger fix generation.
3. The end-to-end fix generation works when call sites match the tracked breaking API (sentry case proves this).
4. REPORT_ONLY handling is correct — 8 removed APIs flagged informational, no spurious PRs.
5. Duplicate PR proposals from the sentry plan (2 identical) warrant investigation.
