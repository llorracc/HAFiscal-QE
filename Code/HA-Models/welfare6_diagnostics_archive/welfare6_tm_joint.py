"""
welfare6_tm_joint.py — Phase T.J of TM-a 4/6-state plan.

2D coupled-asset joint kernel for ui_rec / ui_rec_AD welfare.

Why this exists
---------------
The standard TM-a methods (bucket / percell / stratified) compute welfare
from MARGINAL asset distributions per scenario. For ui_rec, the welfare
integrand involves the JOINT distribution of (a^policy, a^none) under CRN
across scenarios — same agent, same Markov draws, but divergent asset
trajectories due to the policy itself. Marginal-only methods miss this and
under-estimate ui_rec welfare by ~35%.

This module tracks the joint 2D asset distribution explicitly:

    state = (a_p, a_n, j) — asset under policy, asset under no-policy, shared Markov state

and integrates welfare per cell. Evaluates BOTH anchor variants in one pass:
    - b2 (rec-anchor):    (u(c_p) - u(c_n)) / u'(c_n)
    - b3 (base-marginal): (u(c_p) - u(c_n)) / u'(c_b_marginal[j])

See conclusions_private/2026-05-13_TJ_joint_asset_kernel_design.md for
math derivation and removability notes.

Removability
------------
Self-contained module. To remove Phase T.J entirely:
1. Delete this file.
2. Delete the BEGIN/END PHASE T.J block in welfare6_tm.py.
"""
from __future__ import annotations

import numpy as np

# Tolerance for skipping near-zero distribution mass.
_DIST_EPS = 1e-15
# Tolerance for skipping near-zero Markov transition probability.
_TRANS_EPS = 1e-15


def _u(c_lvl, rho):
    """CRRA utility u(c) = c^(1-rho)/(1-rho). c may be array."""
    c_lvl = np.maximum(c_lvl, 1e-12)
    if abs(rho - 1.0) < 1e-12:
        return np.log(c_lvl)
    return (c_lvl ** (1.0 - rho)) / (1.0 - rho)


def _mu_inv(c_lvl, rho):
    """Inverse marginal utility 1/u'(c) = c^rho. c may be array."""
    c_lvl = np.maximum(c_lvl, 1e-12)
    return c_lvl ** rho


def _bilinear_distribute(values_p, values_n, weights, aGrid, target_dist):
    """
    Distribute mass from continuous (a_p, a_n) values onto a 2D asset grid
    via bilinear interpolation.

    Parameters
    ----------
    values_p : np.ndarray, shape (K,)
        Continuous a_p values.
    values_n : np.ndarray, shape (K,)
        Continuous a_n values.
    weights : np.ndarray, shape (K,)
        Mass to distribute at each (values_p[k], values_n[k]) point.
    aGrid : np.ndarray, shape (A,)
        1D asset grid (used for both axes).
    target_dist : np.ndarray, shape (A, A)
        2D distribution array to add to (modified in place).
    """
    A = len(aGrid)
    aMax = aGrid[-1]
    aMin = aGrid[0]
    # Clip to grid range. Off-grid mass is reflected back to nearest cell.
    vp = np.clip(values_p, aMin, aMax)
    vn = np.clip(values_n, aMin, aMax)

    # Locate each value's lower-bracket index in aGrid.
    ip_lo = np.searchsorted(aGrid, vp, side='right') - 1
    in_lo = np.searchsorted(aGrid, vn, side='right') - 1
    ip_lo = np.clip(ip_lo, 0, A - 2)
    in_lo = np.clip(in_lo, 0, A - 2)
    ip_hi = ip_lo + 1
    in_hi = in_lo + 1

    # Bilinear weights.
    wp_hi = (vp - aGrid[ip_lo]) / (aGrid[ip_hi] - aGrid[ip_lo])
    wp_lo = 1.0 - wp_hi
    wn_hi = (vn - aGrid[in_lo]) / (aGrid[in_hi] - aGrid[in_lo])
    wn_lo = 1.0 - wn_hi

    # Distribute mass to 4 corners. Use np.add.at for correct accumulation
    # when multiple K's land in the same cell.
    np.add.at(target_dist, (ip_lo, in_lo), weights * wp_lo * wn_lo)
    np.add.at(target_dist, (ip_lo, in_hi), weights * wp_lo * wn_hi)
    np.add.at(target_dist, (ip_hi, in_lo), weights * wp_hi * wn_lo)
    np.add.at(target_dist, (ip_hi, in_hi), weights * wp_hi * wn_hi)


