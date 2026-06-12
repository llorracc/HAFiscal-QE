"""
JAX-accelerated port of welfare6_tm_joint5d helpers (Phase B of
plans/20260516_5D_ambitious_parallelization.md).

Incremental development: ports one function at a time, validates
against numpy reference, and accumulates a JAX-jit'd kernel.

Phase B.1: compute_joint_markov_jax — vectorized + jit'd.

Precision: FP32 by default per the plan's precision decision.
Set FORCE_FP64=1 to force FP64 for diagnostic comparisons.
"""
from __future__ import annotations
import os

import numpy as np

# Configure JAX precision BEFORE importing jax.numpy
_FORCE_FP64 = os.environ.get('FORCE_FP64', '0') == '1'
_USE_FP64 = _FORCE_FP64  # alias for clarity in test code
if _FORCE_FP64:
    import jax
    jax.config.update('jax_enable_x64', True)

import jax
import jax.numpy as jnp


def compute_joint_markov_jax(MA_pn, MA_b):
    """
    JAX port of welfare6_tm_joint5d.compute_joint_markov.

    Vectorized over all 4 axes (j_pn_src, j_b_src, k_pn, k_b) — no
    Python loops. JIT'd for kernel fusion.

    Returns: jnp.ndarray, shape (J, J, J, J)
    """
    return _compute_joint_markov_jax_impl(MA_pn, MA_b)


@jax.jit
def _compute_joint_markov_jax_impl(MA_pn, MA_b):
    F_pn = jnp.cumsum(MA_pn, axis=1)  # (J, J)
    F_b = jnp.cumsum(MA_b, axis=1)
    # Left edges: prepend 0
    F_pn_left = jnp.concatenate(
        [jnp.zeros((MA_pn.shape[0], 1), dtype=MA_pn.dtype), F_pn[:, :-1]], axis=1)
    F_b_left = jnp.concatenate(
        [jnp.zeros((MA_b.shape[0], 1), dtype=MA_b.dtype), F_b[:, :-1]], axis=1)

    # Broadcast over (j_pn_src, j_b_src, k_pn, k_b):
    #   a = F_pn_left[j_pn_src, k_pn]  → shape (J, 1, J, 1)
    #   b = F_pn     [j_pn_src, k_pn]  → shape (J, 1, J, 1)
    #   c = F_b_left [j_b_src, k_b]    → shape (1, J, 1, J)
    #   d = F_b      [j_b_src, k_b]    → shape (1, J, 1, J)
    # overlap = max(0, min(b, d) - max(a, c))
    a = F_pn_left[:, None, :, None]
    b = F_pn[:, None, :, None]
    c = F_b_left[None, :, None, :]
    d = F_b[None, :, None, :]
    overlap = jnp.maximum(0.0, jnp.minimum(b, d) - jnp.maximum(a, c))
    return overlap


@jax.jit
def _bilinear_lookup(aGrid, values):
    """Return (i_lo, w_lo, w_hi) for bilinear interpolation on a 1D grid.

    i_lo is the index of the grid point ≤ value (clipped to [0, A-2]),
    w_lo + w_hi = 1, and value ≈ w_lo * aGrid[i_lo] + w_hi * aGrid[i_lo + 1].
    """
    A = aGrid.shape[0]
    # searchsorted gives index where value would be inserted; subtract 1 to get
    # the lower bracket. Clip to [0, A-2] so i_hi = i_lo + 1 is valid.
    i_lo = jnp.clip(jnp.searchsorted(aGrid, values, side='right') - 1, 0, A - 2)
    a_lo = aGrid[i_lo]
    a_hi = aGrid[i_lo + 1]
    w_hi = (values - a_lo) / (a_hi - a_lo)
    w_lo = 1.0 - w_hi
    return i_lo, w_lo, w_hi


def bilinear_3d_distribute_jax(values_p, values_n, values_b, weights, aGrid):
    """
    JAX port of welfare6_tm_joint5d._3d_bilinear_distribute.

    Returns a (A, A, A) accumulator. Caller adds this into the
    full 5D target at slice [:, :, :, j_pn, j_b].

    Diagonal preservation (FIX #9): points where v_p == v_n == v_b
    distribute 1D-bilinear along the asset diagonal; off-diagonal
    points use standard 3D-bilinear. Branching implemented via
    jnp.where masks (no Python control flow inside jit).

    Args:
        values_p, values_n, values_b: (N,) continuous asset values
        weights:                       (N,) mass weights
        aGrid:                          (A,) 1D grid
    Returns:
        target_slice: (A, A, A) accumulator
    """
    return _bilinear_3d_distribute_jax_impl(values_p, values_n, values_b, weights, aGrid)


