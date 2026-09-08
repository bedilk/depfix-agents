# Day 2 Decisions

Locked-in choices from the Day 2 restructure. Change only with a follow-up ADR.

## Naming

- **Package name:** `depfix`
- **Import path:** `depfix.*`
- **Console script:** `depfix` (defined in `pyproject.toml` → `[project.scripts]`)

## Layout

- **`src/`-layout** — avoids the classic "editable install picks up the wrong copy"
  bug, forces the package to be installed to be imported.
- Subpackages by responsibility, not by layer:
  - `core/` — models + top-level orchestrator (`DependencyFixAgent`)
  - `scanners/` — codebase search / pattern matching
  - `fixers/` — LLM-driven code generation
  - `validators/` — post-hoc syntax / semantic checks
  - `api/`, `workers/` — placeholders for future HTTP + async surface

## Tooling

| Concern      | Choice                        | Rejected                  |
| ------------ | ----------------------------- | ------------------------- |
| Deps         | `pip` + `requirements*.txt`   | Poetry, PDM, uv           |
| Metadata     | `pyproject.toml` (PEP 621)    | `setup.py`                |
| Lint+format  | `ruff` (`check` + `format`)   | flake8 + black + isort    |
| Type check   | `mypy`                        | pyright, pyre             |
| Security     | `bandit`                      | —                         |
| Tests        | `pytest` + `pytest-cov`       | unittest, nose            |
| Config       | `pydantic-settings` (v2)      | `configparser`, `dynaconf`|

## Python & runtime

- Minimum Python: **3.11**
- CI matrix: **3.11**, **3.12**
- Node.js **20+** required at runtime for JS syntax validation

## Model

- Default Gemini model: **`gemini-2.5-flash`**.
- Rationale: `gemini-1.5-*` returns 404 on new API keys. `2.5-flash` is the
  cheapest available option that still passes the sample-project fixes end-to-end
  (8/8 successful, ~$0.003 total on the demo).

## CI/CD

- Provider: **GitHub Actions** (`.github/workflows/ci.yml`).
- Pipeline: `lint` → `test` (matrix) → `build-docker` (smoke).
- Concurrency: cancel-in-progress per branch.
- Coverage: XML artifact uploaded from the 3.11 job.
- Integration tests are **not** run in CI (they cost money and need a live key).

## Infrastructure

- **Dockerfile:** multi-stage (builder + runtime), non-root user, Node.js installed
  in the runtime stage.
- **docker-compose.yml:** ships Postgres 16 and Redis 7 alongside the app for
  local dev. No hosting target is configured — the image is not pushed to a
  registry.

## Explicitly deferred

- Publishing to PyPI
- Hosted deploy (Railway / Render / Fly / etc.)
- Async worker implementation (`workers/` is a stub)
- HTTP API (`api/` is a stub)
- Non-JS/TS language support in the validator

# Day 3-4 Decisions — npm registry polling

## Runtime

- **One-shot** `depfix poll --once`; scheduling is external (cron / systemd /
  k8s CronJob). Rejected: in-process scheduler (adds daemon lifecycle we don't
  need at this scale).

## HTTP client

- **`httpx` (sync)**. Rejected: `aiohttp` / async httpx — async offers no win
  for ≤hundreds of packages per run and complicates test setup.
- Sends `Accept: application/vnd.npm.install-v1+json` (abbreviated response).
- **No in-process retry loop.** Cron re-invokes on the next tick — that's the
  retry. A transient 5xx or timeout is surfaced as a per-package failure in
  the poll outcome; the process still exits `0` unless *every* package failed.

## Persistence

- **SQLAlchemy 2.x + psycopg 3** against Postgres 16 from `docker-compose.yml`.
  Rejected: raw psycopg (more boilerplate for no clear benefit at this stage).
- **Schema creation via `Base.metadata.create_all`** for now. **Alembic
  migrations are deferred** until Week 2's changelog table lands, at which
  point we'll add a follow-up ADR here.

## Package list

- **YAML file** (`packages.yaml`) with a top-level `packages:` list. Rejected:
  DB-managed list (needs a dashboard to manage — Week 8+); CLI-only args
  (no persistence).

## Tables

| Table              | Purpose                                                       |
| ------------------ | ------------------------------------------------------------- |
| `tracked_package`  | one row per package; keeps `last_latest`, `last_polled_at`.   |
| `version_event`    | emitted when `last_latest` changes; drives Week 2+.           |

