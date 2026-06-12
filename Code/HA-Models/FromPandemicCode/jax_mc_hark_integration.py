"""
jax_mc_hark_integration.py — connect minimal JAX MC to HARK's solved model.

Validates the JAX MC kernel against HARK CPU MC output for HS_Only base scenario.
"""
from __future__ import annotations
import os, sys, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint5d_jax_kernel import (
    tabulate_cfunc_list, extract_incshk_arrays, _resolve_scenario_IncShkDstn,
)


def _broadcast_employed_psi_to_all_states(IncShk_psi, IncShk_xi, IncShk_pmv, IncShk_natoms, employed_state=0):
    """Under HAFiscal's perm_shocks_during_unemployment=True mode, all Mrkv
    states get the EMPLOYED state's psi distribution (instead of psi=1.0).
    Per-state xi (income value) stays — we just broadcast it across all
    n_emp psi atoms to keep them paired correctly in categorical sampling.

    Returns modified (psi, xi, pmv, natoms) copies.
    """
    n_emp = int(IncShk_natoms[employed_state])
    new_psi = IncShk_psi.copy()
    new_xi = IncShk_xi.copy()
    new_pmv = IncShk_pmv.copy()
    new_natoms = IncShk_natoms.copy()
    n_states = IncShk_psi.shape[0]
    for j in range(n_states):
        if j == employed_state:
            continue
        n_xi_this = int(IncShk_natoms[j])
        if n_xi_this != 1:
            continue   # multi-atom xi: outer product needed, not implemented
        xi_value = IncShk_xi[j, 0]   # the single unemp xi for this state
        # Broadcast: n_emp atoms, each with (psi_k_emp, xi=constant)
        new_psi[j, :n_emp] = IncShk_psi[employed_state, :n_emp]
        new_xi[j, :n_emp]  = xi_value   # same xi for all atoms
        new_pmv[j, :n_emp] = IncShk_pmv[employed_state, :n_emp]
        new_natoms[j] = n_emp
    return new_psi, new_xi, new_pmv, new_natoms


def extract_recession_kernel_inputs(agent, scenario='recession', M_grid=500):
    """Extract per-macro arrays for recession-aware JAX kernel.

    For HAFiscal recession scenarios:
      - J = num_base_MrkvStates (6 under bug_fix)
      - n_macro = 2 * (num_experiment_periods + 1) = 22 typical
      - Combined state = macro * J + micro, total 132 entries
      - cFunc, IncShkDstn, Rfree, PermGroFac all indexed by combined state
      - CondMrkvArrays: (n_macro,) of (J, J) micro-transition matrices per macro

    Returns dict with arrays sized for the recession JAX kernel.
    """
    J = int(agent.num_base_MrkvStates)
    n_macro = len(agent.CondMrkvArrays)
    n_combined = n_macro * J
    print(f"  Recession setup: J={J}, n_macro={n_macro}, n_combined={n_combined}")

    # cFunc table for all 132 combined states
    cFuncs_full = agent.solution[0].cFunc
    assert len(cFuncs_full) == n_combined, f"cFunc len {len(cFuncs_full)} != {n_combined}"

    from welfare6_tm_joint5d_jax_kernel import build_m_grid
    m_grid_np = build_m_grid(M_grid)
    cfunc_table_macro = tabulate_cfunc_list(cFuncs_full, m_grid_np).astype(np.float32)
    # shape: (n_combined, M_grid)

    # MrkvArray per macro: shape (n_macro, J, J)
    MrkvArray_macro = np.zeros((n_macro, J, J), dtype=np.float32)
    for m in range(n_macro):
        MrkvArray_macro[m] = np.asarray(agent.CondMrkvArrays[m], dtype=np.float32)

    # IncShkDstn for the scenario
    IncShk_full = _resolve_scenario_IncShkDstn(agent, scenario)
    assert len(IncShk_full) == n_combined, f"IncShk len {len(IncShk_full)} != {n_combined}"

    all_atoms = max(len(np.asarray(d.pmv)) for d in IncShk_full)
    arrs = extract_incshk_arrays(IncShk_full, max_atoms=all_atoms)
    IncShk_psi_macro = arrs['psi'].astype(np.float32)
    IncShk_xi_macro = arrs['xi'].astype(np.float32)
    IncShk_pmv_macro = arrs['pmv'].astype(np.float32)
    IncShk_natoms_macro = arrs['n_atoms'].astype(np.int32)
    # Normalize pmv
    pmv_sum = IncShk_pmv_macro.sum(axis=-1, keepdims=True)
    IncShk_pmv_macro = IncShk_pmv_macro / np.maximum(pmv_sum, 1e-12)

    Rfree_macro = np.asarray(agent.Rfree[:n_combined], dtype=np.float32)
    PermGroFac_macro = np.asarray(agent.PermGroFac[0][:n_combined], dtype=np.float32)
    Splurge = float(agent.Splurge)
    LivPrb_arr = np.asarray(agent.LivPrb[0][:n_combined], dtype=np.float32)
    LivPrb_avg = float(np.mean(LivPrb_arr))

    # Note: BUG-043 u3Q/u4Q state-conditional TranShk overrides are already
    # baked into `agent.IncShkDstn_recessionUI` per welfare6_scenario.py:328-349.
    # IncShkDstn_recession has TranShk=IncUnempNoBenefits for u3Q/u4Q at all macros.
    # IncShkDstn_recessionUI has TranShk=IncUnemp at recession macros, IncUnempNoBenefits
    # at normal macros (matching HARK's runtime override semantics).
    # So no extra override needed here — _resolve_scenario_IncShkDstn returns the
    # correct per-scenario IncShkDstn.

    return dict(
        cfunc_table_macro=cfunc_table_macro,
        m_grid=m_grid_np.astype(np.float32),
        Rfree_macro=Rfree_macro, PermGroFac_macro=PermGroFac_macro,
        MrkvArray_macro=MrkvArray_macro,
        IncShk_psi_macro=IncShk_psi_macro, IncShk_xi_macro=IncShk_xi_macro,
        IncShk_pmv_macro=IncShk_pmv_macro, IncShk_natoms_macro=IncShk_natoms_macro,
        Splurge=Splurge, LivPrb=LivPrb_avg,
        J=J, n_macro=n_macro, n_combined=n_combined,
    )


