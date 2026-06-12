"""
Corrected consumption gap diagnostic.

Previous diagnose_cons_gap.py had a bug: it used different agents for
TM base vs UI, with different state indexing. This version uses the
correct ergodic distribution throughout.
"""

import os
import sys
import numpy as np
from copy import deepcopy

sys.argv = sys.argv[:1]
cwd = os.getcwd()
if not cwd.endswith('FromPandemicCode'):
    os.chdir(cwd + '/Code/HA-Models/FromPandemicCode')
sys.path.insert(0, os.getcwd())

from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from Parameters import return_parameters
from tm_methods import (
    build_tm_agg_fiscal, find_ergodic_distribution,
    _apply_micro_transition, build_experiment_period_tm,
    compute_analytical_mean_pLvl, compute_period_aggregates_tm,
)

[init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
 DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
 convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
 data_EducShares, max_recession_duration, num_experiment_periods,
 recession_changes, UI_changes, recession_UI_changes,
 TaxCut_changes, recession_TaxCut_changes,
 Check_changes, recession_Check_changes] = return_parameters(
    Parametrization='Reduced_Run', OutputFor='_Main.py')

J = num_base_MrkvStates
N = 500000
MCOUNT = 200

BaseType = AggFiscalType(**init_highschool)
BaseType.cycles = 0
BaseType.AgentCount = N
BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]

AggEco = AggregateDemandEconomy(**init_ADEconomy)
BaseType.get_economy_data(AggEco)

IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
IncShkDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])])
BaseType.IncShkDstn[0].seed = 763607780
BaseType.IncShkDstn[0].reset()
EmployedIncShkDstn = deepcopy(BaseType.IncShkDstn[0])
BaseType.IncShkDstn = [[BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]]
BaseType.IncShkDstn_base = BaseType.IncShkDstn
IncShkDstn_recession = [BaseType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
BaseType.IncShkDstn_recession = IncShkDstn_recession
BaseType.IncShkDstn_recessionUI = IncShkDstn_recession
# BUG-023 fix: was `EmployedIncShkDstn.atoms[0][1] = EmployedIncShkDstn.atoms[0][1] * BaseType.TaxCutIncFactor`
# which mutated one PermShk atom; the intended behavior is to
# rescale every joint atom's TranShk component (atoms[1]).
# See BUGS_private/HAFiscal_BUG-023_taxcut_atoms_typo.md.
EmployedIncShkDstn.atoms = (
    np.asarray(EmployedIncShkDstn.atoms[0], dtype=np.float64),
    np.asarray(EmployedIncShkDstn.atoms[1], dtype=np.float64) * BaseType.TaxCutIncFactor,
)
TaxCutStatesIncShkDstn = [EmployedIncShkDstn] + [IncShkDstn_unemp] * UBspell_normal + [IncShkDstn_unemp_nobenefits]
IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates, 1):
    IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
BaseType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
BaseType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

AggEco.agents = [BaseType]
AggEco.solve()
act_T = AggEco.act_T
Splurge = BaseType.Splurge
E_pLvl = compute_analytical_mean_pLvl(BaseType)
E_TranShk = np.array([1.0, 0.7, 0.7, 0.5])
ui_path = list(np.arange(1, AggEco.num_experiment_periods + 1) * 2) + [0] * 20

# Build ergodic under BASE config
tm_data = build_tm_agg_fiscal(BaseType, mCount=MCOUNT, Cratio=1.0)
ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
dist_mGrid = tm_data['dist_mGrid']
M = len(dist_mGrid)

# Get cPol for base (using base agent at macro_t=0)
base_agent = deepcopy(BaseType)
base_agent.update_mrkv_array("base")
base_agent.solve()
_, cPol_base = build_experiment_period_tm(base_agent, 0, 0, dist_mGrid, Cratio=1.0)

# Get cPol for UI (using UI agent at macro_t=ui_path[0])
eco_ui = deepcopy(AggEco)
eco_ui.switch_shock_type("UI")
eco_ui.solve()
ui_agent = eco_ui.agents[0]
_, cPol_ui = build_experiment_period_tm(ui_agent, ui_path[0], ui_path[1], dist_mGrid, Cratio=1.0)

# Apply micro transitions to the SAME ergodic
micro_normal = base_agent.CondMrkvArrays[0]
micro_ui_mat = ui_agent.CondMrkvArrays[ui_path[0]]

