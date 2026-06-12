"""
Multi-cohort JAX MC — extends jax_mc_minimal to handle multiple cohorts.

For HAFiscal:
- HS_Only: 1 cohort (just HS, single beta)
- Reduced_Run: 3 cohorts (D + HS + C, single beta each)
- Baseline: 21 cohorts (3 ed × 7 beta atoms)

Each cohort has potentially different:
  - N_c, cFunc table, MrkvArray, IncShkDstn, Rfree, PermGroFac, LivPrb,
    Splurge, CRRA, initial state

Strategy: serial-cohort Python loop (each cohort is one simulate_jax call).
Simple, robust; per-cohort GPU dispatch is acceptable up to ~20 cohorts.
For larger scale, vmap-over-cohorts is the natural next step.
"""
from __future__ import annotations
import os, sys, time, pickle
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

import jax.numpy as jnp
from welfare6_scenario import build_and_solve
from jax_mc_hark_integration import (
    extract_hark_kernel_inputs, extract_recession_kernel_inputs,
    draw_newborn_pool_from_agent, _broadcast_employed_psi_to_all_states,
)
from jax_mc_minimal import simulate_jax
from jax_mc_recession import simulate_jax_recession


def simulate_all_cohorts(AggEco, scenario='base', act_T=40, seed_base=0,
                         verbose=True, hark_pickle_for_init=None):
    """Run JAX MC for all cohorts in AggEco; aggregate to economy-wide totals.

    If hark_pickle_for_init is given, slice its aNrm/pLvl/Mrkv panels by
    cohort and use as initial state — gives the proper per-cohort post-
    warmup state (impatient D vs patient C have very different steady
    states; agent.initialize_sim() proxy is wrong for both).

    Returns dict with:
      AggInc_total: (act_T,) — sum across cohorts
      AggCons_total: (act_T,)
      per_cohort_AggInc: (C, act_T)
      per_cohort_AggCons: (C, act_T)
      cohort_walls: list of per-cohort JAX wall times
      total_wall: scalar
    """
    AggEco.switch_shock_type(scenario)
    AggEco.solve()
    n_cohorts = len(AggEco.agents)
    if verbose:
        print(f"  scenario={scenario}, n_cohorts={n_cohorts}")

    # Build per-cohort slices into the concatenated HARK panels
    if hark_pickle_for_init is not None:
        import pickle
        hark = pickle.load(open(hark_pickle_for_init, 'rb'))
        h_aNrm = np.asarray(hark['aNrm_all_bs'])
        h_pLvl = np.asarray(hark['pLvl_all_bs'])
        h_mrkv = np.asarray(hark['Mrkv_hist_bs']) % 6
        slices = []
        start = 0
        for ag in AggEco.agents:
            slices.append(slice(start, start + ag.AgentCount))
            start += ag.AgentCount
        if verbose:
            print(f"  using HARK per-cohort init from {hark_pickle_for_init}")

    cohort_AggInc = []
    cohort_AggCons = []
    cohort_walls = []
    t0_total = time.time()

    for c, agent in enumerate(AggEco.agents):
        inp = extract_hark_kernel_inputs(agent, scenario=scenario)
        # Apply BUG-040 psi broadcast if active
        if getattr(agent, 'perm_shocks_during_unemployment', False):
            new_psi, new_xi, new_pmv, new_natoms = _broadcast_employed_psi_to_all_states(
                inp['IncShk_psi'], inp['IncShk_xi'], inp['IncShk_pmv'], inp['IncShk_natoms'])
            inp['IncShk_psi'] = new_psi
            inp['IncShk_xi']  = new_xi
            inp['IncShk_pmv'] = new_pmv
            inp['IncShk_natoms'] = new_natoms
        agent.initialize_sim()
        N = agent.AgentCount
        if N == 0:
            continue
        if hark_pickle_for_init is not None:
            sl = slices[c]
            aNrm0 = h_aNrm[0, sl].astype(np.float32)
            pLvl0 = h_pLvl[0, sl].astype(np.float32)
            mrkv0 = h_mrkv[0, sl].astype(np.int32)
        else:
            aNrm0 = np.asarray(agent.state_now['aNrm'][:N], dtype=np.float32)
            pLvl0 = np.asarray(agent.state_now['pLvl'][:N], dtype=np.float32)
            mrkv0 = np.zeros(N, dtype=np.int32)
        # HARK newborn distribution (kNrmInitDstn / pLvlInitDstn), large pool
        newborn_aNrm, newborn_pLvl, newborn_mrkv = draw_newborn_pool_from_agent(
            agent, pool_N=10000, seed=99 + c)

        jargs = (
            aNrm0, pLvl0, mrkv0,
            jnp.asarray(inp['cfunc_table']), jnp.asarray(inp['m_grid']),
            jnp.asarray(inp['Rfree']), jnp.asarray(inp['PermGroFac']),
            jnp.asarray(inp['MrkvArray']),
            jnp.asarray(inp['IncShk_psi']), jnp.asarray(inp['IncShk_xi']),
            jnp.asarray(inp['IncShk_pmv']),
            1.0, 1.0, inp['Splurge'], inp['LivPrb'],
            jnp.asarray(newborn_aNrm), jnp.asarray(newborn_pLvl),
            jnp.asarray(newborn_mrkv),
        )
        # Warm-up per (cohort, shape) — JIT recompiles on different N
        _ = simulate_jax(*jargs, act_T, seed_base=seed_base, pLvl_unemp_mode='qe')

        t1 = time.time()
        inc, cons, _ = simulate_jax(*jargs, act_T, seed_base=seed_base + c * 100,
                                    pLvl_unemp_mode='qe')
        wall_c = time.time() - t1
        cohort_AggInc.append(np.asarray(inc))
        cohort_AggCons.append(np.asarray(cons))
        cohort_walls.append(wall_c)
        if verbose and c < 3:
            print(f"    cohort {c} (N={N}): wall={wall_c*1000:.1f}ms, "
                  f"mean AggInc={float(inc.mean()):.1f}")

    total_wall = time.time() - t0_total
    cohort_AggInc = np.stack(cohort_AggInc) if cohort_AggInc else np.zeros((0, act_T))
    cohort_AggCons = np.stack(cohort_AggCons) if cohort_AggCons else np.zeros((0, act_T))
    return dict(
        AggInc_total=cohort_AggInc.sum(axis=0),
        AggCons_total=cohort_AggCons.sum(axis=0),
        per_cohort_AggInc=cohort_AggInc,
        per_cohort_AggCons=cohort_AggCons,
        cohort_walls=cohort_walls,
        total_wall=total_wall,
    )


