"""
Isolation diagnostic: run 5D with MA_b = MA_pn (= same Markov for all
scenarios). joint Markov collapses to diagonal-in-j; joint propagation
should give EXACT same pol-marginal as standalone TM-a if propagation
is correct.

If 5D still mismatches → bug NOT in joint Markov, bug is in
asset propagation / newborn / shock atoms.
"""
from __future__ import annotations
import os, sys
from copy import deepcopy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint5d import compute_joint_markov, _resolve_scenario_IncShkDstn, _step_period_5d
from tm_methods import compute_baseline_tm_data, propagate_experiment_tm_a, _effective_LivPrb


A = 20

def _build_path(act_T, nep, dur):
    p = list(np.arange(1, nep + 1) * 2) + [0] * (act_T + 5)
    p = p[:act_T]
    for t in range(min(dur, len(p))):
        p[t] += 1
    return p


def main():
    print("=== ISOLATION: 5D with MA_b = MA_pn (single-Markov check) ===")
    os.environ['HAFISCAL_UI_STATE_ENCODING'] = 'bug_fix'
    ctx = build_and_solve('HS_Only')
    agg_p = deepcopy(ctx['AggEco']); agg_p.switch_shock_type('recessionUI'); agg_p.solve()
    agg_b = deepcopy(ctx['AggEco']); agg_b.switch_shock_type('base'); agg_b.solve()
    for ag in agg_p.agents: ag.tm_a_indexed = True
    for ag in agg_b.agents: ag.tm_a_indexed = True

    bd = compute_baseline_tm_data(agg_b, mCount=A)[0]
    aGrid = bd['dist_aGrid']
    J = int(agg_p.agents[0].num_base_MrkvStates)
    nep = ctx['num_experiment_periods']
    dur = 2
    path = _build_path(ctx['act_T'], nep, dur)
    macro_pn = path[0]
    print(f"path[0:5]={path[:5]}, macro_pn={macro_pn}")

    # Existing TM-a recessionUI pol distribution at t=1
    res_pol = propagate_experiment_tm_a(
        agg_p.agents[0], bd['ergodic'], path, bd['dist_aGrid'],
        bd['E_pLvl'], Cratio=1.0, act_T=ctx['act_T'],
        neutral_measure=True, shock_type='recessionUI',
        interpretation='CDC', compute_welfare=True,
    )
    d_existing_t1 = np.asarray(res_pol['dist_series'][1]).reshape(J, A)
    print(f"\nExisting per-j mass at t=1: {[d_existing_t1[j].sum() for j in range(J)]}")

    # 5D setup
    base_dist_aJ = np.asarray(bd['ergodic']).reshape(J, A)
    dist5d = np.zeros((A, A, A, J, J))
    for j in range(J):
        for i_a in range(A):
            dist5d[i_a, i_a, i_a, j, j] = base_dist_aJ[j, i_a]
    newborn_diag = dist5d.copy()

    cFuncs_full = agg_p.agents[0].solution[0].cFunc
    cFuncs_b_full = agg_b.agents[0].solution[0].cFunc
    base_idx_pn = macro_pn * J
    cFuncs = [cFuncs_full[base_idx_pn + j] for j in range(J)]
    cFuncs_b = [cFuncs_b_full[0 + j] for j in range(J)]
    Rfree = np.asarray(agg_p.agents[0].Rfree[:J], dtype=np.float64)
    PermGroFac = np.asarray(agg_p.agents[0].PermGroFac[0][:J], dtype=np.float64)
    Splurge = float(agg_p.agents[0].Splurge)
    rho = float(agg_p.agents[0].CRRA)

    LivPrb_arr_raw = np.asarray(agg_p.agents[0].LivPrb[0][:J], dtype=np.float64)
    T_age = getattr(agg_p.agents[0], 'T_age', None)
    LivPrb_eff = _effective_LivPrb(LivPrb_arr_raw, T_age)
    LivPrb_avg = float(np.mean(LivPrb_eff))

    # Override newborn_diag to use a=0 + markov_ergodic (matches new fix #5)
    from tm_methods import _solve_markov_ergodic
    MA_b_arr = np.asarray(agg_b.agents[0].CondMrkvArrays[0], dtype=np.float64)
    markov_erg = _solve_markov_ergodic(MA_b_arr)
    newborn_diag = np.zeros((A, A, A, J, J))
    for j in range(J):
        newborn_diag[0, 0, 0, j, j] = markov_erg[j]

    IncShk_pol_full = _resolve_scenario_IncShkDstn(agg_p.agents[0], 'recessionUI')
    base_idx = macro_pn * J
    IS_p = list(IncShk_pol_full[base_idx:base_idx + J])

    MA_pn = np.asarray(agg_p.agents[0].CondMrkvArrays[macro_pn], dtype=np.float64).copy()
    # Unemployment spike at t=0 of recession (mirror existing TM-a)
    if macro_pn % 2 == 1:
        Un = float(getattr(agg_p.agents[0], 'Urate_normal', 0.045))
        Ur = float(getattr(agg_p.agents[0], 'Urate_recession', Un))
        if Ur > Un:
            spike_frac = (Ur - Un) / (1.0 - Un)
            MA_pn[0, :] = (1.0 - spike_frac) * MA_pn[0, :] + spike_frac * MA_pn[1, :]
            print(f"  [t=0 spike] Un={Un}, Ur={Ur}, spike_frac={spike_frac:.4f}")
    # CRITICAL: USE MA_pn for BOTH pol and base axes (= force same Markov)
    joint_markov = compute_joint_markov(MA_pn, MA_pn)

    # Verify: joint_markov should be diagonal in (k_p, k_b) when MAs match
    print(f"\njoint_markov diagonal-vs-off? At source (0,0):")
    print(f"  joint[0,0,0,0]={joint_markov[0,0,0,0]:.4f}, MA_pn[0,0]={MA_pn[0,0]:.4f}")
    print(f"  off-diag mass: {joint_markov[0,0].sum() - np.diag(joint_markov[0,0]).sum():.6f} (should be ~0)")

    # Run one step
    dist_next, _ = _step_period_5d(
        dist5d, aGrid, joint_markov,
        cFuncs, cFuncs_b, IS_p, IS_p, IS_p,  # use POL incomes for ALL scenarios → identical evolution
        Rfree, PermGroFac, Splurge, rho,
        1.0, 1.0, 1.0, 1.0, np.zeros(J), np.zeros(J),
        LivPrb_avg=LivPrb_avg, newborn_dist5d_diag=newborn_diag,
    )
    d_5d_marg = dist_next.sum(axis=(1, 2, 4)).T  # (J, A)

    print(f"\n5D pol-marg per-j mass at t=1: {[d_5d_marg[j].sum() for j in range(J)]}")
    print(f"\nL1 diff (existing - 5D-marg):")
    diff = d_existing_t1 - d_5d_marg
    L1 = np.abs(diff).sum()
    print(f"  Total: {L1:.6f} ({L1*100:.2f}%)")
    for j in range(J):
        print(f"  j={j}: L1={np.abs(diff[j]).sum():.4f}, mass_diff={d_existing_t1[j].sum() - d_5d_marg[j].sum():+.4f}")


if __name__ == '__main__':
    main()
