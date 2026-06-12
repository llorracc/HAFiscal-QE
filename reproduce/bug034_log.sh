#!/bin/bash
# bug034_log.sh — minimal structured-logging helper for BUG-034+035 fix work.
#
# Appends one line to reproduce/logs/bug034-fix.log in the format:
#   [<LEVEL>] [<UTC-ts>] [Phase <X>] [Tier <T>] [<check-id>] <message>
#
# Format spec: see plans/20260425-2137h_cdc-esc-configurable-refactor.md §1.6
#
# Usage:
#   reproduce/bug034_log.sh LEVEL PHASE TIER CHECK_ID MESSAGE...
#
# Examples:
#   reproduce/bug034_log.sh START A - setup "entering Phase A: class hierarchy scaffold"
#   reproduce/bug034_log.sh INFO  A 1 T1.1 "running pytest test_cdc_baseline_pin.py"
#   reproduce/bug034_log.sh PASS  A 1 T1.1 "47 assertions OK in 3.2s"
#   reproduce/bug034_log.sh FAIL  B 2 T2.3 "ESC ς = 0.281, expected 0.267 ± 2%"
#   reproduce/bug034_log.sh HALT  F 4 T4.2 "see status file for diagnostic"
#
# Level codes (5-char fixed-width inside brackets so grep patterns work):
#   INFO  START BG    ALIVE PASS  FAIL  INV   RESOL HALT  RESUM DONE
#
# The trailing space after 4-letter codes (PASS, FAIL, HALT, INFO, INV, DONE,
# BG) is intentional: grep '\[HALT \]' uniquely matches without false positives.

set -euo pipefail

if [[ $# -lt 4 ]]; then
    echo "usage: $0 LEVEL PHASE TIER CHECK_ID MESSAGE..." >&2
    exit 2
fi

LEVEL="$1"; shift
PHASE="$1"; shift
TIER="$1"; shift
CHECK_ID="$1"; shift
MESSAGE="$*"

# Find repo root (script is at <repo>/reproduce/bug034_log.sh)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="$REPO_ROOT/reproduce/logs/bug034-fix.log"

# Make sure logs dir exists (no-op if already there).
mkdir -p "$(dirname "$LOG_FILE")"

# UTC timestamp in ISO 8601 with Z.
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Pad LEVEL to 5 chars with trailing spaces.
printf -v LEVEL_PAD '%-5s' "$LEVEL"

# Pad TIER to single char (might be 1-4, or "-" for non-tier events).
printf -v TIER_PAD '%-1s' "$TIER"

printf '[%s] [%s] [Phase %s] [Tier %s] [%s] %s\n' \
    "$LEVEL_PAD" "$TS" "$PHASE" "$TIER_PAD" "$CHECK_ID" "$MESSAGE" \
    >> "$LOG_FILE"

# Also echo to stderr so the executor can see what's being logged
# without re-reading the log file.
printf '[%s] [Phase %s] [Tier %s] [%s] %s\n' \
    "$LEVEL_PAD" "$PHASE" "$TIER_PAD" "$CHECK_ID" "$MESSAGE" >&2
