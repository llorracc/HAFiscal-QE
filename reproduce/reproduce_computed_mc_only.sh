#!/usr/bin/env bash
# reproduce_computed_mc_only.sh
#
# Sibling of reproduce_computed_tm_only.sh: dispatches `./reproduce.sh
# --comp full --mc-only`. Produces the FULL paper outputs at Baseline
# scale (3 education types x 7 discount factors = 21 types) using the
# Monte Carlo simulation method, including the per-wealth-percentile
# welfare tables that the TM-only path skips.
#
# Expects env var (set by reproduce.sh):
#   HAFISCAL_SIM_METHOD=MC   -- force Run_Dict['sim_method']='MC'
#
# Wall-clock note: MC at Baseline scale is 6-12 hours (vs ~26 min for
# TM-only with the parallelized Simulate.py; m-indexed-era figure — the
# canonical a-indexed Step-5a is slower, see Code/HA-Models/README.md).
# The dominant cost is the AD iteration solves at full agent count, which
# scale linearly in N unlike TM.
#
# Python entry point: AggFiscalMAIN_reduced.py with the --baseline flag,
# which selects Parametrization='Baseline' (21 types, paper scale).

set -euo pipefail

: "${HAFISCAL_SIM_METHOD:=MC}"
export HAFISCAL_SIM_METHOD

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/Code/HA-Models/FromPandemicCode"

echo "[mc-only] HAFISCAL_SIM_METHOD=$HAFISCAL_SIM_METHOD"
echo "[mc-only] cwd=$(pwd)"
echo "[mc-only] Running Baseline parametrization via AggFiscalMAIN_reduced.py --baseline"

MPLBACKEND=Agg python AggFiscalMAIN_reduced.py --baseline

echo "[mc-only] Done. Outputs:"
echo "  Tables: Code/HA-Models/FromPandemicCode/Tables/Baseline/"
echo "  Figures: Code/HA-Models/FromPandemicCode/Figures/Baseline/"
echo ""
echo "Includes per-wealth-percentile welfare tables (WelfareByWPercentile.tex)"
echo "and other per-agent outputs that TM mode cannot produce."
