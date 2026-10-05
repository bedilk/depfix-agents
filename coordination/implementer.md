# Implementer State

## Current Task
T-5 complete — submitted for review.

## Completed Work
- T-3: Added provider_redis.md skill file covering ioredis, node-redis v3/v4 (with breaking-change notes), redis-py, redis gem.
  - provider_postgresql.md was already present and complete.
  - Fixed pre-existing test failure: test_repo_shipped_providers_file_is_valid expected 25 providers but providers.yaml had 27 (mysql + astro added before my round). Updated count to 27.
  - make test: 872 passed, 0 failed.
  - make typecheck: pre-existing failure (mypy + numpy on Python 3.14 — environment issue, not my code).

- T-5: Added 5 ruby ecosystem eval cases.
  - Added `ecosystem` field to `EvalCase` (defaults to "javascript").
  - Updated `loader.py` to read the `ecosystem` field from YAML.
  - Updated `runner.py` `_run_call_sites` to route non-JS ecosystems to `GenericImportScanner`.
  - Updated `Makefile` eval targets to use `PYTHONPATH=src` and `--corpus-dir src/depfix/evals/corpus` so depfix-agents code is used instead of the editable install from `dependency_check`.
  - Added 4 Ruby fixture directories under tests/fixtures/.
  - Added src/depfix/evals/corpus/ruby_callsites.yaml with 5 verified cases.
  - make test: 872 passed, 0 failed.
  - make eval: 10/10 call_sites pass (5 new Ruby + 5 existing JS).

## Notes
- typecheck fails with: `numpy/__init__.pyi:737: error: Type statement is only supported in Python 3.12 and greater` — this is a known environment issue, pre-existing since before T-3.
- make eval reports 89% (24/27 scored) due to 3 pre-existing spec_diff failures unrelated to T-5.
- Waiting for reviewer verdict on T-5.
