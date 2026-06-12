"""
Phase A.6 — β-vectorized 5D welfare kernel.

Within each education group at Baseline, the 7 β-atoms share the
income process entirely (CondMrkvArrays, IncShkDstn, joint Markov
tensor). Only the consumption functions (cFunc) and initial asset
distribution differ per β.

This module batches the n_β-shared work across the 7 β-atoms within
an ed_type, calling cFunc-dependent operations N_β times but
amortizing the β-independent inner-loop setup (IncShkDstn atom
enumeration, Q-reweighting, m_p/m_n/m_b computation, transition
probability lookup) once.

The output is bit-identical (modulo summation order) to running
welfare6_tm_joint5d.compute_joint_welfare5d N_β times in sequence.

Usage:
    res = compute_joint_welfare5d_batch(
        agents_pol_by_beta,         # list of n_β AggFiscalType agents (pol scenario)
        agents_none_by_beta,        # list of n_β AggFiscalType agents (none scenario)
        agents_base_by_beta,        # list of n_β AggFiscalType agents (base scenario)
        baseline_tm_data_by_beta,   # list of n_β baseline_tm_data dicts
        EconomyMrkv_path_pn,
        act_T,
        ...
    )
    # res = list of n_β dicts, each with same shape as compute_joint_welfare5d output.
"""
from __future__ import annotations
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from welfare6_tm_joint5d import (
    compute_joint_markov,
    _resolve_scenario_IncShkDstn,
    _3d_bilinear_distribute,
    _u, _mu_inv,
    _DIST_EPS, _TRANS_EPS,
)


