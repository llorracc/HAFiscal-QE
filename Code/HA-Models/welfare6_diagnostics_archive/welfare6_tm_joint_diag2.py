"""
Diagnostic 2: at t=0 the joint distribution is diagonal (a_p=a_n), so the
joint kernel's integrand should reduce to the per-cell evaluator's integrand.
If they match → joint integrand correct, drift is in t>0 propagation. If
they differ → joint integrand buggy.

Compute both at t=0 for HS_Only bug_fix recessionUI vs recession.
"""
from __future__ import annotations
import os, sys
from copy import deepcopy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint import (
    compute_joint_welfare_period,
    _embed_marginal_base_c_per_j,
    _u, _mu_inv,
)
from tm_methods import compute_baseline_tm_data


def main():
    print("=== Diagnostic 2: joint vs per-cell agreement at t=0 ===")
    print(f"  HAFISCAL_UI_STATE_ENCODING = {os.environ.get('HAFISCAL_UI_STATE_ENCODING', 'legacy')}")

    ctx = build_and_solve('HS_Only')
    AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
    AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()
    AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()
    for ag in AggEco_pol.agents: ag.tm_a_indexed = True
    for ag in AggEco_none.agents: ag.tm_a_indexed = True
    for ag in AggEco_base.agents: ag.tm_a_indexed = True

    aCount = 50
    bd_list = compute_baseline_tm_data(AggEco_base, mCount=aCount)

    agent_pol = AggEco_pol.agents[0]
    agent_none = AggEco_none.agents[0]
    agent_base = AggEco_base.agents[0]
    bd = bd_list[0]
    aGrid = bd['dist_aGrid']
    A = len(aGrid)
    J = int(agent_pol.num_base_MrkvStates)
    base_dist_aJ = np.asarray(bd['ergodic']).reshape(J, A)

    # Initialize diagonal joint dist.
    dist_joint = np.zeros((A, A, J))
    for j in range(J):
        np.fill_diagonal(dist_joint[:, :, j], base_dist_aJ[j, :])

    # Per-state marginal-base c (for b3 anchor in joint kernel).
    Rfree = np.asarray(agent_base.Rfree[:J], dtype=np.float64)
    PermGroFac = np.asarray(agent_base.PermGroFac[0][:J], dtype=np.float64)
    Splurge = float(agent_base.Splurge)
    CRRA = float(agent_base.CRRA)
    base_cFuncs = agent_base.solution[0].cFunc
    base_IncShkDstn = agent_base.IncShkDstn[0]
    c_b_marg = _embed_marginal_base_c_per_j(base_dist_aJ, aGrid, base_cFuncs,
                                             base_IncShkDstn, Rfree, PermGroFac,
                                             Splurge, J)
    print(f"\nc_b_marginal_per_j (b3 anchor): {c_b_marg}")

    # Resolve per-period IncShkDstn for macro=3 (recession Q1).
    macro_t = 3
    IncShkDstn_pol_full = agent_pol.IncShkDstn_recessionUI[0]
    IncShkDstn_none_full = agent_none.IncShkDstn_recession[0]
    IncShkDstn_pol_t = list(IncShkDstn_pol_full[macro_t * J:(macro_t + 1) * J])
    IncShkDstn_none_t = list(IncShkDstn_none_full[macro_t * J:(macro_t + 1) * J])
    print(f"\nIncShkDstn at macro=3 (recession Q1):")
    for jp in range(J):
        xi_p = IncShkDstn_pol_t[jp].atoms[1]
        xi_n = IncShkDstn_none_t[jp].atoms[1]
        diff = '<-- DIFFER' if not np.allclose(xi_p, xi_n) else ''
        print(f"  jp={jp}: pol_xi={xi_p}, none_xi={xi_n}  {diff}")

    MarkovArray_t = np.asarray(agent_pol.CondMrkvArrays[macro_t], dtype=np.float64)
    cFuncs_pol = agent_pol.solution[0].cFunc
    cFuncs_none = agent_none.solution[0].cFunc
    Rfree_pol = np.asarray(agent_pol.Rfree[:J], dtype=np.float64)
    PermGroFac_pol = np.asarray(agent_pol.PermGroFac[0][:J], dtype=np.float64)

    # Run joint kernel for ONE period (t=0 with macro=3).
    dist_next, w2, w3 = compute_joint_welfare_period(
        dist_joint, aGrid, j=None, MarkovArray=MarkovArray_t,
        cFuncs_pol=cFuncs_pol, cFuncs_none=cFuncs_none,
        IncShkDstn_pol=IncShkDstn_pol_t, IncShkDstn_none=IncShkDstn_none_t,
        Rfree=Rfree_pol, PermGroFac=PermGroFac_pol,
        Splurge=Splurge, CRRA=CRRA,
        c_b_marginal_per_j=c_b_marg,
    )
    print(f"\nJoint kernel t=0 (raw, before N×E_pLvl×pLvl_factor scaling):")
    print(f"  welfare_num_b2 = {w2:.6e}")
    print(f"  welfare_num_b3 = {w3:.6e}")

    # Reproduce per-cell integrand at t=0 manually.
    # Per-cell evaluator uses dist_pol (= base dist at t=0).
    # For each (j, jp, atom), compute (u(c_p(a)) - u(c_n(a))) / u'(c_base(a))
    # weighted by dist_pol[j, a] * Markov[j, jp] * pmv.
    rho = CRRA
    pc_b3 = 0.0  # per-cell b3 (using c_b_marg per j as anchor — apples-to-apples with joint b3)
    pc_b2 = 0.0  # per-cell b2 (using c_n as anchor)
    pc_pointwise = 0.0  # per-cell with pointwise c_b (the actual per-cell evaluator)

    for j in range(J):
        d_j = base_dist_aJ[j, :]
        if d_j.sum() <= 1e-15:
            continue
        for jp in range(J):
            trans = MarkovArray_t[j, jp]
            if trans < 1e-15:
                continue
            psi = IncShkDstn_pol_t[jp].atoms[0]
            xi_p = IncShkDstn_pol_t[jp].atoms[1]
            xi_n = IncShkDstn_none_t[jp].atoms[1]
            pmv = IncShkDstn_pol_t[jp].pmv
            for atom in range(len(pmv)):
                psi_a = psi[atom]
                xi_p_a = xi_p[atom]
                xi_n_a = xi_n[atom]
                pmv_a = pmv[atom]
                inv_pG = 1.0 / (psi_a * PermGroFac_pol[jp])
                m_p = Rfree_pol[jp] * aGrid * inv_pG + xi_p_a
                m_n = Rfree_pol[jp] * aGrid * inv_pG + xi_n_a
                cs_p = cFuncs_pol[jp](m_p, np.ones(A))
                cs_n = cFuncs_none[jp](m_n, np.ones(A))
                c_p = (1 - Splurge) * cs_p + Splurge * xi_p_a
                c_n = (1 - Splurge) * cs_n + Splurge * xi_n_a
                # Same xi_b atom (= same atom index) for base scenario.
                xi_b = base_IncShkDstn[jp].atoms[1][min(atom, len(base_IncShkDstn[jp].pmv)-1)]
                m_b = Rfree[jp] * aGrid * inv_pG + xi_b
                cs_b = base_cFuncs[jp](m_b, np.ones(A))
                c_b = (1 - Splurge) * cs_b + Splurge * xi_b
                u_diff = _u(c_p, rho) - _u(c_n, rho)
                w_cell = d_j * trans * pmv_a
                pc_b2 += np.sum(w_cell * u_diff * _mu_inv(c_n, rho))
                pc_b3 += np.sum(w_cell * u_diff * (c_b_marg[jp] ** rho))
                pc_pointwise += np.sum(w_cell * u_diff * _mu_inv(c_b, rho))

    print(f"\nPer-cell-style at t=0 (raw, same scaling):")
    print(f"  per-cell b2 (anchor=c_n pointwise):     {pc_b2:.6e}")
    print(f"  per-cell b3 (anchor=c_b_marg per j):    {pc_b3:.6e}")
    print(f"  per-cell pointwise (anchor=c_b per cell): {pc_pointwise:.6e}")

    print(f"\n=== Comparison ===")
    print(f"  joint b2 vs per-cell b2: {w2:.4e} vs {pc_b2:.4e}  diff={(w2-pc_b2):.2e}")
    print(f"  joint b3 vs per-cell b3: {w3:.4e} vs {pc_b3:.4e}  diff={(w3-pc_b3):.2e}")
    print(f"  per-cell pointwise / per-cell b3: {pc_pointwise / pc_b3:.3f} (signal lost by per-state anchor)")


if __name__ == '__main__':
    main()
