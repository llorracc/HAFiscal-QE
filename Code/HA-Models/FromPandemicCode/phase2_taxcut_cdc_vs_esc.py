"""
Phase 2: tax-cut CDC vs ESC comparison.

Per plans/20260427-0211h_cdc-esc-tm-kernel-comparison-and-suffix.md §6
sub-task 2.1 + 2.2 (multipliers — second policy after Check).

Setup: identical to phase2_check_cdc_vs_esc.py but with shock_type='TaxCut'
and EconomyMrkv_init = [2, 4, 6, 8, 10, 12, 14, 16, 0, 0, ...] — the
no-recession TaxCut path that walks through the experiment-period macro
states for ``num_experiment_periods`` then drops to macro 0.

Routes through production wrappers (compute_baseline_tm_data,
run_experiment_tm_nonbase) using tm_a_indexed=True after Phase 5 dispatch
wiring (commit 48481ede).
"""

import os
import sys
import time
import numpy as np
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

sys.argv = ['phase2_taxcut_cdc_vs_esc']

from HARK.distributions import DiscreteDistribution
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from tm_methods import (
    compute_baseline_tm_data,
    run_experiment_tm_nonbase,
    propagate_experiment_tm_a,
)


def build_HS_economy():
    """TM-a is deterministic on the (a, j) grid; AgentCount is purely a
    level-scaling multiplier inside propagate_experiment_tm_a, not an MC
    sample count. Set AgentCount=1 so AggCons/AggIncome are returned
    already in per-capita units."""
    [init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
     DiscFacCount, AgentCountTotal, base_dict, num_max_iterations_solvingAD,
     convergence_tol_solvingAD, UBspell_normal, num_base_MrkvStates,
     data_EducShares, max_recession_duration, num_experiment_periods,
     recession_changes, UI_changes, recession_UI_changes,
     TaxCut_changes, recession_TaxCut_changes,
     Check_changes, recession_Check_changes] = return_parameters(
        Parametrization='Reduced_Run', OutputFor='_Main.py')

    BaseType = AggFiscalType(**init_highschool)
    BaseType.cycles = 0
    BaseType.AgentCount = 1
    BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]

    economy = AggregateDemandEconomy(**init_ADEconomy)
    BaseType.get_economy_data(economy)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnemp])])
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([BaseType.IncUnempNoBenefits])])

    BaseType.IncShkDstn[0].seed = 763607780
    BaseType.IncShkDstn[0].reset()
    EmployedIncShkDstn = deepcopy(BaseType.IncShkDstn[0])
    BaseType.IncShkDstn = [
        [BaseType.IncShkDstn[0]] + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits]]
    BaseType.IncShkDstn_base = BaseType.IncShkDstn

    IncShkDstn_recession = [
        BaseType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
    BaseType.IncShkDstn_recession = IncShkDstn_recession
    BaseType.IncShkDstn_recessionUI = IncShkDstn_recession
    # BUG-023 fix: scale every joint atom's TranShk by TaxCutIncFactor
    # (atoms[0]=PermShk, atoms[1]=TranShk per HARK convention).
    # The typo `.atoms[0][1] *=` mutates one PermShk atom; production
    # Simulate.py:241-244 was patched in BUG-023 commit.
    EmployedIncShkDstn_TC = deepcopy(EmployedIncShkDstn)
    EmployedIncShkDstn_TC.atoms = (
        np.asarray(EmployedIncShkDstn_TC.atoms[0], dtype=np.float64),
        np.asarray(EmployedIncShkDstn_TC.atoms[1], dtype=np.float64) * BaseType.TaxCutIncFactor,
    )
    TaxCutStatesIncShkDstn = (
        [EmployedIncShkDstn_TC] + [IncShkDstn_unemp] * UBspell_normal
        + [IncShkDstn_unemp_nobenefits])
    IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
    for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates, 1):
        IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
    BaseType.IncShkDstn_recessionTaxCut = IncShkDstn_recessionTaxCut
    BaseType.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

    BaseType.tm_a_indexed = True

    economy.agents = [BaseType]
    economy.solve()
    return economy, num_experiment_periods


def mrkv_path_taxcut_no_recession(num_experiment_periods, total_T):
    """No-recession TaxCut Markov path: walk macro 2,4,6,…,2N then macro 0."""
    head = list(np.arange(1, num_experiment_periods + 1) * 2)
    tail_len = max(0, total_T - len(head))
    return head + [0] * tail_len


