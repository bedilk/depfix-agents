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

# Safety: never push to dependency_check (origin). Only push to agents remote.
if git remote get-url --push origin 2>/dev/null | grep -qv DISABLED; then
  git remote set-url --push origin DISABLED_DO_NOT_PUSH_TO_DEPENDENCY_CHECK
fi

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

# --- Step 5: Check CI status ---
SHA=$(git rev-parse HEAD)
log "Pushed $SHA — checking CI on GitHub Actions..."
echo "$(date_iso) $SHA $ROLE push-ok" >> .local/push-history.log

# Wait up to 10 min for CI to start and complete
CI_STATUS="unknown"
for attempt in $(seq 1 20); do
  sleep 30
  CI_STATUS=$(gh run list --commit "$SHA" --json conclusion,status --jq '.[0] | if .status == "completed" then .conclusion else .status end' 2>/dev/null || echo "unknown")
  log "CI check $attempt/20: $CI_STATUS"
  if [[ "$CI_STATUS" == "success" ]]; then
    log "CI PASSED for $SHA"
    echo "$(date_iso) $SHA $ROLE ci-pass" >> .local/push-history.log
    break
  elif [[ "$CI_STATUS" == "failure" || "$CI_STATUS" == "cancelled" ]]; then
    log "CI FAILED ($CI_STATUS) for $SHA — marking gate as failed"
    echo "$(date_iso) $SHA $ROLE ci-fail:$CI_STATUS" >> .local/push-history.log
    # Show failed steps
    gh run list --commit "$SHA" --json databaseId --jq '.[0].databaseId' 2>/dev/null | xargs -I{} gh run view {} --log-failed 2>/dev/null | tail -30 | tee -a "$LOG" || true
    exit 3
  fi
  # Keep going if still in_progress / queued
done

if [[ "$CI_STATUS" != "success" ]]; then
  log "CI did not complete in 10 min (status: $CI_STATUS) — continuing anyway"
  echo "$(date_iso) $SHA $ROLE ci-timeout:$CI_STATUS" >> .local/push-history.log
fi

exit 0
