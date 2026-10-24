#!/usr/bin/env bash
# Tester agent loop — task-driven, no round counter.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export AGENT_ROLE=tester

timeout() { if command -v gtimeout >/dev/null; then gtimeout "$@"; else command timeout "$@"; fi; }
date_iso() { if command -v gdate >/dev/null; then gdate -Iseconds; else date +%Y-%m-%dT%H:%M:%S%z; fi; }

mkdir -p .local

MODEL="claude-sonnet-5"

while true; do
  [ -f "coordination/tester.stop" ] && exit 0
  TS="$(date_iso)"
  LOGFILE=".local/tester-$(date +%Y%m%d-%H%M%S).log"

  printf 'tester started %s\n' "$TS" >> .local/tester-lifecycle.log

  PROMPT="You are the tester agent in /Users/bedil_karimov/Documents/depfix-agents working on depfix.

STARTUP PROTOCOL:
1. Read AGENTS.md
2. Read coordination/tester.md (your durable state)
3. Read coordination/TASKS.json — find tasks assigned to you (owner=tester)
4. Run: python3 scripts/agent-msg.py inbox tester — read and ack messages

YOUR ROLE: Run tests and report real results. Never describe what tests would show — run them.
- Run depfix commands from /Users/bedil_karimov/Documents/dependency_check (has .env with credentials)
- Capture exact command output, pass/fail counts, error messages
- Write results to the file specified in the task's evidence_paths

Read TASKS.json for your current assignment. The task's acceptance criteria tell you exactly what to test.

WHEN DONE WITH A TASK:
1. Write results to the evidence file
2. Commit: flock .local/git.lock bash -c 'git add <evidence-file> coordination/tester.md && git commit -m \"tester(T-N): <description>\"'
3. Update TASKS.json: set status=done (test reports don't need review)
4. Send: python3 scripts/agent-msg.py send principal '{\"action\":\"task_done\",\"task_id\":\"T-N\",\"summary\":\"...\"}'

SMOKE TEST DUTY:
When principal sends action=smoke_test, run: bash scripts/smoke-real-repos.sh 6
Report results to principal via inbox.

COMMIT YOUR STATE after every step:
flock .local/git.lock bash -c 'git add coordination/tester.md && git commit -m \"tester: state update\"'

If no task is assigned, check TASKS.json and notify the principal."

  git remote get-url --push origin 2>/dev/null | grep -q DISABLED || git remote set-url --push origin DISABLED_DO_NOT_PUSH_TO_DEPENDENCY_CHECK

  timeout 15m claude -p \
    --model "$MODEL" \
    --dangerously-skip-permissions \
    "$PROMPT" 2> >(grep -v 'Permission allow rule' >&2) | tee "$LOGFILE"

  rc=$?
  printf 'tester exit %s %s\n' "$rc" "$(date_iso)" >> .local/tester-lifecycle.log
  [ -f "coordination/tester.stop" ] && exit 0

  if grep -q "429\|rate.limit\|overloaded\|Too Many Requests" "$LOGFILE" 2>/dev/null; then
    printf 'tester 429 — sleeping 30 min %s\n' "$(date_iso)" >> .local/tester-lifecycle.log
    sleep 1800
  else
    sleep 60
  fi
done
