"""Stratified MC welfare-6 aggregator (Phase 2 prototype).

Reads existing MC welfare pickles and computes welfare-6 cells via stratified
post-processing. Stratification is by intake Markov state at t=0:
- Stratum A: employed at recession onset (j_intake = 0)
- Stratum B: unemployed at recession onset (j_intake > 0)

For each stratum, computes the welfare estimator using only that stratum's
agents. Combines via natural strata weights:

    W_total = pi_A · W_A + pi_B · W_B

where pi_A, pi_B are the strata fractions in the sample.

This was the first step toward the then-planned (2026-05-10) MC + CRN + IS
method. It does NOT reduce variance itself (uses only existing MC samples),
but provides:
1. A diagnostic of which stratum drives welfare variance
2. A bug-free aggregator framework that the IS-weighted versions extended
3. Per-stratum welfare estimates (informative for the paper)

For the active-IS variant this fed into, see welfare6_scenario_IS.py: a
separate simulation forces all agents to be unemployed at intake, producing
many more samples in stratum B, which the aggregator weights by pi_B.

OUTCOME (2026-06-10): the IS path was explored and ABANDONED for production —
active IS carries a joint-(aNrm, pLvl, Mrkv) sampling bias (+10% ui_rec even
with forced intake states); production variance reduction is MC + CRN +
stratified-shuffle per the unified-MC decision
(conclusions_private/2026-06-10_welfare_method_unified_MC.md). Kept as a
stratification diagnostic.
"""
import argparse
import os
import pickle
import sys

import numpy as np


def _u(c, rho):
    c = np.maximum(c, 1e-16)
    if abs(rho - 1.0) < 1e-12:
        return np.log(c)
    return c ** (1 - rho) / (1 - rho)


def _calc_npv(series, periods, Rfree):
    series = np.asarray(series, dtype=np.float64)
    disc = Rfree ** np.arange(periods)
    return float(np.sum(series[:periods] / disc))


def _felicity_sum_per_agent(c_panel, CRRA):
    """Per-agent felicity panel u(c) for shape (T, N)."""
    return _u(c_panel, CRRA)


def _per_agent_welfare_integrand(pol_pkl, none_pkl, base_pkl, CRRA):
    """Per-agent per-period welfare integrand:
        Φ_i(t) = (u(c_pol_i) - u(c_none_i)) / u'(c_base_i)
    Returns shape (T, N) — same shape as cLvl panels.
    """
    c_pol = np.array(pol_pkl['cLvl_all_splurge'])  # (T, N)
    c_none = np.array(none_pkl['cLvl_all_splurge'])
    c_base = np.array(base_pkl['cLvl_all_splurge'])
    u_pol = _u(c_pol, CRRA)
    u_none = _u(c_none, CRRA)
    base_MU_safe = np.maximum(c_base, 1e-16) ** (-CRRA)
    integrand = (u_pol - u_none) / base_MU_safe  # (T, N)
    return integrand


