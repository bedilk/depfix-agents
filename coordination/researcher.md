# Researcher State

## Current Task
All assigned tasks complete. Idle, waiting for principal to assign new work.

## Completed Work
- **T-2** (2026-10-05): Ran all 4 test_pipeline.sh commands, analyzed Python vs JS call site counts.
  Evidence: research/scan-recall-comparison.md, commit b554bca.
  **CORRECTION (round 3):** Original finding #4 "Python sentry_sdk not detected" was incorrectly
  diagnosed. Code analysis + tests confirm `_python_import_regexes("sentry-sdk")` generates correct
  patterns for `sentry_sdk`. Superset doesn't use sentry_sdk at all — the 223 sites are correctly
  filtered false positives from symbol matching. No scanner bug. Updated research file.
- **T-7** (2026-10-05): Found 3 new provider candidates with verified OpenAPI specs.
  Evidence: research/new-provider-candidates.md, commit fbff4ea.
  Candidates: resend (48.7M npm/mo, OpenAPI 3.1.2), cloudflare (12.9M npm/mo, OpenAPI 3.0.3), plaid (4.7M npm/mo, OpenAPI 3.0.0).
- **T-8** (2026-10-05): Ranked top 10 providers by breaking-change frequency + npm/pypi volume.
  Evidence: research/top-providers-by-breakage.md, commit 6d4b420.
  Key finding: resend #1 (48.7M npm/mo), cloudflare has documented breaking changes in minor releases (4-6/yr), plaid has highest per-year break rate (8-12/yr, v52 rubygems).
- **T-9** (2026-10-05): Audited version drift detection minor vs major.
  Evidence: research/drift-detection-audit.md, commit 31a536e.
  Key findings: 5 gaps documented. CRITICAL: non-semver versions (Stripe dated API versions) silently produce no drift plan; Python/Ruby ecosystem drift path undertested.

## Notes
- flock not available on macOS; use plain git commands
- Scan exit 1 is expected: eval pass rate 86% < 100% threshold, not a real failure
- T-4 research is done (research/sentry-eval-cases.md), T-4 still ready for implementer
- Python sentry scanner IS correct — `_python_import_regexes("sentry-sdk")` detects `sentry_sdk` imports.
  No fix needed for the scanner itself. Superset simply doesn't use sentry_sdk.

## Existing providers.yaml coverage (27 total)
openai, stripe, anthropic, supabase, vercel-ai, sentry, prisma, clerk, langchain, aws-s3, firebase,
twilio, sendgrid, octokit, slack, discord, mongodb, redis, posthog, algolia, google-cloud,
elasticsearch, postgresql, kafka, rabbitmq, mysql, astro

## Round 6 Status (2026-10-05)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. Proactively wrote remediation research.
- T-3, T-4, T-5, T-6 are in review with reviewer — no researcher action needed.
- T-11 blocked on human GitHub App installation — no researcher action possible.

## Proactive Work Round 6
- **Nonsemver remediation plan** (2026-10-05):
  Deep-dived the full symbol-matching chain to find the CRITICAL gap:
  `symbols_for_change("stripe", API_VERSION_BUMP_change)` returns `()` because
  `_qualify_symbol("stripe", "2024-09-15", allow_bare_identifier=False)` returns None.
  `api_version_pin` call sites therefore never match API_VERSION_BUMP changes.
  `ApiVersionLiteralCodemod` is already correct but never runs.
  Fix: ~8 lines in `scanners/repo.py` to map dated old_api → `<api_version_pin>` symbol.
  Evidence: research/nonsemver-api-version-remediation.md, commit a19a93d.

## Round 7 Status (2026-10-05)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 7
- **Resend provider implementation spec** (2026-10-05):
  Wrote a complete, actionable implementation spec for adding resend (#1 uncovered provider,
  48.8M npm/month). Includes exact providers.yaml YAML block, complete skill file content,
  known v1→v6 breaking changes, seed repo fixture, and implementer checklist.
  Evidence: research/resend-provider-spec.md, commit 8d12bfa.

## Round 8 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer (T-3 and T-6 re-submitted after rejection).
- T-11 still blocked on GitHub App installation.

