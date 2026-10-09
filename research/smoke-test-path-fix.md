# Smoke Test Fix: Use `--path` Mode for Public Repos

## Problem

`smoke-real-repos.sh` runs every 4 hours but has been producing 0/N successful scans since
the beginning because every repo in `real-repos.txt` requires the depfix GitHub App to be
installed — even for public repos. The error is:

```
Error: no GitHub App installation found for OptimalBits/bull. Install the App on this
repository (or its owning org) first.
```

This makes the smoke test useless: it always shows 0 files scanned, 0 call sites, 0 actionable.

## Root Cause

`smoke-real-repos.sh` → `test_pipeline.sh` → `depfix scan --repo owner/repo` →
`GitHubAppAuth.resolve_installation_for_repo()` → 404 → `GitHubAppError`.

The `depfix scan --repo` path (cli.py:1707-1718) unconditionally calls
`gh_auth.resolve_installation_for_repo()` even for read-only scan on a public repo.

## The Fix: `--path` mode already exists

`depfix scan` already supports a `--path` flag (cli.py:2546):

```
--path  Local directory to scan instead of cloning
```

When `--path` is used (cli.py:1702-1705), the GitHub App is **never consulted**:

```python
if args.path:
    owner, name = "local", Path(args.path).name
    repo_full_name = str(Path(args.path).resolve())
    checkout = clone_service.copy_local(args.path)
    # No gh_auth, no installation lookup, no token
```

So: `git clone --depth=1 https://github.com/<repo>` followed by
`depfix scan --path <tmpdir> --provider <provider>` works on any public repo,
no App required.

## Proposed Fix: Update `smoke-real-repos.sh`

Replace the `test_pipeline.sh` delegation inside `smoke-real-repos.sh` (lines 79-84)
with a direct clone-and-scan approach.

### Changes to `scripts/smoke-real-repos.sh`

Change the per-repo scan block (lines 70-108) from:

```bash
# Run scan via test_pipeline.sh (handles init, clone, scan)
if timeout 10m bash scripts/test_pipeline.sh "$entry" > "$scan_log" 2>&1; then
  exit_code=0
else
  exit_code=$?
fi
```

To:

```bash
# Clone publicly, scan with --path (no GitHub App required)
tmpdir=$(mktemp -d "${TMPDIR:-/tmp}/smoke-XXXXXX")
clone_log="$tmpdir/clone.log"

if timeout 3m git clone --depth=1 --quiet "https://github.com/$repo.git" "$tmpdir/repo" \
     > "$clone_log" 2>&1; then
  depfix init --offline --keep-state >> "$scan_log" 2>&1 || true
  if timeout 10m depfix scan --path "$tmpdir/repo" --provider "$provider" \
       > "$scan_log" 2>&1; then
    exit_code=0
  else
    exit_code=$?
  fi
else
  exit_code=$?
  echo "git clone failed: $(cat "$clone_log")" >> "$scan_log"
fi
rm -rf "$tmpdir"
```

### Why This Works

1. `git clone --depth=1 https://github.com/...` — HTTPS, no auth, works on any public repo.
2. `depfix scan --path <dir>` — reads local files, no GitHub API call at all.
3. The scan result (call sites, files scanned) is identical to the `--repo` path because
   `copy_local()` and `clone()` both produce the same working tree layout.

### What Is Lost

- **plan/apply phases**: `test_pipeline.sh` also runs `depfix plan` and `depfix apply`.
  The smoke test does not need these (it's scan health validation, not full pipeline).
  The current smoke test already doesn't run plan/apply — it only extracts scan metrics.
- **No version drift detection** in the smoke scan: `scan --path` doesn't know the repo's
  remote identity, so it won't look up the provider's latest version against the lockfile's
  installed version. This is fine for smoke testing scanner recall.
- **No repo-version-aware exports** (T-15 feature): same reason — `--path` mode sets
  `repo_full_name = str(Path(...).resolve())` which won't match GitHub lookup. Acceptable
  for smoke, since T-15's value is in the plan phase anyway.

## Verification Commands

Test the fix locally:

```bash
# Clone a public repo and scan — should work with no App
git clone --depth=1 https://github.com/OptimalBits/bull /tmp/smoke-bull-test
depfix scan --path /tmp/smoke-bull-test --provider redis
# Expected: files scanned > 0, call sites >= 0, no GitHub App error

git clone --depth=1 https://github.com/langchain-ai/langchainjs /tmp/smoke-langchain-test
depfix scan --path /tmp/smoke-langchain-test --provider langchain
# Expected: files scanned > 0, call sites > 0
```

Expected results based on provider skill files:
- `OptimalBits/bull` + `redis`: bull uses `ioredis`, which imports from `ioredis` (not `redis`).
  Scan will likely find 0 call sites for the `redis` provider but should scan files successfully.
- `langchain-ai/langchainjs` + `langchain`: will find `@langchain/core` + `@langchain/openai` etc.

## Additional: Add `bedilk/` Repos to real-repos.txt

As a belt-and-suspenders addition, add known-working `bedilk/` forks with confirmed call-site
counts (from prior test runs) to `real-repos.txt`. These work in BOTH `--repo` mode (App
installed) and `--path` mode.

```
# --- confirmed bedilk/ forks (App installed, real call-site counts known) ---
mongodb:bedilk/Rocket.Chat       # T-14: 39 call sites, major-gap 6.10→7.7
openai:bedilk/firecrawl          # T-13: 21 call sites
anthropic:bedilk/firecrawl       # T-13: 17 call sites
sentry:bedilk/depfix-test-sentry-v6-app  # T-12: 31 call sites
openai:bedilk/depfix-test-openai-v3-chat  # T-12: 8 call sites
```

These serve as regression benchmarks: if the call-site count drops below the known baseline,
something broke.

## Summary

| Approach | GitHub App required | Works on public repos | Effort |
|---|---|---|---|
| Current (test_pipeline.sh via --repo) | YES | No (fails on 100% of real-repos.txt) | — |
| Proposed (git clone + --path) | NO | Yes, any public repo | ~15 lines in smoke-real-repos.sh |
| Add bedilk/ forks to real-repos.txt | YES (already installed) | bedilk/ only | 5 lines in real-repos.txt |

**Recommendation:** Apply both fixes. The `--path` approach fixes all existing real-repos.txt
entries. The bedilk/ additions provide a regression baseline with known call-site counts.

## Files to Change

| File | Change |
|---|---|
| `scripts/smoke-real-repos.sh` | Replace test_pipeline.sh delegation with git clone + depfix scan --path |
| `real-repos.txt` | Add 5 bedilk/ repos with known call-site baselines |

No changes needed to `depfix` source code — the `--path` mode is already implemented and tested.
