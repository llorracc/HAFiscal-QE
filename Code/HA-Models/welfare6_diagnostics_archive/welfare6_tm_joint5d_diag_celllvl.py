"""
Diagnostic: cell-by-cell comparison of 5D pol-marginal vs existing TM-a pol
distribution at t=1 (first step where they should be identical except for
the joint coupling, which marginalizes out cleanly).

Goal: identify WHERE the L1 ~5% mismatch is concentrated (low-a vs high-a;
which j; etc.) to localize the bug.
"""
from __future__ import annotations
import os, sys
from copy import deepcopy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint5d import (
    compute_joint_markov, _resolve_scenario_IncShkDstn, _step_period_5d,
)
from tm_methods import compute_baseline_tm_data, propagate_experiment_tm_a, _effective_LivPrb


A = 20

def _build_path(act_T, nep, dur):
    p = list(np.arange(1, nep + 1) * 2) + [0] * (act_T + 5)
    p = p[:act_T]
    for t in range(min(dur, len(p))):
        p[t] += 1
    return p


def main():
    print("=== diag-cellvl: localize 5D pol-marginal vs existing TM-a pol mismatch ===")
    os.environ['HAFISCAL_UI_STATE_ENCODING'] = 'bug_fix'
    ctx = build_and_solve('HS_Only')
    agg_p = deepcopy(ctx['AggEco']); agg_p.switch_shock_type('recessionUI'); agg_p.solve()
    agg_b = deepcopy(ctx['AggEco']); agg_b.switch_shock_type('base'); agg_b.solve()
    for ag in agg_p.agents: ag.tm_a_indexed = True
    for ag in agg_b.agents: ag.tm_a_indexed = True

    bd = compute_baseline_tm_data(agg_b, mCount=A)[0]
    aGrid = bd['dist_aGrid']
    J = int(agg_p.agents[0].num_base_MrkvStates)
    act_T = ctx['act_T']
    nep = ctx['num_experiment_periods']
    dur = 2
    path = _build_path(act_T, nep, dur)

    print(f"path[:5] = {path[:5]}, J={J}, A={A}")

    # === 1. Existing TM-a pol distribution at t=0 and t=1 ===
    print("\n[1] existing TM-a pol propagation")
    res_pol = propagate_experiment_tm_a(
        agg_p.agents[0], bd['ergodic'], path, bd['dist_aGrid'],
        bd['E_pLvl'], Cratio=1.0, act_T=act_T,
        neutral_measure=True,
        shock_type='recessionUI',
        interpretation='CDC',
        compute_welfare=True,
    )
    dist_pol_series = res_pol['dist_series']
    d_existing_t0 = np.asarray(dist_pol_series[0]).reshape(J, A)
    d_existing_t1 = np.asarray(dist_pol_series[1]).reshape(J, A)
    print(f"  existing pol t=0 mass: {d_existing_t0.sum():.6f}")
    print(f"  existing pol t=1 mass: {d_existing_t1.sum():.6f}")

    # === 2. 5D propagation, get pol marginal at t=1 ===
    print("\n[2] 5D propagation, pol marginal")
    base_dist_aJ = np.asarray(bd['ergodic']).reshape(J, A)
    dist5d = np.zeros((A, A, A, J, J))
    for j in range(J):
        for i_a in range(A):
            dist5d[i_a, i_a, i_a, j, j] = base_dist_aJ[j, i_a]
    newborn_diag = dist5d.copy()

    cFuncs = agg_p.agents[0].solution[0].cFunc
    cFuncs_b = agg_b.agents[0].solution[0].cFunc
    Rfree = np.asarray(agg_p.agents[0].Rfree[:J], dtype=np.float64)
    PermGroFac = np.asarray(agg_p.agents[0].PermGroFac[0][:J], dtype=np.float64)
    Splurge = float(agg_p.agents[0].Splurge)
    rho = float(agg_p.agents[0].CRRA)

    LivPrb_arr_raw = np.asarray(agg_p.agents[0].LivPrb[0][:J], dtype=np.float64)
    T_age = getattr(agg_p.agents[0], 'T_age', None)
    LivPrb_eff = _effective_LivPrb(LivPrb_arr_raw, T_age)
    LivPrb_avg = float(np.mean(LivPrb_eff))

    IncShk_pol_full = _resolve_scenario_IncShkDstn(agg_p.agents[0], 'recessionUI')
    IncShk_b_full = _resolve_scenario_IncShkDstn(agg_b.agents[0], 'base')
    macro_pn = path[0]
    MA_pn = np.asarray(agg_p.agents[0].CondMrkvArrays[macro_pn], dtype=np.float64)
    MA_b = np.asarray(agg_b.agents[0].CondMrkvArrays[0], dtype=np.float64)
    joint_markov = compute_joint_markov(MA_pn, MA_b)
    base_idx = macro_pn * J
    IS_p = list(IncShk_pol_full[base_idx:base_idx + J])
    IS_n = IS_p  # for THIS test, use POL incomes for the "none" axis too — degenerate test where pol = none → marginal pol must match existing TM-a recessionUI
    IS_b = list(IncShk_b_full[0:J])

    dist5d_next, _ = _step_period_5d(
        dist5d, aGrid, joint_markov,
        cFuncs, cFuncs_b, IS_p, IS_n, IS_b,
        Rfree, PermGroFac, Splurge, rho,
        1.0, 1.0, 1.0, 1.0, np.zeros(J), np.zeros(J),
        LivPrb_avg=LivPrb_avg, newborn_dist5d_diag=newborn_diag,
    )

    # Marginal of dist5d_next over (a_n, a_b, j_b) → (a_p, j_p) shape (A, J)
    d_5d_marg_t1 = dist5d_next.sum(axis=(1, 2, 4))  # shape (A, J)
    # Convert to (J, A) layout
    d_5d_marg_t1_Ja = d_5d_marg_t1.T

    print(f"  5D marg pol t=1 mass: {d_5d_marg_t1_Ja.sum():.6f}")

    # === 3. Cell-by-cell comparison ===
    print("\n[3] CELL-BY-CELL DIFF: existing - 5D-marginal at t=1")
    diff = d_existing_t1 - d_5d_marg_t1_Ja
    L1 = np.abs(diff).sum()
    print(f"  Total L1 diff: {L1:.6f} ({L1*100:.2f}%)")
    print()
    print("  Per-state L1 contribution:")
    for j in range(J):
        L1_j = np.abs(diff[j, :]).sum()
        mass_existing_j = d_existing_t1[j, :].sum()
        mass_5d_j = d_5d_marg_t1_Ja[j, :].sum()
        print(f"    j={j}: L1={L1_j:.4f}, existing_mass={mass_existing_j:.4f}, 5d_mass={mass_5d_j:.4f}, mass_diff={mass_existing_j-mass_5d_j:+.4f}")

    # Locate top 10 worst cells
    flat_diff = np.abs(diff).ravel()
    top_idx = np.argsort(flat_diff)[-10:][::-1]
    print()
    print("  Top 10 worst (j, a) cells:")
    print(f"  {'j':>3} {'a_idx':>6} {'a_value':>10} {'existing':>10} {'5D-marg':>10} {'diff':>10}")
    for idx in top_idx:
        j_idx = idx // A
        a_idx = idx % A
        e = d_existing_t1[j_idx, a_idx]
        f = d_5d_marg_t1_Ja[j_idx, a_idx]
        print(f"  {j_idx:>3} {a_idx:>6} {aGrid[a_idx]:>10.3f} {e:>10.4e} {f:>10.4e} {(e-f):>+10.4e}")


if __name__ == '__main__':
    main()
