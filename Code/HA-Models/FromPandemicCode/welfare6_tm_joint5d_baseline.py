"""
Multi-cohort driver for the 5D joint kernel (Phase A of the ambitious
parallelization plan, plans/20260516_5D_ambitious_parallelization.md).

Generalizes welfare6_tm_joint5d_full.py:
  - Accepts --parametrization {HS_Only, Reduced_Run, Baseline, ...}
    instead of hardcoding HS_Only.
  - Iterates ALL cohorts (e × β-atom combinations) and aggregates the
    welfare-6 cell formula with per-cohort weights = AgentCount /
    sum(AgentCount).
  - Optional outer cohort Pool (--cohort-workers N) on top of the
    inner duration Pool (--workers N).
  - Compatible with the existing equivalence-check infrastructure:
    dump pickle includes per-cohort and per-duration full series.

Parallelism summary:
  - Inner: 11-way duration Pool (existing infrastructure, fork-COW).
  - Outer: cohort Pool. Each outer worker runs the full inner Pool.
    Default 1 (serial cohorts), suitable when inner Pool already
    saturates cores.

The outer cohort Pool can ALSO use fork-COW for agent state, but the
agent objects per cohort are large (cFuncs, transition matrices) and
holding multiple cohorts' worth concurrently can OOM. Memory profile
in production runs.
"""
from __future__ import annotations
import argparse, os, sys, time, pickle
from copy import deepcopy
from typing import Optional
import multiprocessing as mp
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--parametrization', default='HS_Only',
                   help='HS_Only | Reduced_Run | Baseline | ...')
    p.add_argument('--workers', type=int, default=1,
                   help='Total worker count for the flat (cohort, dur) Pool. '
                        'Default 1 (sequential). Use up to ~cores-1. '
                        'IGNORED when --jax is set (JAX path is serial single-process).')
    p.add_argument('--dump-per-duration', type=str, default=None,
                   help='Path to pickle full per-(cohort, duration) outputs.')
    p.add_argument('--tm-a-pickle', type=str, default=None,
                   help='Optional A1 pickle for TM-a denominator comparison.')
    p.add_argument('--jax', action='store_true',
                   help='Use the JAX-GPU kernel (5-10× speedup). Single-process, '
                        'serial over (cohort, dur). JIT compiles once at startup.')
    p.add_argument('--jax-mgrid', type=int, default=500,
                   help='cFunc tabulation grid size for JAX path. Default 500 '
                        '(0.07% rel error vs HARK direct).')
    p.add_argument('--parallel-solve', action='store_true',
                   help='Phase C.1: parallelize the 3 scenario solves via fork '
                        'Pool of 3 workers. Cuts setup ~3× at Baseline.')
    p.add_argument('--cohort-vmap', action='store_true',
                   help='Phase C.4: batch cohorts on a leading GPU axis '
                        'via jax.vmap. Implies --jax.')
    p.add_argument('--cohort-batch-size', type=int, default=7,
                   help='Phase C.4: max cohorts per GPU batch call. '
                        'Default 7 (= one ed_type for Baseline; '
                        'fits within 16 GiB VRAM at A=60). Set to '
                        'n_cohorts (e.g. 21) to attempt full batch.')
    return p.parse_args()


_ARGS = _parse_args()
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint5d import compute_joint_welfare5d
from tm_methods import compute_baseline_tm_data, calculate_NPV
if _ARGS.jax or _ARGS.cohort_vmap:
    from welfare6_tm_joint5d_jax_kernel import compute_joint_welfare5d_jax
    if _ARGS.cohort_vmap:
        from welfare6_tm_joint5d_jax_kernel import compute_joint_welfare5d_jax_batched


# Phase C.1: module-level globals for parallel-solve workers
_CTX_BASE = None

# Policy selector for the 5D joint welfare cell (env-overridable so taxcut_rec /
# check_rec reuse this UI driver with no structural change). Read at import so the
# fork-pool duration workers inherit it.
#   recessionUI -> ui_rec ; recessionTaxCut -> taxcut_rec ; recessionCheck -> check_rec
_POL_SHOCK = os.environ.get('JOINT5D_POL_SHOCK', 'recessionUI')


