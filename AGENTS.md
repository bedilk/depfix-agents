# depfix Agent Team

Repo: /Users/bedil_karimov/Documents/depfix-agents
Project: Building depfix — the missing application layer connecting API providers to their
customers' codebases. Like Dependabot, but for APIs.

**The problem:** API communication is broken. Breaking changes ship with little warning, useful
features go unnoticed, changelogs don't get read. Over 30% of service downtime at AWS was due to
external API/package changes going unnoticed.

**What depfix does:** watches repos for breaking provider API/SDK version changes, finds version
drifts (minor bumps + major breaking), locates every affected call-site in code, generates version
bumps and LLM-written fixes, runs tests to verify, and opens a PR — all automatically.

**Read CONTEXT.md** for the full vision, pipeline details, and domain glossary.

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

## Boundary: depfix-agents ONLY

**CRITICAL: This repo (`depfix-agents`) is the ONLY repo agents may write to or push from.**

- `git push agents <branch>` — ONLY allowed push command
- `git push origin ...` — FORBIDDEN. The `origin` push URL is intentionally disabled.
- Do NOT cd into `/Users/bedil_karimov/Documents/dependency_check` or edit any file there.
- `dependency_check` is read-only reference material; treat it like a third-party library.

Every loop script enforces this with: `git remote set-url --push origin DISABLED_...`

---

## Commit Gate (mandatory)

**Every code change must pass the commit gate before it can be reviewed or marked done.**

```bash
bash scripts/commit-gate.sh    # runs: make test + make lint + make typecheck + git push agents + CI check
```

- **Implementer** runs it before submitting for review. Broken code = immediate reject.
- **Reviewer** runs it after ACCEPTING to push and trigger CI. If CI fails, verdict becomes REJECTED.
- No task reaches `done` without a pushed commit and **passing CI** (commit-gate waits for CI result).
- If CI fails, the commit-gate exits with code 3 — treat this as a REJECTED task and fix the failures.

State files (*.md, TASKS.json) don't need the gate — only code in `src/`, `tests/`, `providers.yaml`,
`scripts/`, or eval corpus YAML.

## Rate Limit Handling

If any LLM call returns a 429 error (rate limit / overloaded), the loop script automatically waits
30 minutes before retrying. Do not spin. Write your current state to your *.md file before sleeping.

---

## 4-Hour Real-Repo Smoke Test

Every 4 hours, depfix scans 5-6 real third-party repos (not our forks — actual popular open-source
projects that use provider SDKs) to verify the scanner works on production codebases.

```bash
bash scripts/smoke-real-repos.sh 6    # picks 6 random repos from real-repos.txt
```

Repos include: chatbot-ui (openai), cal.com (sentry+prisma), discord.js (discord),
Rocket.Chat (mongodb), bolt-js (slack), nextjs-subscription-payments (stripe), and 50+ more.

The smoke test runs automatically as part of `scripts/human-review.sh` (the 4-hour cycle).
Results go to `research/smoke-<timestamp>.md`. Principal triggers tester to run it if the
last smoke is >4 hours old.

---

## Depfix Domain

**Mission:** Build the application layer that connects API providers to their customers' codebases.
When Stripe ships a breaking change, an agent should scan customer codebases, identify affected
usages, and open a PR with the fix.

**Pipeline:** `init → watch → scan → plan → apply`
- **Watch**: poll provider feeds for new versions and breaking changes
- **Scan**: clone repo, find call-sites, detect version drift (minor + major)
- **Plan**: generate LLM-written fixes for breaking changes, version bumps for minor drift
- **Apply**: apply fixes, run tests, open PR

**Current state:**
- 25 providers in `providers.yaml` (stripe, openai, anthropic, sentry, mongodb, etc.)
- 3 fix-supported ecosystems: JavaScript, Python, Ruby (Go is scan-only)
- `breaking_change.source` must be a valid `ClassificationSource` enum value
- `REPORT_ONLY`: removals with no replacement — no LLM fix, no PR
- Plan artifacts are immutable; `apply` never re-calls the LLM
- 8 seed repos (`bedilk/seed-*`) for controlled testing
- Test: `bash scripts/test_pipeline.sh provider:bedilk/repo`
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

## Human-in-the-Loop Review

Every 4 hours, the team pauses for human review. This ensures no agent drifts off-track
and gives you a checkpoint to reprioritize, add tasks, or fix issues.

**Automatic schedule:**
```bash
bash scripts/human-review.sh --schedule   # installs a 4-hour launchd timer
```

**Manual review at any time:**
```bash
bash scripts/human-review.sh              # pause agents, generate summary
# ... review coordination/HUMAN-REVIEW.md, edit TASKS.json as needed ...
bash scripts/human-review.sh --resume     # restart all agents
```

**What the review summary includes:**
- Task status table (from TASKS.json)
- Last 15 commits
- Agent lifecycle logs (last 5 lines each)
- Review receipts
- Unacked inbox messages per agent

**Your powers during review:**
- Edit `coordination/TASKS.json` to add, modify, or reprioritize tasks
- Edit `AGENTS.md` to change instructions or constraints
- Send direct messages: `python3 scripts/agent-msg.py send <role> '{"action":"human_directive","msg":"..."}'`

---

## Initial Task Backlog

See coordination/TASKS.json. Tasks advance depfix toward production-ready "Dependabot for APIs":

**Foundation (do first):**
1. T-1: Run full test suite, establish baseline health (tester)
2. T-2: Measure scan recall — are we finding all call-sites? (researcher)

**Broader provider coverage:**
3. T-3: Add redis + postgresql provider skills (implementer)
4. T-7: Research 3 new high-value providers with OpenAPI specs (researcher)
5. T-8: Rank top 10 API providers by breaking-change frequency — prioritize who to add next (researcher)

**Deeper detection accuracy:**
6. T-4: 10 sentry eval cases — prove we catch real v7→v8 migrations (implementer + researcher)
7. T-5: 5 ruby eval cases — prove ruby ecosystem detection works (implementer)
8. T-9: Audit version drift detection — do we catch both minor and major correctly? (researcher)

**Hardened fixers:**
9. T-6: Adversarial review of ruby fixer — find real bugs before users hit them (reviewer)

**End-to-end proof (seed repos):**
10. T-10: Dry-run full pipeline on 3 seed repos (tester)

**Real-repo validation (the ground truth):**
11. T-11: Scan all 7 forked repos with test_all_repos.sh — octokit, slack, discord, mongodb (tester)
12. T-12: Scan 3 e2e test repos — sentry-v6, openai-v3, anthropic-callsites (tester)
13. T-13: Multi-provider scan on firecrawl — openai + anthropic single and combined (tester)
14. T-14: Large-repo stress test — Rocket.Chat (mongodb) + superset (sentry) at 100k+ files (tester)

Principal assigns and sequences these on first run.
T-11 through T-14 are the ground truth: if depfix can't find real call-sites in real repos, the product doesn't work.