def extract_hark_kernel_inputs(agent, scenario='base'):
    """Pull cFunc table, MrkvArray, IncShkDstn arrays from a solved HARK agent.

    Returns dict ready to feed jax_mc_minimal.simulate_jax / simulate_np.
    """
    J = int(agent.num_base_MrkvStates)   # micro states only (6 under bug_fix)
    # For non-recession (base, Check, TaxCut, UI), only macro=0 is relevant
    # — the recession ones span multiple macro states.
    macro = 0

    # cFunc table for macro=0 only (base scenario)
    base_idx = macro * J
    cFuncs = [agent.solution[0].cFunc[base_idx + j] for j in range(J)]

    M_grid = 500
    from welfare6_tm_joint5d_jax_kernel import build_m_grid
    m_grid_np = build_m_grid(M_grid)
    cfunc_table = tabulate_cfunc_list(cFuncs, m_grid_np).astype(np.float32)
    # cfunc_table shape: (J, M_grid)

    # MrkvArray for macro=0
    MrkvArray = np.asarray(agent.CondMrkvArrays[macro], dtype=np.float32)
    # shape: (J, J)

    # IncShkDstn for scenario
    IncShk_full = _resolve_scenario_IncShkDstn(agent, scenario)
    # Take macro=0's J states
    IncShk_list = list(IncShk_full[base_idx:base_idx + J])

    all_atoms = max(len(np.asarray(d.pmv)) for d in IncShk_list)
    arrs = extract_incshk_arrays(IncShk_list, max_atoms=all_atoms)
    # arrs has 'psi', 'xi', 'pmv' as (J, max_atoms) and 'n_atoms' as (J,)
    IncShk_psi = arrs['psi'].astype(np.float32)
    IncShk_xi  = arrs['xi'].astype(np.float32)
    IncShk_pmv = arrs['pmv'].astype(np.float32)
    IncShk_natoms = arrs['n_atoms'].astype(np.int32)

    # Renormalize pmv to sum to exactly 1 per row (avoid floating-point drift)
    pmv_sum = IncShk_pmv.sum(axis=-1, keepdims=True)
    IncShk_pmv = IncShk_pmv / np.maximum(pmv_sum, 1e-12)

    Rfree = np.asarray(agent.Rfree[base_idx:base_idx + J], dtype=np.float32)
    PermGroFac = np.asarray(agent.PermGroFac[0][base_idx:base_idx + J], dtype=np.float32)
    Splurge = float(agent.Splurge)
    rho = float(agent.CRRA)
    LivPrb_arr = np.asarray(agent.LivPrb[0][base_idx:base_idx + J], dtype=np.float32)
    LivPrb_avg = float(np.mean(LivPrb_arr))

    return dict(
        cfunc_table=cfunc_table, m_grid=m_grid_np.astype(np.float32),
        Rfree=Rfree, PermGroFac=PermGroFac, MrkvArray=MrkvArray,
        IncShk_psi=IncShk_psi, IncShk_xi=IncShk_xi,
        IncShk_pmv=IncShk_pmv, IncShk_natoms=IncShk_natoms,
        Splurge=Splurge, CRRA=rho, LivPrb=LivPrb_avg,
        J=J, M_grid=M_grid,
    )


