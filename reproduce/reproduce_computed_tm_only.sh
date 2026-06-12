#!/usr/bin/env bash
# reproduce_computed_tm_only.sh
#
# Draft dispatcher for `./reproduce.sh --comp full --tm-only`.
# Produces the TM-valid subset of paper outputs at Baseline scale
# (3 education types x 7 discount factors = 21 types), per
# plans/20260405-2228h_full-reproduction-plan.md Phase 1 + Phase 3.
#
# Expects env var (set by reproduce.sh):
#   HAFISCAL_SIM_METHOD=TM   -- force Run_Dict['sim_method']='TM'
#
# Per-wealth-percentile welfare is auto-skipped: Output_Results.py gates the
# Welfare_Results call on presence of 'cLvl_all_splurge' in base_results,
# which TM mode does not produce (the has_individual_data gate in Output_Results.py).
#
# Python entry point: AggFiscalMAIN_reduced.py with the --baseline flag,
# which selects Parametrization='Baseline' (21 types, paper scale) instead
# of the default Reduced_Run.

set -euo pipefail

: "${HAFISCAL_SIM_METHOD:=TM}"
export HAFISCAL_SIM_METHOD

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/Code/HA-Models/FromPandemicCode"

echo "[tm-only] HAFISCAL_SIM_METHOD=$HAFISCAL_SIM_METHOD"
echo "[tm-only] cwd=$(pwd)"
echo "[tm-only] Running Baseline parametrization via AggFiscalMAIN_reduced.py --baseline"

MPLBACKEND=Agg python AggFiscalMAIN_reduced.py --baseline

echo "[tm-only] Done. Outputs:"
echo "  Tables: Code/HA-Models/FromPandemicCode/Tables/CRRA2/Multiplier.ltx"
echo "  Figures: Code/HA-Models/FromPandemicCode/Figures/CRRA2/"
echo ""
echo "NOTE: per-wealth-percentile welfare tables (WelfareByWPercentile.tex)"
echo "      and Lorenz/wealth-share outputs are intentionally skipped."
