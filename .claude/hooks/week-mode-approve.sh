#!/usr/bin/env bash
# PreToolUse hook (all tools): if week-mode-detect.sh has flipped on the
# per-session flag file, auto-allow this permission request unconditionally --
# including Bash calls of any kind (rm -rf, force push, reset --hard, etc.).
# There is deliberately no destructive-command denylist: the user opted into
# full auto-approve for the remainder of the session.
set -euo pipefail

input="$(cat)"
session_id="$(printf '%s' "$input" | jq -r '.session_id // "unknown"')"
flag="/tmp/claude-week-autoapprove-${session_id}"

[ -f "$flag" ] || exit 0

echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"week-mode auto-approve"}}'