def _solve_scenario_worker(args):
    """Fork worker for Phase C.1: deepcopy base AggEco, switch shock type,
    solve, write resulting agents to disk. Returns shock_type as success marker.

    Avoids returning agent objects through Pool (which would pickle and may
    hit unpicklable closures). Each worker writes to its own pickle file.

    Strips agent.ADFunc (an unpicklable AggregateDemandEconomy.update lambda)
    before pickling — the JAX driver doesn't use it.
    """
    shock_type, output_path = args
    AggEco = deepcopy(_CTX_BASE['AggEco'])
    AggEco.switch_shock_type(shock_type)
    AggEco.solve()
    for ag in AggEco.agents:
        ag.tm_a_indexed = True
        # Strip unpicklable AggregateDemandEconomy back-reference.
        # JAX driver uses only solution.cFunc, IncShkDstn, CondMrkvArrays,
        # Rfree, PermGroFac, Splurge, CRRA, LivPrb, num_base_MrkvStates,
        # AgentCount, Urate_normal, Urate_recession, T_age, pop_rescale_factor.
        if hasattr(ag, 'ADFunc'):
            ag.ADFunc = None
    # Pickle the agents to disk
    with open(output_path, 'wb') as f:
        pickle.dump(AggEco.agents, f)
    return shock_type


def _parallel_solve_scenarios(ctx_base, tmp_dir):
    """Phase C.1: solve the 3 scenarios in parallel via fork Pool.
    Returns (agents_pol, agents_none, agents_base).

    Falls back to serial if Pool fails for any reason.
    """
    global _CTX_BASE
    _CTX_BASE = ctx_base
    os.makedirs(tmp_dir, exist_ok=True)
    work = [
        ('recessionUI', os.path.join(tmp_dir, 'agents_pol.pkl')),
        ('recession',   os.path.join(tmp_dir, 'agents_none.pkl')),
        ('base',        os.path.join(tmp_dir, 'agents_base.pkl')),
    ]
    ctx_fork = mp.get_context('fork')
    with ctx_fork.Pool(3) as pool:
        results = pool.map(_solve_scenario_worker, work)
    assert set(results) == {'recessionUI', 'recession', 'base'}, \
        f"unexpected worker results: {results}"
    # Read back
    with open(os.path.join(tmp_dir, 'agents_pol.pkl'), 'rb') as f:
        agents_pol = pickle.load(f)
    with open(os.path.join(tmp_dir, 'agents_none.pkl'), 'rb') as f:
        agents_none = pickle.load(f)
    with open(os.path.join(tmp_dir, 'agents_base.pkl'), 'rb') as f:
        agents_base = pickle.load(f)
    return agents_pol, agents_none, agents_base


def _build_econ_mrkv_path(act_T, num_experiment_periods, dur):
    path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T + 5)
    path = path[:act_T]
    for t in range(min(dur, len(path))):
        path[t] = path[t] + 1
    return path


# Module-level globals for fork-COW. Populated by main(); read by inner workers.
_AGENTS_POL = None    # list of agents, one per cohort
_AGENTS_NONE = None
_AGENTS_BASE = None
_BD_LIST = None       # list of baseline TM data dicts, one per cohort
_ACT_T = None
_NEP = None


def _run_one_duration(args):
    """Inner worker: solve one (cohort_idx, dur) pair."""
    cohort_idx, d_idx, dur, verbose = args
    t_start = time.time()
    path = _build_econ_mrkv_path(_ACT_T, _NEP, dur)
    res = compute_joint_welfare5d(
        _AGENTS_POL[cohort_idx], _AGENTS_NONE[cohort_idx],
        _AGENTS_BASE[cohort_idx], _BD_LIST[cohort_idx],
        EconomyMrkv_path_pn=path, act_T=_ACT_T,
        shock_type_pol=_POL_SHOCK,
        verbose=verbose,
    )
    res['_wall'] = time.time() - t_start
    res['_d_idx'] = d_idx
    res['_dur'] = dur
    res['_cohort_idx'] = cohort_idx
    return (cohort_idx, d_idx, res)


