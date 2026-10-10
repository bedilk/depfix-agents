# Cross-Repo Migration Gap

**Date:** 2026-10-10 (last verified: 2026-10-10)
**Author:** researcher
**Priority:** CRITICAL — action required before any future test runs or task completions are valid

## Summary

All agent code changes since project start were committed to `depfix-agents` (the coordination repo)
instead of `dependency_check` (the production codebase). The human corrected AGENTS.md on 2026-10-10
(commit `90bbb0f`) to redirect code changes going forward, but existing work has not been migrated.

The accepted task work (T-3, T-4, T-5, T-6, T-15) and all proactive implementer work exists in
`depfix-agents/src/` and `depfix-agents/tests/` — NOT in `dependency_check/`.

## Verified Delta

### providers.yaml: 15 new providers missing from dependency_check

`depfix-agents/providers.yaml` has 40 providers; `dependency_check/providers.yaml` has 25.

Missing from dependency_check (added by implementer):
| Provider | Task source |
|---|---|
| Resend | T-8 top-10, implementer added |
| MySQL | agents added |
| Astro | agents added |
| Cloudflare | T-8 top-10, implementer added |
| Datadog | T-8 top-10, implementer added |
| Plaid | T-8 top-10, implementer added |
| Auth0 | T-8 top-10, implementer added |
| Twilio Segment SDK | T-8 top-10, implementer added |
| Shopify API | T-8 top-10, implementer added |
| New Relic APM | T-8 top-10, implementer added |
| Bugsnag Error Monitoring | T-8 top-10, implementer added |
| LaunchDarkly | researcher proactive |
| HubSpot API Client | researcher proactive |
| Mixpanel Analytics SDK | researcher proactive |
| Amplitude | researcher proactive |

### Provider skill files: 35 new files missing from dependency_check

`depfix-agents/src/depfix/providers/skills/` has 43 files; `dependency_check/src/depfix/providers/skills/` has 11.

Missing (32 files, T-3 and proactive work):
```
provider_algolia.md    provider_amplitude.md   provider_anthropic.md
provider_astro.md      provider_auth0.md       provider_aws_s3.md
provider_bugsnag.md    provider_cloudflare.md  provider_datadog.md
provider_discord.md    provider_elasticsearch.md  provider_firebase.md
provider_google_cloud.md  provider_hubspot.md   provider_kafka.md
provider_langchain.md  provider_launchdarkly.md   provider_mixpanel.md
provider_mysql.md      provider_newrelic.md    provider_octokit.md
provider_plaid.md      provider_posthog.md     provider_rabbitmq.md
provider_redis.md      provider_resend.md      provider_segment.md
provider_shopify.md    provider_slack.md       provider_supabase.md
provider_twilio.md     provider_vercel_ai.md
```

Note: `dependency_check` has `provider_postgresql.md` via human commit `51560e2`.
The depfix-agents version may differ.

### Eval corpus YAML files (T-4, T-5)

Missing from `dependency_check/src/depfix/evals/corpus/`:
- `sentry_v8_callsites.yaml` — 10 sentry v7→v8 eval cases (accepted T-4)
- `ruby_callsites.yaml` — 5 ruby eval cases (accepted T-5)

### Source Python file (T-15)

Missing from `dependency_check/src/depfix/sources/`:
- `repo_exports.py` — 178-line module for repo-version-aware ts_exports diff

### Orchestrator integration (T-15)

`depfix-agents/src/depfix/orchestrator/runner.py` has `_augment_with_repo_exports` at line 396 and
the `_augment_with_repo_exports` method at line 776.
`dependency_check/src/depfix/orchestrator/runner.py` does NOT have this integration.

runner.py in dependency_check has 10+ new commits on top of the agent base — direct patch
application will likely conflict. Needs careful merge.

### Test files missing from dependency_check

Tests:
- `tests/unit/test_repo_aware_exports.py` — 24 tests for T-15 (accepted)
- `tests/unit/test_ecosystems_ruby_runtime.py` — ruby runtime tests (T-5/T-6)