@jax.jit
def _bilinear_3d_distribute_jax_impl(values_p, values_n, values_b, weights, aGrid):
    A = aGrid.shape[0]
    aMin = aGrid[0]
    aMax = aGrid[-1]
    vp = jnp.clip(values_p, aMin, aMax)
    vn = jnp.clip(values_n, aMin, aMax)
    vb = jnp.clip(values_b, aMin, aMax)

    # Diagonal mask: tolerance 1e-12 relative diff (same as numpy version)
    diag_tol = 1e-12
    is_diag = (jnp.abs(vp - vn) < diag_tol) & (jnp.abs(vn - vb) < diag_tol)

    # Split weights by diag mask. Each branch will scatter all N points
    # (with zero weight for the wrong-branch points), which is correct
    # under add-scatter semantics.
    w_diag = jnp.where(is_diag, weights, 0.0)
    w_off = jnp.where(is_diag, 0.0, weights)

    # Bilinear lookups (using the diagonal-shared a value for the diag branch)
    v_diag = vp  # arbitrary: vp==vn==vb on diagonal; doesn't matter elsewhere
    i_diag_lo, w_diag_lo, w_diag_hi = _bilinear_lookup(aGrid, v_diag)

    ip_lo, wp_lo, wp_hi = _bilinear_lookup(aGrid, vp)
    in_lo, wn_lo, wn_hi = _bilinear_lookup(aGrid, vn)
    ib_lo, wb_lo, wb_hi = _bilinear_lookup(aGrid, vb)

    target = jnp.zeros((A, A, A), dtype=aGrid.dtype)

    # Diagonal contributions: (i_diag_lo, i_diag_lo, i_diag_lo) and (i_diag_hi, ...)
    target = target.at[i_diag_lo, i_diag_lo, i_diag_lo].add(w_diag * w_diag_lo)
    i_diag_hi = i_diag_lo + 1
    target = target.at[i_diag_hi, i_diag_hi, i_diag_hi].add(w_diag * w_diag_hi)

    # Off-diagonal: 8 corners of the (ip, in, ib) cube
    ip_hi = ip_lo + 1
    in_hi = in_lo + 1
    ib_hi = ib_lo + 1
    for dp, wp in [(ip_lo, wp_lo), (ip_hi, wp_hi)]:
        for dn, wn in [(in_lo, wn_lo), (in_hi, wn_hi)]:
            for db, wb in [(ib_lo, wb_lo), (ib_hi, wb_hi)]:
                target = target.at[dp, dn, db].add(w_off * wp * wn * wb)

    return target


