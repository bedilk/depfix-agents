#!/usr/bin/env bash
# Reviewer agent loop — task-driven, no round counter.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
export AGENT_ROLE=reviewer

timeout() { if command -v gtimeout >/dev/null; then gtimeout "$@"; else command timeout "$@"; fi; }
date_iso() { if command -v gdate >/dev/null; then gdate -Iseconds; else date +%Y-%m-%dT%H:%M:%S%z; fi; }

mkdir -p .local coordination/review

MODEL="claude-opus-5-5"

while true; do
  [ -f "coordination/reviewer.stop" ] && exit 0
  TS="$(date_iso)"
  LOGFILE=".local/reviewer-$(date +%Y%m%d-%H%M%S).log"

  printf 'reviewer started %s\n' "$TS" >> .local/reviewer-lifecycle.log

  PROMPT="You are the reviewer agent in /Users/bedil_karimov/Documents/depfix-agents.
You are an adversarial code reviewer. Your job is to find real bugs, not rubber-stamp work.

STARTUP PROTOCOL:
1. Read AGENTS.md
2. Read coordination/reviewer.md (your durable state)
3. Read coordination/TASKS.json — find tasks with status=review
4. Run: python3 scripts/agent-msg.py inbox reviewer — read and ack messages
5. Resume from your state file

ADVERSARIAL REVIEW CHECKLIST:
For each file changed in the review commit:
- Does this break any existing tests? (run make test to confirm)
- Are there edge cases not handled? (empty input, missing keys, large input)
- Does the code match the existing style (ruff format, type hints)?
- Is the logic actually correct, or does it just look correct?
- Are there obvious improvements that would prevent future bugs?

FOR EACH REVIEW:
1. Read the commit: git show <commit-sha> or git diff HEAD~1
2. Read the full changed files (not just the diff)
3. Run make test
4. Write coordination/review/<task_id>_receipt.json:
   {
     \"task_id\": \"T-N\",
     \"verdict\": \"ACCEPTED\" or \"REJECTED\",
     \"issues\": [\"specific issue 1\", ...],
     \"tests_run\": \"make test: N passed, M failed\",
     \"timestamp\": \"<iso>\"
   }
5. Update TASKS.json:
   - ACCEPTED: set status=done
   - REJECTED: set status=rejected, add issues to task.notes
6. Commit: flock .local/git.lock bash -c 'git add coordination/review/<task_id>_receipt.json coordination/TASKS.json coordination/reviewer.md && git commit -m \"reviewer(T-N): ACCEPTED/REJECTED\"'
7. Send verdict to implementer and principal via inbox

IMPORTANT — Do not rubber stamp:
- 'Looks good' is not a review. Every ACCEPTED verdict needs: tests_run + at least 2 specific things you checked.
- If you find a real bug: REJECT and describe exactly what is wrong.
- If tests fail: REJECT immediately.

Update coordination/reviewer.md after every wake-up."

  git remote get-url --push origin 2>/dev/null | grep -q DISABLED || git remote set-url --push origin DISABLED_DO_NOT_PUSH_TO_DEPENDENCY_CHECK

  timeout 15m claude -p \
    --model "$MODEL" \
    --dangerously-skip-permissions \
    "$PROMPT" 2> >(grep -v 'Permission allow rule' >&2) | tee "$LOGFILE"

  rc=$?
  printf 'reviewer exit %s %s\n' "$rc" "$(date_iso)" >> .local/reviewer-lifecycle.log
  [ -f "coordination/reviewer.stop" ] && exit 0

  if grep -q "429\|rate.limit\|overloaded\|Too Many Requests" "$LOGFILE" 2>/dev/null; then
    printf 'reviewer 429 — sleeping 30 min %s\n' "$(date_iso)" >> .local/reviewer-lifecycle.log
    sleep 1800
  else
    sleep 120
  fi
done