def run_one_interpretation(economy_template, interpretation, num_experiment_periods,
                           mCount=50):
    eco = deepcopy(economy_template)
    for agent in eco.agents:
        agent.interpretation = interpretation

    baseline_tm_data = compute_baseline_tm_data(eco, mCount=mCount, verbose=False)

    eco.switch_shock_type('TaxCut')
    eco.solve()

    act_T = eco.act_T
    EconomyMrkv_init = mrkv_path_taxcut_no_recession(num_experiment_periods, act_T)

    result = run_experiment_tm_nonbase(
        eco, 'TaxCut', EconomyMrkv_init, baseline_tm_data,
        mCount=mCount, verbose=False,
    )
    return {
        'AggCons_pc': np.asarray(result['AggCons']),
        'AggIncome_pc': np.asarray(result['AggIncome']),
        'act_T': act_T,
        'EconomyMrkv_init': EconomyMrkv_init,
    }


def run_baseline(economy_template, interpretation, mCount=50):
    eco = deepcopy(economy_template)
    for agent in eco.agents:
        agent.interpretation = interpretation
    baseline_tm_data = compute_baseline_tm_data(eco, mCount=mCount, verbose=False)
    bd0 = baseline_tm_data[0]
    base_agent = eco.agents[0]

    act_T = eco.act_T
    zero_path = [0] * act_T

    base_res = propagate_experiment_tm_a(
        base_agent, bd0['ergodic'], zero_path,
        bd0['dist_aGrid'], bd0['E_pLvl'],
        Cratio=1.0, act_T=act_T, neutral_measure=False,
        check_info=None,
        interpretation=interpretation,
    )
    return {
        'AggCons_pc': np.asarray(base_res['AggCons']),
        'AggIncome_pc': np.asarray(base_res['AggIncome']),
        'act_T': act_T,
    }


def main():
    print("=" * 72)
    print("Phase 2: tax-cut CDC vs ESC comparison (HS, Reduced_Run)")
    print("=" * 72)

    print("\nBuilding HS economy...")
    t0 = time.time()
    eco, num_experiment_periods = build_HS_economy()
    print(f"  setup + solve: {time.time()-t0:.1f}s")
    print(f"  TaxCutIncFactor = {eco.agents[0].TaxCutIncFactor}")
    print(f"  num_experiment_periods = {num_experiment_periods}")
    print(f"  Splurge ς = {eco.agents[0].Splurge:.4f}; (1-ς) = {1-eco.agents[0].Splurge:.4f}")

    Rfree = eco.agents[0].Rfree[0]

    out = {}
    for interp in ['CDC', 'ESC']:
        print(f"\n--- {interp} interpretation ---")
        t0 = time.time()
        base = run_baseline(eco, interp)
        print(f"  baseline propagation: {time.time()-t0:.1f}s")
        t0 = time.time()
        tc = run_one_interpretation(eco, interp, num_experiment_periods)
        print(f"  TaxCut experiment: {time.time()-t0:.1f}s")
        out[interp] = {'base': base, 'tc': tc}

        cdiff = tc['AggCons_pc'] - base['AggCons_pc']
        ydiff = tc['AggIncome_pc'] - base['AggIncome_pc']
        T = tc['act_T']
        disc = np.array([Rfree ** (-t) for t in range(T)])
        npv_cdiff = float(np.sum(disc * cdiff))
        npv_ydiff = float(np.sum(disc * ydiff))
        mult = npv_cdiff / max(npv_ydiff, 1e-12)
        print(f"  AggCons_pc[base 0..3]: {[f'{x:.4f}' for x in base['AggCons_pc'][:4]]}")
        print(f"  AggCons_pc[tc 0..3]:   {[f'{x:.4f}' for x in tc['AggCons_pc'][:4]]}")
        print(f"  AggCons_pc[tc-base 0..9]: {[f'{x:+.5f}' for x in cdiff[:10]]}")
        print(f"  AggIncome_pc[tc-base 0..9]: {[f'{x:+.5f}' for x in ydiff[:10]]}")
        print(f"  NPV(C diff) = {npv_cdiff:.5f}; NPV(Y diff) = {npv_ydiff:.5f}")
        print(f"  Multiplier (NPV C / NPV Y) = {mult:.4f}")

    print("\n" + "=" * 72)
    print("CDC vs ESC comparison (TaxCut, no recession)")
    print("=" * 72)
    for interp in ['CDC', 'ESC']:
        T = out[interp]['tc']['act_T']
        disc = np.array([Rfree ** (-t) for t in range(T)])
        cdiff = out[interp]['tc']['AggCons_pc'] - out[interp]['base']['AggCons_pc']
        ydiff = out[interp]['tc']['AggIncome_pc'] - out[interp]['base']['AggIncome_pc']
        out[interp]['mult'] = float(np.sum(disc * cdiff) / np.sum(disc * ydiff))

    cdc_m = out['CDC']['mult']
    esc_m = out['ESC']['mult']
    print(f"  CDC multiplier = {cdc_m:.4f}")
    print(f"  ESC multiplier = {esc_m:.4f}")
    print(f"  difference     = {cdc_m - esc_m:+.4f}  ({100*(cdc_m - esc_m):+.2f}pp)")
    print("=" * 72)


if __name__ == "__main__":
    main()