def compute_joint_welfare_period(
    dist_joint, aGrid, j, MarkovArray,
    cFuncs_pol, cFuncs_none, IncShkDstn_pol, IncShkDstn_none,
    Rfree, PermGroFac, Splurge, CRRA,
    Cratio_pol=1.0, Cratio_none=1.0,
    AggDemandFac_pol=1.0, AggDemandFac_none=1.0,
    TranShk_addition_pol=None, TranShk_addition_none=None,
    c_b_marginal_per_j=None,
):
    """
    One period of joint kernel:
      1. From joint dist[a_p, a_n, j], compute next-period joint dist'.
      2. Compute per-period welfare numerator contribution (b2 and b3).

    Parameters
    ----------
    dist_joint : np.ndarray, shape (A, A, J)
        Joint distribution at start of period.
    aGrid : np.ndarray, shape (A,)
        Asset grid (shared for both axes).
    j : int
        (Unused argument retained for symmetry with other propagators —
        the kernel iterates over all source j internally.)
    MarkovArray : np.ndarray, shape (J, J)
        Per-period micro-Markov transition matrix.
    cFuncs_pol, cFuncs_none : list[callable] of length J
        Consumption functions per destination micro state.
    IncShkDstn_pol, IncShkDstn_none : list of HARK distribution objects, length J
        Income-shock distribution per destination micro state. Each has
        .atoms (shape (2, n_atoms)) with row 0 = psi, row 1 = xi, and .pmv.
    Rfree, PermGroFac : np.ndarray, shape (J,)
        Per-state risk-free rate and permanent income growth.
    Splurge, CRRA : float
    Cratio_pol, Cratio_none : float
    AggDemandFac_pol, AggDemandFac_none : float
    TranShk_addition_pol, TranShk_addition_none : np.ndarray, shape (J,) or None
    c_b_marginal_per_j : np.ndarray, shape (J,) or None
        Per-state marginal-base consumption (for b3 anchor). If None, b3 is
        computed using c_n as the anchor (= falls back to b2 for that anchor).

    Returns
    -------
    dist_joint_next : np.ndarray, shape (A, A, J)
    welfare_num_b2 : float
        Welfare numerator contribution this period under b2 anchor.
    welfare_num_b3 : float
        Welfare numerator contribution this period under b3 anchor.
    """
    A = len(aGrid)
    J = MarkovArray.shape[0]
    rho = float(CRRA)

    if TranShk_addition_pol is None:
        TranShk_addition_pol = np.zeros(J)
    if TranShk_addition_none is None:
        TranShk_addition_none = np.zeros(J)

    dist_joint_next = np.zeros((A, A, J), dtype=np.float64)
    welfare_num_b2 = 0.0
    welfare_num_b3 = 0.0

    # Iterate over source Markov state j.
    for j_src in range(J):
        d_src = dist_joint[:, :, j_src]
        if d_src.sum() <= _DIST_EPS:
            continue

        # Iterate over destination Markov state j'.
        for jp in range(J):
            trans = float(MarkovArray[j_src, jp])
            if trans < _TRANS_EPS:
                continue

            dstn_pol = IncShkDstn_pol[jp]
            dstn_none = IncShkDstn_none[jp]
            psi_p = np.asarray(dstn_pol.atoms[0], dtype=np.float64)
            xi_p = np.asarray(dstn_pol.atoms[1], dtype=np.float64)
            pmv_p = np.asarray(dstn_pol.pmv, dtype=np.float64)
            psi_n = np.asarray(dstn_none.atoms[0], dtype=np.float64)
            xi_n = np.asarray(dstn_none.atoms[1], dtype=np.float64)
            pmv_n = np.asarray(dstn_none.pmv, dtype=np.float64)

            # CRN assumption: shock atoms are paired across pol/none. We
            # require equal number of atoms in pol and none for the same
            # destination state. Verify and use shared psi (employment
            # status determines psi distribution; only xi may differ).
            if len(pmv_p) != len(pmv_n):
                raise RuntimeError(
                    f"Joint kernel requires same atom count for pol/none "
                    f"at destination state {jp}: got {len(pmv_p)} vs {len(pmv_n)}.")
            if not np.allclose(psi_p, psi_n) or not np.allclose(pmv_p, pmv_n):
                raise RuntimeError(
                    f"Joint kernel requires CRN-paired atoms (same psi, same "
                    f"pmv) for pol/none at destination state {jp}.")

            psi = psi_p
            pmv = pmv_p
            n_atoms = len(pmv)

            # For each shock atom (n_atoms total), compute m_next_pol/none
            # at every (a_p, a_n) cell in the source distribution.
            # For efficiency, iterate over atoms in an outer loop and
            # use 2D vectorization over (a_p, a_n) inside.
            for atom in range(n_atoms):
                psi_a = psi[atom]
                xi_p_a = xi_p[atom]
                xi_n_a = xi_n[atom]
                pmv_a = pmv[atom]
                if pmv_a < _TRANS_EPS:
                    continue

                # Effective transitory income (with AD factor + TranShk_addition).
                xi_eff_p = AggDemandFac_pol * xi_p_a + TranShk_addition_pol[jp]
                xi_eff_n = AggDemandFac_none * xi_n_a + TranShk_addition_none[jp]

                inv_pG = 1.0 / (psi_a * PermGroFac[jp])
                R_jp = Rfree[jp]

                # m_next per axis, shape (A,) for each.
                m_next_p_per_a = R_jp * aGrid * inv_pG + xi_eff_p
                m_next_n_per_a = R_jp * aGrid * inv_pG + xi_eff_n

                # cFunc evaluation per axis. cFunc(m, Cratio) returns c_star.
                Cratio_p_arr = np.full(A, Cratio_pol)
                Cratio_n_arr = np.full(A, Cratio_none)
                c_star_p_per_a = cFuncs_pol[jp](m_next_p_per_a, Cratio_p_arr)
                c_star_n_per_a = cFuncs_none[jp](m_next_n_per_a, Cratio_n_arr)

                # c_actual per axis (Splurge applied to scenario-specific xi_eff).
                c_actual_p_per_a = ((1.0 - Splurge) * c_star_p_per_a
                                    + Splurge * xi_eff_p)
                c_actual_n_per_a = ((1.0 - Splurge) * c_star_n_per_a
                                    + Splurge * xi_eff_n)

                # a_next per axis (for distribution propagation).
                a_next_p_per_a = m_next_p_per_a - c_actual_p_per_a
                a_next_n_per_a = m_next_n_per_a - c_actual_n_per_a

                # Broadcast to 2D grids (a_p, a_n).
                # a_next_p_2d[i, j] = a_next_p[i] (depends only on a_p)
                # a_next_n_2d[i, j] = a_next_n[j] (depends only on a_n)
                a_next_p_2d = np.broadcast_to(
                    a_next_p_per_a[:, None], (A, A)).ravel()
                a_next_n_2d = np.broadcast_to(
                    a_next_n_per_a[None, :], (A, A)).ravel()

                # Welfare integrand per cell — depends on (c_p_per_a_p,
                # c_n_per_a_n) since cFunc evaluation is per-axis.
                c_p_2d = np.broadcast_to(c_actual_p_per_a[:, None],
                                         (A, A))
                c_n_2d = np.broadcast_to(c_actual_n_per_a[None, :],
                                         (A, A))
                u_p_2d = _u(c_p_2d, rho)
                u_n_2d = _u(c_n_2d, rho)
                u_diff_2d = u_p_2d - u_n_2d

                # b2 anchor: divide by u'(c_n).
                mu_inv_n_2d = _mu_inv(c_n_2d, rho)
                integrand_b2_2d = u_diff_2d * mu_inv_n_2d

                # b3 anchor: divide by u'(c_b_marginal[jp]). If absent,
                # fall back to b2.
                if c_b_marginal_per_j is not None:
                    c_b = c_b_marginal_per_j[jp]
                    mu_inv_b = _mu_inv(np.array([c_b]), rho)[0]
                    integrand_b3_2d = u_diff_2d * mu_inv_b
                else:
                    integrand_b3_2d = integrand_b2_2d

                # Mass weight per (a_p, a_n) cell:
                # d_src[a_p, a_n] · trans · pmv_a
                weight_2d = d_src * trans * pmv_a
                weight_flat = weight_2d.ravel()

                # Accumulate welfare (no per-cell pLvl here; caller scales
                # by E_pLvl_t × N for the full numerator).
                welfare_num_b2 += float(np.sum(weight_2d * integrand_b2_2d))
                welfare_num_b3 += float(np.sum(weight_2d * integrand_b3_2d))

                # Distribute mass to the next-period joint distribution.
                _bilinear_distribute(
                    a_next_p_2d, a_next_n_2d, weight_flat,
                    aGrid, dist_joint_next[:, :, jp])

    return dist_joint_next, welfare_num_b2, welfare_num_b3


