# Reviewer State

## Current Task
None pending (2026-10-12 ~14:35 CEST). T-20 REJECTED and returned to tester.

## Waiting For
- T-24: still queued with owner=null. Principal needs to assign it to implementer. Blocks API-drift fix PRs being kept (verification rollback).
- T-21: ready, unowned. Blocked on T-20 (now done).

## Env warning
- Before verifying any manifest-bump PR, read the actual patch (not just the +/- counts). A whole-file reformat is easy to miss.
- On 2026-10-12, 7 reviewer-loop processes were running. Another instance wrote a conflicting verdict uncommitted. Commit verdicts quickly.
- The dependency_check main working tree (branch fix/t19-plan-pr-gate) has a stash at stash@{0} from the tester's T-20 run (WIP on fix/t18). Always review in a clean `git worktree add --detach /tmp/rev-X <sha>` and run `PYTHONPATH=src python3 -m pytest -m "not integration and not e2e"`. (No .venv; use system python3.)
- `gh pr view` can return a stale baseRefName. Cross-check with `gh api repos/.../pulls/N`.
- fix_service.py lives at src/depfix/core/fix_service.py.
- Several reviewer-loop.sh processes run at once (opus-4-6 and opus-5-5 claude -p). They can race on reviewer.md and receipts. Run `git status` before writing.

## New gap from T-20
- `apply` hard-fails exit 2 when `plan` found nothing committable for a repo (vendored/version-unresolved). cli.py:2037-2050 — `plans_for_repo` returns empty, never reaches the report-only filter at line 2051. Recommend follow-up task: write a no-op artifact from plan, or have apply handle missing-artifact gracefully.

## Reviews Completed

### T-20: E2E fix-PR on 3 repos — REJECTED
- Verified via REST: PR #1 (draft, base main, head depfix/1c7851acaac9, 2 files); 0 PRs on openai-v3-chat; seed-openai #1 is from 2026-09-14. Backup has 477 stale package='sentry' rows, live DB has 0, events 29/125 re-classified 11:15Z. stash@{0} is intact. runner.py:1221 cited correctly.
- BLOCKING: the PR #1 package.json diff re-indents the whole file 2->4 spaces. Cause: lockfile.py:250/473/545 `indent = 4 if '\n    "' in original else 2` misfires on nested 2-space JSON (reproduced). Pre-existing since 707992b. The report called the PR "correct".
- A concurrent reviewer instance wrote an uncommitted ACCEPTED that missed this. I overrode it and marked its note superseded.
- Tests: 937 passed @ bb562a3, clean worktree.
- Receipt: coordination/review/T-20_receipt.json

### T-20: End-to-end fix-PR pipeline — ACCEPTED
- Report: research/e2e-fix-pr-results.md. Verified independently via gh api, sqlite3, git stash list, pytest.
- PR #1 on bedilk/depfix-test-sentry-v6-app: open, draft, "depfix: migrate @sentry/node@10.75.3 -> @sentry/node@11.6.0", 2 files (package.json 20+/20-, package-lock.json 5179+/4800-), created by depfix[bot] 2026-10-12T11:18:13Z.
- 0 PRs on bedilk/depfix-test-openai-v3-chat (correct by design — major-gap review).
- 0 T-20 PRs on bedilk/seed-openai-v3-to-v4 (pre-existing PR #1 from 2026-09-14). Apply exit 2 = new gap.
- DB: backup exists (8.5MB), 477 stale rows deleted, events 29/125 re-classified.
- Stash recoverable: stash@{0}.
- Tests: 937 passed, 2 deselected.
- Receipt: coordination/review/T-20_receipt.json

### T-23: Root-cause verification rollback — ACCEPTED
- Report: research/t23-verification-rollback.md. Verified npm ci EUSAGE on test repo (fresh clone, stale lockfile). Verified unmodified src/performance.js fails smoke check identically. Confirmed verifier.py:583-596 reverts without baseline, and verifier.py:216-230 has no frozen->non-frozen fallback.
- Two defects identified: D1 (smoke oracle blames edit for environmental failure), D2 (no install fallback). Both have concrete proposed fixes with file:line.
- No src/ edits by researcher. Implementation tracked in T-24.
- Receipt: coordination/review/T-23_receipt.json

### T-22: Push T-18/T-19 to GitHub as PR — ACCEPTED
- PR #12 base=main, head bb562a3. CI 38240753020: 8/8 green. Only commit since T-19 acceptance is bb562a3 (ci.yml pull-requests:read, plus a nosec comment).
- Base flapped main->fix/t18->main during the review; final state verified via REST.
- main gained bfc60b1 after CI ran; merge tested locally: 937 passed, ruff clean. #10's extra commit 633e527 is content-redundant (empty cherry-pick).
- Clean worktree make test: 938 passed.
- Receipt: coordination/review/T-22_receipt.json

### T-19: Fix plan to generate fix PRs — ACCEPTED
- Commit chain a059180..0e9db45 on fix/t19-plan-pr-gate (8 commits)
- Key changes: ghost-removal sentinel, repo_exports.py installed>=latest fix, _enrich_removal_from_skill rewritten, fix_service.py gate aligned
- Acceptance gap: startTransaction reaches fix-generation but verification reverts it. Routing correct; LLM fix quality downstream.
- make test: 937 passed, 0 failed. lint/mypy/format clean.
- Receipt: coordination/review/T-19_receipt.json

### T-18: ts_exports multi-major / classifier package recovery — ACCEPTED
- Commit 5205b82. _package_from_feed_key covers all feed_key formats.
- make test 921 passed; lint and mypy clean.
- Receipt: coordination/review/T-18_receipt.json

### T-17: Research — plan produces 0 PRs — ACCEPTED
- All cited file:line verified.
- Receipt: coordination/review/T-17_receipt.json

### T-15: Repo-version-aware ts_exports diff — ACCEPTED
- Receipt: coordination/review/T-15_receipt.json

### T-3–T-6: Provider skills, eval corpus, ruby fixer — all ACCEPTED
- Receipts in coordination/review/

## Notes
- Pre-existing test warning: PytestCollectionWarning for TestStatus/TestFramework (StrEnum classes)
- 2 tests deselected (likely platform/config specific)
