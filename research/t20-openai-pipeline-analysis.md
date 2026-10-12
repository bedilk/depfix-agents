# T-20 OpenAI Pipeline Analysis

## Date: 2026-10-12 (researcher proactive)

## Summary

Traced the full depfix pipeline for the two openai test repos in T-20. Found that
the earlier T-20 prep document had INCORRECT assumptions about these repos. Key
corrections and findings documented below.

## Repo 1: bedilk/depfix-test-openai-v3-chat

### Actual State (NOT v3)
Despite its name, this repo is on **openai@6.49.0** — a v4+ API style codebase.
- `package.json`: `"openai": "6.49.0"`
- **No lockfile** (no package-lock.json, no yarn.lock, no pnpm-lock.yaml)
- 4 source files: `index.js`, `chat.js`, `embeddings.js`, `moderations.js`

### Call Sites (all v4+ style)
| File | Call Site | API Style |
|------|-----------|-----------|
| chat.js | `openai.chat.completions.create(...)` | v4+ (current) |
| chat.js | `openai.beta.chat.completions.stream(...)` | v6 beta (reworked in v7) |
| embeddings.js | `openai.embeddings.create(...)` | v4+ (current) |
| moderations.js | `openai.moderations.create(...)` | v4+ (current) |

### ts_exports Analysis: v6.49.0 → v7.32.0
Ran `TsExportsSource._exports_for()` against both versions:
- **v6 exports: 1496**
- **v7 exports: 2064**
- **Removed in v7: 0** (ZERO)
- **Added in v7: 568** (mainly Agent* types for the new Agents API)

**v7 is a pure superset of v6** at the TypeScript export level. No removals.

### Consequence for T-20
1. **repo_exports.py sub-case A**: EMPTY — no exports removed between v6 and v7
2. **repo_exports.py sub-case B**: EMPTY — all v6 call-site symbols still exist in v7
3. **Version drift**: DETECTABLE — v6.49.0 → 7.32.0 is a major version gap
4. **No lockfile**: `resolved_version` will be `None` (source="range") since no
   lockfile exists. The `declared_range` is "6.49.0" (exact pin). This MAY prevent
   drift detection if the drift path requires `resolved_version` (needs verification).
5. **METHOD_REMOVED for beta.stream()**: NOT DETECTABLE — the streaming API change
   is a method behavior change on a class instance, not a removed TypeScript export.
   ts_exports only tracks top-level `export` declarations from `.d.ts` files.

### Expected T-20 Outcome
- **Best case**: Version drift PR with `package.json` bump 6.49.0 → 7.32.0
- **Worst case**: No PR at all (if no lockfile → no resolved_version → no drift detection)
- **No API migration PR** — all call sites use current v4+ API, and there are zero
  removed exports between v6 and v7

### Openai Skill File Gap
Current `provider_openai.md` has only ONE parseable migration arrow:
```
`createChatCompletion` → `chat.completions.create`
```
This is for v3→v4, NOT v6→v7. Missing arrows for:
- `openai.beta.chat.completions.stream()` → `openai.chat.completions.stream()`
  (promoted from beta in v7)
- Any other v7 breaking behavioral changes

Even if added, these method-level arrows can't fire without a corresponding
METHOD_REMOVED BreakingChange, which ts_exports won't generate because the
exports themselves are unchanged.

## Repo 2: bedilk/seed-openai-v3-to-v4

### Actual State
- `package.json`: `"openai": "file:./vendor/openai"` (vendored dependency)
- Uses v3 API: `sdk.createChatCompletion({ seed: true })`
- Already tested by tester (T-12): "version unresolved (vendored dep)"

### Expected T-20 Outcome
- Call site `createChatCompletion` detected by scanner
- **No PR** — vendored dependency, version unresolved
- Same as prior test result

## Architectural Insight: Limits of ts_exports

The openai v6→v7 migration reveals a structural limit of the ts_exports approach:

### What ts_exports CAN detect (works well)
- Removed top-level classes/functions/types (e.g., sentry `startTransaction`)
- Removed named exports (e.g., `Configuration`, `OpenAIApi` in openai v3→v4)
- Renamed packages (different package, different exports)

