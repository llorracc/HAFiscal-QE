"""
Phase B.2 Steps 2-5: JAX-GPU port of _step_period_5d.

Strategy:
  1. Pre-tabulate HARK cFunc objects on a fine m_grid (one table per
     (cohort, scenario, macro_state, j_micro)).
  2. cFunc evaluation inside JAX kernel becomes jnp.interp lookup.
  3. The J⁴ inner loop becomes a vectorized tensor op (no Python loop).
  4. JIT-compile the per-step kernel.

Originally non-AD only (Cratio=1.0 throughout). The AD follow-up LANDED,
resolved differently than anticipated: AD scenarios are supported via
per-period `Cratio_pol` / `Cratio_none` scalars threaded through
`_step_period_5d` (cFunc evaluation at the realized per-period Cratio,
matching welfare6_tm_joint5d's Cratio_*_series); the once-anticipated
2D (m, Cratio) tabulation was not needed.

Validates against welfare6_tm_joint5d._step_period_5d at small A.
"""
from __future__ import annotations
import os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_FORCE_FP64 = os.environ.get('FORCE_FP64', '0') == '1'
_USE_FP64 = _FORCE_FP64
if _FORCE_FP64:
    import jax
    jax.config.update('jax_enable_x64', True)

import jax
import jax.numpy as jnp

from welfare6_tm_joint5d import (
    _DIST_EPS, _TRANS_EPS, _resolve_scenario_IncShkDstn,
    compute_joint_markov,
)


# ============================================================
# cFunc tabulation
# ============================================================

def build_m_grid(M_grid, m_min=0.01, m_max=50.0):
    """Build the m_grid for cFunc tabulation.

    Default = HARK's triple-log nested grid (NestFac=3), which densifies
    near zero where the welfare integrand -1/c is most curved. linspace
    gives only ~2 pts in [0,1] at N=100; nested gives ~44 pts.

    Override via env var JOINT5D_MGRID_NEST:
      -1  → linspace (legacy, accuracy-degraded; for A/B comparison only)
       0  → exponential
       3  → HARK default triple-log (recommended)
    """
    import os
    nest = int(os.environ.get('JOINT5D_MGRID_NEST', '3'))
    if nest == -1:
        return np.linspace(m_min, m_max, M_grid)
    from HARK.utilities import make_grid_exp_mult
    return make_grid_exp_mult(m_min, m_max, M_grid, nest)


def tabulate_cfunc_list(cfunc_list, m_grid, Cratio=1.0):
    """Pre-tabulate a HARK cFunc list on a fixed m_grid.

    Args:
        cfunc_list: list of N cFuncs (e.g., agent.solution[0].cFunc)
        m_grid: (M,) array of m values to evaluate at
        Cratio: scalar Cratio (default 1.0 for non-AD scenarios)

    Returns:
        (N, M) numpy array of cFunc values.
    """
    M = len(m_grid)
    N = len(cfunc_list)
    out = np.zeros((N, M), dtype=np.float64)
    cr_arr = np.full(M, Cratio)
    for i, cf in enumerate(cfunc_list):
        out[i] = np.asarray(cf(np.asarray(m_grid), cr_arr))
    return out


# ============================================================
# JAX-friendly cFunc lookup via interp
# ============================================================

@jax.jit
def interp_cfunc(m_query, m_grid, c_table):
    """1D linear interpolation: evaluate c_table at m_query.

    Args:
        m_query: (K,) query m values
        m_grid: (M,) sorted grid points
        c_table: (M,) cFunc values at m_grid

    Returns:
        (K,) interpolated c values
    """
    return jnp.interp(m_query, m_grid, c_table)


# ============================================================
# JAX equivalents of the HARK utility functions
# ============================================================

@jax.jit
def _u_jax(c, rho):
    c = jnp.maximum(c, 1e-12)
    # γ=2 is the common case → log avoidance; general CRRA
    return jnp.where(
        jnp.abs(rho - 1.0) < 1e-12,
        jnp.log(c),
        (c ** (1.0 - rho)) / (1.0 - rho),
    )


@jax.jit
def _mu_inv_jax(c, rho):
    c = jnp.maximum(c, 1e-12)
    return c ** rho


# ============================================================
# 3D bilinear distribute (JAX version)
# ============================================================

@jax.jit
def _3d_bilinear_distribute_jax(
    values_p, values_n, values_b, weights,
    aGrid,
):
    """JAX version of welfare6_tm_joint5d._3d_bilinear_distribute.

    Returns a (A, A, A) accumulator (one slice of dist5d_next).
    Reuses the diagonal-preserving logic.

    Inputs:
        values_p, values_n, values_b: (N,) continuous asset values
        weights: (N,) mass weights
        aGrid: (A,) grid
    """
    A = aGrid.shape[0]
    aMin = aGrid[0]
    aMax = aGrid[-1]
    vp = jnp.clip(values_p, aMin, aMax)
    vn = jnp.clip(values_n, aMin, aMax)
    vb = jnp.clip(values_b, aMin, aMax)

    # Diagonal mask
    diag_tol = 1e-12
    is_diag = (jnp.abs(vp - vn) < diag_tol) & (jnp.abs(vn - vb) < diag_tol)

    # Weights split by branch
    w_diag = jnp.where(is_diag, weights, 0.0)
    w_off = jnp.where(is_diag, 0.0, weights)

    # Bilinear lookups
    def _lookup(values):
        i_lo = jnp.clip(jnp.searchsorted(aGrid, values, side='right') - 1, 0, A - 2)
        a_lo = aGrid[i_lo]
        a_hi = aGrid[i_lo + 1]
        w_hi = (values - a_lo) / (a_hi - a_lo)
        w_lo = 1.0 - w_hi
        return i_lo, w_lo, w_hi

    ip_lo, wp_lo, wp_hi = _lookup(vp)
    in_lo, wn_lo, wn_hi = _lookup(vn)
    ib_lo, wb_lo, wb_hi = _lookup(vb)
    # Diagonal branch uses vp as the shared coordinate
    id_lo, wd_lo, wd_hi = _lookup(vp)
    id_hi = id_lo + 1

    target = jnp.zeros((A, A, A), dtype=aGrid.dtype)

    # Diagonal contributions
    target = target.at[id_lo, id_lo, id_lo].add(w_diag * wd_lo)
    target = target.at[id_hi, id_hi, id_hi].add(w_diag * wd_hi)

    # Off-diagonal: 8 corners
    ip_hi = ip_lo + 1
    in_hi = in_lo + 1
    ib_hi = ib_lo + 1
    target = target.at[ip_lo, in_lo, ib_lo].add(w_off * wp_lo * wn_lo * wb_lo)
    target = target.at[ip_lo, in_lo, ib_hi].add(w_off * wp_lo * wn_lo * wb_hi)
    target = target.at[ip_lo, in_hi, ib_lo].add(w_off * wp_lo * wn_hi * wb_lo)
    target = target.at[ip_lo, in_hi, ib_hi].add(w_off * wp_lo * wn_hi * wb_hi)
    target = target.at[ip_hi, in_lo, ib_lo].add(w_off * wp_hi * wn_lo * wb_lo)
    target = target.at[ip_hi, in_lo, ib_hi].add(w_off * wp_hi * wn_lo * wb_hi)
    target = target.at[ip_hi, in_hi, ib_lo].add(w_off * wp_hi * wn_hi * wb_lo)
    target = target.at[ip_hi, in_hi, ib_hi].add(w_off * wp_hi * wn_hi * wb_hi)

    return target


# ============================================================
# IncShkDstn extraction — convert HARK IncShkDstn objects to flat arrays
# ============================================================

def extract_incshk_arrays(incshk_list, max_atoms=None):
    """Convert a list of HARK IncShkDstn objects to fixed-shape numpy arrays.

    Args:
        incshk_list: list of N IncShkDstn objects (each with .atoms and .pmv)
        max_atoms: maximum atom count to pad to (auto-detect if None)

    Returns:
        dict with keys:
            psi:        (N, max_atoms) permanent income shocks
            xi:         (N, max_atoms) transitory income shocks
            pmv:        (N, max_atoms) atom probabilities (padded with 0)
            n_atoms:    (N,) int actual atom counts
    """
    N = len(incshk_list)
    if max_atoms is None:
        max_atoms = max(len(np.asarray(dstn.pmv)) for dstn in incshk_list)

    psi = np.zeros((N, max_atoms), dtype=np.float64)
    xi = np.zeros((N, max_atoms), dtype=np.float64)
    pmv = np.zeros((N, max_atoms), dtype=np.float64)
    n_atoms = np.zeros(N, dtype=np.int64)
    for i, dstn in enumerate(incshk_list):
        p = np.asarray(dstn.pmv)
        n = len(p)
        n_atoms[i] = n
        psi[i, :n] = np.asarray(dstn.atoms[0])
        xi[i, :n] = np.asarray(dstn.atoms[1])
        pmv[i, :n] = p
    return {'psi': psi, 'xi': xi, 'pmv': pmv, 'n_atoms': n_atoms,
            'max_atoms': max_atoms}


# ============================================================
# Q-reweighting (pre-compute Q-twisted pmv)
# ============================================================

def q_reweight_pmv(psi, pmv, n_atoms):
    """Apply Harmenberg neutral-measure Q-reweighting to atom probabilities.

    pmv_q[i, k] = pmv[i, k] * psi[i, k] / E[psi[i]]  (for k < n_atoms[i])

    Args:
        psi: (N, max_atoms) permanent shocks
        pmv: (N, max_atoms) original probabilities
        n_atoms: (N,) actual atom counts

    Returns:
        pmv_q: (N, max_atoms) Q-reweighted probabilities (= 0 where k >= n_atoms[i])
    """
    pmv_q = np.zeros_like(pmv)
    for i in range(len(n_atoms)):
        n = int(n_atoms[i])
        if n == 0:
            continue
        E_psi = float(np.dot(pmv[i, :n], psi[i, :n]))
        if E_psi > 1e-12:
            pmv_q[i, :n] = pmv[i, :n] * psi[i, :n] / E_psi
    return pmv_q


# ============================================================
# Joint atom-pair table (mirrors atom_pairs enumeration in numpy kernel)
# ============================================================

