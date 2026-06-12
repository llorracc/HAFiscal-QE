"""
Characterize the high-a tail of the Doob pi_Q^true ergodic.

For HS β=0.91 (moderate) and CO β=0.988 (high β), CDC and ESC:
  - Top 10 (a, j) cells by Doob pi_Q mass
  - Cumulative mass at top 1%, 5%, 10% of a-grid
  - Boundary pileup ratio (mass at last grid point vs second-to-last)
  - Compare to pi_P at same cells (where is Doob amplifying?)

If significant mass is at the topmost grid points, we're seeing
boundary pileup — the support is being clipped. Doob analytical
then over-weights the boundary.
"""
import os
import sys
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

sys.argv = ['harmenberg_doob_tail_chars']

from harmenberg_doob_tier1 import setup_context, build_agent_for
from tm_methods import (
    build_tm_agg_fiscal_a,
    find_ergodic_distribution,
    compute_doob_pi_q_a,
)


def chars_one(edType, beta, interp, ctx, aCount=200, aMax=500):
    print(f"\n{'=' * 78}")
    print(f"edType={edType}, β={beta:.4f}, interp={interp}, "
          f"aCount={aCount}, aMax={aMax}")
    print('=' * 78)
    agent = build_agent_for(edType, beta, ctx, interpretation=interp)
    tm_data_P = build_tm_agg_fiscal_a(agent, aCount=aCount, aMax=aMax, aFac=3,
                                       neutral_measure=False, interpretation=interp)
    pi_P = find_ergodic_distribution(tm_data_P['TranMatrix'])
    doob_out = compute_doob_pi_q_a(agent, tm_data_P, pi_P, interpretation=interp)
    pi_Q = doob_out['pi_Q_doob']
    w = doob_out['w']
    dist_aGrid = tm_data_P['dist_aGrid']
    A = len(dist_aGrid)
    J = pi_P.shape[0] // A
    pi_P_2d = pi_P.reshape(J, A)
    pi_Q_2d = pi_Q.reshape(J, A)
    w_2d = w.reshape(J, A)

    # Top 10 cells by pi_Q mass
    flat_pi_Q = [(pi_Q_2d[j, i], j, i, dist_aGrid[i]) for j in range(J) for i in range(A)]
    flat_pi_Q.sort(reverse=True)
    print(f"\nTop 10 (j, a) cells by Doob pi_Q mass:")
    print(f"  {'rank':>4} {'j':>2} {'i':>4} {'a':>10} {'pi_P':>12} {'pi_Q':>12} {'w':>10} {'pi_Q/pi_P':>10}")
    for rank, (m, j, i, a) in enumerate(flat_pi_Q[:10], 1):
        pi_P_v = pi_P_2d[j, i]
        ratio = m / pi_P_v if pi_P_v > 0 else float('inf')
        print(f"  {rank:>4} {j:>2} {i:>4} {a:>10.3f} {pi_P_v:>12.6f} {m:>12.6f} {w_2d[j,i]:>10.3f} {ratio:>10.2f}")

    # Cumulative mass in upper a-bins (highest 1%, 5%, 10% of a-grid)
    sorted_a_idx = list(range(A))  # a-grid is monotone increasing already
    pi_Q_a_marg = pi_Q_2d.sum(axis=0)  # marginal over j
    pi_P_a_marg = pi_P_2d.sum(axis=0)
    print(f"\nCumulative mass in top a-grid bins (Q-marginal):")
    print(f"  {'top-N':>10} {'a-cutoff':>10} {'pi_Q':>10} {'pi_P':>10} {'Q/P':>8}")
    for top_N in [1, 2, 5, 10, 20]:
        cutoff = dist_aGrid[A - top_N]
        mass_Q = pi_Q_a_marg[A-top_N:].sum()
        mass_P = pi_P_a_marg[A-top_N:].sum()
        ratio = mass_Q / mass_P if mass_P > 0 else float('inf')
        print(f"  {top_N:>10} {cutoff:>10.3f} {mass_Q:>10.6f} {mass_P:>10.6f} {ratio:>8.2f}")

    # Boundary pileup: ratio of last vs penultimate grid mass
    print(f"\nBoundary pileup check:")
    print(f"  pi_Q at a={dist_aGrid[-1]:.3f} (boundary):     {pi_Q_a_marg[-1]:.6f}")
    print(f"  pi_Q at a={dist_aGrid[-2]:.3f} (penultimate): {pi_Q_a_marg[-2]:.6f}")
    print(f"  pi_Q at a={dist_aGrid[-3]:.3f}:               {pi_Q_a_marg[-3]:.6f}")
    if pi_Q_a_marg[-2] > 0:
        print(f"  ratio boundary/penultimate (pi_Q): {pi_Q_a_marg[-1]/pi_Q_a_marg[-2]:.3f}")
    if pi_P_a_marg[-2] > 0:
        print(f"  ratio boundary/penultimate (pi_P): {pi_P_a_marg[-1]/pi_P_a_marg[-2]:.3f}")
    print(f"  → if ratio >> 1, mass is piling up at boundary (grid truncation).")
    print(f"  → if ratio << 1, distribution decays smoothly (grid is wide enough).")


def main():
    ctx = setup_context('Baseline')
    DFD = ctx['DiscFacDstns']
    configs = [
        (1, float(DFD[1].atoms[0][3]), 'CDC'),  # HS β=0.91
        (2, float(DFD[2].atoms[0][5]), 'CDC'),  # CO β=0.988
        (2, float(DFD[2].atoms[0][5]), 'ESC'),  # CO β=0.988 ESC
    ]
    for cfg in configs:
        chars_one(*cfg, ctx)

    # Also: CO 0.988 with WIDER grid to confirm pileup interpretation
    print("\n\n*** Sensitivity: CO β=0.988 CDC with aMax=5000, aCount=500 ***")
    chars_one(2, float(DFD[2].atoms[0][5]), 'CDC', ctx, aCount=500, aMax=5000)


if __name__ == "__main__":
    main()
