"""
Compare MC variance reduction techniques on 1-Gatekeeper and 2-Harness (--phase baseline).

Three configurations:
  baseline     — standard DualAggFiscalType
  shuffle      — income_shuffle=True
  shuffle+norm — NormalizedDualAggFiscalType + income_shuffle + normalize_pLvl

Usage:
    python parity_variance_reduction_comparison.py
    python parity_variance_reduction_comparison.py --agents 2000 --seeds 5
"""

import sys
import os
import time
import argparse
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
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
from AggFiscalModel import AggFiscalType, DualAggFiscalType, AggregateDemandEconomy
try:
    from AggFiscalModel import NormalizedDualAggFiscalType
    HAS_NORM = True
except (ImportError, NameError):
    HAS_NORM = False
from HARK.distributions import DiscreteDistribution
from tm_methods import compute_baseline_tm_data, run_experiment_tm
from test_asymptotic_equality_revised import mc_burnin, default_warmup

sys.argv = _orig_argv

REPO_ROOT = Path(_THIS_DIR).parent.parent.parent
HISTORY_DIR = REPO_ROOT / "history"


# ---------------------------------------------------------------------------
# Economy builder (single-type, like the Gatekeeper)
# ---------------------------------------------------------------------------

def build_economy(agent_cls, agent_count, seed, periods,
                  income_shuffle=False, normalize_pLvl=False):
    """Build a single-type (highschool) economy."""
    params = return_parameters(Parametrization="Reduced_Run", OutputFor="_Main.py")
    (init_dropout, init_highschool, init_college, init_ADEconomy,
     DiscFacDstns, DiscFacCount, _N, base_dict, *rest) = params
    UBspell_normal = rest[2]
    num_base_MrkvStates = rest[3]

    init_AD = deepcopy(init_ADEconomy)
    init_AD["act_T"] = int(periods)

    agent = agent_cls(**init_highschool)
    agent.cycles = 0
    agent.AgentCount = int(agent_count)
    agent.seed = int(seed)
    agent.DiscFac = DiscFacDstns[1].atoms[0][0]

    economy = AggregateDemandEconomy(**init_AD)
    agent.get_economy_data(economy)

    IncShkDstn_unemp = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([agent.IncUnemp])],
    )
    IncShkDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]),
        [np.array([1.0]), np.array([agent.IncUnempNoBenefits])],
    )
    EmployedIncShkDstn = deepcopy(agent.IncShkDstn[0])
    agent.IncShkDstn = [[agent.IncShkDstn[0]] +
                        [IncShkDstn_unemp] * UBspell_normal +
                        [IncShkDstn_unemp_nobenefits]]
    agent.IncShkDstn_base = agent.IncShkDstn

    num_exp = rest[6]
    IncShkDstn_recession = [agent.IncShkDstn[0] * (2 * (num_exp + 1))]
    agent.IncShkDstn_recession = IncShkDstn_recession
    agent.IncShkDstn_recessionUI = IncShkDstn_recession
    agent.IncShkDstn_recessionTaxCut = deepcopy(IncShkDstn_recession)
    agent.IncShkDstn_recessionCheck = deepcopy(IncShkDstn_recession)

    if isinstance(agent, DualAggFiscalType):
        agent.setup_Q_measure()

    economy.agents = [agent]
    economy.solve()

    if income_shuffle:
        agent.income_shuffle = True
    if normalize_pLvl:
        agent.normalize_pLvl = True

    return economy, base_dict


