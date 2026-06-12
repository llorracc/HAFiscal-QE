"""Diagnostic: measure per-agent CV(A_i) and implied SE of welfare6 from
completed Phase 6-prime MC welfare pickles.

Reads `welfare6_scenario_results_Baseline/*.pkl` and for each welfare cell:
  - computes the per-agent discounted utility contribution A_i
  - computes W^U = sum_i A_i / NPV_cost (which should match the paper's
    welfare6 "utility part" up to the budget residual term)
  - reports CV(A_i) across agents, the implied relative SE at the current
    AgentCount, and the N required to reach <1% relative SE
  - bootstraps SE(W^U) directly by resampling agents with replacement

Usage:
    cd Code/HA-Models/FromPandemicCode
    python diag_welfare6_se.py
"""
import pickle
from pathlib import Path

import numpy as np


DIR = Path("welfare6_scenario_results_Baseline")
R = 1.01  # Rfree
CRRA = 2.0
T = 40


def felicity(c, rho=CRRA):
    if rho == 1:
        return np.log(c)
    return c ** (1 - rho) / (1 - rho)


def mu(c, rho=CRRA):
    return c ** (-rho)


def load_scenarios():
    out = {}
    for f in sorted(DIR.glob("*.pkl")):
        with open(f, "rb") as fp:
            out[f.stem] = pickle.load(fp)
    return out


def compute_cell(pol, none, base, pol_cost, none_cost, discount, label, n_boot=200, rng=None):
    """Paper-consistent welfare6 SE diagnostic (Welfare.py:277,284).

    Numerator uses felicity from (pol, none, base) — AD-specific for
    AD=1 cells. Denominator uses AD=0 NPV_AddInc from (pol_cost,
    none_cost). For AD=0 cells pol_cost==pol, none_cost==none."""
    c_pol = np.asarray(pol["cLvl_all_splurge"])         # (T, N)
    c_none = np.asarray(none["cLvl_all_splurge"])
    c_base = np.asarray(base["cLvl_all_splurge"])
    agg_pol = np.asarray(pol_cost["AggIncome"])         # FIXED to AD=0 pair
    agg_none = np.asarray(none_cost["AggIncome"])
    agg_cons_pol = np.asarray(pol_cost["AggCons"])      # FIXED to AD=0 pair
    agg_cons_none = np.asarray(none_cost["AggCons"])

    # Align N (all scenarios share the same agent population under CRN)
    N = min(c_pol.shape[1], c_none.shape[1], c_base.shape[1])
    c_pol, c_none, c_base = c_pol[:, :N], c_none[:, :N], c_base[:, :N]

    # Per-agent per-period welfare integrand
    du = felicity(c_pol) - felicity(c_none)             # (T, N)
    du_norm = du / mu(c_base)                           # (T, N)

    # Per-agent discounted sum A_i
    A_i = (du_norm * discount[:, None]).sum(axis=0)     # (N,)

    # Aggregate policy cost (additional govt spending NPV)
    NPV_cost = float(((agg_pol - agg_none) * discount).sum())
    NPV_Dc = float(((agg_cons_pol - agg_cons_none) * discount).sum())

    if NPV_cost == 0.0:
        return None

    # W^U (utility part) and budget residual
    W_U = float(A_i.sum() / NPV_cost)
    W_B = float((NPV_cost - NPV_Dc) / NPV_cost)
    W_6 = W_U + W_B

    # CV(A_i) and implied analytic SE
    mean_A = float(A_i.mean())
    std_A = float(A_i.std(ddof=1))
    cv_A = std_A / abs(mean_A) if mean_A != 0 else float("nan")

    # relative SE on W^U from analytic sqrt-N scaling:
    rel_se_WU_analytic = cv_A / np.sqrt(N)
    N_for_1pct_WU = int(np.ceil(cv_A ** 2 * 10000))

    # Bootstrap SE of W_U (resample agents with replacement)
    if rng is None:
        rng = np.random.default_rng(42)
    boot_W_U = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, N, size=N)
        boot_W_U[b] = A_i[idx].sum() / NPV_cost
    boot_SE_WU = float(boot_W_U.std(ddof=1))
    boot_rel_SE_WU = boot_SE_WU / abs(W_U) if W_U != 0 else float("nan")

    # Fraction of agents with non-zero A_i (affected)
    affected = np.abs(A_i) > (std_A * 0.01)  # 1% of typical magnitude threshold
    f_affected = float(affected.mean())

    # CV among affected agents only
    if affected.sum() > 1:
        A_aff = A_i[affected]
        cv_A_aff = float(A_aff.std(ddof=1) / abs(A_aff.mean())) if A_aff.mean() != 0 else float("nan")
    else:
        cv_A_aff = float("nan")

    return {
        "label": label,
        "N": N,
        "W_U": W_U,
        "W_B": W_B,
        "W_6": W_6,
        "NPV_cost": NPV_cost,
        "mean_A": mean_A,
        "std_A": std_A,
        "cv_A": cv_A,
        "f_affected": f_affected,
        "cv_A_affected": cv_A_aff,
        "rel_SE_WU_analytic": rel_se_WU_analytic,
        "boot_rel_SE_WU": boot_rel_SE_WU,
        "N_for_1pct_WU": N_for_1pct_WU,
    }


