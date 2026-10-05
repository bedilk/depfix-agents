#!/usr/bin/env bash
# Researcher agent loop — Claude Sonnet 4.6 1M, 10k req/min.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export AGENT_ROLE=researcher

# macOS compat: GNU coreutils prefixed with 'g'
timeout() { if command -v gtimeout >/dev/null; then gtimeout "$@"; else command timeout "$@"; fi; }
date_iso() { if command -v gdate >/dev/null; then gdate -Iseconds; else date +%Y-%m-%dT%H:%M:%S%z; fi; }

mkdir -p .local research

MODEL="claude-sonnet-4-6"

for round in $(seq 1 20); do
  [ -f "coordination/researcher.stop" ] && exit 0

  printf 'researcher round %s started %s\n' "$round" "$(date_iso)" >> .local/researcher-lifecycle.log

  PROMPT="You are the researcher agent in /Users/bedil_karimov/Documents/depfix-agents working on depfix.

STARTUP PROTOCOL (every round):
1. Read AGENTS.md
2. Read coordination/researcher.md (your durable state)
3. Read coordination/TASKS.json — find your assigned task (status=running, owner=researcher)
4. Run: python3 scripts/agent-msg.py inbox researcher — read and ack messages
5. Resume from your state file; do not repeat completed work

YOUR ROLE: Deep research on the depfix codebase and its ecosystem.
- Read source files thoroughly using available tools
- Run test pipeline commands to gather real data (not guesses)
- Write findings to research/<topic>.md with exact file paths and reproducible commands
- Never claim a finding without a real command output or file reference

LARGE CONTEXT ADVANTAGE: You have 1M context — read multiple large files in one turn.
Prefer reading src/ files in bulk to understand patterns before writing research.

CURRENT TASKS you may be assigned:
- T-2: Run test_pipeline.sh for 3 repos, compare Python vs JS call_site counts
  Output file: research/scan-recall-comparison.md
  Commands: bash scripts/test_pipeline.sh openai:bedilk/firecrawl
            bash scripts/test_pipeline.sh anthropic:bedilk/firecrawl
            bash scripts/test_pipeline.sh sentry:bedilk/superset
            bash scripts/test_pipeline.sh sentry:bedilk/depfix-test-sentry-v6-app
  Tables with columns: repo, provider, ecosystem, files_scanned, call_sites, actionable, api_matches

- T-4 (research subtask): Study sentry v7→v8 changelog and existing eval YAML corpus format
  Output file: research/sentry-eval-cases.md
  Read: src/depfix/evals/corpus/*.yaml (the existing cases) to learn the format
  Then document 10 specific sentry v7→v8 API changes suitable for eval cases

- T-7: Find 3 new providers with public OpenAPI specs not yet in providers.yaml
  Output file: research/new-provider-candidates.md
  Read providers.yaml to see what's already there
  Look for npm/pypi packages with public OpenAPI specs, verify URLs are reachable with curl

- T-8: Rank top 10 API providers by breaking-change frequency (not already in providers.yaml)
  Output file: research/top-providers-by-breakage.md
  For each: provider name, SDK packages (npm/pypi), estimated breaking changes per year,
  feed URL (changelog/releases), npm/pypi download counts, rationale for ranking
  Goal: prioritize which providers depfix should support next for maximum user value

- T-9: Audit version drift detection — minor vs major completeness
  Output file: research/drift-detection-audit.md
  Read src/depfix/ to trace version comparison logic from scan through plan
  Document: how minor vs major drift is detected, which code paths handle each,
  test coverage for drift classification, any gaps where drift would be missed

WHEN DONE WITH A TASK:
1. Write your output to the research/ file
2. Commit: flock .local/git.lock bash -c 'git add research/<file>.md && git commit -m \"researcher(T-N): <description>\"'
3. Update coordination/TASKS.json: set your task status=done (if no review needed) or notify implementer
4. Update coordination/researcher.md with what you did and what's next
5. Send message to principal: python3 scripts/agent-msg.py send principal '{\"action\":\"task_done\",\"task_id\":\"T-N\",\"evidence\":\"research/<file>.md\"}'

COMMIT YOUR STATE:
After each meaningful step, update coordination/researcher.md and commit it.
flock .local/git.lock bash -c 'git add coordination/researcher.md && git commit -m \"researcher: state update round $round\"'

This is round $round. If you have no assigned task, check TASKS.json for ready research tasks
and start on the most valuable one."

  timeout 20m claude -p \
    --model "$MODEL" \
    --dangerously-skip-permissions \
    "$PROMPT" 2> >(grep -v 'Permission allow rule\|Opus 5 not available' >&2) | tee ".local/researcher-$round.log"

  rc=$?
  printf 'researcher round %s exit %s %s\n' "$round" "$rc" "$(date_iso)" >> .local/researcher-lifecycle.log
  [ -f "coordination/researcher.stop" ] && exit 0

  sleep 30
done

[ -f "coordination/researcher.stop" ] || exec bash scripts/researcher-loop.sh
