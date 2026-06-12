"""
SOLO-pol linear policies: UI extension and TaxCut on a single high school type.

Companion to ``parity_solo_pol_check.py`` (for the Check stimulus, which
requires TM-2D with p-buckets).

These policies are p-linear (Class A), so TM-1D (TM-Q) is exact and TM-2D
is unnecessary.  Both MC-P and TM-Q should agree (within MC sampling noise).

  Single high school type, point beta, no recession, no AD.
  TM-Q only (TM-P has small structural bias from ignoring Cov(p,c)).

Usage:
    PYTHONPATH=/path/to/HARK:$PYTHONPATH python parity_solo_pol_linear.py
    PYTHONPATH=... python parity_solo_pol_linear.py --agents 4000 --seeds 5
    PYTHONPATH=... python parity_solo_pol_linear.py --agents 100 500 2000 8000 --seeds 5

References:
    plans/method-parity-map.md (Class A vs Class D)
    history/20260331-mathematical-derivations-harmenberg.md §14.5
"""

import sys
import os
import time
import argparse
import numpy as np
from copy import deepcopy

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
_HA = os.path.dirname(_THIS_DIR)
if _HA not in sys.path:
    sys.path.insert(0, _HA)

_orig_argv = sys.argv[:]
sys.argv = [sys.argv[0], "1.01", "2.0", "0.7"]

from Parameters import return_parameters
from AggFiscalModel import DualAggFiscalType, AggregateDemandEconomy
try:
    from AggFiscalModel import NormalizedDualAggFiscalType
    HAS_NORM = True
except ImportError:
    HAS_NORM = False
from HARK.distributions import DiscreteDistribution
from tm_methods import (
    calculate_NPV,
    compute_baseline_tm_data,
    compute_pLvl_distribution,
    run_experiment_tm,
    run_experiment_tm_nonbase,
)

sys.argv = _orig_argv


def build_solo_pol_economy(AgentCls, N, seed, variance_reduction=False):
    """Build single high school type economy (SOLO-pol)."""
    params = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")
    (init_d, init_h, init_c, init_ADE, DiscFacDstns, DiscFacCount, _N,
     base_dict, _nmi, _ct, UBspell_normal, num_base_MrkvStates,
     data_EducShares, max_rec, num_exp,
     rec_ch, UI_ch, rec_UI_ch, TC_ch, rec_TC_ch, Ck_ch, rec_Ck_ch) = params

    init_ADE["act_T"] = 200
    eco = AggregateDemandEconomy(**init_ADE)

    # Single high school type, point beta
    a = AgentCls(**init_h)
    a.cycles = 0
    a.AgentCount = int(N)
    a.seed = int(seed)
    a.DiscFac = DiscFacDstns[1].atoms[0][0]  # HS, first beta
    a.get_economy_data(eco)

    iu = DiscreteDistribution(np.array([1.0]),
        [np.array([1.0]), np.array([a.IncUnemp])])
    iunb = DiscreteDistribution(np.array([1.0]),
        [np.array([1.0]), np.array([a.IncUnempNoBenefits])])
    a.IncShkDstn = [[a.IncShkDstn[0]] + [iu] * UBspell_normal + [iunb]]
    a.IncShkDstn_base = a.IncShkDstn

    EmployedIncShkDstn = deepcopy(a.IncShkDstn[0][0])
    # NOTE: removed `atoms[0][1] *= TaxCutIncFactor` typo (PermShk[1] not TranShk; not the
    # right margin or granularity).  Both MC and TM apply the tax cut elsewhere — MC at sim
    # time, TM via _scaled_employed_joint_inc_dstn at per-period build.  See Simulate.py.
    TaxCutStatesIncShkDstn = [EmployedIncShkDstn] + [iu] * UBspell_normal + [iunb]

    rec = [a.IncShkDstn[0] * (2 * (num_exp + 1))]
    a.IncShkDstn_recession = rec
    a.IncShkDstn_recessionUI = rec
    a.IncShkDstn_recessionTaxCut = deepcopy(rec)
    for i in range(2 * num_base_MrkvStates, 18 * num_base_MrkvStates):
        a.IncShkDstn_recessionTaxCut[0][i] = TaxCutStatesIncShkDstn[np.mod(i, 4)]
    a.IncShkDstn_recessionCheck = deepcopy(rec)

    if issubclass(AgentCls, DualAggFiscalType):
        a.setup_Q_measure()

    eco.agents = [a]

    if variance_reduction:
        a.income_shuffle = True
        a.markov_shuffle = True
        a.normalize_pLvl = True

    eco.solve()

    return eco, {
        "base_dict": base_dict,
        "num_exp": num_exp,
        "UI_changes": UI_ch,
        "TaxCut_changes": TC_ch,
        "Check_changes": Ck_ch,
    }


