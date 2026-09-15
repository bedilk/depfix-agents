# depfix — Dependency Fix Agent

AI-powered tool that automatically fixes breaking dependency changes in your codebase.

When a package ships a breaking change, `depfix`:

1. **Detects** usages of the affected API across your codebase
2. **Generates** fixes using Google Gemini (or a local Ollama model)
3. **Validates** the fixes for syntax correctness (via Node.js)
4. **Verifies** kept fixes by running the target repo's own test suite before/after (needs npm; `depfix fix` only)
5. **Outputs** unified diffs that can be applied as patches

## Requirements

- Python **3.11+**
- Node.js **20+** (used to syntax-check generated JS/TS fixes)
- npm (used by `depfix fix` to install a target repo's dependencies and run its real test
  suite when verifying a fix; not needed for `depfix scan`/`depfix run`'s syntax-only checks)
- A Google Generative AI API key ([get one here](https://aistudio.google.com/app/apikey)), or a
  local [Ollama](https://ollama.com/) install for `--llm-provider ollama`

## Quick start

```bash
# Clone
git clone <repo-url>
cd dependency-fix-agent

# Create a venv and install (editable, with dev extras)
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY=...

# Run the CLI
depfix --help
depfix run --codebase ./tests/fixtures/openai_v3_project --change-file my_change.json --show-diffs
```

## Watching providers

`depfix watch` polls every feed declared in `providers.yaml` — npm dist-tags,
GitHub releases, and OpenAPI specs today; changelogs and RSS are declared but
not yet implemented — and records changes to Postgres. Like the old poller it
replaces, it's designed to be driven by cron or systemd: one shot per
invocation, no in-process scheduler.

```bash
# 1. Bring up Postgres (Redis too, but the watcher only needs Postgres).
docker compose up -d postgres

# 2. Edit the provider/feed list.
$EDITOR providers.yaml

# 3. Run a watch pass.
depfix watch --once

# Only watch specific providers, or preview without writing to the DB.
depfix watch --once --provider stripe --provider openai
depfix watch --once --dry-run --show-changes

# 4. See what changed.
docker compose exec postgres psql -U depfix -d depfix \
    -c "SELECT provider_id, feed_key, old_token, new_token, severity FROM change_event ORDER BY detected_at DESC LIMIT 20;"
docker compose exec postgres psql -U depfix -d depfix \
    -c "SELECT kind, severity, subject FROM spec_change WHERE severity = 'breaking' ORDER BY id DESC LIMIT 20;"
```

Schedule the watcher with a crontab entry:

```cron
*/15 * * * * cd /srv/depfix && /srv/depfix/.venv/bin/depfix watch --once >> /var/log/depfix.log 2>&1
```

## Classifying detected changes

`depfix classify` turns unclassified `change_event` rows (written by
`depfix watch`) into structured `BreakingChange` rows. Events carrying a
structural OpenAPI diff (`spec_changes`) are classified deterministically —
no LLM, no hallucination risk, always `confidence=1.0`. Events with only
prose release notes are classified by an LLM, gated behind a verbatim-quote
anti-hallucination check; a proposed change is dropped outright if its
`evidence` can't be found in the source text.

```bash
depfix classify                 # classify pending events (LLM if configured)
depfix classify --no-llm        # only the deterministic spec-diff path
depfix classify --limit 50      # process at most 50 events this run
depfix classify --output-dir output/changes  # export each newly created row as <ID>.json
```

The database row is the source of truth. The JSON export is an audit/replay
artifact, not a file that must be placed in the repository being fixed. Use
the printed ID with `--from-event <ID>` for normal plan/apply runs.

For deterministic end-to-end testing without waiting for a real upstream
release, [examples/seed-providers.yaml](examples/seed-providers.yaml) declares
explicit `fixture_change` feeds. They are test-only inputs to `watch`, kept in
Depfix rather than in the target repository; do not add them to production
`providers.yaml`.

`depfix run` can then consume a classified row directly:

```bash
depfix run --codebase ./my-app --from-event 42 --show-diffs
```

## Evaluating the pipeline

`depfix eval` scores the classifier and fixer against a YAML corpus
(`src/depfix/evals/corpus/`). Each case is tagged `verified: true|false` —
unverified cases still run but are reported separately, so a passing eval
never silently counts a case nobody has actually confirmed against a live
model.

```bash
depfix eval --no-llm                     # deterministic spec_diff cases only (CI-safe)
depfix eval                              # full corpus, including LLM-backed cases
depfix eval --category spec_diff         # just one category
depfix eval --save report.json           # persist a JSON report
depfix eval --compare report.json        # fail on any case that regressed pass->fail
```

## Scanning a repo for call sites

`depfix scan` finds usages of a provider's SDK across a codebase — either a
local directory or a remote repo cloned on the fly via a GitHub App
installation — and reports/persists the call sites it finds, with a
confidence level (`HIGH`/`MEDIUM`/`LOW`) reflecting how directly each usage
traces back to the SDK import.

```bash
# Scan a local checkout for every OpenAI SDK symbol.
depfix scan --path ./my-app --provider openai --no-save

# This equivalent legacy-friendly form also works. --old-api narrows the
# report to a particular old API namespace.
depfix scan --repo ./my-app --package openai --old-api openai.Completion --no-save

# Narrow the scan to the symbols touched by one classified breaking change.
depfix scan --path ./my-app --provider openai --from-event 42

# Scan a remote repo by cloning it via the GitHub App (needs GITHUB_APP_ID +
# a private key configured -- see below).
depfix scan --repo acme/widgets --provider stripe

# See what repos the App installation(s) can see.
depfix repos
```

To scan remote repos, register a GitHub App with `contents: read` permission,
install it on the target repo(s)/org, and set:

| Variable | Purpose |
| --- | --- |
| `GITHUB_APP_ID` | Numeric GitHub App ID |
| `GITHUB_APP_PRIVATE_KEY` | PEM private key, inline (wins over the path below if both are set) |
| `GITHUB_APP_PRIVATE_KEY_PATH` | Path to a `.pem` file with the private key |
| `CLONE_DIR` | Base directory for shallow clones (defaults to the system temp dir) |
| `CLONE_MAX_REPO_MB` | Reject a clone once its working tree exceeds this size (default `500`) |

`depfix scan` mints a short-lived, least-privilege installation token per
scan and shallow-clones (`--depth=1`) into a temp directory that's removed
after the scan regardless of outcome.

### Safe GitHub App test repositories

Install the App only on repositories you own or administer. For public
upstream projects, fork them into your own GitHub account or organization
first; an App installation does not grant access to somebody else's
repository. Start with `depfix scan --no-save` and use the pipeline only in a
dedicated test fork containing an explicit `.depfix.yml`.

The default provider set covers 20 active TypeScript/JavaScript SDKs. Useful
upstream fork candidates are [OpenAI's Node SDK](https://github.com/openai/openai-node),
[Anthropic's TypeScript SDK](https://github.com/anthropics/anthropic-sdk-typescript),
[Supabase JS](https://github.com/supabase/supabase-js), [Vercel AI SDK](https://github.com/vercel/ai),
and [Sentry JavaScript](https://github.com/getsentry/sentry-javascript). These
forks are useful for safe scan experiments; for end-to-end fix and PR tests,
use a small repository you control with deliberately outdated SDK call sites.

## Fixing breaking changes

`depfix fix` scans for call sites, generates a fix for each one, writes kept
edits to a disposable copy of the checkout (a local `--path` is never
mutated in place), and -- unless `--no-verify` is passed -- installs the
target repo's own dependencies and runs its real test suite before and after
each edit to decide whether to keep or revert it.

```bash
# Fix a local checkout, printing diffs instead of just a summary.
depfix fix --path ./my-app --provider openai --change-file my_change.json --show-diffs

# Fix straight from a classified breaking_change row (see `depfix classify`).
depfix fix --path ./my-app --provider openai --from-event 42

# Fix a remote repo cloned via the GitHub App, writing .patch files locally.
depfix fix --repo acme/widgets --provider openai --from-event 42 --output ./patches

# Skip real test-suite verification (e.g. no npm on PATH, or the repo has no tests).
depfix fix --path ./my-app --provider openai --change-file my_change.json --no-verify

# Use a local Ollama model instead of Gemini.
depfix fix --path ./my-app --provider openai --change-file my_change.json \
    --llm-provider ollama --ollama-model qwen2.5-coder:7b

# Use a larger local coding model (roughly a 19 GB download).
ollama pull qwen3-coder:30b
LLM_PROVIDER=ollama OLLAMA_MODEL=qwen3-coder:30b depfix fix --path ./my-app \
    --provider openai --change-file my_change.json

# Retry SUSPECT/REVERTED edits up to 3 times, feeding each concrete
# failure (syntax error or failing test) back to the LLM.
depfix fix --path ./my-app --provider openai --change-file my_change.json --max-retries 3

# Disable the retry loop entirely.
depfix fix --path ./my-app --provider openai --change-file my_change.json --no-retry

# Fix a remote repo and open a PR with the KEPT (test-confirmed) edits.
depfix fix --repo acme/widgets --provider openai --from-event 42 --open-pr

# Open the PR as a draft, against a specific base branch.
depfix fix --repo acme/widgets --provider openai --from-event 42 \
    --open-pr --draft-pr --base-branch develop
```

Each edit ends up with a verdict: `KEPT` (written, and confirmed clean or
unverified), `REVERTED` (written, then rolled back because verification
attributed a new test failure to it), `SUSPECT` (written, but not
confirmed clean -- either it failed the syntax/sanity check, or
verification couldn't confirm or deny it: no test script, install failed,
or a test-output format it couldn't parse), or `SKIPPED` (never written --
e.g. fix generation failed, or the fix was identical to the original).
Unless `--no-save` is passed, the run (and every edit + baseline/after-fix
test result) is persisted to the `fix_run`/`file_fix`/`test_run` tables.

When verification is enabled, `SUSPECT`/`REVERTED` edits are retried up to
`--max-retries` times (default: `RETRY_MAX_ROUNDS` env, else 2), each round
feeding the concrete syntax error or attributed failing test back to the
LLM before re-verifying the full batch; `--no-retry` disables this
regardless of `--max-retries`.

`--open-pr` (remote repos only, and only once verification has actually
run) pushes the `KEPT` edits to a deterministic branch
(`depfix/<dedupe-key>`) via the GitHub Git Data API and opens a PR whose
body links back to the breaking change's description, migration guide,
and evidence. Re-running with the same breaking change reuses the same
branch and PR rather than piling up duplicates. `--draft-pr` opens it as a
draft; `--base-branch` overrides the repo's default branch. Unless
`--no-save` is passed, the PR is also persisted to the `pull_request`
table.

## Running the fleet orchestrator

For the safe beta path—dry run, full verification without a PR, draft PRs,
then live—see [repository onboarding](docs/onboarding.md).

## Terraform-style workflow

Use the following workflow for an explicit, reviewable run.  `init` is
read-only: it validates the GitHub App can read the selected repository,
validates its `.depfix.yml`, dry-polls provider feeds without saving events,
and can scan a supplied known breaking change without calling an LLM. `plan`
runs the actual scan -> generate -> verify workflow in a disposable checkout,
but writes no database state, branch, or PR. When it has verified committable
edits, it writes an immutable plan artifact containing the exact diffs and base
commit SHA. `apply --plan-file` consumes that exact artifact: it does not call
the LLM again and refuses a stale repository/file base.

```bash
# Check one opted-in repository and scan a known migration without changing state.
depfix init acme/widgets --provider openai --change-file changes/openai-v3-to-v4.json

# Review the verified proposal. This cannot create a PR. It prints a path
# such as output/plans/<run-id>-<change>.json.
depfix plan acme/widgets --from-event 42 \
  --llm-provider ollama --ollama-model qwen2.5-coder:7b

# Create a PR from precisely that reviewed artifact. No LLM call occurs.
depfix apply acme/widgets --from-event 42 \
  --plan-file output/plans/<run-id>-<change>.json
```

Use `--force` only for intentional controlled retries (for example a seed
fixture that is in retry cooldown). A plan with no artifact reports the
per-file terminal verdict, such as `reverted`, `suspect`, or `skipped`, and
must be corrected/replanned before it can be applied.

`apply` still honours the target repository's `.depfix.yml`: `enabled`,
provider/path filters, verification policy, and `open_pr`/`draft_pr` settings
remain safety gates.  `pipeline` remains available for unattended fleet/cron
runs; `plan` and `apply` are its human-operated counterparts.

`depfix pipeline` is the Week 6 unattended entrypoint: it runs the same
scan -> fix -> verify -> PR pipeline as `depfix fix`, but across every repo
in a batch, gated by each repo's own opt-in `.depfix.yml` (copy
[`.depfix.yml.example`](.depfix.yml.example) into a target repo's root to
enable it) and an idempotency ledger (`change_attempt` table) so cron-driven
reruns never reopen a PR or reprocess an already-terminal outcome.

```bash
# Process every repo visible to the configured GitHub App installation(s),
# against every classified breaking_change row in the database.
depfix pipeline

# Narrow to specific repos and/or a specific provider.
depfix pipeline --repo acme/widgets --repo acme/gizmos --provider openai

# Narrow to specific breaking changes instead of the full classified backlog.
depfix pipeline --from-event 42 --from-event 43

# Bypass bookkeeping skips (already-terminal, max attempts, cooldown, max
# open PRs, max changes per run) for a manual re-run -- a repo's own
# .depfix.yml (enabled/ignore) is never bypassed, even with --force.
depfix pipeline --force
```

A repo with no `.depfix.yml` at all is skipped entirely
(`no_repo_config`) -- the orchestrator never acts on a repo that hasn't
explicitly opted in. Within an opted-in repo, each `(repo, change)` pair is
independently gated by `orchestrator.policy.decide()`: tenant instructions
(`enabled: false`, `ignore`) are checked first and are never bypassable;
then capability (`providers` filter, known provider ids); then bookkeeping
(already-terminal ledger status, max attempts, retry cooldown, max open
PRs, max changes per run), which *is* bypassable with `--force`. One bad
repo, or one bad change within a repo, never aborts the rest of the batch.

## Common tasks

```bash
make install-dev         # install + dev extras + pre-commit hooks
make test                # run unit tests (no LLM calls)
make test-integration    # end-to-end tests (needs GOOGLE_API_KEY)
make lint                # ruff check
make format              # ruff format
make typecheck           # mypy on src/
make security            # bandit on src/
make run ARGS="--help"   # depfix --help
make eval                 # depfix eval --no-llm (CI gate)
make eval-full            # depfix eval with LLM-backed cases included
make eval-compare         # depfix eval --compare against the last saved report
make classify             # depfix classify
make scan ARGS="--path ./my-app --provider openai --no-save"
make fix ARGS="--path ./my-app --provider openai --change-file change.json"
make repos                 # depfix repos
make pipeline ARGS="--repo acme/widgets --force"  # depfix pipeline
make docker-up            # postgres + redis + app via docker compose
```

## Project layout

```
dependency-fix-agent/
├── src/depfix/               # main package
│   ├── core/                 # models + agent orchestrator
│   ├── scanners/             # codebase scanning (manifest + call-site + repo orchestration)
│   ├── fixers/               # LLM-based fix generation (Gemini, Ollama)
│   ├── validators/           # syntax / semantic validation
│   ├── apply/                 # WorkspaceEditor -- transactional in-place file edits
│   ├── verify/                 # sandboxed install/test-run verification of a candidate fix
│   ├── retry/                 # bounded SUSPECT/REVERTED retry loop, fed by verify's attribution
│   ├── sources/               # change feeds (npm dist-tag, GitHub, OpenAPI diff)
│   ├── classify/              # ChangeEvent -> BreakingChange (deterministic + LLM)
│   ├── evals/                 # YAML corpus + scoring harness (`depfix eval`)
│   ├── gh/                   # GitHub App auth, branch/commit + PR creation (Git Data API)
│   ├── clone/                 # shallow-clone / local-copy checkout service
│   ├── repoconfig/            # per-repo opt-in `.depfix.yml` loader/models
│   ├── orchestrator/          # Week 6 fleet orchestrator: policy + runner (`depfix pipeline`)
│   ├── api/                  # (placeholder) HTTP surface
│   ├── workers/              # (placeholder) background jobs
│   ├── registry/             # npm registry HTTP client
│   ├── storage/              # SQLAlchemy schema + session factory + fix_store/attempt_store
│   ├── watcher/               # one-shot feed poller (`depfix watch`)
│   ├── config.py             # Pydantic Settings — env-driven config
│   └── cli.py                # `depfix` entrypoint
├── tests/
│   ├── unit/                            # fast, no external services
│   ├── integration/                     # test_fix_pipeline.py needs node+npm; the rest hit a real LLM API (opt-in via marker)
│   ├── fixtures/openai_v3_project       # sample JS codebase (openai-node v3), for `depfix run`
│   └── fixtures/openai_v3_verifiable    # self-contained shim + real node:test suite, for verification tests
├── pyproject.toml            # PEP 621 metadata, ruff/mypy/pytest config
├── requirements.txt          # runtime deps
├── requirements-dev.txt      # dev/test deps
├── Dockerfile
├── docker-compose.yml        # postgres + redis + app
├── Makefile
└── .github/workflows/ci.yml  # lint → test → docker build
```

## Configuration

All configuration is read from environment variables (or a local `.env` file). See
[`.env.example`](.env.example) for the full list. Key variables:

| Variable          | Default              | Purpose                                  |
| ----------------- | -------------------- | ---------------------------------------- |
| `GOOGLE_API_KEY`  | *(required)*         | Google Generative AI credential          |
| `GEMINI_MODEL`    | `gemini-2.5-flash`   | Which Gemini model to call               |
| `DATABASE_URL`    | in-memory / unset    | Postgres DSN (watcher state, future workers) |
| `REDIS_URL`       | unset                | Redis URL (used by future workers)       |
| `NPM_REGISTRY_URL`| `registry.npmjs.org` | npm registry base URL (override for tests) |
| `CLASSIFY_MIN_CONFIDENCE` | `0.5`        | Drop LLM-derived (release-notes) changes below this confidence |
| `EVAL_CORPUS_DIR` | packaged corpus      | Directory of `*.yaml` eval corpus files  |
| `EVAL_RESULTS_DIR`| `./.depfix-cache/eval-results` | Where `depfix eval --save` writes JSON reports |
| `GITHUB_APP_ID`   | unset                | GitHub App ID for `depfix scan --repo`/`depfix repos` |
| `GITHUB_APP_PRIVATE_KEY` / `GITHUB_APP_PRIVATE_KEY_PATH` | unset | GitHub App private key, inline or by path |
| `CLONE_DIR`       | system temp dir      | Base directory for shallow clones        |
| `CLONE_MAX_REPO_MB` | `500`               | Reject a clone once its working tree exceeds this size |
| `SCAN_MAX_FILES`  | `20000`              | Hard cap on files scanned per repo       |
| `FIX_VALIDATE_SYNTAX` | `true`           | Run syntax/sanity checks before writing an edit to disk |
| `VERIFY_ENABLED`  | `true`               | Whether `depfix fix` runs the repo's own test suite to confirm each edit |
| `VERIFY_INSTALL_TIMEOUT` | `300`         | Wall-clock cap (seconds) for the dependency install step |
| `VERIFY_TEST_TIMEOUT` | `300`            | Wall-clock cap (seconds) for one baseline or after-fix test run |
| `VERIFY_IGNORE_SCRIPTS` | `true`         | Pass `--ignore-scripts` to the install command |
| `VERIFY_MAX_OUTPUT_BYTES` | `2000000`    | Truncate captured install/test output past this size |
| `RETRY_MAX_ROUNDS` | `2`                 | Bounded re-attempts for SUSPECT/REVERTED edits (`depfix fix --max-retries`/`--no-retry`) |
| `REPO_CONFIG_FILENAME` | `.depfix.yml`   | Per-repo opt-in pipeline config file the orchestrator looks for at the repo root |
| `PIPELINE_REQUIRE_CONFIG_FILE` | `true`  | Refuse to touch a repo with no `REPO_CONFIG_FILENAME` at all |
| `PIPELINE_MAX_OPEN_PRS` | `5`            | Per-repo cap on simultaneously open depfix-authored PRs |
| `PIPELINE_MAX_ATTEMPTS` | `3`            | Per-(repo, change) cap on non-terminal orchestrator attempts before giving up |
| `PIPELINE_RETRY_COOLDOWN_HOURS` | `6.0`  | Minimum time between two orchestrator attempts at the same (repo, change) |
| `PIPELINE_MAX_CHANGES_PER_REPO` | `3`    | Hard cap on distinct breaking changes processed per repo per `depfix pipeline` run |
| `LOG_LEVEL`       | `INFO`               | Root logging level                       |
| `SENTRY_DSN`      | unset                | Sentry DSN for error reporting           |

## Testing

Unit tests are pure-Python and never call out to the network:

```bash
pytest tests/unit -m "not integration and not e2e"
```

Integration tests exercise the full pipeline against the real Gemini API. They are
skipped automatically unless `GOOGLE_API_KEY` is set:

```bash
GOOGLE_API_KEY=... pytest tests/integration -m integration
```

`tests/integration/test_fix_pipeline.py` is the exception: it runs `FixPipeline`
against a real `Verifier` (real `npm install` + `node --test`) but never calls an
LLM, so it's deliberately unmarked and runs under plain `pytest`/`make test` --
skipped automatically unless both `node` and `npm` are on `PATH`.

## Docker

```bash
docker compose up -d --build
docker compose exec app depfix --help
```

The compose stack starts Postgres and Redis alongside the app container. The image
uses a multi-stage build with a non-root runtime user and includes Node.js + npm --
required not just for the JS syntax validator, but for `depfix fix`'s verification
step, which installs a target repo's real dependencies and runs its real test suite.
Debian's `nodejs` apt package doesn't bundle npm (and its separate `npm` package pulls
in ~300 unrelated JS library packages), so the runtime stage installs the upstream
Node.js binary tarball instead.

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and PR to `main`:

1. **lint** — `ruff check`, `ruff format --check`, `mypy`, `bandit`
2. **test** — `pytest` on Python 3.11 and 3.12 with coverage
3. **eval** — `depfix eval --no-llm --fail-under 1.0`, gating on the deterministic
   spec-diff corpus (LLM-backed cases are skipped, not failed, without an API key)
4. **build-docker** — smoke build the Dockerfile (waits on both `test` and `eval`)

Coverage XML and the eval JSON report are uploaded as build artifacts.

## Design decisions

- **Package name** — `depfix` (short, lowercase, unique on PyPI)
- **Layout** — `src/`-layout to avoid accidental imports of the wrong copy during dev
- **Dependency management** — `pip` + `requirements*.txt` (no Poetry/PDM)
- **Config** — Pydantic Settings, single `get_settings()` factory (`lru_cache`d)
- **Model default** — `gemini-2.5-flash` (1.5 family is no longer available on new API keys)
- **Linter/formatter** — `ruff` replaces flake8, black, isort
- **Test runner** — `pytest`, with markers `integration` and `e2e` to gate live calls
- **No hosted deploy target yet** — image builds in CI but is not pushed anywhere

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT.