def build_joint_atom_table(pmv_pn_q, pmv_b_q, n_atoms_pn, n_atoms_b):
    """For each (j_pn_dst, j_b_dst) combination, build a list of
    (atom_p_idx, atom_b_idx, joint_pmv) triples and pad to fixed shape.

    Mirrors the atom_pairs logic in welfare6_tm_joint5d._step_period_5d:
      - n_atoms_pn == n_atoms_b: aligned (k, k, pmv_pn[k]) for k in 0..n
      - n_atoms_pn > 1 and n_atoms_b == 1: (k, 0, pmv_pn[k])
      - n_atoms_pn == 1 and n_atoms_b > 1: (0, k, pmv_b[k])
      - else: general overlap (rare in HAFiscal)

    Returns:
        atom_p_idx_arr:  (J_pn, J_b, max_pairs) int
        atom_b_idx_arr:  (J_pn, J_b, max_pairs) int
        joint_pmv_arr:   (J_pn, J_b, max_pairs) float, 0 for padded entries
    """
    J_pn = len(n_atoms_pn)
    J_b = len(n_atoms_b)
    max_pairs = int(max(n_atoms_pn.max(), n_atoms_b.max()))
    atom_p = np.zeros((J_pn, J_b, max_pairs), dtype=np.int64)
    atom_b = np.zeros((J_pn, J_b, max_pairs), dtype=np.int64)
    joint_pmv = np.zeros((J_pn, J_b, max_pairs), dtype=np.float64)

    for jp in range(J_pn):
        n_p = int(n_atoms_pn[jp])
        for jb in range(J_b):
            n_b = int(n_atoms_b[jb])
            if n_p == n_b:
                for k in range(n_p):
                    atom_p[jp, jb, k] = k
                    atom_b[jp, jb, k] = k
                    joint_pmv[jp, jb, k] = pmv_pn_q[jp, k]
            elif n_p > 1 and n_b == 1:
                for k in range(n_p):
                    atom_p[jp, jb, k] = k
                    atom_b[jp, jb, k] = 0
                    joint_pmv[jp, jb, k] = pmv_pn_q[jp, k]
            elif n_p == 1 and n_b > 1:
                for k in range(n_b):
                    atom_p[jp, jb, k] = 0
                    atom_b[jp, jb, k] = k
                    joint_pmv[jp, jb, k] = pmv_b_q[jb, k]
            else:
                # General overlap (rare). Fall back to numpy.
                F_p = np.cumsum(pmv_pn_q[jp, :n_p])
                F_b = np.cumsum(pmv_b_q[jb, :n_b])
                F_p_left = np.concatenate([[0], F_p[:-1]])
                F_b_left = np.concatenate([[0], F_b[:-1]])
                k = 0
                for i in range(n_p):
                    for j in range(n_b):
                        p = max(0.0, min(F_p[i], F_b[j]) - max(F_p_left[i], F_b_left[j]))
                        if p > _TRANS_EPS and k < max_pairs:
                            atom_p[jp, jb, k] = i
                            atom_b[jp, jb, k] = j
                            joint_pmv[jp, jb, k] = p
                            k += 1

    return atom_p, atom_b, joint_pmv


# ============================================================
# Per-period 5D step kernel — JAX version (NOT YET JIT'D / VECTORIZED)
# ============================================================
# This is a CORRECTNESS-FIRST implementation: it uses JAX arrays everywhere
# but with Python loops over (j_src, j_dst). This makes it easy to validate
# against the numpy reference. Once validated, the inner work can be
# vectorized / jit-compiled for speed.
#
# NOT a production kernel yet — see the validation script in
# validate_jax_kernel_vs_numpy.py.

def _step_period_5d_jax_loops(
    dist5d,                      # (A, A, A, J, J)
    aGrid,                       # (A,)
    joint_markov,                # (J, J, J, J)
    cfunc_pol_table_t,           # (J, M)  pre-sliced by macro state for this period
    cfunc_none_table_t,
    cfunc_b_table_t,
    m_grid,                      # (M,)
    psi_pn, xi_pn, pmv_pn_q,     # (J, max_atoms) for pol scenario at this macro
    n_atoms_pn,                  # (J,) int
    psi_n_xi,                    # (J, max_atoms) xi for none scenario (psi shared with pol)
    psi_b, xi_b, pmv_b_q, n_atoms_b,  # (J, max_atoms_b) for base
    atom_p_idx, atom_b_idx, joint_pmv,  # (J, J, max_pairs) joint atom table
    Rfree, PermGroFac,           # (J,)
    Splurge, rho,
    Cratio_pol, Cratio_none,
    AggDemandFac_pol, AggDemandFac_none,
    TranShk_addition_pol,        # (J,)
    TranShk_addition_none,
    LivPrb_avg=1.0, newborn_dist5d_diag=None,
):
    """JAX-array Python-loops implementation of _step_period_5d.

    All arithmetic happens on JAX arrays; loops are in Python. This is
    not max performance but enables direct validation against numpy.
    """
    A = aGrid.shape[0]
    J = joint_markov.shape[0]
    max_pairs = atom_p_idx.shape[-1]

    dist5d_next = jnp.zeros_like(dist5d)
    welfare_num = jnp.float64(0.0) if _USE_FP64 else jnp.float32(0.0)
    agg_inc_pol = welfare_num
    agg_inc_none = welfare_num
    agg_cons_pol = welfare_num
    agg_cons_none = welfare_num

    for j_pn_src in range(J):
        for j_b_src in range(J):
            d_src = dist5d[:, :, :, j_pn_src, j_b_src]  # (A, A, A)
            mass_total = jnp.sum(d_src)
            # Skip if no mass (can't use python conditional on traced value, but
            # since dist5d is concrete here, we can check at the Python level)
            if float(mass_total) <= _DIST_EPS:
                continue

            for j_pn_dst in range(J):
                for j_b_dst in range(J):
                    p_jj = float(joint_markov[j_pn_src, j_b_src, j_pn_dst, j_b_dst])
                    if p_jj < _TRANS_EPS:
                        continue

                    # Iterate atom pairs (padded to max_pairs)
                    for k in range(max_pairs):
                        pmv_a = float(joint_pmv[j_pn_dst, j_b_dst, k])
                        if pmv_a < _TRANS_EPS:
                            continue
                        ap = int(atom_p_idx[j_pn_dst, j_b_dst, k])
                        ab = int(atom_b_idx[j_pn_dst, j_b_dst, k])
                        psi_a = float(psi_pn[j_pn_dst, ap])
                        psi_b_a = float(psi_b[j_b_dst, ab])

                        # Effective income realizations
                        xi_eff_p = AggDemandFac_pol * float(xi_pn[j_pn_dst, ap]) + float(TranShk_addition_pol[j_pn_dst])
                        xi_eff_n = AggDemandFac_none * float(psi_n_xi[j_pn_dst, ap]) + float(TranShk_addition_none[j_pn_dst])
                        xi_eff_b = float(xi_b[j_b_dst, ab])

                        inv_pG_pn = 1.0 / (psi_a * float(PermGroFac[j_pn_dst]))
                        inv_pG_b = 1.0 / (psi_b_a * float(PermGroFac[j_b_dst]))
                        R_pn = float(Rfree[j_pn_dst])
                        R_b = float(Rfree[j_b_dst])

                        m_p = R_pn * aGrid * inv_pG_pn + xi_eff_p
                        m_n = R_pn * aGrid * inv_pG_pn + xi_eff_n
                        m_b = R_b * aGrid * inv_pG_b + xi_eff_b

                        # cFunc via JAX interp from pre-tabulated table
                        c_star_p = interp_cfunc(m_p, m_grid, cfunc_pol_table_t[j_pn_dst])
                        c_star_n = interp_cfunc(m_n, m_grid, cfunc_none_table_t[j_pn_dst])
                        c_star_b = interp_cfunc(m_b, m_grid, cfunc_b_table_t[j_b_dst])

                        c_p = (1 - Splurge) * c_star_p + Splurge * xi_eff_p
                        c_n = (1 - Splurge) * c_star_n + Splurge * xi_eff_n
                        c_b = (1 - Splurge) * c_star_b + Splurge * xi_eff_b

                        a_p_next = m_p - c_p
                        a_n_next = m_n - c_n
                        a_b_next = m_b - c_b

                        u_p = _u_jax(c_p, rho)
                        u_n = _u_jax(c_n, rho)
                        mu_inv_b = _mu_inv_jax(c_b, rho)
                        u_diff = u_p[:, None] - u_n[None, :]
                        integrand_3d = u_diff[:, :, None] * mu_inv_b[None, None, :]

                        weight_3d = d_src * p_jj * pmv_a

                        welfare_num = welfare_num + jnp.sum(weight_3d * integrand_3d)

                        weight_pol = jnp.sum(weight_3d, axis=(1, 2))
                        weight_none = jnp.sum(weight_3d, axis=(0, 2))
                        agg_inc_pol = agg_inc_pol + jnp.sum(weight_pol) * xi_eff_p
                        agg_inc_none = agg_inc_none + jnp.sum(weight_none) * xi_eff_n
                        agg_cons_pol = agg_cons_pol + jnp.sum(weight_pol * c_p)
                        agg_cons_none = agg_cons_none + jnp.sum(weight_none * c_n)

                        # 3D bilinear scatter (per (j_pn_dst, j_b_dst) slice)
                        flat_w = weight_3d.ravel()
                        # Build full coords
                        I = jnp.arange(A)
                        IP, IN, IB = jnp.meshgrid(I, I, I, indexing='ij')
                        vp_full = a_p_next[IP]
                        vn_full = a_n_next[IN]
                        vb_full = a_b_next[IB]
                        slice_contrib = _3d_bilinear_distribute_jax(
                            vp_full.ravel(), vn_full.ravel(), vb_full.ravel(),
                            flat_w, aGrid,
                        )
                        # Add to the right (j_pn_dst, j_b_dst) slice
                        dist5d_next = dist5d_next.at[:, :, :, j_pn_dst, j_b_dst].add(slice_contrib)

    # Mortality + rebirth
    if newborn_dist5d_diag is not None and LivPrb_avg < 1.0 - 1e-15:
        total_mass_before = jnp.sum(dist5d_next)
        dist5d_next = dist5d_next * LivPrb_avg
        newborn_mass = (1.0 - LivPrb_avg) * total_mass_before
        dist5d_next = dist5d_next + newborn_mass * newborn_dist5d_diag

    return dist5d_next, float(welfare_num), {
        'inc_pol': float(agg_inc_pol),
        'inc_none': float(agg_inc_none),
        'cons_pol': float(agg_cons_pol),
        'cons_none': float(agg_cons_none),
    }


# ============================================================
# v3 — JIT-compiled vectorized kernel
# ============================================================
# Like v2 but: no Python conditionals (use masks), no Python loop for scatter
# (use vmap), wraps with @jax.jit.