def tm_q_multiplier(economy, shock_type, meta, mCount):
    """Compute TM-Q multiplier (1D, exact for p-linear policies)."""
    bl = compute_baseline_tm_data(economy, mCount=mCount, neutral_measure=True, verbose=False)
    base = run_experiment_tm(economy, "base", mCount=mCount, neutral_measure=True, verbose=False)

    eco = deepcopy(economy)
    eco.switch_shock_type(shock_type)
    eco.solve()
    EconomyMrkv_init = list(np.arange(1, meta["num_exp"] + 1) * 2) + [0] * 20
    exp = run_experiment_tm_nonbase(eco, shock_type, EconomyMrkv_init, bl,
                                    mCount=mCount, neutral_measure=True,
                                    verbose=False)

    Rfree = economy.agents[0].Rfree[0]
    act_T = economy.act_T
    delta_c = np.array(exp["AggCons"]) - np.array(base["AggCons"])
    delta_y = np.array(exp["AggIncome"]) - np.array(base["AggIncome"])
    npv_c = calculate_NPV(delta_c, act_T, Rfree)[-1]
    npv_y = calculate_NPV(delta_y, act_T, Rfree)[-1]
    return npv_c / npv_y if abs(npv_y) > 1e-10 else float("nan")


def mc_multiplier(economy, shock_type, meta, seed, N, variance_reduction, tm_Ep):
    """Compute MC-P multiplier."""
    from test_asymptotic_equality_revised import (
        mc_burnin, restore_intended_act_T_after_counterfactual_switch
    )

    AgentCls = NormalizedDualAggFiscalType if (variance_reduction and HAS_NORM) else DualAggFiscalType
    eco, m = build_solo_pol_economy(AgentCls, N, seed, variance_reduction=variance_reduction)

    bl = compute_baseline_tm_data(eco, mCount=50, neutral_measure=True, verbose=False)
    mc_burnin(eco, warmup=None, tm_data=bl, use_dual=True)

    if variance_reduction and tm_Ep is not None:
        eco.agents[0]._pLvl_norm_target = tm_Ep

    N_mc = eco.agents[0].AgentCount
    intended_T = int(eco.act_T)
    eco.save_state()
    eco.switch_to_counterfactual_mode("base")
    restore_intended_act_T_after_counterfactual_switch(eco, intended_T)
    eco.make_idiosyncratic_shock_histories()

    base_r = eco.run_experiment(**deepcopy(m["base_dict"]), Full_Output=True)
    eco.store_baseline(base_r["AggCons"])

    eco2 = deepcopy(eco)
    eco2.switch_shock_type(shock_type)
    eco2.solve()
    dictt = deepcopy(m["base_dict"])
    dictt.update(**m[f"{shock_type}_changes"])
    dictt["EconomyMrkv_init"] = list(np.arange(1, m["num_exp"] + 1) * 2) + [0] * 20
    exp_r = eco2.run_experiment(**dictt, Full_Output=True)

    Rfree = eco.agents[0].Rfree[0]
    act_T = eco.act_T
    delta_c = np.array(exp_r["AggCons"]) - np.array(base_r["AggCons"])
    delta_y = np.array(exp_r["AggIncome"]) - np.array(base_r["AggIncome"])
    npv_c = calculate_NPV(delta_c, act_T, Rfree)[-1]
    npv_y = calculate_NPV(delta_y, act_T, Rfree)[-1]
    if hasattr(mc_multiplier, "_return_components") and mc_multiplier._return_components:
        return npv_c, npv_y
    return float(npv_c / npv_y) if abs(npv_y) > 1e-10 else float("nan")


