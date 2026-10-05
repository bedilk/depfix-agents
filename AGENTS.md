# depfix Agent Team

Repo: /Users/bedil_karimov/Documents/depfix-agents
Project: Ongoing development of depfix — the AI-powered breaking-dependency-change fixer.

This repo is a working copy of `dependency_check`. All agent work (research, code, tests, reviews)
happens here. Do not modify /Users/bedil_karimov/Documents/dependency_check directly.

---

## Team and Roles

| Role | Tag | Model | Rate limit | Owns |
|---|---|---|---|---|
| Principal | `principal` | claude-opus-4-6 | 25 req/min shared | coordination/principal.md, task dispatch, oversight |
| Researcher | `researcher` | claude-sonnet-4-6-1m | 10 000 req/min | coordination/researcher.md, research/ outputs |
| Implementer | `implementer` | claude-sonnet-4-6 | 10 000 req/min | coordination/implementer.md, src/ edits |
| Reviewer | `reviewer` | claude-opus-4-6 | 25 req/min shared | coordination/reviewer.md, adversarial review |
| Tester | `tester` | claude-sonnet-4-6 | 10 000 req/min | coordination/tester.md, test runs, reports |

**Opus budget (25 req/min total):** principal + reviewer share this pool. Principal runs one round
every ~5 minutes; reviewer runs one round per review task. Keep rounds tight. Never run both
simultaneously in tight loops.

---

## Startup Protocol (every agent, every round)

1. Read AGENTS.md (this file) and CONTEXT.md
2. Read coordination/OPERATING-MODEL.md
3. Read your own coordination/<role>.md (your durable state)
4. Read coordination/TASKS.json (the live task ledger)
5. Read coordination/inbox/<role>.jsonl (your messages — ack each after reading)
6. Resume from your state file rather than re-reading everything from scratch

Do this at the top of every round. Your state file is the durable fallback.

---

## Task Lifecycle

```
queued → ready → running → review → done
                         → rejected → running (repair)
                         → blocked
```

- **queued**: defined, not yet ready (waiting on a dependency)
- **ready**: all dependencies met, free to assign
- **running**: an agent is working on it
- **review**: implementer/tester done, awaiting reviewer
- **done**: reviewer accepted, evidence committed
- **rejected**: reviewer found critical issues, returns to implementer
- **blocked**: genuine external blocker (not just idle)

Every task in TASKS.json has: `id`, `title`, `status`, `owner`, `depends_on`, `acceptance`,
`evidence_paths`, `next_action`, `notes`.

---

## Review Gate

**No task moves from `review` → `done` without a reviewer verdict.**

When an implementer finishes a task:
1. Set `status: review` in TASKS.json, set `owner: reviewer`
2. Write a summary to `coordination/inbox/reviewer.jsonl`:
   `{"from":"implementer","task_id":"T-N","action":"review_request","summary":"what changed","commit":"<sha>"}`
3. Reviewer reads the commit, runs the tests, checks the diff adversarially
4. Reviewer writes `coordination/review/<task_id>_receipt.json`:
   `{"task_id":"T-N","verdict":"ACCEPTED"|"REJECTED","issues":["..."],"reviewer_commit":"<sha>"}`
5. If ACCEPTED: reviewer sets `status: done` in TASKS.json
6. If REJECTED: reviewer sets `status: rejected`, adds issues to notes; implementer fixes and re-submits

---

## Messaging (file-based inbox)

Use `python3 scripts/agent-msg.py send <to> <json>` to send a message.
Use `python3 scripts/agent-msg.py inbox <role>` to read your inbox.
Use `python3 scripts/agent-msg.py ack <role> <id>` to acknowledge.

Messages are append-only JSONL in `coordination/inbox/<role>.jsonl`.
Format: `{"id":"<uuid>","from":"<role>","to":"<role>","ts":"<iso>","body":{...}}`

---

## Coordination Rules

- **Commit under git lock:** `flock .local/git.lock git commit ...`
- **Only edit your owned files** (or files explicitly assigned to you in a task). Do not overwrite
  peer work. Ask via inbox before touching another agent's area.
- **Never invent results.** A claim is not evidence. Every finding needs a reproducible command or
  file path. Every test result needs a real test run.
- **Incremental saves.** Commit intermediate work. Do not hold large diffs until the end.
- **State your blocker.** If genuinely blocked, write it to TASKS.json and your state file with
  a concrete next step. Silence is not a status.
- **Challenge the approach.** If you believe a task's acceptance criteria or approach is wrong,
  say so in your inbox message — do not silently change direction.

---

## Depfix Domain

Key concepts (full detail in CONTEXT.md and docs/decisions.md):
- Pipeline: `init → watch → scan → plan → apply`
- `fix_supported` ecosystems: javascript, python, ruby (Go is scan-only)
- `breaking_change.source` must be a valid `ClassificationSource` enum value
- `REPORT_ONLY`: removals with no replacement — no LLM fix, no PR
- Plan artifacts are immutable; `apply` never re-calls the LLM
- Providers config: `providers.yaml`; 25 providers
- Test command: `bash scripts/test_pipeline.sh provider:bedilk/repo`
- Unit tests: `make test` (no LLM, no network)
- LLM_PROVIDER=bedrock, BEDROCK_PROFILE=Bedil

**Do not run `depfix pipeline` or open real PRs against repos you do not control.**
Use `--dry-run` and `--no-pr` for all testing.

---

## Resource Policy

- **Opus 4.6 / 4.5**: principal + reviewer combined ≤ 25 req/min. Space rounds ≥ 2 min apart.
- **Sonnet 4.6 / 4.6 1M**: researcher, implementer, tester — no practical cap, use freely.
- **Disk**: do not copy node_modules, .venv, or build artifacts into new directories.
- **DB**: depfix.db is the live SQLite. Always back up before schema changes.
- **No real PRs** without explicit user approval.
- **No purchases, no external API calls** beyond what depfix already makes in normal operation.

---

## Principals' Mutual Check

Principal oversees all agents. After every 2 rounds, principal checks:
- Which tasks moved to `done` since last check?
- Which tasks are `running` with no evidence update in >10 min?
- Does the reviewer have a backlog?
- Are any tasks `blocked` with no owner and no next action?

Principal sends accountability pings via inbox to stalled agents.

---

## Initial Task Backlog

See coordination/TASKS.json. Starting tasks (ordered by value):
1. Run full test suite, report failures (tester)
2. Expand eval corpus — 10 new sentry cases (implementer + researcher)
3. Add provider skill files for redis and postgresql (implementer)
4. Review scan recall: Python vs JS call_site count comparison on 3 repos (researcher)
5. Add 5 eval cases for ruby ecosystem (implementer)
6. Adversarial review of the ruby fixer implementation (reviewer)
7. Research: identify 3 new provider candidates with OpenAPI specs available (researcher)

Principal assigns and sequences these on first run.