def _bilinear_3d_scatter_single(weight_3d, a_p_next, a_n_next, a_b_next, aGrid):
    """Scatter one (A,A,A) weight tensor onto an (A,A,A) accumulator using
    next-period asset values. Returns the (A,A,A) accumulator slice.

    weight_3d: (A, A, A) source mass
    a_p_next, a_n_next, a_b_next: (A,) next-period asset values per axis
    aGrid: (A,) grid

    This is the per-(jp_dst, jb_dst) scatter; vmap over those axes externally.
    """
    A = aGrid.shape[0]
    aMin = aGrid[0]
    aMax = aGrid[-1]

    # Clip
    vp = jnp.clip(a_p_next, aMin, aMax)
    vn = jnp.clip(a_n_next, aMin, aMax)
    vb = jnp.clip(a_b_next, aMin, aMax)

    # Bilinear lookup per axis
    def _lookup1d(values):
        i_lo = jnp.clip(jnp.searchsorted(aGrid, values, side='right') - 1, 0, A - 2)
        a_lo = aGrid[i_lo]
        a_hi = aGrid[i_lo + 1]
        w_hi = (values - a_lo) / (a_hi - a_lo)
        w_lo = 1.0 - w_hi
        return i_lo, w_lo, w_hi

    ip_lo, wp_lo, wp_hi = _lookup1d(vp)  # (A,)
    in_lo, wn_lo, wn_hi = _lookup1d(vn)
    ib_lo, wb_lo, wb_hi = _lookup1d(vb)

    # Diagonal mask: source (i, j, k) is on the model's CRN diagonal when
    # vp[i] == vn[j] == vb[k]. For each source cell:
    diag_tol = 1e-12
    # Expand vp, vn, vb to (A, A, A)
    vpE = vp[:, None, None]
    vnE = vn[None, :, None]
    vbE = vb[None, None, :]
    is_diag = (jnp.abs(vpE - vnE) < diag_tol) & (jnp.abs(vnE - vbE) < diag_tol)
    w_diag = jnp.where(is_diag, weight_3d, 0.0)
    w_off = jnp.where(is_diag, 0.0, weight_3d)

    target = jnp.zeros((A, A, A), dtype=weight_3d.dtype)

    # Off-diagonal: 8 corners
    # Indices broadcast: (A, A, A)
    IP_lo = jnp.broadcast_to(ip_lo[:, None, None], (A, A, A))
    IN_lo = jnp.broadcast_to(in_lo[None, :, None], (A, A, A))
    IB_lo = jnp.broadcast_to(ib_lo[None, None, :], (A, A, A))
    IP_hi = IP_lo + 1
    IN_hi = IN_lo + 1
    IB_hi = IB_lo + 1
    WPL = jnp.broadcast_to(wp_lo[:, None, None], (A, A, A))
    WPH = jnp.broadcast_to(wp_hi[:, None, None], (A, A, A))
    WNL = jnp.broadcast_to(wn_lo[None, :, None], (A, A, A))
    WNH = jnp.broadcast_to(wn_hi[None, :, None], (A, A, A))
    WBL = jnp.broadcast_to(wb_lo[None, None, :], (A, A, A))
    WBH = jnp.broadcast_to(wb_hi[None, None, :], (A, A, A))

    # Flatten everything for scatter
    target = target.at[IP_lo.ravel(), IN_lo.ravel(), IB_lo.ravel()].add(
        (w_off * WPL * WNL * WBL).ravel())
    target = target.at[IP_lo.ravel(), IN_lo.ravel(), IB_hi.ravel()].add(
        (w_off * WPL * WNL * WBH).ravel())
    target = target.at[IP_lo.ravel(), IN_hi.ravel(), IB_lo.ravel()].add(
        (w_off * WPL * WNH * WBL).ravel())
    target = target.at[IP_lo.ravel(), IN_hi.ravel(), IB_hi.ravel()].add(
        (w_off * WPL * WNH * WBH).ravel())
    target = target.at[IP_hi.ravel(), IN_lo.ravel(), IB_lo.ravel()].add(
        (w_off * WPH * WNL * WBL).ravel())
    target = target.at[IP_hi.ravel(), IN_lo.ravel(), IB_hi.ravel()].add(
        (w_off * WPH * WNL * WBH).ravel())
    target = target.at[IP_hi.ravel(), IN_hi.ravel(), IB_lo.ravel()].add(
        (w_off * WPH * WNH * WBL).ravel())
    target = target.at[IP_hi.ravel(), IN_hi.ravel(), IB_hi.ravel()].add(
        (w_off * WPH * WNH * WBH).ravel())

    # Diagonal: For each source diagonal cell (i, i, i), spread to (i_lo, i_lo, i_lo) and (i_hi, i_hi, i_hi)
    # Where i_lo = bilinear lookup of vp[i] (= vn[i] = vb[i] on diagonal)
    # Diagonal source cells: (i, i, i) for i = 0..A-1
    diag_idx = jnp.arange(A)
    id_lo = ip_lo  # diagonal uses vp (= vn = vb on diag), already computed
    id_hi = id_lo + 1
    wd_lo = wp_lo
    wd_hi = wp_hi

    # Pull diagonal of w_diag: shape (A,)
    w_diag_arr = w_diag[diag_idx, diag_idx, diag_idx]

    target = target.at[id_lo, id_lo, id_lo].add(w_diag_arr * wd_lo)
    target = target.at[id_hi, id_hi, id_hi].add(w_diag_arr * wd_hi)

    return target


def _step_period_5d_jax_v3_impl_singleatom(
    atom_k,                # which atom index to process (scalar int via lax.scan)
    dist5d, aGrid, joint_markov,
    d_src_agg,             # pre-computed source aggregation (A,A,A,J,J)
    cfunc_pol_table_t, cfunc_none_table_t, cfunc_b_table_t,
    m_grid,
    psi_pn, xi_pn, psi_n_xi, psi_b, xi_b,
    atom_p_idx, atom_b_idx, joint_pmv,
    Rfree, PermGroFac,
    Splurge, rho,
    Cratio_pol, Cratio_none,
    AggDemandFac_pol, AggDemandFac_none,
    TranShk_addition_pol, TranShk_addition_none,
):
    """Process ONE atom_k for all (j_pn_dst, j_b_dst). Returns per-atom
    contributions to dist5d_next, welfare_num, and aggregates.
    Memory: O(J^2 * A^3) instead of O(J^2 * max_pairs * A^3).
    """
    A = aGrid.shape[0]
    J = joint_markov.shape[0]

    # Gather atom indices for this k across all (jp_dst, jb_dst)
    # atom_p_idx[:, :, k]: (J, J)
    a_pidx = atom_p_idx[:, :, atom_k]
    a_bidx = atom_b_idx[:, :, atom_k]
    pmv_a = joint_pmv[:, :, atom_k]  # (J, J)

    # Broadcast grids
    jp_dst_grid = jnp.arange(J)[:, None]  # (J, 1)
    jb_dst_grid = jnp.arange(J)[None, :]  # (1, J)
    jp_dst_full = jnp.broadcast_to(jp_dst_grid, (J, J))
    jb_dst_full = jnp.broadcast_to(jb_dst_grid, (J, J))

    psi_a = psi_pn[jp_dst_full, a_pidx]      # (J, J)
    xi_p_a = xi_pn[jp_dst_full, a_pidx]
    xi_n_a = psi_n_xi[jp_dst_full, a_pidx]
    psi_b_a = psi_b[jb_dst_full, a_bidx]
    xi_b_a = xi_b[jb_dst_full, a_bidx]

    xi_eff_p = AggDemandFac_pol * xi_p_a + TranShk_addition_pol[jp_dst_full]
    xi_eff_n = AggDemandFac_none * xi_n_a + TranShk_addition_none[jp_dst_full]
    xi_eff_b = xi_b_a

    R_pn = Rfree[jp_dst_full]
    R_b = Rfree[jb_dst_full]
    inv_pG_pn = 1.0 / (psi_a * PermGroFac[jp_dst_full])
    inv_pG_b = 1.0 / (psi_b_a * PermGroFac[jb_dst_full])

    aG = aGrid[None, None, :]
    m_p = R_pn[..., None] * aG * inv_pG_pn[..., None] + xi_eff_p[..., None]  # (J, J, A)
    m_n = R_pn[..., None] * aG * inv_pG_pn[..., None] + xi_eff_n[..., None]
    m_b = R_b[..., None] * aG * inv_pG_b[..., None] + xi_eff_b[..., None]

    B = J * J
    pol_table_per_cell = cfunc_pol_table_t[jp_dst_full].reshape(B, -1)
    none_table_per_cell = cfunc_none_table_t[jp_dst_full].reshape(B, -1)
    b_table_per_cell = cfunc_b_table_t[jb_dst_full].reshape(B, -1)

    c_star_p = jax.vmap(lambda mq, tb: jnp.interp(mq, m_grid, tb))(
        m_p.reshape(B, A), pol_table_per_cell).reshape(J, J, A)
    c_star_n = jax.vmap(lambda mq, tb: jnp.interp(mq, m_grid, tb))(
        m_n.reshape(B, A), none_table_per_cell).reshape(J, J, A)
    c_star_b = jax.vmap(lambda mq, tb: jnp.interp(mq, m_grid, tb))(
        m_b.reshape(B, A), b_table_per_cell).reshape(J, J, A)

    c_p = (1 - Splurge) * c_star_p + Splurge * xi_eff_p[..., None]
    c_n = (1 - Splurge) * c_star_n + Splurge * xi_eff_n[..., None]
    c_b = (1 - Splurge) * c_star_b + Splurge * xi_eff_b[..., None]

    a_p_next = m_p - c_p
    a_n_next = m_n - c_n
    a_b_next = m_b - c_b

    u_p = _u_jax(c_p, rho)
    u_n = _u_jax(c_n, rho)
    mu_inv_b = _mu_inv_jax(c_b, rho)
    u_diff = u_p[..., :, None] - u_n[..., None, :]                       # (J, J, A, A)
    integrand_3d = u_diff[..., :, :, None] * mu_inv_b[..., None, None, :]  # (J, J, A, A, A)

    # Per-(jp_dst, jb_dst): weight = d_src_agg[jp_dst, jb_dst, :, :, :] * pmv_a[jp_dst, jb_dst]
    # R5: d_src_agg already in (J, J, A, A, A) layout — no transpose needed
    d_src_agg_t = d_src_agg
    weight_3d_all = d_src_agg_t * pmv_a[..., None, None, None]   # (J, J, A, A, A)

    welfare_atom = jnp.sum(weight_3d_all * integrand_3d)

    weight_pol_marg = jnp.sum(weight_3d_all, axis=(3, 4))   # (J, J, A)
    weight_none_marg = jnp.sum(weight_3d_all, axis=(2, 4))  # (J, J, A)
    inc_pol_atom = jnp.sum(jnp.sum(weight_pol_marg, axis=-1) * xi_eff_p)
    inc_none_atom = jnp.sum(jnp.sum(weight_none_marg, axis=-1) * xi_eff_n)
    cons_pol_atom = jnp.sum(weight_pol_marg * c_p)
    cons_none_atom = jnp.sum(weight_none_marg * c_n)

    # Scatter per atom_k: vmap over (jp_dst, jb_dst)
    weight_3d_flat = weight_3d_all.reshape(B, A, A, A)
    a_p_next_flat = a_p_next.reshape(B, A)
    a_n_next_flat = a_n_next.reshape(B, A)
    a_b_next_flat = a_b_next.reshape(B, A)
    scattered_flat = jax.vmap(_bilinear_3d_scatter_single, in_axes=(0, 0, 0, 0, None))(
        weight_3d_flat, a_p_next_flat, a_n_next_flat, a_b_next_flat, aGrid)
    scattered = scattered_flat.reshape(J, J, A, A, A)

    return scattered, welfare_atom, inc_pol_atom, inc_none_atom, cons_pol_atom, cons_none_atom


def _step_period_5d_jax_v3_impl(
    dist5d, aGrid, joint_markov,
    cfunc_pol_table_t, cfunc_none_table_t, cfunc_b_table_t,
    m_grid,
    psi_pn, xi_pn, pmv_pn_q,
    psi_n_xi,
    psi_b, xi_b, pmv_b_q,
    atom_p_idx, atom_b_idx, joint_pmv,
    Rfree, PermGroFac,
    Splurge, rho,
    Cratio_pol, Cratio_none,
    AggDemandFac_pol, AggDemandFac_none,
    TranShk_addition_pol, TranShk_addition_none,
    LivPrb_avg, newborn_dist5d_diag,
):
    """Pure-JAX version of the per-step kernel (no Python branching).
    Wrapped by @jax.jit. Returns dist5d_next, welfare_num, agg dict.

    Scans over atom_k to keep peak memory low (~ J^2 × A^3 instead of
    J^2 × max_pairs × A^3).
    """
    A = aGrid.shape[0]
    J = joint_markov.shape[0]
    max_pairs = atom_p_idx.shape[-1]

    # Step 1: source aggregation (R5 layout: dist5d is (p,q,I,J,K))
    d_src_agg = jnp.einsum('pqIJK,pqrs->rsIJK', dist5d, joint_markov)

    # Step 2: scan over atom_k to accumulate
    def _scan_atom(carry, k):
        scattered_acc, w_acc, ip_acc, in_acc, cp_acc, cn_acc = carry
        scat_k, w_k, ip_k, in_k, cp_k, cn_k = _step_period_5d_jax_v3_impl_singleatom(
            k, dist5d, aGrid, joint_markov, d_src_agg,
            cfunc_pol_table_t, cfunc_none_table_t, cfunc_b_table_t,
            m_grid,
            psi_pn, xi_pn, psi_n_xi, psi_b, xi_b,
            atom_p_idx, atom_b_idx, joint_pmv,
            Rfree, PermGroFac,
            Splurge, rho,
            Cratio_pol, Cratio_none,
            AggDemandFac_pol, AggDemandFac_none,
            TranShk_addition_pol, TranShk_addition_none,
        )
        return (
            scattered_acc + scat_k,
            w_acc + w_k,
            ip_acc + ip_k,
            in_acc + in_k,
            cp_acc + cp_k,
            cn_acc + cn_k,
        ), None

    init_scattered = jnp.zeros((J, J, A, A, A), dtype=dist5d.dtype)
    init_scalar = jnp.zeros((), dtype=dist5d.dtype)
    carry_init = (init_scattered, init_scalar, init_scalar, init_scalar,
                  init_scalar, init_scalar)
    (scattered_total, welfare_num, agg_inc_pol, agg_inc_none,
     agg_cons_pol, agg_cons_none), _ = jax.lax.scan(
        _scan_atom, carry_init, jnp.arange(max_pairs))

    # R5: scattered_total already in (J, J, A, A, A) layout — no transpose needed
    dist5d_next = scattered_total

    # Mortality + rebirth (always apply, gated by mask)
    total_mass_before = jnp.sum(dist5d_next)
    dist5d_with_mort = dist5d_next * LivPrb_avg + \
        (1.0 - LivPrb_avg) * total_mass_before * newborn_dist5d_diag
    dist5d_next = jnp.where(LivPrb_avg < 1.0 - 1e-15, dist5d_with_mort, dist5d_next)

    return dist5d_next, welfare_num, agg_inc_pol, agg_inc_none, agg_cons_pol, agg_cons_none