def main():
    parser = argparse.ArgumentParser(description="SOLO-pol linear policies (UI, TaxCut)")
    parser.add_argument("--agents", type=int, nargs="+", default=[500, 2000])
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--mcount", type=int, default=100)
    parser.add_argument("--variance-reduction", action="store_true", default=True)
    parser.add_argument("--no-variance-reduction", dest="variance_reduction", action="store_false")
    args = parser.parse_args()

    seeds = list(range(args.seeds))
    mCount = args.mcount
    vr = args.variance_reduction

    print(f"SOLO-pol LINEAR policies (UI, TaxCut)")
    print(f"  Single HS type, point beta, no recession, TM-Q (1D)")
    print(f"  Agent counts: {args.agents}, seeds={len(seeds)}, mCount={mCount}, variance_reduction={vr}\n")

    # TM reference (deterministic, computed once)
    eco_ref, meta = build_solo_pol_economy(DualAggFiscalType, 1, 0)
    u = getattr(eco_ref.agents[0], 'Urate_normal', 0.044)
    g, p = compute_pLvl_distribution(eco_ref.agents[0], n_points=200, unemployment_rate=u)
    tm_Ep = float(np.dot(p, g))

    policies = ["UI", "TaxCut"]

    print("=" * 75)
    print("  TM-Q (deterministic)")
    print("=" * 75)
    tm_results = {}
    for pol in policies:
        t0 = time.time()
        mult = tm_q_multiplier(eco_ref, pol, meta, mCount)
        elapsed = time.time() - t0
        tm_results[pol] = mult
        print(f"  {pol:>8}: TM-Q={mult:.4f}  ({elapsed:.1f}s)")

    print(f"\n{'=' * 75}")
    print(f"  MC-P (variance_reduction={vr})")
    print(f"{'=' * 75}")
    print(f"\n{'N':>6} {'Policy':>8} {'MC-P mean':>10} {'MC-P SE':>10} "
          f"{'TM-Q':>10} {'|MC-TM|/SE':>11} {'time':>6}")
    print("-" * 65)

    all_results = {}
    for N in args.agents:
        for pol in policies:
            seed_P = []
            t0 = time.time()
            for s in seeds:
                mP = mc_multiplier(eco_ref, pol, meta, s * 100, N, vr, tm_Ep)
                seed_P.append(mP)
            elapsed = time.time() - t0

            n = len(seeds)
            mean_P = float(np.mean(seed_P))
            se_P = float(np.std(seed_P) / np.sqrt(n))
            tm_val = tm_results[pol]
            gap_se = abs(mean_P - tm_val) / se_P if se_P > 1e-16 else float("nan")
            ok = "PASS" if gap_se <= 3.0 else "FAIL"
            print(f"{N:>6d} {pol:>8} {mean_P:10.4f} {se_P:10.4f} "
                  f"{tm_val:10.4f} {gap_se:11.2f} {elapsed:5.0f}s  {ok}")
            all_results[(N, pol)] = {"mean": mean_P, "se": se_P, "gap_se": gap_se}

    print(f"\n  Pass criterion: |MC-P mean - TM-Q| <= 3 * MC-P SE")
    print(f"  Reference: math-derive-harm §14.5 (TM-Q is exact for p-linear policies)")


if __name__ == "__main__":
    main()