def simulate_all_cohorts_recession(AggEco, scenario='recession',
                                    act_T=40, num_experiment_periods=10,
                                    max_recession_duration=11,
                                    seed_base=0, verbose=True,
                                    hark_pickle_for_init=None,
                                    rec_probs=None):
    """Multi-cohort recession scenario with per-duration aggregation.

    For each cohort:
      - Extract per-macro arrays (cfunc_table, MrkvArray, etc.) via
        extract_recession_kernel_inputs
      - Loop over durations 1..max_recession_duration
      - Build EconomyMrkv_path for each duration (recession ends at dur)
      - Run JAX recession kernel
      - Per-cohort: weight per-duration outputs by rec_probs

    Returns dict with dur-weighted AggInc, AggCons aggregated across
    cohorts; plus per-cohort, per-duration panels for diagnostics.
    """
    AggEco.switch_shock_type(scenario)
    AggEco.solve()
    n_cohorts = len(AggEco.agents)
    if verbose:
        print(f"  scenario={scenario}, n_cohorts={n_cohorts}, durations={max_recession_duration}")

    # If rec_probs not given, use HAFiscal default (geometric with Rspell=6)
    if rec_probs is None:
        Rspell = 6
        rec_probs = np.array([
            (1.0 - 1.0/Rspell) ** d * (1.0/Rspell)
            for d in range(max_recession_duration)
        ])
        rec_probs[-1] = 1.0 - np.sum(rec_probs[:-1])

    # HARK init slices
    if hark_pickle_for_init is not None:
        hark = pickle.load(open(hark_pickle_for_init, 'rb'))
        h_aNrm = np.asarray(hark['aNrm_all_bs'])
        h_pLvl = np.asarray(hark['pLvl_all_bs'])
        h_mrkv = np.asarray(hark['Mrkv_hist_bs'])
        slices = []
        start = 0
        for ag in AggEco.agents:
            slices.append(slice(start, start + ag.AgentCount))
            start += ag.AgentCount

    # Build per-duration EconomyMrkv_paths
    paths = []
    for dur in range(max_recession_duration):
        rec_path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * 20
        rec_path[0:dur+1] = (np.array(rec_path[0:dur+1]) + 1).tolist()
        path = (rec_path + [0] * (act_T - len(rec_path)))[:act_T]
        paths.append(path)
    AggDemandFac_path = np.ones(act_T, dtype=np.float32)

    per_cohort_AggInc_dur = []
    per_cohort_AggCons_dur = []
    cohort_walls = []
    t0_total = time.time()
    for c, agent in enumerate(AggEco.agents):
        inp = extract_recession_kernel_inputs(agent, scenario=scenario, M_grid=500)
        J = inp['J']
        if hark_pickle_for_init is not None:
            sl = slices[c]
            aNrm0 = h_aNrm[0, sl].astype(np.float32)
            pLvl0 = h_pLvl[0, sl].astype(np.float32)
            mrkv_micro0 = (h_mrkv[0, sl] % J).astype(np.int32)
        else:
            agent.initialize_sim()
            N = agent.AgentCount
            aNrm0 = np.asarray(agent.state_now['aNrm'][:N], dtype=np.float32)
            pLvl0 = np.asarray(agent.state_now['pLvl'][:N], dtype=np.float32)
            mrkv_micro0 = np.zeros(N, dtype=np.int32)
        nbA, nbP, nbM = draw_newborn_pool_from_agent(agent, pool_N=10000, seed=99 + c)
        dur_AggInc = np.zeros((max_recession_duration, act_T))
        dur_AggCons = np.zeros((max_recession_duration, act_T))
        t1 = time.time()
        for dur, path in enumerate(paths):
            inc, cons, _ = simulate_jax_recession(
                aNrm0, pLvl0, mrkv_micro0,
                path, AggDemandFac_path,
                jnp.asarray(inp['cfunc_table_macro']), jnp.asarray(inp['m_grid']),
                jnp.asarray(inp['Rfree_macro']), jnp.asarray(inp['PermGroFac_macro']),
                jnp.asarray(inp['MrkvArray_macro']),
                jnp.asarray(inp['IncShk_psi_macro']), jnp.asarray(inp['IncShk_xi_macro']),
                jnp.asarray(inp['IncShk_pmv_macro']),
                inp['Splurge'], inp['LivPrb'], jnp.asarray(nbA), jnp.asarray(nbP),
                act_T=act_T, seed_base=seed_base + dur * 100, pLvl_unemp_mode='qe')
            dur_AggInc[dur] = np.asarray(inc)
            dur_AggCons[dur] = np.asarray(cons)
        wall_c = time.time() - t1
        cohort_walls.append(wall_c)
        per_cohort_AggInc_dur.append(dur_AggInc)
        per_cohort_AggCons_dur.append(dur_AggCons)
        if verbose:
            cohort_dur_weighted = (rec_probs[:, None] * dur_AggInc).sum(axis=0)
            print(f"    cohort {c}: wall={wall_c*1000:.0f}ms ({max_recession_duration} durs), "
                  f"weighted AggInc mean={cohort_dur_weighted.mean():.1f}")

    total_wall = time.time() - t0_total
    per_cohort_AggInc_dur = np.stack(per_cohort_AggInc_dur)  # (C, D, T)
    per_cohort_AggCons_dur = np.stack(per_cohort_AggCons_dur)
    # Aggregate: sum across cohorts, weighted by rec_probs across durations
    AggInc_dur_weighted = (rec_probs[None, :, None] * per_cohort_AggInc_dur).sum(axis=1)  # (C, T)
    AggCons_dur_weighted = (rec_probs[None, :, None] * per_cohort_AggCons_dur).sum(axis=1)
    AggInc_total = AggInc_dur_weighted.sum(axis=0)  # (T,)
    AggCons_total = AggCons_dur_weighted.sum(axis=0)
    return dict(
        AggInc_total=AggInc_total, AggCons_total=AggCons_total,
        per_cohort_AggInc_dur=per_cohort_AggInc_dur,
        per_cohort_AggCons_dur=per_cohort_AggCons_dur,
        rec_probs=rec_probs,
        cohort_walls=cohort_walls, total_wall=total_wall,
    )


