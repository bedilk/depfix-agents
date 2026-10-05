#!/usr/bin/env bash
# Principal agent loop — Claude Opus 4.6, 25 req/min shared with reviewer.
# Runs up to 8 rounds then re-execs itself (so it runs indefinitely until .stop).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export AGENT_ROLE=principal

# macOS compat: GNU coreutils prefixed with 'g'
timeout() { if command -v gtimeout >/dev/null; then gtimeout "$@"; else command timeout "$@"; fi; }
date_iso() { if command -v gdate >/dev/null; then gdate -Iseconds; else date +%Y-%m-%dT%H:%M:%S%z; fi; }

mkdir -p .local research coordination/review

MODEL="claude-opus-4-6"

for round in $(seq 1 8); do
  [ -f "coordination/principal.stop" ] && exit 0

  printf 'principal round %s started %s\n' "$round" "$(date_iso)" >> .local/principal-lifecycle.log

  PROMPT="You are the principal agent in /Users/bedil_karimov/Documents/depfix-agents working on the depfix project.

STARTUP PROTOCOL (do this first, every round):
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
- Challenge agents when their evidence is thin or their approach looks wrong
- Reassign tasks when an agent is unresponsive

RATE LIMIT: You share 25 req/min with the reviewer. Space your rounds >= 120s apart.
After this round completes, the script sleeps 120s before the next round.

TASK ASSIGNMENT RULES:
- Assign T-1 to tester if tester is idle (check coordination/tester.md)
- Assign T-2 to researcher if researcher is idle
- Assign T-7 to researcher if T-2 is done and researcher is idle
- Assign T-8 to researcher if T-7 is done and researcher is idle (top providers research)
- Assign T-9 to researcher if T-8 is done and T-1 is done (drift detection audit)
- Assign T-3 to implementer after T-1 is done
- Assign T-4 to implementer after T-1 and T-2 are done (researcher should write research first)
- Assign T-5 to implementer after T-1 is done
- Assign T-6 to reviewer if reviewer is idle (it's a pure review, no dependency)
- Assign T-10 to tester after T-1 is done (end-to-end dry-run on seed repos)
- Assign T-11 to tester after T-1 is done (real-repo scan — 7 forked repos, ground truth test)
- Assign T-12 to tester after T-1 is done (e2e test repos — sentry-v6, openai-v3, anthropic)
- Assign T-13 to tester after T-1 is done (multi-provider scan on firecrawl)
- Assign T-14 to tester after T-1 is done (large-repo stress test — Rocket.Chat + superset)
- PRIORITY: T-11 and T-12 are higher priority than T-10 — real repos matter more than seed repos
- For T-4: first assign research subtask to researcher, then implementation to implementer

When assigning a task:
1. Update coordination/TASKS.json: set task.owner = '<role>' and task.status = 'running'
2. Send inbox message: python3 scripts/agent-msg.py send <role> '{\"action\":\"assign\",\"task_id\":\"T-N\",\"title\":\"...\",\"next_action\":\"...\"}'
3. Update coordination/TEAM-REGISTRY.json: set agent.current_task and agent.status

COMMIT GATE ENFORCEMENT:
- When any agent submits code for review, verify they ran bash scripts/commit-gate.sh
- Check .local/push-history.log for recent pushes
- If a task reaches status=done but no push is logged for its commit SHA: REJECT it

4-HOUR SMOKE TEST:
- Check .local/smoke-history.log for the last smoke test timestamp
- If the last smoke test is >4 hours old (or doesn't exist), send tester:
  python3 scripts/agent-msg.py send tester '{\"action\":\"smoke_test\",\"count\":6}'
- After receiving smoke results, record any regressions in coordination/principal.md

EVIDENCE CHECK (do every round after round 1):
- List commits since your last round: git log --oneline -10
- For each running task: check if the assignee committed anything
- If a running task has no new commit in >2 rounds: flag it in your state file

COMMIT YOUR WORK:
- Update coordination/principal.md with: current round, tasks assigned, tasks completed, issues found, next actions
- Commit: flock .local/git.lock bash -c 'git add coordination/TASKS.json coordination/TEAM-REGISTRY.json coordination/principal.md && git commit -m \"principal(round-$round): task dispatch and oversight\"'

This is round $round. Print a brief final status (5 lines max): tasks assigned, tasks completed, any stalls found."

  timeout 10m claude -p \
    --model "$MODEL" \
    --dangerously-skip-permissions \
    "$PROMPT" 2>&1 | tee ".local/principal-$round.log"

  rc=$?
  printf 'principal round %s exit %s %s\n' "$round" "$rc" "$(date_iso)" >> .local/principal-lifecycle.log

  [ -f "coordination/principal.stop" ] && exit 0
  [ "$rc" -eq 124 ] && { printf 'principal round %s timed out\n' "$round" >> .local/principal-lifecycle.log; }

  # Respect Opus rate limit: 120s between rounds
  sleep 120
done

# Re-exec to keep running indefinitely
[ -f "coordination/principal.stop" ] || exec bash scripts/principal-loop.sh
