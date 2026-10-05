#!/usr/bin/env bash
# Launch the full depfix agent team.
# Each agent runs in its own background process with output going to .local/<role>-loop.log
#
# Usage:
#   bash scripts/run-team.sh              # start all agents
#   bash scripts/run-team.sh --stop       # stop all agents (creates .stop files)
#   bash scripts/run-team.sh --status     # show agent status from coordination files
#   bash scripts/run-team.sh --logs       # tail all agent logs
#
# To stop a single agent: touch coordination/<role>.stop
# To restart a single agent: rm coordination/<role>.stop && bash scripts/<role>-loop.sh &

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

mkdir -p .local

if [[ "${1:-}" == "--stop" ]]; then
  echo "Stopping all agents..."
  for role in principal researcher implementer reviewer tester; do
    touch "coordination/$role.stop"
    echo "  $role: stop file created"
  done
  exit 0
fi

if [[ "${1:-}" == "--status" ]]; then
  echo "=== Task Status ==="
  python3 -c "
import json
from pathlib import Path
data = json.loads(Path('coordination/TASKS.json').read_text())
for t in data['tasks']:
    owner = t.get('owner') or '-'
    print(f\"  {t['id']:4s} [{t['status']:8s}] owner={owner:12s} {t['title']}\")
"
  echo ""
  echo "=== Recent commits ==="
  git log --oneline -10
  echo ""
  echo "=== Agent lifecycle (last 5 lines each) ==="
  for role in principal researcher implementer reviewer tester; do
    log=".local/$role-lifecycle.log"
    if [ -f "$log" ]; then
      echo "  -- $role --"
      tail -3 "$log" | sed 's/^/    /'
    fi
  done
  exit 0
fi

if [[ "${1:-}" == "--logs" ]]; then
  tail -f .local/principal-*.log .local/researcher-*.log .local/implementer-*.log .local/reviewer-*.log .local/tester-*.log 2>/dev/null
  exit 0
fi

# --- Clean stop files before launch ---
for role in principal researcher implementer reviewer tester; do
  rm -f "coordination/$role.stop"
done

echo "Starting depfix agent team..."
echo "Repo: $(pwd)"
echo "Logs: .local/<role>-<round>.log"
echo ""

# Make all scripts executable
chmod +x scripts/*.sh

# --- Launch Sonnet agents (no rate limit concern) ---
echo "Starting tester (Sonnet 4.6)..."
bash scripts/tester-loop.sh > .local/tester-loop.log 2>&1 &
TESTER_PID=$!
echo "  tester PID: $TESTER_PID"

sleep 5

echo "Starting researcher (Sonnet 4.6 1M)..."
bash scripts/researcher-loop.sh > .local/researcher-loop.log 2>&1 &
RESEARCHER_PID=$!
echo "  researcher PID: $RESEARCHER_PID"

sleep 5

echo "Starting implementer (Sonnet 4.6)..."
bash scripts/implementer-loop.sh > .local/implementer-loop.log 2>&1 &
IMPLEMENTER_PID=$!
echo "  implementer PID: $IMPLEMENTER_PID"

# --- Launch Opus agents (25 req/min shared — stagger to avoid collision) ---
# Principal starts immediately, runs a round, then sleeps 120s.
# Reviewer starts 60s later: it runs while principal is sleeping (60–180s).
# This way they don't overlap on the Opus pool.

echo "Starting principal (Opus 4.6) — will use Opus pool..."
bash scripts/principal-loop.sh > .local/principal-loop.log 2>&1 &
PRINCIPAL_PID=$!
echo "  principal PID: $PRINCIPAL_PID"

echo "Waiting 65s before starting reviewer (to stagger Opus usage)..."
sleep 65

echo "Starting reviewer (Opus 4.6) — staggered 65s behind principal..."
bash scripts/reviewer-loop.sh > .local/reviewer-loop.log 2>&1 &
REVIEWER_PID=$!
echo "  reviewer PID: $REVIEWER_PID"

echo ""
echo "All agents running. PIDs:"
echo "  principal:   $PRINCIPAL_PID"
echo "  researcher:  $RESEARCHER_PID"
echo "  implementer: $IMPLEMENTER_PID"
echo "  reviewer:    $REVIEWER_PID"
echo "  tester:      $TESTER_PID"
echo ""
echo "Commands:"
echo "  bash scripts/run-team.sh --status   # check task progress"
echo "  bash scripts/run-team.sh --stop     # stop all agents"
echo "  bash scripts/run-team.sh --logs     # tail all logs"
echo "  tail -f .local/principal-loop.log   # watch principal"
echo "  python3 scripts/agent-msg.py inbox principal  # check principal inbox"
echo ""
echo "To stop a single agent: touch coordination/<role>.stop"

# Write PIDs for monitoring
python3 -c "
import json
from pathlib import Path
pids = {
    'principal': $PRINCIPAL_PID,
    'researcher': $RESEARCHER_PID,
    'implementer': $IMPLEMENTER_PID,
    'reviewer': $REVIEWER_PID,
    'tester': $TESTER_PID,
}
Path('.local/pids.json').write_text(json.dumps(pids, indent=2))
"
echo "PIDs saved to .local/pids.json"
