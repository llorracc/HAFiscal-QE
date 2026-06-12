"""
welfare6_tm_joint5d.py — Phase A2 of TM-a 5/12 plan.

5D coupled-state TM-a kernel for ui_rec / ui_rec_AD welfare. Asymptotically
correct (no anchor approximations, no marginal-only assumptions). Triple-check
on MC welfare measurement.

State: (a_p, a_n, a_b, j_p, j_b) where:
  a_p, a_n, a_b = asset under pol/none/base scenarios
  j_p           = micro Markov state shared by pol & none (CRN, same recession Markov array)
  j_b           = micro Markov state under base (no-recession Markov array — CAN DIFFER from j_p)

See `BUGS_private/HAFiscal_splurge_budget_inconsistency/math_cheatsheet_tm_a_5D_welfare.md`
for math derivation. Equation labels (eq:5D-state) ... (eq:5D-cell-formula)
appear as comments throughout the code.

NOT a production method. Triple-check only. (2026-06-10: additionally
designated the TaxCut-only TM backup — taxcut_rec converged, -0.14% vs MC;
see conclusions_private/2026-06-10_welfare_method_unified_MC.md.)

Removability
------------
Self-contained module. To remove: delete this file. The driver script
(welfare6_tm_joint5d_test.py) is also self-contained.
"""
from __future__ import annotations

import numpy as np

_DIST_EPS = 1e-15
_TRANS_EPS = 1e-15


def _u(c, rho):
    c = np.maximum(c, 1e-12)
    if abs(rho - 1.0) < 1e-12:
        return np.log(c)
    return (c ** (1.0 - rho)) / (1.0 - rho)


def _mu_inv(c, rho):
    c = np.maximum(c, 1e-12)
    return c ** rho


def compute_joint_markov(MA_pn, MA_b):
    """
    `(eq:5D-joint-Markov)` — joint distribution of next-period (j_pn', j_b')
    under shared uniform draw atom across scenarios.

    For two CDFs F_pn (row j_pn_src) and F_b (row j_b_src), each shared
    [0,1]-uniform draw u maps to (F_pn^{-1}(u), F_b^{-1}(u)). The joint
    probability of landing in (k_pn, k_b) is the LENGTH OF OVERLAP between
    intervals [F_pn(k_pn-1), F_pn(k_pn)] and [F_b(k_b-1), F_b(k_b)].

    Returns
    -------
    joint : np.ndarray, shape (J, J, J, J)
        joint[j_pn_src, j_b_src, k_pn, k_b] = Pr(k_pn, k_b | j_pn_src, j_b_src)
    """
    J = MA_pn.shape[0]
    F_pn = np.cumsum(MA_pn, axis=1)  # shape (J, J)
    F_b = np.cumsum(MA_b, axis=1)
    # F_pn[j, k] = sum_{k' <= k} P_pn[j, k']; the right edge of bucket k.
    # Left edge of bucket k = F_pn[j, k-1] (or 0 for k=0).
    F_pn_left = np.concatenate(
        [np.zeros((J, 1)), F_pn[:, :-1]], axis=1)
    F_b_left = np.concatenate(
        [np.zeros((J, 1)), F_b[:, :-1]], axis=1)

    joint = np.zeros((J, J, J, J), dtype=np.float64)
    for j_pn_src in range(J):
        for j_b_src in range(J):
            for k_pn in range(J):
                a, b = F_pn_left[j_pn_src, k_pn], F_pn[j_pn_src, k_pn]
                for k_b in range(J):
                    c, d = F_b_left[j_b_src, k_b], F_b[j_b_src, k_b]
                    overlap = max(0.0, min(b, d) - max(a, c))
                    joint[j_pn_src, j_b_src, k_pn, k_b] = overlap
    return joint


