#!/usr/bin/env python
"""Build + validate the ergodic joint P(a, j, pLvl) for the conditional-init fix.

Forward-iterates (a-grid x j x log-pLvl-grid) using the agent's cFunc and the standard
TM-a dynamics: m = (R/(PermGroFac[j']*psi))*a + xi ; c = cFunc[j'](m) ; a' = m - c ;
pLvl' = pLvl * PermGroFac[j'] * psi  (auto-frozen for unemployed: PermGroFac=1, psi=1).
Death -> newborn (employed, a~0, log-pLvl ~ N(pLogInitMean, pLogInitStd^2)).

DECISIVE VALIDATION: E[aNrm | pLvl-bucket] must reproduce the MC cross-section
(base t=0: -13%..+49%). That is the (a|pLvl) covariance the bucketed-5D drops.

OUTCOME (2026-06-09/10): the conditional-init fix path was NOT adopted — the
check_rec MC-vs-TM gap was diagnosed as the structural phi(pLvl) bucketing limit
(not an init artifact), and check_* welfare is MC-only per the 2026-06-10
unified-MC decision (conclusions_private/2026-06-10_welfare_method_unified_MC.md).
Kept as a diagnostic.
"""
import os, sys, time
import numpy as np
from copy import deepcopy
sys.argv = [sys.argv[0]]
sys.path.insert(0, os.getcwd())  # FromPandemicCode (build_and_solve, tm_methods)
from welfare6_scenario import build_and_solve
from tm_methods import compute_baseline_tm_data, compute_pLvl_distribution


def _bilin(vals, grid):
    n, G = len(vals), len(grid)
    i = np.clip(np.searchsorted(grid, vals) - 1, 0, G - 2)
    f = np.clip((vals - grid[i]) / (grid[i + 1] - grid[i]), 0.0, 1.0)
    W = np.zeros((n, G))
    W[np.arange(n), i] = 1 - f
    W[np.arange(n), i + 1] = f
    return W


def compute_ajpLvl_joint(agent, bd, n_plvl=120, n_iter=2500, tol=1e-12, verbose=True):
    aGrid = np.asarray(bd['dist_aGrid'], dtype=float)
    A = len(aGrid); J = int(agent.num_base_MrkvStates)
    M = np.asarray(agent.CondMrkvArrays[0], dtype=float)
    LivPrb = float(np.asarray(agent.LivPrb).reshape(-1)[0])
    PGF = np.asarray(agent.PermGroFac, dtype=float).reshape(-1)[:J]
    R = float(np.asarray(agent.Rfree).reshape(-1)[0])
    Splurge = float(getattr(agent, 'Splurge', 0.2571044750751492))
    cFuncs = agent.solution[0].cFunc
    incs = agent.IncShkDstn[0]
    pLvl_grid, _ = compute_pLvl_distribution(agent, n_points=n_plvl)
    logp = np.log(pLvl_grid); P = len(logp)
    pLogInitMean = float(getattr(agent, 'pLogInitMean', getattr(agent, 'pLvlInitMean', 0.0)))
    pLogInitStd = float(getattr(agent, 'pLogInitStd', getattr(agent, 'pLvlInitStd', 0.0)))
    ones = np.ones(A)

    trans = [[] for _ in range(J)]
    for jp in range(J):
        d = incs[jp]; at = np.asarray(d.atoms, dtype=float); pmv = np.asarray(d.pmv, dtype=float)
        psi, xi = at[0], at[1]; cf = cFuncs[jp]
        for k in range(len(pmv)):
            if pmv[k] <= 0:
                continue
            m = (R / (PGF[jp] * psi[k])) * aGrid + xi[k]
            try:
                cstar = np.asarray(cf(m, ones))
            except TypeError:
                cstar = np.asarray(cf(m))
            c = (1.0 - Splurge) * cstar + Splurge * xi[k]   # splurge (matches the 5-D kernel)
            a_next = np.clip(m - c, aGrid[0], aGrid[-1])
            A_map = _bilin(a_next, aGrid)
            P_map = _bilin(logp + np.log(PGF[jp] * psi[k]), logp)
            trans[jp].append((A_map, P_map, float(pmv[k])))

    if pLogInitStd > 1e-9:
        nb_p = np.exp(-0.5 * ((logp - pLogInitMean) / pLogInitStd) ** 2); nb_p /= nb_p.sum()
    else:
        nb_p = np.zeros(P); nb_p[int(np.clip(np.searchsorted(logp, pLogInitMean), 0, P - 1))] = 1.0

    dist = np.zeros((A, J, P)); dist[0, 0, :] = nb_p; dist /= dist.sum()
    t0 = time.time()
    for it in range(n_iter):
        nxt = np.zeros((A, J, P))
        for jp in range(J):
            inflow = np.zeros((A, P))
            for j in range(J):
                if M[j, jp] > 0:
                    inflow += M[j, jp] * dist[:, j, :]
            for A_map, P_map, w in trans[jp]:
                nxt[:, jp, :] += A_map.T @ (inflow * w) @ P_map
        nxt *= LivPrb
        nxt[0, 0, :] += (1.0 - LivPrb) * nb_p
        diff = float(np.max(np.abs(nxt - dist))); dist = nxt
        if diff < tol:
            break
    if verbose:
        print(f"  joint converged in {it+1} iters ({time.time()-t0:.1f}s), last diff={diff:.2e}", flush=True)
    dist /= dist.sum()
    return aGrid, pLvl_grid, dist


