# Test Results — Live LLM Runs

*2026-09-18. Machine: macOS, Node v26, Python 3.12. Model under test:
`gemini-3-flash-preview` (fallback configured: `gemini-2.5-pro`). All
numbers below are from real runs on this machine — nothing simulated.*

## 1. Eval corpus (`depfix eval`, full LLM-backed)

| Category | Cases | gemini-3-flash-preview | gemini-2.5-flash (head-to-head) |
|---|---|---|---|
| spec_diff (deterministic, no LLM) | 7 | **7/7** | 7/7 |
| release_notes (LLM classifier) | 2 | 0/2 | 0/2 |
| fix_generation (LLM) | 6 | **6/6** | 6/6 |
| call_sites (scanner) | 5 | **5/5** | 5/5 |
| **Total** | 20 | **90%** | 90% |
| Cost per full eval | | $0.0114 | $0.0026 |

**Model decision: keep `gemini-3-flash-preview`.** The two failures are
identical on both models — so they are a corpus/classifier issue, not a
Gemini 3 regression (the failing cases are `notes-method-renamed` and
`notes-param-removed`; both models produce classifications that don't
match the expected `kind`/`old_api`, most likely the verbatim-quote
anti-hallucination gate or over-strict expectations — **follow-up item**,
see §4). Caveats on the preview model: one API call during the eval took
3m14s (latency spikes exist), and `-preview` models can be retired without
notice — which is exactly why the fallback is pinned to stable
`gemini-2.5-pro` (`gemini-3-pro-preview` already returns 404).

## 2. End-to-end: real Gemini fix, real test-suite verification (JS)

Fixture: `tests/fixtures/openai_v3_verifiable` (real `npm install` +
`node:test` suite). Change: openai v3→v4 `createModeration` →
`moderations.create` incl. response-shape change. Fixer: **live Gemini**,
production configuration (retry loop enabled).

| Run | Outcome |
|---|---|
| Run A (no retry loop) | Gemini's first fix missed the response-shape change → suite failed → **edit correctly REVERTED**, failure attributed to the exact file. The safety net caught a bad LLM fix. |
| Run B (production config, retry loop) | Fix generated, syntax-validated, suite verified clean → **KEPT**, confidence **HIGH** ("the repository's own test suite introduced no new failures"), migration confirmed on disk. **$0.0016, 77s wall-clock.** |

Both terminal behaviors of the trust model demonstrated in live runs: a
wrong fix cannot survive verification, and a right fix lands with
test-suite-backed confidence.

## 3. Python pipeline (new this session) — end-to-end, real subprocesses

Fixture: `tests/fixtures/python_v1_verifiable` (throwaway `.depfix-venv`,
real `pip install`, real pytest with JUnit identities). Now a permanent
integration test (`tests/integration/test_fix_pipeline_python.py`):

- Correct migration → **KEPT**, 0 new failures, edit on disk ✓
- Broken migration → **REVERTED**, ≥1 new failure attributed, original restored ✓
- Wall-clock: **11.7s** for both tests including venv + pip + 4 pytest runs

Suites: **658 unit tests green; JS + Python integration suites green.**
During this work the integration suite also surfaced (and we fixed) a
pre-existing Node 26 crash: a repo test script already pinning
`--test-reporter` got the flag appended twice, which Node 26 rejects —
every such repo verified as SUSPECT instead of KEPT before the fix.

## 4. Known issues / next measurements

1. **release_notes classifier: 0/2 on both models** — diagnose whether the
   anti-hallucination evidence gate drops the proposals or the corpus
   expectations are over-strict. Until fixed, prose-only changes lean on
   the deterministic spec-diff path (which is 7/7).
2. **Preview-model latency spikes** (one 3-minute call observed). Retry/
   timeout budget already covers it; worth watching in fleet runs.
3. **Day-3 real-repo runs still pending** — needs the GitHub App
   (`GITHUB_APP_ID` + key, Bedil) or forks under a personal account; the
   candidates are already shortlisted in `docs/research/npm-fork-candidates.md`.
   That run produces the number that matters commercially: the KEPT rate
   on code we didn't write.
4. **Secret redaction still open** — file contents go to Gemini unscrubbed.
   Must land before running the pipeline on any repo we don't own.