def _embed_marginal_base_c_per_j(base_dist_aJ, base_aGrid, base_cFuncs,
                                 base_IncShkDstn, Rfree, PermGroFac, Splurge,
                                 J):
    """
    Compute per-state expected base consumption c_b_marginal[j] from the
    marginal-base distribution. Used for b3 anchor.

    Approach: take the asset-mean per state from base_dist, evaluate base
    cFunc at the central shock atom, then take the splurge-adjusted c.
    """
    c_b_per_j = np.zeros(J)
    for j in range(J):
        d_j = base_dist_aJ[j]  # shape (A,)
        if d_j.sum() <= _DIST_EPS:
            c_b_per_j[j] = 1.0  # placeholder; unused
            continue
        a_mean = float(np.dot(d_j, base_aGrid) / d_j.sum())
        # Use central atom (median) of IncShkDstn[j].
        dstn = base_IncShkDstn[j]
        psi = np.asarray(dstn.atoms[0])
        xi = np.asarray(dstn.atoms[1])
        pmv = np.asarray(dstn.pmv)
        # Use expected shock for evaluation.
        psi_mean = float(np.dot(pmv, psi))
        xi_mean = float(np.dot(pmv, xi))
        m_eval = Rfree[j] * a_mean / (psi_mean * PermGroFac[j]) + xi_mean
        c_star = float(base_cFuncs[j](np.array([m_eval]), np.array([1.0]))[0])
        c_b_per_j[j] = (1.0 - Splurge) * c_star + Splurge * xi_mean
    return c_b_per_j


