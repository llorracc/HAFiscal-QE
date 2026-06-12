"""
Tier 1 m_grid sensitivity sweep — HS_Only A=30, single cohort.

Hypothesis: m_grid=500 is over-resolved; m_grid=100 (or lower) should
hold ui_rec to within 0.05% rel drift.

Runs on CPU (JAX_PLATFORMS=cpu) so it does not compete with GPU work.
"""
from __future__ import annotations
import os, sys, time
from copy import deepcopy
import numpy as np

# Force CPU before importing jax
os.environ.setdefault('JAX_PLATFORMS', 'cpu')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint5d_jax_kernel import compute_joint_welfare5d_jax
from tm_methods import compute_baseline_tm_data
import jax


def _build_econ_mrkv_path(act_T, num_experiment_periods, dur):
    path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T + 5)
    path = path[:act_T]
    for t in range(min(dur, len(path))):
        path[t] = path[t] + 1
    return path


def main():
    aCount = int(os.environ.get('JOINT5D_ACOUNT', 30))
    dur_test = int(os.environ.get('SWEEP_DUR', 4))  # 4 quarters covers the cFunc shape sensitivity
    m_grids = [int(x) for x in os.environ.get(
        'M_GRIDS', '500,250,100,50,25').split(',')]
    nest_mode = os.environ.get('JOINT5D_MGRID_NEST', '3')

    print(f"{'='*70}")
    print(f"Tier 1 m_grid sensitivity: HS_Only A={aCount} dur={dur_test}")
    print(f"  Sweep: {m_grids}")
    print(f"  Nest mode: {nest_mode} ({'linspace' if nest_mode == '-1' else 'triple-log' if nest_mode == '3' else 'exp'})")
    print(f"  JAX backend: {jax.default_backend()}")
    print(f"{'='*70}")

    # Build once
    print("\nBuilding HS_Only context...")
    ctx = build_and_solve('HS_Only')
    AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
    AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()
    AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()
    for ag in AggEco_pol.agents: ag.tm_a_indexed = True
    for ag in AggEco_none.agents: ag.tm_a_indexed = True
    for ag in AggEco_base.agents: ag.tm_a_indexed = True
    bd_list = compute_baseline_tm_data(AggEco_base, mCount=aCount, neutral_measure=True)

    act_T = ctx['act_T']
    nep = ctx['num_experiment_periods']
    path = _build_econ_mrkv_path(act_T, nep, dur_test)

    results = []
    for m_grid in m_grids:
        print(f"\n--- m_grid={m_grid} ---")
        t1 = time.time()
        res = compute_joint_welfare5d_jax(
            AggEco_pol.agents[0], AggEco_none.agents[0], AggEco_base.agents[0],
            bd_list[0], EconomyMrkv_path_pn=path, act_T=act_T,
            M_grid=m_grid, verbose=(m_grid == m_grids[0]))
        wall = time.time() - t1
        # ui_rec proxy = welfare numerator at end of duration sweep
        # For a single-duration run, we just have the welfare integrand series
        w_num = float(res['welfare_num_series'].sum())
        inc_p = float(res['AggInc_pol_series'].sum())
        cons_p = float(res['AggCons_pol_series'].sum())
        results.append((m_grid, wall, w_num, inc_p, cons_p))
        print(f"  wall={wall:.2f}s  welfare_num_sum={w_num:.6e}  "
              f"AggInc_pol_sum={inc_p:.6e}  AggCons_pol_sum={cons_p:.6e}")

    # Compare all to m_grid[0] (highest resolution = ground truth)
    print(f"\n{'='*70}")
    print(f"Drift vs m_grid={m_grids[0]} (ground truth):")
    print(f"{'='*70}")
    ref = results[0]
    print(f"  m_grid   wall   d(welfare)   d(inc_pol)   d(cons_pol)   speedup")
    print(f"  ------   ----   ----------   ----------   -----------   -------")
    for m_grid, wall, w_num, inc_p, cons_p in results:
        d_w = abs(w_num - ref[2]) / (abs(ref[2]) + 1e-12)
        d_ip = abs(inc_p - ref[3]) / (abs(ref[3]) + 1e-12)
        d_cp = abs(cons_p - ref[4]) / (abs(ref[4]) + 1e-12)
        sp = ref[1] / wall if wall > 0 else float('nan')
        mark = '✓' if d_w < 5e-4 else ('?' if d_w < 5e-3 else '✗')
        print(f"  {m_grid:5d}  {wall:6.1f}s  {d_w:.3e}   {d_ip:.3e}   {d_cp:.3e}   "
              f"{sp:.2f}x  [{mark}]")

    print(f"\nPass criterion (Tier 1): rel diff < 5e-4 (0.05%) on welfare_num")


if __name__ == '__main__':
    main()
