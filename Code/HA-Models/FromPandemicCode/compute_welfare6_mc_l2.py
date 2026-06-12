"""Phase 1: MC-L2 estimator for welfare6.

Computes the L2-decomposition approximation of welfare6's utility part
W^U using the bootstrap-source panels (``*_bs`` keys) persisted by the
regenerated welfare6_scenario_results_Baseline/*.pkl files.

L2 formula (companion doc §4.3, §12.2, with policy-state bucketing):
  W^{U,L2} = (N / NPV_cost) * Σ_t R^{-t} * E[p_t] * Σ_j f_j(t) * Φ_j(t)
where
  Φ_j(t) = E[(X^pol)^{1-ρ} - (X^none)^{1-ρ} | j^pol=j] / (1-ρ)
           * E[(X^base)^ρ | j^pol=j]
  X^scen  = cLvl_all_splurge_bs^scen / pLvl_all_bs^scen
  j       = j^pol_{it}  (policy scenario's Markov state; companion doc
                         §12.2 bullet 3 recommends this as the bucketing
                         index because it isolates the "affected" agents
                         under rare-state policies like UI extension)
  f_j(t)  = fraction of agents with j^pol_{it} = j
  E[…|j]  = sample mean over agents with j^pol_{it} = j at time t

The L2 assumption j^pol = j^none = j^base (CRN state-matching) is exact
for small t and mild macro perturbations; §4.3 & §6 of the companion doc
analyse when it breaks down.

The full-MC W^U (for sanity-matching against diag_welfare6_se.py) uses
the prob-weighted cLvl_all_splurge panel, not the _bs panel.

Usage:
    cd Code/HA-Models/FromPandemicCode
    python compute_welfare6_mc_l2.py
"""
import pickle
from pathlib import Path

import numpy as np


DIR = Path("welfare6_scenario_results_Baseline")
CRRA = 2.0
R = 1.01
T = 40


def load_scenarios():
    out = {}
    for f in sorted(DIR.glob("*.pkl")):
        with open(f, "rb") as fp:
            out[f.stem] = pickle.load(fp)
    return out


def compute_full_mc_WU(pol, none, base, pol_cost, none_cost, discount):
    """Paper-consistent full-MC W^U (Welfare.py:277,284 convention).

    Numerator uses felicity differences from `pol` vs `none` (the cell's
    actual scenarios, including AD if applicable). Denominator uses the
    AD=0 `NPV_AddInc` — passed via `pol_cost, none_cost`, which should
    be the non-AD equivalents of pol/none for recession cells.
    """
    c_pol = np.asarray(pol["cLvl_all_splurge"])
    c_none = np.asarray(none["cLvl_all_splurge"])
    c_base = np.asarray(base["cLvl_all_splurge"])
    agg_pol = np.asarray(pol_cost["AggIncome"])       # FIXED to AD=0 pair
    agg_none = np.asarray(none_cost["AggIncome"])

    N = min(c_pol.shape[1], c_none.shape[1], c_base.shape[1])
    c_pol, c_none, c_base = c_pol[:, :N], c_none[:, :N], c_base[:, :N]

    du = (c_pol ** (1 - CRRA) - c_none ** (1 - CRRA)) / (1 - CRRA)
    mu = c_base ** (-CRRA)
    A_i = ((du / mu) * discount[:, None]).sum(axis=0)
    NPV_cost = float(((agg_pol - agg_none) * discount).sum())
    if NPV_cost == 0:
        return float("nan"), float("nan"), 0
    return float(A_i.sum() / NPV_cost), NPV_cost, N