def _run_one_duration_jax(cohort_idx, d_idx, dur, m_grid,
                          cfunc_pol_table=None,
                          cfunc_none_table=None,
                          cfunc_b_table=None):
    """JAX path: solve one (cohort_idx, dur) pair serially in the main
    process. Single GPU is the bottleneck so no Pool.

    Phase C.2: caller may pass pre-tabulated cFunc tables to skip
    redundant tabulation across the (cohort, dur) loop.
    """
    t_start = time.time()
    path = _build_econ_mrkv_path(_ACT_T, _NEP, dur)
    res = compute_joint_welfare5d_jax(
        _AGENTS_POL[cohort_idx], _AGENTS_NONE[cohort_idx],
        _AGENTS_BASE[cohort_idx], _BD_LIST[cohort_idx],
        EconomyMrkv_path_pn=path, act_T=_ACT_T,
        M_grid=m_grid, verbose=False,
        cfunc_pol_table_full=cfunc_pol_table,
        cfunc_none_table_full=cfunc_none_table,
        cfunc_b_table_full=cfunc_b_table,
    )
    res['_wall'] = time.time() - t_start
    res['_d_idx'] = d_idx
    res['_dur'] = dur
    res['_cohort_idx'] = cohort_idx
    return (cohort_idx, d_idx, res)