def _resolve_scenario_IncShkDstn(agent, shock_type):
    """Return the FULL scenario-specific IncShkDstn list.

    HAFiscal stores scenario-specific IncShkDstn as attributes on the agent:
      - 'base':            agent.IncShkDstn_base[0]   (length J,  steady-state)
      - 'recession':       agent.IncShkDstn_recession[0]   (length 2*(nep+1)*J)
      - 'recessionUI':     agent.IncShkDstn_recessionUI[0] (length 2*(nep+1)*J)
      - 'recessionCheck':  agent.IncShkDstn_recessionCheck[0]
      - 'recessionTaxCut': agent.IncShkDstn_recessionTaxCut[0]
      - 'Check':           agent.IncShkDstn_Check[0]  (or built per scenario)

    For any scenario whose income vector is macro-state-dependent, return
    the full list. For 'base' (no macro variation), tile the steady-state
    list to length 2*(nep+1)*J.

    Returns: list of HARK distribution objects, indexed by macro*J + micro.
    """
    if shock_type == 'base':
        # Tile steady-state across macro states for uniform indexing.
        ss = agent.IncShkDstn[0]  # length J
        # Length of recession-style list (if any other attr exists, use it).
        for attr in ('IncShkDstn_recession', 'IncShkDstn_base'):
            target_len = (
                len(getattr(agent, attr)[0]) if hasattr(agent, attr)
                else None
            )
            if target_len is not None:
                break
        if target_len is None:
            return ss
        if target_len % len(ss) == 0:
            return list(ss) * (target_len // len(ss))
        return ss
    attr_map = {
        'recession': 'IncShkDstn_recession',
        'recessionUI': 'IncShkDstn_recessionUI',
        'recessionCheck': 'IncShkDstn_recessionCheck',
        'recessionTaxCut': 'IncShkDstn_recessionTaxCut',
        'Check': 'IncShkDstn_Check',
        'UI': 'IncShkDstn_UI',
        'TaxCut': 'IncShkDstn_TaxCut',
    }
    attr = attr_map.get(shock_type)
    if attr is None or not hasattr(agent, attr):
        # Fallback to steady-state (warn? for diagnostic only).
        return agent.IncShkDstn[0]
    return getattr(agent, attr)[0]


def compute_joint_welfare(
    agent_pol, agent_none, agent_base, baseline_tm_data,
    EconomyMrkv_path, act_T,
    shock_type_pol='recessionUI', shock_type_none='recession',
    shock_type_base='base',
    AggDemandFac_pol_series=None, AggDemandFac_none_series=None,
    Cratio_pol_series=None, Cratio_none_series=None,
    TranShk_addition_pol_series=None, TranShk_addition_none_series=None,
):
    """
    Top-level entry. Returns per-period welfare numerator series for both
    b2 and b3 anchors, plus the per-period pLvl_factor for level scaling.

    Parameters
    ----------
    agent_pol, agent_none, agent_base : AggFiscalType
        Same cohort, three different solutions (pol = e.g. recessionUI,
        none = recession, base = baseline).
    baseline_tm_data : dict
        Output of compute_baseline_tm_data (or build_tm_agg_fiscal_a) —
        provides ergodic, dist_aGrid, E_pLvl, u_ergodic.
    EconomyMrkv_path : np.ndarray, shape (act_T,)
        Macro-Markov path that drives shock_type for both pol and none.
    act_T : int
        Number of simulation periods.
    AggDemandFac_*_series : np.ndarray, shape (act_T,) or None
        Per-period AD factor; defaults to 1.0 each period.
    Cratio_*_series : np.ndarray, shape (act_T,) or None
        Per-period Cratio; defaults to 1.0 each period.
    TranShk_addition_*_series : list of np.ndarray, shape (act_T, J) or None
        Per-period per-state TranShk addition; defaults to zeros.

    Returns
    -------
    dict with keys:
      'welfare_num_b2_series': np.ndarray, shape (act_T,)
      'welfare_num_b3_series': np.ndarray, shape (act_T,)
      'pLvl_factor_series': np.ndarray, shape (act_T,)
      'AggCons_pol_series', 'AggCons_none_series': for diagnostics
    """
    from income_process_sst import effective_pLvl_growth

    aGrid = baseline_tm_data['dist_aGrid']
    A = len(aGrid)
    J = int(agent_pol.num_base_MrkvStates)

    # Defaults.
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

    # Initial joint distribution: diagonal from base ergodic.
    # base_ergodic is shape (A*J,) with layout [j=0 a=0..A-1, j=1 a=0..A-1, ...]
    base_ergodic = np.asarray(baseline_tm_data['ergodic'], dtype=np.float64)
    base_dist_aJ = base_ergodic.reshape(J, A)  # [j, a]
    dist_joint = np.zeros((A, A, J), dtype=np.float64)
    for j in range(J):
        # Diagonal: dist_joint[a, a, j] = base_dist_aJ[j, a]
        np.fill_diagonal(dist_joint[:, :, j], base_dist_aJ[j, :])

    # Per-state marginal-base c (for b3 anchor).
    base_cFuncs = agent_base.solution[0].cFunc
    base_IncShkDstn = agent_base.IncShkDstn[0]
    Rfree_base = np.asarray(agent_base.Rfree[:J], dtype=np.float64)
    PermGroFac_base = np.asarray(agent_base.PermGroFac[0][:J], dtype=np.float64)
    c_b_marginal_per_j = _embed_marginal_base_c_per_j(
        base_dist_aJ, aGrid, base_cFuncs, base_IncShkDstn,
        Rfree_base, PermGroFac_base, float(agent_base.Splurge), J)

    # Solution refs for pol and none. Note: cFunc is shared across scenarios
    # (steady-state Bellman solution) — only the per-period IncShkDstn varies
    # by macro state.
    cFuncs_pol = agent_pol.solution[0].cFunc
    cFuncs_none = agent_none.solution[0].cFunc
    Rfree_pol = np.asarray(agent_pol.Rfree[:J], dtype=np.float64)
    PermGroFac_pol = np.asarray(agent_pol.PermGroFac[0][:J], dtype=np.float64)
    Splurge = float(agent_pol.Splurge)
    CRRA = float(agent_pol.CRRA)

    # Resolve scenario-specific full IncShkDstn lists (length 2*(nep+1)*J).
    IncShkDstn_pol_full = _resolve_scenario_IncShkDstn(agent_pol, shock_type_pol)
    IncShkDstn_none_full = _resolve_scenario_IncShkDstn(agent_none, shock_type_none)

    welfare_num_b2_series = np.zeros(act_T)
    welfare_num_b3_series = np.zeros(act_T)
    pLvl_factor_series = np.zeros(act_T)
    AggCons_pol_series = np.zeros(act_T)
    AggCons_none_series = np.zeros(act_T)

    # pLvl_factor evolution under shared Markov (drives level scaling).
    u_ergodic = baseline_tm_data.get('u_ergodic', 0.04)
    g_base_pLvl = effective_pLvl_growth(agent_pol, u_ergodic)
    pLvl_factor = 1.0
    E_pLvl = float(baseline_tm_data['E_pLvl'])
    AgentCount = int(getattr(agent_pol, 'AgentCount', 1))
    pop_rescale = float(getattr(agent_pol, 'pop_rescale_factor', 1.0))
    N_eff = AgentCount * pop_rescale

    for t in range(act_T):
        macro_t = int(EconomyMrkv_path[t])
        # Fetch the period's Markov sub-array for this macro state.
        # CondMrkvArrays is indexed by macro state.
        MarkovArray_t = np.asarray(
            agent_pol.CondMrkvArrays[macro_t], dtype=np.float64)

        # Per-period IncShkDstn lookup: indexed by macro_t * J + jp.
        # For the full scenario-specific list, slice out the J entries
        # corresponding to this macro state.
        base_idx = macro_t * J
        if base_idx + J <= len(IncShkDstn_pol_full):
            IncShkDstn_pol_t = list(IncShkDstn_pol_full[base_idx:base_idx + J])
        else:
            # Fallback to steady-state if list is shorter (e.g. base scenario).
            IncShkDstn_pol_t = list(IncShkDstn_pol_full[:J])
        if base_idx + J <= len(IncShkDstn_none_full):
            IncShkDstn_none_t = list(IncShkDstn_none_full[base_idx:base_idx + J])
        else:
            IncShkDstn_none_t = list(IncShkDstn_none_full[:J])

        # Per-period welfare contribution.
        dist_next, w2, w3 = compute_joint_welfare_period(
            dist_joint, aGrid, j=None, MarkovArray=MarkovArray_t,
            cFuncs_pol=cFuncs_pol, cFuncs_none=cFuncs_none,
            IncShkDstn_pol=IncShkDstn_pol_t, IncShkDstn_none=IncShkDstn_none_t,
            Rfree=Rfree_pol, PermGroFac=PermGroFac_pol,
            Splurge=Splurge, CRRA=CRRA,
            Cratio_pol=Cratio_pol_series[t],
            Cratio_none=Cratio_none_series[t],
            AggDemandFac_pol=AggDemandFac_pol_series[t],
            AggDemandFac_none=AggDemandFac_none_series[t],
            TranShk_addition_pol=TranShk_addition_pol_series[t],
            TranShk_addition_none=TranShk_addition_none_series[t],
            c_b_marginal_per_j=c_b_marginal_per_j,
        )

        # Scale welfare contribution by N_eff × E_pLvl × pLvl_factor.
        welfare_num_b2_series[t] = w2 * N_eff * E_pLvl * pLvl_factor
        welfare_num_b3_series[t] = w3 * N_eff * E_pLvl * pLvl_factor
        pLvl_factor_series[t] = pLvl_factor

        # Update pLvl_factor for next period (using base growth — both
        # scenarios share Markov draws so growth is the same).
        # (For full fidelity to scenario-specific pLvl growth, would need
        # to track macro_t-specific u rate. Phase 1 uses base growth.)
        pLvl_factor *= g_base_pLvl

        # Diagnostics: aggregate consumption (marginal).
        # Sum c_p over (a_p, a_n, j_src) → marginal of c_p over a_p.
        # (Approximate; full accuracy would track via 2D dist; for
        # diagnostic only we use the marginal sum.)
        # Skipped for first cut — focus is on welfare numerator.
        AggCons_pol_series[t] = 0.0
        AggCons_none_series[t] = 0.0

        dist_joint = dist_next

    return {
        'welfare_num_b2_series': welfare_num_b2_series,
        'welfare_num_b3_series': welfare_num_b3_series,
        'pLvl_factor_series': pLvl_factor_series,
        'AggCons_pol_series': AggCons_pol_series,
        'AggCons_none_series': AggCons_none_series,
    }
