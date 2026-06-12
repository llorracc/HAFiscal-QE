"""Welfare-6 via representative-agent approximation.

For each cohort, compute per-agent average consumption from AggCons series,
then evaluate welfare-6 integrand at the per-cohort representative agent:

    integrand(t) = (u(cbar_pol(t)) - u(cbar_none(t))) / u'(cbar_base(t))

Per-cohort welfare contribution: N_ℓ · integrand_ℓ(t) (which equals AggCons-level
welfare at the representative agent).

This drops the cross-sectional distribution within each cohort but preserves
the per-period level aggregates. By Jensen's, this approximates the true
welfare integrand.
"""
import argparse
import os
import pickle
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def compute_welfare6_repagent(scen_data):
    """Compute welfare-6 cells using representative-agent approximation.

    Reads from the welfare6_tm.py pickle (full_capture format).
    """
    results = scen_data['results_summary'] if 'results_summary' in scen_data \
        else scen_data['results']
    summary = scen_data['ctx_summary']
    Rfree = summary['Rfree']
    act_T = summary['act_T']
    CRRA = summary['CRRA']

    # Need per-cohort AggCons per scenario. The pickle's results_summary only
    # has cohort-aggregated AggCons. So this script can only run on the FULL
    # results dict (as returned by run_scenario_tm_full_capture in-memory).
    if 'results_summary' in scen_data:
        # Fallback: cohort-aggregated representative agent (single rep agent
        # for the whole population). Coarser, but usable.
        return _compute_repagent_aggregate(scen_data, results, summary)

    # Full results: per-cohort breakdown available
    return _compute_repagent_per_cohort(scen_data, results, summary)


def _u(c, rho):
    c = np.maximum(c, 1e-16)
    if abs(rho - 1.0) < 1e-12:
        return np.log(c)
    return c ** (1.0 - rho) / (1.0 - rho)


def _uprime(c, rho):
    c = np.maximum(c, 1e-16)
    return c ** (-rho)


def _npv(series, periods, Rfree):
    series = np.asarray(series, dtype=np.float64)
    disc = Rfree ** np.arange(periods)
    return float(np.sum(series[:periods] / disc))