if __name__ == '__main__':
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from welfare6_tm_joint5d import compute_joint_markov as compute_joint_markov_np
    from welfare6_tm_joint5d import _3d_bilinear_distribute as _3d_bilinear_np
    import time

    print(f"=== B.1 unit validation: compute_joint_markov_jax ===")
    print(f"  FP64 mode: {_FORCE_FP64}")
    print(f"  JAX backend: {jax.default_backend()}")
    print(f"  JAX devices: {jax.devices()}")

    # Test fixture: synthetic Markov matrices of various sizes
    for J in [4, 8, 16, 24, 32]:
        rng = np.random.default_rng(42)
        MA_pn = rng.dirichlet(np.ones(J), size=J)  # rows sum to 1
        MA_b = rng.dirichlet(np.ones(J), size=J)
        assert np.allclose(MA_pn.sum(axis=1), 1.0)
        assert np.allclose(MA_b.sum(axis=1), 1.0)

        # NumPy reference
        t0 = time.time()
        np_result = compute_joint_markov_np(MA_pn, MA_b)
        np_wall = time.time() - t0

        # JAX (with compilation overhead on first call per shape)
        dtype = np.float64 if _FORCE_FP64 else np.float32
        MA_pn_j = jnp.asarray(MA_pn, dtype=dtype)
        MA_b_j = jnp.asarray(MA_b, dtype=dtype)
        # Warm up JIT
        _ = compute_joint_markov_jax(MA_pn_j, MA_b_j).block_until_ready()
        # Time the warm version
        t0 = time.time()
        jax_result = compute_joint_markov_jax(MA_pn_j, MA_b_j).block_until_ready()
        jax_wall = time.time() - t0
        jax_result_np = np.asarray(jax_result)

        # Compare
        if _FORCE_FP64:
            ok = np.allclose(np_result, jax_result_np, rtol=1e-13, atol=1e-15)
            tol_label = "rtol=1e-13 (FP64)"
        else:
            ok = np.allclose(np_result, jax_result_np, rtol=1e-5, atol=1e-7)
            tol_label = "rtol=1e-5 (FP32)"

        max_diff = float(np.abs(np_result - jax_result_np).max())
        rel_diff = float(np.abs((np_result - jax_result_np) /
                                (np.abs(np_result) + 1e-12)).max())

        # Row-sum check: joint should marginalize back to MA_pn
        joint_marg_pn = jax_result_np.sum(axis=(1, 3))  # sum over j_b_src and k_b
        # Note: this should equal MA_pn (since k_pn is the new state)
        # joint[j_pn_src, j_b_src, k_pn, k_b].sum over (j_b_src, k_b)
        # = sum_j_b_src P(k_pn | j_pn_src) * 1 (marginalize k_b)... hmm depends on math
        # Actually marginalize k_b first: sum_k_b joint = P(k_pn | j_pn_src, j_b_src)
        # then sum_j_b_src... not straightforward without weighting. Skip this check.

        speedup = np_wall / jax_wall if jax_wall > 0 else float('inf')
        status = 'PASS' if ok else 'FAIL'
        print(f"  J={J:2d}: numpy {np_wall*1000:7.2f}ms, jax {jax_wall*1000:7.2f}ms, "
              f"speedup {speedup:5.1f}x, max|diff|={max_diff:.3e}, "
              f"rel|diff|={rel_diff:.3e} [{tol_label}] [{status}]")

    print()
    print(f"=== B.2 Step 1 unit validation: bilinear_3d_distribute_jax ===")

    # Test fixture: synthetic asset distribution with mix of diag and off-diag pts
    for A_grid in [10, 25, 50]:
        rng = np.random.default_rng(123)
        aGrid_np = np.linspace(0.0, 50.0, A_grid)
        # N points: half on diagonal, half off
        N_diag = 100
        N_off = 100
        v_diag = rng.uniform(0.1, 49.9, size=N_diag)
        v_p = np.concatenate([v_diag, rng.uniform(0.1, 49.9, size=N_off)])
        v_n = np.concatenate([v_diag, rng.uniform(0.1, 49.9, size=N_off)])
        v_b = np.concatenate([v_diag, rng.uniform(0.1, 49.9, size=N_off)])
        w = rng.uniform(0.01, 1.0, size=N_diag + N_off)

        # NumPy reference: call with a dummy 5D target with shape (A, A, A, 1, 1)
        # so the function can write to target_dist_5d[:, :, :, 0, 0].
        np_target = np.zeros((A_grid, A_grid, A_grid, 1, 1))
        _3d_bilinear_np(v_p.copy(), v_n.copy(), v_b.copy(), w.copy(),
                        aGrid_np, np_target, 0, 0)
        np_slice = np_target[:, :, :, 0, 0]

        # JAX
        dtype = np.float64 if _USE_FP64 else np.float32
        v_p_j = jnp.asarray(v_p, dtype=dtype)
        v_n_j = jnp.asarray(v_n, dtype=dtype)
        v_b_j = jnp.asarray(v_b, dtype=dtype)
        w_j = jnp.asarray(w, dtype=dtype)
        aGrid_j = jnp.asarray(aGrid_np, dtype=dtype)
        # Warmup
        _ = bilinear_3d_distribute_jax(v_p_j, v_n_j, v_b_j, w_j, aGrid_j).block_until_ready()
        # Time + measure
        t0 = time.time()
        jax_slice = bilinear_3d_distribute_jax(v_p_j, v_n_j, v_b_j, w_j, aGrid_j)
        jax_slice_np = np.asarray(jax_slice.block_until_ready())
        jax_wall = time.time() - t0

        # Compare
        rtol = 1e-13 if _USE_FP64 else 1e-4
        ok = np.allclose(np_slice, jax_slice_np, rtol=rtol, atol=1e-7)
        max_diff = float(np.abs(np_slice - jax_slice_np).max())
        # Mass conservation: both should preserve total weight (excluding clipping)
        np_mass = float(np_slice.sum())
        jax_mass = float(jax_slice_np.sum())
        mass_diff = abs(np_mass - jax_mass) / max(np_mass, 1e-12)
        status = 'PASS' if ok else 'FAIL'
        print(f"  A={A_grid:2d}: max|diff|={max_diff:.3e}, "
              f"mass(np)={np_mass:.4f}, mass(jax)={jax_mass:.4f}, "
              f"rel mass|diff|={mass_diff:.3e}, wall={jax_wall*1000:.2f}ms [{status}]")

    print()
    print("=== Done ===")