def main():
    ctx = build_and_solve('HS_Only')
    base = deepcopy(ctx['AggEco']); base.switch_shock_type('base'); base.solve()
    for ag in base.agents:
        ag.tm_a_indexed = True
    ag = base.agents[0]
    bd = compute_baseline_tm_data(base, mCount=50, neutral_measure=True)[0]
    print("computing (a,j,pLvl) joint...", flush=True)
    aGrid, pLvl_grid, joint = compute_ajpLvl_joint(ag, bd)
    A, J, P = joint.shape
    # marginal (a,j) sanity
    aj = joint.sum(2)            # [A, J]
    print(f"joint shape {joint.shape}; sum={joint.sum():.4f}; P(j)={np.round(aj.sum(0),4)}")
    Ea = np.dot(joint.sum((1, 2)), aGrid)
    aGrid_bd = np.asarray(bd['dist_aGrid'])
    bd_aj = np.asarray(bd['ergodic']).reshape(J, len(aGrid_bd))
    E_a_bd = np.dot(bd_aj.sum(0), aGrid_bd)
    print(f"DIAG E[aNrm]: joint={Ea:.3f}  bd/TM-a={E_a_bd:.3f}  MC=0.174  "
          f"-> joint {'~matches bd (TM-a vs MC gap)' if abs(Ea-E_a_bd)<0.03 else 'DIFFERS from bd (my dynamics bug)'}")
    cf0 = ag.solution[0].cFunc[0]; ms = np.array([0.2, 0.5, 1.0, 2.0, 5.0])
    try:
        cs = np.asarray(cf0(ms, np.ones(5)))
    except TypeError:
        cs = np.asarray(cf0(ms))
    print(f"DIAG cFunc[emp]({ms.tolist()}) = {np.round(cs,3).tolist()}  (a'=m-c at these m: {np.round(ms-cs,3).tolist()})")
    # (a|pLvl-bucket) -- the decisive check vs MC (-13%..+49%)
    pm = joint.sum((0, 1)); cum = np.cumsum(pm); nb = 20
    edges = np.linspace(0, 1, nb + 1)
    print("E[aNrm | pLvl-bucket] (low->high pLvl):")
    devs = []
    for b in range(nb):
        lo = np.searchsorted(cum, edges[b]); hi = np.searchsorted(cum, edges[b + 1])
        if lo >= hi:
            continue
        Pa = joint[:, :, lo:hi].sum((1, 2)); Pa = Pa / Pa.sum()
        ab = np.dot(Pa, aGrid); devs.append(100 * (ab / Ea - 1))
        if b < 5 or b >= nb - 3:
            print(f"  bucket {b:2d}: aNrm={ab:7.3f} ({100*(ab/Ea-1):+5.1f}%)")
    print(f"  range: {min(devs):+.1f}% .. {max(devs):+.1f}%   (MC was -13%..+49%)")
    ok = max(devs) - min(devs) > 20
    print(f"  => {'PASS (reproduces the (a|pLvl) covariance)' if ok else 'CHECK (too flat vs MC)'}")
    print("AJPLVL_BUILD_DONE")


if __name__ == "__main__":
    main()