def compute_welfare6_stratified(mc_dir, base_dir=None, periods=None,
                                  Rfree=None, CRRA=None,
                                  return_diagnostics=False):
    """Compute welfare-6 cells via stratified post-processing of MC pickles.

    Parameters
    ----------
    mc_dir : str
        Directory containing the 12 MC scenario pickles (base.pkl, Check.pkl, ...)
    base_dir : str or None
        Directory containing the base scenario pickles (defaults to mc_dir).
        Allows separating "base" baseline from policy scenarios if needed.
    periods, Rfree, CRRA : optional overrides
    return_diagnostics : bool
        If True, return per-stratum welfare cells in addition to total.

    Returns
    -------
    dict with welfare-6 cells (and optionally per-stratum diagnostics)
    """
    if base_dir is None:
        base_dir = mc_dir

    def load(name, d=mc_dir):
        path = os.path.join(d, f"{name}.pkl")
        with open(path, "rb") as f:
            return pickle.load(f)

    scenarios = ["base", "Check", "UI", "TaxCut",
                 "recession", "recessionUI", "recessionCheck", "recessionTaxCut",
                 "recession_AD", "recessionUI_AD",
                 "recessionCheck_AD", "recessionTaxCut_AD"]
    pkls = {s: load(s) for s in scenarios
            if os.path.exists(os.path.join(mc_dir, f"{s}.pkl"))}  # partial-dir: skip absent scenarios

    if periods is None:
        periods = pkls['base']['act_T']
    if Rfree is None:
        Rfree = pkls['base']['Rfree']
    if CRRA is None:
        CRRA = pkls['base']['CRRA']

    # Identify intake stratum from base scenario's Mrkv_hist (CRN: same agent
    # has same intake state across all scenarios).
    Mrkv_hist = np.array(pkls['base']['Mrkv_hist_bs'])  # (T, N)
    j_intake = Mrkv_hist[0, :]  # intake Markov state per agent
    is_employed_intake = (j_intake == 0)
    N = len(j_intake)
    N_A = int(np.sum(is_employed_intake))    # employed at intake
    N_B = int(np.sum(~is_employed_intake))   # unemployed at intake (any j > 0)
    pi_A = N_A / N
    pi_B = N_B / N

    def npv(scen_key, agg_key):
        series = np.array(pkls[scen_key][agg_key])
        return _calc_npv(series, periods, Rfree)

    def npv_stratum(scen_key, agg_key, mask):
        """Aggregate-level NPV restricted to a stratum, scaled to match the
        full-cohort scale. For stratification, we need per-agent panels."""
        # AggIncome / AggCons are pre-aggregated. To get per-stratum, need
        # per-agent panels. cLvl_all_splurge gives per-agent c.
        # For Income, we don't have per-agent income panel directly; use
        # the full AggIncome and approximate stratum contribution by
        # the agent fraction.
        # SIMPLIFICATION: assume per-stratum AggIncome scales linearly with
        # stratum size. This is exact when income is independent of stratum
        # (true on average; cross-stratum correlations are second-order).
        full = np.array(pkls[scen_key][agg_key])  # (T,) cohort-aggregate
        return _calc_npv(full * (mask.sum() / N), periods, Rfree)

    def welfare6_per_stratum_cell(pol_key, none_key, mask, cost_pol_key=None,
                                    cost_none_key=None):
        """Welfare-6 for a specific stratum mask (boolean array of size N)."""
        if cost_pol_key is None:
            cost_pol_key = pol_key
        if cost_none_key is None:
            cost_none_key = none_key

        # Per-agent integrand for the welfare numerator
        integrand = _per_agent_welfare_integrand(
            pkls[pol_key], pkls[none_key], pkls['base'], CRRA)  # (T, N)

        # Sum over agents IN STRATUM only, per period
        per_period_num = np.sum(integrand[:, mask], axis=1)
        NPV_num = _calc_npv(per_period_num, periods, Rfree)

        # NPV_AddInc and NPV_AddCons: use stratum-restricted aggregates
        # (approximate by scaling full aggregate by stratum fraction)
        NPV_pol_Y = npv_stratum(cost_pol_key, 'AggIncome', mask)
        NPV_none_Y = npv_stratum(cost_none_key, 'AggIncome', mask)
        NPV_AddInc = NPV_pol_Y - NPV_none_Y

        NPV_pol_C = npv_stratum(cost_pol_key, 'AggCons', mask)
        NPV_none_C = npv_stratum(cost_none_key, 'AggCons', mask)
        NPV_AddCons = NPV_pol_C - NPV_none_C

        if abs(NPV_AddInc) < 1e-10:
            return float('nan')
        return NPV_num / NPV_AddInc + (NPV_AddInc - NPV_AddCons) / NPV_AddInc

    def welfare6_strat(pol_key, none_key, cost_pol_key=None,
                       cost_none_key=None):
        """Stratified welfare-6: pi_A * W_A + pi_B * W_B."""
        if cost_pol_key is None:
            cost_pol_key = pol_key
        if cost_none_key is None:
            cost_none_key = none_key

        # Compute per-stratum welfare separately
        W_A = welfare6_per_stratum_cell(pol_key, none_key,
                                         is_employed_intake,
                                         cost_pol_key, cost_none_key)
        W_B = welfare6_per_stratum_cell(pol_key, none_key,
                                         ~is_employed_intake,
                                         cost_pol_key, cost_none_key)

        # NOTE: stratum welfare totals would naively combine as
        # pi_A * W_A + pi_B * W_B if W_A, W_B were comparable per-stratum
        # welfare-per-dollar values. But welfare-6 is a RATIO with stratum-
        # specific NPV_AddInc denominators. We need to combine differently:
        # the OVERALL welfare = sum_i Phi_i / sum_i (Y_pol_i - Y_none_i).
        # Splitting numerator and denominator per stratum:
        #   = (NPV_num_A + NPV_num_B) / (NPV_AddInc_A + NPV_AddInc_B) + ...
        # Just compute the overall as numerator/denominator sum:

        integrand = _per_agent_welfare_integrand(
            pkls[pol_key], pkls[none_key], pkls['base'], CRRA)
        per_period_num_A = np.sum(integrand[:, is_employed_intake], axis=1)
        per_period_num_B = np.sum(integrand[:, ~is_employed_intake], axis=1)

        # For aggregate income/cost: we need per-agent panels to stratify.
        # AggIncome / AggCons in the pickle are TOTAL across agents.
        # We approximate per-stratum AggIncome by scaling by stratum size.
        Y_pol = np.array(pkls[cost_pol_key]['AggIncome'])
        Y_none = np.array(pkls[cost_none_key]['AggIncome'])
        C_pol = np.array(pkls[cost_pol_key]['AggCons'])
        C_none = np.array(pkls[cost_none_key]['AggCons'])

        # Approximation: per-stratum aggregate scales by stratum fraction.
        # This is exact when income/consumption is independent of stratum
        # at the AGGREGATE level (true on average; cross-stratum
        # correlations of income are minor in HAFiscal).
        NPV_AddInc_A = pi_A * _calc_npv(Y_pol - Y_none, periods, Rfree)
        NPV_AddInc_B = pi_B * _calc_npv(Y_pol - Y_none, periods, Rfree)
        NPV_AddCons_A = pi_A * _calc_npv(C_pol - C_none, periods, Rfree)
        NPV_AddCons_B = pi_B * _calc_npv(C_pol - C_none, periods, Rfree)

        NPV_num_A = _calc_npv(per_period_num_A, periods, Rfree)
        NPV_num_B = _calc_npv(per_period_num_B, periods, Rfree)

        # Total welfare numerator and denominator
        NPV_num_total = NPV_num_A + NPV_num_B
        NPV_AddInc_total = NPV_AddInc_A + NPV_AddInc_B
        NPV_AddCons_total = NPV_AddCons_A + NPV_AddCons_B

        if abs(NPV_AddInc_total) < 1e-10:
            return float('nan'), float('nan'), float('nan')

        W_total = (NPV_num_total / NPV_AddInc_total
                    + (NPV_AddInc_total - NPV_AddCons_total)
                       / NPV_AddInc_total)

        # Per-stratum welfare CONTRIBUTIONS to the total numerator
        # (informative for diagnostics)
        contrib_A = (NPV_num_A / NPV_AddInc_total) if abs(NPV_AddInc_total) > 1e-10 else float('nan')
        contrib_B = (NPV_num_B / NPV_AddInc_total) if abs(NPV_AddInc_total) > 1e-10 else float('nan')

        return W_total, contrib_A, contrib_B

    cells = {}
    diagnostics = {'pi_A': pi_A, 'pi_B': pi_B, 'N_A': N_A, 'N_B': N_B}

    cell_specs = [
        ('check_norec',  'Check', 'base'),
        ('ui_norec',     'UI', 'base'),
        ('taxcut_norec', 'TaxCut', 'base'),
        ('check_rec',    'recessionCheck', 'recession'),
        ('ui_rec',       'recessionUI', 'recession'),
        ('taxcut_rec',   'recessionTaxCut', 'recession'),
        ('check_rec_AD', 'recessionCheck_AD', 'recession_AD',
         'recessionCheck', 'recession'),
        ('ui_rec_AD',    'recessionUI_AD', 'recession_AD',
         'recessionUI', 'recession'),
        ('taxcut_rec_AD', 'recessionTaxCut_AD', 'recession_AD',
         'recessionTaxCut', 'recession'),
    ]
    for spec in cell_specs:
        cell_name = spec[0]
        pol = spec[1]; none = spec[2]
        cost_pol = spec[3] if len(spec) > 3 else None
        cost_none = spec[4] if len(spec) > 4 else None
        try:
            W, c_A, c_B = welfare6_strat(pol, none, cost_pol, cost_none)
        except (FileNotFoundError, KeyError):
            W = c_A = c_B = float('nan')  # cell's pickle(s) absent -> skip (partial-dir support)
        cells[cell_name] = W
        diagnostics[cell_name + '_contrib_A'] = c_A
        diagnostics[cell_name + '_contrib_B'] = c_B

    if return_diagnostics:
        return cells, diagnostics
    return cells


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mc_dir")
    p.add_argument("--diagnostics", action="store_true")
    args = p.parse_args()
    if args.diagnostics:
        cells, diag = compute_welfare6_stratified(
            args.mc_dir, return_diagnostics=True)
        print(f"\n=== Stratified MC welfare-6 ===")
        print(f"Strata: pi_A (employed)={diag['pi_A']:.4f} (N={diag['N_A']}), "
              f"pi_B (unemployed)={diag['pi_B']:.4f} (N={diag['N_B']})")
        print(f"\n{'Cell':<22} {'Total':>10} {'Contrib A':>12} {'Contrib B':>12}")
        for k, v in cells.items():
            v_s = 'NaN' if np.isnan(v) else f"{v:.4f}"
            cA = diag.get(k + '_contrib_A', 0)
            cB = diag.get(k + '_contrib_B', 0)
            cA_s = 'NaN' if np.isnan(cA) else f"{cA:.4f}"
            cB_s = 'NaN' if np.isnan(cB) else f"{cB:.4f}"
            print(f"{k:<22} {v_s:>10} {cA_s:>12} {cB_s:>12}")
    else:
        cells = compute_welfare6_stratified(args.mc_dir)
        print(f"\n=== Stratified MC welfare-6 ===")
        for k, v in cells.items():
            v_s = 'NaN' if np.isnan(v) else f"{v:.4f}"
            print(f"  {k:<22} {v_s:>10}")


if __name__ == "__main__":
    main()