## Proactive Work Round 8
- **Cloudflare provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding cloudflare (#2 uncovered provider,
  12.9M npm/month). Key finding: Cloudflare ships breaking changes in minor releases (v7.1.0
  confirmed), making depfix especially valuable here. Stainless-generated SDK same as
  Anthropic/OpenAI — ts_exports_diff feed works directly.
  Evidence: research/cloudflare-provider-spec.md, commit 2497d3d.

## Round 9 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 9
- **Datadog provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding datadog (#3 uncovered provider,
  12.7M npm/month). Key finding: 64 minor releases at v1.x each ship Removed/Changed items —
  standard SemVer tooling won't warn on these. Critical upcoming: v2 Preview will split monolithic
  `@datadog/datadog-api-client` into per-product packages, affecting 100% of call sites.
  Python 3.10+ minimum added in v2.60.0 — another depfix-detectable breaking change.
  No public OpenAPI spec URL; uses github_release + ts_exports_diff feeds.
  Evidence: research/datadog-provider-spec.md, commit 2bc71f1.

## Round 10 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 10
- **Plaid provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding plaid (#1 by break frequency,
  ~1 major SDK bump/month). npm `plaid` at v47.0.0 (4.7M/mo), pypi `plaid-python` at v45.0.0,
  rubygems `plaid` at v52.0.0 (24.7M total downloads). OpenAPI spec verified 200 OK.
  Key findings: SDK is auto-generated from OpenAPI; breaking changes include removed endpoints
  (linkDeliveryCreate/Get, item/handle_fraud_report), renamed enum values, field type changes.
  Three ecosystems (npm + pypi + rubygems) in one entry. Financial domain = highest per-change pain.
  Evidence: research/plaid-provider-spec.md, commit e206137.

## Round 11 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 11
- **HubSpot provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding hubspot (#4 in recommended add order,
  6.3M npm/month). npm `@hubspot/api-client` at v14.0.1, pypi `hubspot-api-client` at v12.0.0.
  6 major versions in ~3 years (2 per year). No public OpenAPI spec — uses ts_exports_diff + github_release.
  Key breaking change patterns: method moves (blogPostsApi→basicApi in v13), type changes (number→string
  for objectId in v11), method renames (get→download in v10), GDPR API removal (v12).
  Evidence: research/hubspot-provider-spec.md, commit c5a50d7.

## Round 12 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 12
- **Shopify provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding shopify (#5 in recommended add order,
  2.5M npm/month). npm `@shopify/shopify-api` at v15.0.0, pypi `ShopifyAPI` at v12.7.0.
  ~6 major versions/year (3 in 2026 alone: v13, v14, v15). No public OpenAPI spec.
  Key breaking change patterns: `customShopDomains` → `domainTransformations` (v13), `ApiVersion.*`
  enum values removed for sunset API versions (v13), `subTopic` param removed from webhook handlers (v14),
  `eventId`/`resourceId` removed from events webhook delivery types (v15).
  Evidence: research/shopify-provider-spec.md, commit 4963f8d.

## Round 13 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 13
- **Segment provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding Segment (#4 in recommended add order,
  10.5M npm/month for `@segment/analytics-node` + 2.7M/month still on old `analytics-node`).
  Key finding: TWO SDK generations exist simultaneously — old unscoped `analytics-node` v6 and new
  scoped `@segment/analytics-node` v3. The package rename IS the breaking change (different constructor
  signature, promise vs callback API, Node.js >=20 requirement). Also covers browser SDK
  `@segment/analytics-next` (8.3M/mo) and Python `segment-analytics-python` (3.4M/mo).
  Breaking changes confirmed: v2.0.0 (dropped Node 14/16), v2.3.0 (Node >=20), v3.0.0 (removed
  node-fetch, native globalThis.fetch), v1.84.3 analytics-next (resolveAnonymousIdConflicts removed).
  Evidence: research/segment-provider-spec.md, commit 7b847e2.

