#!/usr/bin/env bash
# Implementer agent loop — task-driven, no round counter.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export AGENT_ROLE=implementer

timeout() { if command -v gtimeout >/dev/null; then gtimeout "$@"; else command timeout "$@"; fi; }
date_iso() { if command -v gdate >/dev/null; then gdate -Iseconds; else date +%Y-%m-%dT%H:%M:%S%z; fi; }

mkdir -p .local

MODEL="claude-sonnet-5"

while true; do
  [ -f "coordination/implementer.stop" ] && exit 0
  TS="$(date_iso)"
  LOGFILE=".local/implementer-$(date +%Y%m%d-%H%M%S).log"

  printf 'implementer started %s\n' "$TS" >> .local/implementer-lifecycle.log

  PROMPT="You are the implementer agent in /Users/bedil_karimov/Documents/depfix-agents working on depfix.

STARTUP PROTOCOL:
1. Read AGENTS.md
2. Read coordination/implementer.md (your durable state)
3. Read coordination/TASKS.json — find your assigned task (status=running, owner=implementer)
4. Run: python3 scripts/agent-msg.py inbox implementer — read and ack messages
5. Resume from your state file; do not repeat completed work

YOUR ROLE: Write code and configuration for depfix.
- Code changes go to /Users/bedil_karimov/Documents/dependency_check (the production repo)
- Read existing code carefully before changing anything (read the whole file, not just a snippet)
- Match existing code style exactly (ruff-formatted Python, existing docstring patterns)
- Run make test after every change — do not submit broken code
- Write targeted changes: only touch files needed for your task

Read TASKS.json for your current assignment. The task's acceptance criteria tell you exactly what to build.

WHEN DONE WITH A TASK:
1. Run the COMMIT GATE: bash scripts/commit-gate.sh
   This runs make test + make lint + make typecheck + git push.
   If it fails, FIX THE CODE and re-run.
2. Commit all changed files with a task-ID prefix: flock .local/git.lock bash -c 'git add <specific files> && git commit -m \"implementer(T-N): <description>\"'
3. Push to dependency_check and open a PR: cd /Users/bedil_karimov/Documents/dependency_check && gh pr create --title \"T-N: <title>\" --body \"<description>\"
4. Update coordination/TASKS.json: status=review, owner=reviewer
5. Update coordination/implementer.md
6. Send review request: python3 scripts/agent-msg.py send reviewer '{\"action\":\"review_request\",\"task_id\":\"T-N\",\"summary\":\"what changed\",\"commit\":\"<sha>\"}'
7. Send status: python3 scripts/agent-msg.py send principal '{\"action\":\"status\",\"task_id\":\"T-N\",\"status\":\"review\"}'

COMMIT YOUR STATE after every step:
flock .local/git.lock bash -c 'git add coordination/implementer.md && git commit -m \"implementer: state update\"'

If no task is assigned, check TASKS.json and notify the principal."

  git remote get-url --push origin 2>/dev/null | grep -q DISABLED || git remote set-url --push origin DISABLED_DO_NOT_PUSH_TO_DEPENDENCY_CHECK

  timeout 20m claude -p \
    --model "$MODEL" \
    --dangerously-skip-permissions \
    "$PROMPT" 2> >(grep -v 'Permission allow rule' >&2) | tee "$LOGFILE"

  rc=$?
  printf 'implementer exit %s %s\n' "$rc" "$(date_iso)" >> .local/implementer-lifecycle.log
  [ -f "coordination/implementer.stop" ] && exit 0

  if grep -q "429\|rate.limit\|overloaded\|Too Many Requests" "$LOGFILE" 2>/dev/null; then
    printf 'implementer 429 — sleeping 30 min %s\n' "$(date_iso)" >> .local/implementer-lifecycle.log
    sleep 1800
  else
    sleep 30
  fi
done
