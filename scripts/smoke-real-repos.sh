#!/usr/bin/env bash
# Smoke test depfix scan against 5-6 real third-party repos.
# Picks repos randomly from real-repos.txt and runs scan (read-only, no PRs).
#
# Usage:
#   bash scripts/smoke-real-repos.sh           # pick 6 random repos, scan each
#   bash scripts/smoke-real-repos.sh --all     # scan all repos in real-repos.txt
#   bash scripts/smoke-real-repos.sh 3         # scan 3 random repos
#
# Output: research/smoke-<timestamp>.md with results table
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

# macOS compat
timeout() { if command -v gtimeout >/dev/null; then gtimeout "$@"; else command timeout "$@"; fi; }
date_iso() { if command -v gdate >/dev/null; then gdate -Iseconds; else date +%Y-%m-%dT%H:%M:%S%z; fi; }

REPOS_FILE="real-repos.txt"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT_FILE="research/smoke-${TIMESTAMP}.md"
LATEST_LINK="research/smoke-latest.md"
COUNT="${1:-6}"
mkdir -p research .local

if [[ ! -f "$REPOS_FILE" ]]; then
  echo "ERROR: $REPOS_FILE not found"
  exit 1
fi

# Parse real-repos.txt: skip comments and blank lines (bash 3.2 compat, no mapfile)
ALL_REPOS=()
while IFS= read -r line; do
  ALL_REPOS+=("$line")
done < <(grep -v '^\s*#' "$REPOS_FILE" | grep -v '^\s*$')

if [[ "$COUNT" == "--all" ]]; then
  SELECTED=("${ALL_REPOS[@]}")
  COUNT=${#SELECTED[@]}
else
  # Shuffle and pick $COUNT (bash 3.2 compat)
  SELECTED=()
  SHUFFLED=()
  while IFS= read -r line; do
    SHUFFLED+=("$line")
  done < <(printf '%s\n' "${ALL_REPOS[@]}" | sort -R)
  for i in $(seq 0 $(( COUNT - 1 ))); do
    [[ $i -ge ${#SHUFFLED[@]} ]] && break
    SELECTED+=("${SHUFFLED[$i]}")
  done
  COUNT=${#SELECTED[@]}
fi

echo "Smoke testing $COUNT repos -> $OUTPUT_FILE"
echo ""

{
  echo "# Smoke Test — $(date_iso)"
  echo ""
  echo "Repos tested: $COUNT (from real-repos.txt)"
  echo ""
  echo "| # | Provider | Repo | Files Scanned | Call Sites | Actionable | Exit | Time |"
  echo "|---|---|---|---|---|---|---|---|"
} > "$OUTPUT_FILE"

PASS=0
FAIL=0
idx=0

for entry in "${SELECTED[@]}"; do
  idx=$((idx + 1))
  provider="${entry%%:*}"
  repo="${entry#*:}"

  echo "[$idx/$COUNT] $provider : $repo"

  start_ts=$(date +%s)
  scan_log=".local/smoke-${provider}-$(echo "$repo" | tr '/' '-').log"

  # Clone publicly, scan with --path (no GitHub App required)
  tmpdir=$(mktemp -d "${TMPDIR:-/tmp}/smoke-XXXXXX")
  clone_log="$tmpdir/clone.log"

  if timeout 3m git clone --depth=1 --quiet "https://github.com/$repo.git" "$tmpdir/repo" \
       > "$clone_log" 2>&1; then
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
  end_ts=$(date +%s)
  elapsed=$(( end_ts - start_ts ))

  # Extract metrics from log (macOS grep -E compat, no -P)
  files=$(grep -oE 'files scanned: [0-9]+' "$scan_log" 2>/dev/null | grep -oE '[0-9]+' | tail -1 || true)
  sites=$(grep -oE 'call sites: [0-9]+' "$scan_log" 2>/dev/null | grep -oE '[0-9]+' | tail -1 || true)
  actionable=$(grep -oE '[0-9]+ actionable' "$scan_log" 2>/dev/null | grep -oE '^[0-9]+' | tail -1 || true)

  [ -z "$files" ] && files="?"
  [ -z "$sites" ] && sites="?"
  [ -z "$actionable" ] && actionable="?"

  # depfix scan exits 1 when its built-in eval corpus fails the pass-rate check.
  # For smoke purposes, success = scanner reached the repo and scanned ≥1 file.
  if [[ "$files" =~ ^[0-9]+$ ]] && [[ "$files" -gt 0 ]]; then
    status="PASS"
    PASS=$((PASS + 1))
  else
    status="FAIL($exit_code)"
    FAIL=$((FAIL + 1))
  fi

  echo "  -> files=$files sites=$sites actionable=$actionable ${elapsed}s $status"

  echo "| $idx | $provider | $repo | $files | $sites | $actionable | $status | ${elapsed}s |" >> "$OUTPUT_FILE"
done

{
  echo ""
  echo "## Summary"
  echo ""
  echo "- **Passed:** $PASS / $COUNT"
  echo "- **Failed:** $FAIL / $COUNT"
  echo "- **Timestamp:** $(date_iso)"
  echo ""
  if [[ $FAIL -gt 0 ]]; then
    echo "### Failures"
    echo ""
    echo "Check logs in \`.local/smoke-*.log\` for details."
  fi
} >> "$OUTPUT_FILE"

# Update latest symlink
ln -sf "$(basename "$OUTPUT_FILE")" "$LATEST_LINK"

echo ""
echo "Results: $OUTPUT_FILE"
echo "  $PASS passed, $FAIL failed out of $COUNT"

# Log for the 4-hour cycle tracker
echo "smoke $(date_iso) passed=$PASS failed=$FAIL total=$COUNT" >> .local/smoke-history.log
