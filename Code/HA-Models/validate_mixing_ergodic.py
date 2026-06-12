#!/usr/bin/env python
"""validate_mixing_ergodic.py — end-to-end check (plan step 3): does the Alt-3 mixing grid
(tm_mixing_diagnostic.make_mixing_grid) actually CHANGE the computed ergodic / wealth tail / aMax,
or is the mixing fix purely a correctness guarantee?

Builds the COLLEGE most-patient (GIC-cap) atom's a-indexed ergodic on:
  (1) the PRODUCTION grid  make_grid_exp_mult(0, aMax, aCount, aFac=3)
  (2) the Alt-3 MIXING grid make_mixing_grid(..., target = 0.5*logrange_disc)
and compares E[a], the upper-tail quantiles, the (1-1e-4) aMax, and the SPECTRAL GAP
(1 - |lambda_2| of the column-stochastic TM) — the direct mixing-quality / conditioning metric.

The cap atom is used (not an estimated beta) because it is the most patient atom ANY cohort can
have → the fattest ergodic tail → where psi-mixing is most stressed (the BUG-053 region).

ANSWER (2026-06-10): mainly a CORRECTNESS guarantee, plus a modest tail refinement —
E[a] +0.45%, aMax 1123 -> 1096; the production grid's spectral gap is 0.011 >> 0, so the
production ergodic was NOT mixing-limited. See memory project_tm_mixing_ensure_connected.

    cd Code/HA-Models
    HAFISCAL_INTERPRETATION=ESC HAFISCAL_TM_AMAX=1300 \
      /home/shared/github/llorracc/HAFiscal-Latest/.venv/bin/python validate_mixing_ergodic.py
"""
import os
import sys

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

import tm_mixing_diagnostic as D

_HERE = os.path.dirname(os.path.abspath(__file__))
_FPC = os.path.join(_HERE, "FromPandemicCode")
if _FPC not in sys.path:
    sys.path.insert(0, _FPC)


def _build_cap_college_agent(interpretation="ESC"):
    """Most-patient (GIC-cap) college atom, solved — mirrors adaptive_grid_tm.college_top_ergodic
    with beta=1.01,nabla=0 (every discretized atom clips down to the GIC cap)."""
    _saved = sys.argv
    sys.argv = [sys.argv[0]]
    try:
        from HARK.distributions import Uniform, DiscreteDistribution
        import EstimParameters as ep
        from EstimParameters import (init_college, init_ADEconomy, DiscFacCount,
                                     minBeta, gic_capped_beta, UBspell_normal, PermShkStd)
        from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
    finally:
        sys.argv = _saved

    cap = gic_capped_beta(2, ep.theGICfactor)
    dfs = Uniform(1.01 - 0.0, 1.01 + 0.0).discretize(DiscFacCount)
    beta_top = float(np.clip(dfs.atoms[0], minBeta, cap).max())

    ag = AggFiscalType(**init_college); ag.cycles = 0
    eco = AggregateDemandEconomy(**init_ADEconomy); ag.get_economy_data(eco)
    Du = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnemp])])
    Dn = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnempNoBenefits])])
    ag.IncShkDstn = [[ag.IncShkDstn[0]] + [Du] * UBspell_normal + [Dn]]
    ag.IncShkDstn_base = ag.IncShkDstn
    ag.DiscFac = beta_top
    ag.AgentCount = 1
    ag.tm_a_indexed = True
    ag.interpretation = interpretation
    eco.agents = [ag]
    eco.solve()
    return ag, float(PermShkStd[0]), beta_top


def _aNrm_marginal(tm_data, ergodic, J):
    grid = np.asarray(tm_data["dist_aGrid"], dtype=float)
    A = len(grid)
    mass = np.asarray(ergodic, float).reshape(J, A).sum(axis=0)
    mass = mass / mass.sum()
    return grid, mass


def _spectral_gap(TranMatrix):
    """1 - |lambda_2| of the column-stochastic TM. lambda_1 = 1 (ergodic). A larger gap = stronger
    mixing / better-conditioned power iteration; gap -> 0 signals near-reducibility."""
    P = TranMatrix.tocsc() if sp.issparse(TranMatrix) else sp.csc_matrix(TranMatrix)
    N = P.shape[0]
    k = min(6, N - 2)
    try:
        vals = spla.eigs(P, k=k, which="LM", return_eigenvectors=False, maxiter=5000)
        mags = np.sort(np.abs(vals))[::-1]
        lam2 = float(mags[1]) if len(mags) > 1 else float("nan")
    except Exception:
        dense = P.toarray()
        mags = np.sort(np.abs(np.linalg.eigvals(dense)))[::-1]
        lam2 = float(mags[1])
    return 1.0 - lam2, lam2


