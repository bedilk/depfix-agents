# depfix Agent Team — Operating Model

## Work Loop

Each agent runs a shell loop. Every round:
1. Read startup docs (AGENTS.md, your state file, TASKS.json, inbox)
2. Pick up or continue your assigned task
3. Do real work (read code, write code, run tests, research)
4. Commit incremental progress under git lock
5. Update your state file and TASKS.json
6. Send inbox messages as needed
7. Sleep and loop

## Task Assignment Flow

```
Principal reads TASKS.json
  → assigns ready tasks to idle agents (writes task.owner, task.status=running)
  → sends inbox message to assigned agent
Agent receives message, starts task
  → commits incremental work
  → when done: sets status=review, messages reviewer
Reviewer reads inbox
  → adversarially reviews the commit
  → writes coordination/review/<task_id>_receipt.json
  → sets status=done or status=rejected in TASKS.json
  → messages implementer/tester with verdict
Principal checks progress every 2 rounds
  → pings idle agents with ready tasks
  → escalates stalled tasks
```

## Evidence Policy

- A task is NOT done because an agent says it is done.
- A task is done when: (a) reviewer wrote ACCEPTED in the receipt, AND (b) evidence_paths exist and are committed.
- Test results must come from actual `pytest` / `make test` runs, not descriptions.
- Research findings must include real file paths or reproducible commands, not paraphrases.

## Commit Protocol

All commits use the git lock to avoid conflicts:

```bash
flock .local/git.lock bash -c 'git add <specific-files> && git commit -m "role(task): description"'
```

Commit message format: `<role>(<task-id>): <description>`
Examples:
- `implementer(T-3): add provider_redis.md skill file`
- `tester(T-1): run full test suite, 2 failures found`
- `reviewer(T-3): ACCEPTED - redis+postgresql skill files`

Never `git add -A` or `git add .` — stage only your owned files.

## Commit Gate (mandatory for code changes)

**Every code change must pass all three gates before it can be considered done:**

```
1. LOCAL TESTS    →  make test + make lint + make typecheck must all pass
2. COMMIT + PUSH  →  commit under git lock, then push to agents remote
3. CI             →  GitHub Actions CI must pass (lint, test, eval, docker)
```

**Who runs the gate:**

- **Implementer**: before setting status=review, run `bash scripts/commit-gate.sh`.
  If it fails, fix the code and re-run. Do NOT submit broken code for review.
- **Reviewer**: after ACCEPTING a task, run `bash scripts/commit-gate.sh` to push
  the accepted code and verify CI. If CI fails, REJECT and reopen.
- **Tester**: after T-1 baseline and after re-testing implementer commits, run
  `bash scripts/commit-gate.sh --test-only` to verify local tests still pass.

**The gate script (`scripts/commit-gate.sh`) does:**
1. `make test` — unit tests
2. `make lint` — ruff check
3. `make typecheck` — mypy
4. `git push agents <branch>` — push to GitHub
5. Logs the pushed SHA to `.local/push-history.log`

**Rule: no task moves to `done` unless the latest commit has been pushed and CI is green.**
State files and coordination commits (*.md, TASKS.json) don't need the full gate — only
code changes in `src/`, `tests/`, `providers.yaml`, `scripts/`, or eval corpus YAML.

## Rate Limit Observance

Principal and reviewer share the 25 req/min Opus pool:
- Principal: run one claude round, then sleep 120s minimum before next round
- Reviewer: run one review round per task; wait for principal's sleep window
- If both need to run in the same 2-minute window: reviewer defers to next window

Researcher, implementer, tester: run on Sonnet 4.6. No effective rate limit. 
Can run multiple concurrent rounds on different tasks (see run-team.sh).

## Research Directory Layout

```
research/
├── <topic>.md          — research outputs (researcher owns these)
└── sentry-eval-cases.md, scan-recall-comparison.md, new-provider-candidates.md ...
```

## Review Directory Layout

```
coordination/review/
├── T-3_receipt.json    — reviewer verdict for task T-3
├── T-4_receipt.json    — reviewer verdict for task T-4
└── ...
```

Receipt schema:
```json
{
  "task_id": "T-N",
  "verdict": "ACCEPTED",
  "issues": [],
  "tests_run": "make test: 623 passed, 0 failed",
  "reviewer_commit": "abc123",
  "timestamp": "2026-10-05T13:00:00Z"
}
```

## Stall Detection

Principal checks every 2 rounds for tasks that have been `running` for >15 min with no new commit.
If found: principal sends accountability ping to the task owner via inbox.
If no response after next round: principal reassigns the task.

## Dynamic Task Creation

Agents may propose new tasks. The protocol:
1. Agent sends a message to principal with `{"action":"propose_task","title":"...","rationale":"...","suggested_owner":"..."}`
2. Principal validates the proposal, assigns an ID (T-8, T-9, ...), and adds it to TASKS.json
3. Principal assigns the task via the normal assignment flow

Only principal may write new tasks to TASKS.json. Other agents propose; principal decides.

## 4-Hour Smoke Test on Real Repos

Every 4 hours (aligned with the human review cycle), depfix scan runs against 5-6 real
third-party repos to verify the scanner works on production codebases.

**What it does:**
1. Picks 6 random repos from `real-repos.txt` (popular open-source projects that use provider SDKs)
2. Runs `scripts/test_pipeline.sh` on each (scan only — no PRs, no mutations)
3. Writes results to `research/smoke-<timestamp>.md` with a table: repo, provider, files scanned,
   call-sites found, actionable count, pass/fail

**How to run:**
```bash
bash scripts/smoke-real-repos.sh          # 6 random repos
bash scripts/smoke-real-repos.sh 3        # 3 random repos
bash scripts/smoke-real-repos.sh --all    # all repos in real-repos.txt
```

**Real repos in the pool** (from `real-repos.txt`):
- openai: chatbot-ui, chatgpt-api, openai-cookbook, dify
- stripe: nextjs-subscription-payments, accept-a-payment, saas-starter-kit
- sentry: sentry-javascript, cal.com, twenty
- anthropic: pydantic-ai, anthropic-quickstarts
- mongodb: parse-server, mongoose, Rocket.Chat
- discord: discord.js, discord.py
- slack, firebase, twilio, octokit, langchain, posthog, elasticsearch, and more

**Tester responsibility:** after T-1 is done, tester runs the smoke test every 4 hours
(principal triggers it). If any scan regresses from a previous run, tester files a bug.

## Human-in-the-Loop Review

Every 4 hours, `scripts/human-review.sh` pauses all agents and produces a summary for human review.
The smoke test runs as part of this cycle.

The cycle:
1. The script runs `scripts/smoke-real-repos.sh` (real-repo scan)
2. Creates `.stop` files for all agents (graceful pause after current round)
3. Generates `coordination/HUMAN-REVIEW.md` with: task status, smoke results, recent commits, agent health
4. Human reviews, edits TASKS.json or AGENTS.md as needed, then runs `bash scripts/human-review.sh --resume`
5. Resume clears `.stop` files and restarts all agents

To run manually at any time: `bash scripts/human-review.sh`
To schedule automatic 4-hour cycles: `bash scripts/human-review.sh --schedule`

## Boundaries

- Do NOT open real GitHub PRs without explicit user approval.
- Do NOT run `depfix pipeline` on repos you do not own (only seed repos and depfix-agents itself).
- Do NOT modify `.env` or `depfix.db` structure without recording the change in your state file.
- Do NOT delete or overwrite another agent's committed files.
- All test commands: use `make test`, `make eval`, `bash scripts/test_pipeline.sh`.
