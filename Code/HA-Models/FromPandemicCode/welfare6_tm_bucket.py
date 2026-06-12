"""TM-a bucket-aware welfare-6 aggregator.

For each (cohort, period), evaluate the welfare integrand BUCKET-BY-BUCKET
(rather than at the cohort-aggregated mean consumption). This captures Check
progressivity correctly:

    W_bucket(t) = Σ_b w_b · (u(c̄_{b,pol,lvl}) - u(c̄_{b,none,lvl})) / u'(c̄_{b,base,emb,lvl})

where c̄_{b,X,lvl}(t) = (C_splurge_nrm_b / N) · (E_pLvl_b · pLvl_factor)
                     = mean LEVEL consumption of agents in bucket b at time t.

For non-Check scenarios (no buckets), this reduces to the rep-agent formula
since the single "bucket" = whole cohort.

Per-cohort welfare contribution (γ=2, N-cancellation):
    N · W_bucket(t) ∝ Σ_b w_b · c̄_b_base² · (1/c̄_b_none - 1/c̄_b_pol)
                       (with appropriate level scaling)
"""
import argparse
import numpy as np
import os
import pickle
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _u(c_lvl, rho):
    c_safe = np.maximum(c_lvl, 1e-16)
    if abs(rho - 1.0) < 1e-12:
        return np.log(c_safe)
    return c_safe ** (1.0 - rho) / (1.0 - rho)


def _mu_inv(c_lvl, rho):
    return np.maximum(c_lvl, 1e-16) ** rho


def _npv(series, periods, Rfree):
    series = np.asarray(series, dtype=np.float64)
    disc = Rfree ** np.arange(periods)
    return float(np.sum(series[:periods] / disc))


def compute_bucket_welfare_per_period(
    pol_per_cohort_per_dur, none_per_cohort_per_dur, base_per_cohort_per_dur,
    pol_agent_state, none_agent_state, base_agent_state,
    rec_probs, act_T, CRRA):
    """Per-period bucket-aware welfare numerator series (cohort-aggregated)."""
    n_cohorts = len(pol_per_cohort_per_dur)
    welfare_num_series = np.zeros(act_T)
    rho = CRRA

    for ell in range(n_cohorts):
        N = pol_agent_state[ell]['AgentCount']
        rescale = pol_agent_state[ell]['pop_rescale_factor']

        for d_idx in range(len(pol_per_cohort_per_dur[ell])):
            pol_d = pol_per_cohort_per_dur[ell][d_idx]
            d_prob = pol_d['rec_prob']

            # Match duration entry in 'none'.
            none_d = None
            for nd in none_per_cohort_per_dur[ell]:
                if nd['duration'] == pol_d['duration']:
                    none_d = nd
                    break
            if none_d is None:
                none_d = none_per_cohort_per_dur[ell][0]

            base_d = base_per_cohort_per_dur[ell][0]

            pol_buckets = pol_d.get('bucket_welfare_series', [None] * act_T)
            none_buckets = none_d.get('bucket_welfare_series', [None] * act_T)
            base_buckets = base_d.get('bucket_welfare_series', [None] * act_T)

            for t in range(act_T):
                pol_t = pol_buckets[t] if t < len(pol_buckets) else None
                none_t = none_buckets[t] if t < len(none_buckets) else None
                base_t = base_buckets[t] if t < len(base_buckets) else None
                if pol_t is None or none_t is None or base_t is None:
                    continue

                # Pol may have multiple buckets (Check periods).
                # None and Base typically have 1 bucket (no Check, no buckets).
                # Compute per-bucket welfare in pol's bucket structure;
                # for none/base, use the (single) bucket as a "constant" reference.

                # If multiple buckets in pol, iterate; else single bucket.
                # NOTE: previously tried using U_nrm_b and MU_inv_nrm_b directly
                # but that's INCONSISTENT — pol uses bucket-internal Jensen
                # (small variance), none/base use cohort-wide Jensen (large
                # variance). Asymmetry inflates Δu spuriously. Reverted to
                # c̄_b approach which Jensen-approximates ALL terms symmetrically.
                # The remaining ~2% gap vs MC is the irreducible cross-policy
                # state-divergence residual — would need joint distribution
                # tracking to close further. See:
                # conclusions_private/2026-05-10_*per_bucket*
                t_contrib = 0.0
                for pol_b in pol_t:
                    w_b = pol_b['weight']
                    E_pLvl_b = pol_b['E_pLvl_b']
                    pLvl_f = pol_b['pLvl_factor']

                    # Pol bucket b: c_lvl = c_norm_b × E_pLvl_b × pLvl_factor
                    c_pol_bar_lvl = (pol_b['C_splurge_nrm_b']
                                      * E_pLvl_b * pLvl_f)

                    # None scenario: use cohort-mean c_norm, scaled by
                    # POL_b's pLvl (same agent's pLvl in none economy).
                    none_b = none_t[0]
                    c_none_bar_lvl = (none_b['C_splurge_nrm_b']
                                       * E_pLvl_b * none_b['pLvl_factor'])

                    # Base: same logic
                    base_b = base_t[0]
                    c_base_bar_lvl = (base_b['C_splurge_nrm_b']
                                       * E_pLvl_b * base_b['pLvl_factor'])

                    # Per-bucket welfare integrand (Jensen-symmetric: u of mean
                    # for both pol and none).
                    u_pol = _u(c_pol_bar_lvl, rho)
                    u_none = _u(c_none_bar_lvl, rho)
                    mu_inv_base = _mu_inv(c_base_bar_lvl, rho)

                    integrand = (u_pol - u_none) * mu_inv_base
                    t_contrib += w_b * integrand * N * rescale

                welfare_num_series[t] += d_prob * t_contrib

    return welfare_num_series


