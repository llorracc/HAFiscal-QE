"""
Step 11: Multi-cohort JAX-backed AD outer loop.

Generalizes jax_mc_ad_solve.solve_ad_recession_jax to multi-cohort
configurations (Reduced_Run, Baseline). Each iter:
  1. eco.solve() for all cohorts (HARK)
  2. For each cohort: extract recession kernel inputs, build cfunc table,
     run JAX MC with current Cratio_obs beliefs
  3. Aggregate AggCons across cohorts with pop_rescale_factor weights
  4. Compute Cratio_hist = AggCons_total / base_AggCons
  5. Build new MacroCFunc; step CFunc; install across all cohorts
"""
from __future__ import annotations
import os, time
import numpy as np
import jax.numpy as jnp
from jax_mc_ad import (simulate_jax_ad, extract_cfunc_table_per_period,
                        compute_AggDemandFac_path,
                        # Speedup 1A: (m, C) bilinear lift
                        simulate_jax_ad_2d, extract_cfunc_2d_table,
                        # Speedup 1B: vmap across seeds
                        simulate_jax_ad_2d_vmap_seeds,
                        # Speedup 2A: vmap across cohorts + seeds
                        simulate_jax_ad_2d_vmap_cohorts_seeds)

# Speedup 1A toggle: HAFISCAL_JAX_MC_USE_2D_LIFT=1 uses bilinear-in-C cFunc
# lift instead of per-period rebuild. Off by default for backward compat.
_USE_2D_LIFT = os.environ.get("HAFISCAL_JAX_MC_USE_2D_LIFT", "0") == "1"
# Speedup 1B toggle: HAFISCAL_JAX_MC_VMAP_SEEDS=1 runs all seeds in one
# vmap'd JIT call instead of looping. Requires 1A (2D lift) to be on.
_VMAP_SEEDS = os.environ.get("HAFISCAL_JAX_MC_VMAP_SEEDS", "0") == "1"
# Speedup 1C toggle: HAFISCAL_JAX_MC_BATCH_TABLES=1 stacks per-cohort cfunc
# tables into one big tensor + single host->device transfer per iter.
# Requires 1A on. Sets up infrastructure for 2A vmap-across-cohorts.
_BATCH_TABLES = os.environ.get("HAFISCAL_JAX_MC_BATCH_TABLES", "0") == "1"
# Speedup 1D toggle: HAFISCAL_JAX_MC_LAZY_PANEL=1 skips cLvl_panel
# materialization on non-final AD iters. Requires 1A+1B.
_LAZY_PANEL = os.environ.get("HAFISCAL_JAX_MC_LAZY_PANEL", "0") == "1"
# Speedup 2A toggle: HAFISCAL_JAX_MC_VMAP_COHORTS=1 runs ALL cohorts in
# one vmap'd JIT call (padding cohort N to max_N). Requires 1A+1B+1C.
_VMAP_COHORTS = os.environ.get("HAFISCAL_JAX_MC_VMAP_COHORTS", "0") == "1"
from jax_mc_hark_integration import extract_recession_kernel_inputs, draw_newborn_pool_from_agent

# Optional shuffle simulator (jax_mc_ad_shuffle)
try:
    from jax_mc_ad_shuffle import simulate_jax_ad_shuffle
    _HAS_SHUFFLE = True
except ImportError:
    _HAS_SHUFFLE = False

# Policy kernel (for Check / TaxCut scenarios that need per-period income overrides)
try:
    from jax_mc_policy_scenarios import simulate_jax_policy, compute_check_amount_per_agent
    _HAS_POLICY = True
except ImportError:
    _HAS_POLICY = False


_POLICY_SCENARIOS = {'recessionCheck', 'recessionTaxCut', 'Check', 'TaxCut'}
_RECESSION_SCENARIOS = {'recession', 'recessionUI', 'recessionCheck', 'recessionTaxCut'}


