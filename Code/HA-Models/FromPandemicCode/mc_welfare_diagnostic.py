"""MC welfare diagnostic: OLD vs NEW splurge formula, CRN-paired.

Runs the minimum MC subset needed to compute W_6 and Q for UI Rec=1 (no AD)
under both formulas:
  NEW (default): splurge-in-budget asset update a = m - c_actual
  OLD (HAFISCAL_SPLURGE_OLD=1): pre-splurge-in-budget a = m - cFunc(m)

Saves full panel data (cLvl_all_splurge, AggIncome, AggCons) per scenario
to /tmp/welfare_diag/{version}.npz for downstream analysis by
analyze_welfare_gap.py.

Usage:
    cd Code/HA-Models/FromPandemicCode
    HAFISCAL_SPLURGE_OLD=0 python mc_welfare_diagnostic.py   # NEW
    HAFISCAL_SPLURGE_OLD=1 python mc_welfare_diagnostic.py   # OLD

Scope choices (for tractability):
  - Reduced_Run parametrization (3 types, not 21) — OLD vs NEW comparison
    is qualitatively robust to sample composition.
  - Single recession duration (duration=0, longest tail) — not prob-weighted.
    Δc magnitudes are comparable under both formulas at fixed duration.
  - UI extension scenario only (largest welfare asymmetry in Phase 6).
  - No AD training — isolates the BUG-031 mechanism from AD feedback.
"""
import os, sys
from copy import deepcopy
from time import time
import numpy as np

sys.argv_orig = sys.argv[:]
sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith("FromPandemicCode"):
    os.chdir(cwd + "/Code/HA-Models/FromPandemicCode")
sys.path.insert(0, os.getcwd())

os.environ["MPLBACKEND"] = "Agg"
import matplotlib; matplotlib.use("Agg")  # noqa: E702

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy  # noqa: E402
from Parameters import return_parameters  # noqa: E402
from HARK.distributions import DiscreteDistribution  # noqa: E402

version = "OLD" if os.environ.get("HAFISCAL_SPLURGE_OLD", "0") == "1" else "NEW"
_param = "Reduced_Run"
out_dir = "/tmp/welfare_diag"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, f"{version}.npz")

print(f"MC welfare diagnostic: version={version}  param={_param}")
print(f"  HAFISCAL_SPLURGE_OLD={os.environ.get('HAFISCAL_SPLURGE_OLD', '0')}")

(
    init_dropout, init_highschool, init_college,
    init_ADEconomy, DiscFacDstns, DiscFacCount, AgentCountTotal,
    base_dict, num_max_iterations_solvingAD, convergence_tol_solvingAD,
    UBspell_normal, num_base_MrkvStates, data_EducShares,
    max_recession_duration, num_experiment_periods,
    recession_changes, UI_changes, recession_UI_changes,
    TaxCut_changes, recession_TaxCut_changes,
    Check_changes, recession_Check_changes,
) = return_parameters(Parametrization=_param, OutputFor="_Main.py")

[_, Rspell, Rfree_base, _, CRRA] = return_parameters(
    Parametrization=_param, OutputFor="_Output_Results.py")
Rfree = Rfree_base[0]

t0_total = time()
init_params = [init_dropout, init_highschool, init_college]
AgentTypes = []
for e in range(3):
    for d in range(DiscFacCount):
        ThisType = AggFiscalType(**init_params[e])
        ThisType.cycles = 0
        ThisType.DiscFac = DiscFacDstns[e].atoms[0][d]
        ThisType.seed = e * DiscFacCount + d
        ThisType.AgentCount = int(np.floor(
            AgentCountTotal * data_EducShares[e] / DiscFacCount))
        AgentTypes.append(ThisType)

AggEco = AggregateDemandEconomy(**init_ADEconomy)
AggEco.agents = AgentTypes
for a in AggEco.agents:
    a.get_economy_data(AggEco)
    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([a.IncUnemp])])
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([a.IncUnempNoBenefits])])
    a.IncShkDstn[0].seed = 763607780
    a.IncShkDstn[0].reset()
    a.IncShkDstn = [
        [a.IncShkDstn[0]]
        + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits]
    ]
    a.IncShkDstn_base = a.IncShkDstn
    IncShkDstn_recession = [
        a.IncShkDstn[0] * (2 * (num_experiment_periods + 1))
    ]
    a.IncShkDstn_recession = IncShkDstn_recession
    a.IncShkDstn_recessionUI = IncShkDstn_recession

