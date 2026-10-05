# Real-Repo Scan Results (T-11)

**Run date:** 2026-10-05  
**Command:** `bash test_all_repos.sh`  
**Method:** `depfix init → depfix scan --repo → depfix plan`

## Summary Table

| # | Repo | Provider | Files Scanned | Call Sites | Actionable | Drift | Plan PRs | Status |
|---|------|----------|--------------|------------|------------|-------|----------|--------|
| 1 | bedilk/probot | octokit | — | — | — | — | — | **BLOCKED** |
| 2 | bedilk/renovate | octokit | — | — | — | — | — | **BLOCKED** |
| 3 | bedilk/bolt-js | slack | — | — | — | — | — | **BLOCKED** |
| 4 | bedilk/sentry | slack | — | — | — | — | — | **BLOCKED** |
| 5 | bedilk/AtlantaBot | discord | — | — | — | — | — | **BLOCKED** |
| 6 | bedilk/guide | discord | — | — | — | — | — | **BLOCKED** |
| 7 | bedilk/Rocket.Chat | mongodb | 9,648 | 39 | 39 | 6.10.0→7.7.0 (major-gap) | 0 | **PASS** |

## Blocker: GitHub App Not Installed on 6/7 Repos

Repos 1–6 all fail at scan time with:
```
Error: no GitHub App installation found for bedilk/<repo>.
Install the App on this repository (or its owning org) first.
```

The depfix GitHub App is installed on `bedilk/Rocket.Chat` (and the seed repos), but **NOT** on:
- bedilk/probot
- bedilk/renovate  
- bedilk/bolt-js
- bedilk/sentry
- bedilk/AtlantaBot
- bedilk/guide

**Fix required:** Install the depfix GitHub App on these 6 repos (or on the `bedilk` org) before T-11 can be fully tested.

## Repo 7: bedilk/Rocket.Chat (mongodb) — DETAILED RESULTS

### Scan
- **Files scanned:** 9,648
- **Call sites found:** 39 (all 39 actionable, high confidence)
- **Scan method:** Deterministic (no LLM needed — 39 sites, unambiguous)
- **Drift detected:** `mongodb@6.10.0` → `7.7.0` — `major-gap` risk
- **Package manager:** yarn@4.18.0 (installed in Depfix cache)
- **Commit scanned:** (commit SHA truncated in output)

### Upstream Change Matches
All 5 breaking changes from the mongodb feed had `no_call_sites` (none of the specific breaking APIs were referenced by the detected call sites):
- `mongodb.Transaction` — no_call_sites
- `mongodb.configureExplicitResourceManagement` — no_call_sites
- `mongodb.ServerCapabilities` — no_call_sites
- `mongodb.CancellationToken` — no_call_sites
- `mongodb.AsyncDisposable` — no_call_sites

### Plan
- **Breaking changes processed:** 5
- **PRs generated:** 0 (no call sites matched breaking changes)
- **LLM calls:** 0
- **Cost:** $0.0000

### Interpretation
Rocket.Chat uses mongodb 6.10.0 but the breaking changes in mongodb's feed are for APIs (Transaction, CancellationToken, etc.) that Rocket.Chat doesn't call directly. The scanner correctly finds 39 mongodb call sites but none match the specific breaking APIs tracked. The `major-gap` drift (v6→v7) is flagged correctly.

## Assessment

### What Works
- **Scanner finds call sites in large repos** — 39 call sites detected in 9,648 files without LLM (pure deterministic). This proves the scanner scales.
- **Drift detection works** — correctly flags mongodb 6.10.0→7.7.0 as major-gap.
- **GitHub App auth works** — for installed repos.
- **Plan runs correctly** — 0 PRs is correct when no breaking changes match call sites.

### What Needs Fixing
- **GitHub App installation missing on 6/7 forked repos** — this is the only blocker for full T-11 completion.
- Action needed: install depfix GitHub App on bedilk/probot, bedilk/renovate, bedilk/bolt-js, bedilk/sentry, bedilk/AtlantaBot, bedilk/guide (or install org-wide on bedilk).

### Call Site Count Expectation
For the one working repo (Rocket.Chat with mongodb), 39 call sites in a 9,648-file TypeScript monorepo is a reasonable result. The scanner is working correctly at scale.