def compute_welfare6_cells_bucket(scenarios_data):
    """Compute the 9 welfare-6 cells using bucket-aware welfare integration."""
    Rfree = scenarios_data['base']['Rfree']
    act_T = scenarios_data['base']['act_T']
    base = scenarios_data['base']
    if base is None:
        raise RuntimeError("base scenario missing")
    CRRA = base['per_cohort_agent_state'][0]['CRRA']

    def _agg_npv(scen_key, key):
        scen = scenarios_data.get(scen_key)
        if scen is None or scen[key] is None:
            return float('nan')
        return _npv(scen[key], act_T, Rfree)

    def _w(pol_key, none_key, cost_pol_key=None, cost_none_key=None):
        if cost_pol_key is None:
            cost_pol_key = pol_key
        if cost_none_key is None:
            cost_none_key = none_key
        pol = scenarios_data.get(pol_key)
        none = scenarios_data.get(none_key)
        if pol is None or none is None:
            return float('nan')

        wn = compute_bucket_welfare_per_period(
            pol['per_cohort_per_dur'], none['per_cohort_per_dur'],
            base['per_cohort_per_dur'],
            pol['per_cohort_agent_state'], none['per_cohort_agent_state'],
            base['per_cohort_agent_state'],
            pol['rec_probs'], act_T, CRRA)
        NPV_num = _npv(wn, act_T, Rfree)
        NPV_AddInc = (_agg_npv(cost_pol_key, 'AggIncome')
                      - _agg_npv(cost_none_key, 'AggIncome'))
        NPV_AddCons = (_agg_npv(cost_pol_key, 'AggCons')
                       - _agg_npv(cost_none_key, 'AggCons'))
        if abs(NPV_AddInc) < 1e-10:
            return float('nan')
        return NPV_num / NPV_AddInc + (NPV_AddInc - NPV_AddCons) / NPV_AddInc

    return {
        'check_norec': _w('Check', 'base'),
        'ui_norec': _w('UI', 'base'),
        'taxcut_norec': _w('TaxCut', 'base'),
        'check_rec': _w('recessionCheck', 'recession'),
        'ui_rec': _w('recessionUI', 'recession'),
        'taxcut_rec': _w('recessionTaxCut', 'recession'),
        'check_rec_AD': _w('recessionCheck_AD', 'recession_AD',
                            'recessionCheck', 'recession'),
        'ui_rec_AD': _w('recessionUI_AD', 'recession_AD',
                         'recessionUI', 'recession'),
        'taxcut_rec_AD': _w('recessionTaxCut_AD', 'recession_AD',
                             'recessionTaxCut', 'recession'),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("pickle_path")
    args = p.parse_args()
    with open(args.pickle_path, "rb") as f:
        data = pickle.load(f)
    cells = compute_welfare6_cells_bucket(data['results'])
    print(f"\n=== Bucket-aware welfare-6 ({data['parametrization']}) ===\n")
    print(f"{'Cell':<22} {'Welfare-6':>12}")
    print("-" * 35)
    for k, v in cells.items():
        v_s = 'NaN' if np.isnan(v) else f"{v:.4f}"
        print(f"{k:<22} {v_s:>12}")


if __name__ == "__main__":
    main()
