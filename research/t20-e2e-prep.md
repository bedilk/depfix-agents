# T-20 End-to-End Test Preparation

## Prerequisites

### Branch State
T-20 must run on `fix/t19-plan-pr-gate` (or after PRs #10 and #11 are merged to main).
This branch contains:
- repo_exports.py (T-15: synthetic BreakingChange from installed exports)
- classifier.py `_package_from_feed_key` (T-18: correct package recovery)
- runner.py `_enrich_removal_from_skill` (T-19: skill-file enrichment)
- upgrade.py:140 gate on `new_api` (T-19)
- fix_service.py:201 gate on `new_api` (T-19)

**Important:** As of 2026-10-12, the T-19 fixes are UNCOMMITTED in the working tree.
The implementer must commit them before T-20 can run.

### DB State

Current `depfix.db` contains:

| Source | Package | Count | Status |
|--------|---------|-------|--------|
| `learned:*` events | `sentry` (WRONG) | 477 method_removed | Stale — classifier fallback set wrong package |
| `ts_exports:@sentry/node` (event 29) | `@sentry/node` | 477 method_removed | Correct — ATTR_* constants (v10→v11) |
| `ts_exports:@sentry/node` (event 125) | `@sentry/node` | 0 | Classified but no breaking changes |
| `npm:@sentry/node:latest` (event 123) | `@sentry/node` | 1 | dependency_version_bump |
| `npm:...:installed:10.75.3` (event 136) | `@sentry/node` | 1 | dependency_version_bump |

**Key finding: DB cleanup is NOT strictly required for T-20.**

Reason: `build_upgrade_plan` at upgrade.py:114 filters by `c.package == package` where
`package="@sentry/node"`. The 477 stale `package='sentry'` rows are automatically excluded.
The `startTransaction` symbol does NOT exist in ANY persisted BreakingChange row — it is
only created at runtime by repo_exports.py sub-case B.

### Optional DB Cleanup (Recommended for cleanliness)

```bash
cd /Users/bedil_karimov/Documents/dependency_check

# Back up
cp depfix.db depfix.db.bak-$(date +%Y%m%d)

# Delete the 477 stale rows with wrong package
sqlite3 depfix.db "DELETE FROM breaking_change WHERE package = 'sentry';"

# Verify
sqlite3 depfix.db "SELECT package, COUNT(*) FROM breaking_change WHERE provider_id='sentry' GROUP BY package;"
# Expected: @sentry/node|479  (477 ATTR_* + 2 version bumps)

# The learned:* source events' classified_at does NOT need to be reset
# because _package_from_feed_key does not handle the "learned:" prefix —
# re-classifying them would produce the same wrong package='sentry' result.
```

## Test Repo 1: bedilk/depfix-test-sentry-v6-app

### Expected Pipeline Flow

1. **`depfix init`** — creates provider entry for sentry if not exists
2. **`depfix scan --repo bedilk/depfix-test-sentry-v6-app`** — finds call sites:
   - `startTransaction` (removed in v8, but repo uses v10.75.3 — ghost API)
   - `getCurrentHub` (removed in v8)
   - Potentially other v7 APIs
3. **repo_exports.py sub-case B** — fetches v10.75.3 exports from npm, finds these symbols
   absent → creates synthetic METHOD_REMOVED BreakingChange with `package="@sentry/node"`
4. **`_enrich_removal_from_skill`** — reads provider_sentry.md:
   - `startTransaction` → `new_api="Sentry.startSpan"`, `migration_guide="(bullet line)"`
   - `getCurrentHub` → `new_api="Sentry.getClient"` (if in skill file)
5. **upgrade.py:140** — allows through because `change.new_api` is set
6. **fix_service.py:201** — allows through because `change.new_api` is set
7. **LLM fixer** — generates code replacing `startTransaction(ctx)` with `startSpan({...})`
8. **PR opened** on GitHub

### Verification Checklist
- [ ] PR is opened on `bedilk/depfix-test-sentry-v6-app`
- [ ] PR contains `startTransaction` → `startSpan` migration
- [ ] `package.json` version bump to latest @sentry/node (if drift change exists)
- [ ] Fix is syntactically correct JavaScript
- [ ] No false positives (ATTR_* constants should NOT be in the PR — they have no `new_api`)

## Test Repo 2: bedilk/depfix-test-openai-v3-chat

### Expected Flow
This tests VERSION DRIFT, not API removal. The repo has an older openai SDK.
- `depfix scan` detects version drift (old openai version → latest)
- `build_upgrade_plan` builds a version bump plan
- The drift path (not METHOD_REMOVED) handles this case

### Verification
- [ ] PR opened with version bump in package.json
- [ ] Any API migrations included if applicable (openai v3→v4 changes)

## Test Repo 3: bedilk/seed-openai-v3-to-v4

### Expected Flow
Similar to test repo 2 but specifically targets the v3→v4 OpenAI migration.
- `ChatCompletion.create()` → `client.chat.completions.create()`
- Package rename: `openai` stays but API completely restructured

### Verification
- [ ] PR opened with correct API migration
- [ ] `new OpenAI()` client instantiation added
- [ ] `ChatCompletion.create()` replaced with `client.chat.completions.create()`

## Commands for Tester

```bash
cd /Users/bedil_karimov/Documents/dependency_check

# Ensure on the right branch
git checkout fix/t19-plan-pr-gate

# Dry run first
depfix scan --repo bedilk/depfix-test-sentry-v6-app --dry-run --no-pr
depfix plan --repo bedilk/depfix-test-sentry-v6-app --dry-run --no-pr

# Check output before real run
depfix scan --repo bedilk/depfix-test-sentry-v6-app
depfix plan --repo bedilk/depfix-test-sentry-v6-app
depfix apply --repo bedilk/depfix-test-sentry-v6-app

# Repeat for other repos
depfix scan --repo bedilk/depfix-test-openai-v3-chat
depfix plan --repo bedilk/depfix-test-openai-v3-chat
depfix apply --repo bedilk/depfix-test-openai-v3-chat

depfix scan --repo bedilk/seed-openai-v3-to-v4
depfix plan --repo bedilk/seed-openai-v3-to-v4
depfix apply --repo bedilk/seed-openai-v3-to-v4
```

## Risks and Mitigations

1. **repo_exports.py npm fetch failure**: If npm registry is unreachable, sub-case B falls back
   to `installed_exports=None` → no synthetic changes → startTransaction not detected.
   Mitigation: verify network access first.

2. **Skill file arrow mismatch**: If `startTransaction` line in provider_sentry.md doesn't match
   the regex pattern, enrichment returns None → change stays REPORT_ONLY.
   Mitigation: verified that the committed skill file has the correct format.

3. **LLM quality**: The fix depends on Bedrock (LLM_PROVIDER=bedrock) generating correct code.
   The `new_api` and `migration_guide` are passed to the fixer prompt as context.
   Mitigation: use `--dry-run` first to inspect the plan before applying.
