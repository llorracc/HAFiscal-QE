"""
Run the Reduced_Run (3-type) TM-only pipeline under tm_a_indexed=True
and write outputs to Tables/Reduced_Run_TMa/ for direct comparison
against Tables/Reduced_Run/.

Used for Phase 5-lite validation of BUG-033. Full 21-type production
(Phase 5) is blocked on Phase 2 (remote machine).
"""

import os
import sys
from time import time

# Make sure we run from FromPandemicCode so relative imports / Simulate
# internals work.
Abs_Path = os.path.dirname(os.path.abspath(__file__))
os.chdir(Abs_Path)
sys.path.append(Abs_Path)

from Simulate import Simulate
from Output_Results import Output_Results


Run_Dict = {
    'Run_Baseline':          True,
    'Run_Recession ':        True,
    'Run_Check_Recession':   True,
    'Run_UB_Ext_Recession':  True,
    'Run_TaxCut_Recession':  True,
    'Run_Check':             False,
    'Run_UB_Ext':            False,
    'Run_TaxCut':            False,
    'Run_AD ':               True,
    'Run_1stRoundAD':        False,
    'Run_NonAD':             True,
    'sim_method':            'TM',
    'tm_mCount':             50,
    'tm_neutral_measure':    False,
    'tm_a_indexed':          True,
}

_param = 'Reduced_Run'
_suffix = '_TMa'
_fig_base = os.path.join(Abs_Path, 'Figures', _param + _suffix, '') + os.sep
_tab_base = os.path.join(Abs_Path, 'Tables',  _param + _suffix, '') + os.sep
for _d in (_fig_base, _tab_base):
    os.makedirs(_d, exist_ok=True)

t0 = time()
Simulate(Run_Dict, _fig_base, Parametrization=_param)
Output_Results(_fig_base, _fig_base, _tab_base, Parametrization=_param)
t1 = time()
print(f"[TMa] Reduced_Run completed in {(t1 - t0) / 60:.2f} min.")
print(f"[TMa] Outputs: figures -> {_fig_base}")
print(f"[TMa] Outputs: tables  -> {_tab_base}")