def main():
    parametrization = os.environ.get('PARAMETRIZATION', 'Reduced_Run')
    print(f"=== Multi-cohort JAX MC: {parametrization} ===")
    print("\n[1/3] build_and_solve...")
    t0 = time.time()
    ctx = build_and_solve(parametrization)
    solve_wall = time.time() - t0
    print(f"  solve wall: {solve_wall:.1f}s")
    print(f"  n_cohorts: {len(ctx['AggEco'].agents)}")
    print(f"  per-cohort AgentCount: {[a.AgentCount for a in ctx['AggEco'].agents]}")
    print(f"  act_T: {ctx.get('act_T', 'n/a')}")

    print(f"\n[2/3] Simulate base scenario (all cohorts)...")
    result = simulate_all_cohorts(
        ctx['AggEco'], scenario='base',
        act_T=ctx.get('act_T', 40),
        seed_base=0)
    print(f"\n  Total JAX wall: {result['total_wall']:.3f}s")
    print(f"  Per-cohort walls: {[f'{w*1000:.0f}ms' for w in result['cohort_walls'][:5]]}...")
    print(f"  AggInc_total[0..4]: {result['AggInc_total'][:5]}")
    print(f"  AggCons_total[0..4]: {result['AggCons_total'][:5]}")
    print(f"  Mean AggInc: {result['AggInc_total'].mean():.3f}")
    print(f"  Mean AggCons: {result['AggCons_total'].mean():.3f}")

    print(f"\n[3/3] Compare to HARK (if pickle exists)...")
    pkl_candidates = [
        f'welfare6_RR_clean_nshuf/base.pkl' if parametrization == 'Reduced_Run' else '',
        f'welfare6_HS_clean_nshuf/base.pkl' if parametrization == 'HS_Only' else '',
        f'welfare6_stratified_bench_{parametrization}/seed0/base.pkl',
        f'welfare6_BUG044_{parametrization.lower()}_nshuf_1x/base.pkl',
    ]
    for pkl in pkl_candidates:
        if os.path.exists(pkl):
            hark = pickle.load(open(pkl, 'rb'))
            h_inc = np.asarray(hark['AggIncome'])
            h_cons = np.asarray(hark['AggCons'])
            print(f"  Loaded {pkl}")
            print(f"  HARK mean AggInc: {h_inc.mean():.3f}, AggCons: {h_cons.mean():.3f}")
            print(f"  Ratio JAX/HARK: AggInc={result['AggInc_total'].mean()/h_inc.mean():.4f}, "
                  f"AggCons={result['AggCons_total'].mean()/h_cons.mean():.4f}")
            # Drop-1 correlation
            T = min(len(result['AggInc_total']), len(h_inc))
            corr_inc = np.corrcoef(result['AggInc_total'][1:T], h_inc[1:T])[0, 1]
            corr_cons = np.corrcoef(result['AggCons_total'][1:T], h_cons[1:T])[0, 1]
            print(f"  Per-period corr (skip t=0): AggInc={corr_inc:.3f}, AggCons={corr_cons:.3f}")
            break
    else:
        print(f"  No HARK pickle found")


if __name__ == '__main__':
    main()