# JIT-compiled version. static_argnames keeps scalar inputs as Python values
# (improves JIT specialization without recompiling on every call).
_step_period_5d_jax_v3_jit = jax.jit(_step_period_5d_jax_v3_impl)


# ============================================================
# v4 — Multi-cohort batch (Phase C.4)
# ============================================================
# Wraps v3 singleatom with jax.vmap over a leading cohort batch axis,
# so a Baseline run with 21 cohorts processes them in parallel on GPU
# instead of serial loop.

# vmap'd singleatom: produces per-cohort outputs with leading C axis.
# in_axes encodes which inputs are batched (0 = leading axis) vs
# shared across cohorts (None).
_step_period_5d_jax_v3_impl_singleatom_vmapped = jax.vmap(
    _step_period_5d_jax_v3_impl_singleatom,
    in_axes=(
        None,  # atom_k          (shared scalar)
        0,     # dist5d          per-cohort
        None,  # aGrid           shared
        0,     # joint_markov    per-cohort
        0,     # d_src_agg       per-cohort
        0,     # cfunc_pol_t     per-cohort
        0,     # cfunc_none_t    per-cohort
        0,     # cfunc_b_t       per-cohort
        None,  # m_grid          shared
        0,     # psi_pn          per-cohort
        0,     # xi_pn           per-cohort
        0,     # psi_n_xi        per-cohort
        0,     # psi_b           per-cohort
        0,     # xi_b            per-cohort
        0,     # atom_p_idx      per-cohort
        0,     # atom_b_idx      per-cohort
        0,     # joint_pmv       per-cohort
        0,     # Rfree           per-cohort (ed_type may differ)
        0,     # PermGroFac      per-cohort
        None,  # Splurge         shared scalar (truly model-wide)
        None,  # rho             shared scalar (CRRA model-wide)
        None,  # Cratio_pol      shared per-period scalar
        None,  # Cratio_none     shared per-period scalar
        None,  # AggDemandFac_pol shared per-period
        None,  # AggDemandFac_none shared per-period
        None,  # TranShk_addition_pol shared per-period
        None,  # TranShk_addition_none shared per-period
    ),
    out_axes=(0, 0, 0, 0, 0, 0),  # all outputs gain leading C axis
)


def _step_period_5d_jax_v4_impl(
    dist5d_batch,                       # (C, A, A, A, J, J)
    aGrid, joint_markov_batch,          # (C, J, J, J, J) — per-cohort
    cfunc_pol_table_t_batch,            # (C, J, M)
    cfunc_none_table_t_batch,
    cfunc_b_table_t_batch,
    m_grid,
    psi_pn_batch, xi_pn_batch, pmv_pn_q_batch,  # (C, J, max_atoms)
    psi_n_xi_batch,
    psi_b_batch, xi_b_batch, pmv_b_q_batch,
    atom_p_idx_batch, atom_b_idx_batch, joint_pmv_batch,  # (C, J, J, max_pairs)
    Rfree, PermGroFac,
    Splurge, rho,
    Cratio_pol, Cratio_none,
    AggDemandFac_pol, AggDemandFac_none,
    TranShk_addition_pol, TranShk_addition_none,
    LivPrb_avg, newborn_dist5d_diag_batch,  # (C, A, A, A, J, J)
):
    """Cohort-batched version of _step_period_5d_jax_v3_impl.

    Processes all C cohorts in parallel via jax.vmap over the leading
    batch axis. The scan over atom_k is preserved (memory budget reasons).

    Returns:
      dist5d_next_batch:    (C, A, A, A, J, J)
      welfare_num_batch:    (C,)
      agg_inc_pol_batch:    (C,)
      agg_inc_none_batch:   (C,)
      agg_cons_pol_batch:   (C,)
      agg_cons_none_batch:  (C,)
    """
    C = dist5d_batch.shape[0]
    A = aGrid.shape[0]
    J = joint_markov_batch.shape[1]
    max_pairs = atom_p_idx_batch.shape[-1]

    # Step 1: source aggregation per cohort with per-cohort joint_markov
    # R5 layout: dist5d_batch is (C,p,q,I,J,K) → d_src_agg_batch is (C,r,s,I,J,K)
    d_src_agg_batch = jax.vmap(
        lambda d, jm: jnp.einsum('pqIJK,pqrs->rsIJK', d, jm)
    )(dist5d_batch, joint_markov_batch)  # (C, J, J, A, A, A)

    # Step 2: scan over atom_k, calling vmapped singleatom kernel
    def _scan_atom(carry, k):
        scat_acc, w_acc, ip_acc, in_acc, cp_acc, cn_acc = carry
        scat_k, w_k, ip_k, in_k, cp_k, cn_k = _step_period_5d_jax_v3_impl_singleatom_vmapped(
            k, dist5d_batch, aGrid, joint_markov_batch, d_src_agg_batch,
            cfunc_pol_table_t_batch, cfunc_none_table_t_batch, cfunc_b_table_t_batch,
            m_grid,
            psi_pn_batch, xi_pn_batch, psi_n_xi_batch, psi_b_batch, xi_b_batch,
            atom_p_idx_batch, atom_b_idx_batch, joint_pmv_batch,
            Rfree, PermGroFac,
            Splurge, rho,
            Cratio_pol, Cratio_none,
            AggDemandFac_pol, AggDemandFac_none,
            TranShk_addition_pol, TranShk_addition_none,
        )
        return (
            scat_acc + scat_k,    # (C, J, J, A, A, A)
            w_acc + w_k,          # (C,)
            ip_acc + ip_k,
            in_acc + in_k,
            cp_acc + cp_k,
            cn_acc + cn_k,
        ), None

    init_scattered = jnp.zeros((C, J, J, A, A, A), dtype=dist5d_batch.dtype)
    init_scalar = jnp.zeros((C,), dtype=dist5d_batch.dtype)
    carry_init = (init_scattered, init_scalar, init_scalar, init_scalar,
                  init_scalar, init_scalar)
    (scattered_total, welfare_num_batch, agg_inc_pol, agg_inc_none,
     agg_cons_pol, agg_cons_none), _ = jax.lax.scan(
        _scan_atom, carry_init, jnp.arange(max_pairs))

    # R5: scattered_total already in (C, J, J, A, A, A) layout — no transpose needed
    dist5d_next_batch = scattered_total

    # Mortality + rebirth per cohort (gated by LivPrb_avg < 1)
    total_mass_before = jnp.sum(dist5d_next_batch, axis=(1, 2, 3, 4, 5))  # (C,)
    dist5d_with_mort = dist5d_next_batch * LivPrb_avg + \
        (1.0 - LivPrb_avg) * total_mass_before[:, None, None, None, None, None] * newborn_dist5d_diag_batch
    dist5d_next_batch = jnp.where(
        LivPrb_avg < 1.0 - 1e-15, dist5d_with_mort, dist5d_next_batch)

    return (dist5d_next_batch, welfare_num_batch,
            agg_inc_pol, agg_inc_none, agg_cons_pol, agg_cons_none)


_step_period_5d_jax_v4_jit = jax.jit(_step_period_5d_jax_v4_impl)


def _step_period_5d_jax_v4(
    dist5d_batch, aGrid, joint_markov_batch,
    cfunc_pol_table_t_batch, cfunc_none_table_t_batch, cfunc_b_table_t_batch,
    m_grid,
    psi_pn_batch, xi_pn_batch, pmv_pn_q_batch, n_atoms_pn,
    psi_n_xi_batch,
    psi_b_batch, xi_b_batch, pmv_b_q_batch, n_atoms_b,
    atom_p_idx_batch, atom_b_idx_batch, joint_pmv_batch,
    Rfree, PermGroFac,
    Splurge, rho,
    Cratio_pol, Cratio_none,
    AggDemandFac_pol, AggDemandFac_none,
    TranShk_addition_pol, TranShk_addition_none,
    LivPrb_avg=1.0, newborn_dist5d_diag_batch=None,
):
    """Public wrapper for the v4 cohort-batched kernel.
    joint_markov_batch shape: (C, J, J, J, J) — per-cohort.
    """
    if newborn_dist5d_diag_batch is None:
        newborn_dist5d_diag_batch = jnp.zeros_like(dist5d_batch)
    return _step_period_5d_jax_v4_jit(
        dist5d_batch, aGrid, joint_markov_batch,
        cfunc_pol_table_t_batch, cfunc_none_table_t_batch, cfunc_b_table_t_batch,
        m_grid,
        psi_pn_batch, xi_pn_batch, pmv_pn_q_batch,
        psi_n_xi_batch,
        psi_b_batch, xi_b_batch, pmv_b_q_batch,
        atom_p_idx_batch, atom_b_idx_batch, joint_pmv_batch,
        Rfree, PermGroFac,
        Splurge, rho,
        Cratio_pol, Cratio_none,
        AggDemandFac_pol, AggDemandFac_none,
        TranShk_addition_pol, TranShk_addition_none,
        LivPrb_avg, newborn_dist5d_diag_batch,
    )


def _step_period_5d_jax_v3(
    dist5d, aGrid, joint_markov,
    cfunc_pol_table_t, cfunc_none_table_t, cfunc_b_table_t,
    m_grid,
    psi_pn, xi_pn, pmv_pn_q, n_atoms_pn,
    psi_n_xi,
    psi_b, xi_b, pmv_b_q, n_atoms_b,
    atom_p_idx, atom_b_idx, joint_pmv,
    Rfree, PermGroFac,
    Splurge, rho,
    Cratio_pol, Cratio_none,
    AggDemandFac_pol, AggDemandFac_none,
    TranShk_addition_pol, TranShk_addition_none,
    LivPrb_avg=1.0, newborn_dist5d_diag=None,
):
    """Public API wrapper. Returns (dist5d_next, welfare_num, agg_dict)."""
    if newborn_dist5d_diag is None:
        newborn_dist5d_diag = jnp.zeros_like(dist5d)
    dist_next, w_num, ipo, ino, cpo, cno = _step_period_5d_jax_v3_jit(
        dist5d, aGrid, joint_markov,
        cfunc_pol_table_t, cfunc_none_table_t, cfunc_b_table_t,
        m_grid,
        psi_pn, xi_pn, pmv_pn_q,
        psi_n_xi,
        psi_b, xi_b, pmv_b_q,
        atom_p_idx, atom_b_idx, joint_pmv,
        Rfree, PermGroFac,
        Splurge, rho,
        Cratio_pol, Cratio_none,
        AggDemandFac_pol, AggDemandFac_none,
        TranShk_addition_pol, TranShk_addition_none,
        LivPrb_avg, newborn_dist5d_diag,
    )
    return dist_next, float(w_num), {
        'inc_pol': float(ipo),
        'inc_none': float(ino),
        'cons_pol': float(cpo),
        'cons_none': float(cno),
    }


