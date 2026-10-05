#!/usr/bin/env bash
# Commit gate: verify tests pass, push to remote, check CI.
# Called by agents after every code change.
#
# Usage:
#   bash scripts/commit-gate.sh              # run tests, push, report
#   bash scripts/commit-gate.sh --test-only  # just run tests, don't push
#
# Exit codes:
#   0 = all tests pass (and pushed if not --test-only)
#   1 = tests failed
#   2 = push failed
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

# macOS compat
date_iso() { if command -v gdate >/dev/null; then gdate -Iseconds; else date +%Y-%m-%dT%H:%M:%S%z; fi; }

ROLE="${AGENT_ROLE:-unknown}"
LOG=".local/commit-gate.log"
mkdir -p .local

log() { printf '[%s] %s: %s\n' "$(date_iso)" "$ROLE" "$1" | tee -a "$LOG"; }

TEST_ONLY=false
[[ "${1:-}" == "--test-only" ]] && TEST_ONLY=true

# --- Step 1: Run tests ---
log "Running make test..."
if make test > .local/gate-test.log 2>&1; then
  test_result=$(grep -cP '(passed|PASSED)' .local/gate-test.log || echo "?")
  log "make test PASSED ($test_result)"
else
  log "make test FAILED — see .local/gate-test.log"
  tail -20 .local/gate-test.log | tee -a "$LOG"
  exit 1
fi

# --- Step 2: Run lint ---
log "Running make lint..."
if make lint > .local/gate-lint.log 2>&1; then
  log "make lint PASSED"
else
  log "make lint FAILED — see .local/gate-lint.log"
  tail -10 .local/gate-lint.log | tee -a "$LOG"
  exit 1
fi

# --- Step 3: Run typecheck ---
log "Running make typecheck..."
if make typecheck > .local/gate-typecheck.log 2>&1; then
  log "make typecheck PASSED"
else
  log "make typecheck FAILED — see .local/gate-typecheck.log"
  tail -10 .local/gate-typecheck.log | tee -a "$LOG"
  exit 1
fi

log "All local checks passed."

if $TEST_ONLY; then
  exit 0
fi

# --- Step 4: Push to remote ---
log "Pushing to remote (agents branch)..."
BRANCH=$(git rev-parse --abbrev-ref HEAD)

if flock .local/git.lock bash -c "git push agents $BRANCH" > .local/gate-push.log 2>&1; then
  log "Push succeeded: $BRANCH -> agents/$BRANCH"
else
  log "Push FAILED — see .local/gate-push.log"
  tail -5 .local/gate-push.log | tee -a "$LOG"
  exit 2
fi

# --- Step 5: Report CI status (non-blocking) ---
# CI runs on GitHub Actions. We log the push SHA so it can be checked later.
SHA=$(git rev-parse HEAD)
log "Pushed $SHA — CI will run on GitHub Actions"
echo "$(date_iso) $SHA $ROLE push-ok" >> .local/push-history.log

exit 0
