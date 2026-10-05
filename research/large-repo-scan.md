# T-14: Large-Repo Stress Test — Rocket.Chat (mongodb) + superset (sentry)

**Date:** 2026-10-05  
**Tester:** Round 2

---

## Results Table

| Repo | Provider | Files Scanned | Call Sites | Actionable | Breaking Changes | Drift | Cost | Scan Time |
|------|----------|--------------|------------|------------|-----------------|-------|------|-----------|
| bedilk/Rocket.Chat | mongodb | 9,648 | 39 | 39 | 0 | 6.10.0 → 7.7.0 (major-gap) | $0.0000 | ~37s |
| bedilk/superset | sentry | 5,742 | 223 | 0 | 0 | — | $0.3102 | ~3m47s |

---

## Per-Repo Details

### 1. bedilk/Rocket.Chat (mongodb)

- **Files scanned:** 9,648
- **Call sites:** 39 actionable (deterministic scan, no LLM calls)
- **Drift:** mongodb `6.10.0 → 7.7.0` — classified as `major-gap review` (spans a major version boundary)
- **Breaking changes:** 0 from feed; all 39 sites show `no_call_sites` for specific old APIs
- **Plan artifact:** No (major-gap review = human review required before auto-fix)
- **Cost:** $0.0000 — fully deterministic scan, no LLM needed
- **Scan time:** ~37 seconds total (clone + scan + plan)
- **Memory:** No OOM or timeout issues observed
- **Status:** PASS

**Observations:**
- depfix handles a 9,648-file TypeScript monorepo without issues
- 39 mongodb call sites correctly found across the repo
- The major-gap (6.x → 7.x) triggers human-review mode rather than auto-PR — correct safety behavior
- No performance degradation compared to small repos (37s is fast for 9k files)

---

### 2. bedilk/superset (sentry)

- **Files scanned:** 5,742
- **Call sites found:** 223 raw (all low confidence → 0 actionable)
- **Breaking changes:** 0
- **Drift:** Not detected (no `@sentry/node` in any manifest depfix can read)
- **Plan artifact:** No
- **Cost:** $0.3102 (Bedrock Haiku to classify 223 Python sentry sites)
- **Scan time:** ~3m47s total
- **Memory:** No OOM observed
- **Status:** PARTIAL — scan completed without crash; 0 actionable is expected given known gap

**Root cause of 0 actionable:**

The augmentation log shows:
```
hybrid augment bedilk/superset/sentry: 0 actionable before → 0 after (low sites 243 → 223)
```

Superset uses Python `sentry_sdk` (e.g., `sentry_sdk.init()`, `sentry_sdk.capture_exception()`). The depfix sentry scanner searches for JavaScript `@sentry/node` patterns. Python sentry_sdk is a different import namespace and isn't matched.

This is the same gap identified in T-2: **Python `sentry_sdk` is not detected because the scanner looks for `sentry.*` patterns, not `sentry_sdk.*`.**

All 223 detected "call sites" are false positives from Python threading/SQLAlchemy references (`sentry` substring matches). The LLM classifier correctly filters them all to low confidence at a cost of $0.31.

**Key implication:** For repos that use Python's `sentry_sdk`, depfix produces 0 actionable results and wastes ~$0.31 in LLM classification. Two fixes needed:
1. Add `sentry_sdk` as a Python import pattern in the sentry provider scanner
2. Pre-filter false positives earlier (before LLM) to avoid spending $0.31 on classifying 223 junk sites

---

## Performance Summary

| Metric | Rocket.Chat (9,648 files) | superset (5,742 files) |
|--------|--------------------------|------------------------|
| Scan time | ~37s | ~3m47s |
| Cost | $0.0000 | $0.3102 |
| OOM/timeout | None | None |
| Exit | Success | Success (0 actionable expected) |

**Performance is acceptable for both repos.** Rocket.Chat at 9,648 files in 37s is impressive. superset at 5,742 files in 3m47s is slower due to the $0.31 LLM classification pass over 223 false-positive sites — if pre-filtering were improved, this would drop significantly.

---

## Assessment

Large-repo scanning is production-ready for mongodb repos (Rocket.Chat). For Python sentry_sdk repos (superset), the scanner runs without crashing but produces no value today and wastes ~$0.31/run. The fix is to add Python `sentry_sdk.*` patterns to the sentry provider config and improve pre-LLM filtering of false positives.
