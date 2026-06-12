"""Compute welfare-6 (representative-agent approximation) from existing TM-a
Step-5 output files (Figures/<Param>/<scenario>_results.csv pickles).

Uses cohort-aggregated AggCons / AggIncome series. The representative-agent
formulation evaluates the welfare-6 integrand at the population mean
consumption per period:

    integrand(t) = (u(C_pol(t)/N) - u(C_none(t)/N)) / u'(C_base(t)/N)
                 ∝ C_base^γ · (1/C_none - 1/C_pol)   (γ=2)

Per-period welfare contribution scales with the population: N·integrand →
expressed in aggregate units, the formula is N-independent for the welfare-6
ratio. Actually for γ=2 we have N · integrand = (1/N) · C_base² · (1/C_none -
1/C_pol). So we need to know N (or equivalently use per-agent c-bar
explicitly).

Implementation: use cbar = C_agg / N_agent_count by extracting the agent
count from the run if available, OR use C_agg directly (treating the
population as a single agent — gives the same welfare-6 ratio if all welfare
quantities scale homogeneously).

For HAFiscal where AggIncome / AggCons / NPV_AddInc all have the SAME N
scaling, the welfare-6 ratio is N-invariant under the rep-agent approx if we
compute consistently: use C_agg in u(C) and u'(C), and the ratio is
    Σ_t β^t · (u(C_pol) - u(C_none))/u'(C_base) / NPV_AddInc + savings
    (treating C as "single agent's" consumption).
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
    return c ** (1.0 - rho) / (1.0 - rho)


def _uprime(c, rho):
    c = np.maximum(c, 1e-16)
    return c ** (-rho)


def _npv_final(series, periods, Rfree):
    series = np.asarray(series, dtype=np.float64)
    disc = Rfree ** np.arange(periods)
    return float(np.sum(series[:periods] / disc))


def load_scenario_pkl(figs_dir, fname):
    """Load a TM-a Step-5 scenario result pickle."""
    path = os.path.join(figs_dir, fname)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return pickle.load(f)


def compute_welfare6_repagent_from_csvs(figs_dir, periods=40, Rfree=1.01,
                                         CRRA=2.0):
    """Compute the 9 welfare-6 cells using rep-agent + level aggregates."""

    # Map welfare cells to scenario file names.
    scenarios = {
        'base': 'base_results.csv',
        'Check': 'Check_results.csv',
        'UI': 'UI_results.csv',
        'TaxCut': 'TaxCut_results.csv',
        'recession': 'recession_results.csv',
        'recession_AD': 'recession_results_AD.csv',
        'recessionCheck': 'recessionCheck_results.csv',
        'recessionCheck_AD': 'recessionCheck_results_AD.csv',
        'recessionUI': 'recessionUI_results.csv',
        'recessionUI_AD': 'recessionUI_results_AD.csv',
        'recessionTaxCut': 'recessionTaxCut_results.csv',
        'recessionTaxCut_AD': 'recessionTaxCut_results_AD.csv',
    }
    data = {k: load_scenario_pkl(figs_dir, fn) for k, fn in scenarios.items()}

    # Discover act_T and Rfree from base if available
    if data.get('base') is not None:
        if 'AggIncome' in data['base']:
            periods = len(np.asarray(data['base']['AggIncome']))

    def w6_cell(pol_key, none_key, cost_pol_key=None, cost_none_key=None):
        if cost_pol_key is None:
            cost_pol_key = pol_key
        if cost_none_key is None:
            cost_none_key = none_key
        if any(data.get(k) is None for k in (pol_key, none_key, cost_pol_key,
                                              cost_none_key, 'base')):
            return float('nan')
        C_pol = np.asarray(data[pol_key]['AggCons'])
        C_none = np.asarray(data[none_key]['AggCons'])
        C_base = np.asarray(data['base']['AggCons'])
        Y_pol_cost = np.asarray(data[cost_pol_key]['AggIncome'])
        Y_none_cost = np.asarray(data[cost_none_key]['AggIncome'])
        C_pol_cost = np.asarray(data[cost_pol_key]['AggCons'])
        C_none_cost = np.asarray(data[cost_none_key]['AggCons'])

        # Per-period welfare numerator (rep-agent at aggregate level).
        # Per-cohort summed: N · ((u(C_pol/N) - u(C_none/N))/u'(C_base/N))
        # For γ=2: N · (1/(C_none/N) - 1/(C_pol/N)) · (C_base/N)²
        #        = N · (N/C_none - N/C_pol) · C_base²/N²
        #        = (N²/N²) · C_base² · (1/C_none - 1/C_pol)
        #        = C_base² · (1/C_none - 1/C_pol)
        # So the formula in aggregate-level terms is:
        rho = CRRA
        if abs(rho - 1.0) < 1e-12:
            # Log utility special case: per-cohort: N·log(C_pol/N) - N·log(C_none/N)
            #                                    = N·log(C_pol/C_none)  (N cancels)
            # Hmm, this differs in form. For now γ=2 is the production case.
            per_period = (np.log(C_pol) - np.log(C_none)) * C_base
        else:
            # General CRRA: per-period welfare contribution at aggregate scale
            # = C_base^γ · (C_pol^(1-γ) - C_none^(1-γ)) / (1-γ)
            # Wait — let me redo:
            # u(c̄) = c̄^(1-γ)/(1-γ) where c̄ = C_agg/N
            # Per-cohort contribution: N · (u(c̄_pol) - u(c̄_none))/u'(c̄_base)
            # = N · ((C_pol/N)^(1-γ) - (C_none/N)^(1-γ))/(1-γ) · (C_base/N)^γ
            # = N · N^(γ-1) · (C_pol^(1-γ) - C_none^(1-γ))/(1-γ) · N^(-γ) · C_base^γ
            # = N^(γ-1+1-γ) · (C_pol^(1-γ) - C_none^(1-γ))/(1-γ) · C_base^γ
            # = N^0 · ... = (C_pol^(1-γ) - C_none^(1-γ))/(1-γ) · C_base^γ
            # GREAT — N-independent.
            per_period = ((C_pol ** (1 - rho) - C_none ** (1 - rho))
                          / (1 - rho)) * (C_base ** rho)

        NPV_num = _npv_final(per_period, periods, Rfree)
        NPV_AddInc = _npv_final(Y_pol_cost - Y_none_cost, periods, Rfree)
        NPV_AddCons = _npv_final(C_pol_cost - C_none_cost, periods, Rfree)

        if abs(NPV_AddInc) < 1e-10:
            return float('nan')

        return NPV_num / NPV_AddInc + (NPV_AddInc - NPV_AddCons) / NPV_AddInc

    return {
        'check_norec': w6_cell('Check', 'base'),
        'ui_norec': w6_cell('UI', 'base'),
        'taxcut_norec': w6_cell('TaxCut', 'base'),
        'check_rec': w6_cell('recessionCheck', 'recession'),
        'ui_rec': w6_cell('recessionUI', 'recession'),
        'taxcut_rec': w6_cell('recessionTaxCut', 'recession'),
        'check_rec_AD': w6_cell('recessionCheck_AD', 'recession_AD',
                                'recessionCheck', 'recession'),
        'ui_rec_AD': w6_cell('recessionUI_AD', 'recession_AD',
                              'recessionUI', 'recession'),
        'taxcut_rec_AD': w6_cell('recessionTaxCut_AD', 'recession_AD',
                                  'recessionTaxCut', 'recession'),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("figs_dir", help="Path to Figures/<Param>/ directory with TM-a Step-5 CSVs")
    p.add_argument("--periods", type=int, default=40)
    p.add_argument("--Rfree", type=float, default=1.01)
    p.add_argument("--CRRA", type=float, default=2.0)
    args = p.parse_args()

    cells = compute_welfare6_repagent_from_csvs(
        args.figs_dir, periods=args.periods, Rfree=args.Rfree, CRRA=args.CRRA)

    print(f"\n=== Welfare-6 TM-a (representative-agent) from {args.figs_dir} ===\n")
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