Test fixtures:
- `tests/fixtures/sentry_v7_project/` — T-4 sentry v7 fixture
- `tests/fixtures/ruby_openai_project/` — T-5 ruby fixture
- `tests/fixtures/ruby_sentry_project/` — T-5 ruby fixture
- `tests/fixtures/ruby_stripe_project/` — T-5 ruby fixture
- `tests/fixtures/ruby_unrelated_project/` — T-5 negative test fixture

## Implication for "Done" Tasks

| Task | Status in TASKS.json | Actual state in dependency_check |
|---|---|---|
| T-3 redis+postgresql skills | done | provider_redis.md MISSING |
| T-4 sentry eval cases | done | sentry_v8_callsites.yaml MISSING, fixture MISSING |
| T-5 ruby eval cases | done | ruby_callsites.yaml MISSING, fixtures MISSING |
| T-6 ruby fixer tests | done | additional tests NOT verified in dep_check |
| T-15 repo_exports diff | done | repo_exports.py MISSING, runner integration MISSING |
| Provider adds (proactive) | — | 15 providers NOT in dependency_check |
| Skill files (proactive) | — | 32 skill files NOT in dependency_check |

## Migration Difficulty

**Easy (copy-only):**
- All skill files (`provider_*.md`) — no code conflict, just copy
- `repo_exports.py` — new file, no conflict
- `test_repo_aware_exports.py` — new file, no conflict
- `test_ecosystems_ruby_runtime.py` — new file, no conflict
- All eval corpus YAML files — new files, no conflict
- All test fixtures — new directories, no conflict

**Medium (YAML merge):**
- `providers.yaml` — need to insert 15 new provider blocks; the file structure is maintained so
  insertion should be safe but requires careful merge

**Hard (code merge with conflict risk):**
- `orchestrator/runner.py` — dependency_check has 10+ commits of divergence; need to diff and
  apply the T-15 augmentation logic without breaking other changes

## Recommended Action

1. Create task T-16 (implementer): migrate agent work from depfix-agents to dependency_check
   - Copy all easy files (skill files, eval YAML, test files, fixtures)
   - Merge providers.yaml (insert 15 new entries)
   - Port runner.py T-15 integration (read diff in depfix-agents, apply to dependency_check)
   - Run `make test` in dependency_check to verify no regressions

2. After T-16: re-run T-1 health check in dependency_check to get a valid test count

## Dependency_check Divergence Since Initial Analysis

dependency_check received 5 new commits after the migration gap was first identified:
- `722c263` — security: harden codebase for public launch (PR injection, defusedxml, sandbox)
- `fb74b55` — feat: add source-available license and clean credentials
- `23eea17` — fix: restore correct anthropic fixture
- `a1e1419` — fix: implement missing _upgrade_severity method on Orchestrator
- `51560e2` — feat: add call-site fixture changes for anthropic and postgresql providers

These commits make `orchestrator/runner.py` merge harder. The T-15 augmentation must be applied
as a diff on top of the current dependency_check runner.py, not a wholesale replacement.

## Commands to Verify Gaps

```bash
# Count providers
python3 -c "import yaml; p=yaml.safe_load(open('/Users/bedil_karimov/Documents/dependency_check/providers.yaml')); print(len(p['providers']))"
# → 25

# List missing skill files
diff <(ls /Users/bedil_karimov/Documents/depfix-agents/src/depfix/providers/skills/ | sort) \
     <(ls /Users/bedil_karimov/Documents/dependency_check/src/depfix/providers/skills/ | sort)

# Check T-15 integration
grep "_augment_with_repo_exports" /Users/bedil_karimov/Documents/dependency_check/src/depfix/orchestrator/runner.py
# → (no output = not present)

# Check eval corpus
ls /Users/bedil_karimov/Documents/dependency_check/src/depfix/evals/corpus/
# → call-sites.yaml, openai-node-v4-fixes.yaml, release-notes.yaml, spec-diff-coverage.yaml, spec-diff-rules.yaml
# ruby_callsites.yaml and sentry_v8_callsites.yaml are MISSING
```
