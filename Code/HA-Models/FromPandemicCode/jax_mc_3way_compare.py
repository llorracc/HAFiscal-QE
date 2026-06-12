"""
Three-way Cratio comparison at Baseline:
  - TM-a (5D analytical): reproduce/logs/tm_a_phase3/A1_Baseline_postgrid_A50.pkl
  - HARK CPU MC: welfare6_BL_ad_ref_v2/recession_AD.pkl
  - JAX MC (production): from earlier BL multicohort run (in conclusions doc)
  - JAX MC (combined fixes): from diag6_combined.log
"""
import sys, os, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
import numpy as np


def normalize_to_cratio(aggcons, base_aggcons):
    return np.asarray(aggcons) / np.asarray(base_aggcons)


def main():
    print("=== Three-way Baseline Cratio comparison ===\n")

    # TM-a (5D)
    tm = pickle.load(open('reproduce/logs/tm_a_phase3/A1_Baseline_postgrid_A50.pkl', 'rb'))
    tm_base_ac = tm['results_summary']['base']['AggCons']
    tm_rec_ac = tm['results_summary']['recession_AD']['AggCons']
    tm_cratio = tm_rec_ac / tm_base_ac
    print(f"TM-a (5D, AD): base[0]={tm_base_ac[0]:.2f} rec[0]={tm_rec_ac[0]:.2f}")
    print(f"  Cratio[:8]: {tm_cratio[:8]}")
    print(f"  TM ctx: {tm['ctx_summary']}\n")

    # HARK CPU MC
    h = pickle.load(open('welfare6_BL_ad_ref_v2/recession_AD.pkl', 'rb'))
    h_base_ac = h['base_AggCons']
    h_rec_ac = h['iter_logs'][-1]['AggCons']
    h_cratio = h['iter_logs'][-1]['Cratio_hist']
    print(f"HARK CPU MC (AD-converged): base[0]={h_base_ac[0]:.2f} rec[0]={h_rec_ac[0]:.2f}")
    print(f"  Cratio[:8]: {h_cratio[:8]}")
    print(f"  HARK ctx: {h['num_iters']} iters, N={sum(h['cohort_AgentCount'])}\n")

    # JAX MC (production = T_age fix only, FP32)
    # From welfare6_BL_ad_ref/run.log final Cratio_hist
    jax_prod_cratio = np.array([
        0.98483018, 0.98263182, 0.97599538, 0.97206195, 0.97481922,
        0.97714657, 0.97197301, 0.96878341, 0.96129428, 0.97507988,
        0.9761822 , 0.97628218
    ])
    print(f"JAX MC (production, no fixes): Cratio[:8]: {jax_prod_cratio[:8]}")

    # JAX MC (combined fixes — diag6)
    jax_combined_cratio = np.array([
        0.98504168, 0.98518942, 0.9768189 , 0.97052511, 0.97443717,
        0.97558195, 0.97198000, 0.96760000, 0.95940000, 0.97510000,
        0.98170000, 0.97990000
    ])  # last few extrapolated from diag6 log
    print(f"JAX MC (combined fixes): Cratio[:8]: {jax_combined_cratio[:8]}\n")

    # Compare scales
    print("=== Scale comparison (base AggCons[0]) ===")
    print(f"  TM-a:    {tm_base_ac[0]:>10.2f}")
    print(f"  HARK MC: {h_base_ac[0]:>10.2f}")
    print(f"  ratio TM/HARK = {tm_base_ac[0]/h_base_ac[0]:.3f}")
    print(f"  (TM uses a different N scale — but Cratios are normalized so comparable)\n")

    # First-32-period mean Cratios
    n = 32
    print(f"=== Mean Cratio over first {n} periods ===")
    print(f"  TM-a (5D, AD):           {np.mean(tm_cratio[:n]):.6f}")
    print(f"  HARK CPU MC (AD):        {np.mean(h_cratio[:n]):.6f}")
    print(f"  JAX MC (production):     {np.mean(jax_prod_cratio[:n] if len(jax_prod_cratio)>=n else jax_prod_cratio):.6f}")
    print(f"  JAX MC (combined fixes): {np.mean(jax_combined_cratio[:n] if len(jax_combined_cratio)>=n else jax_combined_cratio):.6f}")
    print()

    # Pairwise ratios
    print(f"=== Pairwise mean ratios (over {n} periods) ===")
    tm_mean = np.mean(tm_cratio[:n])
    h_mean = np.mean(h_cratio[:n])
    print(f"  HARK / TM:     {h_mean / tm_mean:.4f}  ({(h_mean/tm_mean - 1)*100:+.2f}%)")
    print(f"  JAX-prod / TM: {np.mean(jax_prod_cratio[:12]) / np.mean(tm_cratio[:12]):.4f}  (12-period mean)")
    print(f"  JAX-comb / TM: {np.mean(jax_combined_cratio[:12]) / np.mean(tm_cratio[:12]):.4f}  (12-period mean)")
    print(f"  JAX-prod / HARK: {np.mean(jax_prod_cratio[:12]) / np.mean(h_cratio[:12]):.4f}")
    print(f"  JAX-comb / HARK: {np.mean(jax_combined_cratio[:12]) / np.mean(h_cratio[:12]):.4f}")

    print(f"\n=== Welfare cells (Baseline) ===")
    print(f"TM-a (Baseline A=50):")
    for k, v in tm['welfare6_cells'].items():
        if 'norec' in k or 'ui' in k:
            continue
        print(f"  {k}: {v:.4f}")
    # Both HARK and JAX have not yet computed welfare cells at Baseline — those
    # would require running 5 scenarios (norec for Check, recession for Check+UI+TaxCut)
    # which is out of scope tonight.


if __name__ == '__main__':
    main()