AggEco.solve()
print(f"  Economy solve: {time()-t0_total:.0f}s")

t0 = time()
AggEco.reset()
for a in AggEco.agents:
    a.initialize_sim()
    a.AggDemandFac = 1.0
    a.RfreeNow = 1.0
    a.CaggNow = 1.0
AggEco.make_history()
AggEco.save_state()
AggEco.switch_to_counterfactual_mode("base")
act_T = AggEco.act_T
for a in AggEco.agents:
    a.T_sim = act_T
    a.EconomyMrkvNow_hist = [0] * act_T
AggEco.make_idiosyncratic_shock_histories()
print(f"  Burn-in + shock histories: {time()-t0:.0f}s  (act_T={act_T})")

base_dict_agg = deepcopy(base_dict)

# Duration-0 recession path: full num_experiment_periods as recession, then calm
rec_path = (
    list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * 20
)
duration = 0  # single period of deepest recession
rec_path[0:duration + 1] = (np.array(rec_path[0:duration + 1]) + 1).tolist()

# ---------- Base (no policy) ----------
t0 = time()
base_res = AggEco.run_experiment(**base_dict_agg, Full_Output=True)
AggEco.store_baseline(base_res['AggCons'])
print(f"  Base: {time()-t0:.0f}s")

# ---------- recession (no UI) ----------
t0 = time()
eco_rec = deepcopy(AggEco)
eco_rec.switch_shock_type('recession')
eco_rec.solve()
d = base_dict_agg.copy()
d.update(recession_changes)
d['EconomyMrkv_init'] = rec_path
rec_res = eco_rec.run_experiment(**d, Full_Output=True)
print(f"  recession: {time()-t0:.0f}s")

# ---------- recessionUI (with UI, no AD) ----------
t0 = time()
eco_recUI = deepcopy(AggEco)
eco_recUI.switch_shock_type('recessionUI')
eco_recUI.solve()
d = base_dict_agg.copy()
d.update(recession_UI_changes)
d['EconomyMrkv_init'] = rec_path
recUI_res = eco_recUI.run_experiment(**d, Full_Output=True)
print(f"  recessionUI: {time()-t0:.0f}s")

# ---------- recession + AD training (no UI) ----------
t0 = time()
eco_recAD = deepcopy(AggEco)
eco_recAD.switch_shock_type('recession')
eco_recAD.solve_ad_recession(
    num_max_iterations=num_max_iterations_solvingAD,
    convergence_cutoff=convergence_tol_solvingAD, name='recession')
eco_recAD.switch_shock_type('recession')
eco_recAD.restore_ADsolution(name='recession')
d = base_dict_agg.copy()
d.update(recession_changes)
d['EconomyMrkv_init'] = rec_path
recAD_res = eco_recAD.run_experiment(**d, Full_Output=True)
print(f"  recession+AD: {time()-t0:.0f}s")

# ---------- recessionUI + AD training ----------
t0 = time()
eco_recUIAD = deepcopy(AggEco)
eco_recUIAD.switch_shock_type('recessionUI')
eco_recUIAD.solve_ad_ui_extension_recession(
    num_max_iterations=num_max_iterations_solvingAD,
    convergence_cutoff=convergence_tol_solvingAD, name='recessionUI')
eco_recUIAD.switch_shock_type('recessionUI')
eco_recUIAD.restore_ADsolution(name='recessionUI')
d = base_dict_agg.copy()
d.update(recession_UI_changes)
d['EconomyMrkv_init'] = rec_path
recUIAD_res = eco_recUIAD.run_experiment(**d, Full_Output=True)
print(f"  recessionUI+AD: {time()-t0:.0f}s")

# ---------- Save panels ----------
keys_to_save = ['cLvl_all_splurge', 'AggIncome', 'AggCons']
save_dict = {'version': version, 'CRRA': CRRA, 'Rfree': Rfree, 'act_T': act_T}
for label, res in [('base', base_res), ('rec', rec_res), ('recUI', recUI_res),
                    ('recAD', recAD_res), ('recUIAD', recUIAD_res)]:
    for k in keys_to_save:
        save_dict[f'{label}_{k}'] = res[k]

np.savez_compressed(out_path, **save_dict)
print(f"\n  Saved: {out_path}")
print(f"  Total: {time()-t0_total:.0f}s ({(time()-t0_total)/60:.1f} min)")