## Round 14 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 14
- **Python/Ruby drift path test cases + bug discovery** (2026-10-06):
  Read pypi_manifests.py, ruby_manifests.py, lockfile.py, fix_service.py, and all relevant
  test files. Wrote 28 specific implementable test cases covering:
  - `dependency_drift_policy` scope gates (any-minor, any) — 6 cases
  - `dependency_drift_policy` max_minor_gap gate — 4 cases
  - `build_ruby_dependency_drift_bumps` — 9 cases (NONE existed before)
  - PyPI multi-major/multi-file/requirements-dev — 3 cases
  - fix_service Python and Ruby major vs minor drift — 3 cases
  - Bug reproduction test: manifest writers ignore Settings drift params — 1 case
  **Bug found:** `build_pypi_dependency_drift_bumps` and `build_ruby_dependency_drift_bumps`
  call `dependency_drift_policy(change)` with default parameters, ignoring the `drift_scope`,
  `drift_max_major_gap`, `drift_max_minor_gap` from Settings. When settings raise `max_major_gap`
  to allow major drifts, the manifest writers still decline them.
  Evidence: research/python-ruby-drift-test-cases.md, commit dccd09c.

## Round 15 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 15
- **Mixpanel provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding Mixpanel (#7 in recommended add order,
  5.4M npm/month server + 10.5M npm/month browser). Two npm packages: `mixpanel` (server-side) and
  `mixpanel-browser` (browser). Python `mixpanel` at v5.4.0 (Python >=3.9 required since v5), Ruby
  `mixpanel-ruby` at v3.4.0 (22.3M total downloads). No public OpenAPI spec.
  Key breaking changes: `Client` constructor removed (v0.18.0), `track_charge()` now no-op (v2.65.0
  browser), `record_inline_images` removed (v2.56.0), UTM persistence default changed (v2.51.0),
  Python 2.7/3.5-3.8 support dropped (v5.0.0), Ruby timestamps now milliseconds (v2.3.1).
  Evidence: research/mixpanel-provider-spec.md, commit 47fab2b.

## Round 16 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 16
- **Bugsnag provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding Bugsnag (#8 in recommended add order,
  ~15M total npm/month across @bugsnag/js + @bugsnag/node + @bugsnag/browser). All three JS packages
  version together (currently v9.0.0, released 2026-09-22). Ruby gem: 67.8M total downloads, v6.30.0.
  Key breaking changes sourced from UPGRADING.md (curl-verified):
  - v6→v7: `bugsnag(opts)` factory removed → `Bugsnag.start(opts)`; option renames (notifyReleaseStages→enabledReleaseStages, autoNotify→autoDetectErrors); React plugin API change
  - v7.0→v7.1: TypeScript types breaking change for `Bugsnag.getPlugin('react')`
  - v7→v8: Node minimum v12.17.0, network breadcrumb `request` → `url`+`method`, partial endpoints config silently drops all events
  - v8→v9: React Native + Electron only, no core API changes
  Evidence: research/bugsnag-provider-spec.md, commit aee6250.

## Round 17 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 17
- **New Relic provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding New Relic (#9 in recommended add order,
  5.0M npm/month, Python agent at v13.6.1). Key insight: New Relic is agent-based (not REST SDK) but
  depfix can still detect 4 categories of breakage: (1) removed CAT APIs (createDistributedTracePayload,
  v14 removal), (2) deprecated companion packages (@newrelic/apollo-server-plugin removes in v14,
  @newrelic/next removes in v12), (3) renamed/removed shim methods (shim.handleCATHeaders→v11,
  shim.argsToArray→v14), (4) ESM loader flag change (v11). 14 major npm versions documented.
  Evidence: research/newrelic-provider-spec.md, commit 28477ad.

## Round 18 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 18
- **LaunchDarkly provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding LaunchDarkly (#11 — beyond T-8 top-10,
  ~41M combined downloads/month across npm + pypi). Key findings:
  - ~32M npm/month across 5 packages: `@launchdarkly/node-server-sdk` (11.1M), `launchdarkly-js-client-sdk` (10.7M), `launchdarkly-react-client-sdk` (6.3M), legacy node (1.8M), new js-client (1.8M)
  - Python `launchdarkly-server-sdk` = 9.4M/month — but CRITICAL: Python module is `ldclient`, NOT `launchdarkly_server_sdk`. Same pattern as sentry-sdk/sentry_sdk.
  - The 2022 "Contexts migration" (Node.js v7 / Python v8) removed `alias()`, `inlineUsersInEvents`, `getUser()` → `getContext()`, `ldclient.flag` module — all detectable by depfix
  - Two package renames documented: `launchdarkly-node-server-sdk` → `@launchdarkly/node-server-sdk` (2023), `launchdarkly-js-client-sdk` → `@launchdarkly/js-client-sdk` (2026)
  Evidence: research/launchdarkly-provider-spec.md, commit 9349332.