def run_one_seed(agent_cls, agent_count, seed, periods, mCount,
                 income_shuffle=False, normalize_pLvl=False):
    """Run one MC seed, return AggCons time series (P and Q) and TM reference."""
    economy, base_dict = build_economy(
        agent_cls, agent_count, seed, periods,
        income_shuffle=income_shuffle, normalize_pLvl=normalize_pLvl,
    )

    # TM reference (deterministic — same for all seeds)
    tm_data = run_experiment_tm(
        economy, shock_type="base", mCount=mCount,
        neutral_measure=False, verbose=False,
    )
    tm_q_data = run_experiment_tm(
        economy, shock_type="base", mCount=mCount,
        neutral_measure=True, verbose=False,
    )
    N = float(economy.agents[0].AgentCount)
    tm_AggCons_P = float(np.mean(tm_data["AggCons"])) / N
    tm_AggCons_Q = float(np.mean(tm_q_data["AggCons"])) / N

    # MC burn-in: TM ergodic init + warmup (1/pDeath periods)
    bl_tm = compute_baseline_tm_data(economy, mCount=mCount, neutral_measure=True, verbose=False)
    use_dual = isinstance(economy.agents[0], DualAggFiscalType)
    mc_burnin(economy, warmup=None, tm_data=bl_tm, use_dual=use_dual)

    # If normalize_pLvl, set the target E[pLvl] from TM (deterministic,
    # consistent across seeds) so the normalization eliminates BOTH
    # within-seed drift AND cross-seed initial-condition variation.
    if normalize_pLvl:
        agent = economy.agents[0]
        from tm_methods import compute_pLvl_distribution
        u_erg = bl_tm[0].get("u_ergodic", getattr(agent, "Urate_normal", 0.044))
        grid, probs = compute_pLvl_distribution(agent, n_points=120,
                                                 unemployment_rate=u_erg)
        E_pLvl = float(np.dot(probs, grid))
        agent._pLvl_norm_target = E_pLvl

    # Run experiment
    intended_T = int(economy.act_T)
    economy.save_state()
    economy.switch_to_counterfactual_mode("base")
    economy.act_T = intended_T
    for a in economy.agents:
        a.get_economy_data(economy)
    economy.make_idiosyncratic_shock_histories()
    res = economy.run_experiment(
        shock_type="base", UpdatePrb=1.0, Splurge=economy.agents[0].Splurge,
        EconomyMrkv_init=[0], Full_Output=True,
    )

    AggCons_P = np.array(res["AggCons"]) / N
    AggCons_Q = np.array(res.get("AggCons_Q", res["AggCons"])) / N

    return {
        "AggCons_P": AggCons_P,  # time series
        "AggCons_Q": AggCons_Q,
        "mean_P": float(np.mean(AggCons_P)),
        "mean_Q": float(np.mean(AggCons_Q)),
        "tm_P": tm_AggCons_P,
        "tm_Q": tm_AggCons_Q,
    }


# ---------------------------------------------------------------------------
# Main comparison
# ---------------------------------------------------------------------------