def _quantile(grid, mass, q):
    cdf = np.cumsum(mass); cdf = cdf / cdf[-1]
    return float(np.interp(q, cdf, grid))


def main():
    interp = os.environ.get("HAFISCAL_INTERPRETATION", "ESC")
    aMax = float(os.environ.get("HAFISCAL_TM_AMAX", "1300"))
    aCount = int(os.environ.get("HAFISCAL_MIXING_ACOUNT", "200"))
    aFac = 3
    safety = float(os.environ.get("HAFISCAL_MIXING_SAFETY", "0.5"))

    from HARK.utilities import make_grid_exp_mult
    from tm_methods import build_tm_agg_fiscal_a, find_ergodic_distribution

    print(f"=== ensure-connected-TM end-to-end validation (interp={interp}, aMax={aMax}, "
          f"aCount={aCount}, aFac={aFac}, safety={safety}) ===")
    ag, perm_std, beta_top = _build_cap_college_agent(interp)
    J = ag.MrkvArray[0].shape[0]
    print(f"College cap atom beta_top={beta_top:.6f}, PermShkStd={perm_std:.4f}")

    logrange_disc, logrange_cont = D.shock_logrange(ag.IncShkDstn[0], perm_std)
    target = safety * logrange_disc

    grids = {
        "production (exp-mult)": make_grid_exp_mult(0.0, aMax, aCount, aFac),
        "Alt-3 mixing grid": D.make_mixing_grid(0.0, aMax, aCount, aFac, target, verbose=True),
    }

    rows = []
    for name, grid in grids.items():
        tm = build_tm_agg_fiscal_a(ag, dist_aGrid=grid, Cratio=1.0, interpretation=interp)
        erg = find_ergodic_distribution(tm["TranMatrix"])
        g, mass = _aNrm_marginal(tm, erg, J)
        gap, lam2 = _spectral_gap(tm["TranMatrix"])
        mean_a = float(np.sum(g * mass))
        rows.append(dict(
            name=name, n=len(g), mean_a=mean_a,
            q99=_quantile(g, mass, 0.99), q999=_quantile(g, mass, 0.999),
            q9999=_quantile(g, mass, 0.9999), aMax_need=_quantile(g, mass, 1 - 1e-4),
            edge_mass=float(mass[-1]), gap=gap, lam2=lam2,
        ))

    print("\n--- ergodic aNrm marginal (college cap atom) ---")
    hdr = (f"{'grid':22s} {'N':>4s} {'E[a]':>9s} {'q99':>8s} {'q99.9':>9s} "
           f"{'q99.99':>9s} {'edgeMass':>10s} {'1-|l2| gap':>11s}")
    print(hdr); print("-" * len(hdr))
    for r in rows:
        print(f"{r['name']:22s} {r['n']:4d} {r['mean_a']:9.4f} {r['q99']:8.2f} "
              f"{r['q999']:9.2f} {r['q9999']:9.2f} {r['edge_mass']:10.2e} {r['gap']:11.4e}")

    p, m = rows[0], rows[1]
    print("\n--- production vs mixing grid (relative change) ---")
    def _rel(a, b): return (b - a) / a if a else float("nan")
    print(f"  E[a]:        {p['mean_a']:.4f} -> {m['mean_a']:.4f}   ({_rel(p['mean_a'],m['mean_a'])*100:+.3f}%)")
    print(f"  q99.99:      {p['q9999']:.2f} -> {m['q9999']:.2f}   ({_rel(p['q9999'],m['q9999'])*100:+.3f}%)")
    print(f"  aMax(1-1e-4):{p['aMax_need']:.2f} -> {m['aMax_need']:.2f}")
    print(f"  spectral gap:{p['gap']:.4e} -> {m['gap']:.4e}   "
          f"({_rel(p['gap'],m['gap'])*100:+.1f}% mixing-quality change)")
    print(f"  top-edge mass:{p['edge_mass']:.2e} -> {m['edge_mass']:.2e}")


if __name__ == "__main__":
    main()