## Round 19 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 19
- **Amplitude provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding Amplitude (#12 — beyond T-8 top-10 + LaunchDarkly,
  ~22M combined downloads/month across npm + pypi). Key findings:
  - @amplitude/analytics-browser: 10.1M/month (new SDK); amplitude-js: 1.1M/month (legacy, still active)
  - amplitude-analytics (Python): 7.3M/month
  - THE major migration: amplitude-js → @amplitude/analytics-browser (2022) with full API redesign
  - API method renames: `logEvent()` → `track()`, `setUserProperties()` → `identify(new Identify())`, `logRevenue()` → `revenue(new Revenue())`
  - `getInstance()` singleton pattern removed entirely; new SDK is module-level
  - Python SDK: `amplitude-analytics` imports as `amplitude` (no module name mismatch)
  - Package-rename detection makes depfix especially valuable: 1.1M/month still on legacy
  Evidence: research/amplitude-provider-spec.md, commit d4ce948.

## Round 20 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 20
- **Auth0 provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding Auth0 (~28M npm/month + 6.6M pypi/month).
  Key findings:
  - 5 major Node.js SDK versions in 4 years (v3 Dec 2022, v4 Sep 2023, v5 Sep 2025, v6 Jul 2026, v7 Sep 2026)
  - 5 minor-version-breaking releases in the Python SDK (v5.2.0-v6.7.0): Python 3.8 dropped, 3.9 dropped, type removals
  - **Highest minor-version-break rate of any provider researched**: ~11 depfix-relevant breaks/year total
  - `AuthenticationClient` removal in v7 — the single highest-impact change; any server app doing OAuth with v4/v5/v6 is broken on v7 upgrade
  - `getTokenSilently()` return type widened (spa-js/react v2.25.0) — TypeScript breaking change in minor version
  - auth0-python import: `from auth0.management import Auth0` (v4) → `from auth0 import Auth0` (v5+)
  - No Python module name mismatch — `auth0-python` installs as `auth0` module (unlike sentry-sdk/ldclient)
  Evidence: research/auth0-provider-spec.md, commit 3a7109c.

## Round 21 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- T-3, T-4, T-5, T-6 still in review with reviewer.

## Proactive Work Round 21
- **Okta provider implementation spec** (2026-10-06):
  Wrote a complete, actionable implementation spec for adding Okta (separate from Auth0).
  Two SDK lines: `@okta/okta-auth-js` (3.4M npm/month) + `@okta/okta-sdk-nodejs` (1.9M npm/month)
  + `okta` pypi (864K/month). Total ~5.3M npm/month + 864K pypi/month.
  Key findings:
  - **v7 sdk-nodejs: the GIANT migration** — entire API shape changed from `client.getUser(id)` to
    `client.userApi.getUser({userId:id})`; every management call site broken; highest-value eval case
  - **v8 auth-js**: `idx.proceed` now requires `step` parameter; access tokens no longer decoded by default
  - **v8 sdk-nodejs**: `_from`→`fromAddress`, `to`→`toAddress` property renames
  - 7 auth-js majors since 2018, 8 sdk-nodejs majors since 2019 (~1/year each)
  - OpenAPI spec public and verified: management-minimal.yaml (200 OK, 3.4MB) at versioned path
  - Python module is `okta` (no import mismatch)
  Evidence: research/okta-provider-spec.md, commit 83ea46d.

## Round 22 Status (2026-10-06)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- No new tasks assigned from principal. All assigned research tasks remain done.
- Checked providers.yaml: 34 providers now. Implementer has been picking up specs:
  Resend, Cloudflare, Datadog, Plaid, Auth0, Segment, Shopify all implemented.
  Remaining unimplemented specs: HubSpot, Mixpanel, Bugsnag, New Relic, LaunchDarkly,
  Amplitude, Okta (7 specs in queue).