def draw_newborn_pool_from_agent(agent, pool_N=10000, seed=42):
    """Sample newborn (aNrm, pLvl, mrkv) pool from HARK's own newborn distributions.

    HARK's sim_birth uses kNrmInitDstn (single atom ~0 for HAFiscal) and
    pLvlInitDstn (discrete lognormal-like). My JAX newborn pool must match
    these to avoid systematic bias from wrong replacement distribution.
    """
    rs = np.random.RandomState(seed)
    if hasattr(agent, 'kNrmInitDstn'):
        # Re-seed the HARK distribution for reproducibility
        agent.kNrmInitDstn.seed = seed
        newborn_aNrm = np.asarray(agent.kNrmInitDstn.draw(pool_N), dtype=np.float32)
    else:
        # Fallback: deterministic ~0 (HAFiscal-style)
        newborn_aNrm = np.full(pool_N, 1e-5, dtype=np.float32)
    if hasattr(agent, 'pLvlInitDstn'):
        agent.pLvlInitDstn.seed = seed + 1
        newborn_pLvl = np.asarray(agent.pLvlInitDstn.draw(pool_N), dtype=np.float32)
    else:
        newborn_pLvl = np.ones(pool_N, dtype=np.float32)
    # Newborns enter at Mrkv state 0 (employed) per HAFiscal convention
    newborn_mrkv = np.zeros(pool_N, dtype=np.int32)
    return newborn_aNrm, newborn_pLvl, newborn_mrkv


def initial_states_from_agent(agent, N=None):
    """Pull initial agent state from a solved (but not yet simulated) HARK agent."""
    if N is None:
        N = agent.AgentCount
    # If agent has been initialized, state_now has the lognormal-drawn initial state.
    # Otherwise we need to call initialize_sim first.
    if not hasattr(agent, 'state_now') or agent.state_now.get('aNrm') is None:
        agent.initialize_sim()
    aNrm0 = np.asarray(agent.state_now['aNrm'][:N], dtype=np.float32)
    pLvl0 = np.asarray(agent.state_now['pLvl'][:N], dtype=np.float32)
    if 'Mrkv' in agent.shocks:
        mrkv0 = np.asarray(agent.shocks['Mrkv'][:N], dtype=np.int32)
    elif hasattr(agent, 'MicroMrkvNow'):
        mrkv0 = np.asarray(agent.MicroMrkvNow[:N], dtype=np.int32)
    else:
        # Default to all employed
        mrkv0 = np.zeros(N, dtype=np.int32)
    return aNrm0, pLvl0, mrkv0


