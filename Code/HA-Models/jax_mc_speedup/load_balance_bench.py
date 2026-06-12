"""Load-balancing benchmark: re-run parallel_solve_test at Baseline 5x to
measure speedup improvement from imap_unordered + largest-β-first scheduling.

Compares to the prior pool.map result (3.88× at Baseline 5x). Expected
lift: 5-7× from better dynamic balancing.

OUTCOME (measured, 2026-05-19): the 5-7× did not materialize — ~3.88× stands;
load-imbalance limited (high-β cohorts ~5-10× slower than average), mitigated
by largest-first scheduling. See CLAUDE.md §Cohort-parallel HARK solves.
"""
import sys, os, time
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "FromPandemicCode"))
sys.argv = [sys.argv[0]]
os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')

import numpy as np
from copy import deepcopy
import welfare6_scenario as ws


def main():
    parametrization = os.environ.get('TEST_PARAM', 'Baseline')
    n_workers_str = os.environ.get('TEST_N_WORKERS', '21')
    n_workers = int(n_workers_str)
    print(f"=== Load-balanced parallel solve: {parametrization}, n_workers={n_workers} ===")

    print(f"\nBuilding {parametrization} (sequential build)...")
    ws._SOLVE_WORKERS = 1
    t0 = time.time()
    ctx = ws.build_and_solve(parametrization)
    AggEco = ctx['AggEco']
    print(f"  built+solved in {time.time()-t0:.2f}s, {len(AggEco.agents)} cohorts")

    eco_s = deepcopy(AggEco)
    eco_s.switch_shock_type('recession')

    eco_p = deepcopy(AggEco)
    eco_p.switch_shock_type('recession')

    # Sequential reference
    ws._SOLVE_WORKERS = 1
    for a in eco_s.agents:
        a.solution = []
    print(f"\n[Sequential] solving {len(eco_s.agents)} cohorts ...")
    t0 = time.time()
    eco_s.solve()
    t_seq = time.time() - t0
    print(f"  seq: {t_seq:.2f}s")

    # Parallel with load-balanced version
    ws._SOLVE_WORKERS = n_workers
    for a in eco_p.agents:
        a.solution = []
    print(f"\n[Parallel load-balanced] solving {len(eco_p.agents)} cohorts ...")
    t0 = time.time()
    eco_p.solve()
    t_par = time.time() - t0
    print(f"  par: {t_par:.2f}s")
    ws._SOLVE_WORKERS = 1

    # Validate bit-identical
    m_query = np.linspace(1.0, 10.0, 30)
    C_query = np.full(30, 1.0)
    n_pass = 0
    max_rd_overall = 0.0
    for c_idx, (a_s, a_p) in enumerate(zip(eco_s.agents, eco_p.agents)):
        sol_s = a_s.solution[0]
        sol_p = a_p.solution[0]
        if len(sol_s.cFunc) != len(sol_p.cFunc):
            continue
        max_rd = 0.0
        for j in range(len(sol_s.cFunc)):
            c_s = sol_s.cFunc[j](m_query, C_query)
            c_p = sol_p.cFunc[j](m_query, C_query)
            rd = np.abs((c_p - c_s) / np.maximum(np.abs(c_s), 1e-12)).max()
            max_rd = max(max_rd, rd)
        max_rd_overall = max(max_rd_overall, max_rd)
        if max_rd < 1e-10:
            n_pass += 1

    print(f"\n=== Summary ===")
    print(f"  Sequential: {t_seq:.2f}s")
    print(f"  Parallel:   {t_par:.2f}s")
    speedup = t_seq / t_par if t_par > 0 else float('nan')
    print(f"  Speedup:    {speedup:.2f}x")
    print(f"  Prior (pool.map): ~3.88x")
    print(f"  Improvement: {speedup/3.88:.2f}x over prior")
    print(f"  Bit-identical: {n_pass}/{len(eco_s.agents)}")
    print(f"  Global max rel: {max_rd_overall:.4e}")
    if n_pass == len(eco_s.agents):
        if speedup > 5.0:
            print("\n✓ Load-balancing materially improves speedup (>5x)")
        elif speedup > 3.88:
            print(f"\n⚠ Mild improvement (3.88x → {speedup:.2f}x)")
        else:
            print(f"\n✗ No improvement vs prior ({speedup:.2f}x ≤ 3.88x)")
    else:
        print(f"\n✗ Bit-identical FAILED: {len(eco_s.agents)-n_pass} cohorts differ")


if __name__ == '__main__':
    main()