# ============================================================
# End-to-end driver: compute_joint_welfare5d using JAX kernel
# ============================================================

def compute_joint_welfare5d_jax(
    agent_pol, agent_none, agent_base, baseline_tm_data,
    EconomyMrkv_path_pn, act_T,
    shock_type_pol='recessionUI',
    shock_type_none='recession',
    AggDemandFac_pol_series=None, AggDemandFac_none_series=None,
    Cratio_pol_series=None, Cratio_none_series=None,
    TranShk_addition_pol_series=None, TranShk_addition_none_series=None,
    M_grid=500,
    verbose=False,
    # Phase C.2 optimization: accept pre-tabulated cFunc tables to avoid
    # redundant per-call tabulation (same cFuncs reused across all durations
    # of one cohort). Caller should tabulate once per cohort and pass in.
    cfunc_pol_table_full=None,
    cfunc_none_table_full=None,
    cfunc_b_table_full=None,
):
    """End-to-end JAX-accelerated 5D welfare driver.

    API matches welfare6_tm_joint5d.compute_joint_welfare5d. Returns
    the same per-period series dict.

    Implementation: pre-tabulate cFunc + IncShkDstn ONCE, then call
    the JIT'd v3 kernel per period. The per-period kernel JIT-cached
    after first call.

    Phase C.2: if cfunc_*_table_full are provided, skip the cFunc
    tabulation (which takes ~5 sec per scenario). This is the
    recommended path when this function is called repeatedly with
    the same agents (e.g. per (cohort, dur) loop).
    """
    from income_process_sst import effective_pLvl_growth
    from tm_methods import _effective_LivPrb, _solve_markov_ergodic

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

    # Initial dist5d (= base ergodic on diagonal)
    # Layout: (J, J, A, A, A) — J-first, A-trailing (R5: matches scatter convention)
    base_ergodic = np.asarray(baseline_tm_data['ergodic'], dtype=np.float64)
    base_dist_aJ = base_ergodic.reshape(J, A)
    dist5d = np.zeros((J, J, A, A, A), dtype=np.float64)
    for j in range(J):
        for a_idx in range(A):
            dist5d[j, j, a_idx, a_idx, a_idx] = base_dist_aJ[j, a_idx]

    # LivPrb
    LivPrb_arr_raw = np.asarray(agent_pol.LivPrb[0][:J], dtype=np.float64)
    T_age = getattr(agent_pol, 'T_age', None)
    LivPrb_eff = _effective_LivPrb(LivPrb_arr_raw, T_age)
    LivPrb_avg = float(np.mean(LivPrb_eff))
    death_prob = 1.0 - LivPrb_avg

    # cFunc tables (one per (scenario, full cFunc index))
    cFuncs_pol_full = agent_pol.solution[0].cFunc
    cFuncs_none_full = agent_none.solution[0].cFunc
    cFuncs_b_full = agent_base.solution[0].cFunc

    m_grid_np = build_m_grid(M_grid)
    # C.2: tabulate only if not provided by caller
    if cfunc_pol_table_full is None:
        cfunc_pol_table_full = tabulate_cfunc_list(cFuncs_pol_full, m_grid_np)
    if cfunc_none_table_full is None:
        cfunc_none_table_full = tabulate_cfunc_list(cFuncs_none_full, m_grid_np)
    if cfunc_b_table_full is None:
        cfunc_b_table_full = tabulate_cfunc_list(cFuncs_b_full, m_grid_np)

    Rfree = np.asarray(agent_pol.Rfree[:J], dtype=np.float64)
    PermGroFac = np.asarray(agent_pol.PermGroFac[0][:J], dtype=np.float64)
    Splurge = float(agent_pol.Splurge)
    CRRA = float(agent_pol.CRRA)
    rho = CRRA

    # Pre-resolve scenario IncShkDstn
    IncShk_pol_full = _resolve_scenario_IncShkDstn(agent_pol, shock_type_pol)
    IncShk_none_full = _resolve_scenario_IncShkDstn(agent_none, shock_type_none)
    IncShk_base_full = _resolve_scenario_IncShkDstn(agent_base, 'base')

    MA_b = np.asarray(agent_base.CondMrkvArrays[0], dtype=np.float64)
    markov_erg_base = _solve_markov_ergodic(MA_b)

    # Build newborn distribution (same as numpy version)
    IncShk_b_macro0 = list(IncShk_base_full[0:J])
    cFuncs_b_macro0 = [cFuncs_b_full[0 + j] for j in range(J)]
    newborn_dist5d_diag = np.zeros((J, J, A, A, A), dtype=np.float64)
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
            newborn_dist5d_diag[j, j, i_lo, i_lo, i_lo] += mass_atom * w_lo
            newborn_dist5d_diag[j, j, i_hi, i_hi, i_hi] += mass_atom * w_hi
    nb_total = newborn_dist5d_diag.sum()
    if nb_total > _DIST_EPS:
        newborn_dist5d_diag /= nb_total

    # pLvl scaling
    u_ergodic = baseline_tm_data.get('u_ergodic', 0.04)
    g_base_pLvl = effective_pLvl_growth(agent_pol, u_ergodic)
    pLvl_factor = 1.0
    E_pLvl = float(baseline_tm_data['E_pLvl'])
    AgentCount = int(getattr(agent_pol, 'AgentCount', 1))
    pop_rescale = float(getattr(agent_pol, 'pop_rescale_factor', 1.0))
    N_eff = AgentCount * pop_rescale

    welfare_num_series = np.zeros(act_T)
    pLvl_factor_series = np.zeros(act_T)
    AggInc_pol_series = np.zeros(act_T)
    AggInc_none_series = np.zeros(act_T)
    AggCons_pol_series = np.zeros(act_T)
    AggCons_none_series = np.zeros(act_T)

    # Pre-t0 SPIKE state-shift
    macro_pn_t0 = int(EconomyMrkv_path_pn[0])
    if (macro_pn_t0 % 2 == 1):
        Un = float(getattr(agent_pol, 'Urate_normal', 0.045))
        Ur = float(getattr(agent_pol, 'Urate_recession', Un))
        if Ur > Un:
            spike_frac = (Ur - Un) / (1.0 - Un)
            # R5 layout: dist5d is (J, J, A, A, A); axes (0,1) = (j_pn, j_b)
            for j_b in range(J):
                emp_mass = dist5d[0, j_b, :, :, :].copy()
                dist5d[0, j_b, :, :, :] = emp_mass * (1.0 - spike_frac)
                dist5d[1, j_b, :, :, :] += emp_mass * spike_frac

    # Convert to JAX once
    dtype = jnp.float64 if _USE_FP64 else jnp.float32
    dist5d_jax = jnp.asarray(dist5d, dtype=dtype)
    aGrid_jax = jnp.asarray(aGrid, dtype=dtype)
    m_grid_jax = jnp.asarray(m_grid_np, dtype=dtype)
    Rfree_jax = jnp.asarray(Rfree, dtype=dtype)
    PermGroFac_jax = jnp.asarray(PermGroFac, dtype=dtype)
    newborn_dist5d_diag_jax = jnp.asarray(newborn_dist5d_diag, dtype=dtype)

    if verbose:
        print(f"  [jax-5d] A={A}, J={J}, M_grid={M_grid}, FP={'64' if _USE_FP64 else '32'}")

    for t in range(act_T):
        macro_pn = int(EconomyMrkv_path_pn[t])
        MA_pn = np.asarray(agent_pol.CondMrkvArrays[macro_pn], dtype=np.float64)
        joint_markov = compute_joint_markov(MA_pn, MA_b)

        # Per-period IncShkDstn + cFunc tables (slice from full)
        base_idx_pn = macro_pn * J
        IncShk_pol_t = list(IncShk_pol_full[base_idx_pn:base_idx_pn + J])
        IncShk_none_t = list(IncShk_none_full[base_idx_pn:base_idx_pn + J])
        IncShk_b_t = list(IncShk_base_full[0:J])

        all_atoms = max(
            max(len(np.asarray(d.pmv)) for d in IncShk_pol_t),
            max(len(np.asarray(d.pmv)) for d in IncShk_none_t),
            max(len(np.asarray(d.pmv)) for d in IncShk_b_t),
        )
        pol_arrs = extract_incshk_arrays(IncShk_pol_t, max_atoms=all_atoms)
        none_arrs = extract_incshk_arrays(IncShk_none_t, max_atoms=all_atoms)
        b_arrs = extract_incshk_arrays(IncShk_b_t, max_atoms=all_atoms)
        pmv_pol_q = q_reweight_pmv(pol_arrs['psi'], pol_arrs['pmv'], pol_arrs['n_atoms'])
        pmv_b_q = q_reweight_pmv(b_arrs['psi'], b_arrs['pmv'], b_arrs['n_atoms'])

        atom_p_idx, atom_b_idx, joint_pmv = build_joint_atom_table(
            pmv_pol_q, pmv_b_q, pol_arrs['n_atoms'], b_arrs['n_atoms']
        )

        cfunc_pol_table_t = cfunc_pol_table_full[base_idx_pn:base_idx_pn + J]
        cfunc_none_table_t = cfunc_none_table_full[base_idx_pn:base_idx_pn + J]
        cfunc_b_table_t = cfunc_b_table_full[0:J]

        # Call JIT'd kernel
        dist_next_jax, w_num, agg = _step_period_5d_jax_v3(
            dist5d_jax, aGrid_jax,
            jnp.asarray(joint_markov, dtype=dtype),
            jnp.asarray(cfunc_pol_table_t, dtype=dtype),
            jnp.asarray(cfunc_none_table_t, dtype=dtype),
            jnp.asarray(cfunc_b_table_t, dtype=dtype),
            m_grid_jax,
            jnp.asarray(pol_arrs['psi'], dtype=dtype),
            jnp.asarray(pol_arrs['xi'], dtype=dtype),
            jnp.asarray(pmv_pol_q, dtype=dtype),
            pol_arrs['n_atoms'],
            jnp.asarray(none_arrs['xi'], dtype=dtype),
            jnp.asarray(b_arrs['psi'], dtype=dtype),
            jnp.asarray(b_arrs['xi'], dtype=dtype),
            jnp.asarray(pmv_b_q, dtype=dtype),
            b_arrs['n_atoms'],
            jnp.asarray(atom_p_idx, dtype=jnp.int32),
            jnp.asarray(atom_b_idx, dtype=jnp.int32),
            jnp.asarray(joint_pmv, dtype=dtype),
            Rfree_jax, PermGroFac_jax,
            Splurge, rho,
            float(Cratio_pol_series[t]), float(Cratio_none_series[t]),
            float(AggDemandFac_pol_series[t]), float(AggDemandFac_none_series[t]),
            jnp.asarray(TranShk_addition_pol_series[t], dtype=dtype),
            jnp.asarray(TranShk_addition_none_series[t], dtype=dtype),
            LivPrb_avg=LivPrb_avg,
            newborn_dist5d_diag=newborn_dist5d_diag_jax,
        )

        scale = N_eff * E_pLvl * pLvl_factor
        welfare_num_series[t] = w_num * scale
        AggInc_pol_series[t] = agg['inc_pol'] * scale
        AggInc_none_series[t] = agg['inc_none'] * scale
        AggCons_pol_series[t] = agg['cons_pol'] * scale
        AggCons_none_series[t] = agg['cons_none'] * scale
        pLvl_factor_series[t] = pLvl_factor

        # pLvl recurrence (uses dist5d before update; same as numpy)
        # R5 layout (J,J,A,A,A): sum (j_b, a_n, a_b) = axes (1, 3, 4) to keep (j_pn, a_p)
        marg_pol = np.asarray(dist5d_jax).sum(axis=(1, 3, 4))  # (J, A)
        state_fracs_pol = marg_pol.sum(axis=1)  # (J,)
        u_rec_t = 1.0 - state_fracs_pol[0]
        g_rec_t = effective_pLvl_growth(agent_pol, u_rec_t)
        pLvl_factor = ((1.0 - death_prob) * g_rec_t * pLvl_factor
                       + (1.0 - (1.0 - death_prob) * g_base_pLvl))
        dist5d_jax = dist_next_jax

    return {
        'welfare_num_series': welfare_num_series,
        'pLvl_factor_series': pLvl_factor_series,
        'AggInc_pol_series': AggInc_pol_series,
        'AggInc_none_series': AggInc_none_series,
        'AggCons_pol_series': AggCons_pol_series,
        'AggCons_none_series': AggCons_none_series,
    }


