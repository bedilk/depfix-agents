# depfix — Dependency Fix Agent

AI-powered tool that automatically fixes breaking dependency changes in your codebase.

When a package ships a breaking change, `depfix`:

1. **Detects** usages of the affected API across your codebase
2. **Generates** fixes using Google Gemini
3. **Validates** the fixes for syntax correctness (via Node.js)
4. **Outputs** unified diffs that can be applied as patches

## Requirements

- Python **3.11+**
- Node.js **20+** (used to syntax-check generated JS/TS fixes)
- A Google Generative AI API key ([get one here](https://aistudio.google.com/app/apikey))

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
depfix --codebase ./tests/fixtures/test_project --package lodash --show-diffs
```

## Polling npm

`depfix poll` checks every package in `packages.yaml` against the npm registry and
records any version changes to Postgres. It is designed to be driven by cron or
systemd — one shot per invocation, no in-process scheduler.

```bash
# 1. Bring up Postgres (Redis too, but the poller only needs Postgres).
docker compose up -d postgres

# 2. Edit the list of tracked packages.
$EDITOR packages.yaml

# 3. Run a poll.
depfix poll --once

# 4. See what changed.
docker compose exec postgres psql -U depfix -d depfix \
    -c "SELECT * FROM version_event ORDER BY detected_at DESC LIMIT 20;"
```

Schedule the poller with a crontab entry:

```cron
*/15 * * * * cd /srv/depfix && /srv/depfix/.venv/bin/depfix poll --once >> /var/log/depfix.log 2>&1
```

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
make docker-up           # postgres + redis + app via docker compose
```

## Project layout

```
dependency-fix-agent/
├── src/depfix/               # main package
│   ├── core/                 # models + agent orchestrator
│   ├── scanners/             # codebase scanning
│   ├── fixers/               # LLM-based fix generation
│   ├── validators/           # syntax / semantic validation
│   ├── api/                  # (placeholder) HTTP surface
│   ├── workers/              # (placeholder) background jobs
│   ├── registry/             # npm registry HTTP client
│   ├── storage/              # SQLAlchemy schema + session factory
│   ├── pollers/              # one-shot pollers (npm today; more later)
│   ├── config.py             # Pydantic Settings — env-driven config
│   └── cli.py                # `depfix` entrypoint
├── tests/
│   ├── unit/                 # fast, no external services
│   ├── integration/          # hit real LLM API (opt-in via marker)
│   └── fixtures/test_project # sample JS codebase
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
| `DATABASE_URL`    | in-memory / unset    | Postgres DSN (poller state, future workers) |
| `REDIS_URL`       | unset                | Redis URL (used by future workers)       |
| `PACKAGES_FILE`   | `packages.yaml`      | YAML list of npm packages to poll        |
| `NPM_REGISTRY_URL`| `registry.npmjs.org` | npm registry base URL (override for tests) |
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

## Docker

```bash
docker compose up -d --build
docker compose exec app depfix --help
```

The compose stack starts Postgres and Redis alongside the app container. The image
uses a multi-stage build with a non-root runtime user and includes Node.js so the JS
syntax validator works.

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and PR to `main`:

1. **lint** — `ruff check`, `ruff format --check`, `mypy`, `bandit`
2. **test** — `pytest` on Python 3.11 and 3.12 with coverage
3. **build-docker** — smoke build the Dockerfile

Coverage XML is uploaded as a build artifact from the 3.11 job.

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
