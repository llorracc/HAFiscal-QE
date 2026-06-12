"""
Phase 2 starter: CDC vs ESC aggregate-consumption comparison at baseline.

Per plans/20260427-0211h_cdc-esc-tm-kernel-comparison-and-suffix.md §6
sub-task 2.1 (CDC) + 2.2 (ESC), but limited to baseline (no policy
intervention). This establishes the methodology + comparison harness
before scaling to the actual multiplier scenarios (Check, UI, TaxCut).

Setup:
  - 1 HS cohort, single agent (single mid-β; per L3a-c)
  - propagate_experiment_tm_a at T=24 (2 years quarterly) with macro
    state 0 throughout (no recession, no policy)
  - Run for both interpretation='CDC' and 'ESC'
  - Compare AggCons (level series) and per-period ratio

Per Phase 2 §6.0 caveats:
  (a) Don't expect simple (1-ς) rescaling; kernel ergodics differ
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

# CLAUDE.md: patch sys.argv before importing EstimParameters.
sys.argv = ['phase2_baseline_cdc_vs_esc']

from EstimParameters import init_highschool, init_ADEconomy, UBspell_normal
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from tm_methods import (
    build_tm_agg_fiscal_a,
    find_ergodic_distribution,
    propagate_experiment_tm_a,
)
from HARK.distributions import DiscreteDistribution


def build_HS_agent():
    init = deepcopy(init_highschool)
    agent = AggFiscalType(**init)
    agent.cycles = 0
    economy = AggregateDemandEconomy(**init_ADEconomy)
    agent.get_economy_data(economy)
    IncomeDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([agent.IncUnemp])]
    )
    IncomeDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([agent.IncUnempNoBenefits])]
    )
    agent.IncShkDstn = [
        [agent.IncShkDstn[0]]
        + [IncomeDstn_unemp] * UBspell_normal
        + [IncomeDstn_unemp_nobenefits]
    ]
    agent.IncShkDstn_base = agent.IncShkDstn
    economy.agents = [agent]
    economy.solve()
    return agent


def main():
    print("=" * 72)
    print("Phase 2 starter: CDC vs ESC AggCons comparison (baseline, no policy)")
    print("=" * 72)

    print("\nBuilding + solving HS agent...")
    t0 = time.time()
    agent = build_HS_agent()
    # AgentCount is needed for level scaling inside propagate_experiment_tm_a
    agent.AgentCount = 10000
    print(f"  agent setup in {time.time()-t0:.1f}s")

    T_sim = 24  # 2 years quarterly

    results = {}
    for interp in ['CDC', 'ESC']:
        print(f"\n--- Running {interp} ---")
        t0 = time.time()

        # BUG-051 matched-pair fix: this diagnostic loops `interp` over both
        # 'CDC' and 'ESC' within a single process. build_tm_agg_fiscal_a
        # validates its explicit interpretation against HAFISCAL_INTERPRETATION,
        # so set the env to match THIS arm before the kernel calls and restore
        # the prior value after, so the arms don't leak into each other (and
        # the guard is never weakened).
        _prev_interp = os.environ.get('HAFISCAL_INTERPRETATION')
        os.environ['HAFISCAL_INTERPRETATION'] = interp
        try:
            # Build baseline TM ergodic under this interpretation
            tm_data = build_tm_agg_fiscal_a(agent, interpretation=interp)
            ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
            print(f"  baseline TM + ergodic: {time.time()-t0:.1f}s; "
                  f"ergodic sums to {ergodic.sum():.6f}")

            # Run experiment propagator at constant macro state 0 (baseline-no-policy)
            t0 = time.time()
            out = propagate_experiment_tm_a(
                agent,
                baseline_ergodic=ergodic,
                EconomyMrkv_init=[0] * T_sim,
                dist_aGrid=tm_data['dist_aGrid'],
                E_pLvl=1.0,
                Cratio=1.0,
                act_T=T_sim,
                shock_type=None,
                interpretation=interp,
            )
        finally:
            if _prev_interp is None:
                os.environ.pop('HAFISCAL_INTERPRETATION', None)
            else:
                os.environ['HAFISCAL_INTERPRETATION'] = _prev_interp
        elapsed = time.time() - t0
        results[interp] = out
        print(f"  propagate done: {elapsed:.1f}s")
        print(f"  AggCons[:5]: {out['AggCons'][:5].tolist()}")
        print(f"  AggCons[-5:]: {out['AggCons'][-5:].tolist()}")

    print("\n" + "=" * 72)
    print("CDC vs ESC comparison")
    print("=" * 72)
    cdc = results['CDC']['AggCons']
    esc = results['ESC']['AggCons']
    cdc_y = results['CDC']['AggIncome']
    esc_y = results['ESC']['AggIncome']

    print(f"  Stationarity check (period 5 vs period 20):")
    print(f"    CDC: AggCons[5]={cdc[5]:.4f}, AggCons[20]={cdc[20]:.4f}, "
          f"diff={abs(cdc[20]-cdc[5])/cdc[5]:.4%}")
    print(f"    ESC: AggCons[5]={esc[5]:.4f}, AggCons[20]={esc[20]:.4f}, "
          f"diff={abs(esc[20]-esc[5])/esc[5]:.4%}")

    print(f"\n  Mean over periods 4-{T_sim-1} (post-burnin):")
    cdc_mean = float(np.mean(cdc[4:]))
    esc_mean = float(np.mean(esc[4:]))
    cdc_y_mean = float(np.mean(cdc_y[4:]))
    esc_y_mean = float(np.mean(esc_y[4:]))
    print(f"    CDC AggCons mean = {cdc_mean:.4f}, AggIncome mean = {cdc_y_mean:.4f}")
    print(f"    ESC AggCons mean = {esc_mean:.4f}, AggIncome mean = {esc_y_mean:.4f}")
    print(f"    ESC/CDC AggCons ratio = {esc_mean/cdc_mean:.4f}")
    print(f"    ESC/CDC AggIncome ratio = {esc_y_mean/cdc_y_mean:.4f}")
    print(f"    Splurge ς = {agent.Splurge:.4f}; (1-ς) = {1-agent.Splurge:.4f}")

    # Save trajectories for post-analysis
    import json
    out_path = '/tmp/phase2_baseline_cdc_vs_esc_results.json'
    with open(out_path, 'w') as f:
        json.dump({
            'CDC_AggCons': cdc.tolist(),
            'CDC_AggIncome': cdc_y.tolist(),
            'ESC_AggCons': esc.tolist(),
            'ESC_AggIncome': esc_y.tolist(),
            'splurge': float(agent.Splurge),
            'T_sim': T_sim,
        }, f, indent=2)
    print(f"\n  Trajectories saved to {out_path}")
    print("=" * 72)


if __name__ == "__main__":
    main()