def _build_init_panels_via_hark_quick_sim(eco, shock_type, verbose=True):
    """Run a 1-step HARK no-AD recession cycle on a deepcopy to capture
    history[0] as JAX init.

    HARK's run_experiment calls initialize_sim() (fresh state draws) +
    hit_with_recession_shock (spike) + make_history (forward sim).
    history[0] = post-first-step state, which is purely a function of the
    initial draws + recession shock + 1 step of the kernel — does NOT
    depend on the subsequent ~40 forward sim steps. So running with
    T_sim=1 / act_T=1 produces a bit-identical history[0] in
    ~1/T_sim_full of the wall time. At Baseline this turns a ~40 min
    forward sim into ~1 min.

    The previous "full forward sim" variant is preserved behind
    HAFISCAL_HARK_REFSIM_FULL=1 for paranoia / regression-testing.

    Wall cost: ~one HARK no-AD eco.solve + ~1 period of make_history.
    Verified bit-identical to the full-sim variant at HS_Only.

    agent.aNrm_base does NOT work as init (it's the pre-sim state, not
    the post-step state JAX expects; and HARK redraws fresh state inside
    run_experiment so _base isn't even what HARK uses).
    """
    from copy import deepcopy
    eco_ref = deepcopy(eco)
    eco_ref.switch_shock_type(shock_type)
    if verbose:
        print(f"  [jax-ad-mc] auto-init: running HARK no-AD ref sim "
              f"({shock_type}) to capture t=0 state...", flush=True)
    t0 = time.time()
    # Step 1 (real fix): the original code called eco_ref.solve() BEFORE
    # updating each agent's MrkvArray, which meant the solve happened at
    # the BASE state space (fast but wasted). The real recession-state-space
    # solve then happened in the per-cohort `solve_if_changed()` loop below
    # — serial × 21 cohorts ≈ 945s. Fix: call update_mrkv_array on each
    # agent FIRST so eco_ref.solve() solves at recession directly, then set
    # MrkvArray_prev=MrkvArray so the per-cohort solve_if_changed short-
    # circuits instead of re-solving.
    for ThisType in eco_ref.agents:
        ThisType.update_mrkv_array(shock_type)
    # Optional cohort-parallel solve (HAFISCAL_REFSIM_PARALLEL=N>1, uses
    # fork-based parallel_eco_solve with plain HARK solve_agent in each
    # worker — bypasses the welfare6_scenario 2B-aware persistent pool).
    _refsim_parallel = os.environ.get('HAFISCAL_REFSIM_PARALLEL', '').strip()
    t_solve_start = time.time()
    if _refsim_parallel.isdigit() and int(_refsim_parallel) > 1:
        n_refsim_workers = int(_refsim_parallel)
        if verbose:
            print(f"  [jax-ad-mc] auto-init: parallel HARK ref-sim solve "
                  f"with {n_refsim_workers} fork workers...", flush=True)
        from parallel_solve import parallel_eco_solve
        parallel_eco_solve(eco_ref, n_workers=n_refsim_workers,
                           warm_start=True, verbose=verbose)
    else:
        eco_ref.solve()
    # Short-circuit the per-cohort solve_if_changed() loop below: its purpose
    # is to detect MrkvArray drift and re-solve, but we've already solved at
    # the current MrkvArray. Setting MrkvArray_prev=MrkvArray makes the
    # check pass and the loop's self.solve() call is skipped.
    for ThisType in eco_ref.agents:
        ThisType.MrkvArray_prev = ThisType.MrkvArray
    if verbose:
        print(f"  [jax-ad-mc] auto-init: eco_ref.solve done in "
              f"{time.time()-t_solve_start:.1f}s", flush=True)
    num_exp = eco_ref.num_experiment_periods
    EconomyMrkv_init = list(np.arange(1, num_exp + 1) * 2 + 1) + [1] * 12 + [0] * 20

    fast = os.environ.get('HAFISCAL_HARK_REFSIM_FULL', '').lower() not in ('1', 'on', 'true')

    if fast:
        # Run only 1 step of make_history: history[0] is determined by
        # initialize_sim + hit_with_recession_shock + 1 kernel step;
        # subsequent steps don't affect history[0]. Replicates what
        # AggregateDemandEconomy.run_experiment does, but with T_sim=1.
        eco_ref.act_T = 1
        eco_ref.EconomyMrkvNow_hist = [EconomyMrkv_init[0]]
        eco_ref.sow_init['CratioNow'] = eco_ref.CFunc[0][
            EconomyMrkv_init[0] * eco_ref.num_base_MrkvStates].intercept
        RecState = EconomyMrkv_init[0] % 2 == 1
        eco_ref.sow_init['AggDemandFac'] = eco_ref.ADFunc(
            eco_ref.sow_init['CratioNow'], RecState)
        exp_dict = {
            'use_prestate': True, 'shock_type': shock_type, 'UpdatePrb': 1.0,
        }
        for ThisType in eco_ref.agents:
            ThisType.T_sim = 1
            ThisType.read_shocks = True
            ThisType.assign_parameters(**exp_dict)
            ThisType.update_mrkv_array(shock_type)
            ThisType.solve_if_changed()
            ThisType.initialize_sim()
            ThisType.EconomyMrkvNow_hist = eco_ref.EconomyMrkvNow_hist
            if getattr(ThisType, 'mc_shuffle', False):
                ThisType._hit_with_recession_shock_shuffled(shock_type)
            else:
                ThisType.hit_with_recession_shock(shock_type)
        eco_ref.make_history()
    else:
        # Legacy: run the full ~40-step forward sim (only history[0] is
        # actually used). Kept behind HAFISCAL_HARK_REFSIM_FULL=1 as a
        # safety net.
        rec_dict = {
            'shock_type': shock_type, 'UpdatePrb': 1.0,
            'Splurge': eco_ref.agents[0].Splurge,
            'EconomyMrkv_init': EconomyMrkv_init,
        }
        _ = eco_ref.run_experiment(**rec_dict, Full_Output=True)

    init_panels = []
    for ag in eco_ref.agents:
        J = ag.num_base_MrkvStates
        a0 = np.asarray(ag.history['aNrm'][0], dtype=np.float32)
        p0 = np.asarray(ag.history['pLvl'][0], dtype=np.float32)
        m0 = (np.asarray(ag.shock_history['Mrkv'][0]) % J).astype(np.int32)
        init_panels.append((a0, p0, m0))

    # Side benefit: transfer the eco_ref converged recession-state-space
    # solution back to the source `eco` so JAX-AD iter 1's `eco.solve()`
    # warm-starts from a close belief instead of cold-starting (which
    # would re-do ~3-5 min of work that auto-init's eco_ref.solve()
    # already did). The two ecos' state spaces match (both at the
    # recession shock_type), so the solution shape is compatible.
    for src_ag, dst_ag in zip(eco_ref.agents, eco.agents):
        if hasattr(src_ag, 'solution') and len(src_ag.solution) > 0:
            dst_ag.solution = src_ag.solution

    if verbose:
        Urate_t0 = [(p[2] != 0).mean() for p in init_panels]
        tag = "fast (T_sim=1)" if fast else "full sim"
        print(f"  [jax-ad-mc] auto-init: HARK ref done in {time.time()-t0:.1f}s "
              f"[{tag}]; per-cohort Urate(t=0)={['%.3f'%u for u in Urate_t0]}",
              flush=True)
    return init_panels