An earlier draft included a `package_version_snapshot` audit table and an
ETag / `last_http_status` column on `tracked_package`. Both were dropped —
`version_event` already captures every change, and diagnostic HTTP state
belongs in logs, not the schema. Revisit if we ever need to answer "what did
the registry return at time T" for something other than debugging.

# Week 1 Decisions — change sources

## Architecture

- **Provider owns N `ChangeSource` feeds**, not "one package, one version
  string". `npm dist-tag` was the trunk assumption through Day 4; it is now
  one feed kind among several (`github_release`, `openapi_spec`, with
  `changelog_file` / `changelog_html` / `rss` declared for Week 2). Every
  provider entry in `providers.yaml` can mix any number of feed kinds.
- **`ChangeSource` is the seam.** Two methods only: `feed_key` (stable
  identity — the primary key of persisted state) and `poll(state) ->
  FeedPoll`. Sources are stateless; the watcher owns persistence. This is
  what makes each source testable with a stubbed HTTP client and no
  database, and what let the differ ship with pure-function unit tests.
- **`Watcher.run_once()` replaces `NpmPoller.poll_once()`** as the trunk loop.
  Still one-shot by design — cron remains the scheduler *and* the retry
  loop, unchanged from the Day 3-4 ADR. Rejected: an in-process scheduler
  (still no daemon lifecycle we want to own).
- **`SourceDeps` bundles what sources need** (shared `httpx.Client`, the
  existing `NpmRegistryClient`, the spec cache dir, size caps, GitHub API
  base URL) and is built once per watch run via `SourceDeps.from_settings()`.
  Rejected: constructing clients per-source — that would open a new
  connection pool per feed for no benefit.

## OpenAPI diffing

- **Structural diff, not text diff.** `openapi_diff.diff_specs()` walks
  paths → operations → parameters → request/response schemas and emits
  typed `SpecChange` records (`PATH_REMOVED`, `PARAM_NOW_REQUIRED`,
  `PROPERTY_TYPE_CHANGED`, etc.) rather than a line-based diff. A line diff
  cannot distinguish "someone reordered YAML keys" from "someone deleted a
  required field", and that distinction is the entire value of the feature.
- **Severity is direction-aware.** Removing a *request* property or enum
  value breaks callers who still send it; removing the same thing from a
  *response* only breaks callers who over-parse. Request-side removals are
  `BREAKING`; response-side are `POTENTIALLY_BREAKING`. This is why
  `SpecChange.direction` exists as a first-class field, not metadata bolted
  on later.
- **Local `$ref` resolution only**, with cycle-safe traversal and a
  `MAX_DEPTH` cap (6). Remote/external `$ref`s are out of scope for Week 1 —
  every provider we watch inlines or self-references its schemas.
  `allOf` is shallow-flattened (union of member properties) rather than
  fully resolved against JSON Schema semantics; `oneOf`/`anyOf` are not
  interpreted at all yet.
- **Change list is capped** (`MAX_CHANGES`, default 500) so a from-scratch
  spec rewrite produces a bounded report instead of a multi-thousand-line
  wall of noise that nobody reads.
- **Content-hash detection, not ETags.** Specs are compared by `sha256` of
  the fetched body against the last cached copy, not HTTP `ETag`/
  `If-None-Match`. Providers are inconsistent about serving correct ETags
  for raw GitHub URLs and static JSON dumps; a body hash is always correct
  and costs one hash per poll.

## Persistence

- **New tables, old tables untouched.** `provider`, `feed_state`,
  `change_event`, `spec_change` are additive. `tracked_package` and
  `version_event` are not touched by this change — see "deprecated" below.
