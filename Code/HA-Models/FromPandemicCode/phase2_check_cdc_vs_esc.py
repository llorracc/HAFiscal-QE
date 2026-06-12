"""
Phase 2: stimulus-check CDC vs ESC comparison.

Per plans/20260427-0211h_cdc-esc-tm-kernel-comparison-and-suffix.md §6
sub-tasks 2.1 + 2.2 + 2.3 (multipliers for one policy).

Setup:
  - Single HS agent (Reduced_Run scope)
  - tm_a_indexed=True (use a-indexed TM kernel)
  - Run baseline (no shock) under both interpretations
  - Run shock_type='Check' under both interpretations
  - Compare AggCons and AggIncome trajectories
  - Compute simple multiplier: NPV(C_check - C_base) / sum(check expenditure)

Uses production wrappers (compute_baseline_tm_data, run_experiment_tm_nonbase)
which now thread the interpretation parameter through to the a-indexed
kernel chain after Phase 2 dispatch wiring (commit 48481ede).

Per Phase 2 §6.0 caveats:
  (a) CDC/ESC differences emerge under policy interventions; baseline
      is nearly identical (per phase2_baseline_cdc_vs_esc.py finding)
  (b) Direct kernel invocation; no production-pipeline involvement
"""

import os
import sys
import time
import numpy as np
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

# CLAUDE.md: patch sys.argv before importing EstimParameters / Parameters.
sys.argv = ['phase2_check_cdc_vs_esc']

from HARK.distributions import DiscreteDistribution
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from Parameters import return_parameters
from tm_methods import (
    compute_baseline_tm_data,
    run_experiment_tm_nonbase,
    propagate_experiment_tm_a,
)


def build_HS_economy():
    """Build a single-type HS economy with full IncShkDstn variants needed
    for switch_shock_type to work for 'Check' / 'recessionCheck'.

    Under TM-a (tm_a_indexed=True) the kernel is deterministic on the
    (a, j) grid; AgentCount is purely a level-scaling multiplier inside
    propagate_experiment_tm_a (`scale = AgentCount * E_pLvl * pLvl_factor`),
    not an MC sample count. We set AgentCount=1 so the returned AggCons /
    AggIncome are already per-capita.
    """
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
    BaseType.DiscFac = DiscFacDstns[1].atoms[0][0]  # mid β atom

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

    # Variants needed for switch_shock_type:
    IncShkDstn_recession = [
        BaseType.IncShkDstn[0] * (2 * (num_experiment_periods + 1))]
    BaseType.IncShkDstn_recession = IncShkDstn_recession
    BaseType.IncShkDstn_recessionUI = IncShkDstn_recession
    # BUG-023 fix: scale every joint atom's TranShk by TaxCutIncFactor
    # (atoms[0]=PermShk, atoms[1]=TranShk). Per Simulate.py:241-244.
    # Not actually used by 'Check' shock_type, but kept consistent.
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

    # Critical: enable a-indexed TM dispatch
    BaseType.tm_a_indexed = True

    economy.agents = [BaseType]
    economy.solve()
    return economy, num_experiment_periods


def run_one_interpretation(economy_template, shock_type, interpretation,
                           num_experiment_periods, mCount=50):
    """Run a single (shock_type × interpretation) experiment via the
    production wrapper. Returns (AggCons, AggIncome) per-capita series."""
    eco = deepcopy(economy_template)
    for agent in eco.agents:
        agent.interpretation = interpretation

    # 1. Baseline TM data (in 'base' Markov config)
    baseline_tm_data = compute_baseline_tm_data(eco, mCount=mCount, verbose=False)

    # 2. Switch to the shock type and re-solve
    eco.switch_shock_type(shock_type)
    eco.solve()

    act_T = eco.act_T

    # 3. Build the experiment Markov path. For Check (no recession), use
    #    [0]*act_T (no recession; check applied via check_info in period 0).
    EconomyMrkv_init = [0] * act_T

    # 4. Run via wrapper (handles a-indexed dispatch + check_info auto-construction)
    result = run_experiment_tm_nonbase(
        eco, shock_type, EconomyMrkv_init, baseline_tm_data,
        mCount=mCount, verbose=False,
    )
    return {
        'AggCons_pc': np.asarray(result['AggCons']),
        'AggIncome_pc': np.asarray(result['AggIncome']),
        'act_T': act_T,
    }


