"""Welfare-6 TM aggregator.

Reads the per-scenario pickle from welfare6_tm.py and combines the per-cohort
per-period welfare moments into welfare-6 cells using the analytical formula
derived in conclusions_private/2026-05-09_welfare6_tm_a_option_b3_math.md:

    welfare_num(t) = Σ_cohort N_ℓ · pop_rescale_ℓ · E_ℓ[p_t]
                     · MU_inv_base_norm_ℓ(t)
                     · (U_pol_norm_ℓ(t) - U_none_norm_ℓ(t))

    W = NPV(welfare_num) / NPV_AddInc
        + (NPV_AddInc - NPV_AddCons) / NPV_AddInc

The lifecycle factor E_ℓ[p_t] = E_init_ℓ · pLvl_factor_ℓ(t) is taken from the
"none" scenario (matches the agent's actual lifecycle in that counterfactual).

Welfare cells:
    (Rec=0, AD=0): check_norec, ui_norec, taxcut_norec
    (Rec=1, AD=0): check_rec, ui_rec, taxcut_rec
    (Rec=1, AD=1): check_rec_AD, ui_rec_AD, taxcut_rec_AD

For AD cells, denominator (NPV_AddInc, NPV_AddCons) uses the non-AD
scenarios' aggregates, matching the welfare6_mc convention.
"""
import argparse
import os
import pickle
import sys

import numpy as np


def _calculate_NPV(series, periods, Rfree):
    """Mirrors tm_methods.calculate_NPV[-1] — the cumulative NPV at the
    final index."""
    series = np.asarray(series, dtype=np.float64)
    disc = Rfree ** np.arange(periods)
    return float(np.sum(series[:periods] / disc))


def _per_period_welfare_num(per_cohort_pol, per_cohort_none,
                            per_cohort_base, lifecycle_source='none'):
    """Compute the per-period welfare numerator series across cohorts.

    welfare_num(t) = Σ_ℓ N_ℓ · pop_rescale_ℓ · E_init_ℓ · pLvl_factor_ℓ(t)
                     · MU_inv_base_norm_ℓ(t) · (U_pol_norm_ℓ(t) - U_none_norm_ℓ(t))

    lifecycle_source: which scenario's pLvl_factor_series to use as the
    cohort's E[p_t] factor. 'none' (default) matches the counterfactual's
    lifecycle path; 'pol' uses the policy economy's path; 'base' uses base.
    """
    n_cohorts = len(per_cohort_base)
    act_T = len(per_cohort_base[0]['MU_inv_nrm_series'])
    welfare_num = np.zeros(act_T)
    for ell in range(n_cohorts):
        c_pol = per_cohort_pol[ell]
        c_none = per_cohort_none[ell]
        c_base = per_cohort_base[ell]
        if lifecycle_source == 'none':
            pLvl_factor = c_none['pLvl_factor_series']
        elif lifecycle_source == 'pol':
            pLvl_factor = c_pol['pLvl_factor_series']
        else:
            pLvl_factor = c_base['pLvl_factor_series']
        E_init = c_base['E_pLvl_init']
        N = c_base['AgentCount']
        rescale = c_base['pop_rescale_factor']
        MU_inv_base = c_base['MU_inv_nrm_series']
        dU = c_pol['U_nrm_series'] - c_none['U_nrm_series']
        contrib = N * rescale * E_init * pLvl_factor * MU_inv_base * dU
        welfare_num += contrib
    return welfare_num


def compute_welfare6_cells(pkl_data):
    """Compute the 9 welfare-6 cells from per-scenario welfare moments."""
    results = pkl_data['results']
    summary = pkl_data['ctx_summary']
    act_T = summary['act_T']
    Rfree = summary['Rfree']

    # Helper: get per-cohort moments for a scenario (or None if missing).
    def get(scen):
        r = results.get(scen)
        if r is None:
            return None
        return r['per_cohort']

    base = get('base')
    if base is None:
        raise RuntimeError("'base' scenario missing from pickle")

    # Helper: NPV of an aggregate-level series.
    def npv(scen, key):
        r = results.get(scen)
        if r is None or r[key] is None:
            return float('nan')
        return _calculate_NPV(r[key], act_T, Rfree)

    cells = {}

    def w6_cell(pol_scen, none_scen, cost_pol_scen=None, cost_none_scen=None):
        if cost_pol_scen is None:
            cost_pol_scen = pol_scen
        if cost_none_scen is None:
            cost_none_scen = none_scen
        pol = get(pol_scen)
        none = get(none_scen)
        if pol is None or none is None:
            return float('nan')

        # Per-period welfare numerator (cohort-aggregated).
        welfare_num_series = _per_period_welfare_num(pol, none, base)
        NPV_num = _calculate_NPV(welfare_num_series, act_T, Rfree)

        NPV_pol_Y = npv(cost_pol_scen, 'AggIncome')
        NPV_none_Y = npv(cost_none_scen, 'AggIncome')
        NPV_AddInc = NPV_pol_Y - NPV_none_Y

        NPV_pol_C = npv(cost_pol_scen, 'AggCons')
        NPV_none_C = npv(cost_none_scen, 'AggCons')
        NPV_AddCons = NPV_pol_C - NPV_none_C

        if abs(NPV_AddInc) < 1e-10:
            return float('nan')

        W = (NPV_num / NPV_AddInc) + (NPV_AddInc - NPV_AddCons) / NPV_AddInc
        return W

    # (Rec=0, AD=0): non-recession policy vs no-policy base
    cells['check_norec'] = w6_cell('Check', 'base')
    cells['ui_norec'] = w6_cell('UI', 'base')
    cells['taxcut_norec'] = w6_cell('TaxCut', 'base')

    # (Rec=1, AD=0): recession policy vs recession-no-policy
    cells['check_rec'] = w6_cell('recessionCheck', 'recession')
    cells['ui_rec'] = w6_cell('recessionUI', 'recession')
    cells['taxcut_rec'] = w6_cell('recessionTaxCut', 'recession')

    # (Rec=1, AD=1): AD versions, denominator uses non-AD cost pair
    cells['check_rec_AD'] = w6_cell(
        'recessionCheck_AD', 'recession_AD',
        cost_pol_scen='recessionCheck', cost_none_scen='recession')
    cells['ui_rec_AD'] = w6_cell(
        'recessionUI_AD', 'recession_AD',
        cost_pol_scen='recessionUI', cost_none_scen='recession')
    cells['taxcut_rec_AD'] = w6_cell(
        'recessionTaxCut_AD', 'recession_AD',
        cost_pol_scen='recessionTaxCut', cost_none_scen='recession')

    return cells


def main():
    p = argparse.ArgumentParser()
    p.add_argument("pickle_path")
    p.add_argument("--out-csv", default=None,
                   help="Optional CSV output path")
    args = p.parse_args()

    with open(args.pickle_path, "rb") as f:
        data = pickle.load(f)

    cells = compute_welfare6_cells(data)

    print(f"\n=== Welfare-6 TM-a results ({data['parametrization']}) ===\n")
    print(f"{'Cell':<22} {'Welfare-6':>12}")
    print("-" * 35)
    for k, v in cells.items():
        if np.isnan(v):
            print(f"{k:<22} {'NaN':>12}")
        else:
            print(f"{k:<22} {v:>12.4f}")
    print()

    if args.out_csv:
        import csv
        with open(args.out_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["cell", "welfare6"])
            for k, v in cells.items():
                w.writerow([k, "" if np.isnan(v) else f"{v:.6f}"])
        print(f"Wrote CSV to {args.out_csv}")


if __name__ == "__main__":
    main()
