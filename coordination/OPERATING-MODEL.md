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

## Human-in-the-Loop Review

Every 4 hours, `scripts/human-review.sh` pauses all agents and produces a summary for human review.

The cycle:
1. The script creates `.stop` files for all agents (graceful pause after current round)
2. Generates `coordination/HUMAN-REVIEW.md` with: task status, recent commits, open issues, agent health
3. Human reviews, edits TASKS.json or AGENTS.md as needed, then runs `bash scripts/human-review.sh --resume`
4. Resume clears `.stop` files and restarts all agents

To run manually at any time: `bash scripts/human-review.sh`
To schedule automatic 4-hour cycles: `bash scripts/human-review.sh --schedule`

## Boundaries

- Do NOT open real GitHub PRs without explicit user approval.
- Do NOT run `depfix pipeline` on repos you do not own (only seed repos and depfix-agents itself).
- Do NOT modify `.env` or `depfix.db` structure without recording the change in your state file.
- Do NOT delete or overwrite another agent's committed files.
- All test commands: use `make test`, `make eval`, `bash scripts/test_pipeline.sh`.
