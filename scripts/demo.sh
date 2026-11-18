#!/usr/bin/env bash
# Demo run for screen recordings: init -> scan -> plan in one go, with trimmed output.
# Then run `depfix apply` yourself and open the PR.
#
# Usage (from the repo root, venv active):
#   bash scripts/demo.sh [OWNER/REPO] [PROVIDER]
#   bash scripts/demo.sh bedilk/depfix-test-sentry-v6-app sentry
set -euo pipefail

REPO=${1:-bedilk/depfix-test-sentry-v6-app}
PROVIDER=${2:-sentry}
PLAN_DIR=${PLAN_DIR:-.depfix/plans}
export COLUMNS=${COLUMNS:-120}
export FORCE_COLOR=1

step() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }

step "depfix init"
depfix --log-level ERROR init --keep-state 2>&1 | tail -n 3

step "depfix scan --repo $REPO --provider $PROVIDER"
depfix --log-level ERROR scan --repo "$REPO" --provider "$PROVIDER" 2>&1 \
  | sed -n '/Call Sites/,/files scanned/p; /Dependency Drift Summary/,/└/p'

# Start from fresh plans so apply only sees what this run produced
rm -f "$PLAN_DIR/${REPO/\//__}__"*.json

step "depfix plan $REPO --provider $PROVIDER"
depfix --log-level ERROR plan "$REPO" --provider "$PROVIDER" --force 2>&1 \
  | grep -E "would process|PR planned|PR\(s\) planned|Apply with" || echo "No PR planned."

printf '\n\033[1;32mNext:\033[0m depfix apply %s --provider %s --force\n' "$REPO" "$PROVIDER"