- **`feed_state` is the compare-and-store cursor**, keyed by
  `(provider_id, feed_key)`. It stores `last_token` (opaque per source: a
  semver, a tag name, a spec's `info.version`), `last_payload_sha256`, and
  `last_payload_path` — a pointer to the cached OpenAPI document on disk,
  not the document itself. Stripe's spec is ~6 MB; storing it as a DB
  column would bloat every backup and is never queried by column.
- **`dedupe_key` on `change_event` is the Week 6 idempotency anchor.** It is
  `sha256(provider_id|feed_key|new_token)` — a function of *where we
  landed*, not of the event body. A provider silently editing release notes
  must not produce a second event for the same version; only a real cursor
  move does.
- **Still no Alembic.** Every table added this week is additive, so
  `Base.metadata.create_all` remains sufficient, per the Day 3-4 decision.
  Alembic still lands when an `ALTER` is unavoidable — flagged for Week 6.

## Deprecated this week, deleted next

- `depfix poll`, `pollers/npm.py`, `packages.yaml`, and the `tracked_package`
  / `version_event` tables are **kept alive, unchanged, one more week** so
  existing cron jobs don't break mid-migration. `depfix poll` now prints a
  deprecation notice pointing at `depfix watch`. All of it is deleted in
  Week 2 alongside the lodash fixture.

## Failure posture

- **One bad feed must never lose the results of the others.** Every
  `source.poll()` call is wrapped; a source that raises is treated as a bug
  in that source, not a reason to abort the run — it is recorded as a
  `failed` feed report and the watcher moves on.
- **Each provider commits independently** inside `run_once()`, so a crash
  partway through a run cannot roll back cursors already advanced for
  earlier providers.
- **CLI exit code mirrors the Day 3-4 poller convention:** `depfix watch`
  exits non-zero only if *every* feed failed. Partial failure (one feed
  down, others healthy) still exits `0` — cron/systemd should page on "the
  whole run is dark", not on "one flaky feed".

# Week 2 Decisions — classification + eval harness

## Classification

- **Two classification paths, one `Classifier` router.** A `ChangeEvent`
  with `spec_changes` (from `depfix watch`'s OpenAPI diffing) is classified
  deterministically by `classify.spec_rules` — no LLM call, no hallucination
  risk, `confidence` always `1.0`. An event with only prose `body` (release
  notes) is classified by `classify.notes.NotesClassifier`, which asks an
  LLM and is lower-precision by design.
- **Anti-hallucination gate on the LLM path.** Every LLM-proposed change
  must carry an `evidence` quote found verbatim (whitespace-insensitive) in
  the source release notes; a change whose quote isn't found is dropped
  outright rather than kept at a discount. A missed change can still be
  caught some other way (spec diff, corpus, manual triage); a fabricated
  one erodes trust in every other line of the report.
- **`temperature=0` on every classification call**, so eval scores are
  stable run-to-run rather than a source of flaky CI.
- **Idempotent persistence.** `BreakingChange.dedupe_key` is a hash of
  `provider_id|package|kind|old_api`; `classify.store.persist_classification`
  skips changes whose dedupe key it already has a row for, and
  `change_event.classified_at` is stamped only on success — an event that
  errors (e.g. release notes with no LLM configured) is left unclassified so
  a later run retries it instead of giving up forever.

## Eval harness

- **`verified: true|false` is mandatory on every corpus case**, enforced by
  the loader raising rather than defaulting. A silently-defaulted
  `verified: true` is exactly the kind of thing that inflates a pass rate
  without anyone noticing.
- **Property-based scoring, not exact-match.** Classification cases match on
  `(kind, old_api substring, min_confidence)` greedily one-to-one; fix cases
  assert `must_contain`/`must_not_contain`/`max_changed_line_ratio`.
  Exact-match on LLM output measures formatting luck, not correctness.
- **`--no-llm` skips, never fails, LLM-requiring cases.** `depfix eval
  --no-llm --fail-under 1.0` runs in CI without any API key and gates only
  the deterministic `spec_diff` corpus; `release_notes`/`fix_generation`
  cases are reported as `skipped` and excluded from `pass_rate` in either
  direction.
- **Regression detection is per-case and one-directional.**
  `compare_reports()` flags only cases that flipped pass -> fail; an
  improved aggregate pass rate can otherwise hide one case that broke.
- **Shipped ~15 honest cases, not a padded 20+.** The corpus favors a
  smaller set of `verified: true` deterministic cases plus a few
  `verified: false` LLM cases that are runnable but haven't been scored
  against a live model in this environment, over fabricating more cases to
  hit a round number.

## Removed this week

- `depfix poll`, `pollers/npm.py`, `packages.yaml`, `PACKAGES_FILE`, and the
  `tracked_package`/`version_event` tables are deleted outright (not just
  deprecated) — superseded by `depfix watch` + the Week 1 sources layer.
  `depfix run` no longer ships a built-in lodash demo fixture; the fixture
  and test suite now exercise a real SDK migration
  (`openai.createChatCompletion` -> `openai.chat.completions.create`,
  openai-node v3 -> v4) via `--change-file`/`--from-event`.

# Week 3 Decisions — repo access + call-site scanner

## GitHub App auth

- **GitHub App, not a PAT, for repo access.** `github_token` (Week 1) remains
  a PAT used only to poll public release feeds; a separate GitHub App
  (`GitHubAppAuth`) mints short-lived, least-privilege installation tokens
  (`contents: read`, scoped to the specific repo) per scan. A long-lived PAT
  with broad repo access would be a standing credential for something that
  only ever needs read-only, single-repo, few-minutes-lifetime access.
- **App JWT signed with `PyJWT[crypto]` (RS256)**, not a hand-rolled signer.
  The private key is accepted either inline (`github_app_private_key`, for
  secret-manager-injected env vars) or via a `.pem` file path
  (`github_app_private_key_path`, for local dev) — the inline value wins if
  both are set, so a deploy env can override a checked-in dev key without
  editing files.
- **Installation tokens are cached in-process until expiry**, keyed by
  installation id, rather than re-minted on every call — GitHub rate-limits
  token creation, and a scan touches the API more than once per run.
- **`InstallationToken.__repr__`/`__str__` scrub the secret.** A token
  accidentally landing in a log line or exception traceback must not leak
  the credential itself.

## Shallow clone service

- **`git clone --depth=1`, not the GitHub REST/tarball API.** A shallow clone
  gives a real working tree (needed for the manifest + call-site scanners to
  just read files off disk) with bounded network/disk cost, and reuses the
  same `git` binary already required for local `--path` scans instead of a
  second code path for "how do I get these files."
- **Size-capped and always cleaned up.** `clone_max_repo_mb` rejects an
  oversized checkout after the clone completes; either way (success or cap
  violation) the temp directory is removed — a scanner that leaks clones to
  disk on every run of a scheduled job is a slow-motion outage.
- **Tokens are scrubbed from clone-failure error messages.** A failed `git
  clone` embeds the URL (with credentials) in its stderr by default; that
  string is redacted before it's ever raised, logged, or surfaced to a CLI
  user.
- **`Checkout.resolve_inside` blocks path traversal.** Scan results reference
  file paths relative to the checkout root; resolving them without checking
  they stay inside that root would let a crafted repo (e.g. a symlink or a
  `../`-laden manifest reference) point the scanner at files outside the
  clone.

## Repo / call-site scanner

- **Regex + binding propagation, not a full parser (yet).** `callsites.py`
  tracks `require`/`import` bindings and re-export hops (`module.exports =
  client`, `export const client = ...`) across files with degrading
  confidence (HIGH direct → MEDIUM one-hop → LOW two-hop wrapper), rather
  than building/depending on a JS/TS AST. `scan_min_recall` (default `0.85`)
  is the trigger, per `docs/plan.md`: if the `call_sites` eval category's
  recall drops below that floor, the regex approach is retired in favor of
  tree-sitter — not before, since a parser dependency is a bigger cost than
  the regex approach's current known gaps (e.g. quoted-key version-pin
  literals, see `test_callsites.py`).
- **`build_scan_target` narrows scope from a `BreakingChange` when one is
  supplied**, using `call_site_hints` plus a dotted-symbol extraction off
  `old_api` (prose descriptions are ignored, not mistaken for a symbol) —
  scanning for every symbol in the provider when the caller already knows
  which API changed wastes time and produces noisier reports.
  With no change given, every provider symbol is in scope (the "which repos
  even use this SDK at all" case).
  A directory that happens to be nested inside a resolved but unrelated
  outer repo (e.g. this tool's own checkout, or a subfolder of some
  monorepo) must not report the outer repo's commit as if it belonged to
  the scanned path — that's a metadata-integrity bug, not just cosmetic.
- **Manifest scanning resolves from the lockfile when present, else falls
  back to the declared range.** A lockfile pins the exact installed
  version; without one, `range_allows_major` conservatively decides whether
  the *declared* semver range could resolve to a version affected by a
  given breaking change. Ranges it can't reason about (`latest`, `*`, git
  URLs, `workspace:`, multi-constraint space-separated specs) return
  `None` (unknown) rather than guessing — a false "not affected" is worse
  than an honest "can't tell."

## Persistence

- **New tables only: `repo`, `repo_scan`, `call_site`.** No existing table is
  touched. `upsert_repo` never clobbers a previously-recorded field
  (`installation_id`, `default_branch`, etc.) with `None` on a later call
  that doesn't have that information — e.g. a local `--path` scan (no
  installation) must not blank out a repo's installation id recorded by an
  earlier `--repo` scan of the same repo.