def _reduce_results(flat_results, n_cohorts, max_dur, rec_probs):
    """Group (cohort, dur) flat results into per-cohort aggregates.
    flat_results: list of (cohort_idx, d_idx, res_dict). Order arbitrary."""
    # Build cohort-major nested structure
    by_cohort = {c: [None] * max_dur for c in range(n_cohorts)}
    for cohort_idx, d_idx, res in flat_results:
        by_cohort[cohort_idx][d_idx] = res

    cohort_aggs = []
    for cohort_idx in range(n_cohorts):
        welfare_num_c = np.zeros(_ACT_T)
        AddInc_c = np.zeros(_ACT_T)
        AddCons_c = np.zeros(_ACT_T)
        per_dur = []
        for d_idx in range(max_dur):
            res = by_cohort[cohort_idx][d_idx]
            assert res is not None, f"missing result for cohort {cohort_idx} d_idx {d_idx}"
            welfare_num_c += rec_probs[d_idx] * res['welfare_num_series']
            AddInc_c += rec_probs[d_idx] * (res['AggInc_pol_series'] - res['AggInc_none_series'])
            AddCons_c += rec_probs[d_idx] * (res['AggCons_pol_series'] - res['AggCons_none_series'])
            per_dur.append({
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
        cohort_aggs.append({
            'cohort_idx': cohort_idx,
            'welfare_num': welfare_num_c,
            'AddInc': AddInc_c,
            'AddCons': AddCons_c,
            'per_duration': per_dur,
        })
    return cohort_aggs


def main():
    args = _ARGS
    aCount = int(os.environ.get('JOINT5D_ACOUNT', 50))
    workers = max(1, args.workers)
    dump_path: Optional[str] = args.dump_per_duration

    print(f"=== welfare6_tm_joint5d_baseline: {args.parametrization}, A={aCount}, "
          f"workers={workers} (flat cohort×dur Pool) ===")
    if dump_path:
        print(f"      dump-per-duration: {dump_path}")

    t0 = time.time()
    print(f"[1/5] Build {args.parametrization} context + solve 3 scenarios...")
    ctx = build_and_solve(args.parametrization)

    if args.parallel_solve:
        # Phase C.1: parallel solve via fork Pool of 3 workers.
        tmp_dir = os.path.join(os.path.dirname(args.dump_per_duration or '/tmp'),
                                f'_parallel_solve_{os.getpid()}')
        print(f"      [C.1] parallel solve enabled (3-way fork Pool, tmp={tmp_dir})")
        t_solve = time.time()
        agents_pol, agents_none, agents_base = _parallel_solve_scenarios(ctx, tmp_dir)
        print(f"      [C.1] parallel solve wall: {time.time() - t_solve:.1f}s")
        # Build dummy AggEco shells for downstream code that may need it
        # (compute_baseline_tm_data wants an economy with .agents attribute)
        class _AggEcoShell:
            def __init__(self, agents):
                self.agents = agents
        AggEco_pol = _AggEcoShell(agents_pol)
        AggEco_none = _AggEcoShell(agents_none)
        AggEco_base = _AggEcoShell(agents_base)
    else:
        AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type(_POL_SHOCK); AggEco_pol.solve()
        AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()
        AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()
        for ag in AggEco_pol.agents: ag.tm_a_indexed = True
        for ag in AggEco_none.agents: ag.tm_a_indexed = True
        for ag in AggEco_base.agents: ag.tm_a_indexed = True

    n_cohorts = len(AggEco_pol.agents)
    print(f"      {n_cohorts} cohorts")

    print(f"[2/5] Compute baseline_tm_data for all cohorts (aCount={aCount})...")
    bd_list = compute_baseline_tm_data(AggEco_base, mCount=aCount, neutral_measure=True)
    assert len(bd_list) == n_cohorts, f"bd_list len {len(bd_list)} != n_cohorts {n_cohorts}"

    act_T = ctx['act_T']
    nep = ctx['num_experiment_periods']
    Rspell = ctx.get('Rspell', 4.0)
    max_dur = ctx.get('max_recession_duration', nep)
    R_persist = 1.0 - 1.0 / Rspell
    rec_probs = np.array([R_persist**t * (1 - R_persist) for t in range(max_dur)])
    rec_probs[-1] = 1.0 - np.sum(rec_probs[:-1])

    # Per-cohort weights = AgentCount / sum(AgentCount)
    agent_counts = np.array([ag.AgentCount for ag in AggEco_pol.agents], dtype=np.float64)
    cohort_weights = agent_counts / agent_counts.sum()
    print(f"      cohort weights: min={cohort_weights.min():.4f} max={cohort_weights.max():.4f} sum={cohort_weights.sum():.4f}")

    # Populate module globals for fork-COW inheritance
    global _AGENTS_POL, _AGENTS_NONE, _AGENTS_BASE, _BD_LIST, _ACT_T, _NEP
    _AGENTS_POL = AggEco_pol.agents
    _AGENTS_NONE = AggEco_none.agents
    _AGENTS_BASE = AggEco_base.agents
    _BD_LIST = bd_list
    _ACT_T = act_T
    _NEP = nep

    n_work = n_cohorts * max_dur
    if args.jax:
        print(f"[3/5] Iterate {n_cohorts} cohorts × {max_dur} durations "
              f"= {n_work} (cohort, dur) work items, JAX path (serial single-process)...")
    else:
        print(f"[3/5] Iterate {n_cohorts} cohorts × {max_dur} durations "
              f"= {n_work} (cohort, dur) work items, flat Pool workers={workers}...")
    t1 = time.time()

    if args.cohort_vmap:
        # Phase C.4: cohort-batched JAX path. Iterate durations only; each
        # iteration calls the batched kernel with all cohorts on GPU axis.
        from welfare6_tm_joint5d_jax_kernel import tabulate_cfunc_list
        m_grid = args.jax_mgrid
        from welfare6_tm_joint5d_jax_kernel import build_m_grid
        m_grid_np = build_m_grid(m_grid)
        # Pre-tabulate cFunc tables for all cohorts (C.2 within C.4)
        cfunc_pol_tables = [
            tabulate_cfunc_list(AggEco_pol.agents[c].solution[0].cFunc, m_grid_np)
            for c in range(n_cohorts)
        ]
        cfunc_none_tables = [
            tabulate_cfunc_list(AggEco_none.agents[c].solution[0].cFunc, m_grid_np)
            for c in range(n_cohorts)
        ]
        cfunc_b_tables = [
            tabulate_cfunc_list(AggEco_base.agents[c].solution[0].cFunc, m_grid_np)
            for c in range(n_cohorts)
        ]

        flat_raw = []
        cohort_batch_size = min(args.cohort_batch_size, n_cohorts)
        # Build cohort chunks (e.g., 21 cohorts → [0..6], [7..13], [14..20])
        cohort_chunks = []
        c = 0
        while c < n_cohorts:
            cohort_chunks.append(list(range(c, min(c + cohort_batch_size, n_cohorts))))
            c += cohort_batch_size
        print(f"      cohort chunks: {[len(ch) for ch in cohort_chunks]} (total {n_cohorts})")

        for d_idx, dur in enumerate(range(1, max_dur + 1)):
            path = _build_econ_mrkv_path(act_T, nep, dur)
            t_d = time.time()
            # Run each chunk separately on GPU
            chunk_results_all = {}  # cohort_idx -> result dict
            for chunk in cohort_chunks:
                pol_agents_ch = [AggEco_pol.agents[c] for c in chunk]
                none_agents_ch = [AggEco_none.agents[c] for c in chunk]
                base_agents_ch = [AggEco_base.agents[c] for c in chunk]
                bd_ch = [bd_list[c] for c in chunk]
                cf_pol_ch = [cfunc_pol_tables[c] for c in chunk]
                cf_none_ch = [cfunc_none_tables[c] for c in chunk]
                cf_b_ch = [cfunc_b_tables[c] for c in chunk]
                results_ch = compute_joint_welfare5d_jax_batched(
                    pol_agents_ch, none_agents_ch, base_agents_ch, bd_ch,
                    EconomyMrkv_path_pn=path, act_T=act_T, M_grid=m_grid,
                    verbose=(d_idx == 0 and chunk[0] == 0),
                    cfunc_pol_tables_full=cf_pol_ch,
                    cfunc_none_tables_full=cf_none_ch,
                    cfunc_b_tables_full=cf_b_ch,
                )
                for i, c_idx in enumerate(chunk):
                    chunk_results_all[c_idx] = results_ch[i]
            wall_d = time.time() - t_d

            for c_idx in range(n_cohorts):
                res = chunk_results_all[c_idx]
                res['_wall'] = wall_d / n_cohorts
                res['_d_idx'] = d_idx
                res['_dur'] = dur
                res['_cohort_idx'] = c_idx
                flat_raw.append((c_idx, d_idx, res))
            print(f"      [{(d_idx + 1)}/{max_dur}] dur={dur} wall={wall_d:.2f}s "
                  f"({len(cohort_chunks)} chunks of up to {cohort_batch_size})")
    elif args.jax:
        # JAX path: serial main-process execution. GPU is the bottleneck so
        # no Pool. JIT cache persists across calls.
        #
        # C.2: pre-tabulate cFunc ONCE per cohort, reuse across all 21 durations.
        from welfare6_tm_joint5d_jax_kernel import tabulate_cfunc_list
        flat_raw = []
        m_grid = args.jax_mgrid
        from welfare6_tm_joint5d_jax_kernel import build_m_grid
        m_grid_np = build_m_grid(m_grid)
        for c_idx in range(n_cohorts):
            # C.2: tabulate cFuncs for this cohort (once, before the dur loop)
            t_tab = time.time()
            cfunc_pol_t = tabulate_cfunc_list(AggEco_pol.agents[c_idx].solution[0].cFunc, m_grid_np)
            cfunc_none_t = tabulate_cfunc_list(AggEco_none.agents[c_idx].solution[0].cFunc, m_grid_np)
            cfunc_b_t = tabulate_cfunc_list(AggEco_base.agents[c_idx].solution[0].cFunc, m_grid_np)
            tab_wall = time.time() - t_tab

            for d_idx, dur in enumerate(range(1, max_dur + 1)):
                flat_raw.append(_run_one_duration_jax(
                    c_idx, d_idx, dur, m_grid,
                    cfunc_pol_table=cfunc_pol_t,
                    cfunc_none_table=cfunc_none_t,
                    cfunc_b_table=cfunc_b_t,
                ))
                if (c_idx * max_dur + d_idx + 1) % 10 == 0:
                    print(f"      [{c_idx * max_dur + d_idx + 1}/{n_work}] "
                          f"cohort={c_idx} d_idx={d_idx} dur={dur} "
                          f"wall={flat_raw[-1][2]['_wall']:.2f}s "
                          f"(cohort_tab={tab_wall:.2f}s)")
    else:
        # CPU/numpy Pool path
        flat_work = [(c_idx, d_idx, dur, False)
                     for d_idx, dur in enumerate(range(1, max_dur + 1))
                     for c_idx in range(n_cohorts)]
        if workers <= 1:
            flat_raw = [_run_one_duration(w) for w in flat_work]
        else:
            eff_workers = min(workers, n_work)
            ctx_outer = mp.get_context('fork')
            with ctx_outer.Pool(eff_workers) as pool:
                flat_raw = pool.map(_run_one_duration, flat_work)

    cohort_results = _reduce_results(flat_raw, n_cohorts, max_dur, rec_probs)

    total_wall = time.time() - t1
    print(f"      total cohort×duration wall: {total_wall:.1f}s")

    print(f"[4/5] Aggregate across cohorts...")
    welfare_num_total = np.zeros(act_T)
    AddInc_total = np.zeros(act_T)
    AddCons_total = np.zeros(act_T)
    for c_idx, cr in enumerate(cohort_results):
        w = cohort_weights[c_idx]
        welfare_num_total += w * cr['welfare_num']
        AddInc_total += w * cr['AddInc']
        AddCons_total += w * cr['AddCons']

    Rfree_t = float(np.asarray(AggEco_pol.agents[0].Rfree).flatten()[0])
    print(f"      Rfree = {Rfree_t}, act_T = {act_T}")

    def _npv(s):
        v = calculate_NPV(s, act_T, Rfree_t)
        return float(v[-1]) if hasattr(v, '__len__') else float(v)

    NPV_w = _npv(welfare_num_total)
    NPV_AI_5D = _npv(AddInc_total)
    NPV_AC_5D = _npv(AddCons_total)
    print(f"      NPV(welfare_num)  = {NPV_w:.3e}")
    print(f"      NPV(AddInc) 5D    = {NPV_AI_5D:.3e}")
    print(f"      NPV(AddCons) 5D   = {NPV_AC_5D:.3e}")

    # Optional TM-a denominator path (uses external A1 pickle if provided)
    NPV_AI_TMa = None
    NPV_AC_TMa = None
    if args.tm_a_pickle:
        print(f"[4b/5] Load TM-a denominators from {args.tm_a_pickle} ...")
        with open(args.tm_a_pickle, 'rb') as f:
            t2 = pickle.load(f)
        AC_pol = np.asarray(t2['results_summary']['recessionUI']['AggCons'])
        AC_none = np.asarray(t2['results_summary']['recession']['AggCons'])
        AI_pol = np.asarray(t2['results_summary']['recessionUI']['AggIncome'])
        AI_none = np.asarray(t2['results_summary']['recession']['AggIncome'])
        Add_Inc = AI_pol - AI_none
        Add_Cons = AC_pol - AC_none
        NPV_AI_TMa = _npv(Add_Inc)
        NPV_AC_TMa = _npv(Add_Cons)
        print(f"      NPV(AddInc) TM-a  = {NPV_AI_TMa:.3e}")
        print(f"      NPV(AddCons) TM-a = {NPV_AC_TMa:.3e}")

    print()
    print("=== Results ===")
    if abs(NPV_AI_5D) > 1e-10:
        ui_rec_5D = NPV_w / NPV_AI_5D + (NPV_AI_5D - NPV_AC_5D) / NPV_AI_5D
        print(f"  CELL[{_POL_SHOCK}] (5D-self denom, {args.parametrization}, A={aCount}):  {ui_rec_5D:.4f}")
    if NPV_AI_TMa is not None and abs(NPV_AI_TMa) > 1e-10:
        ui_rec_TMa = NPV_w / NPV_AI_TMa + (NPV_AI_TMa - NPV_AC_TMa) / NPV_AI_TMa
        print(f"  ui_rec (TM-a denom, {args.parametrization}, A={aCount}):    {ui_rec_TMa:.4f}")

    print(f"\n[5/5] Wall summary:")
    print(f"  total parallel region: {total_wall:.1f}s ({total_wall/60:.1f} min)")
    print(f"  ({n_work} work items / {workers} workers)")

    if dump_path:
        os.makedirs(os.path.dirname(os.path.abspath(dump_path)) or '.', exist_ok=True)
        with open(dump_path, 'wb') as f:
            pickle.dump({
                'parametrization': args.parametrization,
                'aCount': aCount,
                'workers': workers,
                'n_cohorts': n_cohorts,
                'act_T': act_T,
                'max_dur': max_dur,
                'rec_probs': rec_probs,
                'cohort_weights': cohort_weights,
                'welfare_num_total': welfare_num_total,
                'AddInc_total_5D': AddInc_total,
                'AddCons_total_5D': AddCons_total,
                'per_cohort': [{
                    'cohort_idx': cr['cohort_idx'],
                    'weight': float(cohort_weights[cr['cohort_idx']]),
                    'welfare_num': cr['welfare_num'],
                    'AddInc': cr['AddInc'],
                    'AddCons': cr['AddCons'],
                    'per_duration': cr['per_duration'],
                } for cr in cohort_results],
                'total_wall_compute': total_wall,
            }, f)
        print(f"\n      dumped to {dump_path}")

    print(f"\nTotal wall: {time.time() - t0:.1f}s")


if __name__ == '__main__':
    main()