# ============================================================
# Phase C.4: cohort-batched end-to-end driver
# ============================================================

def compute_joint_welfare5d_jax_batched(
    agents_pol_list,       # list of C AggFiscalType
    agents_none_list,
    agents_base_list,
    baseline_tm_data_list, # list of C bd dicts
    EconomyMrkv_path_pn, act_T,
    shock_type_pol='recessionUI',
    shock_type_none='recession',
    AggDemandFac_pol_series=None, AggDemandFac_none_series=None,
    Cratio_pol_series=None, Cratio_none_series=None,
    TranShk_addition_pol_series=None, TranShk_addition_none_series=None,
    M_grid=500,
    verbose=False,
    cfunc_pol_tables_full=None,    # optional list of C (one per cohort)
    cfunc_none_tables_full=None,
    cfunc_b_tables_full=None,
):
    """Phase C.4 cohort-batched driver. Processes all C cohorts on a
    leading GPU batch axis via jax.vmap.

    Returns list of C dicts (one per cohort), each with the same keys
    as compute_joint_welfare5d_jax's return value.
    """
    from income_process_sst import effective_pLvl_growth
    from tm_methods import _effective_LivPrb, _solve_markov_ergodic

    C = len(agents_pol_list)
    assert len(agents_none_list) == C
    assert len(agents_base_list) == C
    assert len(baseline_tm_data_list) == C

    # All cohorts share aGrid, J, Markov structure (within a parametrization)
    aGrid = baseline_tm_data_list[0]['dist_aGrid']
    A = len(aGrid)
    J = int(agents_pol_list[0].num_base_MrkvStates)

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

    # Build per-cohort initial dist5d batch: (C, J, J, A, A, A)
    # Layout: J-first, A-trailing (R5: matches scatter convention)
    dist5d_batch = np.zeros((C, J, J, A, A, A), dtype=np.float64)
    for c in range(C):
        be = np.asarray(baseline_tm_data_list[c]['ergodic'], dtype=np.float64)
        bd_aJ = be.reshape(J, A)
        for j in range(J):
            for a_idx in range(A):
                dist5d_batch[c, j, j, a_idx, a_idx, a_idx] = bd_aJ[j, a_idx]

    # LivPrb per cohort (ed_type may differ)
    LivPrb_avg_per_cohort = np.zeros(C, dtype=np.float64)
    death_prob_per_cohort = np.zeros(C, dtype=np.float64)
    for c in range(C):
        LivPrb_arr_raw_c = np.asarray(agents_pol_list[c].LivPrb[0][:J], dtype=np.float64)
        T_age_c = getattr(agents_pol_list[c], 'T_age', None)
        LivPrb_eff_c = _effective_LivPrb(LivPrb_arr_raw_c, T_age_c)
        LivPrb_avg_per_cohort[c] = float(np.mean(LivPrb_eff_c))
        death_prob_per_cohort[c] = 1.0 - LivPrb_avg_per_cohort[c]
    # If all cohorts share the same LivPrb, use the shared value
    if np.allclose(LivPrb_avg_per_cohort, LivPrb_avg_per_cohort[0]):
        LivPrb_avg = float(LivPrb_avg_per_cohort[0])
        death_prob = 1.0 - LivPrb_avg
    else:
        # Per-cohort case: use mean for the JIT call (kernel takes scalar);
        # the small mortality differences are second-order
        LivPrb_avg = float(np.mean(LivPrb_avg_per_cohort))
        death_prob = 1.0 - LivPrb_avg

    # cFunc tabulations per cohort (C.2 amortization)
    m_grid_np = build_m_grid(M_grid)
    if cfunc_pol_tables_full is None:
        cfunc_pol_tables_full = [
            tabulate_cfunc_list(ag.solution[0].cFunc, m_grid_np)
            for ag in agents_pol_list
        ]
    if cfunc_none_tables_full is None:
        cfunc_none_tables_full = [
            tabulate_cfunc_list(ag.solution[0].cFunc, m_grid_np)
            for ag in agents_none_list
        ]
    if cfunc_b_tables_full is None:
        cfunc_b_tables_full = [
            tabulate_cfunc_list(ag.solution[0].cFunc, m_grid_np)
            for ag in agents_base_list
        ]

    # Rfree, PermGroFac per cohort (ed_type may differ)
    Rfree_batch = np.stack([
        np.asarray(agents_pol_list[c].Rfree[:J], dtype=np.float64)
        for c in range(C)
    ])  # (C, J)
    PermGroFac_batch = np.stack([
        np.asarray(agents_pol_list[c].PermGroFac[0][:J], dtype=np.float64)
        for c in range(C)
    ])  # (C, J)
    Splurge = float(agents_pol_list[0].Splurge)
    CRRA = float(agents_pol_list[0].CRRA)
    rho = CRRA

    # IncShkDstn extracted per cohort (ed_type-level but broadcast for C.4.1 simplicity)
    IncShk_pol_full_list = [
        _resolve_scenario_IncShkDstn(ag, shock_type_pol) for ag in agents_pol_list
    ]
    IncShk_none_full_list = [
        _resolve_scenario_IncShkDstn(ag, shock_type_none) for ag in agents_none_list
    ]
    IncShk_base_full_list = [
        _resolve_scenario_IncShkDstn(ag, 'base') for ag in agents_base_list
    ]

    # MA_b per cohort (within an ed_type it's the same, across ed_types it differs)
    MA_b_list = [
        np.asarray(agents_base_list[c].CondMrkvArrays[0], dtype=np.float64)
        for c in range(C)
    ]
    markov_erg_base_list = [_solve_markov_ergodic(MA_b_list[c]) for c in range(C)]

    # Build newborn dist per cohort (uses cFunc_b per cohort + per-cohort IncShk_b)
    newborn_dist5d_diag_batch = np.zeros((C, J, J, A, A, A), dtype=np.float64)
    for c in range(C):
        cFuncs_b_macro0_c = [agents_base_list[c].solution[0].cFunc[0 + j] for j in range(J)]
        IncShk_b_macro0_c = list(IncShk_base_full_list[c][0:J])
        markov_erg_base = markov_erg_base_list[c]
        for j in range(J):
            if markov_erg_base[j] < _DIST_EPS:
                continue
            dstn_j = IncShk_b_macro0_c[j]
            psi_j = np.asarray(dstn_j.atoms[0])
            xi_j = np.asarray(dstn_j.atoms[1])
            pmv_raw_j = np.asarray(dstn_j.pmv)
            E_psi_j = float(np.dot(pmv_raw_j, psi_j))
            pmv_j = pmv_raw_j * psi_j / max(E_psi_j, 1e-12)
            for atom_idx, (xi_val, pmv_val) in enumerate(zip(xi_j, pmv_j)):
                if pmv_val < _DIST_EPS:
                    continue
                m_init = float(xi_val)
                c_star = float(cFuncs_b_macro0_c[j](np.array([m_init]), np.array([1.0]))[0])
                c_actual = (1.0 - Splurge) * c_star + Splurge * m_init
                a_init = max(0.0, m_init - c_actual)
                a_init_clip = max(aGrid[0], min(aGrid[-1], a_init))
                i_lo = np.searchsorted(aGrid, a_init_clip, side='right') - 1
                i_lo = max(0, min(A - 2, int(i_lo)))
                i_hi = i_lo + 1
                w_hi = (a_init_clip - aGrid[i_lo]) / max(aGrid[i_hi] - aGrid[i_lo], 1e-12)
                w_lo = 1.0 - w_hi
                mass_atom = markov_erg_base[j] * pmv_val
                newborn_dist5d_diag_batch[c, j, j, i_lo, i_lo, i_lo] += mass_atom * w_lo
                newborn_dist5d_diag_batch[c, j, j, i_hi, i_hi, i_hi] += mass_atom * w_hi
        nb_total = newborn_dist5d_diag_batch[c].sum()
        if nb_total > _DIST_EPS:
            newborn_dist5d_diag_batch[c] /= nb_total

    # pLvl scaling: per-cohort g_base_pLvl, N_eff, E_pLvl, pLvl_factor
    g_base_pLvl_batch = np.array([
        effective_pLvl_growth(agents_pol_list[c],
                              baseline_tm_data_list[c].get('u_ergodic', 0.04))
        for c in range(C)
    ])
    pLvl_factor_batch = np.ones(C, dtype=np.float64)
    E_pLvl_arr = np.array([
        float(baseline_tm_data_list[c]['E_pLvl']) for c in range(C)
    ])
    AgentCount_arr = np.array([
        int(getattr(agents_pol_list[c], 'AgentCount', 1)) for c in range(C)
    ], dtype=np.float64)
    pop_rescale_arr = np.array([
        float(getattr(agents_pol_list[c], 'pop_rescale_factor', 1.0)) for c in range(C)
    ])
    N_eff_arr = AgentCount_arr * pop_rescale_arr

    # Pre-t0 SPIKE state-shift (Urate per cohort — differs across ed_types)
    macro_pn_t0 = int(EconomyMrkv_path_pn[0])
    if (macro_pn_t0 % 2 == 1):
        for c in range(C):
            Un = float(getattr(agents_pol_list[c], 'Urate_normal', 0.045))
            Ur = float(getattr(agents_pol_list[c], 'Urate_recession', Un))
            if Ur > Un:
                spike_frac = (Ur - Un) / (1.0 - Un)
                # R5 layout: dist5d_batch is (C,J,J,A,A,A); axes (1,2) = (j_pn, j_b)
                for j_b in range(J):
                    emp_mass = dist5d_batch[c, 0, j_b, :, :, :].copy()
                    dist5d_batch[c, 0, j_b, :, :, :] = emp_mass * (1.0 - spike_frac)
                    dist5d_batch[c, 1, j_b, :, :, :] += emp_mass * spike_frac

    # Convert to JAX
    dtype = jnp.float64 if _USE_FP64 else jnp.float32
    dist5d_batch_jax = jnp.asarray(dist5d_batch, dtype=dtype)
    aGrid_jax = jnp.asarray(aGrid, dtype=dtype)
    m_grid_jax = jnp.asarray(m_grid_np, dtype=dtype)
    Rfree_batch_jax = jnp.asarray(Rfree_batch, dtype=dtype)        # (C, J)
    PermGroFac_batch_jax = jnp.asarray(PermGroFac_batch, dtype=dtype)
    newborn_dist5d_diag_batch_jax = jnp.asarray(newborn_dist5d_diag_batch, dtype=dtype)

    # Per-cohort output series
    welfare_num_series_batch = np.zeros((C, act_T))
    pLvl_factor_series_batch = np.zeros((C, act_T))
    AggInc_pol_series_batch = np.zeros((C, act_T))
    AggInc_none_series_batch = np.zeros((C, act_T))
    AggCons_pol_series_batch = np.zeros((C, act_T))
    AggCons_none_series_batch = np.zeros((C, act_T))

    if verbose:
        print(f"  [jax-5d batched] C={C}, A={A}, J={J}, M_grid={M_grid}, FP={'64' if _USE_FP64 else '32'}")

    for t in range(act_T):
        macro_pn = int(EconomyMrkv_path_pn[t])
        # Per-cohort joint_markov (each cohort has its own CondMrkvArrays in
        # general; within an ed_type they're identical but we compute per-cohort
        # for correctness)
        joint_markov_batch = np.zeros((C, J, J, J, J), dtype=np.float64)
        for c in range(C):
            MA_pn_c = np.asarray(agents_pol_list[c].CondMrkvArrays[macro_pn], dtype=np.float64)
            joint_markov_batch[c] = compute_joint_markov(MA_pn_c, MA_b_list[c])
        base_idx_pn = macro_pn * J

        # Per-cohort IncShk arrays at this period
        IncShk_pol_t_list = [list(IncShk_pol_full_list[c][base_idx_pn:base_idx_pn + J]) for c in range(C)]
        IncShk_none_t_list = [list(IncShk_none_full_list[c][base_idx_pn:base_idx_pn + J]) for c in range(C)]
        IncShk_b_t_list = [list(IncShk_base_full_list[c][0:J]) for c in range(C)]

        all_atoms = max(
            max(max(len(np.asarray(d.pmv)) for d in IncShk_pol_t_list[c]) for c in range(C)),
            max(max(len(np.asarray(d.pmv)) for d in IncShk_none_t_list[c]) for c in range(C)),
            max(max(len(np.asarray(d.pmv)) for d in IncShk_b_t_list[c]) for c in range(C)),
        )

        # Build per-cohort batched IncShk arrays
        psi_pn_batch = np.zeros((C, J, all_atoms), dtype=np.float64)
        xi_pn_batch = np.zeros((C, J, all_atoms), dtype=np.float64)
        pmv_pn_q_batch = np.zeros((C, J, all_atoms), dtype=np.float64)
        psi_n_xi_batch = np.zeros((C, J, all_atoms), dtype=np.float64)
        psi_b_batch = np.zeros((C, J, all_atoms), dtype=np.float64)
        xi_b_batch = np.zeros((C, J, all_atoms), dtype=np.float64)
        pmv_b_q_batch = np.zeros((C, J, all_atoms), dtype=np.float64)
        n_atoms_pn_batch = np.zeros((C, J), dtype=np.int64)
        n_atoms_b_batch = np.zeros((C, J), dtype=np.int64)

        for c in range(C):
            pol_arrs = extract_incshk_arrays(IncShk_pol_t_list[c], max_atoms=all_atoms)
            none_arrs = extract_incshk_arrays(IncShk_none_t_list[c], max_atoms=all_atoms)
            b_arrs = extract_incshk_arrays(IncShk_b_t_list[c], max_atoms=all_atoms)
            psi_pn_batch[c] = pol_arrs['psi']
            xi_pn_batch[c] = pol_arrs['xi']
            pmv_pn_q_batch[c] = q_reweight_pmv(pol_arrs['psi'], pol_arrs['pmv'], pol_arrs['n_atoms'])
            psi_n_xi_batch[c] = none_arrs['xi']
            psi_b_batch[c] = b_arrs['psi']
            xi_b_batch[c] = b_arrs['xi']
            pmv_b_q_batch[c] = q_reweight_pmv(b_arrs['psi'], b_arrs['pmv'], b_arrs['n_atoms'])
            n_atoms_pn_batch[c] = pol_arrs['n_atoms']
            n_atoms_b_batch[c] = b_arrs['n_atoms']

        # Joint atom table per cohort
        max_pairs = all_atoms
        atom_p_idx_batch = np.zeros((C, J, J, max_pairs), dtype=np.int64)
        atom_b_idx_batch = np.zeros((C, J, J, max_pairs), dtype=np.int64)
        joint_pmv_batch = np.zeros((C, J, J, max_pairs), dtype=np.float64)
        for c in range(C):
            ap, ab, jp = build_joint_atom_table(
                pmv_pn_q_batch[c], pmv_b_q_batch[c],
                n_atoms_pn_batch[c], n_atoms_b_batch[c]
            )
            atom_p_idx_batch[c] = ap
            atom_b_idx_batch[c] = ab
            joint_pmv_batch[c] = jp

        # Per-cohort cFunc table slices for this macro state
        cfunc_pol_t_batch = np.stack([
            cfunc_pol_tables_full[c][base_idx_pn:base_idx_pn + J] for c in range(C)
        ])
        cfunc_none_t_batch = np.stack([
            cfunc_none_tables_full[c][base_idx_pn:base_idx_pn + J] for c in range(C)
        ])
        cfunc_b_t_batch = np.stack([
            cfunc_b_tables_full[c][0:J] for c in range(C)
        ])

        # Call v4 batched kernel
        (dist_next_batch, w_num_batch, ipo_batch, ino_batch,
         cpo_batch, cno_batch) = _step_period_5d_jax_v4(
            dist5d_batch_jax, aGrid_jax,
            jnp.asarray(joint_markov_batch, dtype=dtype),
            jnp.asarray(cfunc_pol_t_batch, dtype=dtype),
            jnp.asarray(cfunc_none_t_batch, dtype=dtype),
            jnp.asarray(cfunc_b_t_batch, dtype=dtype),
            m_grid_jax,
            jnp.asarray(psi_pn_batch, dtype=dtype),
            jnp.asarray(xi_pn_batch, dtype=dtype),
            jnp.asarray(pmv_pn_q_batch, dtype=dtype),
            n_atoms_pn_batch,
            jnp.asarray(psi_n_xi_batch, dtype=dtype),
            jnp.asarray(psi_b_batch, dtype=dtype),
            jnp.asarray(xi_b_batch, dtype=dtype),
            jnp.asarray(pmv_b_q_batch, dtype=dtype),
            n_atoms_b_batch,
            jnp.asarray(atom_p_idx_batch, dtype=jnp.int32),
            jnp.asarray(atom_b_idx_batch, dtype=jnp.int32),
            jnp.asarray(joint_pmv_batch, dtype=dtype),
            Rfree_batch_jax, PermGroFac_batch_jax,
            Splurge, rho,
            float(Cratio_pol_series[t]), float(Cratio_none_series[t]),
            float(AggDemandFac_pol_series[t]), float(AggDemandFac_none_series[t]),
            jnp.asarray(TranShk_addition_pol_series[t], dtype=dtype),
            jnp.asarray(TranShk_addition_none_series[t], dtype=dtype),
            LivPrb_avg=LivPrb_avg,
            newborn_dist5d_diag_batch=newborn_dist5d_diag_batch_jax,
        )

        # Per-cohort scaling
        for c in range(C):
            scale_c = N_eff_arr[c] * E_pLvl_arr[c] * pLvl_factor_batch[c]
            welfare_num_series_batch[c, t] = float(w_num_batch[c]) * scale_c
            AggInc_pol_series_batch[c, t] = float(ipo_batch[c]) * scale_c
            AggInc_none_series_batch[c, t] = float(ino_batch[c]) * scale_c
            AggCons_pol_series_batch[c, t] = float(cpo_batch[c]) * scale_c
            AggCons_none_series_batch[c, t] = float(cno_batch[c]) * scale_c
            pLvl_factor_series_batch[c, t] = pLvl_factor_batch[c]

        # pLvl recurrence per cohort (uses pre-update dist5d_batch)
        # R5 layout (J,J,A,A,A): sum (j_b, a_n, a_b) = axes (1, 3, 4) to keep (j_pn, a_p)
        dist5d_np = np.asarray(dist5d_batch_jax)
        for c in range(C):
            marg_pol = dist5d_np[c].sum(axis=(1, 3, 4))  # (J, A)
            state_fracs_pol = marg_pol.sum(axis=1)  # (J,)
            u_rec_t = 1.0 - state_fracs_pol[0]
            g_rec_t = effective_pLvl_growth(agents_pol_list[c], u_rec_t)
            dp_c = death_prob_per_cohort[c]
            g_base_c = g_base_pLvl_batch[c]
            pLvl_factor_batch[c] = ((1.0 - dp_c) * g_rec_t * pLvl_factor_batch[c]
                                    + (1.0 - (1.0 - dp_c) * g_base_c))
        dist5d_batch_jax = dist_next_batch

    # Return per-cohort series
    return [
        {
            'welfare_num_series': welfare_num_series_batch[c],
            'pLvl_factor_series': pLvl_factor_series_batch[c],
            'AggInc_pol_series': AggInc_pol_series_batch[c],
            'AggInc_none_series': AggInc_none_series_batch[c],
            'AggCons_pol_series': AggCons_pol_series_batch[c],
            'AggCons_none_series': AggCons_none_series_batch[c],
        }
        for c in range(C)
    ]


