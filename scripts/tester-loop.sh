#!/usr/bin/env bash
# Tester agent loop — Claude Sonnet 4.6, 10k req/min.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export AGENT_ROLE=tester

# macOS compat: GNU coreutils prefixed with 'g'
timeout() { if command -v gtimeout >/dev/null; then gtimeout "$@"; else command timeout "$@"; fi; }
date_iso() { if command -v gdate >/dev/null; then gdate -Iseconds; else date +%Y-%m-%dT%H:%M:%S%z; fi; }

mkdir -p .local

MODEL="claude-sonnet-4-6"

for round in $(seq 1 20); do
  [ -f "coordination/tester.stop" ] && exit 0

  printf 'tester round %s started %s\n' "$round" "$(date_iso)" >> .local/tester-lifecycle.log

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

TASK T-10: End-to-end dry-run on 3 seed repos (after T-1)
  Run the full pipeline in dry-run mode on:
  1. depfix pipeline --dry-run --no-pr bedilk/seed-openai-v3-to-v4
  2. depfix pipeline --dry-run --no-pr bedilk/seed-stripe-apiversion
  3. depfix pipeline --dry-run --no-pr bedilk/seed-sentry-v7-v8
  For each repo capture: drifts found, call-sites detected, plan output, whether fixes generated,
  test results. This proves the end-to-end flow works.
  Write results to coordination/tester.md with a section per repo.

TASK T-11: Real-repo scan — test all 7 forked repos (after T-1)
  Run: bash test_all_repos.sh
  This tests: probot(octokit), renovate(octokit), bolt-js(slack), sentry(slack),
  AtlantaBot(discord), guide(discord), Rocket.Chat(mongodb)
  For each: record files_scanned, call_sites, actionable, plan output.
  Write results table to research/real-repo-scan-results.md
  THIS IS THE GROUND TRUTH TEST — if depfix can't find call-sites in real repos, it doesn't work.

TASK T-12: Real-repo scan — test 3 e2e repos (after T-1)
  Run test_pipeline.sh on:
  1. sentry:bedilk/depfix-test-sentry-v6-app
  2. openai:bedilk/depfix-test-openai-v3-chat
  3. anthropic:bedilk/depfix-test-anthropic-callsites
  Then run depfix plan --dry-run for repos with actionable findings.
  Write to research/e2e-repo-results.md

TASK T-13: Multi-provider scan on firecrawl (after T-1)
  Run: (1) test_pipeline.sh openai:bedilk/firecrawl
       (2) test_pipeline.sh anthropic:bedilk/firecrawl
       (3) test_pipeline.sh openai,anthropic:bedilk/firecrawl
  Compare single vs multi-provider results. Write to research/multi-provider-scan.md

TASK T-14: Large-repo scan — Rocket.Chat + superset (after T-1)
  Run: (1) test_pipeline.sh mongodb:bedilk/Rocket.Chat
       (2) test_pipeline.sh sentry:bedilk/superset
  These are 100k+ file repos. Monitor scan time, call-sites, any failures.
  Write to research/large-repo-scan.md

4-HOUR SMOKE TEST DUTY:
When principal sends you a message with action=smoke_test, run:
  bash scripts/smoke-real-repos.sh 6
This picks 6 random real third-party repos from real-repos.txt and scans them.
Results go to research/smoke-<timestamp>.md.
Report the summary to principal:
  python3 scripts/agent-msg.py send principal '{\"action\":\"smoke_results\",\"file\":\"research/smoke-<timestamp>.md\",\"passed\":N,\"failed\":M}'
Commit the results:
  flock .local/git.lock bash -c 'git add research/smoke-*.md && git commit -m \"tester: 4-hour smoke test\"'

COMMIT YOUR STATE after every step:
flock .local/git.lock bash -c 'git add coordination/tester.md && git commit -m \"tester: state update round $round\"'

This is round $round."

  timeout 15m claude -p \
    --model "$MODEL" \
    --permission-mode auto \
    --output-format stream-json \
    "$PROMPT" 2>&1 | tee ".local/tester-$round.log"

  rc=$?
  printf 'tester round %s exit %s %s\n' "$round" "$rc" "$(date_iso)" >> .local/tester-lifecycle.log
  [ -f "coordination/tester.stop" ] && exit 0

  sleep 60
done

[ -f "coordination/tester.stop" ] || exec bash scripts/tester-loop.sh
