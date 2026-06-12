"""Diagnostic: does agent.aNrm_base equal HARK's history[0]['aNrm'] for recession?"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
os.environ['JAX_ENABLE_X64'] = 'True'
import jax
jax.config.update('jax_enable_x64', True)
import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve, run_base


def stats(name, arr):
    a = np.asarray(arr)
    return (f"  {name}: mean={a.mean():.4f} min={a.min():.4f} max={a.max():.4f} "
            f"std={a.std():.4f} N={len(a)} <=0={(a<=0).sum()}")


def main():
    ctx = build_and_solve('HS_Only')
    AggEco = ctx['AggEco']
    base_mc = run_base(ctx)

    print("=== After run_base: agent._base ===")
    for c_idx, ag in enumerate(AggEco.agents):
        print(f"\nCohort {c_idx}:")
        print(stats('aNrm_base', ag.aNrm_base))
        print(stats('pLvl_base', ag.pLvl_base))
        Mrkv_base = np.asarray(ag.Mrkv_base, dtype=np.int64)
        J = ag.num_base_MrkvStates
        micro = Mrkv_base % J
        macro = Mrkv_base // J
        from collections import Counter
        print(f"  Mrkv_base micro counts: {dict(sorted(Counter(micro.tolist()).items()))}")
        print(f"  Mrkv_base macro counts: {dict(sorted(Counter(macro.tolist()).items()))}")

    print("\n=== After run_experiment(recession): history[0] ===")
    eco_h = deepcopy(AggEco)
    eco_h.switch_shock_type('recession')
    eco_h.solve_ad_recession(
        num_max_iterations=ctx['num_max_iterations_solvingAD'],
        convergence_cutoff=ctx['convergence_tol_solvingAD'], name='recession')
    eco_h.switch_shock_type('recession')
    eco_h.restore_ADsolution(name='recession')
    num_exp = eco_h.num_experiment_periods
    rec_dict = {'shock_type': 'recession', 'UpdatePrb': 1.0,
                'Splurge': eco_h.agents[0].Splurge,
                'EconomyMrkv_init': list(np.arange(1, num_exp+1)*2+1) + [1]*12 + [0]*20}
    h_res = eco_h.run_experiment(**rec_dict, Full_Output=True)
    aNrm_t0 = np.asarray(h_res['aNrm_all'][0])
    pLvl_t0 = np.asarray(h_res['pLvl_all'][0])
    Mrkv_t0 = np.asarray(h_res['Mrkv_hist'][0])
    J = eco_h.num_base_MrkvStates
    micro_t0 = Mrkv_t0 % J
    macro_t0 = Mrkv_t0 // J
    from collections import Counter
    print(stats('HARK recession history[0] aNrm', aNrm_t0))
    print(stats('HARK recession history[0] pLvl', pLvl_t0))
    print(f"  Mrkv micro counts: {dict(sorted(Counter(micro_t0.tolist()).items()))}")
    print(f"  Mrkv macro counts: {dict(sorted(Counter(macro_t0.tolist()).items()))}")

    print(f"\nHARK Cratio[0] = {h_res['Cratio_hist'][0]:.4f}")
    print(f"HARK AggCons[0] = {h_res['AggCons'][0]:.4f}")
    print(f"base_AggCons[0] = {AggEco.base_AggCons[0]:.4f}")
    print(f"Implied ratio = {h_res['AggCons'][0]/AggEco.base_AggCons[0]:.4f}")


if __name__ == '__main__':
    main()
