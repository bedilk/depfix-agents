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
```

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
│   ├── sources/               # change feeds (npm dist-tag, GitHub, OpenAPI diff)
│   ├── classify/              # ChangeEvent -> BreakingChange (deterministic + LLM)
│   ├── evals/                 # YAML corpus + scoring harness (`depfix eval`)
│   ├── gh/                   # GitHub App auth (JWT + installation tokens)
│   ├── clone/                 # shallow-clone / local-copy checkout service
│   ├── api/                  # (placeholder) HTTP surface
│   ├── workers/              # (placeholder) background jobs
│   ├── registry/             # npm registry HTTP client
│   ├── storage/              # SQLAlchemy schema + session factory + fix_store
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
