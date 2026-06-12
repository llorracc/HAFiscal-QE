"""IS-combined welfare-6 aggregator: combines sim A (natural) and sim B (forced unemp).

Computes welfare-6 cells via the stratified IS estimator:

    \\hat{W} = pi_A · W_simA_stratumA + pi_B · W_simB

where pi_A, pi_B are natural intake fractions.

For variance estimation, can be invoked with multiple seed pairs:
each (sim A seed s, sim B seed s) → one IS estimate. Average across seeds
for the IS estimate; SD/sqrt(N_seeds) for IS SE.

Also supports comparison vs standard MC (sim A alone) for variance reduction.

OUTCOME (2026-06-10): the IS path was explored and ABANDONED for production —
active IS carries a joint-(aNrm, pLvl, Mrkv) sampling bias (+10% ui_rec even
with forced intake states); production variance reduction is MC + CRN +
stratified-shuffle per the unified-MC decision
(conclusions_private/2026-06-10_welfare_method_unified_MC.md). Kept as a
diagnostic.
"""
import argparse
import os
import pickle
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _u(c, rho):
    c = np.maximum(c, 1e-16)
    if abs(rho - 1.0) < 1e-12:
        return np.log(c)
    return c ** (1 - rho) / (1 - rho)


def _calc_npv(series, periods, Rfree):
    series = np.asarray(series, dtype=np.float64)
    disc = Rfree ** np.arange(periods)
    return float(np.sum(series[:periods] / disc))


def _per_agent_integrand(pol_pkl, none_pkl, base_pkl, CRRA):
    """Per-agent welfare integrand panel (T, N)."""
    c_pol = np.array(pol_pkl['cLvl_all_splurge'])
    c_none = np.array(none_pkl['cLvl_all_splurge'])
    c_base = np.array(base_pkl['cLvl_all_splurge'])
    u_pol = _u(c_pol, CRRA)
    u_none = _u(c_none, CRRA)
    base_MU = np.maximum(c_base, 1e-16) ** (-CRRA)
    return (u_pol - u_none) / base_MU


def load_pkls(d):
    """Load all 12 scenario pickles from a directory."""
    scenarios = ["base", "Check", "UI", "TaxCut",
                 "recession", "recessionUI", "recessionCheck", "recessionTaxCut",
                 "recession_AD", "recessionUI_AD",
                 "recessionCheck_AD", "recessionTaxCut_AD"]
    out = {}
    for s in scenarios:
        path = os.path.join(d, f"{s}.pkl")
        if not os.path.isfile(path):
            # try doubled-path artifact
            path = os.path.join(HERE, d, f"{s}.pkl")
        if not os.path.isfile(path):
            print(f"  [warn] missing pickle for {s} in {d}")
            out[s] = None
            continue
        with open(path, "rb") as f:
            out[s] = pickle.load(f)
    return out


def compute_welfare_simA_natural(simA_pkls):
    """Standard MC welfare from sim A (natural intake), as a baseline."""
    base = simA_pkls['base']
    periods = base['act_T']; Rfree = base['Rfree']; CRRA = base['CRRA']

    cells = {}
    cell_specs = [
        ('check_norec', 'Check', 'base'),
        ('ui_norec', 'UI', 'base'),
        ('taxcut_norec', 'TaxCut', 'base'),
        ('check_rec', 'recessionCheck', 'recession'),
        ('ui_rec', 'recessionUI', 'recession'),
        ('taxcut_rec', 'recessionTaxCut', 'recession'),
        ('check_rec_AD', 'recessionCheck_AD', 'recession_AD',
         'recessionCheck', 'recession'),
        ('ui_rec_AD', 'recessionUI_AD', 'recession_AD',
         'recessionUI', 'recession'),
        ('taxcut_rec_AD', 'recessionTaxCut_AD', 'recession_AD',
         'recessionTaxCut', 'recession'),
    ]
    for spec in cell_specs:
        cell_name = spec[0]; pol_key = spec[1]; none_key = spec[2]
        cost_pol = spec[3] if len(spec) > 3 else pol_key
        cost_none = spec[4] if len(spec) > 4 else none_key

        if any(simA_pkls.get(k) is None for k in (pol_key, none_key, cost_pol, cost_none, 'base')):
            cells[cell_name] = float('nan')
            continue

        integrand = _per_agent_integrand(simA_pkls[pol_key],
                                          simA_pkls[none_key],
                                          base, CRRA)
        per_period_num = np.sum(integrand, axis=1)
        NPV_num = _calc_npv(per_period_num, periods, Rfree)

        Y_pol_cost = np.array(simA_pkls[cost_pol]['AggIncome'])
        Y_none_cost = np.array(simA_pkls[cost_none]['AggIncome'])
        NPV_AddInc = _calc_npv(Y_pol_cost - Y_none_cost, periods, Rfree)

        C_pol_cost = np.array(simA_pkls[cost_pol]['AggCons'])
        C_none_cost = np.array(simA_pkls[cost_none]['AggCons'])
        NPV_AddCons = _calc_npv(C_pol_cost - C_none_cost, periods, Rfree)

        if abs(NPV_AddInc) < 1e-10:
            cells[cell_name] = float('nan')
        else:
            cells[cell_name] = (NPV_num / NPV_AddInc
                                 + (NPV_AddInc - NPV_AddCons) / NPV_AddInc)
    return cells


