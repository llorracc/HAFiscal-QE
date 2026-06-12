"""
Multi-duration HS_Only driver for the 5D joint kernel.

Computes ui_rec via the welfare-6 formula, weighting per-duration contributions
by recession probabilities. Compares against MC reference.

Parallelism:
  --workers N      (or JOINT5D_NUM_WORKERS env var)
                   N=1: in-process sequential loop (bit-identical to original code).
                   N>1: multiprocessing.Pool.map over the 11-way duration axis.
                   Reductions sum in d_idx order so floating-point output is
                   deterministic regardless of Pool completion order.

Diagnostics:
  --dump-per-duration PATH  (or JOINT5D_DUMP_PATH env var)
                   Pickle full per-duration outputs + final reduced arrays for
                   equivalence-checking the parallel implementation.
"""
from __future__ import annotations
import argparse, os, sys, time, pickle
from copy import deepcopy
from typing import Optional
import multiprocessing as mp
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Parse args BEFORE clobbering sys.argv (the HARK Parameters.py workaround
# below would otherwise hide our CLI flags from argparse).
def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--workers', type=int, default=None,
                   help='Number of parallel workers. Default: JOINT5D_NUM_WORKERS env var, else 1.')
    p.add_argument('--dump-per-duration', type=str, default=None,
                   help='Path to pickle full per-duration outputs for equivalence checks.')
    return p.parse_args()


_ARGS = _parse_args()
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint5d import compute_joint_welfare5d
from tm_methods import compute_baseline_tm_data, calculate_NPV


def _build_econ_mrkv_path(act_T, num_experiment_periods, dur):
    path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T + 5)
    path = path[:act_T]
    for t in range(min(dur, len(path))):
        path[t] = path[t] + 1
    return path


# Module-level globals populated in main BEFORE forking the Pool.
# Workers inherit these via Linux fork() copy-on-write — no pickling needed,
# which avoids the AggregateDemandEconomy.update.<locals>.<lambda> pickle error.
_AGENT_POL = None
_AGENT_NONE = None
_AGENT_BASE = None
_BD = None
_ACT_T = None
_NEP = None


def _run_one_duration(args):
    """Worker: solve one recession duration. Reads agents from module globals
    inherited via fork() to avoid pickling unpicklable HARK closures."""
    d_idx, dur, verbose = args
    t_start = time.time()
    path = _build_econ_mrkv_path(_ACT_T, _NEP, dur)
    res = compute_joint_welfare5d(
        _AGENT_POL, _AGENT_NONE, _AGENT_BASE, _BD,
        EconomyMrkv_path_pn=path, act_T=_ACT_T,
        verbose=verbose,
    )
    res['_wall'] = time.time() - t_start
    res['_d_idx'] = d_idx
    res['_dur'] = dur
    return d_idx, res