def _build_policy_paths(eco, agent, shock_type, EconomyMrkv_path, init_pLvl, J):
    """Build (extra_dollars_path, tax_cut_factor_path) per HARK's policy semantics.

    extra_dollars_path: (T, N) — Check stimulus added at t=0 for employed agents
    tax_cut_factor_path: (T,) — TaxCutIncFactor at periods where macro % 2*J in [2, 9*2) (8 active periods)
    """
    act_T = len(EconomyMrkv_path)
    N = len(init_pLvl)
    extra_dollars = np.zeros((act_T, N), dtype=np.float32)
    tax_cut = np.ones(act_T, dtype=np.float32)

    if shock_type in ('recessionCheck', 'Check'):
        CheckStimLvl = float(getattr(agent, 'CheckStimLvl', 0.0))
        cs_start = float(getattr(agent, 'CheckStimLvl_PLvl_Cutoff_start', None) or 0)
        cs_end = float(getattr(agent, 'CheckStimLvl_PLvl_Cutoff_end', None) or 0)
        check_per_agent = compute_check_amount_per_agent(
            np.asarray(init_pLvl), CheckStimLvl, cs_start, cs_end)
        extra_dollars[0, :] = check_per_agent
    if shock_type in ('recessionTaxCut', 'TaxCut'):
        TaxCutIncFactor = float(getattr(agent, 'TaxCutIncFactor', 1.0))
        # Per HARK AggFiscalModel:747: tax cut active when Mrkv in [2*J, 9*2*J)
        for t, macro_t in enumerate(EconomyMrkv_path):
            if (2 * J) <= macro_t < (9 * 2 * J):
                tax_cut[t] = TaxCutIncFactor
    return extra_dollars, tax_cut


def _maybe_get_per_agent_weights(agents):
    """Match HARK's edu-share-respecting AggCons: per-cohort scalar weight."""
    weights_mode = os.environ.get('HAFISCAL_AGGREGATE_BY_EDU_SHARE', 'auto').lower()
    has_co = any(os.environ.get(v, '').strip() != ''
                 for v in ('HAFISCAL_AGENTCOUNT_D', 'HAFISCAL_AGENTCOUNT_H',
                           'HAFISCAL_AGENTCOUNT_C'))
    if weights_mode in ('on', '1', 'true') or (weights_mode == 'auto' and has_co):
        return [float(getattr(a, 'pop_rescale_factor', 1.0)) for a in agents]
    return [1.0] * len(agents)


