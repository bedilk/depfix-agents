#!/usr/bin/env bash
# Human-in-the-loop review for the depfix agent team.
#
# Usage:
#   bash scripts/human-review.sh              # pause agents, generate review summary
#   bash scripts/human-review.sh --resume     # clear stop files, restart all agents
#   bash scripts/human-review.sh --schedule   # install a launchd plist that runs every 4 hours
#
# The review cycle:
#   1. This script pauses all agents (creates .stop files)
#   2. Generates coordination/HUMAN-REVIEW.md with a full status summary
#   3. You review, edit TASKS.json / AGENTS.md as needed
#   4. Run: bash scripts/human-review.sh --resume
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

# macOS compat
date_iso() { if command -v gdate >/dev/null; then gdate -Iseconds; else date +%Y-%m-%dT%H:%M:%S%z; fi; }

ROLES=(principal researcher implementer reviewer tester)
REVIEW_FILE="coordination/HUMAN-REVIEW.md"
PLIST_LABEL="com.depfix.human-review"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"

if [[ "${1:-}" == "--resume" ]]; then
  echo "Resuming all agents..."
  for role in "${ROLES[@]}"; do
    rm -f "coordination/$role.stop"
  done
  bash scripts/run-team.sh
  exit 0
fi

if [[ "${1:-}" == "--schedule" ]]; then
  SCRIPT_ABS="$(cd "$(dirname "$0")" && pwd)/human-review.sh"
  cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${PLIST_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${SCRIPT_ABS}</string>
  </array>
  <key>StartInterval</key>
  <integer>14400</integer>
  <key>StandardOutPath</key>
  <string>${HOME}/.local/human-review-cron.log</string>
  <key>StandardErrorPath</key>
  <string>${HOME}/.local/human-review-cron.log</string>
</dict>
</plist>
PLIST
  launchctl load "$PLIST_PATH" 2>/dev/null || true
  echo "Scheduled: human-review runs every 4 hours."
  echo "  Plist: $PLIST_PATH"
  echo "  To unschedule: launchctl unload $PLIST_PATH && rm $PLIST_PATH"
  exit 0
fi

# --- Default: smoke test + pause + generate review ---

# Run the 4-hour smoke test on real repos BEFORE pausing agents
echo "Running 4-hour smoke test on real repos..."
if bash scripts/smoke-real-repos.sh 6; then
  SMOKE_STATUS="PASSED"
else
  SMOKE_STATUS="SOME FAILURES"
fi
SMOKE_FILE="$(ls -t research/smoke-*.md 2>/dev/null | head -1)"
echo ""

echo "Pausing all agents for human review..."
for role in "${ROLES[@]}"; do
  touch "coordination/$role.stop"
done

echo "Generating review summary -> $REVIEW_FILE"

{
  echo "# Human Review — $(date_iso)"
  echo ""
  echo "Agents paused. Review the status below, then run:"
  echo '```'
  echo "bash scripts/human-review.sh --resume"
  echo '```'
  echo ""

  echo "## Task Status"
  echo ""
  echo '```'
  python3 -c "
import json
from pathlib import Path
data = json.loads(Path('coordination/TASKS.json').read_text())
for t in data['tasks']:
    owner = t.get('owner') or '-'
    print(f\"  {t['id']:4s} [{t['status']:8s}] owner={owner:12s} {t['title']}\")
" 2>/dev/null || echo "  (could not parse TASKS.json)"
  echo '```'
  echo ""

  echo "## Real-Repo Smoke Test"
  echo ""
  echo "Status: **$SMOKE_STATUS**"
  echo ""
  if [ -n "$SMOKE_FILE" ] && [ -f "$SMOKE_FILE" ]; then
    # Include the results table from the smoke test
    sed -n '/^|/p' "$SMOKE_FILE"
    echo ""
    sed -n '/^## Summary/,/^$/p' "$SMOKE_FILE"
    echo ""
    echo "Full report: \`$SMOKE_FILE\`"
  else
    echo "_No smoke test results found._"
  fi
  echo ""

  echo "## Recent Commits (last 15)"
  echo ""
  echo '```'
  git log --oneline -15 2>/dev/null || echo "  (no git history)"
  echo '```'
  echo ""

  echo "## Agent Lifecycle (last 5 lines each)"
  echo ""
  for role in "${ROLES[@]}"; do
    log=".local/$role-lifecycle.log"
    if [ -f "$log" ]; then
      echo "### $role"
      echo '```'
      tail -5 "$log"
      echo '```'
      echo ""
    else
      echo "### $role"
      echo "_No lifecycle log yet._"
      echo ""
    fi
  done

  echo "## Open Review Receipts"
  echo ""
  if [ -d "coordination/review" ] && ls coordination/review/*.json 1>/dev/null 2>&1; then
    for f in coordination/review/*.json; do
      echo "### $(basename "$f")"
      echo '```json'
      cat "$f"
      echo '```'
      echo ""
    done
  else
    echo "_No review receipts yet._"
    echo ""
  fi

  echo "## Pending Inbox Messages"
  echo ""
  for role in "${ROLES[@]}"; do
    count=$(python3 -c "
import json
from pathlib import Path
p = Path('coordination/inbox/$role.jsonl')
if not p.exists(): print(0); exit()
msgs = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
print(sum(1 for m in msgs if not m.get('acked')))
" 2>/dev/null || echo 0)
    if [ "$count" != "0" ]; then
      echo "- **$role**: $count unacked messages"
    fi
  done
  echo ""

  echo "---"
  echo ""
  echo "**Actions you can take:**"
  echo "- Edit \`coordination/TASKS.json\` to add/modify/reprioritize tasks"
  echo "- Edit \`AGENTS.md\` to change agent instructions or add constraints"
  echo "- Send a message: \`python3 scripts/agent-msg.py send <role> '{\"action\":\"human_directive\",\"msg\":\"...\"}'\`"
  echo "- Resume: \`bash scripts/human-review.sh --resume\`"

} > "$REVIEW_FILE"

echo ""
echo "Review summary written to: $REVIEW_FILE"
echo ""
echo "Next steps:"
echo "  1. Read $REVIEW_FILE"
echo "  2. Edit TASKS.json or AGENTS.md as needed"
echo "  3. Resume: bash scripts/human-review.sh --resume"
