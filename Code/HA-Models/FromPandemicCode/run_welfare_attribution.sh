#!/usr/bin/env bash
# Welfare attribution experiment (v2 §6): Baseline, 4 runs.
#
# Run A: current Phase 6 (splurge-in-budget, ς=0.261, current β/∇) — already produced.
# Run B: BUG-031 alone rolled back (OLD assets, ς=0.261, current β/∇).
# Run C: ς rollback only (NEW assets, ς=0.318, current β/∇).
# Run D: full QE-side rollback (OLD assets, ς=0.318, pre-splurge-in-budget β/∇).
#
# Acceptance (v2 §9): Run C's UI Rec+AD welfare6 ≥ 1.8 confirms H1.
# Expected cost: ~2-2.5 h compute on the current machine.

set -euo pipefail
cd "$(dirname "$0")"

REPO_ROOT="$(git rev-parse --show-toplevel)"
ATTR_FILE="$REPO_ROOT/Code/HA-Models/Results/attribution/DiscFacEstim_preOptionD.txt"
OUT_ROOT="$(pwd)/Tables/Attribution"

mkdir -p "$OUT_ROOT"/{A,B,C,D}

run_one() {
    local label=$1; shift
    local outdir="$OUT_ROOT/$label"
    local logfile="$outdir/run.log"
    echo "==== Run $label → $outdir ===="
    echo "  env: $*"
    # shellcheck disable=SC2068
    env $@ HAFISCAL_TABLE_DIR="$outdir" \
        python run_hybrid_welfare6.py --baseline 2>&1 | tee "$logfile"
    echo "  done: $outdir/welfare6.tex"
}

# Run A — reuse existing Tables/Baseline/welfare6.tex if present.
if [[ -f "Tables/Baseline/welfare6.tex" ]]; then
    cp Tables/Baseline/welfare6.tex "$OUT_ROOT/A/welfare6.tex"
    echo "Run A: copied existing Tables/Baseline/welfare6.tex → $OUT_ROOT/A/"
else
    run_one A
fi

run_one B HAFISCAL_SPLURGE_OLD=1
run_one C HAFISCAL_SPLURGE_OVERRIDE=0.318
run_one D HAFISCAL_SPLURGE_OLD=1 HAFISCAL_SPLURGE_OVERRIDE=0.318 \
         HAFISCAL_DISCFAC_FILE="$ATTR_FILE"

echo
echo "All runs complete. Tables in $OUT_ROOT/{A,B,C,D}/welfare6.tex"