def _run_vmap_all_cohorts_inline(
        eco, shock_type, n_combined, J,
        EconomyMrkv_path, ADF_path, Cratio_obs,
        init_panels, seeds, cohort_T_age,
        act_T, num_max_iterations, it, iter_history,
        convergence_cutoff,
        AggCons_total, cohort_weights,
        per_cohort_cLvl, per_cohort_AggInc, cohort_times,
        lazy_panel=False, verbose=True):
    """Speedup 2A driver: build per-cohort stacks and run ONE vmap'd JAX
    call across all (cohort, seed) pairs. Mutates AggCons_total,
    per_cohort_cLvl, per_cohort_AggInc, cohort_times in place. Returns
    True on success, False if a precondition isn't met."""
    n_cohorts = len(eco.agents)
    n_seeds = len(seeds)

    # Per-cohort prepass: extract kernel inputs + cfunc tables
    t_pre = time.time()
    per_cohort_inp = []
    per_cohort_tables = []
    cohort_Ns = []
    C_grid_shared = None
    for c_idx, agent in enumerate(eco.agents):
        inp = extract_recession_kernel_inputs(agent, scenario=shock_type)
        per_cohort_inp.append(inp)
        m_grid = np.asarray(inp['m_grid'])
        tbl, Cg = extract_cfunc_2d_table(
            agent, m_grid, n_combined=n_combined)
        per_cohort_tables.append(tbl)
        C_grid_shared = Cg
        cohort_Ns.append(init_panels[c_idx][0].shape[0])
    max_N = max(cohort_Ns)
    m_grid_shared = np.asarray(per_cohort_inp[0]['m_grid'])

    # Per-cohort stacks (cfunc table, macro params, scalars, newborn pools)
    cfunc_stk = np.stack(per_cohort_tables, axis=0)  # (n_cohorts, n_combined, M, C_grid)
    Rfree_stk = np.stack([np.asarray(p['Rfree_macro']) for p in per_cohort_inp], axis=0)
    PGF_stk = np.stack([np.asarray(p['PermGroFac_macro']) for p in per_cohort_inp], axis=0)
    Mrkv_stk = np.stack([np.asarray(p['MrkvArray_macro']) for p in per_cohort_inp], axis=0)

    # Per-cohort IncShk arrays may have different max_atoms; pad to common max.
    max_atoms = max(
        np.asarray(p['IncShk_pmv_macro']).shape[-1] for p in per_cohort_inp)
    Psi_stk = np.zeros((n_cohorts, n_combined, max_atoms), dtype=np.float32)
    Xi_stk = np.zeros_like(Psi_stk)
    Pmv_stk = np.zeros_like(Psi_stk)
    for c, p in enumerate(per_cohort_inp):
        pmv = np.asarray(p['IncShk_pmv_macro'])
        psi = np.asarray(p['IncShk_psi_macro'])
        xi = np.asarray(p['IncShk_xi_macro'])
        n_a = pmv.shape[-1]
        Pmv_stk[c, :, :n_a] = pmv
        Psi_stk[c, :, :n_a] = psi
        Xi_stk[c, :, :n_a] = xi
        # Pad remaining psi atoms to 1.0 so they're valid if pmv=0 indexes them
        Psi_stk[c, :, n_a:] = 1.0
    Splurge_stk = np.array(
        [float(p['Splurge']) for p in per_cohort_inp], dtype=np.float32)
    LivPrb_stk = np.array(
        [float(p['LivPrb']) for p in per_cohort_inp], dtype=np.float32)

    # Newborn pools — same pool_N=10000 per cohort
    pool_N = 10000
    nbA_stk = np.zeros((n_cohorts, pool_N), dtype=np.float32)
    nbP_stk = np.zeros_like(nbA_stk)
    for c, agent in enumerate(eco.agents):
        nbA, nbP, _ = draw_newborn_pool_from_agent(agent, pool_N=pool_N, seed=99 + c)
        nbA_stk[c] = nbA
        nbP_stk[c] = nbP

    # Init panels: pad each to max_N, build active_mask
    aNrm0_stk = np.zeros((n_cohorts, max_N), dtype=np.float32)
    pLvl0_stk = np.zeros((n_cohorts, max_N), dtype=np.float32)
    mrkv0_stk = np.zeros((n_cohorts, max_N), dtype=np.int32)
    active_mask_stk = np.zeros((n_cohorts, max_N), dtype=bool)
    for c, (a0, p0, m0) in enumerate(init_panels):
        N_c = a0.shape[0]
        aNrm0_stk[c, :N_c] = a0
        pLvl0_stk[c, :N_c] = p0
        mrkv0_stk[c, :N_c] = m0
        # Pad agents get something valid so they don't NaN; pLvl0=1.0 avoids div0
        aNrm0_stk[c, N_c:] = 0.0
        pLvl0_stk[c, N_c:] = 1.0
        mrkv0_stk[c, N_c:] = 0
        active_mask_stk[c, :N_c] = True

    # Per-cohort policy paths (no policy in this 2A path → all defaults)
    tax_cut_stk = np.ones((n_cohorts, act_T), dtype=np.float32)
    check_dollars_stk = np.zeros((n_cohorts, act_T, max_N), dtype=np.float32)

    # Per-cohort skip_transition path (same for all cohorts)
    skip_transition = np.zeros(act_T, dtype=np.int32)
    skip_transition[0] = 1

    # Per-cohort seed_bases: shape (n_cohorts, n_seeds)
    seed_bases_stk = np.array(
        [[s * 31 + c for s in seeds] for c in range(n_cohorts)], dtype=np.int64)

    # T_age_max: use max across cohorts (alive_mask handles per-cohort cutoff)
    T_age_max_global = int(max(cohort_T_age))

    # Materialize panel decision
    is_final_iter = (it == num_max_iterations - 1)
    will_converge_now = (
        len(iter_history) > 0
        and iter_history[-1]['Total_Diff'] < convergence_cutoff
    )
    materialize = (not lazy_panel) or is_final_iter or will_converge_now

    if verbose:
        print(f"    [2A prep] n_cohorts={n_cohorts}, max_N={max_N}, "
              f"materialize={materialize}, prep_wall={time.time()-t_pre:.2f}s",
              flush=True)

    # Single vmap'd call across cohorts and seeds
    AggInc, AggCons, cLvl_panel = simulate_jax_ad_2d_vmap_cohorts_seeds(
        aNrm0_stk, pLvl0_stk, mrkv0_stk, active_mask_stk,
        seed_bases_stk,
        EconomyMrkv_path, ADF_path, Cratio_obs,
        skip_transition,
        tax_cut_stk, check_dollars_stk,
        cfunc_stk, m_grid_shared, C_grid_shared,
        Rfree_stk, PGF_stk, Mrkv_stk,
        Psi_stk, Xi_stk, Pmv_stk,
        Splurge_stk, LivPrb_stk,
        nbA_stk, nbP_stk,
        act_T, T_age_max=T_age_max_global,
        materialize_panel=materialize,
    )
    AggInc_np = np.asarray(AggInc)
    AggCons_np = np.asarray(AggCons)
    cLvl_np = np.asarray(cLvl_panel) if cLvl_panel is not None else None

    # Per-cohort aggregation
    for c in range(n_cohorts):
        AggCons_cohort = AggCons_np[c].mean(axis=0)  # mean over seeds
        AggCons_total += AggCons_cohort * cohort_weights[c]
        per_cohort_AggInc[c] = AggInc_np[c].mean(axis=0)
        if materialize and cLvl_np is not None:
            N_c = cohort_Ns[c]
            per_cohort_cLvl[c] = cLvl_np[c, :, :, :N_c].mean(axis=0)
        cohort_times.append(0.0)  # not separable in vmap'd call

    return True