def _resolve_scenario_IncShkDstn(agent, shock_type):
    """Return scenario-specific full IncShkDstn list (length 2*(nep+1)*J).
    For 'base', tile steady-state across macro states for uniform indexing.
    """
    if shock_type == 'base':
        ss = agent.IncShkDstn[0]
        for attr in ('IncShkDstn_recession', 'IncShkDstn_base'):
            if hasattr(agent, attr):
                target_len = len(getattr(agent, attr)[0])
                if target_len % len(ss) == 0:
                    return list(ss) * (target_len // len(ss))
        return ss
    attr_map = {
        'recession': 'IncShkDstn_recession',
        'recessionUI': 'IncShkDstn_recessionUI',
        'recessionCheck': 'IncShkDstn_recessionCheck',
        'recessionTaxCut': 'IncShkDstn_recessionTaxCut',
    }
    attr = attr_map.get(shock_type)
    if attr is not None and hasattr(agent, attr):
        return getattr(agent, attr)[0]
    return agent.IncShkDstn[0]


def _3d_bilinear_distribute(values_p, values_n, values_b, weights, aGrid, target_dist_5d, j_pn, j_b):
    """
    Distribute mass at continuous (a_p, a_n, a_b) onto a 3D grid.

    DIAGONAL-PRESERVING (fix #9): when a_p == a_n == a_b (= no CRN
    divergence under shared shocks), distribute as 1D-bilinear along
    the diagonal direction. ONLY off-diagonal cells where actual
    divergence is present get standard 3D-bilinear.

    Standard 3D-bilinear spreads diagonal-source mass into 8 corners
    including off-diagonal ones — for source on diagonal at (a, a, a)
    with w_lo = w_hi = 0.5, only 25% stays on-diagonal, 75% goes
    off-diagonal as a numerical artifact. This artifact gives spurious
    welfare contributions from c_p(a_p) ≠ c_n(a_n) at cells where
    under CRN c_p should equal c_n.

    For points NOT on the diagonal (a_p ≠ a_n or a_n ≠ a_b), use
    standard 3D-bilinear (= correct distribution of off-diagonal mass).

    `(eq:5D-asset-projection)`

    target_dist_5d[a_p_idx, a_n_idx, a_b_idx, j_pn, j_b] gets accumulated.
    """
    A = len(aGrid)
    aMin = aGrid[0]
    aMax = aGrid[-1]
    vp = np.clip(values_p, aMin, aMax)
    vn = np.clip(values_n, aMin, aMax)
    vb = np.clip(values_b, aMin, aMax)

    target_slice = target_dist_5d[:, :, :, j_pn, j_b]

    # Fix #9: separate diagonal points from off-diagonal points.
    # Tolerance: relative diff < 1e-12 → treat as on-diagonal.
    diag_tol = 1e-12
    is_diag = (np.abs(vp - vn) < diag_tol) & (np.abs(vn - vb) < diag_tol)

    # On-diagonal: 1D bilinear at the shared a value.
    if is_diag.any():
        v_diag = vp[is_diag]  # = vn = vb
        w_diag = weights[is_diag]
        i_lo = np.searchsorted(aGrid, v_diag, side='right') - 1
        i_lo = np.clip(i_lo, 0, A - 2)
        i_hi = i_lo + 1
        w_hi = (v_diag - aGrid[i_lo]) / (aGrid[i_hi] - aGrid[i_lo])
        w_lo = 1.0 - w_hi
        # Diagonal cells: (i_lo, i_lo, i_lo) and (i_hi, i_hi, i_hi)
        np.add.at(target_slice, (i_lo, i_lo, i_lo), w_diag * w_lo)
        np.add.at(target_slice, (i_hi, i_hi, i_hi), w_diag * w_hi)

    # Off-diagonal: standard 3D-bilinear (8 corners).
    if (~is_diag).any():
        vp_off = vp[~is_diag]
        vn_off = vn[~is_diag]
        vb_off = vb[~is_diag]
        w_off = weights[~is_diag]
        ip_lo = np.searchsorted(aGrid, vp_off, side='right') - 1
        in_lo = np.searchsorted(aGrid, vn_off, side='right') - 1
        ib_lo = np.searchsorted(aGrid, vb_off, side='right') - 1
        ip_lo = np.clip(ip_lo, 0, A - 2)
        in_lo = np.clip(in_lo, 0, A - 2)
        ib_lo = np.clip(ib_lo, 0, A - 2)
        ip_hi = ip_lo + 1
        in_hi = in_lo + 1
        ib_hi = ib_lo + 1

        wp_hi = (vp_off - aGrid[ip_lo]) / (aGrid[ip_hi] - aGrid[ip_lo])
        wp_lo = 1.0 - wp_hi
        wn_hi = (vn_off - aGrid[in_lo]) / (aGrid[in_hi] - aGrid[in_lo])
        wn_lo = 1.0 - wn_hi
        wb_hi = (vb_off - aGrid[ib_lo]) / (aGrid[ib_hi] - aGrid[ib_lo])
        wb_lo = 1.0 - wb_hi

        for dp, wp_d in [(0, wp_lo), (1, wp_hi)]:
            ip = ip_lo if dp == 0 else ip_hi
            for dn, wn_d in [(0, wn_lo), (1, wn_hi)]:
                inn = in_lo if dn == 0 else in_hi
                for db, wb_d in [(0, wb_lo), (1, wb_hi)]:
                    ib = ib_lo if db == 0 else ib_hi
                    np.add.at(target_slice, (ip, inn, ib),
                              w_off * wp_d * wn_d * wb_d)


def compute_joint_welfare5d(
    agent_pol, agent_none, agent_base, baseline_tm_data,
    EconomyMrkv_path_pn, act_T,
    shock_type_pol='recessionUI',
    shock_type_none='recession',
    AggDemandFac_pol_series=None, AggDemandFac_none_series=None,
    Cratio_pol_series=None, Cratio_none_series=None,
    TranShk_addition_pol_series=None, TranShk_addition_none_series=None,
    initial_aJ_dist=None,
    verbose=False,
):
    """
    Top-level entry. Returns per-period welfare numerator series.
    `(eq:5D-aggregation)` and `(eq:5D-cell-formula)`.

    `EconomyMrkv_path_pn` is the macro path for pol & none (shared because
    both are recession scenarios with same dynamics). Base scenario macro
    path is implicitly all-0 (no recession).
    """
    from income_process_sst import effective_pLvl_growth
    from tm_methods import _effective_LivPrb

    aGrid = baseline_tm_data['dist_aGrid']
    A = len(aGrid)
    J = int(agent_pol.num_base_MrkvStates)

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

    # `(eq:5D-init)` — diagonal in all three asset axes AND j_p = j_b.
    # Initial dist = base ergodic (steady-state under base scenario, includes
    # accumulated savings of all surviving cohorts).
    # initial_aJ_dist (opt-in): per-pLvl-bucket CONDITIONAL (a,j) init for the
    # conditional-init fix (closes the (a|pLvl) factorization). Default None = the
    # marginal (a,j) ergodic (original behavior).
    if initial_aJ_dist is not None:
        base_dist_aJ = np.asarray(initial_aJ_dist, dtype=np.float64).reshape(J, A)
    else:
        base_dist_aJ = np.asarray(baseline_tm_data['ergodic'], dtype=np.float64).reshape(J, A)
    dist5d = np.zeros((A, A, A, J, J), dtype=np.float64)
    for j in range(J):
        for a_idx in range(A):
            dist5d[a_idx, a_idx, a_idx, j, j] = base_dist_aJ[j, a_idx]

    # Newborn distribution: build below after MA_b is defined.
    if verbose:
        print(f"  [5D init] dist5d shape={dist5d.shape}, total mass={dist5d.sum():.6f}")

    # LivPrb (per-state survival prob, with T_age effective adjustment).
    # Use mean across J states for the per-period death rate (matches the
    # `delta_eff = 1.0 - np.mean(_LivPrb_eff)` pattern in propagate_experiment_tm_a).
    LivPrb_arr_raw = np.asarray(agent_pol.LivPrb[0][:J], dtype=np.float64)
    T_age = getattr(agent_pol, 'T_age', None)
    LivPrb_eff = _effective_LivPrb(LivPrb_arr_raw, T_age)
    LivPrb_avg = float(np.mean(LivPrb_eff))
    death_prob = 1.0 - LivPrb_avg
    if verbose:
        print(f"  [5D mortality] LivPrb_eff={LivPrb_eff}, avg={LivPrb_avg:.6f}, "
              f"death_prob/period={death_prob:.6f}")

    # Solution refs. cFunc is the FULL agent solution (length 2*(nep+1)*J,
    # ~132 entries), indexed by combined state = macro*J + j. cFuncs vary
    # by macro state because the Bellman is solved jointly over (macro, j).
    # Per-macro slicing is done in the per-period inner loop below.
    # FIX #11 (BUG-045): pol and none scenarios have DIFFERENT cFuncs because
    # their value functions differ — pol agent at u3Q expects UI extension
    # in future, so consumes more today than none at same m. Previously,
    # cFuncs_full was loaded from agent_pol.solution and used for BOTH c_p
    # AND c_n, making u_diff zero whenever m_p == m_n. This MISSED the welfare
    # contribution from cFunc divergence (= the dominant welfare channel).
    cFuncs_pol_full = agent_pol.solution[0].cFunc
    cFuncs_none_full = agent_none.solution[0].cFunc
    cFuncs_b_full = agent_base.solution[0].cFunc
    Rfree = np.asarray(agent_pol.Rfree[:J], dtype=np.float64)
    PermGroFac = np.asarray(agent_pol.PermGroFac[0][:J], dtype=np.float64)
    Splurge = float(agent_pol.Splurge)
    CRRA = float(agent_pol.CRRA)
    rho = CRRA

    IncShk_pol_full = _resolve_scenario_IncShkDstn(agent_pol, shock_type_pol)
    IncShk_none_full = _resolve_scenario_IncShkDstn(agent_none, shock_type_none)
    IncShk_base_full = _resolve_scenario_IncShkDstn(agent_base, 'base')

    # Markov arrays — base always uses macro=0 (no recession).
    MA_b = np.asarray(agent_base.CondMrkvArrays[0], dtype=np.float64)

    # Newborn distribution (5D-style v2 = matches existing TM-a's
    # _make_newborn_dist convention):
    # Newborns enter at m = xi (income shock at first period) and
    # immediately make consumption decision. End-of-period asset:
    #   a_init = max(0, m_init - c_actual) = max(0, xi - cFunc(xi))
    # For low xi (constrained), a_init ≈ 0. For high xi (unconstrained),
    # a_init > 0.
    # Q-reweight (fix #6 v2): xi pmv reweighted by psi/E[psi] under
    # Harmenberg neutral measure (consistent with cell-level Q in #6).
    # Diagonal across all 3 asset axes AND j_p=j_b at distribution time.
    from tm_methods import _solve_markov_ergodic
    markov_erg_base = _solve_markov_ergodic(MA_b)  # shape (J,)
    base_idx_macro0 = 0  # base scenario macro=0
    cFuncs_b_macro0 = [cFuncs_b_full[base_idx_macro0 + j] for j in range(J)]
    # No analogous newborn cFunc for pol/none because newborns enter under
    # base distribution; only their post-newborn evolution diverges by scenario.
    IncShk_b_macro0 = list(IncShk_base_full[0:J])

    newborn_dist5d_diag = np.zeros((A, A, A, J, J), dtype=np.float64)
    for j in range(J):
        if markov_erg_base[j] < _DIST_EPS:
            continue
        dstn_j = IncShk_b_macro0[j]
        psi_j = np.asarray(dstn_j.atoms[0])
        xi_j = np.asarray(dstn_j.atoms[1])
        pmv_raw_j = np.asarray(dstn_j.pmv)
        # Q-reweight pmv by psi/E[psi]
        E_psi_j = float(np.dot(pmv_raw_j, psi_j))
        pmv_j = pmv_raw_j * psi_j / max(E_psi_j, 1e-12)
        for atom_idx, (xi_val, pmv_val) in enumerate(zip(xi_j, pmv_j)):
            if pmv_val < _DIST_EPS:
                continue
            # Newborn: m = xi (no assets); c = cFunc(xi); a = m - c
            m_init = float(xi_val)
            c_star = float(cFuncs_b_macro0[j](np.array([m_init]), np.array([1.0]))[0])
            c_actual = (1.0 - Splurge) * c_star + Splurge * m_init
            a_init = max(0.0, m_init - c_actual)
            # Bilinear placement on aGrid (1D)
            a_init_clip = max(aGrid[0], min(aGrid[-1], a_init))
            i_lo = np.searchsorted(aGrid, a_init_clip, side='right') - 1
            i_lo = max(0, min(A - 2, int(i_lo)))
            i_hi = i_lo + 1
            w_hi = (a_init_clip - aGrid[i_lo]) / max(aGrid[i_hi] - aGrid[i_lo], 1e-12)
            w_lo = 1.0 - w_hi
            mass_atom = markov_erg_base[j] * pmv_val
            # Diagonal: same a-cell for all 3 axes, same j for j_p=j_b
            newborn_dist5d_diag[i_lo, i_lo, i_lo, j, j] += mass_atom * w_lo
            newborn_dist5d_diag[i_hi, i_hi, i_hi, j, j] += mass_atom * w_hi
    # Normalize (should sum to ~1.0 already, but make exact)
    nb_total = newborn_dist5d_diag.sum()
    if nb_total > _DIST_EPS:
        newborn_dist5d_diag /= nb_total
    if verbose:
        print(f"  [5D newborn v2] markov_erg_base={markov_erg_base}")
        # Show how much mass is NOT at a=0 (= newborns who saved some)
        nb_at_a0 = newborn_dist5d_diag[0, 0, 0, :, :].sum()
        print(f"  [5D newborn v2] mass at a=0: {nb_at_a0:.4f}, mass at a>0: {1-nb_at_a0:.4f}")

    # pLvl scaling.
    u_ergodic = baseline_tm_data.get('u_ergodic', 0.04)
    g_base_pLvl = effective_pLvl_growth(agent_pol, u_ergodic)
    pLvl_factor = 1.0
    E_pLvl = float(baseline_tm_data['E_pLvl'])
    AgentCount = int(getattr(agent_pol, 'AgentCount', 1))
    pop_rescale = float(getattr(agent_pol, 'pop_rescale_factor', 1.0))
    N_eff = AgentCount * pop_rescale

    welfare_num_series = np.zeros(act_T)
    pLvl_factor_series = np.zeros(act_T)
    # FIX #12: compute internal AddInc/AddCons for consistent scaling
    AggInc_pol_series = np.zeros(act_T)
    AggInc_none_series = np.zeros(act_T)
    AggCons_pol_series = np.zeros(act_T)
    AggCons_none_series = np.zeros(act_T)

    # FIX #10 (BUG-044): Apply unemployment SPIKE as STATE SHIFT before
    # the Markov transition, not as a Markov row blend. The blend approximation
    # is correct for MARGINAL distributions but BREAKS the joint distribution
    # because it conflates "spike + Markov" into a single Markov step. In MC,
    # spike applies a STATE shift (e → u1Q for ~5.5% of emp agents in pol axis
    # only), THEN the joint Markov fires from the post-spike state. The mass
    # that should land at MIXED (u2Q-pol, emp-base) at t=0 (= post-spike
    # spiked agent advances u1Q→u2Q in pol, base stays emp) instead lands at
    # (u1Q-pol, emp-base) under the blend approximation, MISSING the welfare
    # contribution from the deeper unemp-pol-vs-emp-base mismatch.
    macro_pn_t0 = int(EconomyMrkv_path_pn[0])
    if (macro_pn_t0 % 2 == 1):  # recession at t=0
        Un = float(getattr(agent_pol, 'Urate_normal', 0.045))
        Ur = float(getattr(agent_pol, 'Urate_recession', Un))
        if Ur > Un:
            spike_frac = (Ur - Un) / (1.0 - Un)
            # State-shift on pol-axis only: move spike_frac of mass from
            # (j_p=0, j_b=*) to (j_p=1, j_b=*). This creates MIXED cells
            # (j_p=u1Q, j_b=emp) for spiked-pol-base-stayed-emp agents.
            # Apply BEFORE entering the t=0 step.
            for j_b in range(J):
                emp_mass = dist5d[:, :, :, 0, j_b].copy()
                dist5d[:, :, :, 0, j_b] = emp_mass * (1.0 - spike_frac)
                dist5d[:, :, :, 1, j_b] += emp_mass * spike_frac
            if verbose:
                print(f"  [5D pre-t0 SPIKE state-shift] Un={Un}, Ur={Ur}, "
                      f"spike_frac={spike_frac:.4f}")
                # Print post-spike (j_p, j_b) marginal for diagnostic
                jj_marg_post = dist5d.sum(axis=(0, 1, 2))
                for (jp, jb) in [(0, 0), (1, 0), (1, 1), (0, 1)]:
                    m = float(jj_marg_post[jp, jb])
                    if m > 1e-8:
                        print(f"    [post-spike] (j_p={jp}, j_b={jb}) mass={m:.6f}")

    for t in range(act_T):
        macro_pn = int(EconomyMrkv_path_pn[t])
        # `(eq:5D-update-Markov)` — joint Markov per shared u-draw.
        # NOTE (FIX #10): No longer blend spike into MA_pn[0,:]; spike was
        # applied as state shift to dist5d above, before the t=0 step.
        MA_pn = np.asarray(agent_pol.CondMrkvArrays[macro_pn], dtype=np.float64)

        joint_markov = compute_joint_markov(MA_pn, MA_b)  # (J, J, J, J)

        # Per-period IncShkDstn AND cFunc lookup — `(eq:5D-update-shocks)`.
        # cFuncs are indexed by combined macro*J + j to match the Bellman
        # solution's macro-aware structure.
        base_idx_pn = macro_pn * J
        IncShk_pol_t = list(IncShk_pol_full[base_idx_pn:base_idx_pn + J])
        IncShk_none_t = list(IncShk_none_full[base_idx_pn:base_idx_pn + J])
        # Base always macro=0.
        IncShk_b_t = list(IncShk_base_full[0:J])
        # Per-macro cFunc slicing (BUG-23-style fix on cFunc indexing).
        # FIX #11 (BUG-045): use scenario-specific cFuncs.
        cFuncs_pol_t = [cFuncs_pol_full[base_idx_pn + j] for j in range(J)]
        cFuncs_none_t = [cFuncs_none_full[base_idx_pn + j] for j in range(J)]
        cFuncs_b_t = [cFuncs_b_full[0 + j] for j in range(J)]  # base macro=0

        # Per-period welfare contribution + mortality (in _step_period_5d).
        dist_next, w_num, agg = _step_period_5d(
            dist5d, aGrid, joint_markov,
            cFuncs_pol_t, cFuncs_none_t, cFuncs_b_t,
            IncShk_pol_t, IncShk_none_t, IncShk_b_t,
            Rfree, PermGroFac, Splurge, rho,
            Cratio_pol_series[t], Cratio_none_series[t],
            AggDemandFac_pol_series[t], AggDemandFac_none_series[t],
            TranShk_addition_pol_series[t], TranShk_addition_none_series[t],
            LivPrb_avg=LivPrb_avg,
            newborn_dist5d_diag=newborn_dist5d_diag,
        )

        scale = N_eff * E_pLvl * pLvl_factor
        welfare_num_series[t] = w_num * scale
        AggInc_pol_series[t] = agg['inc_pol'] * scale
        AggInc_none_series[t] = agg['inc_none'] * scale
        AggCons_pol_series[t] = agg['cons_pol'] * scale
        AggCons_none_series[t] = agg['cons_none'] * scale
        pLvl_factor_series[t] = pLvl_factor

        # `(eq:5D-pLvl-recurrence)` mirror tm_methods.py:5613-5616.
        # Survivors grow by g_rec_t (state-dependent unemployment-aware growth),
        # newborns enter at pLvl=1 with mass (1 - LivPrb_avg). The constant
        # `(1 - LivPrb_avg * g_base_pLvl)` term keeps the pLvl_factor bounded
        # (vs the simple `*= g_base` which grows unboundedly).
        # Compute per-period u_rate from current pol-axis state fractions
        # to get state-dependent growth.
        marg_pol = dist5d.sum(axis=(1, 2, 4))  # (A, J)
        state_fracs_pol = marg_pol.sum(axis=0)  # (J,)
        u_rec_t = 1.0 - state_fracs_pol[0]  # employed = j=0
        g_rec_t = effective_pLvl_growth(agent_pol, u_rec_t)
        pLvl_factor = ((1.0 - death_prob) * g_rec_t * pLvl_factor
                       + (1.0 - (1.0 - death_prob) * g_base_pLvl))
        dist5d = dist_next

        if verbose and t < 8:
            # Marginal (j_p, j_b) of dist5d for diagnostic
            jj_marg = dist5d.sum(axis=(0, 1, 2))  # (J, J)
            jj_diag_mass = float(np.trace(jj_marg))
            jj_off_mass = float(jj_marg.sum() - jj_diag_mass)
            print(f"  [5D t={t}] macro_pn={macro_pn}, dist_mass={dist5d.sum():.6f}, "
                  f"pLvl_factor={pLvl_factor:.6f}, w_num_raw={w_num:.6e}, "
                  f"scaled={welfare_num_series[t]:.6e}")
            print(f"    [5D t={t}] (j_p,j_b) diag_mass={jj_diag_mass:.4f}, "
                  f"off_mass={jj_off_mass:.4f}")
            # Per-cell mean c_p, c_n, c_b for cells of interest (MIXED + diag)
            cells_of_interest = [(0,0), (1,1), (2,2), (3,3),
                                 (2,0), (3,0), (4,0), (5,0)]
            per_cell = agg.get('per_cell', {})
            print(f"    [5D t={t}] per-cell stats (DESTINATION cells, post-Markov):")
            print(f"    {'cell':<15} {'mass%':>8} {'mean_cp':>9} {'mean_cn':>9} {'mean_cb':>9} {'sum_w':>10}")
            for jp, jb in cells_of_interest:
                pc = per_cell.get((jp, jb), None)
                if pc is None or pc['mass'] < 1e-8:
                    continue
                mp_norm = pc['sum_cp'] / pc['mass']
                mn_norm = pc['sum_cn'] / pc['mass']
                mb_norm = pc['sum_cb'] / pc['mass']
                # Convert norm to LEVEL by multiplying by E_pLvl × pLvl_factor
                scale_pLvl = E_pLvl * pLvl_factor
                print(f"    ({jp},{jb}){'':>5} {pc['mass']*100:>8.3f} {mp_norm*scale_pLvl:>9.4f} {mn_norm*scale_pLvl:>9.4f} {mb_norm*scale_pLvl:>9.4f} {pc['sum_w']:>10.2e}")

    return {
        'welfare_num_series': welfare_num_series,
        'pLvl_factor_series': pLvl_factor_series,
        'AggInc_pol_series': AggInc_pol_series,
        'AggInc_none_series': AggInc_none_series,
        'AggCons_pol_series': AggCons_pol_series,
        'AggCons_none_series': AggCons_none_series,
    }


def _step_period_5d(
    dist5d, aGrid, joint_markov,
    cFuncs_pol, cFuncs_none, cFuncs_b,
    IncShk_pol_t, IncShk_none_t, IncShk_b_t,
    Rfree, PermGroFac, Splurge, rho,
    Cratio_pol, Cratio_none,
    AggDemandFac_pol, AggDemandFac_none,
    TranShk_addition_pol, TranShk_addition_none,
    LivPrb_avg=1.0, newborn_dist5d_diag=None,
):
    """
    One period of the 5D kernel. Iterates source (j_pn_src, j_b_src) and
    destination (j_pn_dst, j_b_dst), and integrates over shock atoms.

    Implements `(eq:5D-asset-update)`, `(eq:5D-welfare-integrand)`,
    `(eq:5D-aggregation)` per period.
    """
    A = len(aGrid)
    J = joint_markov.shape[0]
    dist5d_next = np.zeros_like(dist5d)
    welfare_num = 0.0
    # FIX #12: aggregate income/consumption per period (consistent scaling
    # with welfare_num for clean ui_rec computation).
    agg_inc_pol = 0.0
    agg_inc_none = 0.0
    agg_cons_pol = 0.0
    agg_cons_none = 0.0
    # DIAG #13: per-cell mean c_p, c_n, c_b and welfare contribution
    # Indexed by (j_pn_dst, j_b_dst), each storing
    # weighted sum and total mass for later mean computation.
    per_cell = {}  # (jp, jb) -> {'mass', 'sum_cp', 'sum_cn', 'sum_cb', 'sum_w'}

    # Iterate over source (j_pn, j_b).
    for j_pn_src in range(J):
        for j_b_src in range(J):
            d_src = dist5d[:, :, :, j_pn_src, j_b_src]  # (A, A, A)
            mass_total = d_src.sum()
            if mass_total <= _DIST_EPS:
                continue

            # Iterate over destination (j_pn_dst, j_b_dst).
            for j_pn_dst in range(J):
                for j_b_dst in range(J):
                    p_jj = joint_markov[j_pn_src, j_b_src, j_pn_dst, j_b_dst]
                    if p_jj < _TRANS_EPS:
                        continue

                    # Per-scenario IncShkDstn at destination state.
                    dstn_p = IncShk_pol_t[j_pn_dst]
                    dstn_n = IncShk_none_t[j_pn_dst]  # j_n = j_pn (shared)
                    dstn_b = IncShk_b_t[j_b_dst]

                    psi = np.asarray(dstn_p.atoms[0])
                    xi_p = np.asarray(dstn_p.atoms[1])
                    xi_n = np.asarray(dstn_n.atoms[1])
                    pmv_raw = np.asarray(dstn_p.pmv)
                    psi_b = np.asarray(dstn_b.atoms[0])
                    xi_b = np.asarray(dstn_b.atoms[1])
                    pmv_b_raw = np.asarray(dstn_b.pmv)

                    # `(eq:Q-reweight)` from math_cheatsheet_tm_a_p_vs_q.md +
                    # `(eq:5D-aggregation)` second paragraph: apply Harmenberg
                    # neutral measure (Q) reweighting to each scenario's
                    # IncShkDstn pmv: pmv_q = pmv * psi / E[psi]. Under Q,
                    # the cross-section satisfies c_norm ⊥ p, so summing the
                    # normalized integrand over the Q-cross-section and
                    # multiplying by E_P[p] gives the correct welfare
                    # E_P[p · g(c_norm)] (per Harmenberg).
                    E_psi_p = float(np.dot(pmv_raw, psi))
                    pmv = pmv_raw * psi / max(E_psi_p, 1e-12)
                    E_psi_b = float(np.dot(pmv_b_raw, psi_b))
                    pmv_b = pmv_b_raw * psi_b / max(E_psi_b, 1e-12)

                    n_atoms_pn = len(pmv)
                    n_atoms_b = len(pmv_b)

                    # CRN: shared uniform draw u ∈ [0,1] applied separately
                    # to each scenario's CDF. When pol and base have
                    # different employment status (different atom counts),
                    # joint atom probability under shared u equals
                    # overlap of CDF intervals. For typical HAFiscal cases
                    # (employed: 7 atoms; unemp: 1 atom), the smaller
                    # distribution has cumulative=1.0 over [0,1] entirely,
                    # so EVERY atom of the larger distribution maps to
                    # atom=0 of the smaller (and vice versa).
                    #
                    # General implementation: enumerate pol atoms 0..n_pn-1
                    # and base atoms 0..n_b-1 with joint probability
                    # = overlap of [F_p[k_p-1], F_p[k_p]] and [F_b[k_b-1], F_b[k_b]].
                    #
                    # Special case used here: at least one of the two has
                    # 1 atom. In that case the joint probability collapses
                    # to pmv_p[k_p] × pmv_b[k_b] with shared draw treated
                    # as: iterate over the LARGER atom set, the smaller
                    # always maps to its only atom (since its CDF is 1
                    # over the whole unit interval).
                    if n_atoms_pn == n_atoms_b:
                        # Aligned: shared atom index i with joint pmv = pmv_p[i] = pmv_b[i].
                        atom_pairs = [(i, i, pmv[i]) for i in range(n_atoms_pn)]
                    elif n_atoms_pn > 1 and n_atoms_b == 1:
                        # Iterate pol atoms; base always at atom 0.
                        atom_pairs = [(i, 0, pmv[i]) for i in range(n_atoms_pn)]
                    elif n_atoms_pn == 1 and n_atoms_b > 1:
                        # Iterate base atoms; pol always at atom 0.
                        atom_pairs = [(0, j, pmv_b[j]) for j in range(n_atoms_b)]
                    else:
                        # Both have >1 atoms but different counts — fall
                        # back to general overlap (rare in HAFiscal).
                        F_p = np.cumsum(pmv)
                        F_b = np.cumsum(pmv_b)
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

                        # Effective income realizations.
                        xi_eff_p = AggDemandFac_pol * xi_p[atom_p_idx] + TranShk_addition_pol[j_pn_dst]
                        xi_eff_n = AggDemandFac_none * xi_n[atom_p_idx] + TranShk_addition_none[j_pn_dst]
                        xi_eff_b = xi_b[atom_b_idx]
                        # Base scenario: no AD, no TranShk_addition.

                        # m_next per axis.
                        inv_pG_pn = 1.0 / (psi_a * PermGroFac[j_pn_dst])
                        inv_pG_b = 1.0 / (psi_b_a * PermGroFac[j_b_dst])
                        R_pn = Rfree[j_pn_dst]
                        R_b = Rfree[j_b_dst]

                        m_p = R_pn * aGrid * inv_pG_pn + xi_eff_p
                        m_n = R_pn * aGrid * inv_pG_pn + xi_eff_n
                        m_b = R_b * aGrid * inv_pG_b + xi_eff_b

                        # FIX #11 (BUG-045): scenario-specific cFunc per axis.
                        # pol: cFunc_pol; none: cFunc_none; base: cFunc_b.
                        Cratio_p = np.full(A, Cratio_pol)
                        Cratio_n = np.full(A, Cratio_none)
                        Cratio_b = np.full(A, 1.0)
                        c_star_p = cFuncs_pol[j_pn_dst](m_p, Cratio_p)
                        c_star_n = cFuncs_none[j_pn_dst](m_n, Cratio_n)
                        c_star_b = cFuncs_b[j_b_dst](m_b, Cratio_b)

                        c_p = (1 - Splurge) * c_star_p + Splurge * xi_eff_p
                        c_n = (1 - Splurge) * c_star_n + Splurge * xi_eff_n
                        c_b = (1 - Splurge) * c_star_b + Splurge * xi_eff_b

                        # `(eq:5D-asset-update)` — a_next per scenario.
                        a_p_next = m_p - c_p  # (A,)
                        a_n_next = m_n - c_n
                        a_b_next = m_b - c_b

                        # `(eq:5D-welfare-integrand)` per cell.
                        # Integrand at (a_p_idx, a_n_idx, a_b_idx) = (u(c_p[a_p]) - u(c_n[a_n])) * c_b[a_b]^rho
                        u_p = _u(c_p, rho)  # (A,)
                        u_n = _u(c_n, rho)  # (A,)
                        mu_inv_b = _mu_inv(c_b, rho)  # (A,)
                        # Outer combine: 3D integrand.
                        # integrand[i, j, k] = (u_p[i] - u_n[j]) * mu_inv_b[k]
                        u_diff = u_p[:, None] - u_n[None, :]  # (A, A)
                        integrand_3d = u_diff[:, :, None] * mu_inv_b[None, None, :]  # (A, A, A)

                        # Mass weight per cell.
                        weight_3d = d_src * p_jj * pmv_a  # (A, A, A)

                        # Welfare contribution.
                        welfare_num += float(np.sum(weight_3d * integrand_3d))

                        # FIX #12: per-period aggregates for AddInc/AddCons.
                        # Sum mass × income (per-axis) → aggregate income.
                        # weight_3d = (A, A, A) mass; xi_eff_p, c_p are per-axis (A,).
                        # Marginalize weight to per-axis: pol uses axis 0, base axis 2.
                        # weight_pol_axis = sum over (a_n, a_b) of weight_3d
                        weight_pol = weight_3d.sum(axis=(1, 2))  # (A_p,)
                        weight_none = weight_3d.sum(axis=(0, 2))  # (A_n,)
                        weight_base = weight_3d.sum(axis=(0, 1))  # (A_b,)
                        # Income from this destination atom × pmv weight
                        # (xi_eff is scalar per atom; sum mass × xi_eff)
                        agg_inc_pol += float(np.sum(weight_pol) * xi_eff_p)
                        agg_inc_none += float(np.sum(weight_none) * xi_eff_n)
                        # Consumption: c_p, c_n are (A,) per-axis-grid.
                        agg_cons_pol += float(np.sum(weight_pol * c_p))
                        agg_cons_none += float(np.sum(weight_none * c_n))

                        # DIAG #13: per-cell mean c_p, c_n, c_b, welfare
                        cell_key = (j_pn_dst, j_b_dst)
                        if cell_key not in per_cell:
                            per_cell[cell_key] = {
                                'mass': 0.0, 'sum_cp': 0.0, 'sum_cn': 0.0,
                                'sum_cb': 0.0, 'sum_w': 0.0,
                            }
                        pc = per_cell[cell_key]
                        cell_mass = float(np.sum(weight_3d))
                        pc['mass'] += cell_mass
                        pc['sum_cp'] += float(np.sum(weight_pol * c_p))
                        pc['sum_cn'] += float(np.sum(weight_none * c_n))
                        pc['sum_cb'] += float(np.sum(weight_base * c_b))
                        pc['sum_w'] += float(np.sum(weight_3d * integrand_3d))

                        # Distribute mass to next-period 5D dist via 3D-bilinear.
                        # values per axis broadcast to (A, A, A) for distribution.
                        # Source mass at (i_p, i_n, i_b) goes to next-period
                        # (a_p_next[i_p], a_n_next[i_n], a_b_next[i_b]).
                        # Use Numpy meshgrid + ravel.
                        # For efficiency, flatten and call _3d_bilinear_distribute.
                        I = np.arange(A)
                        IP, IN, IB = np.meshgrid(I, I, I, indexing='ij')
                        flat_w = weight_3d.ravel()
                        # Skip near-zero weights.
                        mask = flat_w > _DIST_EPS
                        if not mask.any():
                            continue
                        vp_flat = a_p_next[IP].ravel()[mask]
                        vn_flat = a_n_next[IN].ravel()[mask]
                        vb_flat = a_b_next[IB].ravel()[mask]
                        w_flat = flat_w[mask]
                        _3d_bilinear_distribute(
                            vp_flat, vn_flat, vb_flat, w_flat,
                            aGrid, dist5d_next, j_pn_dst, j_b_dst)

    # `(eq:5D-mortality)` — apply death + rebirth at end of period.
    # Survivors keep mass × LivPrb_avg; deaths (mass × death_prob) are
    # replaced by newborns at the diagonal initial-state distribution.
    # Conserves total mass.
    if newborn_dist5d_diag is not None and LivPrb_avg < 1.0 - 1e-15:
        total_mass_before = dist5d_next.sum()
        dist5d_next *= LivPrb_avg
        newborn_mass = (1.0 - LivPrb_avg) * total_mass_before
        dist5d_next += newborn_mass * newborn_dist5d_diag

    return dist5d_next, welfare_num, {
        'inc_pol': agg_inc_pol,
        'inc_none': agg_inc_none,
        'cons_pol': agg_cons_pol,
        'cons_none': agg_cons_none,
        'per_cell': per_cell,
    }
