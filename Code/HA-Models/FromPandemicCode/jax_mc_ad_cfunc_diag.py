"""
Quick diagnostic: how much error does my pre-tabulation introduce into the
cFunc lookup, especially at high mNrm where high-beta agents live?

Compare:
  (a) Direct HARK call: cFunc[state](mNrm_test, Cratio_test)
  (b) My pre-tabulation on m_grid_500 + linear interp between grid points

For a high-beta cohort (College beta=0.99), evaluate at mNrm in [1, 5, 10, 20, 30, 40]
and combined_state = a recession macro × J + 0 (employed).
"""
import sys, os, pickle, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
import numpy as np
from copy import deepcopy
from welfare6_scenario import build_and_solve, run_base


def main():
    print("=== cFunc tabulation precision test (Baseline, high-beta cohort) ===")
    ref = pickle.load(open('welfare6_BL_ad_ref/recession_AD.pkl', 'rb'))
    hark_cratio = ref['iter_logs'][-1]['Cratio_hist']
    num_exp = ref['num_experiment_periods']

    print(f"Building Baseline...", flush=True)
    t0 = time.time()
    ctx = build_and_solve('Baseline')
    _ = run_base(ctx)
    print(f"build+base: {time.time()-t0:.1f}s", flush=True)

    AggEco = ctx['AggEco']
    eco = deepcopy(AggEco)
    eco.switch_shock_type('recession')

    # Install HARK-converged MacroCFunc
    from AggFiscalModel import CRule
    n_combined = len(eco.CFunc)
    J = eco.num_base_MrkvStates
    n_macro = n_combined // J
    MacroCFunc = [[CRule(1.0, 0.0) for _ in range(n_macro)] for _ in range(n_macro)]
    MacroCFunc[0][3] = CRule(float(hark_cratio[0]), 0.0)
    for j in range(num_exp - 1):
        MacroCFunc[2 * j + 3][2 * j + 5] = CRule(float(hark_cratio[j + 1]), 0.0)
    MacroCFunc[2 * num_exp + 1][1] = CRule(float(hark_cratio[num_exp]), 0.0)
    MacroCFunc[1][1] = CRule(float(np.mean(hark_cratio[num_exp + 1:num_exp + 10])), 0.0)
    eco.CFunc = eco.Macro_2_Micro_CFunc(MacroCFunc)
    for agent in eco.agents:
        agent.CFunc = eco.CFunc
    eco.ADelasticity = eco.demand_ADelasticity

    print(f"Solving eco...", flush=True)
    t0 = time.time()
    eco.solve()
    print(f"solve: {time.time()-t0:.1f}s", flush=True)

    # Pick a high-beta cohort (College, beta=0.9988 → cohort 20)
    high_beta_agent = eco.agents[20]
    print(f"\nUsing high-beta agent: beta={float(high_beta_agent.DiscFac):.4f}")

    # Combined state for macro=3 (first recession), micro=0 (employed)
    test_states = [3 * J, 5 * J, 7 * J]  # macros 3, 5, 7, all micro=0
    test_mNrm = np.array([1.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 49.0])
    test_Cratio = 0.98

    # Pre-tabulate
    from welfare6_tm_joint5d_jax_kernel import build_m_grid, tabulate_cfunc_list
    m_grid = build_m_grid(500)
    sol = high_beta_agent.solution[0]

    for state_idx in test_states:
        cf = sol.cFunc[state_idx]
        # Tabulate on m_grid at Cratio=0.98
        c_tab = np.array([float(cf(np.array([mg]), np.array([test_Cratio]))[0])
                          for mg in m_grid])
        # Direct evaluations
        c_direct = np.array([float(cf(np.array([mn]), np.array([test_Cratio]))[0])
                              for mn in test_mNrm])
        # Interpolated from tabulation
        c_interp = []
        for mn in test_mNrm:
            i_lo = max(0, min(len(m_grid) - 2, int(np.searchsorted(m_grid, mn, side='right') - 1)))
            w_hi = (mn - m_grid[i_lo]) / (m_grid[i_lo + 1] - m_grid[i_lo])
            c_interp.append(c_tab[i_lo] + w_hi * (c_tab[i_lo + 1] - c_tab[i_lo]))
        c_interp = np.array(c_interp)
        rel_err = (c_interp - c_direct) / np.maximum(c_direct, 1e-9)
        print(f"\n  state={state_idx} (macro={state_idx//J}, micro=0):")
        print(f"  {'mNrm':>6} {'c_direct':>12} {'c_interp':>12} {'rel_err':>10}")
        for k, mn in enumerate(test_mNrm):
            print(f"  {mn:>6.2f} {c_direct[k]:>12.6f} {c_interp[k]:>12.6f} {rel_err[k]:>+10.4%}")


if __name__ == '__main__':
    main()