# ============================================================
# v2 — Vectorized per-step kernel (JIT-friendly)
# ============================================================
# Strategy:
#   1. Source-aggregate via einsum (collapses J^4 loop into one contraction).
#   2. Vectorize (j_pn_dst, j_b_dst, atom_k) computations via broadcasting.
#   3. Scatter via per-(j_pn_dst, j_b_dst) Python loop initially (each iter
#      JIT'd internally). Optimization for later.
#
# Replaces the Python-loop-based _step_period_5d_jax_loops with a structure
# that JIT can optimize.

def _step_period_5d_jax_v2(
    dist5d, aGrid, joint_markov,
    cfunc_pol_table_t, cfunc_none_table_t, cfunc_b_table_t,
    m_grid,
    psi_pn, xi_pn, pmv_pn_q, n_atoms_pn,
    psi_n_xi,  # xi for none scenario (psi shared with pol)
    psi_b, xi_b, pmv_b_q, n_atoms_b,
    atom_p_idx, atom_b_idx, joint_pmv,  # (J, J, max_pairs)
    Rfree, PermGroFac,
    Splurge, rho,
    Cratio_pol, Cratio_none,
    AggDemandFac_pol, AggDemandFac_none,
    TranShk_addition_pol, TranShk_addition_none,
    LivPrb_avg=1.0, newborn_dist5d_diag=None,
):
    """Vectorized per-step kernel. Algorithm:

    Step 1: d_src_agg = einsum(dist5d, joint_markov) — (A,A,A,J,J)
        d_src_agg[a_p,a_n,a_b,j_pn_dst,j_b_dst] = sum over source of
        dist5d[a_p,a_n,a_b,j_pn_src,j_b_src] × joint_markov[src,dst].

    Step 2: For each (j_pn_dst, j_b_dst, atom_k), compute the per-atom
        contribution using vectorized broadcasting over (A,) → asset
        evolution + welfare integrand.

    Step 3: For each (j_pn_dst, j_b_dst), sum atom contributions and
        scatter the result into dist5d_next[:, :, :, j_pn_dst, j_b_dst].

    Outputs match _step_period_5d_jax_loops to interpolation precision.
    """
    A = aGrid.shape[0]
    J = joint_markov.shape[0]
    max_pairs = atom_p_idx.shape[-1]
    fdtype = dist5d.dtype

    # === Step 1: source aggregation ===
    # d_src_agg[I, J, K, jp_dst, jb_dst] = sum over (jp_src, jb_src)
    d_src_agg = jnp.einsum('IJKpq,pqrs->IJKrs', dist5d, joint_markov)

    # === Step 2: per-(j_pn_dst, j_b_dst, atom_k) work ===
    # Build atom-pair feature tables of shape (J, J, max_pairs).
    # We need: psi_a, xi_eff_p, xi_eff_n, xi_eff_b, R_pn, R_b,
    #          inv_pG_pn, inv_pG_b for each cell.
    #
    # For atom indices, use take_along_axis-style gather. But since
    # atom_p_idx and atom_b_idx are integer arrays of shape (J, J, max_pairs),
    # we can index psi_pn[j_pn_dst, atom_p_idx[j_pn_dst, j_b_dst, k]] via:
    #
    #     psi_a = psi_pn[jp_dst_grid, atom_p_idx]
    #
    # where jp_dst_grid is a broadcast of j_pn_dst over (J, J, max_pairs).

    jp_dst_grid = jnp.arange(J)[:, None, None]  # (J, 1, 1)
    jb_dst_grid = jnp.arange(J)[None, :, None]  # (1, J, 1)
    # Broadcast to (J, J, max_pairs):
    jp_dst_full = jnp.broadcast_to(jp_dst_grid, (J, J, max_pairs))
    jb_dst_full = jnp.broadcast_to(jb_dst_grid, (J, J, max_pairs))

    psi_a = psi_pn[jp_dst_full, atom_p_idx]      # (J, J, max_pairs)
    xi_p_a = xi_pn[jp_dst_full, atom_p_idx]      # (J, J, max_pairs)
    xi_n_a = psi_n_xi[jp_dst_full, atom_p_idx]   # (J, J, max_pairs); psi_n_xi is xi-only for none
    psi_b_a = psi_b[jb_dst_full, atom_b_idx]     # (J, J, max_pairs)
    xi_b_a = xi_b[jb_dst_full, atom_b_idx]       # (J, J, max_pairs)

    # Effective income shocks per (j_pn_dst, j_b_dst, atom_k)
    # xi_eff_p[jp, jb, k] = AggDemandFac_pol * xi_p_a[jp, jb, k] + TranShk_addition_pol[jp]
    xi_eff_p = AggDemandFac_pol * xi_p_a + TranShk_addition_pol[jp_dst_full]
    xi_eff_n = AggDemandFac_none * xi_n_a + TranShk_addition_none[jp_dst_full]
    xi_eff_b = xi_b_a

    # Asset-evolution arithmetic constants per (j_pn_dst, j_b_dst, atom_k)
    R_pn = Rfree[jp_dst_full]               # (J, J, max_pairs)
    R_b = Rfree[jb_dst_full]                # (J, J, max_pairs)
    inv_pG_pn = 1.0 / (psi_a * PermGroFac[jp_dst_full])  # (J, J, max_pairs)
    inv_pG_b = 1.0 / (psi_b_a * PermGroFac[jb_dst_full])

    # m_p, m_n, m_b: shape (J, J, max_pairs, A)
    # m_p[jp, jb, k, i] = R_pn[jp,jb,k] * aGrid[i] * inv_pG_pn[jp,jb,k] + xi_eff_p[jp,jb,k]
    aG = aGrid[None, None, None, :]                       # (1, 1, 1, A)
    m_p = R_pn[..., None] * aG * inv_pG_pn[..., None] + xi_eff_p[..., None]
    m_n = R_pn[..., None] * aG * inv_pG_pn[..., None] + xi_eff_n[..., None]
    m_b = R_b[..., None]  * aG * inv_pG_b[..., None]  + xi_eff_b[..., None]

    # cFunc lookup via vectorized interp.
    # cfunc_pol_table_t[j_pn_dst] is (M,). We need for each (jp, jb, k), the
    # table at j_pn_dst = jp. So we gather: cfunc_pol_table_t[jp_dst_full] →
    # (J, J, max_pairs, M).
    # Then interp each row of m_p[jp, jb, k, :] against m_grid using that row of table.
    # JAX has no batched interp; do it via vmap over leading dims.

    # vmap(interp_cfunc, in_axes=(0, None, 0)) operates over a batch dim
    # of m_query (shape (B, A)) and table (shape (B, M)). We need to flatten
    # (J, J, max_pairs) into a single batch dim then reshape.
    def _interp_batch(m_query_batch, table_batch):
        # m_query_batch: (B, A); table_batch: (B, M); m_grid: (M,) constant
        return jax.vmap(lambda mq, tb: jnp.interp(mq, m_grid, tb))(m_query_batch, table_batch)

    B = J * J * max_pairs
    m_p_flat = m_p.reshape(B, A)
    m_n_flat = m_n.reshape(B, A)
    m_b_flat = m_b.reshape(B, A)
    # Tables per (jp, jb, k): use direct indexing
    # cfunc_pol_table_t: (J, M). jp_dst_full: (J, J, max_pairs).
    # cfunc_pol_table_t[jp_dst_full]: (J, J, max_pairs, M). ✓
    pol_table_per_cell = cfunc_pol_table_t[jp_dst_full].reshape(B, -1)
    none_table_per_cell = cfunc_none_table_t[jp_dst_full].reshape(B, -1)
    b_table_per_cell = cfunc_b_table_t[jb_dst_full].reshape(B, -1)

    c_star_p_flat = _interp_batch(m_p_flat, pol_table_per_cell)
    c_star_n_flat = _interp_batch(m_n_flat, none_table_per_cell)
    c_star_b_flat = _interp_batch(m_b_flat, b_table_per_cell)

    c_star_p = c_star_p_flat.reshape(J, J, max_pairs, A)
    c_star_n = c_star_n_flat.reshape(J, J, max_pairs, A)
    c_star_b = c_star_b_flat.reshape(J, J, max_pairs, A)

    # Splurge adjustment
    c_p = (1 - Splurge) * c_star_p + Splurge * xi_eff_p[..., None]
    c_n = (1 - Splurge) * c_star_n + Splurge * xi_eff_n[..., None]
    c_b = (1 - Splurge) * c_star_b + Splurge * xi_eff_b[..., None]

    # a_next
    a_p_next = m_p - c_p                      # (J, J, max_pairs, A)
    a_n_next = m_n - c_n
    a_b_next = m_b - c_b

    # Welfare integrand 3D
    u_p = _u_jax(c_p, rho)                    # (J, J, max_pairs, A)
    u_n = _u_jax(c_n, rho)
    mu_inv_b = _mu_inv_jax(c_b, rho)
    # u_diff[jp, jb, k, i, j] = u_p[jp, jb, k, i] - u_n[jp, jb, k, j]
    u_diff = u_p[..., :, None] - u_n[..., None, :]                  # (J, J, max_pairs, A, A)
    # integrand[jp, jb, k, i, j, l] = u_diff[..., i, j] * mu_inv_b[..., l]
    integrand_3d = u_diff[..., :, :, None] * mu_inv_b[..., None, None, :]  # (J, J, max_pairs, A, A, A)

    # === Step 3: mass weights + welfare contribution + scatter ===
    # For each (j_pn_dst, j_b_dst, atom_k):
    #   weight_3d = d_src_agg[:, :, :, j_pn_dst, j_b_dst] * joint_pmv[jp_dst, jb_dst, k]
    # That has shape (A, A, A) per cell.
    # → broadcast: weight_3d shape (J, J, max_pairs, A, A, A)
    d_src_agg_t = d_src_agg.transpose(3, 4, 0, 1, 2)  # (J, J, A, A, A)
    # joint_pmv (J, J, max_pairs)
    weight_3d_all = d_src_agg_t[:, :, None, :, :, :] * joint_pmv[..., None, None, None]
    # weight_3d_all: (J, J, max_pairs, A, A, A)

    # Welfare contribution: sum over (jp, jb, k, i, j, l) of weight × integrand
    welfare_num = jnp.sum(weight_3d_all * integrand_3d)

    # Aggregates: per-axis marginals
    # weight_pol[jp, jb, k, i] = sum over (j, l) of weight_3d_all[jp, jb, k, i, j, l]
    weight_pol = jnp.sum(weight_3d_all, axis=(4, 5))   # (J, J, max_pairs, A)
    weight_none = jnp.sum(weight_3d_all, axis=(3, 5))  # (J, J, max_pairs, A)
    weight_base = jnp.sum(weight_3d_all, axis=(3, 4))  # (J, J, max_pairs, A)

    agg_inc_pol = jnp.sum(jnp.sum(weight_pol, axis=-1) * xi_eff_p)
    agg_inc_none = jnp.sum(jnp.sum(weight_none, axis=-1) * xi_eff_n)
    agg_cons_pol = jnp.sum(weight_pol * c_p)
    agg_cons_none = jnp.sum(weight_none * c_n)

    # Scatter: For each (j_pn_dst, j_b_dst, atom_k), scatter the (A,A,A)
    # weight into dist5d_next[:, :, :, j_pn_dst, j_b_dst].
    # The atom_k dim sums into the same (j_pn_dst, j_b_dst) slice.
    dist5d_next = jnp.zeros_like(dist5d)
    aMin = aGrid[0]
    aMax = aGrid[-1]
    diag_tol = 1e-12

    # Flatten (J, J, max_pairs) into a single dim for vmap; then aggregate
    # back by (j_pn_dst, j_b_dst). Each batch instance is one scatter.
    # For correctness-first, do the Python loop here.
    for j_pn_dst in range(J):
        for j_b_dst in range(J):
            slice_contrib = jnp.zeros((A, A, A), dtype=fdtype)
            for k in range(max_pairs):
                pmv_a = float(joint_pmv[j_pn_dst, j_b_dst, k])
                if pmv_a < _TRANS_EPS:
                    continue
                w = weight_3d_all[j_pn_dst, j_b_dst, k]  # (A, A, A)
                a_p = a_p_next[j_pn_dst, j_b_dst, k]
                a_n = a_n_next[j_pn_dst, j_b_dst, k]
                a_b = a_b_next[j_pn_dst, j_b_dst, k]

                # Build full a_p, a_n, a_b (A,A,A) coordinate tensors
                vp_full = jnp.broadcast_to(a_p[:, None, None], (A, A, A)).ravel()
                vn_full = jnp.broadcast_to(a_n[None, :, None], (A, A, A)).ravel()
                vb_full = jnp.broadcast_to(a_b[None, None, :], (A, A, A)).ravel()
                flat_w = w.ravel()
                slice_contrib = slice_contrib + _3d_bilinear_distribute_jax(
                    vp_full, vn_full, vb_full, flat_w, aGrid)
            dist5d_next = dist5d_next.at[:, :, :, j_pn_dst, j_b_dst].add(slice_contrib)

    # Mortality + rebirth
    if newborn_dist5d_diag is not None and LivPrb_avg < 1.0 - 1e-15:
        total_mass_before = jnp.sum(dist5d_next)
        dist5d_next = dist5d_next * LivPrb_avg
        newborn_mass = (1.0 - LivPrb_avg) * total_mass_before
        dist5d_next = dist5d_next + newborn_mass * newborn_dist5d_diag

    return dist5d_next, float(welfare_num), {
        'inc_pol': float(agg_inc_pol),
        'inc_none': float(agg_inc_none),
        'cons_pol': float(agg_cons_pol),
        'cons_none': float(agg_cons_none),
    }
