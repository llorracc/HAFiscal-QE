"""
Diagnostic: verify that the 5D joint distribution's marginal over
(a_n, a_b, j_b) at each period equals the standalone POL scenario's
distribution as computed by the existing 1D TM-a kernel.

If equal → 5D propagation is correct, welfare bug is elsewhere.
If differ → 5D propagation has a bug.

Single-cohort, single-duration HS_Only A=20 for fast iteration.
"""
from __future__ import annotations
import os, sys, time
from copy import deepcopy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint5d import (
    compute_joint_markov, _resolve_scenario_IncShkDstn,
)
from tm_methods import compute_baseline_tm_data, propagate_experiment_tm_a

A = 20

def _build_path(act_T, nep, dur):
    p = list(np.arange(1, nep + 1) * 2) + [0] * (act_T + 5)
    p = p[:act_T]
    for t in range(min(dur, len(p))):
        p[t] += 1
    return p


def main():
    print("=== diag: 5D pol-marginal vs existing TM-a pol distribution ===")
    os.environ['HAFISCAL_UI_STATE_ENCODING'] = 'bug_fix'
    ctx = build_and_solve('HS_Only')
    agg_p = deepcopy(ctx['AggEco']); agg_p.switch_shock_type('recessionUI'); agg_p.solve()
    agg_n = deepcopy(ctx['AggEco']); agg_n.switch_shock_type('recession'); agg_n.solve()
    agg_b = deepcopy(ctx['AggEco']); agg_b.switch_shock_type('base'); agg_b.solve()
    for ag in agg_p.agents: ag.tm_a_indexed = True
    for ag in agg_n.agents: ag.tm_a_indexed = True
    for ag in agg_b.agents: ag.tm_a_indexed = True

    bd_list_b = compute_baseline_tm_data(agg_b, mCount=A)
    bd = bd_list_b[0]
    aGrid = bd['dist_aGrid']
    J = int(agg_p.agents[0].num_base_MrkvStates)
    act_T = ctx['act_T']
    nep = ctx['num_experiment_periods']
    dur = 2
    path = _build_path(act_T, nep, dur)

    # ============ EXISTING TM-a POL: get dist_series ============
    print(f"[1] Run existing TM-a propagator for POL (recessionUI)...")
    res_pol = propagate_experiment_tm_a(
        agg_p.agents[0], bd['ergodic'], path, bd['dist_aGrid'],
        bd['E_pLvl'], Cratio=1.0, act_T=act_T,
        neutral_measure=True,
        shock_type='recessionUI',
        interpretation='CDC',
        compute_welfare=True,
    )
    dist_pol_series = res_pol.get('dist_series', None)
    print(f"      dist_pol_series len: {len(dist_pol_series) if dist_pol_series else 'NONE'}")
    if dist_pol_series is None:
        print("      ERROR: no dist_series returned. Exit.")
        return

    # ============ 5D JOINT KERNEL: run a few periods, marginalize ============
    pass  # _step_period_5d imported below
    print(f"[2] Run 5D kernel for {min(5, act_T)} periods, compare marginals each step...")

    # Initialize 5D dist diagonal in (a_p, a_n, a_b) AND j_p = j_b.
    base_dist_aJ = np.asarray(bd['ergodic']).reshape(J, A)
    dist5d = np.zeros((A, A, A, J, J), dtype=np.float64)
    for j in range(J):
        for i_a in range(A):
            dist5d[i_a, i_a, i_a, j, j] = base_dist_aJ[j, i_a]

    cFuncs = agg_p.agents[0].solution[0].cFunc
    cFuncs_b = agg_b.agents[0].solution[0].cFunc
    Rfree = np.asarray(agg_p.agents[0].Rfree[:J], dtype=np.float64)
    PermGroFac = np.asarray(agg_p.agents[0].PermGroFac[0][:J], dtype=np.float64)
    Splurge = float(agg_p.agents[0].Splurge)
    rho = float(agg_p.agents[0].CRRA)

    # Mortality config (mirror compute_joint_welfare5d setup)
    from tm_methods import _effective_LivPrb
    LivPrb_arr_raw = np.asarray(agg_p.agents[0].LivPrb[0][:J], dtype=np.float64)
    T_age = getattr(agg_p.agents[0], 'T_age', None)
    LivPrb_eff = _effective_LivPrb(LivPrb_arr_raw, T_age)
    LivPrb_avg = float(np.mean(LivPrb_eff))
    newborn_diag = dist5d.copy()  # snapshot of t=0 init for rebirth
    print(f"  LivPrb_avg={LivPrb_avg:.6f}, death/period={1-LivPrb_avg:.6f}")

    IncShk_pol_full = _resolve_scenario_IncShkDstn(agg_p.agents[0], 'recessionUI')
    IncShk_none_full = _resolve_scenario_IncShkDstn(agg_n.agents[0], 'recession')
    IncShk_b_full = _resolve_scenario_IncShkDstn(agg_b.agents[0], 'base')
    MA_b = np.asarray(agg_b.agents[0].CondMrkvArrays[0], dtype=np.float64)

    # Compare pre-step distributions: 5D pol-marginal vs dist_pol_series[t]
    print(f"\n{'t':<3} {'macro':<5} {'mass_5d':>10} {'marg_pol_total':>15} {'pol_total':>10} {'L1 diff':>10}")
    for t in range(min(6, act_T)):
        # Marginal of dist5d over (a_n, a_b, j_b) → get (a_p, j_p) distribution.
        marg_pol = dist5d.sum(axis=(1, 2, 4))  # shape (A, J)
        marg_pol_J_first = marg_pol.T.flatten()  # to match dist_pol_series's layout (J*A or A*J?)
        # dist_pol from existing TM-a is (A*J,) — need to know layout.
        d_pol = np.asarray(dist_pol_series[t])
        # Try both layouts.
        if d_pol.size == A * J:
            d_pol_aJ = d_pol.reshape(J, A)  # try J first then A
            l1_v1 = np.abs(marg_pol.T - d_pol_aJ).sum()
            d_pol_Ja = d_pol.reshape(A, J)
            l1_v2 = np.abs(marg_pol - d_pol_Ja).sum()
            l1 = min(l1_v1, l1_v2)
            layout = 'J-first' if l1_v1 < l1_v2 else 'A-first'
        else:
            l1 = float('nan')
            layout = '?'

        macro_t = path[t]
        print(f"{t:<3} {macro_t:<5} {dist5d.sum():>10.6f} {marg_pol.sum():>15.6f} {d_pol.sum():>10.6f} {l1:>10.4e} (layout={layout})")

        if t < min(5, act_T):
            # Step 5D forward.
            macro_pn = path[t]
            MA_pn = np.asarray(agg_p.agents[0].CondMrkvArrays[macro_pn], dtype=np.float64)
            joint_markov = compute_joint_markov(MA_pn, MA_b)
            base_idx = macro_pn * J
            IS_p = list(IncShk_pol_full[base_idx:base_idx + J])
            IS_n = list(IncShk_none_full[base_idx:base_idx + J])
            IS_b = list(IncShk_b_full[0:J])
            from welfare6_tm_joint5d import _step_period_5d
            dist5d, _ = _step_period_5d(
                dist5d, aGrid, joint_markov,
                cFuncs, cFuncs_b,
                IS_p, IS_n, IS_b,
                Rfree, PermGroFac, Splurge, rho,
                1.0, 1.0, 1.0, 1.0,
                np.zeros(J), np.zeros(J),
                LivPrb_avg=LivPrb_avg, newborn_dist5d_diag=newborn_diag,
            )


if __name__ == '__main__':
    main()
