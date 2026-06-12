"""
Single source of truth helpers for HAFiscal income process (per-micro-state growth
and unemployment shock structure). See history/20260403-sst-permgrofac-income-process-plan.md.

Outer-product unemployed distributions use independent marginals from the employed
IncShkDstn (correlation in the employed joint grid is not preserved).
"""

from __future__ import annotations

import numpy as np
from HARK.distributions import DiscreteDistribution


def build_PermGroFac_micro(G_employed, num_base_MrkvStates, G_unemployed=1.0):
    """Per-micro-state permanent income growth: j=0 employed, j>0 unemployed."""
    n = int(num_base_MrkvStates)
    if n < 1:
        raise ValueError("num_base_MrkvStates must be >= 1")
    return [float(G_employed)] + [float(G_unemployed)] * (n - 1)


def tile_PermGroFac_composite(PermGroFac_base, PermGroFac_unemp, num_mrkv_states, num_base_MrkvStates):
    """Full PermGroFac for composite Markov states; employed when j % nb == 0."""
    G_emp = float(np.asarray(PermGroFac_base).ravel()[0])
    G_u = float(PermGroFac_unemp)
    nb = int(num_base_MrkvStates)
    n = int(num_mrkv_states)
    return np.array([G_emp if (j % nb) == 0 else G_u for j in range(n)], dtype=np.float64)


def effective_pLvl_growth(agent, unemployment_rate=None):
    """g = (1-u)*G_emp + u*G_unemp from agent.PermGroFac[0] (SST)."""
    pgf = np.asarray(agent.PermGroFac[0], dtype=float)
    G_emp = float(pgf[0])
    if unemployment_rate is None:
        return G_emp
    u = float(unemployment_rate)
    G_unemp = float(pgf[0]) if len(pgf) < 2 else float(pgf[1])
    return (1.0 - u) * G_emp + u * G_unemp


def effective_perm_shock_variance_periods(ages, agent, unemployment_rate=None):
    """
    Expected number of i.i.d. employed permanent-shock draws accumulated so far.

    First argument is **not** HARK ``state_now.t_age``: it is the count of
    stochastic shock draws (cohort index ``k`` in ``compute_pLvl_distribution``,
    where ``t_age = k + 1`` and the newborn's first growth step has no perm
    shock — BUG-003). For TM/MC initialization from ``t_age``, use
    ``effective_perm_shock_periods_for_t_age`` instead of passing ``t_age``
    here directly.

    When ``perm_shocks_during_unemployment`` is false, scales by ``(1-u)`` per
    period (unemployed periods contribute no perm-shock variance).
    """
    ages = np.asarray(ages, dtype=float)
    if getattr(agent, "perm_shocks_during_unemployment", False):
        return ages
    u = unemployment_rate
    if u is None:
        u = float(getattr(agent, "Urate_normal", 0.0))
    return (1.0 - float(u)) * ages


def effective_perm_shock_periods_for_t_age(t_age, agent, unemployment_rate=None):
    """
    Map HARK ``state_now.t_age`` (1..T_age) to shock-draw count for synthetic ``pLvl``.

    Aligns TM-init and ``compute_pLvl_distribution``: cohort ``k = t_age - 1`` has
    had ``k`` stochastic permanent shocks after BUG-003 (first growth step is
    deterministic).
    """
    t_age = np.asarray(t_age, dtype=float)
    return effective_perm_shock_variance_periods(
        np.maximum(t_age - 1.0, 0.0), agent, unemployment_rate
    )


def _marginal_atom(dstn, axis: int):
    atoms = np.asarray(dstn.atoms[axis], dtype=float).ravel()
    pmv = np.asarray(dstn.pmv, dtype=float).ravel()
    acc = {}
    for a, p in zip(atoms, pmv):
        acc[a] = acc.get(a, 0.0) + p
    keys = np.array(sorted(acc.keys()), dtype=float)
    vals = np.array([acc[k] for k in keys], dtype=float)
    s = vals.sum()
    if s > 0:
        vals /= s
    return keys, vals


def build_unemployed_inc_shk_dstn(
    employed_dstn,
    inc_unemp_level,
    perm_shocks_during_unemployment: bool,
    tran_shocks_during_unemployment: bool,
):
    """Unemployed IncShkDstn from SST flags (independent outer product if both True)."""
    p_on = bool(perm_shocks_during_unemployment)
    t_on = bool(tran_shocks_during_unemployment)

    if not p_on and not t_on:
        return DiscreteDistribution(
            np.array([1.0]),
            [np.array([1.0]), np.array([float(inc_unemp_level)])],
        )

    if p_on and not t_on:
        a0, p0 = _marginal_atom(employed_dstn, 0)
        a1 = np.full_like(a0, float(inc_unemp_level), dtype=float)
        return DiscreteDistribution(p0, [a0, a1])

    if not p_on and t_on:
        a1, p1 = _marginal_atom(employed_dstn, 1)
        a0 = np.ones_like(a1, dtype=float)
        return DiscreteDistribution(p1, [a0, a1])

    a0, p0 = _marginal_atom(employed_dstn, 0)
    a1, p1 = _marginal_atom(employed_dstn, 1)
    joint_p = np.outer(p0, p1).ravel()
    joint_a0 = np.repeat(a0, len(a1))
    joint_a1 = np.tile(a1, len(a0))
    return DiscreteDistribution(joint_p, [joint_a0, joint_a1])