def _step_period_5d_batch(
    dist5d_batch,          # (n_β, A, A, A, J, J)
    aGrid,
    joint_markov,
    cFuncs_pol_batch,      # list of n_β cFunc lists
    cFuncs_none_batch,     # list of n_β cFunc lists
    cFuncs_b_batch,        # list of n_β cFunc lists
    IncShk_pol_t, IncShk_none_t, IncShk_b_t,
    Rfree, PermGroFac, Splurge, rho,
    Cratio_pol, Cratio_none,
    AggDemandFac_pol, AggDemandFac_none,
    TranShk_addition_pol, TranShk_addition_none,
    LivPrb_avg=1.0,
    newborn_dist5d_diag_batch=None,  # (n_β, A, A, A, J, J) or None
):
    """
    Batched per-period 5D kernel. Amortizes the β-shared inner-loop work
    across n_β β-atoms.

    Returns
    -------
    dist5d_next_batch : (n_β, A, A, A, J, J)
    welfare_num_per_beta : (n_β,) float
    info_per_beta : list of n_β dicts, each with keys
        inc_pol, inc_none, cons_pol, cons_none, per_cell
    """
    n_beta = dist5d_batch.shape[0]
    A = len(aGrid)
    J = joint_markov.shape[0]

    dist5d_next_batch = np.zeros_like(dist5d_batch)
    welfare_num_per_beta = np.zeros(n_beta, dtype=np.float64)
    agg_inc_pol_per_beta = np.zeros(n_beta, dtype=np.float64)
    agg_inc_none_per_beta = np.zeros(n_beta, dtype=np.float64)
    agg_cons_pol_per_beta = np.zeros(n_beta, dtype=np.float64)
    agg_cons_none_per_beta = np.zeros(n_beta, dtype=np.float64)
    per_cell_per_beta = [{} for _ in range(n_beta)]

    # Precompute meshgrid (β-shared)
    I = np.arange(A)
    IP, IN, IB = np.meshgrid(I, I, I, indexing='ij')
    Cratio_p_arr = np.full(A, Cratio_pol)
    Cratio_n_arr = np.full(A, Cratio_none)
    Cratio_b_arr = np.full(A, 1.0)

    # Iterate over source (j_pn, j_b).
    for j_pn_src in range(J):
        for j_b_src in range(J):
            # Per-β source slice and mass
            d_src_batch = dist5d_batch[:, :, :, :, j_pn_src, j_b_src]  # (n_β, A, A, A)
            mass_total_per_beta = d_src_batch.sum(axis=(1, 2, 3))      # (n_β,)
            if mass_total_per_beta.max() <= _DIST_EPS:
                continue

            # Destination iteration
            for j_pn_dst in range(J):
                for j_b_dst in range(J):
                    p_jj = joint_markov[j_pn_src, j_b_src, j_pn_dst, j_b_dst]
                    if p_jj < _TRANS_EPS:
                        continue

                    # β-SHARED: IncShkDstn extraction + Q-reweighting
                    dstn_p = IncShk_pol_t[j_pn_dst]
                    dstn_n = IncShk_none_t[j_pn_dst]
                    dstn_b = IncShk_b_t[j_b_dst]

                    psi = np.asarray(dstn_p.atoms[0])
                    xi_p_atoms = np.asarray(dstn_p.atoms[1])
                    xi_n_atoms = np.asarray(dstn_n.atoms[1])
                    pmv_raw = np.asarray(dstn_p.pmv)
                    psi_b = np.asarray(dstn_b.atoms[0])
                    xi_b_atoms = np.asarray(dstn_b.atoms[1])
                    pmv_b_raw = np.asarray(dstn_b.pmv)

                    E_psi_p = float(np.dot(pmv_raw, psi))
                    pmv = pmv_raw * psi / max(E_psi_p, 1e-12)
                    E_psi_b = float(np.dot(pmv_b_raw, psi_b))
                    pmv_b_arr = pmv_b_raw * psi_b / max(E_psi_b, 1e-12)

                    n_atoms_pn = len(pmv)
                    n_atoms_b = len(pmv_b_arr)

                    # β-SHARED: atom-pair enumeration
                    if n_atoms_pn == n_atoms_b:
                        atom_pairs = [(i, i, pmv[i]) for i in range(n_atoms_pn)]
                    elif n_atoms_pn > 1 and n_atoms_b == 1:
                        atom_pairs = [(i, 0, pmv[i]) for i in range(n_atoms_pn)]
                    elif n_atoms_pn == 1 and n_atoms_b > 1:
                        atom_pairs = [(0, j, pmv_b_arr[j]) for j in range(n_atoms_b)]
                    else:
                        F_p = np.cumsum(pmv)
                        F_b = np.cumsum(pmv_b_arr)
                        F_p_left = np.concatenate([[0], F_p[:-1]])
                        F_b_left = np.concatenate([[0], F_b[:-1]])
                        atom_pairs = []
                        for i in range(n_atoms_pn):
                            for j in range(n_atoms_b):
                                p = max(0.0, min(F_p[i], F_b[j]) - max(F_p_left[i], F_b_left[j]))
                                if p > _TRANS_EPS:
                                    atom_pairs.append((i, j, p))

                    for atom_p_idx, atom_b_idx, pmv_a in atom_pairs:
                        psi_a = psi[atom_p_idx]
                        psi_b_a = psi_b[atom_b_idx]
                        if pmv_a < _TRANS_EPS:
                            continue

                        # β-SHARED: effective income, asset update grids
                        xi_eff_p = AggDemandFac_pol * xi_p_atoms[atom_p_idx] + TranShk_addition_pol[j_pn_dst]
                        xi_eff_n = AggDemandFac_none * xi_n_atoms[atom_p_idx] + TranShk_addition_none[j_pn_dst]
                        xi_eff_b = xi_b_atoms[atom_b_idx]

                        inv_pG_pn = 1.0 / (psi_a * PermGroFac[j_pn_dst])
                        inv_pG_b = 1.0 / (psi_b_a * PermGroFac[j_b_dst])
                        R_pn = Rfree[j_pn_dst]
                        R_b = Rfree[j_b_dst]

                        m_p = R_pn * aGrid * inv_pG_pn + xi_eff_p
                        m_n = R_pn * aGrid * inv_pG_pn + xi_eff_n
                        m_b = R_b * aGrid * inv_pG_b + xi_eff_b

                        # β-DEPENDENT: cFunc + asset evolution + welfare + distribute
                        for b in range(n_beta):
                            d_src = d_src_batch[b]
                            if d_src.sum() <= _DIST_EPS:
                                continue

                            cFuncs_pol = cFuncs_pol_batch[b]
                            cFuncs_none = cFuncs_none_batch[b]
                            cFuncs_b = cFuncs_b_batch[b]

                            c_star_p = cFuncs_pol[j_pn_dst](m_p, Cratio_p_arr)
                            c_star_n = cFuncs_none[j_pn_dst](m_n, Cratio_n_arr)
                            c_star_b = cFuncs_b[j_b_dst](m_b, Cratio_b_arr)

                            c_p = (1 - Splurge) * c_star_p + Splurge * xi_eff_p
                            c_n = (1 - Splurge) * c_star_n + Splurge * xi_eff_n
                            c_b = (1 - Splurge) * c_star_b + Splurge * xi_eff_b

                            a_p_next = m_p - c_p
                            a_n_next = m_n - c_n
                            a_b_next = m_b - c_b

                            u_p = _u(c_p, rho)
                            u_n = _u(c_n, rho)
                            mu_inv_b = _mu_inv(c_b, rho)
                            u_diff = u_p[:, None] - u_n[None, :]
                            integrand_3d = u_diff[:, :, None] * mu_inv_b[None, None, :]

                            weight_3d = d_src * p_jj * pmv_a

                            welfare_num_per_beta[b] += float(np.sum(weight_3d * integrand_3d))

                            weight_pol = weight_3d.sum(axis=(1, 2))
                            weight_none = weight_3d.sum(axis=(0, 2))
                            weight_base = weight_3d.sum(axis=(0, 1))
                            agg_inc_pol_per_beta[b] += float(np.sum(weight_pol) * xi_eff_p)
                            agg_inc_none_per_beta[b] += float(np.sum(weight_none) * xi_eff_n)
                            agg_cons_pol_per_beta[b] += float(np.sum(weight_pol * c_p))
                            agg_cons_none_per_beta[b] += float(np.sum(weight_none * c_n))

                            # per_cell tracking
                            cell_key = (j_pn_dst, j_b_dst)
                            if cell_key not in per_cell_per_beta[b]:
                                per_cell_per_beta[b][cell_key] = {
                                    'mass': 0.0, 'sum_cp': 0.0, 'sum_cn': 0.0,
                                    'sum_cb': 0.0, 'sum_w': 0.0,
                                }
                            pc = per_cell_per_beta[b][cell_key]
                            cell_mass = float(np.sum(weight_3d))
                            pc['mass'] += cell_mass
                            pc['sum_cp'] += float(np.sum(weight_pol * c_p))
                            pc['sum_cn'] += float(np.sum(weight_none * c_n))
                            pc['sum_cb'] += float(np.sum(weight_base * c_b))
                            pc['sum_w'] += float(np.sum(weight_3d * integrand_3d))

                            # Bilinear distribute (per β)
                            flat_w = weight_3d.ravel()
                            mask = flat_w > _DIST_EPS
                            if not mask.any():
                                continue
                            vp_flat = a_p_next[IP].ravel()[mask]
                            vn_flat = a_n_next[IN].ravel()[mask]
                            vb_flat = a_b_next[IB].ravel()[mask]
                            w_flat = flat_w[mask]
                            _3d_bilinear_distribute(
                                vp_flat, vn_flat, vb_flat, w_flat,
                                aGrid, dist5d_next_batch[b], j_pn_dst, j_b_dst)

    # Mortality + rebirth, per β
    if newborn_dist5d_diag_batch is not None and LivPrb_avg < 1.0 - 1e-15:
        total_mass_per_beta = dist5d_next_batch.sum(axis=(1, 2, 3, 4, 5))
        dist5d_next_batch *= LivPrb_avg
        newborn_mass_per_beta = (1.0 - LivPrb_avg) * total_mass_per_beta
        for b in range(n_beta):
            dist5d_next_batch[b] += newborn_mass_per_beta[b] * newborn_dist5d_diag_batch[b]

    info_per_beta = [
        {
            'inc_pol': float(agg_inc_pol_per_beta[b]),
            'inc_none': float(agg_inc_none_per_beta[b]),
            'cons_pol': float(agg_cons_pol_per_beta[b]),
            'cons_none': float(agg_cons_none_per_beta[b]),
            'per_cell': per_cell_per_beta[b],
        }
        for b in range(n_beta)
    ]

    return dist5d_next_batch, welfare_num_per_beta, info_per_beta


