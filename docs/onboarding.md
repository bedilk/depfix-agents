# Onboarding a repository

Onboard in increasing order of blast radius. Do not skip a stage.

## 0. Prerequisites

- The GitHub App is installed on the repository or organisation.
- A `.depfix.yml` is committed to the repository's default branch. It is the
  maintainer's consent record; depfix reads it there even when it works on a
  different `base_branch`.

## 1. Rehearse — `--dry-run`

```sh
depfix pipeline OWNER/NAME --dry-run --show-skips
```

This writes nothing to GitHub or the database. It confirms that the config
parses, a change is in scope, and the ledger would allow it to proceed.

## 2. Full run without a PR — `--no-pr`

```sh
depfix pipeline OWNER/NAME --no-pr
```

This clones, scans, fixes, and runs the repository test suite, but opens no
PR. The result is persisted as `FIXED_NO_PR`.

## 3. Live as drafts

Set `draft_pr: true` in `.depfix.yml`, then run:

```sh
depfix pipeline OWNER/NAME
```

Review and undraft a PR manually when you trust the result.

## 4. Live

Remove `draft_pr: true` after the draft stage is working well.

## Cron

The advisory lock is enabled by default. Give an hourly cron job a finite
window and emit JSON logs for aggregation:

```sh
depfix pipeline --max-duration 55 --log-format json
```

A duration or cost ceiling stops cleanly between work items and exits zero;
the next scheduled run resumes the remaining work.
