#!/usr/bin/env bash
# Researcher agent loop — task-driven, no round counter.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export AGENT_ROLE=researcher

timeout() { if command -v gtimeout >/dev/null; then gtimeout "$@"; else command timeout "$@"; fi; }
date_iso() { if command -v gdate >/dev/null; then gdate -Iseconds; else date +%Y-%m-%dT%H:%M:%S%z; fi; }

mkdir -p .local research

MODEL="claude-opus-5-5"

while true; do
  [ -f "coordination/researcher.stop" ] && exit 0
  TS="$(date_iso)"
  LOGFILE=".local/researcher-$(date +%Y%m%d-%H%M%S).log"

  printf 'researcher started %s\n' "$TS" >> .local/researcher-lifecycle.log

  PROMPT="You are the researcher agent in /Users/bedil_karimov/Documents/depfix-agents working on depfix.

STARTUP PROTOCOL:
1. Read AGENTS.md
2. Read coordination/researcher.md (your durable state)
3. Read coordination/TASKS.json — find your assigned task (status=running, owner=researcher)
4. Run: python3 scripts/agent-msg.py inbox researcher — read and ack messages
5. Resume from your state file; do not repeat completed work

YOUR ROLE: Deep research on the depfix codebase and its ecosystem.
- Read source files thoroughly using available tools
- Run commands to gather real data (not guesses)
- Write findings to research/<topic>.md with exact file paths and reproducible commands
- Never claim a finding without a real command output or file reference

Read TASKS.json for your current assignment. The task's acceptance criteria tell you what to produce.

WHEN DONE WITH A TASK:
1. Write your output to the research/ file specified in the task
2. Commit: flock .local/git.lock bash -c 'git add research/<file>.md && git commit -m \"researcher(T-N): <description>\"'
3. Update coordination/TASKS.json: set your task status=done
4. Update coordination/researcher.md with what you did and what's next
5. Send message to principal: python3 scripts/agent-msg.py send principal '{\"action\":\"task_done\",\"task_id\":\"T-N\",\"evidence\":\"research/<file>.md\"}'

COMMIT YOUR STATE after each meaningful step:
flock .local/git.lock bash -c 'git add coordination/researcher.md && git commit -m \"researcher: state update\"'

If you have no assigned task, check TASKS.json for ready research tasks and notify the principal."

  git remote get-url --push origin 2>/dev/null | grep -q DISABLED || git remote set-url --push origin DISABLED_DO_NOT_PUSH_TO_DEPENDENCY_CHECK

  timeout 20m claude -p \
    --model "$MODEL" \
    --dangerously-skip-permissions \
    "$PROMPT" 2> >(grep -v 'Permission allow rule' >&2) | tee "$LOGFILE"

  rc=$?
  printf 'researcher exit %s %s\n' "$rc" "$(date_iso)" >> .local/researcher-lifecycle.log
  [ -f "coordination/researcher.stop" ] && exit 0

  if grep -q "429\|rate.limit\|overloaded\|Too Many Requests" "$LOGFILE" 2>/dev/null; then
    printf 'researcher 429 — sleeping 30 min %s\n' "$(date_iso)" >> .local/researcher-lifecycle.log
    sleep 1800
  else
    sleep 30
  fi
done