def compute_welfare_IS_combined(simA_pkls, simB_pkls):
    """Stratified IS estimator combining sim A and sim B.

    Welfare = pi_A · W_A_from_simA_stratumA + pi_B · W_B_from_simB

    where pi_A, pi_B are read from sim A's intake distribution.

    For per-cohort welfare aggregation: we identify stratum from sim A's
    Mrkv_hist[0,:] for each agent index. Sim B's agents are all forced to
    stratum B (Mrkv = 1).
    """
    base_A = simA_pkls['base']
    base_B = simB_pkls['base']
    periods = base_A['act_T']; Rfree = base_A['Rfree']; CRRA = base_A['CRRA']

    # Identify stratum membership in sim A
    Mrkv_hist_A = np.array(base_A['Mrkv_hist_bs'])
    j_intake_A = Mrkv_hist_A[0, :]
    is_A_employed = (j_intake_A == 0)
    N_A_total = len(j_intake_A)
    pi_B_natural = float(np.mean(~is_A_employed))
    pi_A_natural = 1.0 - pi_B_natural

    # Verify sim B agents are all in stratum B (j=1)
    Mrkv_hist_B = np.array(base_B['Mrkv_hist_bs'])
    j_intake_B = Mrkv_hist_B[0, :]
    n_B_unemp = int(np.sum(j_intake_B != 0))
    print(f"  Sim A: N={N_A_total}, pi_B_natural={pi_B_natural:.4f} ({np.sum(~is_A_employed)} unemp)")
    print(f"  Sim B: N={len(j_intake_B)}, {n_B_unemp} forced-unemp at intake "
          f"({100*n_B_unemp/len(j_intake_B):.1f}%)")

    cells = {}
    cell_specs = [
        ('check_norec', 'Check', 'base'),
        ('ui_norec', 'UI', 'base'),
        ('taxcut_norec', 'TaxCut', 'base'),
        ('check_rec', 'recessionCheck', 'recession'),
        ('ui_rec', 'recessionUI', 'recession'),
        ('taxcut_rec', 'recessionTaxCut', 'recession'),
        ('check_rec_AD', 'recessionCheck_AD', 'recession_AD',
         'recessionCheck', 'recession'),
        ('ui_rec_AD', 'recessionUI_AD', 'recession_AD',
         'recessionUI', 'recession'),
        ('taxcut_rec_AD', 'recessionTaxCut_AD', 'recession_AD',
         'recessionTaxCut', 'recession'),
    ]
    for spec in cell_specs:
        cell_name = spec[0]; pol_key = spec[1]; none_key = spec[2]
        cost_pol = spec[3] if len(spec) > 3 else pol_key
        cost_none = spec[4] if len(spec) > 4 else none_key

        # Per-agent integrand for sim A and sim B
        integrand_A = _per_agent_integrand(simA_pkls[pol_key],
                                            simA_pkls[none_key],
                                            base_A, CRRA)
        integrand_B = _per_agent_integrand(simB_pkls[pol_key],
                                            simB_pkls[none_key],
                                            base_B, CRRA)

        # Sim A stratum A contribution: per-period sum over employed agents
        per_period_A_stratumA = np.sum(integrand_A[:, is_A_employed], axis=1)
        # Sim B contribution: per-period sum over all agents (all forced to B)
        per_period_B = np.sum(integrand_B, axis=1)

        # Scale to population size: sim A stratum A represents N_A_natural
        # agents in the natural population; sim B represents N_B agents in
        # the natural population.
        # In sim A stratum A: have np.sum(is_A_employed) agents naturally.
        # In sim B: have len(j_intake_B) agents (all forced).
        # For unbiased welfare numerator (per-cohort aggregate over total N):
        #   NPV_num_total = NPV_num_A_stratumA + NPV_num_B
        # where each is scaled to represent its share of total population.
        #
        # Sim A's stratum-A sum already represents pi_A · N_total agents
        # (since sim A samples natural distribution): no rescaling.
        # Sim B's sum represents N_B agents in proposal but pi_B · N_total
        # in natural population: need scale factor pi_B · N_total / N_simB.

        N_simA = simA_pkls['base']['Mrkv_hist_bs'].shape[1]
        N_simB = simB_pkls['base']['Mrkv_hist_bs'].shape[1]
        # Stratum A from sim A: scale = 1 (natural sampling).
        # Stratum B from sim B: scale = (pi_B · N_total) / N_simB
        # But N_total is what we want the estimator to scale to. For the
        # welfare ratio (NPV_num / NPV_AddInc), the N cancels — what matters
        # is the relative weighting between strata.
        #
        # Equivalent formulation: per-AGENT MEAN per stratum, then weight by
        # natural pi_A, pi_B.

        N_A_stratumA_simA = int(np.sum(is_A_employed))  # actual count
        per_period_A_mean = (per_period_A_stratumA / N_A_stratumA_simA)
        per_period_B_mean = (per_period_B / N_simB)

        # Per-agent welfare-num contribution at the population level
        per_period_pop_mean = (pi_A_natural * per_period_A_mean
                                + pi_B_natural * per_period_B_mean)

        # NPV (per-agent average); scale to total welfare numerator by N_total
        # (which cancels in the welfare ratio with NPV_AddInc).
        # Use sim A's N_total as the population size for both numerator and
        # denominator (consistent ratio).
        NPV_num_per_agent = _calc_npv(per_period_pop_mean, periods, Rfree)
        NPV_num_total = NPV_num_per_agent * N_simA

        # NPV_AddInc and NPV_AddCons: use sim A (natural sampling) for the
        # cohort-aggregate income/consumption (these are well-converged at
        # standard N for non-rare quantities).
        # IS doesn't help with these unless we have a separate IS for them.
        Y_pol_cost = np.array(simA_pkls[cost_pol]['AggIncome'])
        Y_none_cost = np.array(simA_pkls[cost_none]['AggIncome'])
        NPV_AddInc = _calc_npv(Y_pol_cost - Y_none_cost, periods, Rfree)

        C_pol_cost = np.array(simA_pkls[cost_pol]['AggCons'])
        C_none_cost = np.array(simA_pkls[cost_none]['AggCons'])
        NPV_AddCons = _calc_npv(C_pol_cost - C_none_cost, periods, Rfree)

        if abs(NPV_AddInc) < 1e-10:
            cells[cell_name] = float('nan')
        else:
            cells[cell_name] = (NPV_num_total / NPV_AddInc
                                 + (NPV_AddInc - NPV_AddCons) / NPV_AddInc)

    return cells


