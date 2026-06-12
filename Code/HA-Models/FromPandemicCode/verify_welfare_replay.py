"""Paper-grade welfare cell verification via JAX replay-v2.

This is the production tool for getting a paper-grade welfare cell value when
your AD pipeline used JAX (which has a ~6% systematic welfare bias vs HARK
due to independent RNG realizations — see
project_welfare_gap_replay_closes_2026_05_19.md).

Usage:

    # Spot-check HS_Only check_rec_AD welfare cell
    python verify_welfare_replay.py --parametrization HS_Only --policy recessionCheck

    # Other scenarios
    python verify_welfare_replay.py --parametrization HS_Only --policy recessionTaxCut
    python verify_welfare_replay.py --parametrization HS_Only --policy recessionUI

    # Baseline (slower — runs full HARK AD)
    python verify_welfare_replay.py --parametrization Baseline --policy recessionCheck

What it does:
  1. Build agents, run base scenario
  2. Run HARK AD for "no-policy" recession baseline AND policy scenario, capturing shocks
  3. Run JAX replay-v2 on both scenarios using HARK's exact shocks
  4. Compute welfare cell two ways:
     - HARK reference (canonical)
     - JAX replay-v2 (should match HARK to <0.5%)
  5. Report the comparison

The JAX replay-v2 number is paper-grade and matches HARK to bit-precision-ish
(~0.2% rel). Use it as a verification that your JAX-AD-derived numbers are
consistent with HARK, OR as a way to spot-check that your JAX kernel changes
haven't broken anything.

Wall cost: ~one HARK AD run per scenario + ~10s per JAX replay. At HS_Only
that's ~1 min total; at Baseline ~70 min total. NOT a speedup — it's a
verification tool that gives you the HARK answer using the JAX kernel as
an oracle.
"""
import sys, os, argparse, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--parametrization', '-p', default='HS_Only',
                   choices=['HS_Only', 'Reduced_Run', 'Baseline',
                            'CRRA1', 'CRRA3', 'CRRA1_PVSame', 'CRRA3_PVSame'],
                   help='Which HAFiscal config to verify (default: HS_Only)')
    p.add_argument('--policy', default='recessionCheck',
                   choices=['recessionCheck', 'recessionTaxCut', 'recessionUI'],
                   help='Policy scenario to compute welfare for (default: recessionCheck)')
    p.add_argument('--no-policy', default='recession',
                   help='Baseline no-policy scenario (default: recession)')
    p.add_argument('--solve-workers', type=int, default=None,
                   help='Number of parallel cohort workers for HARK solves '
                        '(default: from HAFISCAL_PARALLEL_SOLVE env or 1=sequential)')
    return p.parse_args()


def main():
    args = _parse_args()
    # Strip CLI args before HAFiscal Parameters.py sees them
    sys.argv = [sys.argv[0]]
    os.environ['JAX_ENABLE_X64'] = 'True'
    import jax
    jax.config.update('jax_enable_x64', True)

    import numpy as np
    from copy import deepcopy
    import welfare6_scenario as ws
    from welfare6_scenario import build_and_solve, run_base
    from run_welfare6_parallel import welfare6_mc
    # Reuse the proven harness from jax_mc_welfare_replay_test
    from jax_mc_welfare_replay_test import (
        run_hark_with_capture, jax_replay_scenario)

    # Activate cohort parallelization for HARK solves (huge wall-time win at Baseline)
    n_workers = args.solve_workers
    if n_workers is None:
        env = os.environ.get('HAFISCAL_PARALLEL_SOLVE', '').strip()
        if env.isdigit() and int(env) > 0:
            n_workers = int(env)
    if n_workers and n_workers > 1:
        ws._SOLVE_WORKERS = n_workers
        print(f"  Parallel solve: {n_workers} workers", flush=True)

    print(f"=== Welfare cell verification ===")
    print(f"  Parametrization: {args.parametrization}")
    print(f"  Policy scenario: {args.policy}")
    print(f"  No-policy scenario: {args.no_policy}")

    t_total = time.time()
    ctx = build_and_solve(args.parametrization)
    AggEco = ctx['AggEco']
    base_result = run_base(ctx)
    num_exp = ctx['num_experiment_periods']
    num_iter = ctx['num_max_iterations_solvingAD']
    cutoff = ctx['convergence_tol_solvingAD']

    print(f"\n[HARK+capture] {args.no_policy} ...", flush=True)
    eco_none, hark_none_log = run_hark_with_capture(
        AggEco, args.no_policy, num_exp, num_iter, cutoff)

    print(f"[HARK+capture] {args.policy} ...", flush=True)
    eco_pol, hark_pol_log = run_hark_with_capture(
        AggEco, args.policy, num_exp, num_iter, cutoff)

    hark_none_r = {'AggCons': hark_none_log['AggCons'],
                   'AggIncome': hark_none_log['AggIncome'],
                   'cLvl_all_splurge': hark_none_log['cLvl_all_splurge']}
    hark_pol_r = {'AggCons': hark_pol_log['AggCons'],
                  'AggIncome': hark_pol_log['AggIncome'],
                  'cLvl_all_splurge': hark_pol_log['cLvl_all_splurge']}
    hark_cell = welfare6_mc(hark_pol_r, hark_none_r, base_result,
                              ctx['act_T'], ctx['Rfree'], ctx['CRRA'])
    print(f"\nHARK welfare cell: {hark_cell:.6f}", flush=True)

    print(f"\n[JAX-replay-v2] {args.no_policy} ...", flush=True)
    jax_none_r = jax_replay_scenario(eco_none, hark_none_log, args.no_policy, num_exp)
    print(f"  Cratio[0]: JAX {jax_none_r['Cratio_hist'][0]:.4f} vs HARK {hark_none_log['Cratio_hist'][0]:.4f}")

    print(f"\n[JAX-replay-v2] {args.policy} ...", flush=True)
    jax_pol_r = jax_replay_scenario(eco_pol, hark_pol_log, args.policy, num_exp)
    print(f"  Cratio[0]: JAX {jax_pol_r['Cratio_hist'][0]:.4f} vs HARK {hark_pol_log['Cratio_hist'][0]:.4f}")

    jax_cell = welfare6_mc(jax_pol_r, jax_none_r, base_result,
                            ctx['act_T'], ctx['Rfree'], ctx['CRRA'])

    rel = (jax_cell - hark_cell) / hark_cell * 100
    print(f"\n=== Result ===")
    print(f"HARK welfare cell:         {hark_cell:.6f}")
    print(f"JAX-replay-v2 welfare cell: {jax_cell:.6f}")
    print(f"Relative diff: {rel:+.4f}%")
    print(f"Total wall: {time.time()-t_total:.1f}s")
    if abs(rel) < 0.5:
        print("\n✓ JAX-replay-v2 matches HARK welfare to <0.5% — paper-grade")
    elif abs(rel) < 2.0:
        print(f"\n⚠ JAX-replay-v2 diverges by {abs(rel):.2f}% — investigate if >1%")
    else:
        print(f"\n✗ JAX-replay-v2 diverges by {abs(rel):.2f}% — kernel regression")


if __name__ == '__main__':
    main()
