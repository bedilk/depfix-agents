# Real-Repo Scan Results (T-11)

**Run date:** 2026-10-10  
**Method:** `git clone --depth=1` + `depfix scan --path` (no GitHub App required)  
**Note:** The original bedilk forks (bedilk/probot, bedilk/renovate, etc.) no longer exist on GitHub.
Equivalent repos from real-repos.txt were substituted, covering the same provider categories.

---

## Summary Table

| # | Repo | Provider | Files | Call Sites | Actionable | Drift | Decision | Plan PRs | Status |
|---|------|----------|-------|------------|------------|-------|----------|----------|--------|
| 1 | probot/probot | octokit | 99 | 0 | 0 | — | SDK excluded | 0 | NOTE |
| 2 | github/codeql-action | octokit | 190 | 0 | 0 | @octokit/core 7.0.8 | version unresolved | 0 | PARTIAL |
| 3 | Rapptz/RoboDanny | discord | 80 | 10 | 10 | 4 drift detections | no API match | 0 | PASS |
| 4 | nicehash/NiceHashQuickMiner | discord | 0 | 0 | 0 | — | C++ project, no source | 0 | N/A |
| 5 | n8n-io/n8n | slack | 15,069 | 34 | 0 | — | no API match | 0 | PASS |
| 6 | parse-community/parse-server | mongodb | 378 | 8 | 8 | mongodb 7.1.0→7.7.0 | same-major drift | 0 | PASS |
| 7 | RocketChat/Rocket.Chat | mongodb | 9,648 | 39 | 39 | mongodb 6.10.0→7.7.0 | major-gap | 0 | PASS |

---

## Per-Repo Details

### 1. probot/probot (octokit) — SDK excluded