def main():
    p = argparse.ArgumentParser()
    p.add_argument("simA_dir", help="Sim A pickles directory (natural intake)")
    p.add_argument("simB_dir", help="Sim B pickles directory (forced-unemp intake)")
    args = p.parse_args()

    print(f"Loading sim A: {args.simA_dir}")
    simA = load_pkls(args.simA_dir)
    print(f"Loading sim B: {args.simB_dir}")
    simB = load_pkls(args.simB_dir)

    print("\n=== Standard MC welfare (sim A only, baseline) ===")
    cells_simA = compute_welfare_simA_natural(simA)
    for k, v in cells_simA.items():
        v_s = 'NaN' if np.isnan(v) else f"{v:.4f}"
        print(f"  {k:<22} {v_s:>10}")

    print("\n=== IS-combined welfare (sim A + sim B) ===")
    cells_is = compute_welfare_IS_combined(simA, simB)
    for k, v in cells_is.items():
        v_s = 'NaN' if np.isnan(v) else f"{v:.4f}"
        print(f"  {k:<22} {v_s:>10}")

    print("\n=== Comparison ===")
    print(f"{'Cell':<22} {'simA':>10} {'IS':>10} {'IS-simA':>10}")
    for k in cells_simA:
        a = cells_simA[k]; b = cells_is[k]
        d = b - a if not (np.isnan(a) or np.isnan(b)) else float('nan')
        a_s = 'NaN' if np.isnan(a) else f"{a:.4f}"
        b_s = 'NaN' if np.isnan(b) else f"{b:.4f}"
        d_s = 'NaN' if np.isnan(d) else f"{d:+.4f}"
        print(f"  {k:<22} {a_s:>10} {b_s:>10} {d_s:>10}")


if __name__ == "__main__":
    main()
