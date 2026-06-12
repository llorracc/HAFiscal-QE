"""
Validate multi-cohort recession kernel at Reduced_Run.
"""
import sys, os, pickle, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]
import numpy as np
from welfare6_scenario import build_and_solve
from jax_mc_multicohort import simulate_all_cohorts_recession


def main():
    hark = pickle.load(open('welfare6_RR_recession_ref/recession.pkl','rb'))
    h_inc = np.asarray(hark['AggIncome'])
    h_cons = np.asarray(hark['AggCons'])
    rec_probs = np.asarray(hark['rec_probs'])
    print(f"HARK Reduced_Run recession: AggInc mean={h_inc.mean():.3f}, AggCons mean={h_cons.mean():.3f}")
    print(f"HARK rec_probs: {rec_probs}")

    ctx = build_and_solve('Reduced_Run')
    t0 = time.time()
    result = simulate_all_cohorts_recession(
        ctx['AggEco'], scenario='recession',
        act_T=ctx.get('act_T', 40),
        num_experiment_periods=ctx['num_experiment_periods'],
        max_recession_duration=ctx['max_recession_duration'],
        seed_base=0, verbose=True,
        hark_pickle_for_init='welfare6_RR_recession_ref/recession.pkl',
        rec_probs=rec_probs,
    )
    wall = time.time() - t0
    j_inc = result['AggInc_total']; j_cons = result['AggCons_total']
    print(f"\nJAX wall: {wall:.1f}s")
    print(f"JAX dur-weighted AggInc mean: {j_inc.mean():.3f}")
    print(f"JAX dur-weighted AggCons mean: {j_cons.mean():.3f}")
    print(f"Ratio: AggInc={j_inc.mean()/h_inc.mean():.4f}, AggCons={j_cons.mean()/h_cons.mean():.4f}")
    print(f"Per-period correlation (skip t=0): "
          f"AggInc={np.corrcoef(j_inc[1:], h_inc[1:])[0,1]:.3f}, "
          f"AggCons={np.corrcoef(j_cons[1:], h_cons[1:])[0,1]:.3f}")


if __name__ == '__main__':
    main()
