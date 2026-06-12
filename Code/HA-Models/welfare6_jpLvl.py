#!/usr/bin/env python
"""Analytical ergodic joint P(j, pLvl) for the conditional-init fix (no MC).

The bucketed-5D inits every pLvl bucket from the MARGINAL (a,j) ergodic, dropping the
(j|pLvl) correlation. That correlation is the unemployment-pLvl-freeze (BUG-040:
unemployed -> PermShk=1, pLvl frozen), so currently-unemployed agents carry lower pLvl.
We recover P(j | pLvl-bucket) from the ergodic joint (j, pLvl), built by forward-
iterating the (j x log-pLvl) Markov: employment via the micro Markov; pLvl grows
(x G x psi) when the destination micro state is EMPLOYED (index 0), frozen otherwise;
death -> rebirth at the initial pLvl. Marginal-over-j reproduces compute_pLvl_distribution
(mean-field), and E[pLvl|unemployed] comes out ~3-7% below marginal (the documented gap).

OUTCOME (2026-06-09/10): the conditional-init fix path was NOT adopted — the
check_rec MC-vs-TM gap was diagnosed as the structural phi(pLvl) bucketing limit
(not an init artifact), and check_* welfare is MC-only per the 2026-06-10
unified-MC decision (conclusions_private/2026-06-10_welfare_method_unified_MC.md).
Kept as a diagnostic.
"""
import numpy as np
from tm_methods import compute_pLvl_distribution

_EMPLOYED = 0  # micro state index 0 = employed (1..J-1 = unemployment durations/noBen)


def _employed_growth_and_shock(agent):
    """(G_employed, psi_atoms, psi_pmv) for the employed micro state.
    NOTE: row index of the permanent shock inside atoms is confirmed by inspection."""
    G = float(np.asarray(agent.PermGroFac).reshape(-1)[_EMPLOYED])
    d = agent.IncShkDstn[0][_EMPLOYED]
    atoms = np.asarray(d.atoms, dtype=float)
    psi = atoms[0]                       # row 0 = permanent shock (confirm vs inspection)
    pmv = np.asarray(d.pmv, dtype=float)
    return G, psi, pmv


def compute_jpLvl_joint(agent, n_plvl=300, unemployment_rate=None, n_iter=6000, tol=1e-13):
    """Ergodic joint. Returns (pLvl_grid[n_plvl], joint[J, n_plvl]) with sum==1."""
    J = int(agent.num_base_MrkvStates)
    M = np.asarray(agent.CondMrkvArrays[0], dtype=float)
    assert M.shape == (J, J), f"micro Markov {M.shape} != ({J},{J})"
    LivPrb = float(np.asarray(agent.LivPrb).reshape(-1)[0])
    G, psi, pmv = _employed_growth_and_shock(agent)

    pLvl_grid, _ = compute_pLvl_distribution(agent, n_points=n_plvl,
                                             unemployment_rate=unemployment_rate)
    logp = np.log(pLvl_grid)
    P = len(logp)

    pLogInitMean = float(getattr(agent, 'pLogInitMean',
                                 getattr(agent, 'pLvlInitMean', 0.0)))

    # Employed pLvl-growth operator: new[p'] = sum_psi pmv * dist[p' - (logG + log psi)]
    shifts = np.log(G) + np.log(psi)

    def grow(col):
        out = np.zeros(P)
        for s, w in zip(shifts, pmv):
            out += w * np.interp(logp - s, logp, col, left=0.0, right=0.0)
        return out

    # Newborn distribution (enters EMPLOYED; log-pLvl ~ N(pLogInitMean, pLogInitStd^2)).
    pLogInitStd = float(getattr(agent, 'pLogInitStd', getattr(agent, 'pLvlInitStd', 0.0)))
    if pLogInitStd > 1e-9:
        nb_dist = np.exp(-0.5 * ((logp - pLogInitMean) / pLogInitStd) ** 2)
    else:
        nb_dist = np.zeros(P)
        nb_dist[int(np.clip(np.searchsorted(logp, pLogInitMean), 0, P - 1))] = 1.0
    nb_dist = nb_dist / nb_dist.sum()

    dist = np.zeros((J, P))
    dist[_EMPLOYED] = 1.0 / P            # uniform start; ergodic is start-independent
    last = None
    for _ in range(n_iter):
        nxt = np.zeros((J, P))
        for j in range(J):
            dj = dist[j]
            if dj.sum() <= 0:
                continue
            for jp in range(J):
                if M[j, jp] <= 0:
                    continue
                m = M[j, jp] * dj
                nxt[jp] += grow(m) if jp == _EMPLOYED else m
        nxt *= LivPrb
        nxt[_EMPLOYED] += (1.0 - LivPrb) * nb_dist
        if last is not None and np.max(np.abs(nxt - last)) < tol:
            dist = nxt
            break
        last = dist
        dist = nxt
    dist /= dist.sum()
    return pLvl_grid, dist


def conditional_j_given_bucket(agent, n_buckets, n_plvl=300, unemployment_rate=None):
    """List (len n_buckets) of P(j | bucket) arrays [J], bucketed by the SAME
    pLvl-quantile edges _compute_check_buckets uses (the compute_pLvl_distribution
    marginal), so it aligns one-to-one with the check buckets."""
    pLvl_grid, joint = compute_jpLvl_joint(agent, n_plvl=n_plvl,
                                           unemployment_rate=unemployment_rate)
    _, marg_ref = compute_pLvl_distribution(agent, n_points=n_plvl,
                                            unemployment_rate=unemployment_rate)
    cum = np.cumsum(marg_ref)
    edges = np.linspace(0.0, 1.0, n_buckets + 1)
    out = []
    for b in range(n_buckets):
        lo = int(np.searchsorted(cum, edges[b]))
        hi = int(np.searchsorted(cum, edges[b + 1]))
        if lo >= hi:
            continue
        mass_j = joint[:, lo:hi].sum(1)
        out.append(mass_j / mass_j.sum())
    return out
