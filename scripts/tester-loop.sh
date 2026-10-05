#!/usr/bin/env bash
# Tester agent loop — Claude Sonnet 4.6, 10k req/min.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export AGENT_ROLE=tester

mkdir -p .local

MODEL="claude-sonnet-4-6"

for round in $(seq 1 20); do
  [ -f "coordination/tester.stop" ] && exit 0

  printf 'tester round %s started %s\n' "$round" "$(date -Is)" >> .local/tester-lifecycle.log

  PROMPT="You are the tester agent in /Users/bedil_karimov/Documents/depfix-agents working on depfix.

STARTUP PROTOCOL (every round):
1. Read AGENTS.md
2. Read coordination/tester.md (your durable state)
3. Read coordination/TASKS.json — find tasks with owner=tester or status=running that need testing
4. Run: python3 scripts/agent-msg.py inbox tester — read and ack messages

YOUR ROLE: Run tests and report real results. Never describe what tests would show — run them.

TASK T-1: Run full test suite and report failures
  Commands to run (in order):
  1. make test                  — unit tests (captures pytest output)
  2. make typecheck             — mypy
  3. make lint                  — ruff check
  4. make eval                  — eval corpus (no LLM: make eval uses --no-llm)

  For each command: capture the full output, count pass/fail, extract error messages.

  Write coordination/tester.md with:
  - Exact command outputs (truncated to 200 lines if very long)
  - Pass/fail counts for each command
  - For each failure: file, line, error message, likely root cause
  - Overall assessment: is the codebase healthy?

  When done:
  1. Commit: flock .local/git.lock bash -c 'git add coordination/tester.md && git commit -m \"tester(T-1): full test suite results\"'
  2. Update TASKS.json: T-1 status=done (no review needed for a test report)
  3. Send: python3 scripts/agent-msg.py send principal '{\"action\":\"task_done\",\"task_id\":\"T-1\",\"summary\":\"X tests pass, Y fail, see coordination/tester.md\"}'

ONGOING TESTING (after T-1):
After any implementer commits new code, re-run the relevant tests:
- After T-3 (skill files): make test (skill .md files don't affect tests but verify anyway)
- After T-4 (eval cases): make eval
- After T-5 (ruby eval cases): make eval
Report results in coordination/tester.md and send to principal.

If tests fail after an implementer commit:
- Send: python3 scripts/agent-msg.py send implementer '{\"action\":\"test_failure\",\"task_id\":\"T-N\",\"failures\":[\"<test>\",\"<error>\"]}'
- Update TASKS.json: set status=rejected for the relevant task if the failures are caused by the new code

COMMIT YOUR STATE after every step:
flock .local/git.lock bash -c 'git add coordination/tester.md && git commit -m \"tester: state update round $round\"'

This is round $round."

  timeout 15m claude -p \
    --model "$MODEL" \
    --permission-mode auto \
    --output-format stream-json \
    "$PROMPT" 2>&1 | tee ".local/tester-$round.log"

  rc=$?
  printf 'tester round %s exit %s %s\n' "$round" "$rc" "$(date -Is)" >> .local/tester-lifecycle.log
  [ -f "coordination/tester.stop" ] && exit 0

  sleep 60
done

[ -f "coordination/tester.stop" ] || exec bash scripts/tester-loop.sh
