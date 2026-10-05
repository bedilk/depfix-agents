# Researcher State

## Current Task
Starting T-4 research subtask (sentry eval cases) and T-7 (new provider candidates).
T-2 is done.

## Completed Work
- **T-2** (2026-10-05): Ran all 4 test_pipeline.sh commands, analyzed Python vs JS call site counts.
  Evidence: research/scan-recall-comparison.md, commit b554bca.
  Key finding: Python sentry_sdk gap — scanner detects `sentry.*` but Python apps use `sentry_sdk.*`.

## Notes
- flock not available on macOS; use Python fcntl approach:
  `python3 -c "import fcntl,subprocess; ..." (see .local/git.lock pattern in AGENTS.md)`
- Scan exit 1 is expected: eval pass rate 86% < 100% threshold, not a real failure
- T-1 done (tester): 871 pass, 1 fail, eval 86%
- T-4 depends on T-1+T-2 (both done) → can start research subtask now
- T-7 and T-8 are also ready (no dependencies)

## Next Steps
1. Start T-4 research: study eval YAML format + sentry v7→v8 changelog
2. Optionally take T-7 (new provider candidates) or T-8 (top 10 providers by breakage)
