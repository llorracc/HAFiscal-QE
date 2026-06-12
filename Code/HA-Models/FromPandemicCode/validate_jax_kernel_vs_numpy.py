"""
Phase B.2 Step 2b: validate _step_period_5d_jax_loops against the
numpy _step_period_5d for a single period at small A.

This is the critical correctness gate before scaling up.

Expected difference: ~interpolation precision from cFunc tabulation
(M=500 gives ~0.07% rel error). If the kernel logic is correct,
weighting metrics like welfare_num should agree to ~0.1%.
"""
from __future__ import annotations
import os, sys, time
from copy import deepcopy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint5d import (
    _step_period_5d, compute_joint_markov,
    _resolve_scenario_IncShkDstn,
)
from welfare6_tm_joint5d_jax_kernel import (
    tabulate_cfunc_list, extract_incshk_arrays, q_reweight_pmv,
    build_joint_atom_table, _step_period_5d_jax_loops,
    _step_period_5d_jax_v2, _step_period_5d_jax_v3, _USE_FP64,
)
from tm_methods import compute_baseline_tm_data, _solve_markov_ergodic
import jax
import jax.numpy as jnp


def main():
    aCount = int(os.environ.get('JOINT5D_ACOUNT', 10))
    M_grid = int(os.environ.get('M_GRID', 500))
    print(f"{'='*70}")
    print(f"Phase B.2 Step 2b: JAX kernel vs numpy single-period")
    print(f"  A={aCount}, M_grid={M_grid}")
    print(f"  FP mode: {'FP64' if _USE_FP64 else 'FP32'}")
    print(f"  JAX backend: {jax.default_backend()}")
    print(f"{'='*70}")

    print(f"\n[1/5] Build HS_Only context + solve...")
    t0 = time.time()
    ctx = build_and_solve('HS_Only')
    AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
    AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()
    AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()
    for ag in AggEco_pol.agents: ag.tm_a_indexed = True
    for ag in AggEco_none.agents: ag.tm_a_indexed = True
    for ag in AggEco_base.agents: ag.tm_a_indexed = True
    bd_list = compute_baseline_tm_data(AggEco_base, mCount=aCount, neutral_measure=True)
    print(f"  setup wall: {time.time() - t0:.1f}s")

    agent_pol = AggEco_pol.agents[0]
    agent_none = AggEco_none.agents[0]
    agent_base = AggEco_base.agents[0]
    bd = bd_list[0]

    aGrid = bd['dist_aGrid']
    A = len(aGrid)
    J = int(agent_pol.num_base_MrkvStates)
    print(f"  A={A}, J={J}")

    # Pick test period (e.g., t=0 with macro=1 = recession Q1)
    # Use macro_pn=1 (recession Q1) for testing the recession-active path
    macro_pn = 1

    print(f"\n[2/5] Pre-tabulate cFunc on m_grid (M={M_grid})...")
    m_grid = np.linspace(0.01, 50.0, M_grid)
    base_idx_pn = macro_pn * J
    cFuncs_pol_t = [agent_pol.solution[0].cFunc[base_idx_pn + j] for j in range(J)]
    cFuncs_none_t = [agent_none.solution[0].cFunc[base_idx_pn + j] for j in range(J)]
    cFuncs_b_t = [agent_base.solution[0].cFunc[0 + j] for j in range(J)]
    cfunc_pol_table_t = tabulate_cfunc_list(cFuncs_pol_t, m_grid)
    cfunc_none_table_t = tabulate_cfunc_list(cFuncs_none_t, m_grid)
    cfunc_b_table_t = tabulate_cfunc_list(cFuncs_b_t, m_grid)

    print(f"\n[3/5] Extract IncShkDstn arrays...")
    IncShk_pol_full = _resolve_scenario_IncShkDstn(agent_pol, 'recessionUI')
    IncShk_none_full = _resolve_scenario_IncShkDstn(agent_none, 'recession')
    IncShk_base_full = _resolve_scenario_IncShkDstn(agent_base, 'base')
    IncShk_pol_t = list(IncShk_pol_full[base_idx_pn:base_idx_pn + J])
    IncShk_none_t = list(IncShk_none_full[base_idx_pn:base_idx_pn + J])
    IncShk_b_t = list(IncShk_base_full[0:J])

    # max_atoms across all three
    all_atoms = max(
        max(len(np.asarray(d.pmv)) for d in IncShk_pol_t),
        max(len(np.asarray(d.pmv)) for d in IncShk_none_t),
        max(len(np.asarray(d.pmv)) for d in IncShk_b_t),
    )
    pol_arrs = extract_incshk_arrays(IncShk_pol_t, max_atoms=all_atoms)
    none_arrs = extract_incshk_arrays(IncShk_none_t, max_atoms=all_atoms)
    b_arrs = extract_incshk_arrays(IncShk_b_t, max_atoms=all_atoms)
    pmv_pol_q = q_reweight_pmv(pol_arrs['psi'], pol_arrs['pmv'], pol_arrs['n_atoms'])
    pmv_b_q = q_reweight_pmv(b_arrs['psi'], b_arrs['pmv'], b_arrs['n_atoms'])

    print(f"  pol: {pol_arrs['n_atoms']}, base: {b_arrs['n_atoms']}, max_atoms={all_atoms}")

    print(f"\n[4/5] Build joint atom table...")
    atom_p_idx, atom_b_idx, joint_pmv = build_joint_atom_table(
        pmv_pol_q, pmv_b_q, pol_arrs['n_atoms'], b_arrs['n_atoms']
    )

    # Markov arrays for this period
    MA_pn = np.asarray(agent_pol.CondMrkvArrays[macro_pn], dtype=np.float64)
    MA_b = np.asarray(agent_base.CondMrkvArrays[0], dtype=np.float64)
    joint_markov = compute_joint_markov(MA_pn, MA_b)

    # Other params
    Rfree = np.asarray(agent_pol.Rfree[:J], dtype=np.float64)
    PermGroFac = np.asarray(agent_pol.PermGroFac[0][:J], dtype=np.float64)
    Splurge = float(agent_pol.Splurge)
    rho = float(agent_pol.CRRA)
    Cratio_pol = 1.0
    Cratio_none = 1.0
    AggDemandFac_pol = 1.0
    AggDemandFac_none = 1.0
    TranShk_addition_pol = np.zeros(J)
    TranShk_addition_none = np.zeros(J)

    # Build initial dist5d (use a simple synthetic distribution for testing)
    # Same as compute_joint_welfare5d init: diagonal in all three asset axes AND j_p = j_b
    base_ergodic = np.asarray(bd['ergodic'], dtype=np.float64)
    base_dist_aJ = base_ergodic.reshape(J, A)
    dist5d_init = np.zeros((A, A, A, J, J), dtype=np.float64)
    for j in range(J):
        for a_idx in range(A):
            dist5d_init[a_idx, a_idx, a_idx, j, j] = base_dist_aJ[j, a_idx]

    print(f"\n[5/5] Run both kernels and compare...")
    # NUMPY kernel
    t1 = time.time()
    np_dist_next, np_w, np_agg = _step_period_5d(
        dist5d_init, aGrid, joint_markov,
        cFuncs_pol_t, cFuncs_none_t, cFuncs_b_t,
        IncShk_pol_t, IncShk_none_t, IncShk_b_t,
        Rfree, PermGroFac, Splurge, rho,
        Cratio_pol, Cratio_none,
        AggDemandFac_pol, AggDemandFac_none,
        TranShk_addition_pol, TranShk_addition_none,
        LivPrb_avg=1.0, newborn_dist5d_diag=None,
    )
    np_wall = time.time() - t1
    print(f"  NUMPY kernel wall: {np_wall:.2f}s")

    # JAX kernel
    dtype = jnp.float64 if _USE_FP64 else jnp.float32
    t1 = time.time()
    jax_dist_next, jax_w, jax_agg = _step_period_5d_jax_loops(
        jnp.asarray(dist5d_init, dtype=dtype),
        jnp.asarray(aGrid, dtype=dtype),
        jnp.asarray(joint_markov, dtype=dtype),
        jnp.asarray(cfunc_pol_table_t, dtype=dtype),
        jnp.asarray(cfunc_none_table_t, dtype=dtype),
        jnp.asarray(cfunc_b_table_t, dtype=dtype),
        jnp.asarray(m_grid, dtype=dtype),
        jnp.asarray(pol_arrs['psi'], dtype=dtype),
        jnp.asarray(pol_arrs['xi'], dtype=dtype),
        jnp.asarray(pmv_pol_q, dtype=dtype),
        pol_arrs['n_atoms'],
        jnp.asarray(none_arrs['xi'], dtype=dtype),  # psi shared with pol
        jnp.asarray(b_arrs['psi'], dtype=dtype),
        jnp.asarray(b_arrs['xi'], dtype=dtype),
        jnp.asarray(pmv_b_q, dtype=dtype),
        b_arrs['n_atoms'],
        atom_p_idx, atom_b_idx,
        jnp.asarray(joint_pmv, dtype=dtype),
        jnp.asarray(Rfree, dtype=dtype),
        jnp.asarray(PermGroFac, dtype=dtype),
        Splurge, rho,
        Cratio_pol, Cratio_none,
        AggDemandFac_pol, AggDemandFac_none,
        jnp.asarray(TranShk_addition_pol, dtype=dtype),
        jnp.asarray(TranShk_addition_none, dtype=dtype),
        LivPrb_avg=1.0, newborn_dist5d_diag=None,
    )
    jax_dist_next_np = np.asarray(jax_dist_next.block_until_ready())
    jax_wall = time.time() - t1
    print(f"  JAX kernel wall: {jax_wall:.2f}s")

    print(f"\n=== Comparison ===")
    print(f"  welfare_num:  numpy={np_w:.6e}, jax={jax_w:.6e}, rel={abs(jax_w - np_w)/(abs(np_w)+1e-12):.3e}")
    print(f"  inc_pol:      numpy={np_agg['inc_pol']:.6e}, jax={jax_agg['inc_pol']:.6e}, rel={abs(jax_agg['inc_pol'] - np_agg['inc_pol'])/(abs(np_agg['inc_pol'])+1e-12):.3e}")
    print(f"  cons_pol:     numpy={np_agg['cons_pol']:.6e}, jax={jax_agg['cons_pol']:.6e}, rel={abs(jax_agg['cons_pol'] - np_agg['cons_pol'])/(abs(np_agg['cons_pol'])+1e-12):.3e}")

    diff = np.abs(np_dist_next - jax_dist_next_np)
    max_abs = diff.max()
    max_rel = (diff / (np.abs(np_dist_next) + 1e-12)).max()
    np_total = np_dist_next.sum()
    jax_total = jax_dist_next_np.sum()
    mass_rel = abs(jax_total - np_total) / max(abs(np_total), 1e-12)
    print(f"  dist5d_next: max|diff|={max_abs:.3e}, max rel|diff|={max_rel:.3e}")
    print(f"  mass: numpy={np_total:.6f}, jax={jax_total:.6f}, rel mass diff={mass_rel:.3e}")

    # === v2 vectorized kernel ===
    print(f"\n  Running v2 vectorized JAX kernel...")
    t1 = time.time()
    v2_dist_next, v2_w, v2_agg = _step_period_5d_jax_v2(
        jnp.asarray(dist5d_init, dtype=dtype),
        jnp.asarray(aGrid, dtype=dtype),
        jnp.asarray(joint_markov, dtype=dtype),
        jnp.asarray(cfunc_pol_table_t, dtype=dtype),
        jnp.asarray(cfunc_none_table_t, dtype=dtype),
        jnp.asarray(cfunc_b_table_t, dtype=dtype),
        jnp.asarray(m_grid, dtype=dtype),
        jnp.asarray(pol_arrs['psi'], dtype=dtype),
        jnp.asarray(pol_arrs['xi'], dtype=dtype),
        jnp.asarray(pmv_pol_q, dtype=dtype),
        pol_arrs['n_atoms'],
        jnp.asarray(none_arrs['xi'], dtype=dtype),
        jnp.asarray(b_arrs['psi'], dtype=dtype),
        jnp.asarray(b_arrs['xi'], dtype=dtype),
        jnp.asarray(pmv_b_q, dtype=dtype),
        b_arrs['n_atoms'],
        atom_p_idx, atom_b_idx,
        jnp.asarray(joint_pmv, dtype=dtype),
        jnp.asarray(Rfree, dtype=dtype),
        jnp.asarray(PermGroFac, dtype=dtype),
        Splurge, rho,
        Cratio_pol, Cratio_none,
        AggDemandFac_pol, AggDemandFac_none,
        jnp.asarray(TranShk_addition_pol, dtype=dtype),
        jnp.asarray(TranShk_addition_none, dtype=dtype),
        LivPrb_avg=1.0, newborn_dist5d_diag=None,
    )
    v2_dist_next_np = np.asarray(v2_dist_next.block_until_ready())
    v2_wall = time.time() - t1
    print(f"  v2 kernel wall: {v2_wall:.2f}s (vs v1 {jax_wall:.2f}s, numpy {np_wall:.2f}s)")
    print(f"\n=== v2 Comparison ===")
    print(f"  welfare_num:  numpy={np_w:.6e}, v2={v2_w:.6e}, rel={abs(v2_w - np_w)/(abs(np_w)+1e-12):.3e}")
    print(f"  cons_pol:     numpy={np_agg['cons_pol']:.6e}, v2={v2_agg['cons_pol']:.6e}, rel={abs(v2_agg['cons_pol'] - np_agg['cons_pol'])/(abs(np_agg['cons_pol'])+1e-12):.3e}")
    diff2 = np.abs(np_dist_next - v2_dist_next_np)
    print(f"  dist5d_next: max|diff|={diff2.max():.3e}")
    v2_mass = v2_dist_next_np.sum()
    print(f"  mass: numpy={np_total:.6f}, v2={v2_mass:.6f}, rel mass diff={abs(v2_mass-np_total)/max(abs(np_total),1e-12):.3e}")

    # === v3 JIT'd kernel ===
    print(f"\n  Running v3 JIT'd kernel (first call includes compile)...")
    t1 = time.time()
    v3_dist_next, v3_w, v3_agg = _step_period_5d_jax_v3(
        jnp.asarray(dist5d_init, dtype=dtype),
        jnp.asarray(aGrid, dtype=dtype),
        jnp.asarray(joint_markov, dtype=dtype),
        jnp.asarray(cfunc_pol_table_t, dtype=dtype),
        jnp.asarray(cfunc_none_table_t, dtype=dtype),
        jnp.asarray(cfunc_b_table_t, dtype=dtype),
        jnp.asarray(m_grid, dtype=dtype),
        jnp.asarray(pol_arrs['psi'], dtype=dtype),
        jnp.asarray(pol_arrs['xi'], dtype=dtype),
        jnp.asarray(pmv_pol_q, dtype=dtype),
        pol_arrs['n_atoms'],
        jnp.asarray(none_arrs['xi'], dtype=dtype),
        jnp.asarray(b_arrs['psi'], dtype=dtype),
        jnp.asarray(b_arrs['xi'], dtype=dtype),
        jnp.asarray(pmv_b_q, dtype=dtype),
        b_arrs['n_atoms'],
        atom_p_idx, atom_b_idx,
        jnp.asarray(joint_pmv, dtype=dtype),
        jnp.asarray(Rfree, dtype=dtype),
        jnp.asarray(PermGroFac, dtype=dtype),
        Splurge, rho,
        Cratio_pol, Cratio_none,
        AggDemandFac_pol, AggDemandFac_none,
        jnp.asarray(TranShk_addition_pol, dtype=dtype),
        jnp.asarray(TranShk_addition_none, dtype=dtype),
        LivPrb_avg=1.0, newborn_dist5d_diag=None,
    )
    v3_dist_next_np = np.asarray(v3_dist_next.block_until_ready())
    v3_wall_first = time.time() - t1
    print(f"  v3 first call (compile+exec): {v3_wall_first:.2f}s")

    # Second call (cached compile)
    t1 = time.time()
    v3_dist_next2, _, _ = _step_period_5d_jax_v3(
        jnp.asarray(dist5d_init, dtype=dtype),
        jnp.asarray(aGrid, dtype=dtype),
        jnp.asarray(joint_markov, dtype=dtype),
        jnp.asarray(cfunc_pol_table_t, dtype=dtype),
        jnp.asarray(cfunc_none_table_t, dtype=dtype),
        jnp.asarray(cfunc_b_table_t, dtype=dtype),
        jnp.asarray(m_grid, dtype=dtype),
        jnp.asarray(pol_arrs['psi'], dtype=dtype),
        jnp.asarray(pol_arrs['xi'], dtype=dtype),
        jnp.asarray(pmv_pol_q, dtype=dtype),
        pol_arrs['n_atoms'],
        jnp.asarray(none_arrs['xi'], dtype=dtype),
        jnp.asarray(b_arrs['psi'], dtype=dtype),
        jnp.asarray(b_arrs['xi'], dtype=dtype),
        jnp.asarray(pmv_b_q, dtype=dtype),
        b_arrs['n_atoms'],
        atom_p_idx, atom_b_idx,
        jnp.asarray(joint_pmv, dtype=dtype),
        jnp.asarray(Rfree, dtype=dtype),
        jnp.asarray(PermGroFac, dtype=dtype),
        Splurge, rho,
        Cratio_pol, Cratio_none,
        AggDemandFac_pol, AggDemandFac_none,
        jnp.asarray(TranShk_addition_pol, dtype=dtype),
        jnp.asarray(TranShk_addition_none, dtype=dtype),
        LivPrb_avg=1.0, newborn_dist5d_diag=None,
    )
    _ = jnp.asarray(v3_dist_next2).block_until_ready()
    v3_wall_warm = time.time() - t1
    print(f"  v3 warm call (cached): {v3_wall_warm:.2f}s")

    speedup_warm = np_wall / v3_wall_warm
    print(f"\n=== v3 JIT'd Comparison ===")
    print(f"  numpy:   {np_wall:.2f}s")
    print(f"  v3 cold: {v3_wall_first:.2f}s")
    print(f"  v3 warm: {v3_wall_warm:.2f}s")
    print(f"  warm speedup vs numpy: {speedup_warm:.2f}x")
    print(f"  welfare_num:  numpy={np_w:.6e}, v3={v3_w:.6e}, rel={abs(v3_w - np_w)/(abs(np_w)+1e-12):.3e}")
    diff3 = np.abs(np_dist_next - v3_dist_next_np)
    print(f"  dist5d_next: max|diff|={diff3.max():.3e}")
    v3_mass = v3_dist_next_np.sum()
    print(f"  mass: numpy={np_total:.6f}, v3={v3_mass:.6f}, rel mass diff={abs(v3_mass-np_total)/max(abs(np_total),1e-12):.3e}")


if __name__ == '__main__':
    main()