def main():
    parametrization = os.environ.get('PARAMETRIZATION', 'HS_Only')
    seed_offset = int(os.environ.get('SEED_OFFSET', '0'))
    print(f"=== JAX MC vs HARK MC validation ({parametrization}, seed={seed_offset}) ===")

    print(f"\n[1/4] build_and_solve...")
    t0 = time.time()
    ctx = build_and_solve(parametrization, seed_offset=seed_offset)
    print(f"  solve wall: {time.time()-t0:.1f}s")
    AggEco = ctx['AggEco']
    if not AggEco.agents:
        print("  ERROR: no agents")
        return
    # HS_Only has 1 agent type
    agent = AggEco.agents[0]
    print(f"  AgentCount per type: {agent.AgentCount}")
    print(f"  num_base_MrkvStates: {agent.num_base_MrkvStates}")

    print(f"\n[2/4] Extract kernel inputs (base scenario, macro=0)...")
    AggEco.switch_shock_type('base')
    AggEco.solve()
    agent = AggEco.agents[0]
    inputs = extract_hark_kernel_inputs(agent, scenario='base')
    print(f"  cfunc_table shape: {inputs['cfunc_table'].shape}")
    print(f"  MrkvArray shape: {inputs['MrkvArray'].shape}")
    print(f"  IncShk_psi shape: {inputs['IncShk_psi'].shape}")
    print(f"  LivPrb_avg: {inputs['LivPrb']:.4f}")

    print(f"\n[3/4] Initialize agent state + run JAX kernel...")
    agent.initialize_sim()
    N = agent.AgentCount
    # Need at least these state arrays. Use the agent's own init.
    aNrm0 = np.asarray(agent.state_now.get('aNrm', np.zeros(N)), dtype=np.float32)
    pLvl0 = np.asarray(agent.state_now.get('pLvl', np.ones(N)), dtype=np.float32)
    # Mrkv0 — for base scenario, start everyone employed (state 0)
    mrkv0 = np.zeros(N, dtype=np.int32)

    # Newborn pool: use a few hundred newborns at (small a, p=1, mrkv=0)
    rs = np.random.RandomState(42)
    nb_N = 200
    newborn_aNrm = rs.uniform(0.0, 0.5, size=nb_N).astype(np.float32)
    newborn_pLvl = np.ones(nb_N, dtype=np.float32)
    newborn_mrkv = np.zeros(nb_N, dtype=np.int32)

    act_T = ctx.get('act_T', 100)
    print(f"  N={N}, act_T={act_T}")

    # Run JAX
    import jax.numpy as jnp
    from jax_mc_minimal import simulate_jax, simulate_np

    print(f"\n[3a] JAX run (warm-up + timed)...")
    jax_args = (
        aNrm0, pLvl0, mrkv0,
        jnp.asarray(inputs['cfunc_table']), jnp.asarray(inputs['m_grid']),
        jnp.asarray(inputs['Rfree']), jnp.asarray(inputs['PermGroFac']),
        jnp.asarray(inputs['MrkvArray']),
        jnp.asarray(inputs['IncShk_psi']), jnp.asarray(inputs['IncShk_xi']),
        jnp.asarray(inputs['IncShk_pmv']),
        1.0,  # AggDemandFac
        1.0,  # Cratio
        inputs['Splurge'],
        inputs['LivPrb'],
        jnp.asarray(newborn_aNrm), jnp.asarray(newborn_pLvl),
        jnp.asarray(newborn_mrkv),
    )
    _ = simulate_jax(*jax_args, act_T, seed_base=seed_offset)
    t0 = time.time()
    jax_inc, jax_cons, jax_cls = simulate_jax(*jax_args, act_T, seed_base=seed_offset)
    wall_jax = time.time() - t0
    print(f"  JAX wall (after warmup): {wall_jax:.3f}s")
    print(f"  AggInc[0..5]: {np.asarray(jax_inc[:5])}")
    print(f"  AggCons[0..5]: {np.asarray(jax_cons[:5])}")
    print(f"  AggInc mean: {float(jax_inc.mean()):.3f}")
    print(f"  AggCons mean: {float(jax_cons.mean()):.3f}")

    print(f"\n[3b] numpy run (for sanity)...")
    t0 = time.time()
    np_inc, np_cons, np_cls = simulate_np(
        aNrm0, pLvl0, mrkv0,
        inputs['cfunc_table'], inputs['m_grid'],
        inputs['Rfree'], inputs['PermGroFac'], inputs['MrkvArray'],
        inputs['IncShk_psi'], inputs['IncShk_xi'],
        inputs['IncShk_pmv'], inputs['IncShk_natoms'],
        1.0, 1.0, inputs['Splurge'], inputs['LivPrb'],
        newborn_aNrm, newborn_pLvl, newborn_mrkv,
        act_T, seed_base=seed_offset)
    wall_np = time.time() - t0
    print(f"  numpy wall: {wall_np:.3f}s")
    print(f"  AggInc mean: {np_inc.mean():.3f}")
    print(f"  AggCons mean: {np_cons.mean():.3f}")
    print(f"  speedup (numpy/JAX): {wall_np/wall_jax:.1f}x")

    print(f"\n[4/4] HARK CPU MC comparison (load existing pickle)...")
    # Try to find HARK MC output for HS_Only at matching seed
    pkl_path = None
    candidates = [
        f'welfare6_stratified_bench_HS_Only/seed{seed_offset}/base.pkl',
        f'welfare6_BUG044_baseline_nshuf_1x/base.pkl',
    ]
    for c in candidates:
        if os.path.exists(c):
            pkl_path = c
            break
    if pkl_path is None:
        print(f"  No HARK pickle found in candidates; skipping comparison")
        print(f"  (To enable: run welfare6_scenario.py base scenario at same seed)")
    else:
        import pickle
        hark_data = pickle.load(open(pkl_path, 'rb'))
        hark_AggInc = np.asarray(hark_data['AggIncome'])
        hark_AggCons = np.asarray(hark_data['AggCons'])
        print(f"  Loaded {pkl_path}")
        print(f"  HARK AggInc mean: {hark_AggInc.mean():.3f}")
        print(f"  HARK AggCons mean: {hark_AggCons.mean():.3f}")
        print(f"  ratio JAX/HARK AggInc: {float(jax_inc.mean())/hark_AggInc.mean():.4f}")
        print(f"  ratio JAX/HARK AggCons: {float(jax_cons.mean())/hark_AggCons.mean():.4f}")
        # Per-period correlation
        if len(hark_AggInc) == act_T:
            jax_inc_np = np.asarray(jax_inc)
            corr = np.corrcoef(jax_inc_np, hark_AggInc)[0, 1]
            print(f"  per-period correlation AggInc: {corr:.4f}")


if __name__ == '__main__':
    main()
