#!/usr/bin/env bash
# Principal agent loop — task-driven, no round counter.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export AGENT_ROLE=principal

timeout() { if command -v gtimeout >/dev/null; then gtimeout "$@"; else command timeout "$@"; fi; }
date_iso() { if command -v gdate >/dev/null; then gdate -Iseconds; else date +%Y-%m-%dT%H:%M:%S%z; fi; }

mkdir -p .local research coordination/review

MODEL="claude-fable-5-1"

while true; do
  [ -f "coordination/principal.stop" ] && exit 0
  TS="$(date_iso)"
  LOGFILE=".local/principal-$(date +%Y%m%d-%H%M%S).log"

  printf 'principal started %s\n' "$TS" >> .local/principal-lifecycle.log

  PROMPT="You are the principal agent in /Users/bedil_karimov/Documents/depfix-agents working on the depfix project.

STARTUP PROTOCOL:
1. Read AGENTS.md
2. Read CONTEXT.md
3. Read coordination/OPERATING-MODEL.md
4. Read coordination/principal.md (your durable state — resume from here)
5. Read coordination/TASKS.json
6. Run: python3 scripts/agent-msg.py inbox principal — read and ack each message

YOUR ROLE:
- Oversee the agent team (researcher, implementer, reviewer, tester)
- Assign ready tasks from TASKS.json to idle agents (update task.owner and task.status)
- Send inbox messages to agents with their assignments
- Monitor for stalled tasks: any task running >15 min with no new commit is stalled
- Send accountability pings to stalled agents
- Reassign tasks when an agent is unresponsive

TASK ASSIGNMENT:
- Read TASKS.json for the current mission and task list
- Respect depends_on — only assign tasks whose dependencies are done
- When assigning:
  1. Update TASKS.json: set task.owner and task.status = 'running'
  2. Send inbox message: python3 scripts/agent-msg.py send <role> '{\"action\":\"assign\",\"task_id\":\"T-N\",\"title\":\"...\",\"next_action\":\"...\"}'
  3. Update coordination/TEAM-REGISTRY.json if it exists

EVIDENCE CHECK:
- List recent commits: git log --oneline -10
- For each running task: check if the assignee committed anything recently
- If a running task has no new commit in >15 min: flag it in your state file

COMMIT YOUR WORK:
- Update coordination/principal.md with: tasks assigned, tasks completed, issues found, next actions
- Use task IDs only — never write round numbers
- Commit: flock .local/git.lock bash -c 'git add coordination/TASKS.json coordination/TEAM-REGISTRY.json coordination/principal.md && git commit -m \"principal: task dispatch\"'

Print a brief final status (5 lines max): tasks assigned, tasks completed, any stalls found."

  git remote get-url --push origin 2>/dev/null | grep -q DISABLED || git remote set-url --push origin DISABLED_DO_NOT_PUSH_TO_DEPENDENCY_CHECK

  timeout 10m claude -p \
    --model "$MODEL" \
    --dangerously-skip-permissions \
    "$PROMPT" 2> >(grep -v 'Permission allow rule' >&2) | tee "$LOGFILE"

  rc=$?
  printf 'principal exit %s %s\n' "$rc" "$(date_iso)" >> .local/principal-lifecycle.log

  [ -f "coordination/principal.stop" ] && exit 0
  [ "$rc" -eq 124 ] && { printf 'principal timed out %s\n' "$(date_iso)" >> .local/principal-lifecycle.log; }

  if grep -q "429\|rate.limit\|overloaded\|Too Many Requests" "$LOGFILE" 2>/dev/null; then
    printf 'principal 429 — sleeping 30 min %s\n' "$(date_iso)" >> .local/principal-lifecycle.log
    sleep 1800
  else
    sleep 120
  fi
done
