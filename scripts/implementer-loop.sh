#!/usr/bin/env bash
# Implementer agent loop — Claude Sonnet 4.6, 10k req/min.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export AGENT_ROLE=implementer

# macOS compat: GNU coreutils prefixed with 'g'
timeout() { if command -v gtimeout >/dev/null; then gtimeout "$@"; else command timeout "$@"; fi; }
date_iso() { if command -v gdate >/dev/null; then gdate -Iseconds; else date +%Y-%m-%dT%H:%M:%S%z; fi; }

mkdir -p .local

MODEL="claude-sonnet-4-6"

for round in $(seq 1 20); do
  [ -f "coordination/implementer.stop" ] && exit 0

  printf 'implementer round %s started %s\n' "$round" "$(date_iso)" >> .local/implementer-lifecycle.log

  PROMPT="You are the implementer agent in /Users/bedil_karimov/Documents/depfix-agents working on depfix.

STARTUP PROTOCOL (every round):
1. Read AGENTS.md
2. Read coordination/implementer.md (your durable state)
3. Read coordination/TASKS.json — find your assigned task (status=running, owner=implementer)
4. Run: python3 scripts/agent-msg.py inbox implementer — read and ack messages
5. Resume from your state file; do not repeat completed work

YOUR ROLE: Write code and configuration for depfix.
- Read existing code carefully before changing anything (read the whole file, not just a snippet)
- Match existing code style exactly (ruff-formatted Python, existing docstring patterns)
- Run make test after every change — do not submit broken code
- Write targeted changes: only touch files needed for your task
- Never touch peer-owned files without an acknowledged handoff

CURRENT TASKS you may be assigned:

T-3: Add provider skill files for redis and postgresql
  - Read src/depfix/providers/skills/provider_sentry.md for the exact template format
  - Write src/depfix/providers/skills/provider_redis.md
    Focus: redis commands used as SDK calls, import patterns (ioredis, node-redis, redis-py, redis gem)
    Key APIs that break between major versions: client.set/get, pipeline, publish/subscribe, streams
  - Write src/depfix/providers/skills/provider_postgresql.md
    Focus: pg/psycopg/pg gem import patterns, query/connect APIs, connection pool patterns
  - Run make test (these are .md files so tests should still pass)
  - Set status=review in TASKS.json, send review request to reviewer

T-4 (implementation): Write 10 sentry eval YAML cases
  - First read research/sentry-eval-cases.md (researcher output) — only start after that exists
  - Read src/depfix/evals/corpus/ to learn the exact YAML schema
  - Add 10 new cases to a new file: src/depfix/evals/corpus/sentry_v8_callsites.yaml
  - Run make eval to verify no regressions
  - Set status=review, send review request to reviewer

T-5: Add 5 ruby ecosystem eval cases
  - Read src/depfix/evals/corpus/ for existing call_sites YAML format
  - Read src/depfix/ecosystems/specs.py RUBY definition and ruby_import_regexes
  - Write 5 cases to src/depfix/evals/corpus/ruby_callsites.yaml
    Test patterns: require 'openai', require 'stripe', require 'sentry-ruby'
  - Run make eval
  - Set status=review, send review request to reviewer

WHEN DONE WITH A TASK:
1. Run the COMMIT GATE: bash scripts/commit-gate.sh
   This runs make test + make lint + make typecheck + git push.
   If it fails, FIX THE CODE and re-run. Do NOT submit broken code for review.
2. Commit all changed files: flock .local/git.lock bash -c 'git add <specific files> && git commit -m \"implementer(T-N): <description>\"'
3. Run commit gate again after committing: bash scripts/commit-gate.sh
4. Update coordination/TASKS.json: status=review, owner=reviewer
5. Update coordination/implementer.md
6. Send: python3 scripts/agent-msg.py send reviewer '{\"action\":\"review_request\",\"task_id\":\"T-N\",\"summary\":\"what changed\",\"commit\":\"<sha>\",\"files_changed\":[\"...\"]}'
7. Send: python3 scripts/agent-msg.py send principal '{\"action\":\"status\",\"task_id\":\"T-N\",\"status\":\"review\",\"reviewer\":\"reviewer\"}'

COMMIT YOUR STATE after every step:
flock .local/git.lock bash -c 'git add coordination/implementer.md && git commit -m \"implementer: state update round $round\"'

This is round $round. Work on your assigned task. If no task assigned yet, check TASKS.json
for tasks with owner=implementer and status=running."

  timeout 20m claude -p \
    --model "$MODEL" \
    --permission-mode auto \
    "$PROMPT" 2>&1 | tee ".local/implementer-$round.log"

  rc=$?
  printf 'implementer round %s exit %s %s\n' "$round" "$rc" "$(date_iso)" >> .local/implementer-lifecycle.log
  [ -f "coordination/implementer.stop" ] && exit 0

  sleep 30
done

[ -f "coordination/implementer.stop" ] || exec bash scripts/implementer-loop.sh