def solve_ad_recession_jax_multicohort(eco, base_AggCons,
                                        num_max_iterations, convergence_cutoff,
                                        shock_type='recession',
                                        use_shuffle=False,  # use stratified-shuffle Mrkv transitions
                                        init_panels=None,   # list[(aNrm, pLvl, micro)] per cohort
                                        seeds=(0, 1, 2, 3),
                                        verbose=True):
    """Multi-cohort JAX AD outer loop.

    init_panels: optional list of (aNrm0, pLvl0, micro0) arrays per cohort.
      If None, draws from each cohort's newborn distribution.

    Returns: dict with iter_history, final Cratio_hist, wall_time.
    """
    from AggFiscalModel import CRule

    eco.switch_shock_type(shock_type)
    n_combined = len(eco.CFunc)
    J = eco.num_base_MrkvStates
    n_macro = n_combined // J
    num_exp = eco.num_experiment_periods
    ADelasticity = eco.demand_ADelasticity
    eco.ADelasticity = ADelasticity

    # Reset CFunc to identity
    eco.CFunc = [[CRule(1.0, 0.0) for _ in range(n_combined)] for _ in range(n_combined)]
    for agent in eco.agents:
        agent.CFunc = eco.CFunc

    act_T = eco.agents[0].T_sim
    EconomyMrkv_init = list(np.arange(1, num_exp + 1) * 2 + 1) + [1] * 12 + [0] * 20
    EconomyMrkv_path = (EconomyMrkv_init + [0] * act_T)[:act_T]
    macros = np.array([m for m in EconomyMrkv_path], dtype=int)

    MacroCFunc = [[CRule(1.0, 0.0) for _ in range(n_macro)] for _ in range(n_macro)]

    cohort_weights = _maybe_get_per_agent_weights(eco.agents)
    base_AggCons = np.asarray(base_AggCons)
    iter_history = []
    wall_start = time.time()
    converged = False

    # Per-cohort T_age (200 at Baseline, 100 at HS_Only/RR). My JAX kernel
    # default of 100 was killing agents 100 periods early at Baseline → fewer
    # mature agents, more newborns, lower per-agent consumption, biased Cratio LOW.
    cohort_T_age = [int(getattr(a, 'T_age', 100) or 100) for a in eco.agents]
    if verbose:
        print(f"  [jax-ad-mc] per-cohort T_age: {set(cohort_T_age)}", flush=True)

    # Build init_panels from a one-time HARK no-AD ref sim if caller didn't supply them.
    # Closes the recession Cratio gap from ~1.3% to ~0.18% at HS_Only (was previously
    # ~20% bias with the newborn-pool fallback init). ~3 min overhead at Baseline
    # (one HARK eco.solve + run_experiment, no AD iteration).
    #
    # NOTE: this does NOT close the welfare-cell gap (~6% on check_rec_AD at HS_Only) —
    # that's a separate kernel-level RNG/FP/newborn-timing bias documented in
    # project_jax_mc_ad_baseline_residual_bias.md and confirmed by replay-v2.
    if init_panels is None:
        init_panels = _build_init_panels_via_hark_quick_sim(eco, shock_type, verbose=verbose)

    for it in range(num_max_iterations):
        iter_start = time.time()
        if verbose:
            print(f"  [jax-ad-mc iter {it+1}/{num_max_iterations}] solving agents...",
                  flush=True)
        eco.solve()

        # Build Cratio_obs path from current MacroCFunc beliefs (shared across cohorts)
        Cratio_obs = np.zeros(act_T)
        Cratio_obs[0] = MacroCFunc[0][macros[0]].intercept
        for t in range(1, act_T):
            i, j = macros[t - 1], macros[t]
            rule = MacroCFunc[i][j]
            Cratio_obs[t] = rule.intercept + rule.slope * (Cratio_obs[t - 1] - 1.0)
        ADF_path = compute_AggDemandFac_path(Cratio_obs, EconomyMrkv_path, 1, ADelasticity)

        # Per-cohort JAX MC: each cohort uses its own cfunc table + init + IncShk
        AggCons_total = np.zeros(act_T)
        cohort_times = []
        # Per-cohort panels (overwritten each iter; final iter values are kept).
        # cLvl_panel shape (T, N_c) — full splurge-adjusted consumption per agent per period.
        per_cohort_cLvl = [None] * len(eco.agents)
        per_cohort_AggInc = [None] * len(eco.agents)

        # Speedup 2A: vmap across cohorts — process ALL cohorts in one
        # JAX call. When this runs, the entire per-cohort loop below is
        # skipped (ran_vmap_cohorts becomes True).
        ran_vmap_cohorts = False
        if (_USE_2D_LIFT and _VMAP_COHORTS and _VMAP_SEEDS
                and not use_shuffle and shock_type not in _POLICY_SCENARIOS):
            t_2a_start = time.time()
            ran_vmap_cohorts = _run_vmap_all_cohorts_inline(
                eco, shock_type, n_combined, J,
                EconomyMrkv_path, ADF_path, Cratio_obs,
                init_panels, seeds, cohort_T_age,
                act_T, num_max_iterations, it, iter_history,
                convergence_cutoff,
                AggCons_total, cohort_weights,
                per_cohort_cLvl, per_cohort_AggInc, cohort_times,
                lazy_panel=_LAZY_PANEL,
                verbose=verbose,
            )
            if ran_vmap_cohorts and verbose:
                print(f"    [2A vmap-cohorts] all {len(eco.agents)} cohorts "
                      f"in {time.time()-t_2a_start:.2f}s", flush=True)

        # Speedup 1C: pre-build ALL cohorts' cfunc tables in a single batch and
        # do ONE host->device transfer instead of one per cohort. Only matters
        # when 1A (2D lift) is on. Skipped under 2A (vmap-cohorts handles its own).
        batched_cfunc_jax = None
        if not ran_vmap_cohorts and _USE_2D_LIFT and _BATCH_TABLES:
            t_batch = time.time()
            per_cohort_inp = []
            per_cohort_tables = []
            C_grid_shared = None
            for agent in eco.agents:
                inp_b = extract_recession_kernel_inputs(agent, scenario=shock_type)
                m_grid_b = np.asarray(inp_b['m_grid'])
                tbl, Cg = extract_cfunc_2d_table(
                    agent, m_grid_b, n_combined=n_combined)
                per_cohort_inp.append(inp_b)
                per_cohort_tables.append(tbl)
                C_grid_shared = Cg
            cfunc_stack = np.stack(per_cohort_tables, axis=0)  # (n_cohorts, n_combined, M, C_grid)
            batched_cfunc_jax = jnp.asarray(cfunc_stack)
            if verbose:
                print(f"    [1C batch tables] built+transferred {cfunc_stack.shape} "
                      f"in {time.time()-t_batch:.2f}s", flush=True)

        for c_idx, agent in enumerate(eco.agents) if not ran_vmap_cohorts else []:
            c_start = time.time()
            if _USE_2D_LIFT and _BATCH_TABLES and batched_cfunc_jax is not None:
                # 1C: reuse pre-built batched table; just slice on GPU.
                inp = per_cohort_inp[c_idx]
                m_grid = np.asarray(inp['m_grid'])
                cfunc_2d_table = batched_cfunc_jax[c_idx]
                C_grid = C_grid_shared
            elif _USE_2D_LIFT:
                inp = extract_recession_kernel_inputs(agent, scenario=shock_type)
                m_grid = np.asarray(inp['m_grid'])
                # Speedup 1A: lift cFunc ONCE on uniform (m, C) grid; kernel
                # does bilinear lookup at per-period Cratio_obs[t].
                cfunc_2d_table, C_grid = extract_cfunc_2d_table(
                    agent, m_grid, n_combined=n_combined)
            else:
                inp = extract_recession_kernel_inputs(agent, scenario=shock_type)
                m_grid = np.asarray(inp['m_grid'])
                cfunc_table = extract_cfunc_table_per_period(
                    agent, Cratio_obs, m_grid, n_combined=n_combined)
            nbA, nbP, _ = draw_newborn_pool_from_agent(agent, pool_N=10000, seed=99 + c_idx)
            aNrm0, pLvl0, micro0 = init_panels[c_idx]

            common = dict(
                Rfree_macro=jnp.asarray(inp['Rfree_macro']),
                PermGroFac_macro=jnp.asarray(inp['PermGroFac_macro']),
                MrkvArray_macro=jnp.asarray(inp['MrkvArray_macro']),
                IncShk_psi_macro=jnp.asarray(inp['IncShk_psi_macro']),
                IncShk_xi_macro=jnp.asarray(inp['IncShk_xi_macro']),
                IncShk_pmv_macro=jnp.asarray(inp['IncShk_pmv_macro']),
                Splurge=inp['Splurge'], LivPrb=inp['LivPrb'],
                newborn_aNrm=jnp.asarray(nbA), newborn_pLvl=jnp.asarray(nbP),
                act_T=act_T, T_age_max=cohort_T_age[c_idx],
            )

            cons_per_seed = []
            cLvl_panels_per_seed = []
            AggInc_per_seed = []
            is_policy = shock_type in _POLICY_SCENARIOS
            if is_policy:
                extra_dollars_path, tax_cut_factor_path = _build_policy_paths(
                    eco, agent, shock_type, EconomyMrkv_path, pLvl0, J)
            else:
                extra_dollars_path, tax_cut_factor_path = None, None
            if _USE_2D_LIFT and _VMAP_SEEDS and not use_shuffle:
                # 1A + 1B: single vmap'd JIT call across all seeds
                seed_bases = [s * 31 + c_idx for s in seeds]
                # 1D: only materialize the (S, T, N) panel on the final iter.
                # Convergence flag isn't yet known here, so use "last iteration
                # of num_max_iterations OR Total_Diff already below cutoff on
                # previous iter." Since we don't know the future, materialize
                # ALWAYS on the last iter; otherwise skip if 1D is on.
                is_final_iter = (it == num_max_iterations - 1)
                will_converge_now = (
                    len(iter_history) > 0
                    and iter_history[-1]['Total_Diff'] < convergence_cutoff
                )
                materialize = (not _LAZY_PANEL) or is_final_iter or will_converge_now
                AggInc_stk, AggCons_stk, cLvl_stk = simulate_jax_ad_2d_vmap_seeds(
                    seed_bases,
                    aNrm0, pLvl0, micro0,
                    EconomyMrkv_path, ADF_path, Cratio_obs,
                    cfunc_2d_table, jnp.asarray(m_grid), C_grid,
                    **common,
                    tax_cut_path=tax_cut_factor_path,
                    check_dollars_path=extra_dollars_path,
                    materialize_panel=materialize)
                # Unstack into per-seed lists for downstream aggregation
                for s_idx in range(len(seeds)):
                    cons_per_seed.append(np.asarray(AggCons_stk[s_idx]))
                    if materialize and cLvl_stk is not None:
                        cLvl_panels_per_seed.append(np.asarray(cLvl_stk[s_idx]))
                    AggInc_per_seed.append(np.asarray(AggInc_stk[s_idx]))
            else:
                for s in seeds:
                    if use_shuffle:
                        if not _HAS_SHUFFLE:
                            raise RuntimeError("use_shuffle=True requires jax_mc_ad_shuffle")
                        inc, cons, cLvl_panel = simulate_jax_ad_shuffle(
                            aNrm0, pLvl0, micro0,
                            EconomyMrkv_path, ADF_path, cfunc_table,
                            jnp.asarray(m_grid), **common,
                            seed_base=s * 31 + c_idx,
                            tax_cut_path=tax_cut_factor_path,
                            check_dollars_path=extra_dollars_path, J=J)
                    elif _USE_2D_LIFT:
                        inc, cons, cLvl_panel = simulate_jax_ad_2d(
                            aNrm0, pLvl0, micro0,
                            EconomyMrkv_path, ADF_path, Cratio_obs,
                            cfunc_2d_table, jnp.asarray(m_grid), C_grid,
                            **common,
                            seed_base=s * 31 + c_idx,
                            tax_cut_path=tax_cut_factor_path,
                            check_dollars_path=extra_dollars_path)
                    else:
                        inc, cons, cLvl_panel = simulate_jax_ad(
                            aNrm0, pLvl0, micro0,
                            EconomyMrkv_path, ADF_path, cfunc_table,
                            jnp.asarray(m_grid), **common,
                            seed_base=s * 31 + c_idx,
                            tax_cut_path=tax_cut_factor_path,
                            check_dollars_path=extra_dollars_path)
                    cons_per_seed.append(np.asarray(cons))
                    cLvl_panels_per_seed.append(np.asarray(cLvl_panel))
                    AggInc_per_seed.append(np.asarray(inc))
            AggCons_cohort = np.mean(cons_per_seed, axis=0)
            AggCons_total += AggCons_cohort * cohort_weights[c_idx]
            # Save per-cohort artifacts from the LAST iter (for welfare cell aggregation).
            # Under 1D lazy-panel, cLvl is only materialized on the final iter (or
            # whenever materialize=True). Skip the update when empty.
            if cLvl_panels_per_seed:
                per_cohort_cLvl[c_idx] = np.mean(cLvl_panels_per_seed, axis=0)
            per_cohort_AggInc[c_idx] = np.mean(AggInc_per_seed, axis=0)
            cohort_times.append(time.time() - c_start)

        Cratio_hist = AggCons_total / base_AggCons

        # Build new MacroCFunc (HARK lines 2343-2347)
        new_MacroCFunc = [[CRule(1.0, 0.0) for _ in range(n_macro)] for _ in range(n_macro)]
        new_MacroCFunc[0][3] = CRule(float(Cratio_hist[0]), 0.0)
        for j in range(num_exp - 1):
            new_MacroCFunc[2 * j + 3][2 * j + 5] = CRule(float(Cratio_hist[j + 1]), 0.0)
        new_MacroCFunc[2 * num_exp + 1][1] = CRule(float(Cratio_hist[num_exp]), 0.0)
        recovery_window = Cratio_hist[num_exp + 1:num_exp + 10]
        new_MacroCFunc[1][1] = CRule(float(np.mean(recovery_window)), 0.0)

        # Step CFunc
        Old_CFunc = eco.CFunc
        New_CFunc = eco.Macro_2_Micro_CFunc(new_MacroCFunc)
        step = eco.Cfunc_iter_stepsize
        Step_CFunc = [[CRule(1.0, 0.0) for _ in range(n_combined)] for _ in range(n_combined)]
        for ii in range(n_combined):
            for jj in range(n_combined):
                Step_CFunc[ii][jj].slope = (
                    Old_CFunc[ii][jj].slope
                    + step * (New_CFunc[ii][jj].slope - Old_CFunc[ii][jj].slope))
                Step_CFunc[ii][jj].intercept = (
                    Old_CFunc[ii][jj].intercept
                    + step * (New_CFunc[ii][jj].intercept - Old_CFunc[ii][jj].intercept))
        eco.CFunc = Step_CFunc
        for agent in eco.agents:
            agent.CFunc = eco.CFunc
        MacroCFunc = new_MacroCFunc

        Total_Diff = eco.Compare_CFunc_Convergence(Old_CFunc, eco.CFunc)
        wall_iter = time.time() - iter_start
        iter_history.append({
            'iter': it + 1,
            'Cratio_hist': Cratio_hist.copy(),
            'Total_Diff': Total_Diff,
            'wall': wall_iter,
            'cohort_times': cohort_times,
        })
        if verbose:
            print(f"  [jax-ad-mc iter {it+1}] Total_Diff={Total_Diff:.4g}, "
                  f"Cratio[0]={Cratio_hist[0]:.4f}, wall={wall_iter:.1f}s "
                  f"(cohorts: {[f'{t:.1f}' for t in cohort_times]})",
                  flush=True)
        if Total_Diff < convergence_cutoff:
            converged = True
            break

    wall = time.time() - wall_start
    if verbose:
        print(f"[jax-ad-mc] {len(iter_history)} iters, "
              f"converged={converged}, wall={wall:.1f}s")

    # Build final per-agent panel by concatenating per-cohort panels along agent axis
    # Apply cohort_weights as PER-AGENT weights so welfare-6 post-processor can sum directly.
    cLvl_full = None
    AggIncome_full = None
    if all(p is not None for p in per_cohort_cLvl):
        # Each cohort contributes weight * cLvl_panel. Concat along agent axis.
        weighted_panels = []
        for i, p in enumerate(per_cohort_cLvl):
            w = cohort_weights[i]
            # Scale each agent's consumption by sqrt(w) so sum-of-squares-like
            # aggregations work; for welfare-6 sum-of-felicity, just scale by w
            # in the post-processor. We pass unscaled panel + weights separately.
            weighted_panels.append(p)
        cLvl_full = np.concatenate(weighted_panels, axis=1)
        AggIncome_full = np.zeros_like(iter_history[-1]['Cratio_hist'])
        for i, ai in enumerate(per_cohort_AggInc):
            AggIncome_full += ai * cohort_weights[i]

    return {
        'iter_history': iter_history,
        'final_Cratio_hist': iter_history[-1]['Cratio_hist'],
        'final_AggCons': iter_history[-1]['Cratio_hist'] * base_AggCons,  # absolute AggCons
        'final_AggIncome': AggIncome_full,
        'final_cLvl_all_splurge': cLvl_full,  # (T, total_N) panel for welfare cells
        'per_cohort_cLvl': per_cohort_cLvl,
        'per_cohort_AggInc': per_cohort_AggInc,
        'cohort_weights': cohort_weights,
        'converged': converged,
        'wall_time': wall,
    }