- **Every call site is persisted, not just actionable ones.** LOW-confidence
  sites are report-only (never auto-fixed) but still valuable for a human
  reviewing scan history; `depfix scan` filters them from the default CLI
  output (`--show-low` to include them) without dropping them from the DB.

## CLI

- **`depfix scan`** clones (`--repo owner/name`) or reads a local checkout
  (`--path`), narrows to a `BreakingChange`'s symbols when
  `--change-file`/`--from-event` is given, and by default persists the
  result (`--no-save` to skip). **`depfix repos`** lists repos visible to
  the configured GitHub App installation(s) — the "what can I even scan"
  discovery step before a real `--repo` invocation.

# Week 4 Decisions — apply/verify pipeline

## Workspace editing

- **`WorkspaceEditor` preserves byte-level formatting on write, not just
  content.** `write_fix` captures a file's original bytes/mode before its
  first write and re-encodes the fixed text to match the original's BOM,
  CRLF-vs-LF line endings, and trailing-newline presence. A diff (and a
  revert) full of incidental whitespace churn because the tool normalized
  line endings on the way in would bury the actual fix.
- **Atomic writes (`os.replace` after a same-directory temp-file write)**,
  not an in-place truncate. A process interrupted mid-write must never
  leave a half-written source file on disk — that's a self-inflicted
  outage in whatever repo is being fixed.
