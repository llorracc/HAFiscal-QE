#!/usr/bin/env python3
"""Run a single parametrization with Option C code and published estimates.

Usage: python run_optc_param.py <Parametrization>
  e.g.  python run_optc_param.py CRRA1
"""
import os, sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
os.environ['MPLBACKEND'] = 'Agg'
os.environ['MATPLOTLIB_BACKEND'] = 'agg'  # matplotlib_config.py checks this
os.environ['NONINTERACTIVE'] = '1'
os.environ.setdefault('HAFISCAL_NO_FORK', '1')

if len(sys.argv) < 2:
    print('Usage: run_optc_param.py <Parametrization>')
    sys.exit(1)

param = sys.argv[1]
# EstimParameters.py reads sys.argv[1] as a float Rfree. Clear argv before imports.
sys.argv = ['run_optc_param']

sys.path.insert(0, '.')

from time import time
from Simulate import Simulate
from Output_Results import Output_Results

Run_Dict = dict()
Run_Dict['Run_Baseline']            = True
Run_Dict['Run_Recession ']          = True
Run_Dict['Run_Check_Recession']     = True
Run_Dict['Run_UB_Ext_Recession']    = True
Run_Dict['Run_TaxCut_Recession']    = True
Run_Dict['Run_Check']               = True
Run_Dict['Run_UB_Ext']              = True
Run_Dict['Run_TaxCut']              = True
Run_Dict['Run_AD ']                 = True
Run_Dict['Run_1stRoundAD']          = False
Run_Dict['Run_NonAD']               = True
Run_Dict['sim_method']              = 'TM'
Run_Dict['tm_neutral_measure']      = True
Run_Dict['tm_mCount']               = 100

fig_base = os.path.abspath('.') + f'/Figures/{param}/'
tab_base = os.path.abspath('.') + f'/Tables/{param}/'
os.makedirs(fig_base, exist_ok=True)
os.makedirs(tab_base, exist_ok=True)

t0 = time()
print(f'Running {param} TM with Option C (published estimates)')
Simulate(Run_Dict, fig_base, Parametrization=param)
Output_Results(fig_base, fig_base, tab_base, Parametrization=param)
print(f'{param} done in {(time()-t0)/60:.1f} min')
