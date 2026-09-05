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