- **Files scanned:** 99
- **Call sites:** 0 (0 actionable)
- **Why:** Depfix detects that the repo declares itself as `probot` (one of octokit's `sdk_packages`). It is a bot framework, not an octokit consumer. Scan skips its own tests and internal imports. Correct behavior — no false positives.
- **Drift:** `@octokit/core@7.0.6` in lockfile; feed version not observed (version unresolved).
- **Assessment:** Scanner correctly excludes SDK internals. Not a customer-codebase failure.

### 2. github/codeql-action (octokit) — version unresolved

- **Files scanned:** 190
- **Call sites:** 0 (0 actionable)
- **Drift:** `@octokit/core@7.0.8` in lockfile; feed version not observed → `version unresolved`.
- **Assessment:** The octokit feed doesn't observe the `@octokit/core` version that codeql-action declares. No actionable findings because no breaking changes were surfaced from the feed. The scanner scanned all 190 files without error.

### 3. Rapptz/RoboDanny (discord) — PASS

- **Files scanned:** 80
- **Call sites:** 10 (10 actionable, all high confidence)
- **Method:** Deterministic (no LLM needed, 10 unambiguous sites)
- **Drift:** 4 drift detections in `.depfix/learned_migrations.yaml` (discord.py Python bot)
- **Breaking changes matched:** 0 — all 25+ tracked discord API changes returned `no_call_sites`
- **Breaking changes list (sample):** `discord.WebhookType`, `discord.WelcomeScreen`, `discord.enum`, `discord.WebhookEdit*` — none used by RoboDanny
- **Cost:** $0.00
- **Assessment:** Scanner finds 10 real discord.py call sites in a Python bot. The specific APIs tracked in the discord feed don't overlap with RoboDanny's API surface. This is correct behavior — not a false negative.

### 4. nicehash/NiceHashQuickMiner (discord) — N/A (C++ project)

- **Files scanned:** 0
- **Why:** NiceHashQuickMiner is primarily a C++ Windows miner; contains no JavaScript/TypeScript/Python source that uses discord. The discord node is in the JS layer of another service. Scanner finds 0 scannable files.
- **Assessment:** Not a valid discord test target. Real discord users from real-repos.txt should be preferred (Rapptz/RoboDanny was the better choice).

### 5. n8n-io/n8n (slack) — PASS

- **Files scanned:** 15,069
- **Call sites:** 34 (0 actionable)
- **Method:** Deterministic (34 low-confidence/non-breaking sites found)
- **Breaking changes matched:** 0 — all tracked slack API removals returned `no_call_sites`
- **Breaking changes list (sample):** `slack.requestErrorWithCode`, `slack.warnIfNotUsingFix*`, `slack.WorkflowsStepComplete/Fail`, `slack.Ts`, `slack.UserTeam` — none used by n8n
- **Cost:** $0.00
- **Assessment:** Scanner successfully scanned 15,069 files in a large monorepo without crash. The 34 slack call sites are low-confidence (non-actionable); the specific removed APIs from the slack feed don't match n8n's usage pattern.

### 6. parse-community/parse-server (mongodb) — PASS

- **Files scanned:** 378
- **Call sites:** 8 (8 actionable, all high confidence)
- **Actual call sites found:**
  - `spec/MongoCollection.spec.js:52` — `mongodb.MongoClient` (bare_symbol)
  - `spec/MongoStorageAdapter.spec.js:676,692,707` — `mongodb.prototype.*` (method_call)
  - `spec/MongoTransform.spec.js:392,393` — `mongodb.Long.fromNumber`, `mongodb.Double`
  - `src/Adapters/Files/GridFSBucketAdapter.js:75` — `mongodb.GridFSBucket` (bare_symbol)
  - `src/Adapters/Storage/Mongo/MongoStorageAdapter.js:1334` — `mongodb.Binary`
- **Drift:** `mongodb@7.1.0` → `7.7.0` — **same-major drift** (minor upgrade path)
- **Python drift:** `pymongo@4.18.2` → `4.18.3` — **actionable** (patch drift)
- **Breaking changes matched:** 5 tracked, 0 matched call sites (`Transaction`, `configureExplicitResourceManagement`, `ServerCapabilities`, `CancellationToken`, `AsyncDisposable`)
- **Cost:** $0.00
- **Assessment:** Scanner correctly detects 8 real mongodb call sites in test and source files. mongodb same-major drift (7.1→7.7) flagged for review. pymongo patch drift actionable. No PR generated because the 5 tracked breaking APIs aren't used.

### 7. RocketChat/Rocket.Chat (mongodb) — PASS (from T-14, 2026-10-05)

- **Files scanned:** 9,648
- **Call sites:** 39 (39 actionable, high confidence)
- **Drift:** `mongodb@6.10.0` → `7.7.0` — **major-gap** risk
- **Breaking changes matched:** 5 tracked, 0 call sites matched (`Transaction`, `configureExplicitResourceManagement`, `ServerCapabilities`, `CancellationToken`, `AsyncDisposable`)
- **Plan PRs:** 0 (no matched call sites)
- **Scan time:** ~37s
- **Cost:** $0.00
- **Assessment:** Scanner scales to 9,648 files without OOM or timeout. Major-gap detection (v6→v7) triggers human-review mode correctly. 39 call sites found, but none match the specific tracked breaking APIs.

---

## Overall Assessment

### What Works
- **Call-site detection scales:** 9,648 files (Rocket.Chat), 15,069 files (n8n) scanned without crash or timeout.
- **Drift detection works:** mongodb 7.1→7.7 (same-major), mongodb 6.10→7.7 (major-gap), pymongo 4.18.2→4.18.3 all detected correctly.
- **No false positives:** SDK self-scans correctly excluded (probot).
- **Python ecosystem detection works:** RoboDanny (discord.py), parse-server (pymongo) both detected correctly.
- **Monorepo scanning works:** n8n (15,069 files) scanned cleanly.

### Gaps and Observations
- **octokit feed coverage:** `@octokit/core` doesn't surface breaking changes via the feed — codeql-action shows version unresolved. Feed may need octokit REST API changelog entries.
- **discord/slack API match gap:** 10 RoboDanny call sites and 34 n8n sites found, but none match the specific tracked removed APIs. This is a feed coverage gap: the tracked APIs are internal SDK symbols (WebhookType, WelcomeScreen, UserTeam), not the high-level client APIs these apps actually use.
- **Bedilk forks missing:** All 6 non-Rocket.Chat bedilk forks (probot, renovate, bolt-js, sentry, AtlantaBot, guide) no longer exist on GitHub. T-11 completed using equivalent real-repos.txt substitutes.
- **NiceHashQuickMiner not a valid discord test:** C++ project, not relevant. Use discord bots (RoboDanny, RobotDave, etc.) for discord testing.