def main():
    args = _ARGS

    aCount = int(os.environ.get('JOINT5D_ACOUNT', 20))
    workers = args.workers
    if workers is None:
        workers = int(os.environ.get('JOINT5D_NUM_WORKERS', 1))
    if workers < 1:
        workers = 1

    dump_path: Optional[str] = args.dump_per_duration or os.environ.get('JOINT5D_DUMP_PATH')

    print(f"=== welfare6_tm_joint5d_full: ui_rec multi-duration (HS_Only, A={aCount}, workers={workers}) ===")
    if dump_path:
        print(f"      dump-per-duration: {dump_path}")

    t0 = time.time()
    print("[1/5] Load existing A1 pickle for AggCons/AggIncome denominators...")
    HERE = os.path.dirname(os.path.abspath(__file__))
    T2_PKL = os.path.join(HERE, "reproduce/logs/tm_a_phase3/A1_HS_Only_bugfix_A50.pkl")
    with open(T2_PKL, 'rb') as f:
        t2 = pickle.load(f)
    AC_pol = np.asarray(t2['results_summary']['recessionUI']['AggCons'])
    AC_none = np.asarray(t2['results_summary']['recession']['AggCons'])
    AI_pol = np.asarray(t2['results_summary']['recessionUI']['AggIncome'])
    AI_none = np.asarray(t2['results_summary']['recession']['AggIncome'])
    _rf = t2['results_summary']['recessionUI']['Rfree']
    Rfree_t = float(_rf if np.isscalar(_rf) else _rf[0])
    print(f"      Rfree = {Rfree_t}, act_T = {len(AC_pol)}")

    print("[2/5] Build HS_Only context + solve 3 scenarios...")
    ctx = build_and_solve('HS_Only')
    AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
    AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()
    AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()
    for ag in AggEco_pol.agents: ag.tm_a_indexed = True
    for ag in AggEco_none.agents: ag.tm_a_indexed = True
    for ag in AggEco_base.agents: ag.tm_a_indexed = True

    print(f"[3/5] Compute baseline_tm_data (aCount={aCount})...")
    bd_list = compute_baseline_tm_data(AggEco_base, mCount=aCount, neutral_measure=True)

    agent_pol = AggEco_pol.agents[0]
    agent_none = AggEco_none.agents[0]
    agent_base = AggEco_base.agents[0]
    bd = bd_list[0]
    act_T = ctx['act_T']
    nep = ctx['num_experiment_periods']

    Rspell = ctx.get('Rspell', 4.0)
    max_dur = ctx.get('max_recession_duration', nep)
    R_persist = 1.0 - 1.0 / Rspell
    rec_probs = np.array([R_persist**t * (1 - R_persist) for t in range(max_dur)])
    rec_probs[-1] = 1.0 - np.sum(rec_probs[:-1])

    eff_workers = min(workers, max_dur)
    print(f"[4/5] Iterate {max_dur} durations (workers={eff_workers})...")
    t1 = time.time()

    # Populate module globals so forked workers can read agents via COW
    # (avoids pickling unpicklable HARK closures).
    global _AGENT_POL, _AGENT_NONE, _AGENT_BASE, _BD, _ACT_T, _NEP
    _AGENT_POL = agent_pol
    _AGENT_NONE = agent_none
    _AGENT_BASE = agent_base
    _BD = bd
    _ACT_T = act_T
    _NEP = nep

    # Build work list. Verbose only for d_idx=0 to preserve original log shape
    # when sequential; suppress in Pool to avoid interleaved output.
    work = [(d_idx, dur, d_idx == 0 and eff_workers == 1)
            for d_idx, dur in enumerate(range(1, max_dur + 1))]

    if eff_workers <= 1:
        # In-process sequential path — bit-identical to pre-refactor code.
        results = [_run_one_duration(w) for w in work]
    else:
        # 'fork' is Linux default; child processes inherit module globals via COW.
        ctx = mp.get_context('fork')
        with ctx.Pool(eff_workers) as pool:
            results = pool.map(_run_one_duration, work)

    # Reduction MUST be in d_idx order for floating-point determinism.
    results.sort(key=lambda kv: kv[0])

    welfare_num_total = np.zeros(act_T)
    AddInc_total_5D = np.zeros(act_T)
    AddCons_total_5D = np.zeros(act_T)
    per_dur_dump = []
    for d_idx, res in results:
        welfare_num_total += rec_probs[d_idx] * res['welfare_num_series']
        AddInc_total_5D += rec_probs[d_idx] * (res['AggInc_pol_series'] - res['AggInc_none_series'])
        AddCons_total_5D += rec_probs[d_idx] * (res['AggCons_pol_series'] - res['AggCons_none_series'])
        print(f"      dur={res['_dur']:2d}, prob={rec_probs[d_idx]:.4f}, "
              f"sum(w_num)={res['welfare_num_series'].sum():.3e}, "
              f"sum(AddInc_5D)={(res['AggInc_pol_series']-res['AggInc_none_series']).sum():.3e}, "
              f"wall={res['_wall']:.1f}s")
        if dump_path:
            per_dur_dump.append({
                'd_idx': d_idx,
                'dur': res['_dur'],
                'rec_prob': float(rec_probs[d_idx]),
                'welfare_num_series': res['welfare_num_series'].copy(),
                'AggInc_pol_series': res['AggInc_pol_series'].copy(),
                'AggInc_none_series': res['AggInc_none_series'].copy(),
                'AggCons_pol_series': res['AggCons_pol_series'].copy(),
                'AggCons_none_series': res['AggCons_none_series'].copy(),
                'wall': res['_wall'],
            })

    total_wall_parallel = time.time() - t1
    print(f"      total wall: {total_wall_parallel:.1f}s")

    print(f"[5/5] welfare-6 cell formula:")
    Add_Inc = AI_pol - AI_none
    Add_Cons = AC_pol - AC_none
    def _npv_scalar(s):
        v = calculate_NPV(s, act_T, Rfree_t)
        return float(v[-1]) if hasattr(v, '__len__') else float(v)
    NPV_w = _npv_scalar(welfare_num_total)
    NPV_AI_TMa = _npv_scalar(Add_Inc)
    NPV_AC_TMa = _npv_scalar(Add_Cons)
    NPV_AI_5D = _npv_scalar(AddInc_total_5D)
    NPV_AC_5D = _npv_scalar(AddCons_total_5D)
    print(f"      NPV(welfare_num)  = {NPV_w:.3e}")
    print(f"      NPV(AddInc) TM-a  = {NPV_AI_TMa:.3e}")
    print(f"      NPV(AddInc) 5D    = {NPV_AI_5D:.3e}")
    print(f"      NPV(AddCons) TM-a = {NPV_AC_TMa:.3e}")
    print(f"      NPV(AddCons) 5D   = {NPV_AC_5D:.3e}")
    print()
    print("=== Results ===")
    if abs(NPV_AI_TMa) > 1e-10:
        ui_rec_TMa = NPV_w / NPV_AI_TMa + (NPV_AI_TMa - NPV_AC_TMa) / NPV_AI_TMa
        print(f"  ui_rec (TM-a denom, A={aCount}):  {ui_rec_TMa:.4f}")
    if abs(NPV_AI_5D) > 1e-10:
        ui_rec_5D = NPV_w / NPV_AI_5D + (NPV_AI_5D - NPV_AC_5D) / NPV_AI_5D
        print(f"  ui_rec (5D-self denom, A={aCount}):  {ui_rec_5D:.4f}")
    print(f"  ui_rec (MC nshuf 6-seed):       1.6168 ± 0.0027")

    if dump_path:
        os.makedirs(os.path.dirname(os.path.abspath(dump_path)) or '.', exist_ok=True)
        with open(dump_path, 'wb') as f:
            pickle.dump({
                'aCount': aCount,
                'workers': eff_workers,
                'act_T': act_T,
                'max_dur': max_dur,
                'rec_probs': rec_probs,
                'welfare_num_total': welfare_num_total,
                'AddInc_total_5D': AddInc_total_5D,
                'AddCons_total_5D': AddCons_total_5D,
                'per_duration': per_dur_dump,
                'total_wall_parallel_region': total_wall_parallel,
            }, f)
        print(f"\n      dumped per-duration outputs to {dump_path}")

    print(f"\nTotal wall: {time.time() - t0:.1f}s")


if __name__ == '__main__':
    main()