### What ts_exports CANNOT detect
| Change Type | Example | Why Undetectable |
|-------------|---------|------------------|
| Method-level changes | `beta.chat.completions.stream()` → `chat.completions.stream()` | Not a top-level export |
| Behavioral changes | `stream()` returns different type in v7 | Signature unchanged |
| Parameter semantics | Required field added to options object | Type unchanged |
| Namespace promotion | `beta.X` → `X` (non-beta) | Both exist simultaneously |
| Runtime deprecation | `gpt-3.5-turbo` model sunset | Not an export |

### Impact on depfix coverage
For providers where breaking changes are additive or behavioral (openai v6→v7,
anthropic minor releases), ts_exports produces zero METHOD_REMOVED changes.
depfix's value for these is limited to VERSION DRIFT detection only.

For providers where breaking changes involve class/function removal (sentry v7→v8,
discord.js v13→v14, firebase v8→v9), ts_exports works well and repo_exports.py
catches multi-major gaps.

### Possible future enhancement
A complementary detection strategy for method-level changes could use:
1. **OpenAPI spec diff** (already in providers.yaml for openai) — detects endpoint
   additions/removals/parameter changes. Limited to REST API changes, not SDK wrappers.
2. **Skill-file-driven scanning** — let the skill file declare specific call-site
   patterns to search for (e.g., "if you find `beta.chat.completions.stream`, flag it").
   This inverts the current model: instead of detecting removals from exports and then
   looking up replacements, you pre-declare what to look for.
3. **Release notes parsing** — extract breaking changes from CHANGELOG.md and map
   to code patterns. High false-positive risk.

## No-Lockfile Fallback: VERIFIED WORKING

Traced the full applicability path for the no-lockfile case:

1. `scan_manifests` sets `resolved_version=None`, `declared_range="6.49.0"`, `source="range"`
2. `_decide_one` at applicability.py:55 — `dep.resolved_version` is None → skip resolved block
3. `_decide_one` at applicability.py:82 — `dep.declared_range` is "6.49.0" → enter declared block
4. `declared_major("6.49.0")` → 6
5. `new[0]` = 7 (from the DEPENDENCY_VERSION_BUMP change's new_version)
6. `6 != 7` → **APPLIES** with "major drift to 7.32.0 requires human review"

The version drift detection works WITHOUT a lockfile because the exact pin "6.49.0" in
package.json provides enough information to compute the major-version gap.

### DB Verification
depfix.db currently has:
- `DEPENDENCY_VERSION_BUMP openai 3.3.0→7.31.0` (major jump, will trigger drift)
- `DEPENDENCY_VERSION_BUMP openai 7.31.0→7.32.0` (latest, will trigger drift)
- Zero METHOD_REMOVED records for openai (consistent with zero removed exports)
- 8 older spec_diff records (v2.3.0, param_removed/param_type_changed) — NOT_AFFECTED
  for v6.49.0 since `6.49.0 < 2.3.0` is False

### repo_exports.py Sub-case B: NOT available without lockfile
`_installed_version_for(result, "openai")` checks `dep.resolved_version` which is None.
Returns None → `synthetic_changes_for_scan` skips the package entirely.
No sub-case A or B synthetic changes. Not an issue for openai (0 removals anyway) but
important for repos using removed APIs on providers where the only BreakingChange comes
from repo_exports.py (e.g., a sentry repo without a lockfile would miss sub-case B).

## Updated T-20 Expectations

| Repo | Version Drift PR | API Migration PR | Blocker |
|------|-----------------|-----------------|---------|
| depfix-test-sentry-v6-app | YES (10.75.3→11.6.0) | Reverted by verification (T-24) | T-24 |
| depfix-test-openai-v3-chat | YES (6.49.0→7.32.0, major drift) | NO (0 removed exports) | None |
| seed-openai-v3-to-v4 | NO (vendored) | NO (vendored) | Vendored dep |

## Recommendation for Tester
1. Run the sentry repo first — it's the only one that tests the METHOD_REMOVED pipeline
2. The openai test repo WILL produce a version drift PR (major drift 6→7 detected
   via declared_range fallback). Expect "major drift ... requires human review" decision.
3. The seed repo will produce no PR (vendored). Same result as T-12.
4. No lockfile fix needed for the openai test repo — declared_range fallback works.
