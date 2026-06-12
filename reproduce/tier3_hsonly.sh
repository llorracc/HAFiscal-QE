#!/bin/bash
# tier3_hsonly.sh — Tier 3 HS-only validation of BUG-034 + BUG-035 fixes.
#
# Sequence:
#   Step 1: Estimation_BetaNablaSplurge.py        (~30 min, exercises BUG-035)
#   Step 2: EstimAggFiscalMAIN.py (HAFISCAL_EDTYPES=1)  (~60 min, exercises BUG-034 for HS only)
#
# Output:
#   reproduce/logs/tier3_hsonly_<UTC>.log  — full stdout/stderr
#   reproduce/logs/bug034-fix.log          — structured progress markers (via bug034_log.sh)
#   reproduce/logs/bug034-status.json      — current state (via bug034_status.sh)
#
# Files modified by the runs (these will INVALIDATE pin tests, expected):
#   Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt
#   Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_edType1.txt

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

TS_START="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$REPO_ROOT/reproduce/logs/tier3_hsonly_${TS_START}.log"

# Activate the project venv (so subprocesses use the right python)
if [[ -d "$REPO_ROOT/.venv-linux-x86_64" ]]; then
    export VIRTUAL_ENV="$REPO_ROOT/.venv-linux-x86_64"
    export PATH="$VIRTUAL_ENV/bin:$PATH"
fi

{
    echo "=== Tier 3 HS-only run starting at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
    echo "REPO_ROOT=$REPO_ROOT"
    echo "VIRTUAL_ENV=${VIRTUAL_ENV:-unset}"
    echo "Branch: $(git rev-parse --abbrev-ref HEAD)"
    echo "HEAD: $(git rev-parse HEAD)"

    "$REPO_ROOT/reproduce/bug034_log.sh"    START - 3 T3.start "Tier 3 HS-only kicked off"
    BACKGROUND_PID=$$ "$REPO_ROOT/reproduce/bug034_status.sh" background - 3 T3.start

    # ----- Step 1 -----
    echo ""
    echo "=== Step 1: Splurge estimation (Estimation_BetaNablaSplurge.py) ==="
    "$REPO_ROOT/reproduce/bug034_log.sh" START - 3 T3.1 "Step 1: Splurge estimation"
    BACKGROUND_PID=$$ "$REPO_ROOT/reproduce/bug034_status.sh" background - 3 T3.1
    cd "$REPO_ROOT/Code/HA-Models/Target_AggMPCX_LiquWealth" || exit 1
    T0=$(date +%s)
    if python Estimation_BetaNablaSplurge.py; then
        T1=$(date +%s)
        "$REPO_ROOT/reproduce/bug034_log.sh" PASS - 3 T3.1 "Step 1 done in $((T1-T0))s"
    else
        RC=$?
        "$REPO_ROOT/reproduce/bug034_log.sh" FAIL - 3 T3.1 "Step 1 exited rc=$RC"
        HALT_REASON="Step 1 failed (rc=$RC); see log for details" \
            "$REPO_ROOT/reproduce/bug034_status.sh" halted - 3 T3.1
        exit $RC
    fi
    cd "$REPO_ROOT" || exit 1

    # ----- Step 2 (HS only) -----
    echo ""
    echo "=== Step 2: Discount-factor estimation (HS only) ==="
    "$REPO_ROOT/reproduce/bug034_log.sh" START - 3 T3.2 "Step 2: HS only (HAFISCAL_EDTYPES=1)"
    BACKGROUND_PID=$$ "$REPO_ROOT/reproduce/bug034_status.sh" background - 3 T3.2
    cd "$REPO_ROOT/Code/HA-Models/FromPandemicCode" || exit 1
    T0=$(date +%s)
    if HAFISCAL_EDTYPES=1 python EstimAggFiscalMAIN.py; then
        T1=$(date +%s)
        "$REPO_ROOT/reproduce/bug034_log.sh" PASS - 3 T3.2 "Step 2 HS-only done in $((T1-T0))s"
    else
        RC=$?
        "$REPO_ROOT/reproduce/bug034_log.sh" FAIL - 3 T3.2 "Step 2 exited rc=$RC"
        HALT_REASON="Step 2 failed (rc=$RC); see log for details" \
            "$REPO_ROOT/reproduce/bug034_status.sh" halted - 3 T3.2
        exit $RC
    fi
    cd "$REPO_ROOT" || exit 1

    "$REPO_ROOT/reproduce/bug034_log.sh" DONE - 3 T3.complete "Tier 3 HS-only complete"
    "$REPO_ROOT/reproduce/bug034_status.sh" complete - 3 T3.complete

    echo ""
    echo "=== Tier 3 HS-only done at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
} 2>&1 | tee "$LOG"
