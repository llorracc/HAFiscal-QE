#!/bin/bash
# bug034_status.sh — atomically update reproduce/logs/bug034-status.json
#
# The status file tracks current execution state for the BUG-034+035 fix.
# Updated atomically via temp-file + mv so concurrent reads always see a
# consistent snapshot.
#
# Schema spec: see plans/20260425-2137h_cdc-esc-configurable-refactor.md §1.6
#
# Usage:
#   reproduce/bug034_status.sh STATE PHASE [TIER [CHECK_ID]]
#
#   STATE: running | halted | complete | background
#   PHASE: A | B | C | D | E | E2 | F | G | H | I | J | "" (empty for none)
#   TIER:  1 | 2 | 3 | 4 | "" (empty for not-in-tier)
#   CHECK_ID: T<tier>.<index> or "" (empty for not-checking)
#
# Optional environment variables:
#   HALT_REASON     — short description of why halted (state=halted only)
#   USER_QUERY      — full text of what input is needed from user (state=halted only)
#   BACKGROUND_PID  — PID of background task (state=background only)
#
# Examples:
#   reproduce/bug034_status.sh running A 1 T1.1
#   HALT_REASON='ESC ς out of range' USER_QUERY='need formula clarification' \
#       reproduce/bug034_status.sh halted B 2 T2.3
#   BACKGROUND_PID=12345 reproduce/bug034_status.sh background F 4 T4.1

set -euo pipefail

STATE="${1:?usage: $0 STATE PHASE [TIER [CHECK_ID]]}"
PHASE="${2:-}"
TIER="${3:-}"
CHECK_ID="${4:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
STATUS_FILE="$REPO_ROOT/reproduce/logs/bug034-status.json"
TMP_FILE="${STATUS_FILE}.tmp.$$"

mkdir -p "$(dirname "$STATUS_FILE")"

NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Read existing started_at if status file exists, else use NOW.
STARTED_AT="$NOW"
if [[ -f "$STATUS_FILE" ]]; then
    STARTED_AT="$(python3 -c "import json,sys; d=json.load(open('$STATUS_FILE')); print(d.get('started_at_utc', '$NOW'))" 2>/dev/null || echo "$NOW")"
fi

# Build phases_complete list from prior status (preserve forward progress).
PHASES_COMPLETE='[]'
if [[ -f "$STATUS_FILE" ]]; then
    PHASES_COMPLETE="$(python3 -c "import json; print(json.dumps(json.load(open('$STATUS_FILE')).get('phases_complete', [])))" 2>/dev/null || echo '[]')"
fi

# Compute elapsed seconds from started_at to now.
ELAPSED="$(python3 -c "
from datetime import datetime
s = datetime.fromisoformat('$STARTED_AT'.replace('Z','+00:00'))
n = datetime.fromisoformat('$NOW'.replace('Z','+00:00'))
print(int((n-s).total_seconds()))
" 2>/dev/null || echo 0)"

# JSON-quote string fields safely.
json_str() {
    python3 -c "import json,sys; print(json.dumps(sys.stdin.read().rstrip()))" <<< "$1"
}

PHASE_JSON="null"; [[ -n "$PHASE" && "$PHASE" != "-" ]] && PHASE_JSON="$(json_str "$PHASE")"
TIER_JSON="null"; [[ -n "$TIER" && "$TIER" != "-" ]] && TIER_JSON="$TIER"
CHECK_JSON="null"; [[ -n "$CHECK_ID" && "$CHECK_ID" != "-" ]] && CHECK_JSON="$(json_str "$CHECK_ID")"
HALT_JSON="null"; [[ -n "${HALT_REASON:-}" ]] && HALT_JSON="$(json_str "$HALT_REASON")"
QUERY_JSON="null"; [[ -n "${USER_QUERY:-}" ]] && QUERY_JSON="$(json_str "$USER_QUERY")"
BGPID_JSON="null"; [[ -n "${BACKGROUND_PID:-}" ]] && BGPID_JSON="$BACKGROUND_PID"

cat > "$TMP_FILE" <<EOF
{
  "state": "$STATE",
  "phase": $PHASE_JSON,
  "tier": $TIER_JSON,
  "current_check": $CHECK_JSON,
  "started_at_utc": "$STARTED_AT",
  "last_update_utc": "$NOW",
  "elapsed_seconds": $ELAPSED,
  "phases_complete": $PHASES_COMPLETE,
  "halt_reason": $HALT_JSON,
  "user_query": $QUERY_JSON,
  "background_pid": $BGPID_JSON
}
EOF

mv -f "$TMP_FILE" "$STATUS_FILE"
