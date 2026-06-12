"""
Phase B.2 Step 2a: validate cFunc tabulation + JAX interp lookup
against direct HARK cFunc evaluation.

Pass criterion: tabulated cFunc agrees with HARK cFunc to interpolation
precision on a fine grid (rtol ~1e-3 with M=200 m_grid, ~1e-5 with M=1000).
"""
from __future__ import annotations
import os, sys, time
from copy import deepcopy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint5d_jax_kernel import tabulate_cfunc_list, interp_cfunc, _USE_FP64
import jax
import jax.numpy as jnp


def main():
    print(f"=== Phase B.2 Step 2a: cFunc tabulation + JAX interp ===")
    print(f"  FP mode: {'FP64' if _USE_FP64 else 'FP32'}")
    print(f"  JAX backend: {jax.default_backend()}")

    ctx = build_and_solve('HS_Only')
    AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
    cfunc_list = AggEco_pol.agents[0].solution[0].cFunc
    print(f"  cFunc list length: {len(cfunc_list)}")

    # m_grid range chosen to cover plausible cash-on-hand values
    # (test points in the model typically m ∈ [0, ~50])
    M_grids = [100, 200, 500, 1000]
    # Test points where we'll compare HARK direct vs JAX tabulation
    m_test = np.array([0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 35.0, 49.0])
    cr_test = np.ones_like(m_test)

    # Test on a sample of cFuncs (every 20th to span the list)
    cf_indices = list(range(0, len(cfunc_list), 20))
    print(f"  testing cFunc indices: {cf_indices}")

    for M in M_grids:
        m_grid = np.linspace(0.01, 50.0, M)
        # Tabulate
        c_table_all = tabulate_cfunc_list(cfunc_list, m_grid)
        max_rel_err = 0
        for cf_idx in cf_indices:
            c_table = c_table_all[cf_idx]
            # HARK direct
            c_hark = cfunc_list[cf_idx](m_test, cr_test)
            # JAX interp from table
            dtype = np.float64 if _USE_FP64 else np.float32
            c_jax = np.asarray(
                interp_cfunc(
                    jnp.asarray(m_test, dtype=dtype),
                    jnp.asarray(m_grid, dtype=dtype),
                    jnp.asarray(c_table, dtype=dtype),
                ).block_until_ready()
            )
            rel_err = np.max(np.abs(c_hark - c_jax) / (np.abs(c_hark) + 1e-10))
            if rel_err > max_rel_err:
                max_rel_err = rel_err
        print(f"  M={M:5d}: max rel|HARK - JAX-tabulated| = {max_rel_err:.3e}")


if __name__ == '__main__':
    main()
