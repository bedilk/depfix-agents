# T-23: Why verification reverts the enriched startTransaction / getCurrentHub fixes

**Date:** 2026-10-12 · **Branch:** `dependency_check` `fix/t19-plan-pr-gate` @ `bb562a3` · **Author:** researcher (read-only, no src/ edits)

## TL;DR

The LLM fixes are never judged on their merits. Verification reverts them **because the test
repo's `package-lock.json` is out of sync with `package.json`** (`connect@3.7.0` is missing from the
lockfile). Here is the chain:

1. The fix pipeline's `Verifier` runs a **frozen** install (`npm ci`). The bump/drift path uses
   `frozen_install=False` (`npm install`). `npm ci` exits with `EUSAGE` ("package.json and
   package-lock.json … not in sync").
2. When the install fails, the verifier goes to `_decide_without_tests` and then `suspect()`. It never
   runs tests.
3. `suspect()` runs a per-file **module-load smoke check** (`node -e "require(file)"`). There is no
   `node_modules`, so `require("@sentry/node")` throws `Cannot find module '@sentry/node'`.
4. The smoke failure **reverts the edit unconditionally**. There's no baseline comparison: the
   *unmodified* file fails the same way. The result is `REVERTED` for every edit, and the change
   reports `no_kept_edits`.

The retry loop can't recover. A smoke revert carries no test attribution, so `_find_retryable`
skips it.

**Two defects (both need fixing):**
- **D1 (root cause, correctness):** the smoke oracle blames the edit for an environmental failure.
  It must compare against the original file before it reverts.
- **D2 (signal loss):** the fix-path verifier has no fallback when a frozen install fails on a stale
  lockfile, so tests never run. Many real repos have slightly stale lockfiles.

## Reproduction

```bash
# 1. Full pipeline, read-only (no PR, no apply). Log kept at /tmp/t23_plan.log (2389 lines)
cd /Users/bedil_karimov/Documents/dependency_check
set -a && source .env && set +a
depfix --log-level DEBUG plan bedilk/depfix-test-sentry-v6-app --provider sentry > /tmp/t23_plan.log 2>&1
grep -n "no_kept_edits\|reverted --\|installing dependencies\|running tests\|Generated fix" /tmp/t23_plan.log
```

Relevant output (`/tmp/t23_plan.log`):
```
161  generating and verifying a fix for 1c7851acaac9          # drift bump
162  installing dependencies: npm install --ignore-scripts      # non-frozen → OK
163  running tests: npm test -- --json ...                      # tests RUN for drift path
201  generating and verifying a fix for a49fb6c59168            # startTransaction
...  Generated fix for src/performance.js / src/tracing.js
319  installing dependencies: npm ci --ignore-scripts           # frozen → fails; NO "running tests" follows
324  generating and verifying a fix for 621952969f19            # getCurrentHub
375  installing dependencies: npm ci --ignore-scripts           # same; no tests
     impact check skipped: baseline install failed (install error)
449  @sentry/node sentry.startTransaction: no_kept_edits
451    src/performance.js: reverted -- this fix was rolled back by verification
452    src/tracing.js: reverted -- this fix was rolled back by verification
454  @sentry/node sentry.getCurrentHub: no_kept_edits
456    src/tracing.js: reverted -- this fix was rolled back by verification
```

```bash
# 2. Why npm ci fails: the target repo lockfile is stale
gh repo clone bedilk/depfix-test-sentry-v6-app /tmp/t23-repo   # HEAD 349b58d
cd /tmp/t23-repo && npm ci --ignore-scripts
# npm error code EUSAGE
# npm error `npm ci` can only install packages when your package.json and package-lock.json ... are in sync.
# npm error Missing: connect@3.7.0 from lock file   (+ finalhandler, encodeurl, on-finished, statuses)
```

```bash
# 3. Smoke check fails on the UNMODIFIED files when node_modules is absent
cd /tmp/t23-repo   # fresh clone, no node_modules, no edits
node -e "try { require('$PWD/src/tracing.js'); } catch(e) { console.error(e.message); process.exit(1); }"
# Cannot find module '@sentry/node'   → exit 1   (same for src/performance.js)
```

```bash
# 4. Same thing through depfix's own functions, fresh clone, unmodified files (decisive A/B)
git clone -q /tmp/t23-repo /tmp/t23-repo2 && cd /tmp/t23-repo2
/Users/bedil_karimov/Documents/.venv/bin/python - <<'EOF'
from pathlib import Path
from depfix.verify.manager import install_dependencies
from depfix.verify.smoke import run_smoke_check
root = Path('/tmp/t23-repo2')
for frozen in (True, False):
    r = install_dependencies(root, timeout=300, frozen=frozen)
    print('frozen=', frozen, 'ok=', r.ok, 'reason=', repr(r.skipped_reason))
    for f in ('src/performance.js', 'src/tracing.js'):
        s = run_smoke_check(root, f); print('  smoke', f, s.ran, s.passed, (s.error or '')[:60])
EOF
```
Output:
```
frozen= True ok= False reason= ''
  smoke src/performance.js True False Cannot find module '@sentry/node' ...
  smoke src/tracing.js True False Cannot find module '@sentry/node' ...
frozen= False ok= True reason= ''
  smoke src/performance.js True True
  smoke src/tracing.js True True
```
Note the `''` reason: an install that runs and fails returns no `skipped_reason`. That is why
the report only says the generic "install error" and drops the npm `EUSAGE` text.

```bash
# 5. With a working install, tests run and the fixed files aren't covered by them
cd /tmp/t23-repo && npm install --ignore-scripts && npx jest --passWithNoTests
# Tests: 2 failed, 8 passed (baseline; pre-existing failures in src/sentry.test.js, unrelated to performance.js/tracing.js)
node -e "const S=require('@sentry/node');console.log(typeof S.startSpan, typeof S.getCurrentScope, typeof S.startTransaction)"
# function function undefined   → installed 10.75.3 already has startSpan/getCurrentScope; old APIs are gone
```
With a working install, the verifier compares new failures against the baseline
(`verifier.py:293`). The fixes don't touch any tested file, so they would settle `KEPT`.

## Code path (file:line, `fix/t19-plan-pr-gate` @ bb562a3)

| Step | Location | What happens |
|---|---|---|
| Fix-pipeline verifier built **without** `frozen_install` | `src/depfix/core/fix_service.py:75-94` | Default `frozen_install=True` (`src/depfix/verify/verifier.py:143`) |
| Drift/upgrade verifiers set `frozen_install=False` | `src/depfix/core/fix_service.py:587`, `src/depfix/core/upgrade_service.py:203` | This is why the bump PR verified fine (log line 162-164) |
| Frozen + lockfile → `npm ci` | `src/depfix/verify/manager.py:236-247` | `npm ci` hard-fails on stale lockfile |
| Install not ok → no tests | `src/depfix/verify/verifier.py:216-230` | goes to `_decide_without_tests(... skipped_reason=install.skipped_reason or "dependency install failed")` |
| JS + failed install → `suspect()` | `src/depfix/verify/verifier.py:653-668` | `resolved_install = install` (failed) → `suspect("could not install dependencies for a typecheck …")` |
| **Smoke reverts unconditionally** | `src/depfix/verify/verifier.py:583-596` | `run_smoke_check` fails → `self._editor.revert(...)` + `EditVerdict.REVERTED`, **no check that the original file loads** |
| Smoke = bare `require()` | `src/depfix/verify/smoke.py:72-81` | Needs `node_modules`; fails on any file importing a dependency when install failed |
| Retry can't help | `src/depfix/retry/loop.py:153-158` | `REVERTED` only retryable with `verification.attribution` (test attribution); smoke reverts have none |
| User-facing message | `src/depfix/core/explain.py:103` | "this fix was rolled back by verification": hides the real cause (install failure + smoke env error) |
| Impact check also frozen | `src/depfix/verify/impact.py:134-140` | Same `npm ci` failure ("baseline install failed (install error)") |

## Proposed changes (for implementer)

### Change 1 (required, fixes D1): smoke check must prove the edit caused the failure
`src/depfix/verify/verifier.py`, inside `suspect()`'s per-file smoke loop (lines 583-596).
When smoke fails on an edit, revert it and re-run smoke on the original. Keep the revert only if
the original loads:

```python
for edit in on_disk:
    smoke = run_smoke_check(typecheck_root, edit.relpath)
    if not (smoke.ran and not smoke.passed):
        continue
    self._editor.revert(edit.relpath)
    original_smoke = run_smoke_check(typecheck_root, edit.relpath)
    if original_smoke.ran and not original_smoke.passed:
        # Original fails identically: environmental (e.g. no node_modules), not the edit's fault.
        # Restore the edit and leave it SUSPECT (already marked by _mark_suspect above).
        (Path(root) / edit.relpath).write_text(edit.fixed_content)   # or the editor's write API
        smoke_inconclusive.append(f"{edit.relpath}: original also fails to load ({original_smoke.error[:120]})")
        continue
    settled = tuple(... EditVerdict.REVERTED ...)   # existing code
    smoke_failures.append(...)
```
Add `smoke_inconclusive` to `reason` so the report explains what happened.
Use the editor's existing write path (`src/depfix/apply/workspace.py:67 write_fix`) rather than a
raw write if its signature allows, so editor state stays consistent.

**Expected effect:** the edits stay `SUSPECT` (tier LOW) instead of `REVERTED`.
Check before claiming the effect: does `SUSPECT` produce a planned PR or a draft/needs-review PR
under the current plan policy? Read `src/depfix/core/upgrade_service.py:211` and the fix-path
equivalent, then confirm with a dry-run. Either way, a correct fix no longer gets thrown away.

Tests to add (`tests/verify/`):
- smoke fails on edit **and** on original → edit stays on disk, verdict `SUSPECT`, not `REVERTED`
- smoke fails on edit, passes on original → `REVERTED` (current behaviour preserved)

### Change 2 (recommended, fixes D2): fall back to non-frozen install when the lockfile is stale
`src/depfix/verify/verifier.py:216-230` (and the same pattern at `src/depfix/verify/impact.py:134`):
if the frozen install fails, retry once with `frozen=False` and record the fallback in the report:

```python
install = install_dependencies(root, ..., frozen=self._frozen_install)
if not install.ok and self._frozen_install:
    logger.info("frozen install failed; retrying non-frozen (lockfile may be out of sync)")
    install = install_dependencies(root, ..., frozen=False)
```
Rationale: fix-path edits don't touch manifests, so a non-frozen install resolves the same
pinned versions plus the entries missing from the lockfile. The drift path already accepts
non-frozen installs (`fix_service.py:587`). Downside: `npm install` rewrites `package-lock.json` in
the checkout (`git status` shows `M package-lock.json` after step 5). The PR must not commit
that incidental lockfile change. Confirm the committer only stages `FileEdit` relpaths before
merging this.

Narrower alternative: fall back only when npm's output contains `EUSAGE` / "in sync".

Tests: frozen install fails → non-frozen retried → tests run (mock `install_dependencies`).

### Change 3 (small, diagnostics)
Have `install_dependencies` (`src/depfix/verify/manager.py` around line 350+, the run-and-fail
branch) put the first stderr line in `skipped_reason`. Right now a real npm failure reports `''`,
and the user sees "install error" / "rolled back by verification" with no cause.

## Validation plan after the fix
```bash
depfix --log-level DEBUG plan bedilk/depfix-test-sentry-v6-app --provider sentry 2>&1 | \
  grep -E "startTransaction|getCurrentHub|running tests|frozen install failed"
```
Expected with Change 1 + 2: `running tests` appears after each fix's install. The startTransaction
and getCurrentHub edits settle `KEPT`, since neither touched file is covered by the 2 baseline
failures. Change 1 alone gives `SUSPECT`, not `REVERTED`.

## Side observation (not the cause)
The test repo itself (`bedilk/depfix-test-sentry-v6-app`, HEAD 349b58d) has a stale lockfile.
Regenerating it would hide the bug on this repo without fixing depfix. **Do not** fix the
fixture instead of the code; real customer repos have stale lockfiles too.

## Artifacts
- `/tmp/t23_plan.log`: full DEBUG plan run (13:08-13:09 CEST)
- `/tmp/t23_npmci.log`: `npm ci` EUSAGE output
- `/tmp/t23-repo`, `/tmp/t23-repo2`: scratch clones (not in dependency_check)
- `depfix.db` backed up to `/tmp/t23_depfix.db.bak` before the plan run