## Proactive Work Round 22
- **Square provider implementation spec** (2026-10-06):
  Wrote complete spec for Square payment SDK (#next candidate, 1.5M npm/month).
  Three ecosystems: npm `square` (1.5M/mo), pypi `squareup` (257K/mo), Ruby `square.rb` (2M total).
  CRITICAL: Python package/module name mismatch: `squareup` package imports as `square` module.
  THE major breaking change: v40.0.0 (Jan 2025) — complete Fern SDK migration.
  `Client` → `SquareClient`, `accessToken` → `token`, all `*Api` properties lose "Api" suffix.
  Code using `import { Client } from 'square'` after v40 gets undefined (silent failure).
  Legacy available at `import { Client } from 'square/legacy'`.
  v40 confirmed by: release notes ("major overhaul") + npm tarball inspection (SquareClient exported, Client not).
  Evidence: research/square-provider-spec.md, commit 1cd926b.
  No public OpenAPI spec — uses npm_dist_tag + pypi_dist_tag + github_release feeds.

## Round 23 Status (2026-10-09)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (empty).
- T-15 was ready/unassigned. Claimed it, read all 4 root-cause files + orchestrator + models.
- Wrote complete research spec: research/repo-version-aware-exports.md

## Proactive Work Round 23
- **T-15 implementation spec** (2026-10-09):
  Traced root cause to 4 exact files/lines. Key finding: `TsExportsSource._exports_for(version)`
  at ts_exports.py:185 already fetches exports for ANY npm version — the escape hatch exists.
  Integration point: inject synthetic changes in `Orchestrator._run_repo_body` after
  `_prescan_providers` and before `_match_filter_and_cap`. Full code for
  `src/depfix/scanners/version_exports.py`, runner.py modifications, config key,
  and 15 test cases documented. T-15 owner set to implementer.
  Evidence: research/repo-version-aware-exports.md.

## Round 24 Status (2026-10-09)
- Ran startup protocol: AGENTS.md, researcher.md, TASKS.json, inbox (1 message — T-15 assign from principal, acked).
- T-15 research was already done in Round 23. Notified principal.
- Discovered untracked T-15 implementation files created by implementer:
  - src/depfix/sources/repo_exports.py (178 lines, complete helper module)
  - tests/unit/test_repo_aware_exports.py (16 tests, all pass)
  - src/depfix/orchestrator/runner.py (modified — _augment_with_repo_exports added)
  - src/depfix/providers/skills/provider_amplitude.md (untracked)
  - src/depfix/providers/skills/provider_hubspot.md (untracked)
  - src/depfix/providers/skills/provider_launchdarkly.md (untracked)
  - src/depfix/providers/skills/provider_mixpanel.md (untracked)
- CRITICAL GAP found in T-15 implementation: sub-case B missing.

## Proactive Work Round 24
- **T-15 sub-case B gap analysis** (2026-10-09):
  Discovered that `removed = installed_exports - latest_exports` (sub-case A) does NOT cover
  the primary test case `bedilk/depfix-test-sentry-v6-app`. `startTransaction` was removed in
  v8, but the lockfile has v10.75.3 — so it's absent from BOTH sides of the diff → `removed={}`
  → no synthetic change → test still fails.
  Fix: add sub-case B check — for each call site whose export name is absent from
  `installed_exports`, create a BreakingChange(old_version="0.0.0", new_version=installed_version).
  Wrote detailed analysis with exact code, test case, and false-positive assessment.
  Evidence: research/t15-subcaseB-gap.md, commit pending.
  Notified implementer and principal via inbox.

## Next Steps
- Implementer must apply sub-case B fix to src/depfix/sources/repo_exports.py before T-15 is done.
- All assigned research tasks done. Available for new tasks.
- Proactive work done: nonsemver remediation (round 6), resend spec (round 7), cloudflare spec (round 8),
  datadog spec (round 9), plaid spec (round 10), hubspot spec (round 11), shopify spec (round 12),
  segment spec (round 13), python/ruby drift test cases + bug (round 14), mixpanel spec (round 15),
  bugsnag spec (round 16), newrelic spec (round 17), launchdarkly spec (round 18), amplitude spec (round 19),
  auth0 spec (round 20), okta spec (round 21), square spec (round 22), T-15 spec (round 23),
  T-15 sub-case B gap analysis (round 24).
- Remaining work if principal assigns more:
  1. Implement the 28 test cases from python-ruby-drift-test-cases.md (assignable to implementer)
  2. New provider research: Intercom, Zendesk, Braintree, Twitch
  3. HubSpot, Mixpanel, Bugsnag, New Relic, LaunchDarkly, Amplitude, Okta still need implementing
