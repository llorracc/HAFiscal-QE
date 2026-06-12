#!/bin/bash
# Reproduce computational results using TM-first, then MC-validate strategy.
#
# Phase 1 (TM, ~1 h):  All multipliers, IRFs, NPVs via transition matrix
#                       (m-indexed TM, pinned below; the canonical do_all
#                       Step-5a is a-indexed and slower — see Code/HA-Models/README.md).
#                       → Tables/Baseline/Multiplier.tex
# Phase 2 (MC, ~6-12 h): MC validation of TM multipliers (separate dir).
#                        → Tables/Baseline_MC/Multiplier.tex
# Phase 3 (MC, ~6 h):   Canonical CRN-paired welfare-6 (post-splurge-
#                       in-budget-bugfix). → Tables/Baseline/welfare6.tex
#
# Monitor progress:
#   tail -f /tmp/hafiscal_progress.log
#
# See plans/20260405-2228h_full-reproduction-plan.md for rationale.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROGRESS_LOG="/tmp/hafiscal_progress.log"

# Ensure output is unbuffered and tee'd to the progress log
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    echo "$msg" >> "$PROGRESS_LOG"
}

: > "$PROGRESS_LOG"  # truncate
log "=== TM-and-MC reproduction started ==="
log "Monitor: tail -f $PROGRESS_LOG"
log ""

cd "$PROJECT_ROOT/Code/HA-Models"

# ====================================================================
# Phase 1: TM
# ====================================================================
log "========================================"
log "Phase 1: TM-only reproduction (~1 hour, m-indexed TM)"
log "========================================"
log "  All multipliers, IRFs, NPVs (Class A, exact under TM)"

PHASE1_START=$(date +%s)

PYTHONUNBUFFERED=1 python -c "
import sys, os
sys.argv = ['reproduce', '1.01', '2.0', '0.7']
os.chdir('FromPandemicCode')

# Progress logger that writes to both stdout and file
_plog = open('/tmp/hafiscal_progress.log', 'a')
import builtins
_orig_print = builtins.print
def _tee_print(*args, **kwargs):
    _orig_print(*args, **kwargs)
    _orig_print(*args, **{**kwargs, 'file': _plog, 'flush': True})
builtins.print = _tee_print

from Simulate import Simulate
from Output_Results import Output_Results

Abs_Path = os.getcwd()  # cwd is FromPandemicCode
figs_dir = Abs_Path + '/Figures/Baseline/'
tables_dir = Abs_Path + '/Tables/Baseline/'
os.makedirs(figs_dir, exist_ok=True)
os.makedirs(tables_dir, exist_ok=True)

Run_Dict = {
    'Teffs'            : True,
    'GLP1'             : False,
    'Run_Baseline'     : True,
    'Run_Recession'    : True,
    'Run_Check_Recession': True,
    'Run_UB_Ext_Recession': True,
    'Run_TaxCut_Recession': True,
    'Run_Check'        : True,
    'Run_UB_Ext'       : True,
    'Run_TaxCut'       : True,
    'Run_AD'           : True,
    'Run_1stRoundAD'   : True,
    'Run_NonAD'        : True,
    'sim_method'       : 'TM',
    'tm_mCount'        : 100,
}

print('[Phase 1] Running TM simulation (Baseline, all experiments)...')
Simulate(Run_Dict, figs_dir, Parametrization='Baseline')

print('[Phase 1] Generating output tables and figures...')
Output_Results(figs_dir, figs_dir, tables_dir, Parametrization='Baseline')

print('[Phase 1] TM reproduction complete.')
_plog.close()
" 2>&1

PHASE1_END=$(date +%s)
PHASE1_ELAPSED=$((PHASE1_END - PHASE1_START))
log ""
log "Phase 1 completed in $(printf '%d:%02d:%02d' $((PHASE1_ELAPSED/3600)) $((PHASE1_ELAPSED%3600/60)) $((PHASE1_ELAPSED%60)))"
log ""

# ====================================================================
# Phase 2: MC
# ====================================================================
log "========================================"
log "Phase 2: MC reproduction (~6-12 hours)"
log "========================================"
log "  Welfare tables + MC validation of TM multipliers"

PHASE2_START=$(date +%s)

