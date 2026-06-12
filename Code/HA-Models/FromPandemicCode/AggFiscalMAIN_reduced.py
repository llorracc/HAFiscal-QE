'''
This is the main script for the paper
'''
#from Parameters import return_parameters

import os
import sys
from time import time
mystr = lambda x : '{:.2f}'.format(x)

# for output
cwd             = os.getcwd()
folders         = cwd.split(os.path.sep)
top_most_folder = folders[-1]
if top_most_folder == 'FromPandemicCode':
    Abs_Path = cwd
else:
    Abs_Path = cwd + '/Code/HA-Models/FromPandemicCode'
    os.chdir(Abs_Path)

sys.path.append(Abs_Path)
from Simulate import Simulate
from Output_Results import Output_Results

#%%



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
Run_Dict['Run_1stRoundAD']          = True   # 2026-04-30: re-enabled. Was set to
                                              # False in the original 2023 "reduced
                                              # reproduce" stub (commit 5ab588e5) and
                                              # never flipped back when the rest of
                                              # the flags became production. Flipping
                                              # it back to True restores the 1st-round
                                              # AD multipliers the QE paper reports
                                              # (Multiplier.tex row "1st round AD
                                              # effect only"). Adds ~25% to Step 5
                                              # runtime.
Run_Dict['Run_NonAD']               = True
Run_Dict['sim_method']              = 'TM'   # 'MC', 'TM', or 'both'

# Harmenberg neutral measure for 1D TM:
#   E_P[p * f(m)] = E_P[p] * E_Q[f(m)]   — math-derive-harm (neutral-identity)
#   BST ApndxHarKmenberg, Theorem 1 / "Harmenberg's Method"
#   Notebook: Harmenberg-Four-Way-Comparison.ipynb §8j (uncorrected 1D pitfall)
# Applies to Type A/B (p-linear) outputs only — see type-map:
#   history/20260402-reduced-run-harmenberg-output-type-map.md
Run_Dict['tm_neutral_measure'] = True
# HAFISCAL_TM_MCOUNT env-var override for D-6-proper test of TM aggregation
# grid refinement. See memory project_mc_tm_newborn_timing_asymmetry.md.
Run_Dict['tm_mCount'] = int(os.environ.get('HAFISCAL_TM_MCOUNT', 100))
if 'HAFISCAL_TM_MCOUNT' in os.environ:
    print(f'[tm-mcount-override-rundict] Run_Dict[tm_mCount] = {Run_Dict["tm_mCount"]}')
# Coarser grid (Phase 2 of plans/20260403-1253h_harmenberg-reduced-reproduce-acceleration-plan.md).
# Currently only tm_mCount is consumed by Simulate.py; the FastReproduce tag is
# a forward-looking key for future code that may adjust additional parameters
# (AD iteration count, grid bounds, etc.).  Validate multipliers before relying.
if '--fast-reproduce' in sys.argv:
    sys.argv.remove('--fast-reproduce')
    Run_Dict['FastReproduce'] = True  # tag only — not yet consumed downstream
    Run_Dict['tm_mCount'] = 40

# SOLO-rec mode (formerly GLP-1): single agent type with recession + policies.
# 1 college type, point beta, fixed 3-quarter recession, all policies, no AD.
# Companion: SOLO-pol (no recession, single policy at a time, HS type) — see
# parity_solo_pol_*.py.
# CLI: python AggFiscalMAIN_reduced.py --solo-rec  (alias: --glp1)
if '--solo-rec' in sys.argv or '--glp1' in sys.argv:
    for _flag in ('--solo-rec', '--glp1'):
        if _flag in sys.argv:
            sys.argv.remove(_flag)
    Run_Dict['GLP1'] = True  # internal flag name kept for backward compatibility
    Run_Dict['GLP1_recession_duration'] = 3  # fixed 3-quarter recession
    Run_Dict['sim_method'] = 'TM'

# Dual-measure MC: runs P-track (standard) and Q-track (Harmenberg neutral)
# simultaneously with shared base draws.  Provides variance reduction and
# Q-aggregate as cross-check on P-aggregate.
# See: plans/20260403-1253h_dual-measure-mc-reduced-reproduce-plan.md
if '--dual-mc' in sys.argv:
    sys.argv.remove('--dual-mc')
    Run_Dict['sim_method'] = 'dual_MC'

# Override sim_method from environment (used by reproduce.sh --tm-only etc.)
_env_sim_method = os.environ.get('HAFISCAL_SIM_METHOD', '').strip()
if _env_sim_method:
    Run_Dict['sim_method'] = _env_sim_method

