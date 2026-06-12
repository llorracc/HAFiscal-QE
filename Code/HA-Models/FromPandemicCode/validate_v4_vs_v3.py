"""
Phase C.4.1 → C.4.2 validation: v4 cohort-batched kernel with n_cohorts=1
must produce bit-identical output to v3 single-cohort kernel.
"""
from __future__ import annotations
import os, sys, time
from copy import deepcopy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]

from welfare6_scenario import build_and_solve
from welfare6_tm_joint5d_jax_kernel import (
    tabulate_cfunc_list, extract_incshk_arrays, q_reweight_pmv,
    build_joint_atom_table,
    _step_period_5d_jax_v3, _step_period_5d_jax_v4,
    _USE_FP64,
)
from welfare6_tm_joint5d import (
    compute_joint_markov, _resolve_scenario_IncShkDstn,
)
from tm_methods import compute_baseline_tm_data
import jax
import jax.numpy as jnp


def _build_econ_mrkv_path(act_T, num_experiment_periods, dur):
    path = list(np.arange(1, num_experiment_periods + 1) * 2) + [0] * (act_T + 5)
    path = path[:act_T]
    for t in range(min(dur, len(path))):
        path[t] = path[t] + 1
    return path


def main():
    aCount = int(os.environ.get('JOINT5D_ACOUNT', 10))
    M_grid = int(os.environ.get('M_GRID', 500))
    print(f"{'='*70}")
    print(f"Phase C.4.2 validation: v4 (n=1) vs v3 single-cohort")
    print(f"  A={aCount}, M_grid={M_grid}")
    print(f"  JAX backend: {jax.default_backend()}")
    print(f"{'='*70}")

    print(f"\n[1/4] Build HS_Only context + solve...")
    ctx = build_and_solve('HS_Only')
    AggEco_pol = deepcopy(ctx['AggEco']); AggEco_pol.switch_shock_type('recessionUI'); AggEco_pol.solve()
    AggEco_none = deepcopy(ctx['AggEco']); AggEco_none.switch_shock_type('recession'); AggEco_none.solve()
    AggEco_base = deepcopy(ctx['AggEco']); AggEco_base.switch_shock_type('base'); AggEco_base.solve()
    for ag in AggEco_pol.agents: ag.tm_a_indexed = True
    for ag in AggEco_none.agents: ag.tm_a_indexed = True
    for ag in AggEco_base.agents: ag.tm_a_indexed = True
    bd_list = compute_baseline_tm_data(AggEco_base, mCount=aCount, neutral_measure=True)

    agent_pol = AggEco_pol.agents[0]
    agent_none = AggEco_none.agents[0]
    agent_base = AggEco_base.agents[0]
    bd = bd_list[0]
    aGrid = bd['dist_aGrid']
    A = len(aGrid)
    J = int(agent_pol.num_base_MrkvStates)

    print(f"\n[2/4] Prepare common inputs for one period (macro=1 recession Q1)...")
    macro_pn = 1
    m_grid = np.linspace(0.01, 50.0, M_grid)
    base_idx_pn = macro_pn * J

    # Tabulate cFunc
    cFuncs_pol_t = [agent_pol.solution[0].cFunc[base_idx_pn + j] for j in range(J)]
    cFuncs_none_t = [agent_none.solution[0].cFunc[base_idx_pn + j] for j in range(J)]
    cFuncs_b_t = [agent_base.solution[0].cFunc[0 + j] for j in range(J)]
    cfunc_pol = tabulate_cfunc_list(cFuncs_pol_t, m_grid)
    cfunc_none = tabulate_cfunc_list(cFuncs_none_t, m_grid)
    cfunc_b = tabulate_cfunc_list(cFuncs_b_t, m_grid)

    # IncShkDstn
    IncShk_pol_full = _resolve_scenario_IncShkDstn(agent_pol, 'recessionUI')
    IncShk_none_full = _resolve_scenario_IncShkDstn(agent_none, 'recession')
    IncShk_base_full = _resolve_scenario_IncShkDstn(agent_base, 'base')
    IncShk_pol_t = list(IncShk_pol_full[base_idx_pn:base_idx_pn + J])
    IncShk_none_t = list(IncShk_none_full[base_idx_pn:base_idx_pn + J])
    IncShk_b_t = list(IncShk_base_full[0:J])
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
    atom_p_idx, atom_b_idx, joint_pmv = build_joint_atom_table(
        pmv_pol_q, pmv_b_q, pol_arrs['n_atoms'], b_arrs['n_atoms']
    )

    # Markov + economic params
    MA_pn = np.asarray(agent_pol.CondMrkvArrays[macro_pn], dtype=np.float64)
    MA_b = np.asarray(agent_base.CondMrkvArrays[0], dtype=np.float64)
    joint_markov = compute_joint_markov(MA_pn, MA_b)
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

    # Initial dist5d
    base_ergodic = np.asarray(bd['ergodic'], dtype=np.float64)
    base_dist_aJ = base_ergodic.reshape(J, A)
    dist5d_init = np.zeros((A, A, A, J, J), dtype=np.float64)
    for j in range(J):
        for a_idx in range(A):
            dist5d_init[a_idx, a_idx, a_idx, j, j] = base_dist_aJ[j, a_idx]

    dtype = jnp.float64 if _USE_FP64 else jnp.float32

    print(f"\n[3/4] Run v3 (single-cohort) kernel...")
    t1 = time.time()
    v3_dist, v3_w, v3_agg = _step_period_5d_jax_v3(
        jnp.asarray(dist5d_init, dtype=dtype),
        jnp.asarray(aGrid, dtype=dtype),
        jnp.asarray(joint_markov, dtype=dtype),
        jnp.asarray(cfunc_pol, dtype=dtype),
        jnp.asarray(cfunc_none, dtype=dtype),
        jnp.asarray(cfunc_b, dtype=dtype),
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
        jnp.asarray(atom_p_idx, dtype=jnp.int32),
        jnp.asarray(atom_b_idx, dtype=jnp.int32),
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
    # v3 returns numpy dist (converted internally); just measure
    v3_wall = time.time() - t1
    print(f"  v3 wall: {v3_wall:.2f}s, welfare_num={v3_w:.6e}")

    print(f"\n[4/4] Run v4 (cohort-batched, n=1) kernel...")
    # Build batched inputs with leading axis size 1
    def _add_batch_axis(arr):
        return jnp.asarray(arr, dtype=dtype)[None, ...]

    t1 = time.time()
    v4_dist, v4_w, v4_ipo, v4_ino, v4_cpo, v4_cno = _step_period_5d_jax_v4(
        _add_batch_axis(dist5d_init),         # (1, A, A, A, J, J)
        jnp.asarray(aGrid, dtype=dtype),
        _add_batch_axis(joint_markov),        # (1, J, J, J, J) per-cohort
        _add_batch_axis(cfunc_pol),           # (1, J, M)
        _add_batch_axis(cfunc_none),
        _add_batch_axis(cfunc_b),
        jnp.asarray(m_grid, dtype=dtype),
        _add_batch_axis(pol_arrs['psi']),     # (1, J, max_atoms)
        _add_batch_axis(pol_arrs['xi']),
        _add_batch_axis(pmv_pol_q),
        pol_arrs['n_atoms'],
        _add_batch_axis(none_arrs['xi']),
        _add_batch_axis(b_arrs['psi']),
        _add_batch_axis(b_arrs['xi']),
        _add_batch_axis(pmv_b_q),
        b_arrs['n_atoms'],
        jnp.asarray(atom_p_idx, dtype=jnp.int32)[None, ...],
        jnp.asarray(atom_b_idx, dtype=jnp.int32)[None, ...],
        _add_batch_axis(joint_pmv),
        _add_batch_axis(Rfree),       # (1, J)
        _add_batch_axis(PermGroFac),  # (1, J)
        Splurge, rho,
        Cratio_pol, Cratio_none,
        AggDemandFac_pol, AggDemandFac_none,
        jnp.asarray(TranShk_addition_pol, dtype=dtype),
        jnp.asarray(TranShk_addition_none, dtype=dtype),
        LivPrb_avg=1.0, newborn_dist5d_diag_batch=None,
    )
    v4_dist.block_until_ready()
    v4_wall = time.time() - t1
    v4_w_scalar = float(v4_w[0])
    print(f"  v4 wall: {v4_wall:.2f}s, welfare_num[0]={v4_w_scalar:.6e}")

    print(f"\n=== Comparison v3 vs v4 (n=1) ===")
    print(f"  welfare_num: v3={v3_w:.6e}, v4={v4_w_scalar:.6e}, rel diff={abs(v4_w_scalar-v3_w)/(abs(v3_w)+1e-12):.3e}")
    print(f"  inc_pol:     v3={v3_agg['inc_pol']:.6e}, v4={float(v4_ipo[0]):.6e}")
    print(f"  cons_pol:    v3={v3_agg['cons_pol']:.6e}, v4={float(v4_cpo[0]):.6e}")
    diff = np.abs(np.asarray(v3_dist) - np.asarray(v4_dist[0]))
    print(f"  dist5d_next: max|diff|={diff.max():.3e}")
    mass_v3 = np.asarray(v3_dist).sum()
    mass_v4 = np.asarray(v4_dist[0]).sum()
    print(f"  mass: v3={mass_v3:.6f}, v4={mass_v4:.6f}, diff={abs(mass_v4-mass_v3):.3e}")

    rel_w = abs(v4_w_scalar - v3_w) / (abs(v3_w) + 1e-12)
    if rel_w < 1e-5:
        print(f"\n  ✓ PASS — v4 with n=1 matches v3 within rtol=1e-5")
    else:
        print(f"\n  ✗ FAIL — rel diff {rel_w:.3e} > 1e-5")


if __name__ == '__main__':
    main()