def run_comparison(agents=1000, seeds_list=None, periods=200, mCount=50):
    if seeds_list is None:
        seeds_list = [42, 43, 44]

    configs = [
        ("baseline", DualAggFiscalType, False, False),
        ("shuffle", DualAggFiscalType, True, False),
    ]
    if HAS_NORM:
        configs.append(("shuffle+norm", NormalizedDualAggFiscalType, True, True))

    all_results = {}

    for label, cls, shuf, norm in configs:
        print(f"\n{'='*60}")
        print(f"  Config: {label}")
        print(f"  agent_cls={cls.__name__}, income_shuffle={shuf}, normalize_pLvl={norm}")
        print(f"{'='*60}")

        t0 = time.time()
        seed_results = []
        for s in seeds_list:
            print(f"  seed {s}...", end=" ", flush=True)
            ts = time.time()
            r = run_one_seed(cls, agents, s, periods, mCount,
                             income_shuffle=shuf, normalize_pLvl=norm)
            print(f"done ({time.time()-ts:.1f}s)")
            seed_results.append(r)

        elapsed = time.time() - t0

        # Cross-seed statistics
        means_P = [r["mean_P"] for r in seed_results]
        means_Q = [r["mean_Q"] for r in seed_results]
        n = len(seeds_list)

        se_P = np.std(means_P) / np.sqrt(n)
        se_Q = np.std(means_Q) / np.sqrt(n)
        mean_P = np.mean(means_P)
        mean_Q = np.mean(means_Q)
        tm_P = seed_results[0]["tm_P"]
        tm_Q = seed_results[0]["tm_Q"]

        # Time-series variance (single seed, post-warmup)
        ts_var_P = np.var(seed_results[0]["AggCons_P"])
        ts_var_Q = np.var(seed_results[0]["AggCons_Q"])

        gap_P = abs(tm_P - mean_P)
        gap_Q = abs(tm_Q - mean_Q)
        gap_se_P = gap_P / se_P if se_P > 1e-16 else float("nan")
        gap_se_Q = gap_Q / se_Q if se_Q > 1e-16 else float("nan")

        all_results[label] = {
            "mean_P": mean_P, "mean_Q": mean_Q,
            "se_P": se_P, "se_Q": se_Q,
            "tm_P": tm_P, "tm_Q": tm_Q,
            "gap_se_P": gap_se_P, "gap_se_Q": gap_se_Q,
            "ts_var_P": ts_var_P, "ts_var_Q": ts_var_Q,
            "elapsed": elapsed,
            "n_seeds": n,
        }

        print(f"\n  MC-P: mean={mean_P:.4f}, SE={se_P:.4f}, TM={tm_P:.4f}, |TM-MC|/SE={gap_se_P:.2f}")
        print(f"  MC-Q: mean={mean_Q:.4f}, SE={se_Q:.4f}, TM={tm_Q:.4f}, |TM-MC|/SE={gap_se_Q:.2f}")
        print(f"  SE ratio P/Q: {se_P/se_Q:.2f}x" if se_Q > 1e-16 else "  SE_Q ~ 0")
        print(f"  TS var P: {ts_var_P:.4e}, TS var Q: {ts_var_Q:.4e}")
        print(f"  Time: {elapsed:.1f}s")

    return all_results


