"""
Phase A.5.1 — Profile the per-step kernel `_step_period_5d` to identify
where time is actually spent at Baseline-relevant J sizes.

Runs a single Reduced_Run cohort × single duration at A=50, with
cProfile wrapping the kernel call. Outputs a sorted-by-cumtime
breakdown of the top time consumers.

Goal: answer the question "is the bottleneck Python overhead in the
quadruple loop, or cFunc evaluation?" This determines whether
sparsity+vectorization on CPU is worth pursuing (Phase A.5) or
whether the JAX-GPU port (Phase B) is the only viable path.

Usage:
    JOINT5D_ACOUNT=50 python profile_5d_kernel.py
"""
from __future__ import annotations
import cProfile
import io
import os
import pstats
import sys
import time
from copy import deepcopy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint5d import compute_joint_welfare5d
from tm_methods import compute_baseline_tm_data


def _build_econ_mrkv_path(act_T, num_experiment_periods, dur):
    path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T + 5)
    path = path[:act_T]
    for t in range(min(dur, len(path))):
        path[t] = path[t] + 1
    return path


def main():
    aCount = int(os.environ.get('JOINT5D_ACOUNT', 50))
    parametrization = os.environ.get('PROFILE_PARAM', 'Reduced_Run')
    print(f"=== A.5.1 profile: {parametrization} A={aCount} single duration ===")

    print(f"[1/4] Build {parametrization} context + solve...")
    t0 = time.time()
    ctx = build_and_solve(parametrization)
    AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
    AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()
    AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()
    for ag in AggEco_pol.agents: ag.tm_a_indexed = True
    for ag in AggEco_none.agents: ag.tm_a_indexed = True
    for ag in AggEco_base.agents: ag.tm_a_indexed = True
    print(f"      setup wall: {time.time()-t0:.1f}s")
    print(f"      n_cohorts: {len(AggEco_pol.agents)}")
    print(f"      pol J: {AggEco_pol.agents[0].num_base_MrkvStates}")
    print(f"      base J: {AggEco_base.agents[0].num_base_MrkvStates}")

    print(f"[2/4] Compute baseline_tm_data (A={aCount})...")
    t0 = time.time()
    bd_list = compute_baseline_tm_data(AggEco_base, mCount=aCount, neutral_measure=True)
    print(f"      wall: {time.time()-t0:.1f}s")

    act_T = ctx['act_T']
    nep = ctx['num_experiment_periods']
    max_dur = ctx.get('max_recession_duration', nep)
    print(f"      act_T={act_T}, max_dur={max_dur}")

    # Use cohort 0 (representative)
    agent_pol = AggEco_pol.agents[0]
    agent_none = AggEco_none.agents[0]
    agent_base = AggEco_base.agents[0]
    bd = bd_list[0]

    # Use shortest duration (= dur=1) — cheap-ish, still exercises the kernel
    dur = 1
    path = _build_econ_mrkv_path(act_T, nep, dur)

    print(f"[3/4] cProfile single (cohort=0, dur={dur}) at A={aCount}...")
    profiler = cProfile.Profile()
    t0 = time.time()
    profiler.enable()
    res = compute_joint_welfare5d(
        agent_pol, agent_none, agent_base, bd,
        EconomyMrkv_path_pn=path, act_T=act_T,
        verbose=False,
    )
    profiler.disable()
    wall = time.time() - t0
    print(f"      wall: {wall:.1f}s")
    print(f"      welfare_num sum: {res['welfare_num_series'].sum():.3e}")

    print(f"[4/4] Profile breakdown (top 40 by cumulative time):")
    print()
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats(40)
    print(s.getvalue())

    # Save profile binary for offline analysis
    profile_path = f'reproduce/logs/5D_parallel/profile_{parametrization}_A{aCount}.prof'
    profiler.dump_stats(profile_path)
    print(f"      saved profile binary to {profile_path}")

    # Also print top by tottime (= self time, no descendants)
    print()
    print("Top 30 by self time (= bottleneck functions):")
    s2 = io.StringIO()
    ps2 = pstats.Stats(profiler, stream=s2).sort_stats('tottime')
    ps2.print_stats(30)
    print(s2.getvalue())


if __name__ == '__main__':
    main()