dist_base = _apply_micro_transition(ergodic.copy(), micro_normal, M)
dist_ui = _apply_micro_transition(ergodic.copy(), micro_ui_mat, M)

print(f"Splurge={Splurge:.4f}, E_pLvl={E_pLvl:.4f}")

# ============================================================
# Per-state mean mNrm from the correct distributions
# ============================================================
print("\n" + "=" * 70)
print("Per-state mean mNrm (from ergodic and after micro transitions)")
print("=" * 70)

print(f"\n  State  ergodic     after_normal after_UI     diff(UI-normal)")
for j in range(J):
    erg_j = ergodic[j*M:(j+1)*M]
    base_j = dist_base[j*M:(j+1)*M]
    ui_j = dist_ui[j*M:(j+1)*M]
    erg_mean = np.dot(dist_mGrid, erg_j) / max(np.sum(erg_j), 1e-30)
    base_mean = np.dot(dist_mGrid, base_j) / max(np.sum(base_j), 1e-30)
    ui_mean = np.dot(dist_mGrid, ui_j) / max(np.sum(ui_j), 1e-30)
    print(f"  [{j}]   {erg_mean:8.4f}    {base_mean:8.4f}    {ui_mean:8.4f}    {ui_mean-base_mean:+.6f}")

# ============================================================
# cPol comparison: base vs UI cFunc on the same grid
# ============================================================
print("\n" + "=" * 70)
print("cPol comparison: base vs UI at key mNrm values")
print("=" * 70)

test_mNrm = [0.5, 0.7, 1.0, 1.4, 2.0]
for m in test_mNrm:
    idx = np.searchsorted(dist_mGrid, m)
    idx = min(idx, M-1)
    m_actual = dist_mGrid[idx]
    print(f"\n  mNrm ≈ {m_actual:.4f}:")
    for j in range(J):
        cb = cPol_base[j][idx]
        cu = cPol_ui[j][idx]
        print(f"    State {j}: cPol_base={cb:.6f}, cPol_ui={cu:.6f}, diff={cu-cb:+.6f}")

# ============================================================
# Consumption TE decomposition (corrected)
# ============================================================
print("\n" + "=" * 70)
print("Consumption TE decomposition (corrected)")
print("=" * 70)

fracs_base = np.array([np.sum(dist_base[j*M:(j+1)*M]) for j in range(J)])
fracs_ui = np.array([np.sum(dist_ui[j*M:(j+1)*M]) for j in range(J)])

# Total consumption = (1-S)*C_nrm + S*income_nrm
# where C_nrm = sum_j dot(cPol[j], dist[j])
# and income_nrm = sum_j frac_j * E_TranShk_j

C_nrm_base = sum(np.dot(cPol_base[j], dist_base[j*M:(j+1)*M]) for j in range(J))
C_nrm_ui = sum(np.dot(cPol_ui[j], dist_ui[j*M:(j+1)*M]) for j in range(J))
income_base = np.dot(fracs_base, E_TranShk)
income_ui = np.dot(fracs_ui, E_TranShk)

cons_base = (1-Splurge) * C_nrm_base + Splurge * income_base
cons_ui = (1-Splurge) * C_nrm_ui + Splurge * income_ui
cons_TE = cons_ui - cons_base

# Decompose: what if we hold cPol fixed and only change dist?
# "Distribution effect" with base cPol
C_nrm_ui_basecFunc = sum(np.dot(cPol_base[j], dist_ui[j*M:(j+1)*M]) for j in range(J))
cons_ui_basecFunc = (1-Splurge) * C_nrm_ui_basecFunc + Splurge * income_ui
dist_effect = cons_ui_basecFunc - cons_base

# "Policy effect" = total - distribution
policy_effect = cons_TE - dist_effect

print(f"\n  TM total cons TE (nrm):     {cons_TE:.8f}")
print(f"  TM total cons TE (levels):  {cons_TE * E_pLvl:.8f}")
print(f"  Distribution effect:        {dist_effect:.8f}  ({dist_effect*E_pLvl:.8f} levels)")
print(f"  Policy effect (cFunc diff):  {policy_effect:.8f}  ({policy_effect*E_pLvl:.8f} levels)")

# Now check: which effect dominates?
print(f"\n  Distribution effect share: {dist_effect/cons_TE*100:.1f}%")
print(f"  Policy effect share:       {policy_effect/cons_TE*100:.1f}%")

print("\nDone.")