def run_baseline(economy_template, interpretation, num_experiment_periods, mCount=50):
    """Compute the baseline (no-shock) AggCons, also through the a-indexed kernel."""
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
    print("Phase 2: stimulus-check CDC vs ESC comparison (HS, Reduced_Run)")
    print("=" * 72)

    print("\nBuilding HS economy...")
    t0 = time.time()
    eco, num_experiment_periods = build_HS_economy()
    print(f"  setup + solve: {time.time()-t0:.1f}s")
    print(f"  CheckStimLvl = {eco.agents[0].CheckStimLvl}")
    print(f"  Splurge ς = {eco.agents[0].Splurge:.4f}; (1-ς) = {1-eco.agents[0].Splurge:.4f}")

    Rfree = eco.agents[0].Rfree[0]

    out = {}
    for interp in ['CDC', 'ESC']:
        print(f"\n--- {interp} interpretation ---")
        t0 = time.time()
        base = run_baseline(eco, interp, num_experiment_periods)
        print(f"  baseline propagation: {time.time()-t0:.1f}s")
        t0 = time.time()
        check = run_one_interpretation(eco, 'Check', interp, num_experiment_periods)
        print(f"  Check experiment: {time.time()-t0:.1f}s")
        out[interp] = {'base': base, 'check': check}

        # Compute simple NPV multiplier (ratio of NPV consumption response to
        # NPV of fiscal expenditure). The check expenditure is
        # CheckStimLvl·E[pLvl] in period 0.
        cdiff = check['AggCons_pc'] - base['AggCons_pc']
        T = check['act_T']
        disc = np.array([Rfree ** (-t) for t in range(T)])
        npv_cdiff = float(np.sum(disc * cdiff))
        # Income-based NPV (alternative): sum of Income difference in check period
        ydiff = check['AggIncome_pc'] - base['AggIncome_pc']
        npv_ydiff = float(np.sum(disc * ydiff))
        # Multiplier = NPV(consumption response) / NPV(income transfer)
        mult = npv_cdiff / max(npv_ydiff, 1e-12)
        print(f"  AggCons_pc[base 0..3]: {[f'{x:.4f}' for x in base['AggCons_pc'][:4]]}")
        print(f"  AggCons_pc[check 0..3]: {[f'{x:.4f}' for x in check['AggCons_pc'][:4]]}")
        print(f"  AggCons_pc[check-base 0..6]: {[f'{x:+.5f}' for x in cdiff[:7]]}")
        print(f"  NPV(C diff) = {npv_cdiff:.5f}; NPV(Y diff) = {npv_ydiff:.5f}")
        print(f"  Multiplier (NPV C / NPV Y) = {mult:.4f}")

    print("\n" + "=" * 72)
    print("CDC vs ESC comparison")
    print("=" * 72)
    cdc_mult = sum((out['CDC']['check']['AggCons_pc'] - out['CDC']['base']['AggCons_pc']) *
                   np.array([Rfree ** (-t) for t in range(out['CDC']['check']['act_T'])])) / \
               sum((out['CDC']['check']['AggIncome_pc'] - out['CDC']['base']['AggIncome_pc']) *
                   np.array([Rfree ** (-t) for t in range(out['CDC']['check']['act_T'])]))
    esc_mult = sum((out['ESC']['check']['AggCons_pc'] - out['ESC']['base']['AggCons_pc']) *
                   np.array([Rfree ** (-t) for t in range(out['ESC']['check']['act_T'])])) / \
               sum((out['ESC']['check']['AggIncome_pc'] - out['ESC']['base']['AggIncome_pc']) *
                   np.array([Rfree ** (-t) for t in range(out['ESC']['check']['act_T'])]))
    print(f"  CDC multiplier = {cdc_mult:.4f}")
    print(f"  ESC multiplier = {esc_mult:.4f}")
    print(f"  difference     = {cdc_mult - esc_mult:+.4f}  ({100*(cdc_mult - esc_mult):+.2f}pp)")
    print("=" * 72)


if __name__ == "__main__":
    main()
