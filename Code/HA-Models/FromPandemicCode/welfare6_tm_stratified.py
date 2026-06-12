"""TM-a stratified rep-agent welfare-6 (Path B).

Implements stratified Monte Carlo / importance sampling at the analytical
limit: per-Markov-state aggregation captures the concentration of UI welfare
gain on the small affected sub-population (which vanilla rep-agent dilutes).

Formula (per-cohort, per-period):
    W_strat(t) = Σ_j π_j(t) · (u(C̄_pol_j_lvl(t)) - u(C̄_none_j_lvl(t)))
                              / u'(C̄_base_j_emb_lvl(t))

where:
    π_j(t) = analytical fraction of population in destination Markov state j
    C̄_X_j(t) = Σ_a π_X(j, a, t) · c_X(j, a, ξ, ψ) / π_X_j(t)
    j_emb = j mod J_base = embedded base micro-state for evaluating u'(c_base)

Per-cohort welfare contribution (γ=2 simplification):
    N_ℓ · W_strat_ℓ(t) = Σ_j (π_j_pol · N_ℓ) · (1/C̄_none_lvl_j - 1/C̄_pol_lvl_j) · C̄_base_lvl_j_emb²

NPV-aggregate:
    NPV_num = Σ_t β^t · Σ_ℓ contribution_ℓ(t)

Final:
    W = NPV_num / NPV_AddInc + (NPV_AddInc - NPV_AddCons) / NPV_AddInc
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


def _npv(series, periods, Rfree):
    series = np.asarray(series, dtype=np.float64)
    disc = Rfree ** np.arange(periods)
    return float(np.sum(series[:periods] / disc))


def compute_stratified_welfare_per_period(
    pol_per_cohort_per_dur, none_per_cohort_per_dur, base_per_cohort_per_dur,
    pol_agent_state, none_agent_state, base_agent_state,
    rec_probs, act_T, CRRA):
    """Compute per-period welfare numerator series via stratified rep-agent.

    Inputs:
        pol/none/base_per_cohort_per_dur: per-cohort × per-duration list of
            results dicts (each with C_splurge_per_jp_series, etc.)
        pol/none/base_agent_state: cohort agent state (J_micro, AgentCount, etc.)

    Returns: per-period welfare numerator (cohort-aggregated, scalar series).
    """
    n_cohorts = len(pol_per_cohort_per_dur)
    welfare_num_series = np.zeros(act_T)
    rho = CRRA

    for ell in range(n_cohorts):
        N = pol_agent_state[ell]['AgentCount']
        rescale = pol_agent_state[ell]['pop_rescale_factor']
        E_init = pol_agent_state[ell]['E_pLvl_init']
        J_pol = pol_agent_state[ell]['num_base_MrkvStates']
        J_base = base_agent_state[ell]['num_base_MrkvStates']

        # Per-cohort: average across pol durations weighted by rec_probs.
        # (none and base may have different durations setup; align by index.)
        for d_idx in range(len(pol_per_cohort_per_dur[ell])):
            pol_d = pol_per_cohort_per_dur[ell][d_idx]
            d_prob = pol_d['rec_prob']

            # Find matching duration entry in 'none'.
            none_d = None
            for nd in none_per_cohort_per_dur[ell]:
                if nd['duration'] == pol_d['duration']:
                    none_d = nd
                    break
            if none_d is None:
                # If none has different durations (e.g., none is base/no-rec),
                # use the only entry (none has no duration averaging).
                none_d = none_per_cohort_per_dur[ell][0]

            # Base: always single-entry (no recession durations).
            base_d = base_per_cohort_per_dur[ell][0]

            # Per-period aggregation.
            for t in range(act_T):
                # Pol per-state aggregates at time t.
                C_pol_per_jp = pol_d['C_splurge_per_jp_series'][t, :]
                state_fracs_pol = pol_d['state_fracs_dest_series'][t, :]
                pLvl_factor_pol = pol_d['pLvl_factor_series'][t]

                # None per-state aggregates at time t.
                C_none_per_jp = none_d['C_splurge_per_jp_series'][t, :]
                state_fracs_none = none_d['state_fracs_dest_series'][t, :]
                pLvl_factor_none = none_d['pLvl_factor_series'][t]

                # Base per-state aggregates (in base's J_base space; embed below).
                C_base_per_jp_base = base_d['C_splurge_per_jp_series'][t, :J_base]
                state_fracs_base = base_d['state_fracs_dest_series'][t, :J_base]
                pLvl_factor_base = base_d['pLvl_factor_series'][t]

                # Mean consumption per state under each economy.
                C_bar_pol_jp = np.where(state_fracs_pol > 1e-15,
                                          C_pol_per_jp / np.maximum(state_fracs_pol, 1e-30),
                                          1e-16)
                C_bar_none_jp = np.where(state_fracs_none > 1e-15,
                                          C_none_per_jp / np.maximum(state_fracs_none, 1e-30),
                                          1e-16)
                C_bar_base_jp_base = np.where(
                    state_fracs_base > 1e-15,
                    C_base_per_jp_base / np.maximum(state_fracs_base, 1e-30),
                    1e-16)

                # Apply lifecycle scaling to LEVEL units.
                C_bar_pol_lvl_jp = C_bar_pol_jp * (E_init * pLvl_factor_pol)
                C_bar_none_lvl_jp = C_bar_none_jp * (E_init * pLvl_factor_none)
                C_bar_base_lvl_jp_base = C_bar_base_jp_base * (E_init * pLvl_factor_base)

                # Compute MU_inv = 1/u'(c_base) per base state, then index by
                # embedding from pol's / none's jp via jp % J_base.
                if abs(rho - 1.0) < 1e-12:
                    u_pol_jp = np.log(np.maximum(C_bar_pol_lvl_jp, 1e-16))
                    u_none_jp = np.log(np.maximum(C_bar_none_lvl_jp, 1e-16))
                else:
                    u_pol_jp = (np.maximum(C_bar_pol_lvl_jp, 1e-16) ** (1.0 - rho)
                                 / (1.0 - rho))
                    u_none_jp = (np.maximum(C_bar_none_lvl_jp, 1e-16) ** (1.0 - rho)
                                  / (1.0 - rho))
                mu_inv_base_jp_base = (np.maximum(C_bar_base_lvl_jp_base, 1e-16)
                                        ** rho)
                # Embed pol's jp / none's jp to base via jp % J_base.
                mu_inv_for_pol_jp = np.array(
                    [mu_inv_base_jp_base[jp % J_base] for jp in range(J_pol)])
                mu_inv_for_none_jp = mu_inv_for_pol_jp  # same J space for pol/none

                # CORRECT stratified formula:
                # W_num(t) ≈ N · [ Σ_jp π_pol[jp] · u(C̄_pol_jp_lvl) · MU_inv_base_emb[jp]
                #               - Σ_jp π_none[jp] · u(C̄_none_jp_lvl) · MU_inv_base_emb[jp] ]
                # This uses each scenario's OWN state distribution as the
                # weighting measure (population-shift effect captured by
                # the difference in π_pol vs π_none).
                A_pol = float(np.sum(state_fracs_pol * u_pol_jp
                                      * mu_inv_for_pol_jp))
                A_none = float(np.sum(state_fracs_none * u_none_jp
                                       * mu_inv_for_none_jp))
                t_contrib = (A_pol - A_none) * N * rescale

                # Debug print at t=0 and t=5 for cohort 0
                if ell == 0 and (t == 0 or t == 5):
                    print(f"    [debug t={t}] cohort={ell} A_pol={A_pol:.4f} "
                          f"A_none={A_none:.4f} A_pol-A_none={(A_pol-A_none):.4f} "
                          f"t_contrib={t_contrib:.2f}")
                    print(f"      state_fracs_pol[:6]={state_fracs_pol[:6]}")
                    print(f"      state_fracs_none[:6]={state_fracs_none[:6]}")
                    print(f"      C_bar_pol_lvl_jp[:6]={C_bar_pol_lvl_jp[:6]}")
                    print(f"      C_bar_none_lvl_jp[:6]={C_bar_none_lvl_jp[:6]}")
                    print(f"      mu_inv_for_pol_jp[:6]={mu_inv_for_pol_jp[:6]}")
                    print(f"      C_bar_base_lvl_jp_base[:4]={C_bar_base_lvl_jp_base[:4]}")
                    print(f"      pLvl_factors: pol={pLvl_factor_pol:.4f} none={pLvl_factor_none:.4f} base={pLvl_factor_base:.4f}")

                welfare_num_series[t] += d_prob * t_contrib

    return welfare_num_series


def compute_welfare6_cells_stratified(scenarios_data):
    """Compute the 9 welfare-6 cells via stratified rep-agent."""
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

        wn = compute_stratified_welfare_per_period(
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
    """For testing: takes welfare6_tm.py FULL pickle path (not summary)."""
    p = argparse.ArgumentParser()
    p.add_argument("pickle_path", help="welfare6_tm full pickle (in-memory dump)")
    args = p.parse_args()
    with open(args.pickle_path, "rb") as f:
        data = pickle.load(f)
    cells = compute_welfare6_cells_stratified(data['results'])
    print(f"\n=== Stratified rep-agent welfare-6 ({data['parametrization']}) ===\n")
    print(f"{'Cell':<22} {'Welfare-6':>12}")
    print("-" * 35)
    for k, v in cells.items():
        if np.isnan(v):
            print(f"{k:<22} {'NaN':>12}")
        else:
            print(f"{k:<22} {v:>12.4f}")


if __name__ == "__main__":
    main()