def _compute_repagent_aggregate(scen_data, results, summary):
    """Single representative-agent approximation across the full population."""
    Rfree = summary['Rfree']
    act_T = summary['act_T']
    CRRA = summary['CRRA']

    # Estimate population-average per-agent consumption from AggCons
    # (sum across all cohorts, divide by total agent count).
    # Total agent count not directly in results_summary; assume base scenario
    # provides aggregate; we'll use the ratio C/Y as a proxy that doesn't
    # depend on N.
    # Actually for the integrand, we just need per-agent consumption levels.
    # Without N, we can't compute c_norm. But we can compute the welfare-6
    # ratio if we set up the formula in N-cancellation form.

    # Per-period welfare at representative agent (level cbar):
    #   integrand(t) = (u(C_pol(t)/N) - u(C_none(t)/N)) / u'(C_base(t)/N)
    # Per-cohort contribution: N * integrand(t)
    # = N * (u(C_pol(t)/N) - u(C_none(t)/N)) / u'(C_base(t)/N)
    # For γ=2: integrand = (1/c_none - 1/c_pol) * c_base^2
    #          = (N/C_none - N/C_pol) * (C_base/N)^2
    #          = N * (1/C_none - 1/C_pol) * (C_base/N)^2
    #          = (C_base^2 / N) * (1/C_none - 1/C_pol)
    # N * integrand = C_base^2 * (1/C_none - 1/C_pol)
    # So we don't need N (it cancels in the welfare ratio with NPV_AddInc / N).
    # Wait, NPV_AddInc is already N-independent (sum over all agents).
    # Let me re-derive carefully.

    # The welfare formula: w6 = Σ_t β^t * Σ_i integrand_i / NPV_AddInc + savings.
    # Under repagent approx: integrand_i = same for all i in a cohort.
    # Σ_i integrand_i = N * integrand_repagent.
    # Per cohort, N * integrand_repagent = ... formula above (N cancels).

    # For multi-cohort: Σ_ℓ N_ℓ * integrand_repagent_ℓ.
    # Need per-cohort N to weight. Without per-cohort N in results_summary,
    # can only do aggregate (treat full population as 1 cohort).

    cells = {}
    def w6_aggr(pol_key, none_key, cost_pol_key=None, cost_none_key=None):
        if cost_pol_key is None:
            cost_pol_key = pol_key
        if cost_none_key is None:
            cost_none_key = none_key
        if results.get(pol_key) is None or results.get(none_key) is None:
            return float('nan')
        C_pol = np.asarray(results[pol_key]['AggCons'])
        C_none = np.asarray(results[none_key]['AggCons'])
        C_base = np.asarray(results['base']['AggCons'])

        # Per-period welfare contribution (cohort-summed) for repagent:
        #   N · integrand(t) = (1/c_none - 1/c_pol) · c_base² · N
        # In aggregate: C_X / N is c̄_X. Per cohort contribution = N · u(cbar)
        # Compatible for γ=2: simplify to C_base²/N · (1/C_none - 1/C_pol)
        # Without N, we can express per-period welfare contribution per "agent":
        # using per-period c-bar (population-average c).
        #
        # For simplicity, use C_X directly with effective N=1 (i.e., treat the
        # entire population as a single agent). The result has the correct
        # ratio structure for welfare-6.
        #
        # Actually the repagent approximation aggregates integrand differently
        # — let's just use cbar directly:

        # Use TOTAL_N = C_base.sum() / cbar_init estimate (not great).
        # Cleanest: just compute (u(C_pol) - u(C_none))/u'(C_base) using
        # aggregate-level consumption as the "single agent" proxy.
        rho = CRRA
        u_pol = _u(C_pol, rho)
        u_none = _u(C_none, rho)
        mu_inv_base = _uprime(C_base, rho) ** (-1)  # = c_base^γ

        per_period = (u_pol - u_none) * mu_inv_base
        NPV_num = _npv(per_period, act_T, Rfree)

        Y_pol = np.asarray(results[cost_pol_key]['AggIncome'])
        Y_none = np.asarray(results[cost_none_key]['AggIncome'])
        NPV_AddInc = _npv(Y_pol - Y_none, act_T, Rfree)

        C_pol_cost = np.asarray(results[cost_pol_key]['AggCons'])
        C_none_cost = np.asarray(results[cost_none_key]['AggCons'])
        NPV_AddCons = _npv(C_pol_cost - C_none_cost, act_T, Rfree)

        if abs(NPV_AddInc) < 1e-10:
            return float('nan')

        return NPV_num / NPV_AddInc + (NPV_AddInc - NPV_AddCons) / NPV_AddInc

    cells['check_norec'] = w6_aggr('Check', 'base')
    cells['ui_norec'] = w6_aggr('UI', 'base')
    cells['taxcut_norec'] = w6_aggr('TaxCut', 'base')
    cells['check_rec'] = w6_aggr('recessionCheck', 'recession')
    cells['ui_rec'] = w6_aggr('recessionUI', 'recession')
    cells['taxcut_rec'] = w6_aggr('recessionTaxCut', 'recession')
    cells['check_rec_AD'] = w6_aggr('recessionCheck_AD', 'recession_AD',
                                     'recessionCheck', 'recession')
    cells['ui_rec_AD'] = w6_aggr('recessionUI_AD', 'recession_AD',
                                  'recessionUI', 'recession')
    cells['taxcut_rec_AD'] = w6_aggr('recessionTaxCut_AD', 'recession_AD',
                                      'recessionTaxCut', 'recession')
    return cells


def _compute_repagent_per_cohort(scen_data, results, summary):
    """Per-cohort representative-agent (each cohort has its own rep agent)."""
    raise NotImplementedError("per-cohort path not yet wired; use aggregate path")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("pickle_path")
    args = p.parse_args()

    with open(args.pickle_path, "rb") as f:
        data = pickle.load(f)

    cells = compute_welfare6_repagent(data)

    print(f"\n=== Welfare-6 TM-a (representative-agent) results "
          f"({data['parametrization']}) ===\n")
    print(f"{'Cell':<22} {'Welfare-6':>12}")
    print("-" * 35)
    for k, v in cells.items():
        if np.isnan(v):
            print(f"{k:<22} {'NaN':>12}")
        else:
            print(f"{k:<22} {v:>12.4f}")
    print()


if __name__ == "__main__":
    main()
