"""
Diagnostic: does increasing TM aMax close the L3c.b2 30% MC↔TM gap?

Per L3c.b2 finding (commit 5508dde0): with HS 7-atom β atoms reaching
0.995 (near GIC boundary at Rfree=1.01), TM at default aMax=50 produced
K/Y = 5.32 while MC stabilized at 7.78 (gap ~30%).

Hypothesis: TM grid truncates the wealthy tail of the high-β atom's
ergodic distribution. Larger aMax → less truncation → higher TM K/Y.

Test: sweep aMax ∈ {50, 100, 200, 500, 1000} for the same 7-atom HS
setup; report TM K/Y at each. If TM K/Y monotonically rises toward MC's
~7.78, truncation is the cause. If it plateaus much lower, the issue is
something else.

Compute cost: ~2-5 min total (TM is fast even at large aMax + aCount).
No MC re-runs needed (we have the L3c.b2 cascade results).
"""

import os
import sys
import time
import numpy as np
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, '..')))

# CLAUDE.md: patch sys.argv before importing EstimParameters.
sys.argv = ['diag_l3c2_aMax_sweep']

from EstimParameters import (
    init_highschool, init_ADEconomy, UBspell_normal,
    DiscFacDstns, DiscFacCount,
)
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from tm_methods import (
    build_tm_agg_fiscal_a,
    compute_type_aggregates_tm_a,
    find_ergodic_distribution,
)
from HARK.distributions import DiscreteDistribution


def build_HS_7type():
    init = deepcopy(init_highschool)
    base = AggFiscalType(**init)
    base.cycles = 0
    economy = AggregateDemandEconomy(**init_ADEconomy)
    base.get_economy_data(economy)
    IncomeDstn_unemp = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([base.IncUnemp])]
    )
    IncomeDstn_unemp_nobenefits = DiscreteDistribution(
        np.array([1.0]), [np.array([1.0]), np.array([base.IncUnempNoBenefits])]
    )
    base.IncShkDstn = [
        [base.IncShkDstn[0]]
        + [IncomeDstn_unemp] * UBspell_normal
        + [IncomeDstn_unemp_nobenefits]
    ]
    base.IncShkDstn_base = base.IncShkDstn

    discfac_dstn = DiscFacDstns[1]
    pmv = discfac_dstn.pmv
    atoms = discfac_dstn.atoms[0]
    print(f"  HS β atoms: {atoms.tolist()}")

    typelist = []
    for b_idx in range(DiscFacCount):
        agent = deepcopy(base)
        agent.DiscFac = float(atoms[b_idx])
        agent.solve()
        typelist.append(agent)
    return typelist, pmv


def tm_KY_at_aMax(typelist, pmv, aMax, aCount=200):
    """Compute population K/Y under given (aMax, aCount). Also report
    per-type ergodic mass at the upper grid edge — signature of truncation."""
    A_sum = 0.0
    Y_sum = 0.0
    edge_masses = []
    for b_idx, agent in enumerate(typelist):
        tm_data = build_tm_agg_fiscal_a(agent, aCount=aCount, aMax=aMax,
                                         interpretation='CDC')
        ergodic = find_ergodic_distribution(tm_data['TranMatrix'])
        agg = compute_type_aggregates_tm_a(agent, tm_data, ergodic, interpretation='CDC')
        A_sum += pmv[b_idx] * agg['A_nrm']
        Y_sum += pmv[b_idx] * agg['Income_nrm']
        # Mass at the upper-most asset grid points (last 5%)
        n = len(ergodic)
        # Layout is (J, A) for J=4 micro-states, A=aCount; pull last 5% of A
        J = agent.MrkvArray[0].shape[0]
        erg_2d = np.asarray(ergodic).reshape(J, aCount)
        last_pct = int(0.05 * aCount)
        edge = float(erg_2d[:, -last_pct:].sum())
        edge_masses.append(edge)
    return A_sum / Y_sum, edge_masses


def main():
    print("=" * 72)
    print("L3c.b2 diagnostic: aMax sweep")
    print("=" * 72)

    print("\nBuilding 7 HS types...")
    t0 = time.time()
    typelist, pmv = build_HS_7type()
    print(f"  done in {time.time()-t0:.1f}s")

    print(f"\nMC reference (from L3c.b2 cascade): ~7.78 at large N")
    print(f"\naMax sweep at aCount=200:")
    print(f"  {'aMax':>6s}  {'TM K/Y':>10s}  {'rel_gap vs MC':>14s}  {'edge mass per type (last 5%)':<40s}")
    mc_ref = 7.78
    for aMax in [50, 100, 200, 500, 1000]:
        t0 = time.time()
        ky, edges = tm_KY_at_aMax(typelist, pmv, aMax=aMax, aCount=200)
        gap_pct = 100 * abs(ky - mc_ref) / mc_ref
        print(f"  {aMax:>6d}  {ky:>10.4f}  {gap_pct:>13.2f}%  {[f'{e:.3f}' for e in edges]}  ({time.time()-t0:.1f}s)")


if __name__ == "__main__":
    main()