def compute_mc_l2_WU(pol, none, base, pol_cost, none_cost, discount, return_components=False):
    """MC-L2 estimator using bootstrap-source panels with j^pol bucketing.
    Uses paper-consistent fixed AD=0 `NPV_AddInc` denominator (from
    `pol_cost, none_cost`)."""
    c_pol  = np.asarray(pol["cLvl_all_splurge_bs"])
    c_none = np.asarray(none["cLvl_all_splurge_bs"])
    c_base = np.asarray(base["cLvl_all_splurge_bs"])
    p_pol  = np.asarray(pol["pLvl_all_bs"])
    p_none = np.asarray(none["pLvl_all_bs"])
    p_base = np.asarray(base["pLvl_all_bs"])
    j_pol  = np.asarray(pol["Mrkv_hist_bs"])

    agg_pol = np.asarray(pol_cost["AggIncome"])       # FIXED to AD=0 pair
    agg_none = np.asarray(none_cost["AggIncome"])

    N = min(c_pol.shape[1], c_none.shape[1], c_base.shape[1])
    c_pol, c_none, c_base = c_pol[:, :N], c_none[:, :N], c_base[:, :N]
    p_pol, p_none, p_base = p_pol[:, :N], p_none[:, :N], p_base[:, :N]
    j_pol = j_pol[:, :N]

    X_pol  = c_pol / p_pol
    X_none = c_none / p_none
    X_base = c_base / p_base

    rho = CRRA
    E_pt = p_base.mean(axis=1)            # (T,)
    states = np.unique(j_pol)

    # L2_t = Σ_j f_j(t) · [(E[(X^pol)^{1-ρ}|j^pol=j] - E[(X^none)^{1-ρ}|j^pol=j]) / (1-ρ)]
    #        · E[(X^base)^ρ|j^pol=j]
    # (L2 assumption: agents with j^pol=j are also approximately in j^base=j under CRN.)
    L2_t = np.zeros(T)
    for t in range(T):
        for j in states:
            mask = j_pol[t] == j
            if not np.any(mask):
                continue
            f_j = float(mask.mean())
            b_pol  = float((X_pol[t, mask]  ** (1 - rho)).mean())
            b_none = float((X_none[t, mask] ** (1 - rho)).mean())
            c_j    = float((X_base[t, mask] ** rho).mean())
            L2_t[t] += f_j * (b_pol - b_none) / (1 - rho) * c_j

    NPV_cost = float(((agg_pol - agg_none) * discount).sum())
    if NPV_cost == 0:
        return float("nan"), float("nan"), 0
    W_L2 = N * float((discount * E_pt * L2_t).sum()) / NPV_cost
    if return_components:
        return W_L2, NPV_cost, N, {"L2_t": L2_t, "E_pt": E_pt, "states": states}
    return W_L2, NPV_cost, N


# Each row: (label, pol, none, base, pol_cost, none_cost).
# pol/none/base drive the numerator (felicity, MU); pol_cost/none_cost
# supply the fixed AD=0 NPV_AddInc denominator per Welfare.py:277,284.
# For AD=1 cells, pol_cost/none_cost are the non-AD versions of the
# same policy; for AD=0 cells they equal pol/none.
CELLS = [
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


def main():
    sc = load_scenarios()
    missing_keys = []
    for name, d in sc.items():
        for k in ("cLvl_all_splurge_bs", "pLvl_all_bs", "Mrkv_hist_bs"):
            if k not in d:
                missing_keys.append((name, k))
    if missing_keys:
        print("Pickles missing required _bs keys — regenerate with the updated "
              "welfare6_scenario.py:")
        for n, k in missing_keys:
            print(f"  {n}: missing {k}")
        return 1

    discount = R ** (-np.arange(T))
    print(f"{'cell':22s} {'W^U_MC':>10s} {'W^U_L2':>10s} {'diff':>10s} {'rel.diff':>9s}")
    print("-" * 67)
    for label, pol_k, none_k, base_k, pol_cost_k, none_cost_k in CELLS:
        if not all(k in sc for k in (pol_k, none_k, base_k, pol_cost_k, none_cost_k)):
            print(f"{label:22s}  [skip — missing pickle]")
            continue
        W_MC, _, _ = compute_full_mc_WU(sc[pol_k], sc[none_k], sc[base_k],
                                        sc[pol_cost_k], sc[none_cost_k], discount)
        W_L2, _, _ = compute_mc_l2_WU(sc[pol_k], sc[none_k], sc[base_k],
                                      sc[pol_cost_k], sc[none_cost_k], discount)
        rel = (W_L2 - W_MC) / abs(W_MC) if W_MC else float("nan")
        print(f"{label:22s} {W_MC:10.4f} {W_L2:10.4f} {W_L2-W_MC:+10.4f} "
              f"{rel*100:+8.2f}%")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
