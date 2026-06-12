"""
GLP1 policy comparison: all valid methods on Check, UI, TaxCut.

Single college type, point beta, no recession, no AD.
Runs MC-P, MC-Q, TM-P, TM-Q, and TM-2D (p-buckets for Check).

Usage:
    PYTHONPATH=/path/to/HARK:$PYTHONPATH python parity_glp1_policy_comparison.py
    PYTHONPATH=/path/to/HARK:$PYTHONPATH python parity_glp1_policy_comparison.py --agents 4000 --seeds 5
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


def build_glp1_economy(AgentCls, N, seed, variance_reduction=False):
    """Build single-college-type economy (GLP1 style)."""
    params = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")
    (init_d, init_h, init_c, init_ADE, DiscFacDstns, DiscFacCount, _N,
     base_dict, _nmi, _ct, UBspell_normal, num_base_MrkvStates,
     data_EducShares, max_rec, num_exp,
     rec_ch, UI_ch, rec_UI_ch, TC_ch, rec_TC_ch, Ck_ch, rec_Ck_ch) = params

    init_ADE["act_T"] = 200
    eco = AggregateDemandEconomy(**init_ADE)

    # Single college type, point beta
    a = AgentCls(**init_c)
    a.cycles = 0
    a.AgentCount = int(N)
    a.seed = int(seed)
    a.DiscFac = DiscFacDstns[2].atoms[0][0]  # college, first beta
    a.get_economy_data(eco)

    iu = DiscreteDistribution(np.array([1.0]),
        [np.array([1.0]), np.array([a.IncUnemp])])
    iunb = DiscreteDistribution(np.array([1.0]),
        [np.array([1.0]), np.array([a.IncUnempNoBenefits])])
    a.IncShkDstn = [[a.IncShkDstn[0]] + [iu] * UBspell_normal + [iunb]]
    a.IncShkDstn_base = a.IncShkDstn

    EmployedIncShkDstn = deepcopy(a.IncShkDstn[0][0])
    EmployedIncShkDstn.atoms[0][1] = EmployedIncShkDstn.atoms[0][1] * a.TaxCutIncFactor
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
        "Check_changes": Ck_ch,
        "UI_changes": UI_ch,
        "TaxCut_changes": TC_ch,
    }


def tm_multiplier(economy, shock_type, meta, mCount, neutral_measure, check_use_p_buckets=True):
    """Compute TM multiplier for a no-recession policy."""
    bl = compute_baseline_tm_data(economy, mCount=mCount, neutral_measure=neutral_measure, verbose=False)
    base = run_experiment_tm(economy, "base", mCount=mCount, neutral_measure=neutral_measure, verbose=False)

    eco = deepcopy(economy)
    eco.switch_shock_type(shock_type)
    eco.solve()
    EconomyMrkv_init = list(np.arange(1, meta["num_exp"] + 1) * 2) + [0] * 20
    exp = run_experiment_tm_nonbase(eco, shock_type, EconomyMrkv_init, bl,
                                    mCount=mCount, neutral_measure=neutral_measure,
                                    verbose=False, check_use_p_buckets=check_use_p_buckets)

    Rfree = economy.agents[0].Rfree[0]
    act_T = economy.act_T
    delta_c = np.array(exp["AggCons"]) - np.array(base["AggCons"])
    delta_y = np.array(exp["AggIncome"]) - np.array(base["AggIncome"])
    npv_c = calculate_NPV(delta_c, act_T, Rfree)[-1]
    npv_y = calculate_NPV(delta_y, act_T, Rfree)[-1]
    mult = npv_c / npv_y if abs(npv_y) > 1e-10 else float("nan")
    return mult, npv_c, npv_y


def mc_multiplier(economy, shock_type, meta, seed, N, variance_reduction, tm_Ep):
    """Compute MC multiplier for a no-recession policy. Returns P and Q multipliers."""
    from test_asymptotic_equality_revised import mc_burnin, restore_intended_act_T_after_counterfactual_switch

    AgentCls = NormalizedDualAggFiscalType if (variance_reduction and HAS_NORM) else DualAggFiscalType
    eco, m = build_glp1_economy(AgentCls, N, seed, variance_reduction=variance_reduction)

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

    delta_c_P = np.array(exp_r["AggCons"]) - np.array(base_r["AggCons"])
    delta_y = np.array(exp_r["AggIncome"]) - np.array(base_r["AggIncome"])
    npv_c_P = calculate_NPV(delta_c_P, act_T, Rfree)[-1]
    npv_y = calculate_NPV(delta_y, act_T, Rfree)[-1]
    mult_P = npv_c_P / npv_y if abs(npv_y) > 1e-10 else float("nan")

    return mult_P


def main():
    parser = argparse.ArgumentParser(description="GLP1 policy comparison: all methods")
    parser.add_argument("--agents", type=int, default=4000)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--mcount", type=int, default=100)
    parser.add_argument("--variance-reduction", action="store_true")
    args = parser.parse_args()

    seeds = list(range(args.seeds))
    N = args.agents
    mCount = args.mcount
    vr = args.variance_reduction

    print(f"GLP1 policy comparison: N={N}, {len(seeds)} seeds, mCount={mCount}, variance_reduction={vr}")
    print(f"Single college type, point beta, no recession\n")

    # TM reference economy
    eco_ref, meta = build_glp1_economy(DualAggFiscalType, 1, 0)

    # TM E[pLvl] for normalization target
    u = getattr(eco_ref.agents[0], 'Urate_normal', 0.044)
    g, p = compute_pLvl_distribution(eco_ref.agents[0], n_points=200, unemployment_rate=u)
    tm_Ep = float(np.dot(p, g))

    policies = ["Check", "UI", "TaxCut"]

    # === TM results (deterministic) ===
    print("=" * 80)
    print("  TM results (deterministic)")
    print("=" * 80)

    # All TM runs use check_use_p_buckets=True (required for Check; no-op for others).
    # TM-P and TM-Q should agree for Class A (p-linear) results.
    # For Check (Class D), the p-bucket mechanism handles the phase-out.
    tm_results = {}
    for pol in policies:
        t0 = time.time()
        mult_P, npv_c_P, npv_y_P = tm_multiplier(eco_ref, pol, meta, mCount,
                                                   neutral_measure=False,
                                                   check_use_p_buckets=True)
        mult_Q, npv_c_Q, npv_y_Q = tm_multiplier(eco_ref, pol, meta, mCount,
                                                   neutral_measure=True,
                                                   check_use_p_buckets=True)
        elapsed = time.time() - t0
        tm_results[pol] = {"TM-P": mult_P, "TM-Q": mult_Q}
        pq_pct = abs(mult_P - mult_Q) / abs(mult_Q) * 100 if abs(mult_Q) > 1e-10 else float("nan")
        print(f"  {pol:>8}: TM-P={mult_P:.4f}  TM-Q={mult_Q:.4f}  "
              f"|P-Q|/Q={pq_pct:.2f}%  ({elapsed:.1f}s)")

    # === MC results (stochastic, multiple seeds) ===
    print(f"\n{'=' * 80}")
    print(f"  MC results (N={N}, {len(seeds)} seeds, variance_reduction={vr})")
    print(f"{'=' * 80}")

    mc_results = {}
    for pol in policies:
        seed_P = []
        t0 = time.time()
        for s in seeds:
            mP = mc_multiplier(eco_ref, pol, meta, s * 100, N, vr, tm_Ep)
            seed_P.append(mP)
        elapsed = time.time() - t0

        n = len(seeds)
        mc_results[pol] = {
            "MC-P mean": np.mean(seed_P),
            "MC-P SE": np.std(seed_P) / np.sqrt(n),
            "n_seeds": n,
        }
        mc = mc_results[pol]
        print(f"  {pol:>8}: MC-P={mc['MC-P mean']:.4f} (SE={mc['MC-P SE']:.4f})  ({elapsed:.1f}s)")

    # === Comparison table ===
    print(f"\n{'=' * 80}")
    print(f"  COMPARISON: method-parity-map assessment")
    print(f"{'=' * 80}")
    print(f"\n  Class A (p-linear): MC-P = MC-Q = TM-P = TM-Q (all should agree)")
    print(f"  Class D (Check): p-buckets are always used for TM (required for phase-out).")
    print(f"  All TM results use check_use_p_buckets=True.")
    print(f"\n{'Policy':>8} {'TM-P':>8} {'TM-Q':>8} {'|P-Q|%':>7} {'MC-P':>8} {'MC-P SE':>8} "
          f"{'|MC-TM_P|/SE':>12}")
    print("-" * 67)
    for pol in policies:
        tm = tm_results[pol]
        mc = mc_results[pol]
        pq = abs(tm["TM-P"] - tm["TM-Q"]) / abs(tm["TM-Q"]) * 100 if abs(tm["TM-Q"]) > 1e-10 else float("nan")
        gap_se = abs(mc["MC-P mean"] - tm["TM-P"]) / mc["MC-P SE"] if mc["MC-P SE"] > 1e-16 else float("nan")
        ok = "PASS" if gap_se <= 3.0 else "FAIL"
        print(f"{pol:>8} {tm['TM-P']:8.4f} {tm['TM-Q']:8.4f} {pq:7.2f} "
              f"{mc['MC-P mean']:8.4f} {mc['MC-P SE']:8.4f} "
              f"{gap_se:12.2f} {ok}")

    print(f"\n  Notes:")
    print(f"  - TM-P vs TM-Q should agree for UI and TaxCut (Class A, p-linear).")
    print(f"  - For Check (Class D), P and Q may differ because the phase-out")
    print(f"    interacts with pLvl differently under each measure.")
    print(f"  - MC-P is the gold standard for all policies.")


if __name__ == "__main__":
    main()