- **Revert restores the *first*-observed bytes, not the previous write's.**
  `write_fix` only captures `_originals[relpath]` the first time a given
  path is touched; this is what lets `Verifier` write a candidate fix,
  revert to run a clean baseline, rewrite the fix, and ultimately land back
  on the pre-fix state no matter how many times it toggles the file.
- **`session()`'s `keep_on_exit` is only honored for temporary checkouts.**
  A caller-supplied local directory (`depfix fix --path`) is never left
  modified, even if the caller asks — silently mutating someone's real
  working tree from a `--path` invocation would be a much worse surprise
  than ignoring the flag.

## Verification

- **Identity-based baseline-vs-after-fix comparison, not a pass/fail
  count.** `VerificationReport.new_failure_count` diffs
  `after_fix.failed_identities - baseline.failed_identities`. A repo with
  3 pre-existing failures where a fix breaks a 4th distinct test must not
  be waved through as "still 3 failures" just because some unrelated flaky
  test happened to pass in the same run.
- **A degraded parse on *either* run marks every on-disk edit `SUSPECT`,
  never `KEPT` or `REVERTED`.** `used_fallback_parser` means only
  aggregate pass/fail counts were recoverable (no per-test identities), so
  there's no reliable way to tell "the same failures, just reordered" from
  "a different failure with the same count" — the tool says "couldn't
  confirm" rather than guessing either way.
- **Verification runs `npm install` for real, inside a disposable copy of
  the checkout, not a mock.** The whole point of Week 4 is to catch fixes
  that are syntactically fine but semantically wrong (call the right
  method with the wrong shape, miss a renamed field); nothing short of
  actually running the target repo's own tests would catch that class of
  bug.
- **A missing test script, a failed install, or a crashed/timed-out test
  run all mark edits `SUSPECT` (kept on disk, not reverted).** Failing
  *open* is deliberate: verification's job is to catch a fix that broke
  something, not to auto-revert a good fix just because the environment
  couldn't prove it — a scan-only repo with no `test` script and an LLM fix
  that's actually correct shouldn't be thrown away for lack of evidence
  either way.

## Sandbox execution

- **Allowlisted environment, not a denylist, for every `npm`/`node`
  subprocess this tool runs on a target repo's behalf.** `ENV_ALLOWLIST`
  (`sandbox.py`) names the handful of vars `npm`/`node`/`yarn`/`pnpm`
  actually need; everything else in this process's environment —
  credentials, tokens, cloud SDK config — is stripped rather than trying
  to enumerate every secret-shaped name a deployment might set.
- **Fixed argv, never a shell string.** `run_sandboxed` always calls
  `subprocess.Popen` with a list, so nothing in a target repo's
  `package.json` (script text, package names) is ever interpreted by a
  shell.
