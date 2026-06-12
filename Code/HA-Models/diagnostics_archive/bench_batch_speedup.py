"""
Phase A.6 speedup measurement: how much faster is batch n_β=7 vs
7 sequential n_β=1 calls?

Uses HS_Only (1 cohort) duplicated 7 times as a stand-in for the
Baseline within-ed-type case. The batch function's β-shared work
is genuinely shared across the 7 identical agents.

This is NOT a correctness test (output is duplicated). It's purely
to measure the amortization benefit.
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


def main():
    aCount = int(os.environ.get('JOINT5D_ACOUNT', 30))
    dur = int(os.environ.get('VALIDATE_DUR', 1))
    n_beta = int(os.environ.get('N_BETA', 7))

    print(f"{'='*70}\nPhase A.6 speedup bench (A={aCount}, dur={dur}, n_β={n_beta})\n{'='*70}")

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
    print(f"  setup wall: {time.time() - t0:.1f}s")

    # Sequential: n_β calls of compute_joint_welfare5d
    print(f"\n  Running {n_beta} SEQUENTIAL single calls...")
    t1 = time.time()
    seq_results = []
    for b in range(n_beta):
        res = compute_joint_welfare5d(
            AggEco_pol.agents[0], AggEco_none.agents[0], AggEco_base.agents[0],
            bd_list[0], EconomyMrkv_path_pn=path, act_T=ctx['act_T'], verbose=False)
        seq_results.append(res)
    seq_wall = time.time() - t1
    print(f"  SEQUENTIAL wall (n={n_beta}): {seq_wall:.2f}s ({seq_wall/n_beta:.2f}s per call)")

    # Batch: single call with n_β identical agents
    print(f"\n  Running 1 BATCH call with n_β={n_beta} identical agents...")
    agents_pol_batch = [AggEco_pol.agents[0]] * n_beta
    agents_none_batch = [AggEco_none.agents[0]] * n_beta
    agents_base_batch = [AggEco_base.agents[0]] * n_beta
    bd_batch = [bd_list[0]] * n_beta
    t1 = time.time()
    batch_results = compute_joint_welfare5d_batch(
        agents_pol_batch, agents_none_batch, agents_base_batch, bd_batch,
        EconomyMrkv_path_pn=path, act_T=ctx['act_T'], verbose=False)
    batch_wall = time.time() - t1
    print(f"  BATCH wall (n_β={n_beta}): {batch_wall:.2f}s")
    print(f"\n  SPEEDUP (seq / batch): {seq_wall / batch_wall:.2f}x")
    print(f"  Per-element wall: SEQ={seq_wall/n_beta:.2f}s, BATCH={batch_wall/n_beta:.2f}s")

    # Sanity check: all batch results should equal seq[0] (since input identical)
    max_d = 0
    for b in range(n_beta):
        for k in ['welfare_num_series', 'AggInc_pol_series', 'AggCons_pol_series']:
            d = float(np.abs(seq_results[0][k] - batch_results[b][k]).max())
            max_d = max(max_d, d)
    print(f"\n  Correctness sanity (all batch results identical to seq[0]): max|diff|={max_d:.3e}")


if __name__ == '__main__':
    main()