PYTHONUNBUFFERED=1 python -c "
import sys, os
sys.argv = ['reproduce', '1.01', '2.0', '0.7']
os.chdir('FromPandemicCode')

_plog = open('/tmp/hafiscal_progress.log', 'a')
import builtins
_orig_print = builtins.print
def _tee_print(*args, **kwargs):
    _orig_print(*args, **kwargs)
    _orig_print(*args, **{**kwargs, 'file': _plog, 'flush': True})
builtins.print = _tee_print

from Simulate import Simulate
from Output_Results import Output_Results

Abs_Path = os.getcwd()  # cwd is FromPandemicCode
figs_dir = Abs_Path + '/Figures/Baseline_MC/'
tables_dir = Abs_Path + '/Tables/Baseline_MC/'
os.makedirs(figs_dir, exist_ok=True)
os.makedirs(tables_dir, exist_ok=True)

Run_Dict = {
    'Teffs'            : True,
    'GLP1'             : False,
    'Run_Baseline'     : True,
    'Run_Recession'    : True,
    'Run_Check_Recession': True,
    'Run_UB_Ext_Recession': True,
    'Run_TaxCut_Recession': True,
    'Run_Check'        : True,
    'Run_UB_Ext'       : True,
    'Run_TaxCut'       : True,
    'Run_AD'           : True,
    'Run_1stRoundAD'   : True,
    'Run_NonAD'        : True,
    'sim_method'       : 'MC',
}

print('[Phase 2] Running MC simulation (Baseline, all experiments)...')
Simulate(Run_Dict, figs_dir, Parametrization='Baseline')

print('[Phase 2] Generating output tables and figures...')
Output_Results(figs_dir, figs_dir, tables_dir, Parametrization='Baseline')

print('[Phase 2] MC multiplier reproduction complete (Welfare_Results is obsolete on this tree; see Phase 3).')
_plog.close()
" 2>&1

PHASE2_END=$(date +%s)
PHASE2_ELAPSED=$((PHASE2_END - PHASE2_START))
log ""
log "Phase 2 completed in $(printf '%d:%02d:%02d' $((PHASE2_ELAPSED/3600)) $((PHASE2_ELAPSED%3600/60)) $((PHASE2_ELAPSED%60)))"
log ""

# ====================================================================
# Phase 3: MC welfare-6 (CRN-paired, canonical post-bugfix)
# ====================================================================
log "========================================"
log "Phase 3: MC welfare-6 (~6 h serial)"
log "========================================"
log "  Canonical CRN-paired welfare-6 via run_hybrid_welfare6.py"
log "  → Tables/Baseline/welfare6.tex"

PHASE3_START=$(date +%s)
(
    cd "$PROJECT_ROOT/Code/HA-Models/FromPandemicCode"
    PYTHONUNBUFFERED=1 python run_hybrid_welfare6.py --baseline 2>&1 | tee -a "$PROGRESS_LOG"
)
PHASE3_END=$(date +%s)
PHASE3_ELAPSED=$((PHASE3_END - PHASE3_START))
log ""
log "Phase 3 completed in $(printf '%d:%02d:%02d' $((PHASE3_ELAPSED/3600)) $((PHASE3_ELAPSED%3600/60)) $((PHASE3_ELAPSED%60)))"
log ""

# ====================================================================
# Summary
# ====================================================================
TOTAL_ELAPSED=$((PHASE3_END - PHASE1_START))
log "========================================"
log "All phases complete"
log "========================================"
log "Total time: $(printf '%d:%02d:%02d' $((TOTAL_ELAPSED/3600)) $((TOTAL_ELAPSED%3600/60)) $((TOTAL_ELAPSED%60)))"
log ""
log "Results:"
log "  TM tables:            Code/HA-Models/FromPandemicCode/Tables/Baseline/"
log "  MC-validation tables: Code/HA-Models/FromPandemicCode/Tables/Baseline_MC/"
log "  welfare-6 (CRN MC):   Code/HA-Models/FromPandemicCode/Tables/Baseline/welfare6.tex"
log "  TM figures:           Code/HA-Models/FromPandemicCode/Figures/Baseline/"
log "  MC figures:           Code/HA-Models/FromPandemicCode/Figures/Baseline_MC/"
log ""
log "Compare multipliers: diff ...Tables/Baseline/Multiplier.tex ...Tables/Baseline_MC/Multiplier.tex"