- **`--ignore-scripts` on install by default.** `postinstall`/`preinstall`
  hooks are exactly where a hostile dependency tree would put arbitrary
  code execution; verification needs the *dependencies* installed to run
  tests, not permission to run their install-time scripts.
- **Timeout kills the whole process group (`killpg`), not just the direct
  child.** Test runners spawn workers/watchers; killing only the parent
  process on timeout would leave orphaned children running.
- **Output is byte-capped in memory (`DEFAULT_MAX_OUTPUT_BYTES = 2_000_000`),
  not buffered unbounded.** A runaway `console.log` loop in a repo's own
  test script is untrusted output from this tool's perspective and
  shouldn't be able to exhaust memory just because verification ran it.

## Failure attribution

- **Four-tier trust order, most to least reliable, documented directly on
  `attribution.py`:** (1) import graph — a failing test file that actually
  imports the touched file via the scanner's own relative-import
  resolution; (2) filename convention — `chat.test.js`/`__tests__/chat.js`
  naming `chat.js`; (3) sole-candidate elimination — if only one file was
  touched at all, every new failure must be about it by definition; (4)
  unattributed — reported as such, never guessed at. A batch fix touching
  several files needs to know *which* file a new failure is about so only
  that file gets reverted, not the whole batch.
- **Any unattributed failure marks every remaining on-disk edit in that
  batch `SUSPECT`, not just the one nearest the failure.** Clearing an
  edit as confirmed-`KEPT` while some new failure in the same run can't be
  pinned on anything would be trusting a guess.

## Persistence (`fix_store`)

- **New tables only: `fix_run`, `file_fix`, `test_run`.** Mirrors the Week
  3 scanner's "additive, never touch existing tables" convention.
- **Every edit is persisted regardless of verdict, not just the ones that
  ended up on disk.** A `SKIPPED`/`REVERTED` edit *is* the "why didn't this
  get fixed" record a human reviewing a fix run needs — dropping anything
  but `KEPT` edits would make failed fix attempts invisible after the
  fact.
- **Baseline and after-fix test runs are both persisted (`test_run.phase`)
  when verification actually ran**, with per-run `failed_identities`, not
  just counts — the same identity-over-count principle as
  `new_failure_count` applies to what gets stored, not just what gets
  compared live.

## Local-copy cloning

- **`CloneService.copy_local`, a second entry point alongside `clone()`.**
  `depfix fix --path` needs a disposable copy to install dependencies into
  and run tests against — `local()` (Week 3) deliberately never deletes or
  mutates its target, since it's presumed to be the caller's real working
  tree, so it can't be reused for something that needs to write files.
  `copy_local` returns `is_temporary=True` for exactly this reason.
- **`.git`/`node_modules` are excluded from both the size check and the
  copy itself.** Neither is needed by the fix/verify pipeline (dependencies
  get reinstalled fresh either way); copying them would just inflate the
  size check against `clone_max_repo_mb` for repos that happen to have a
  large `node_modules` checked in.
- **Symlinks are dereferenced during the copy (`symlinks=False`), same
  rationale as `clone()`'s `core.symlinks=false`.** A symlink materialized
  as a real file/directory can't be used to smuggle a reference to
  something outside the copy back into what's supposed to be a sandboxed
  checkout.

## Verifiable fixture

- **`tests/fixtures/openai_v3_verifiable` ships a self-contained SDK shim,
  not a real `openai` dependency.** Zero real npm packages means
  `npm install` has nothing to fetch over the network, and the fixture's
  own `client.js`/`openai-shim.js` exposes both the v3 method
  (`createModeration`) and the v4 replacement
  (`moderations.create`) on the same object — enough surface for one
  fixture to exercise both a correct migration (`KEPT`) and a broken one
  (`REVERTED`) against a real `node --test` run, without needing network
  access or a paid API key.
- **The fixture's `test` script pins `--test-reporter=tap`
  (`node --test --test-reporter=tap`), not bare `node --test`.** Node's
  default `node --test` reporter varies by Node version (newer versions
  default to a "spec"-style unicode summary rather than TAP even when
  output isn't a TTY); `depfix.verify.runner` only requests an explicit
  reporter for Jest/Vitest/Mocha, so pinning TAP here is what keeps the
  fixture's baseline/after-fix runs parseable across Node versions instead
  of silently falling back to the degraded aggregate-count parser.