def compute_joint_welfare5d_batch(
    agents_pol_by_beta,           # list of n_β AggFiscalType
    agents_none_by_beta,
    agents_base_by_beta,
    baseline_tm_data_by_beta,     # list of n_β baseline_tm_data dicts
    EconomyMrkv_path_pn, act_T,
    shock_type_pol='recessionUI',
    shock_type_none='recession',
    AggDemandFac_pol_series=None, AggDemandFac_none_series=None,
    Cratio_pol_series=None, Cratio_none_series=None,
    TranShk_addition_pol_series=None, TranShk_addition_none_series=None,
    verbose=False,
):
    """
    β-vectorized version of compute_joint_welfare5d.

    All n_β agents must share the SAME income process (CondMrkvArrays,
    IncShkDstn, Rfree, PermGroFac, etc.) — typically the case for the
    7 β-atoms within a Baseline education group.

    Returns a list of n_β dicts, each with the same keys as
    compute_joint_welfare5d's return value.
    """
    from income_process_sst import effective_pLvl_growth
    from tm_methods import _effective_LivPrb, _solve_markov_ergodic

    n_beta = len(agents_pol_by_beta)
    assert n_beta == len(agents_none_by_beta) == len(agents_base_by_beta) == len(baseline_tm_data_by_beta)

    # All agents in the batch share the income process. Use cohort 0 as
    # representative for the β-shared structure.
    agent_pol_0 = agents_pol_by_beta[0]
    agent_none_0 = agents_none_by_beta[0]
    agent_base_0 = agents_base_by_beta[0]
    aGrid = baseline_tm_data_by_beta[0]['dist_aGrid']
    A = len(aGrid)
    J = int(agent_pol_0.num_base_MrkvStates)

    if AggDemandFac_pol_series is None:
        AggDemandFac_pol_series = np.ones(act_T)
    if AggDemandFac_none_series is None:
        AggDemandFac_none_series = np.ones(act_T)
    if Cratio_pol_series is None:
        Cratio_pol_series = np.ones(act_T)
    if Cratio_none_series is None:
        Cratio_none_series = np.ones(act_T)
    if TranShk_addition_pol_series is None:
        TranShk_addition_pol_series = np.zeros((act_T, J))
    if TranShk_addition_none_series is None:
        TranShk_addition_none_series = np.zeros((act_T, J))

    # β-shared: Markov array, scenario IncShkDstn, Rfree, PermGroFac, Splurge, rho
    MA_b = np.asarray(agent_base_0.CondMrkvArrays[0], dtype=np.float64)
    IncShk_pol_full = _resolve_scenario_IncShkDstn(agent_pol_0, shock_type_pol)
    IncShk_none_full = _resolve_scenario_IncShkDstn(agent_none_0, shock_type_none)
    IncShk_base_full = _resolve_scenario_IncShkDstn(agent_base_0, 'base')
    Rfree = np.asarray(agent_pol_0.Rfree[:J], dtype=np.float64)
    PermGroFac = np.asarray(agent_pol_0.PermGroFac[0][:J], dtype=np.float64)
    Splurge = float(agent_pol_0.Splurge)
    rho = float(agent_pol_0.CRRA)

    # LivPrb (β-shared per construction)
    LivPrb_arr_raw = np.asarray(agent_pol_0.LivPrb[0][:J], dtype=np.float64)
    T_age = getattr(agent_pol_0, 'T_age', None)
    LivPrb_eff = _effective_LivPrb(LivPrb_arr_raw, T_age)
    LivPrb_avg = float(np.mean(LivPrb_eff))
    death_prob = 1.0 - LivPrb_avg

    # β-shared: ergodic baseline Markov distribution
    markov_erg_base = _solve_markov_ergodic(MA_b)
    IncShk_b_macro0 = list(IncShk_base_full[0:J])

    # β-dependent setup: dist5d initial, cFuncs, newborn_dist
    dist5d_batch = np.zeros((n_beta, A, A, A, J, J), dtype=np.float64)
    newborn_dist5d_diag_batch = np.zeros((n_beta, A, A, A, J, J), dtype=np.float64)
    cFuncs_pol_full_batch = [a.solution[0].cFunc for a in agents_pol_by_beta]
    cFuncs_none_full_batch = [a.solution[0].cFunc for a in agents_none_by_beta]
    cFuncs_b_full_batch = [a.solution[0].cFunc for a in agents_base_by_beta]

    for b in range(n_beta):
        bd_b = baseline_tm_data_by_beta[b]
        base_ergodic = np.asarray(bd_b['ergodic'], dtype=np.float64)
        base_dist_aJ = base_ergodic.reshape(J, A)
        for j in range(J):
            for a_idx in range(A):
                dist5d_batch[b, a_idx, a_idx, a_idx, j, j] = base_dist_aJ[j, a_idx]

        # newborn dist (uses cFunc_b which is per β)
        cFuncs_b_macro0 = [cFuncs_b_full_batch[b][0 + j] for j in range(J)]
        for j in range(J):
            if markov_erg_base[j] < _DIST_EPS:
                continue
            dstn_j = IncShk_b_macro0[j]
            psi_j = np.asarray(dstn_j.atoms[0])
            xi_j = np.asarray(dstn_j.atoms[1])
            pmv_raw_j = np.asarray(dstn_j.pmv)
            E_psi_j = float(np.dot(pmv_raw_j, psi_j))
            pmv_j = pmv_raw_j * psi_j / max(E_psi_j, 1e-12)
            for atom_idx, (xi_val, pmv_val) in enumerate(zip(xi_j, pmv_j)):
                if pmv_val < _DIST_EPS:
                    continue
                m_init = float(xi_val)
                c_star = float(cFuncs_b_macro0[j](np.array([m_init]), np.array([1.0]))[0])
                c_actual = (1.0 - Splurge) * c_star + Splurge * m_init
                a_init = max(0.0, m_init - c_actual)
                a_init_clip = max(aGrid[0], min(aGrid[-1], a_init))
                i_lo = np.searchsorted(aGrid, a_init_clip, side='right') - 1
                i_lo = max(0, min(A - 2, int(i_lo)))
                i_hi = i_lo + 1
                w_hi = (a_init_clip - aGrid[i_lo]) / max(aGrid[i_hi] - aGrid[i_lo], 1e-12)
                w_lo = 1.0 - w_hi
                mass_atom = markov_erg_base[j] * pmv_val
                newborn_dist5d_diag_batch[b, i_lo, i_lo, i_lo, j, j] += mass_atom * w_lo
                newborn_dist5d_diag_batch[b, i_hi, i_hi, i_hi, j, j] += mass_atom * w_hi
        nb_total = newborn_dist5d_diag_batch[b].sum()
        if nb_total > _DIST_EPS:
            newborn_dist5d_diag_batch[b] /= nb_total

    # β-shared: pLvl scaling (uses agent_pol_0 since they share income process)
    u_ergodic_per_beta = [bd.get('u_ergodic', 0.04) for bd in baseline_tm_data_by_beta]
    g_base_pLvl = effective_pLvl_growth(agent_pol_0, u_ergodic_per_beta[0])  # β-shared
    pLvl_factor_per_beta = np.ones(n_beta, dtype=np.float64)
    E_pLvl_per_beta = np.array([float(bd['E_pLvl']) for bd in baseline_tm_data_by_beta])
    AgentCount_per_beta = np.array(
        [int(getattr(a, 'AgentCount', 1)) for a in agents_pol_by_beta],
        dtype=np.float64,
    )
    pop_rescale_per_beta = np.array(
        [float(getattr(a, 'pop_rescale_factor', 1.0)) for a in agents_pol_by_beta],
        dtype=np.float64,
    )
    N_eff_per_beta = AgentCount_per_beta * pop_rescale_per_beta

    # Output series (per β)
    welfare_num_series_batch = np.zeros((n_beta, act_T))
    pLvl_factor_series_batch = np.zeros((n_beta, act_T))
    AggInc_pol_series_batch = np.zeros((n_beta, act_T))
    AggInc_none_series_batch = np.zeros((n_beta, act_T))
    AggCons_pol_series_batch = np.zeros((n_beta, act_T))
    AggCons_none_series_batch = np.zeros((n_beta, act_T))

    # Pre-t0 SPIKE state-shift (β-shared because spike depends on rates, not β)
    macro_pn_t0 = int(EconomyMrkv_path_pn[0])
    if (macro_pn_t0 % 2 == 1):
        Un = float(getattr(agent_pol_0, 'Urate_normal', 0.045))
        Ur = float(getattr(agent_pol_0, 'Urate_recession', Un))
        if Ur > Un:
            spike_frac = (Ur - Un) / (1.0 - Un)
            # Apply per β (each has own dist5d)
            for b in range(n_beta):
                for j_b in range(J):
                    emp_mass = dist5d_batch[b, :, :, :, 0, j_b].copy()
                    dist5d_batch[b, :, :, :, 0, j_b] = emp_mass * (1.0 - spike_frac)
                    dist5d_batch[b, :, :, :, 1, j_b] += emp_mass * spike_frac

    for t in range(act_T):
        macro_pn = int(EconomyMrkv_path_pn[t])
        # β-shared per-period
        MA_pn = np.asarray(agent_pol_0.CondMrkvArrays[macro_pn], dtype=np.float64)
        joint_markov = compute_joint_markov(MA_pn, MA_b)
        base_idx_pn = macro_pn * J
        IncShk_pol_t = list(IncShk_pol_full[base_idx_pn:base_idx_pn + J])
        IncShk_none_t = list(IncShk_none_full[base_idx_pn:base_idx_pn + J])
        IncShk_b_t = list(IncShk_base_full[0:J])

        # β-dependent per-period: cFunc slicing
        cFuncs_pol_t_batch = [
            [cFuncs_pol_full_batch[b][base_idx_pn + j] for j in range(J)]
            for b in range(n_beta)
        ]
        cFuncs_none_t_batch = [
            [cFuncs_none_full_batch[b][base_idx_pn + j] for j in range(J)]
            for b in range(n_beta)
        ]
        cFuncs_b_t_batch = [
            [cFuncs_b_full_batch[b][0 + j] for j in range(J)]
            for b in range(n_beta)
        ]

        # Call batch kernel
        dist_next_batch, w_num_per_beta, agg_per_beta = _step_period_5d_batch(
            dist5d_batch, aGrid, joint_markov,
            cFuncs_pol_t_batch, cFuncs_none_t_batch, cFuncs_b_t_batch,
            IncShk_pol_t, IncShk_none_t, IncShk_b_t,
            Rfree, PermGroFac, Splurge, rho,
            Cratio_pol_series[t], Cratio_none_series[t],
            AggDemandFac_pol_series[t], AggDemandFac_none_series[t],
            TranShk_addition_pol_series[t], TranShk_addition_none_series[t],
            LivPrb_avg=LivPrb_avg,
            newborn_dist5d_diag_batch=newborn_dist5d_diag_batch,
        )

        for b in range(n_beta):
            scale_b = N_eff_per_beta[b] * E_pLvl_per_beta[b] * pLvl_factor_per_beta[b]
            welfare_num_series_batch[b, t] = w_num_per_beta[b] * scale_b
            AggInc_pol_series_batch[b, t] = agg_per_beta[b]['inc_pol'] * scale_b
            AggInc_none_series_batch[b, t] = agg_per_beta[b]['inc_none'] * scale_b
            AggCons_pol_series_batch[b, t] = agg_per_beta[b]['cons_pol'] * scale_b
            AggCons_none_series_batch[b, t] = agg_per_beta[b]['cons_none'] * scale_b
            pLvl_factor_series_batch[b, t] = pLvl_factor_per_beta[b]

        # pLvl_factor update per β
        for b in range(n_beta):
            marg_pol = dist5d_batch[b].sum(axis=(1, 2, 4))  # (A, J)
            state_fracs_pol = marg_pol.sum(axis=0)
            u_rec_t = 1.0 - state_fracs_pol[0]
            g_rec_t = effective_pLvl_growth(agent_pol_0, u_rec_t)
            pLvl_factor_per_beta[b] = ((1.0 - death_prob) * g_rec_t * pLvl_factor_per_beta[b]
                                       + (1.0 - (1.0 - death_prob) * g_base_pLvl))
        dist5d_batch = dist_next_batch

    return [
        {
            'welfare_num_series': welfare_num_series_batch[b],
            'pLvl_factor_series': pLvl_factor_series_batch[b],
            'AggInc_pol_series': AggInc_pol_series_batch[b],
            'AggInc_none_series': AggInc_none_series_batch[b],
            'AggCons_pol_series': AggCons_pol_series_batch[b],
            'AggCons_none_series': AggCons_none_series_batch[b],
        }
        for b in range(n_beta)
    ]
