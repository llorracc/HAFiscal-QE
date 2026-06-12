"""
Full Baseline TM-only timing test.

Runs Simulate() with sim_method='TM' and Baseline parametrization,
measuring wall-clock time to compare against the prediction.
"""

import os
import sys
from time import time

cwd = os.getcwd()
if not cwd.endswith('FromPandemicCode'):
    os.chdir(cwd + '/Code/HA-Models/FromPandemicCode')
    cwd = os.getcwd()

sys.path.insert(0, cwd)

from Simulate import Simulate

Run_Dict = {
    'Run_Baseline': True,
    'Run_Recession ': True,
    'Run_Check_Recession': True,
    'Run_UB_Ext_Recession': True,
    'Run_TaxCut_Recession': True,
    'Run_Check': True,
    'Run_UB_Ext': True,
    'Run_TaxCut': True,
    'Run_AD ': False,       # AD feedback not supported by TM
    'Run_1stRoundAD': False,
    'Run_NonAD': True,
    'sim_method': 'TM',
}

figs_dir = cwd + '/Figures/CRRA2_TM_timing_test/'
os.makedirs(figs_dir, exist_ok=True)

print("=" * 60)
print("FULL BASELINE TM-ONLY TIMING TEST")
print(f"  Parametrization: Baseline")
print(f"  sim_method: TM")
print(f"  Output: {figs_dir}")
print("=" * 60)

t0 = time()
Simulate(Run_Dict, figs_dir, Parametrization='Baseline')
elapsed = time() - t0

print(f"\n{'=' * 60}")
print(f"TOTAL WALL-CLOCK TIME: {elapsed:.1f}s ({elapsed/60:.1f} min)")
print(f"Prediction was: ~20-25 min")
print("=" * 60)