# Enable a-indexed TM (BUG-033 splurge-in-budget fix) from environment.
# Routes baseline + experiments through tm_methods' _a variants, eliminating
# the ξ-variance collapse that biases m-indexed multipliers by 15–25% under
# splurge-in-budget. See BUGS_private/HAFiscal_BUG-033_tm_a_indexed_refactor.md.
if os.environ.get('HAFISCAL_TM_A_INDEXED', '').strip() in ('1', 'true', 'yes'):
    Run_Dict['tm_a_indexed'] = True

# Override sim_method via env var (used by run_with_tma_companion.py wrapper
# to switch the script to MC mode without code edits). Valid: MC, TM, both.
_sim_method_env = os.environ.get('HAFISCAL_SIM_METHOD', '').strip()
if _sim_method_env in ('MC', 'TM', 'both'):
    Run_Dict['sim_method'] = _sim_method_env

# Crash / wiring check only: Parametrization Smoke_Test (N=100). Not for moments.
# --baseline: Paper-scale 'Baseline' parametrization (21 types). Used by
# `./reproduce.sh --comp full --tm-only` to get the full TM-valid subset.
if '--smoke-test' in sys.argv:
    sys.argv.remove('--smoke-test')
    _reduced_param = 'Smoke_Test'
elif '--baseline' in sys.argv:
    sys.argv.remove('--baseline')
    _reduced_param = 'Baseline'
elif '--hs-only' in sys.argv:
    # Single-cohort (HS, DiscFacCount=1) Step-5 multiplier scope — the cheapest meaningful
    # multiplier run, used as the first cascade tier for fast wiring/sanity gating before
    # escalating to Reduced_Run then Baseline (BUG-053 followup multiplier verification).
    sys.argv.remove('--hs-only')
    _reduced_param = 'HS_Only'
else:
    _reduced_param = 'Reduced_Run'

t0 = time()

# HAFISCAL_FIGS_SUFFIX: append a suffix to the parametrization name in the
# output dir paths (so parallel runs don't collide on Figures/Reduced_Run/).
# Example: HAFISCAL_FIGS_SUFFIX=_h0_treat_seed0 → Figures/Reduced_Run_h0_treat_seed0/
_figs_suffix = os.environ.get('HAFISCAL_FIGS_SUFFIX', '')
if _figs_suffix:
    print(f'[figs-suffix] HAFISCAL_FIGS_SUFFIX={_figs_suffix}')
_fig_base = Abs_Path + '/Figures/' + _reduced_param + _figs_suffix + '/'
_tab_base = Abs_Path + '/Tables/' + _reduced_param + _figs_suffix + '/'
Simulate(Run_Dict, _fig_base, Parametrization=_reduced_param)

if not Run_Dict.get('GLP1', False):
    Output_Results(_fig_base, _fig_base, _tab_base, Parametrization=_reduced_param)

t1 = time()
print('Whole script took ' + mystr((t1-t0)/60) + ' min.')

# ---- Registry hook ----
# Register Step-5 outputs (Multiplier.tex, base_results.csv, key figures)
# in the SQLite registry. No-op if registry import fails.
try:
    import sys as _sys_reg
    _ha_root_reg = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if _ha_root_reg not in _sys_reg.path:
        _sys_reg.path.insert(0, _ha_root_reg)
    import _registry as _reg

    # Override step5_scope in the config so it gets recorded properly
    os.environ.setdefault('HAFISCAL_STEP5_SCOPE', _reduced_param)
    _cfg = _reg.get_current_config()
    _cfg['step5_scope'] = _reduced_param
    _cfg['step5_method'] = Run_Dict.get('sim_method', 'TM')

    _run_id = _reg.register_run(config=_cfg, notes=f"AggFiscalMAIN_reduced.py {_reduced_param}")

    # Register key Step-5 outputs that exist
    _outputs_to_register = [
        (f"step5_multiplier_{_reduced_param.lower()}", _tab_base + "Multiplier.tex"),
        (f"step5_multiplier_{_reduced_param.lower()}", _tab_base + "Multiplier.ltx"),
        (f"step5_base_results_{_reduced_param.lower()}", _fig_base + "base_results.csv"),
    ]
    for _output_type, _path in _outputs_to_register:
        if os.path.exists(_path):
            _reg.register_output(_run_id, _output_type, _path)

    # Key figures
    for _fig_name in ('Cumulative_multipliers', 'Cumulative_multipliers_withHank'):
        _fig_pdf = _fig_base + _fig_name + '.pdf'
        if os.path.exists(_fig_pdf):
            _reg.register_output(_run_id, f"step5_figure_{_fig_name.lower()}_{_reduced_param.lower()}", _fig_pdf)

    _reg.mark_run_status(_run_id, "complete", wall_total_sec=(t1 - t0))
    print(f"[registry] Step-5 ({_reduced_param}) registered as run {_run_id}")
except Exception as _reg_err:
    print(f"[registry] WARNING: Step-5 registry hook failed: {_reg_err!r}")