def write_report(results, agents, seeds, periods, mCount):
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M")
    fname = f"variance-reduction-comparison_{ts}.md"
    path = HISTORY_DIR / fname

    L = []
    L.append("# Variance reduction comparison: baseline vs shuffle vs shuffle+norm")
    L.append("")
    L.append(f"**Generated (UTC):** {now.isoformat()}")
    L.append(f"**Agents:** {agents}, **Seeds:** {seeds}, **Periods:** {periods}, **mCount:** {mCount}")
    L.append("")

    # --- Cross-seed SE table ---
    L.append("## Cross-seed SE (primary precision metric)")
    L.append("")
    L.append("SE = std(seed means) / sqrt(n_seeds). Lower is better.")
    L.append("")
    L.append("| Config | MC-P mean | SE (P) | MC-Q mean | SE (Q) | SE P/Q | Time |")
    L.append("|--------|----------:|-------:|----------:|-------:|-------:|-----:|")
    for label, r in results.items():
        pq = r["se_P"] / r["se_Q"] if r["se_Q"] > 1e-16 else float("nan")
        L.append(f"| {label} | {r['mean_P']:.4f} | {r['se_P']:.4f} | {r['mean_Q']:.4f} | {r['se_Q']:.4f} | {pq:.1f}x | {r['elapsed']:.0f}s |")
    L.append("")

    # --- SE reduction ratios ---
    if "baseline" in results:
        bl = results["baseline"]
        L.append("### SE reduction vs baseline")
        L.append("")
        L.append("| Config | SE_P reduction | SE_Q reduction |")
        L.append("|--------|:--------------:|:--------------:|")
        for label, r in results.items():
            if label == "baseline":
                continue
            rp = bl["se_P"] / r["se_P"] if r["se_P"] > 1e-16 else float("nan")
            rq = bl["se_Q"] / r["se_Q"] if r["se_Q"] > 1e-16 else float("nan")
            L.append(f"| {label} | {rp:.2f}x | {rq:.2f}x |")
        L.append("")

    # --- TM agreement ---
    L.append("## TM agreement (3 SE criterion)")
    L.append("")
    L.append("| Config | TM-P | |TM-MC|/SE_P | Pass? | TM-Q | |TM-MC|/SE_Q | Pass? |")
    L.append("|--------|-----:|:-----------:|:-----:|-----:|:-----------:|:-----:|")
    for label, r in results.items():
        ok_P = "PASS" if r["gap_se_P"] <= 3.0 else "FAIL"
        ok_Q = "PASS" if r["gap_se_Q"] <= 3.0 else "FAIL"
        L.append(f"| {label} | {r['tm_P']:.4f} | {r['gap_se_P']:.2f} | **{ok_P}** | {r['tm_Q']:.4f} | {r['gap_se_Q']:.2f} | **{ok_Q}** |")
    L.append("")

    # --- Time-series variance ---
    L.append("## Time-series variance of per-period AggCons/N (seed 0)")
    L.append("")
    L.append("Var(AggCons_t / N) across experiment periods. Lower = less noisy aggregates.")
    L.append("")
    L.append("| Config | TS var (P) | TS var (Q) | P/Q ratio |")
    L.append("|--------|----------:|----------:|----------:|")
    for label, r in results.items():
        pq = r["ts_var_P"] / r["ts_var_Q"] if r["ts_var_Q"] > 1e-20 else float("nan")
        L.append(f"| {label} | {r['ts_var_P']:.4e} | {r['ts_var_Q']:.4e} | {pq:.1f}x |")
    L.append("")

    if "baseline" in results:
        bl = results["baseline"]
        L.append("### TS variance reduction vs baseline")
        L.append("")
        L.append("| Config | TS var P reduction | TS var Q reduction |")
        L.append("|--------|:------------------:|:------------------:|")
        for label, r in results.items():
            if label == "baseline":
                continue
            rp = bl["ts_var_P"] / r["ts_var_P"] if r["ts_var_P"] > 1e-20 else float("nan")
            rq = bl["ts_var_Q"] / r["ts_var_Q"] if r["ts_var_Q"] > 1e-20 else float("nan")
            L.append(f"| {label} | {rp:.2f}x | {rq:.2f}x |")
        L.append("")

    # --- Timing ---
    L.append("## Timing")
    L.append("")
    L.append("| Config | Total time | Per seed |")
    L.append("|--------|----------:|--------:|")
    for label, r in results.items():
        per = r["elapsed"] / r["n_seeds"]
        L.append(f"| {label} | {r['elapsed']:.0f}s | {per:.0f}s |")
    L.append("")

    path.write_text("\n".join(L), encoding="utf-8")
    print(f"\nReport written: {path.relative_to(REPO_ROOT)}")
    return path


def main():
    parser = argparse.ArgumentParser(description="Variance reduction comparison")
    parser.add_argument("--agents", type=int, default=1000)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--periods", type=int, default=200)
    parser.add_argument("--mcount", type=int, default=50)
    args = parser.parse_args()

    seeds_list = list(range(42, 42 + args.seeds))
    print(f"Variance reduction comparison: N={args.agents}, seeds={seeds_list}, "
          f"T={args.periods}, mCount={args.mcount}")
    if not HAS_NORM:
        print("WARNING: NormalizedDualAggFiscalType not available; skipping shuffle+norm config")

    t0 = time.time()
    results = run_comparison(args.agents, seeds_list, args.periods, args.mcount)
    total = time.time() - t0

    print(f"\n{'='*60}")
    print(f"  Total elapsed: {total:.0f}s ({total/60:.1f} min)")
    print(f"{'='*60}")

    write_report(results, args.agents, seeds_list, args.periods, args.mcount)


if __name__ == "__main__":
    main()
