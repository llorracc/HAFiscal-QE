"""
Phase C.4 validation: compute_joint_welfare5d_jax_batched vs the
serial per-cohort compute_joint_welfare5d_jax.

Tests:
  HS_Only (n=1): batched n=1 must match serial output.
  Reduced_Run (n=3): batched per-cohort series must match 3 serial calls.
"""
from __future__ import annotations
import os, sys, time
from copy import deepcopy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint5d_jax_kernel import (
    compute_joint_welfare5d_jax,
    compute_joint_welfare5d_jax_batched,
)
from tm_methods import compute_baseline_tm_data


def _build_econ_mrkv_path(act_T, num_experiment_periods, dur):
    path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T + 5)
    path = path[:act_T]
    for t in range(min(dur, len(path))):
        path[t] = path[t] + 1
    return path


def _compare(s, b, label):
    print(f"  {label}:")
    max_d = 0
    for k in ['welfare_num_series', 'AggInc_pol_series', 'AggInc_none_series',
              'AggCons_pol_series', 'AggCons_none_series', 'pLvl_factor_series']:
        d = float(np.abs(s[k] - b[k]).max())
        denom = max(float(np.abs(s[k]).max()), 1e-12)
        rel = d / denom
        ok = '✓' if rel < 1e-10 else ('?' if rel < 1e-4 else '✗')
        print(f"    {k:<28} max|diff|={d:.3e} rel|diff|={rel:.3e} [{ok}]")
        max_d = max(max_d, rel)
    return max_d


def test(parametrization, aCount, dur):
    print(f"\n{'='*70}")
    print(f"TEST: {parametrization} A={aCount} dur={dur}")
    print(f"{'='*70}")

    ctx = build_and_solve(parametrization)
    AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
    AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()
    AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()
    for ag in AggEco_pol.agents: ag.tm_a_indexed = True
    for ag in AggEco_none.agents: ag.tm_a_indexed = True
    for ag in AggEco_base.agents: ag.tm_a_indexed = True
    bd_list = compute_baseline_tm_data(AggEco_base, mCount=aCount, neutral_measure=True)
    n_cohorts = len(AggEco_pol.agents)
    print(f"  n_cohorts={n_cohorts}")

    act_T = ctx['act_T']
    nep = ctx['num_experiment_periods']
    path = _build_econ_mrkv_path(act_T, nep, dur)

    # Serial path: n_cohorts calls
    print(f"\n  Running SERIAL (n_cohorts={n_cohorts} sequential calls)...")
    t1 = time.time()
    serial_results = []
    for c in range(n_cohorts):
        res = compute_joint_welfare5d_jax(
            AggEco_pol.agents[c], AggEco_none.agents[c], AggEco_base.agents[c],
            bd_list[c], EconomyMrkv_path_pn=path, act_T=act_T, verbose=False)
        serial_results.append(res)
    serial_wall = time.time() - t1
    print(f"  SERIAL wall: {serial_wall:.2f}s")

    # Batched path: 1 call processing all cohorts
    print(f"\n  Running BATCHED (n_cohorts={n_cohorts} on GPU batch)...")
    t1 = time.time()
    batched_results = compute_joint_welfare5d_jax_batched(
        AggEco_pol.agents, AggEco_none.agents, AggEco_base.agents,
        bd_list, EconomyMrkv_path_pn=path, act_T=act_T, verbose=True)
    batched_wall = time.time() - t1
    print(f"  BATCHED wall: {batched_wall:.2f}s")
    print(f"  speedup: {serial_wall/batched_wall:.2f}x")

    # Compare per-cohort
    print(f"\n=== Per-cohort comparison ===")
    overall_max = 0
    for c in range(n_cohorts):
        d = _compare(serial_results[c], batched_results[c], f"cohort {c}")
        overall_max = max(overall_max, d)
    print(f"\n  overall max rel diff: {overall_max:.3e}")
    if overall_max < 1e-6:
        print(f"  ✓ PASS")
    elif overall_max < 1e-3:
        print(f"  ? marginal (rel diff < 0.1%, > 1e-6)")
    else:
        print(f"  ✗ FAIL")


def main():
    aCount = int(os.environ.get('JOINT5D_ACOUNT', 30))
    dur = int(os.environ.get('VALIDATE_DUR', 1))

    # Gate C.4.2: HS_Only (n=1)
    test('HS_Only', aCount, dur)

    # Gate C.4.4: Reduced_Run (n=3)
    test('Reduced_Run', aCount, dur)


if __name__ == '__main__':
    main()