def main():
    print("Loading scenarios...")
    sc = load_scenarios()
    print("Available:", sorted(sc.keys()))

    discount = R ** (-np.arange(T))

    # Welfare cells following Welfare.py:277/284 convention. The 5th/6th
    # keys are the AD=0 cost-denominator scenarios (matching per policy);
    # for AD=0 cells they equal pol/none.
    cells = [
        ("Check,  Rec=0, AD=0 ", "Check",              "base",          "base", "Check",              "base"),
        ("UI,     Rec=0, AD=0 ", "UI",                 "base",          "base", "UI",                 "base"),
        ("TaxCut, Rec=0, AD=0 ", "TaxCut",             "base",          "base", "TaxCut",             "base"),
        ("Check,  Rec=1, AD=0 ", "recessionCheck",     "recession",     "base", "recessionCheck",     "recession"),
        ("UI,     Rec=1, AD=0 ", "recessionUI",        "recession",     "base", "recessionUI",        "recession"),
        ("TaxCut, Rec=1, AD=0 ", "recessionTaxCut",    "recession",     "base", "recessionTaxCut",    "recession"),
        ("Check,  Rec=1, AD=1 ", "recessionCheck_AD",  "recession_AD",  "base", "recessionCheck",     "recession"),
        ("UI,     Rec=1, AD=1 ", "recessionUI_AD",     "recession_AD",  "base", "recessionUI",        "recession"),
        ("TaxCut, Rec=1, AD=1 ", "recessionTaxCut_AD", "recession_AD",  "base", "recessionTaxCut",    "recession"),
    ]

    rows = []
    rng = np.random.default_rng(42)
    for label, pol_k, none_k, base_k, pol_cost_k, none_cost_k in cells:
        if not all(k in sc for k in (pol_k, none_k, base_k, pol_cost_k, none_cost_k)):
            print(f"  [skip] {label}: missing pickle")
            continue
        r = compute_cell(sc[pol_k], sc[none_k], sc[base_k],
                         sc[pol_cost_k], sc[none_cost_k], discount, label, rng=rng)
        if r is not None:
            rows.append(r)

    # Print summary table
    print()
    print("=" * 118)
    print("WELFARE6 STANDARD-ERROR DIAGNOSTIC")
    print("=" * 118)
    print(f"{'cell':22s} {'W_6':>7s} {'W^U':>7s} {'W^B':>7s} "
          f"{'N':>7s} {'f_aff':>7s} {'CV(A)':>7s} {'CV(A|aff)':>9s} "
          f"{'rel.SE(W^U)':>12s} {'boot.SE':>9s} {'N→<1%':>10s}")
    print("-" * 118)
    for r in rows:
        print(f"{r['label']:22s} "
              f"{r['W_6']:7.3f} {r['W_U']:7.3f} {r['W_B']:7.3f} "
              f"{r['N']:7d} {r['f_affected']:7.3f} "
              f"{r['cv_A']:7.2f} {r['cv_A_affected']:9.2f} "
              f"{r['rel_SE_WU_analytic']*100:11.2f}% {r['boot_rel_SE_WU']*100:8.2f}% "
              f"{r['N_for_1pct_WU']:10,d}")

    print()
    print("Notes:")
    print("  W^U = sum_i A_i / NPV_cost  (utility part of welfare6)")
    print("  W^B = (NPV_cost - NPV_Dc) / NPV_cost  (budget residual)")
    print("  W_6 = W^U + W^B (should match paper's reported W6)")
    print("  CV(A)      = SD(A_i) / |mean(A_i)| across ALL agents")
    print("  CV(A|aff)  = SD conditional on |A_i| > 1%*SD threshold (affected fraction)")
    print("  f_aff      = fraction of agents with non-negligible A_i")
    print("  rel.SE     = CV(A)/sqrt(N)  (analytic, treating NPV_cost as known)")
    print("  boot.SE    = bootstrap SE of W^U (200 resamples of agents with replacement)")
    print("  N→<1%     = N needed so CV(A)/sqrt(N) < 0.01 (on W^U alone)")


if __name__ == "__main__":
    main()
