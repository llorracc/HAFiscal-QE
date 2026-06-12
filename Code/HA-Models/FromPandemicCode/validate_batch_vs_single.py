"""
Phase A.6 validation v2: batch function assumes all input cohorts share
income process. Test by:
  - HS_Only: n_β=1, single batch call → bit-identical to single-cohort call.
  - Reduced_Run: 3 ed_types with 1 β each → 3 separate batch calls each
    of n_β=1 → each batch must match its corresponding single-cohort run.
  - (Baseline would group cohorts by ed_type with 7 β each; expensive to test.)
"""
from __future__ import annotations
import os, sys, time
from copy import deepcopy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint5d import compute_joint_welfare5d
from welfare6_tm_joint5d_batch import compute_joint_welfare5d_batch
from tm_methods import compute_baseline_tm_data


def _build_econ_mrkv_path(act_T, num_experiment_periods, dur):
    path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T + 5)
    path = path[:act_T]
    for t in range(min(dur, len(path))):
        path[t] = path[t] + 1
    return path


def _compare(single, batch, label):
    max_d = 0
    print(f"  {label}:")
    for k in ['welfare_num_series', 'AggInc_pol_series', 'AggInc_none_series',
              'AggCons_pol_series', 'AggCons_none_series', 'pLvl_factor_series']:
        d = float(np.abs(single[k] - batch[k]).max())
        denom = max(float(np.abs(single[k]).max()), 1e-12)
        rel = d / denom
        ok = '✓' if rel < 1e-10 else ('?' if rel < 1e-5 else '✗')
        print(f"    {k:<28} max|diff|={d:.3e} rel|diff|={rel:.3e} [{ok}]")
        if d > max_d:
            max_d = d
    return max_d


def main():
    aCount = int(os.environ.get('JOINT5D_ACOUNT', 30))
    dur = int(os.environ.get('VALIDATE_DUR', 1))

    print(f"{'='*70}\nPhase A.6 validation v2 (A={aCount}, dur={dur})\n{'='*70}")

    # ============================================================
    # HS_Only: 1 cohort, batch n_β=1 must match single-cohort path
    # ============================================================
    print(f"\n=== HS_Only: batch n_β=1 vs single ===")
    t0 = time.time()
    ctx = build_and_solve('HS_Only')
    AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
    AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()
    AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()
    for ag in AggEco_pol.agents: ag.tm_a_indexed = True
    for ag in AggEco_none.agents: ag.tm_a_indexed = True
    for ag in AggEco_base.agents: ag.tm_a_indexed = True
    bd_list = compute_baseline_tm_data(AggEco_base, mCount=aCount, neutral_measure=True)
    path = _build_econ_mrkv_path(ctx['act_T'], ctx['num_experiment_periods'], dur)
    print(f"  setup wall: {time.time() - t0:.1f}s, n_cohorts={len(AggEco_pol.agents)}")

    t1 = time.time()
    s_res = compute_joint_welfare5d(
        AggEco_pol.agents[0], AggEco_none.agents[0], AggEco_base.agents[0],
        bd_list[0], EconomyMrkv_path_pn=path, act_T=ctx['act_T'], verbose=False)
    single_wall = time.time() - t1
    print(f"  SINGLE wall: {single_wall:.2f}s")

    t1 = time.time()
    b_res = compute_joint_welfare5d_batch(
        AggEco_pol.agents, AggEco_none.agents, AggEco_base.agents,
        bd_list, EconomyMrkv_path_pn=path, act_T=ctx['act_T'], verbose=False)
    batch_wall = time.time() - t1
    print(f"  BATCH wall: {batch_wall:.2f}s")
    print(f"  speedup: {single_wall/batch_wall:.2f}x")
    _compare(s_res, b_res[0], "cohort 0")

    # ============================================================
    # Reduced_Run: 3 ed_types, batch correctly = 3 separate batch calls of n_β=1
    # ============================================================
    print(f"\n=== Reduced_Run: 3 separate batch n_β=1 calls vs single per cohort ===")
    t0 = time.time()
    ctx = build_and_solve('Reduced_Run')
    AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
    AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()
    AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()
    for ag in AggEco_pol.agents: ag.tm_a_indexed = True
    for ag in AggEco_none.agents: ag.tm_a_indexed = True
    for ag in AggEco_base.agents: ag.tm_a_indexed = True
    bd_list = compute_baseline_tm_data(AggEco_base, mCount=aCount, neutral_measure=True)
    path = _build_econ_mrkv_path(ctx['act_T'], ctx['num_experiment_periods'], dur)
    n_coh = len(AggEco_pol.agents)
    print(f"  setup wall: {time.time() - t0:.1f}s, n_cohorts={n_coh}")

    t1 = time.time()
    single_results = []
    for c in range(n_coh):
        single_results.append(compute_joint_welfare5d(
            AggEco_pol.agents[c], AggEco_none.agents[c], AggEco_base.agents[c],
            bd_list[c], EconomyMrkv_path_pn=path, act_T=ctx['act_T'], verbose=False))
    print(f"  SINGLE wall (all {n_coh}): {time.time() - t1:.2f}s")

    # For Reduced_Run, each ed_type has 1 β-atom, so each "ed_type batch" is n_β=1.
    # Call the batch function once per cohort with just that cohort's agents.
    t1 = time.time()
    batch_results = []
    for c in range(n_coh):
        res = compute_joint_welfare5d_batch(
            [AggEco_pol.agents[c]], [AggEco_none.agents[c]], [AggEco_base.agents[c]],
            [bd_list[c]], EconomyMrkv_path_pn=path, act_T=ctx['act_T'], verbose=False)
        batch_results.append(res[0])
    print(f"  BATCH wall (3 separate n_β=1 calls): {time.time() - t1:.2f}s")

    max_overall = 0
    for c in range(n_coh):
        d = _compare(single_results[c], batch_results[c], f"cohort {c}")
        max_overall = max(max_overall, d)
    print(f"\n  max overall diff: {max_overall:.3e}")
    if max_overall < 1e-10:
        print("  ✓ ALL bit-identical (correct usage of batch function)")
    else:
        print("  ✗ DIVERGENCE — bug in batch function")


if __name__ == '__main__':
    main()
