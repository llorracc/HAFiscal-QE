#!/usr/bin/env python
"""tm_mixing_diagnostic.py — ensure the discretized transition matrix MIXES (is irreducible /
strongly connected on the asset grid), so its computed ergodic is the unique, faithful
approximation of the continuous model's stationary distribution rather than a grid artifact.

THE MIXING MECHANISM
--------------------
In the normalized model the next-period market-resources recursion (exactly as built in
tm_methods._build_period_tm) is

    mNext = Rfree * aPol[j,i] / (psi * Gamma_j) + xi          # psi = perm shock, xi = tran shock

so the PERMANENT shock psi enters as the normalized return Rfree/(Gamma*psi) on end-of-period
assets aPol: mNext is strictly DECREASING in psi. For a fixed source m-node i the spread of psi
"fans out" mNext across a band of dist_mGrid nodes — this fan-out is what connects adjacent grid
cells. If, after the grid-assignment step, the largest psi (and everything above the median) lands
on the SAME node as the median psi (and likewise the smallest psi on the high-m side), that row of
the TM is a near-point-mass: the continuous problem mixes but the DISCRETIZATION has destroyed it.

WHY IT MATTERS (the math)
-------------------------
The ergodic is the unit-eigenvalue left eigenvector of the stochastic matrix P (pi P = pi). A unique
pi (and a well-posed power iteration) requires P irreducible (its directed graph strongly connected)
and aperiodic — Perron-Frobenius. The shock fan-out supplies the off-diagonal edges; systematic
collapse fragments P into non-communicating classes -> reducible -> pi non-unique / initial-condition
dependent / an artifact. Short of reducibility, weak fan-out drives the spectral gap -> 0, so pi
becomes ill-conditioned and hypersensitive to node placement. "Ensure mixing" = guarantee enough
cell-to-cell connectivity that P is irreducible with a real spectral gap, PRESERVING the continuous
model's mixing under discretization.

TWO-LEVEL CHECK (the atoms are interior to [inf, sup])
------------------------------------------------------
(A) CONTINUOUS (bounded): the inf and sup of the truncated psi must reach nodes ADJACENT to, and not
    identical to, the median-psi node -> the true bounded model has local connectivity.
(B) DISCRETIZED: the MIN and MAX atoms of the discretized psi must reach nodes DIFFERENT from the
    median atom's node -> the COMPUTED TM actually mixes. (B) is the binding one (the extreme atoms
    sit strictly inside [inf, sup], so their fan-out is smaller and collapses first). (A) passes but
    (B) fails => shock discretization too coarse (Alt 1: more psi atoms); (A) fails => asset grid too
    coarse at that node (refine, or Alt 3: design the spacing).

METHODIZATION PARAMETERIZATION
------------------------------
Parameters that govern the numerical METHOD (the discretization), not the economics. Here:
  - SIGMA_BOUND (k): truncation radius of the permanent shock, in std-devs of log psi. Defining
    inf/sup of psi REQUIRES a bounded shock; we recharacterize the true (lognormal) permanent shock
    as truncated at +/- k sigma. Tradeoff: tighter k = cleaner inf/sup but more discarded tail mass.
  - the m-grid (aCount / aMax / aFac), and the shock atom counts (N_perm, N_tran).

ALT-3 CLOSED FORM (design the grid, don't patch it)
---------------------------------------------------
In the psi-dominated region mNext ~ Rfree*aPol/(Gamma*psi), so log(mNext) shifts by -log(psi): the
fan-out's LOG-width is just log(psi_max/psi_min). For psi truncated at k sigma that is 2*k*sigma_psi.
Hence on a log-spaced grid the mixing requirement is simply

    Delta_log(grid)  <  2*k*sigma_psi          (continuous, condition A)
    Delta_log(grid)  <  log(psi_max_atom/psi_min_atom)   (discretized, condition B — binding)

so the grid's local log-spacing must be finer than the shock's log-range. This module reports both
the per-node empirical check AND this closed-form criterion.

CAVEAT: near the constraint mNext is dominated by the additive transitory shock xi (psi's fan-out
~ Rfree*aPol/Gamma * Delta(1/psi) -> 0 as aPol -> 0), so NO grid is fine enough there — but mixing is
then supplied by xi, not psi. The psi diagnostic is therefore gated to states/regions where psi is
the operative mixer (employed Markov states with Var[psi] > 0).
"""
from __future__ import annotations

import os
import sys
import numpy as np

# ---- METHODIZATION PARAMETERS (numerical method, not economics) ----
SIGMA_BOUND = float(os.environ.get("HAFISCAL_MIXING_SIGMA_BOUND", "3.0"))  # truncate perm shock at k sigma
COLLAPSE_GAP = 1  # a fan-out endpoint "reaches a different node" iff its cell index differs by >= this
# aPol below this is treated as the constraint region, where psi's fan-out ~ Rfree*aPol/Gamma*Delta(1/psi)
# vanishes and mixing is supplied by the transitory shock, not psi. Collapses there are EXPECTED, not
# failures; the headline counts only psi-operative collapses (aPol > APOL_CONSTRAINT_TOL).
APOL_CONSTRAINT_TOL = float(os.environ.get("HAFISCAL_MIXING_APOL_TOL", "0.05"))


def bounded_perm_shock_bounds(perm_std, k=SIGMA_BOUND):
    """inf/sup of a mean-1 lognormal permanent shock truncated at +/- k std-devs of log psi.

    log psi ~ N(-sigma^2/2, sigma^2)  (so E[psi]=1); truncate log psi to [-sigma^2/2 +/- k sigma].
    Returns (psi_inf, psi_med, psi_sup). The log-range sup/inf is exactly 2*k*sigma (Alt-3 criterion).
    """
    s = float(perm_std)
    mu = -0.5 * s * s
    psi_inf = float(np.exp(mu - k * s))
    psi_med = float(np.exp(mu))          # median of the (truncated, symmetric-in-log) shock
    psi_sup = float(np.exp(mu + k * s))
    return psi_inf, psi_med, psi_sup


def shock_logrange(IncShkDstn_list, perm_std, k=SIGMA_BOUND):
    """The two Alt-3 shock log-ranges, picking the FIRST psi-mixing Markov state:
      logrange_disc = log(psi_max_atom / psi_min_atom)   (discretized, BINDING)
      logrange_cont = 2*k*sigma_psi                      (continuous, looser)
    Returns (logrange_disc, logrange_cont). The grid's local log-spacing must stay below
    logrange_disc for the COMPUTED TM to mix (condition B); below logrange_cont for the bounded
    continuous model to mix (condition A). Raises if no state has a non-degenerate psi.
    """
    _, logrange_cont = None, float(2.0 * k * float(perm_std))
    for j in range(len(IncShkDstn_list)):
        psi_atoms, _ = extract_employed_shock_psi(IncShkDstn_list[j])
        if len(psi_atoms) >= 2 and np.ptp(psi_atoms) > 1e-9:
            logrange_disc = float(np.log(psi_atoms[-1] / psi_atoms[0]))
            return logrange_disc, logrange_cont
    raise ValueError("no Markov state has a non-degenerate permanent shock")


def max_operative_dlog(aMin, aMax, aCount, aFac, m_gate):
    """Max local log-spacing of the exp-mult base grid over the psi-OPERATIVE region — the binding
    quantity for connectivity. Operative = lower node m > m_gate (the additive<->multiplicative
    crossover xi*G/R; below it xi mixes, not psi) AND upper node < aMax (the top interval is
    boundary-excused: no grid above aMax). Grid-only (no solve); m_gate is a valid lower bound on the
    operative m since aPol < m => aPol > xi*G/R requires m > xi*G/R."""
    from HARK.utilities import make_grid_exp_mult
    g = make_grid_exp_mult(aMin, aMax, aCount, aFac)
    lo, hi = g[:-1], g[1:]
    mask = (lo > m_gate) & (hi < aMax)
    if not mask.any():
        return 0.0
    return float(np.max(np.log(hi[mask] / lo[mask])))


def min_aCount_for_mixing(aMin, aMax, aFac, logrange_disc, m_gate, safety=2.0,
                          search_lo=8, search_hi=20000):
    """Smallest exp-mult aCount whose BASE grid is connected in the psi-operative region with a
    `safety`-fold margin, i.e. max_operative_dlog <= logrange_disc / safety. This is the principled
    floor: at safety=1 it is the GUARANTEE threshold (largest aCount-1 below it has a tail interval
    wider than the shock fan-out => connectivity becomes alignment-dependent); safety>1 ("substantially
    greater") keeps the coarsest operative spacing a factor `safety` below the shock log-range so a row
    can never collapse to a point mass regardless of alignment. max_operative_dlog is monotone
    decreasing in aCount, so a simple bisection finds the threshold. Returns an int aCount."""
    target = float(logrange_disc) / float(safety)
    if max_operative_dlog(aMin, aMax, search_hi, aFac, m_gate) > target:
        return int(search_hi)  # even the cap is too coarse (pathological) -> report the cap
    lo, hi = int(search_lo), int(search_hi)
    while lo < hi:
        mid = (lo + hi) // 2
        if max_operative_dlog(aMin, aMax, mid, aFac, m_gate) <= target:
            hi = mid
        else:
            lo = mid + 1
    return int(lo)


def make_aprime_lo(agent, xi_rep=None, state=0):
    """Build the worst-case downward asset map a'_lo(a) for the agent's employed Markov `state`:
    the LOWEST next-period end-of-period asset reachable from end-of-period asset a, via the largest
    permanent shock (psi_max gives the lowest m') at representative transitory xi. Returns
    (aprime_lo_fn, scalars). Used by make_fanout_grid; the agent must be solved."""
    R = float(agent.Rfree[state]); G = float(agent.PermGroFac[0][state])
    psi_atoms, _ = extract_employed_shock_psi(agent.IncShkDstn[0][state])
    psi_max = float(psi_atoms[-1]); psi_min = float(psi_atoms[0])
    if xi_rep is None:
        atoms = agent.IncShkDstn[0][state].atoms; pmv = agent.IncShkDstn[0][state].pmv
        xi_rep = float(np.sum(atoms[1] * pmv) / np.sum(pmv))   # E[xi] employed
    cE = agent.solution[0].cFunc[state]

    def aprime(a, psi):
        m = R * a / (G * psi) + xi_rep
        return float(m - cE(np.array([m]), np.array([1.0]))[0])

    def aprime_lo(a):
        return aprime(a, psi_max)

    return aprime_lo, dict(R=R, G=G, psi_max=psi_max, psi_min=psi_min, xi_rep=xi_rep,
                           aprime=aprime, a_gate=xi_rep * G / R)


def make_fanout_grid(aprime_lo_fn, aMax, a_handoff, s=2, n_lo=30, aFac=3, aMin=0.0,
                     max_steps=200000, verbose=False):
    """Top-down FAN-OUT-MATCHED aNrm grid (user, 2026-06-09). Build the asset grid DOWNWARD from aMax
    (the most-patient college agent's required max), stepping by 1/s of the worst-case downward asset
    reach a'_lo(a), so the psi-fan-out from EVERY node spans `s` grid points => >= s downward grid
    cells accessible (no node can get stuck; s-fold connectivity robustness by construction).

      a[0] = aMax
      a[k+1] = a[k] * ( a'_lo(a[k]) / a[k] )^(1/s)        # geometric, 1/s of the down-fan-out
      stop when a <= a_handoff  OR  a'_lo(a) >= a (worst-case down-drift reverses near the constraint)

    Below a_handoff the psi reach vanishes / reverses and xi supplies mixing, so [aMin, a_handoff] is
    filled with the existing dense exp-mult packing (n_lo points). aCount is an OUTPUT (~ s *
    log(aMax/a_handoff)/logrange + n_lo), not a guessed input. Returns the sorted unique grid."""
    from HARK.utilities import make_grid_exp_mult
    pts = [float(aMax)]; a = float(aMax)
    for _ in range(max_steps):
        if a <= a_handoff:
            break
        f = aprime_lo_fn(a) / a
        if f >= 1.0:                       # worst-case asset down-drift reversed -> stop the leg
            break
        anext = a * f ** (1.0 / s)
        if anext >= a - 1e-12:
            break
        pts.append(anext); a = anext
    tail = np.array(pts)
    lo = make_grid_exp_mult(aMin, a_handoff, n_lo, aFac)
    grid = np.unique(np.concatenate([tail, lo]))
    if verbose:
        print(f"[make_fanout_grid] s={s} a_handoff={a_handoff} aMax={aMax} -> aCount={len(grid)} "
              f"(fan-out tail={len(tail)}, near-0 packing={n_lo})", flush=True)
    return grid


def make_worstcase_landings(agent, emp_state=0):
    """JOINT-SHOCK worst-case downward landings (user, 2026-06-09). The two binding income realizations
    that push next-period normalized assets DOWN differ by region; this returns BOTH region anchors as
    actual (not conservatively-paired) realizations, so the grid constructor can resolve whichever binds:

      PERMANENT channel (binds in the TAIL): the two largest employed permanent shocks psi_max, psi_2
        shrink normalized assets via the rising-permanent-income denominator; at representative theta.
      BENEFIT-CLIFF channel (binds in LOW WEALTH): the two unemployment income levels — IncUnemp
        (a UI-benefit spell) and IncUnempNoBenefits (benefits exhausted, the lowest theta | unemployed),
        each at psi=1 (no permanent risk while unemployed), with that state's OWN cFunc.

    Returns (landings_fn, scalars). landings_fn(a) -> dict {P1,P2,U1,U2} of next-period end-of-period
    assets a' = m' - c(m'); the constructor takes the two deepest below a. Agent must be solved."""
    J = agent.MrkvArray[0].shape[0]
    R0 = float(agent.Rfree[emp_state]); G0 = float(agent.PermGroFac[0][emp_state])
    psi_atoms, _ = extract_employed_shock_psi(agent.IncShkDstn[0][emp_state])
    psi_max = float(psi_atoms[-1]); psi_2 = float(psi_atoms[-2])
    eatoms = agent.IncShkDstn[0][emp_state].atoms; epmv = agent.IncShkDstn[0][emp_state].pmv
    theta_bar = float(np.sum(eatoms[1] * epmv) / np.sum(epmv))
    cE = agent.solution[0].cFunc[emp_state]

    # unemployment states = degenerate-psi states; benefits = highest theta, nobenefits = lowest
    unemp = []
    for j in range(J):
        if j == emp_state:
            continue
        pa, _ = extract_employed_shock_psi(agent.IncShkDstn[0][j])
        if len(pa) >= 2 and np.ptp(pa) > 1e-9:
            continue  # another employed-like state
        tr = np.asarray(agent.IncShkDstn[0][j].atoms[1]); pm = np.asarray(agent.IncShkDstn[0][j].pmv)
        unemp.append((j, float(np.sum(tr * pm) / np.sum(pm))))
    if len(unemp) < 2:
        raise ValueError("need >=2 unemployment income states (benefits + no-benefits)")
    unemp.sort(key=lambda x: x[1])
    (j_nob, th_nob), (j_ben, th_ben) = unemp[0], unemp[-1]
    cU_ben = agent.solution[0].cFunc[j_ben]; cU_nob = agent.solution[0].cFunc[j_nob]
    Rb, Gb = float(agent.Rfree[j_ben]), float(agent.PermGroFac[0][j_ben])
    Rn, Gn = float(agent.Rfree[j_nob]), float(agent.PermGroFac[0][j_nob])

    def _ap(a, R, G, psi, theta, cF):
        m = R * a / (G * psi) + theta
        return float(m - cF(np.array([m]), np.array([1.0]))[0])

    def landings(a):
        return {
            "P1": _ap(a, R0, G0, psi_max, theta_bar, cE),   # deepest permanent (psi_max)
            "P2": _ap(a, R0, G0, psi_2, theta_bar, cE),     # 2nd permanent (psi_2)
            "U1": _ap(a, Rn, Gn, 1.0, th_nob, cU_nob),      # unemployment no benefits (deepest income)
            "U2": _ap(a, Rb, Gb, 1.0, th_ben, cU_ben),      # unemployment with benefits
        }

    sc = dict(psi_max=psi_max, psi_2=psi_2, theta_bar=theta_bar, th_benefits=th_ben,
              th_nobenefits=th_nob, j_benefits=j_ben, j_nobenefits=j_nob)
    return landings, sc


def make_fanout_grid_jointshock(landings_fn, aMax, a_min=0.05, n_lin=4, max_steps=200000, verbose=False):
    """Top-down JOINT-SHOCK fan-out grid (user synthesis, 2026-06-09). Step DOWN from aMax to the
    SECOND-deepest worst-case downward landing at each node, so the deepest + second-deepest landings
    occupy two distinct lower cells => >=2 accessible downward gridpoints by construction, region-aware:
    the permanent channel (psi_max, psi_2) binds in the tail, the benefit cliff (IncUnemp,
    IncUnempNoBenefits) binds in low wealth, and whichever gives the two deepest sub-node landings sets
    the local spacing. Stop when <2 landings lie strictly below the node (no further downward structure)
    or a<=a_min; cap with n_lin linear points down to 0. aCount is an OUTPUT."""
    pts = [float(aMax)]; a = float(aMax)
    for _ in range(max_steps):
        if a <= a_min:
            break
        below = sorted(v for v in landings_fn(a).values() if v < a - 1e-12)
        if len(below) < 2:
            break
        anext = below[1]                # the SECOND-deepest landing (shallower of the two deepest)
        if anext >= a - 1e-12:
            break
        pts.append(anext); a = anext
    pts = np.array(sorted(pts))
    if pts[0] > 1e-9:                   # cap the bottom with a few linear points to 0
        pts = np.concatenate([np.linspace(0.0, pts[0], n_lin + 1)[:-1], pts])
    grid = np.unique(pts)
    if verbose:
        print(f"[make_fanout_grid_jointshock] aMax={aMax} a_min={a_min} -> aCount={len(grid)}", flush=True)
    return grid


def joint_downward_report(grid, agent, emp_state=0, verbose=True):
    """Faithful joint-shock connectivity check: for each node, count DISTINCT grid cells strictly below
    it that the worst-case landings {P1,P2,U1,U2} reach. Reports nodes with <2 (the robustness target),
    skipping nodes from which fewer than 2 landings go down at all (no downward structure -> xi/Markov
    handles them; e.g. very low wealth where even the worst draw can't go lower)."""
    grid = np.asarray(grid, float); M = len(grid)
    landings, sc = make_worstcase_landings(agent, emp_state=emp_state)

    def cell(v):
        return int(np.clip(np.searchsorted(grid, v, side="right") - 1, 0, M - 2))

    nbad = 0; n_checked = 0; min_cells = 10 ** 9
    for i, a in enumerate(grid):
        below = [v for v in landings(a).values() if v < a - 1e-12]
        if len(below) < 2 or i < 2:
            continue   # no downward structure here, or boundary-excused bottom nodes
        n_checked += 1
        distinct = len({cell(v) for v in below if cell(v) < i})
        min_cells = min(min_cells, distinct)
        if distinct < 2:
            nbad += 1
    if verbose:
        print(f"   joint-shock downward: {n_checked} checked nodes; min distinct downward cells="
              f"{min_cells if min_cells < 10**9 else 'n/a'}; nodes with <2 downward cells={nbad}",
              flush=True)
    return dict(n_checked=n_checked, nbad=nbad, min_cells=int(min_cells) if min_cells < 10**9 else None)


def downward_cells_report(grid, agent, s, a_floor=None, state=0, xi_rep=None, verbose=True):
    """Faithful a-indexed connectivity check: for each FAN-OUT-region a-grid node, count how many grid
    cells STRICTLY BELOW it receive mass from the psi-fan-out (lowest reach a'(psi_max) .. a node).
    Reports nodes with < s such downward cells (the robustness target). Also reports upward cells via
    a'(psi_min). Boundary-excuses nodes within s cells of the grid bottom.

    a_floor bounds the fan-out region from below (default = a_handoff if known, else the additive<->
    multiplicative crossover xi*G/R). The s-downward guarantee applies only ABOVE it: below, the
    worst-case psi down-reach a'(psi_max) shrinks toward the income-floor fixed point (a'_lo(a)->a), so
    no grid fits s cells in it and xi supplies mixing there instead. Nodes with a'_lo(a) >= a (worst
    psi cannot push down at all) are always skipped."""
    grid = np.asarray(grid, float); M = len(grid)
    aprime_lo, sc = make_aprime_lo(agent, xi_rep=xi_rep, state=state)
    aprime = sc["aprime"]; pmin, pmax = sc["psi_min"], sc["psi_max"]; tol = sc["a_gate"]
    if a_floor is None:
        a_floor = tol

    def cell(v):
        return int(np.clip(np.searchsorted(grid, v, side="right") - 1, 0, M - 2))

    nbad_dn = 0; nbad_up = 0; n_op = 0; min_dn = 10 ** 9
    for i, a in enumerate(grid):
        if a <= a_floor:
            continue
        a_lo = aprime(a, pmax)           # lowest a' (worst-case psi)
        if a_lo >= a:
            continue   # worst-case psi does NOT push assets down here (income floor dominates) ->
                       # psi is not the downward mixer; xi handles it. Not a fan-out-region node.
        n_op += 1
        c_lo = cell(a_lo)                # lowest a' -> low index
        c_hi = cell(aprime(a, pmin))     # highest a' -> high index
        dn = i - c_lo                    # grid cells strictly below node i that the fan-out reaches
        up = c_hi - i
        if i >= s:                       # boundary-excuse only the bottom s nodes
            min_dn = min(min_dn, dn)
            if dn < s:
                nbad_dn += 1
        if up < s and i < M - 1 - s:
            nbad_up += 1
    if verbose:
        print(f"   a-indexed connectivity: {n_op} operative nodes; min downward cells={min_dn}; "
              f"nodes with <{s} downward cells={nbad_dn}; with <{s} upward cells={nbad_up}", flush=True)
    return dict(n_operative=n_op, nbad_downward=nbad_dn, nbad_upward=nbad_up, min_downward=int(min_dn))


def refine_grid_for_mixing(base_grid, logspacing_target, m_floor=None):
    """Alt-3 core: subdivide tail intervals of `base_grid` so every interval with lower endpoint
    >= m_floor has local log-spacing <= `logspacing_target`. Pure (grid in, refined grid out); the
    canonical implementation shared by make_mixing_grid (diagnostic) and the production TM-a build.

    For each adjacent interval [g[i], g[i+1]] with g[i] >= m_floor and log(g[i+1]/g[i]) > target,
    insert geometrically-spaced interior nodes so each sub-interval has log-spacing <= target
    (geometric => uniform-in-log => each piece = logrange/n_sub; n_sub = ceil(logrange/target)).
    Union + sort + unique. The lower region (below m_floor / non-positive) is left bit-identical.
    Returns (refined_grid, n_added).
    """
    if m_floor is None:
        m_floor = APOL_CONSTRAINT_TOL
    base = np.asarray(base_grid, dtype=float)
    target = float(logspacing_target)
    pieces = [base]
    n_added = 0
    for i in range(len(base) - 1):
        lo, hi = float(base[i]), float(base[i + 1])
        if lo < m_floor or lo <= 0.0:
            continue
        lr = np.log(hi / lo)
        if lr <= target:
            continue
        n_sub = int(np.ceil(lr / target))           # number of equal-log sub-intervals
        interior = lo * np.exp(np.linspace(0.0, lr, n_sub + 1)[1:-1])  # exclude endpoints (in base)
        pieces.append(interior)
        n_added += len(interior)
    return np.unique(np.concatenate(pieces)), n_added


def mixing_logspacing_target(IncShkDstn_list, perm_std=None, safety=None):
    """The production mixing log-spacing target = safety * log(psi_max_atom/psi_min_atom) (the BINDING
    discretized criterion). safety defaults to HAFISCAL_MIXING_SAFETY (1.0): at safety=1 the criterion
    is Delta_log(grid) < the FULL min->max atom log-range, which guarantees the extreme atoms straddle
    >=1 cell boundary (the row is not a point mass) for ANY alignment — the MODEST goal (one
    off-diagonal edge per psi-operative row = irreducibility), NOT two-sided per-node connectivity.
    Drop safety below 1 only to add margin against the near-crossover span compression (the +xi term
    shrinks the realized log-span just above the aPol>xi*G/R gate). perm_std unused for the discretized
    target (kept for signature symmetry with shock_logrange)."""
    if safety is None:
        safety = float(os.environ.get("HAFISCAL_MIXING_SAFETY", "1.0"))
    logrange_disc, _ = shock_logrange(IncShkDstn_list, perm_std if perm_std is not None else 0.0)
    return float(safety) * logrange_disc


def make_mixing_grid(ming, maxg, ng, aFac, logspacing_target, m_floor=None, verbose=False):
    """Alt-3 DEFAULT REPAIR: an m-grid whose local log-spacing never exceeds `logspacing_target`
    in the psi-operative (saving) region, so the discretized TM mixes (Perron-Frobenius
    irreducibility) — by DESIGN, not by patching. Builds the production exp-mult base grid (dense
    constraint-region packing intact, where psi's fan-out vanishes and xi mixes anyway) then refines
    the tail via refine_grid_for_mixing. The lower region is bit-identical to make_grid_exp_mult.
    """
    from HARK.utilities import make_grid_exp_mult
    base = make_grid_exp_mult(ming, maxg, ng, aFac)
    grid, n_added = refine_grid_for_mixing(base, logspacing_target, m_floor)
    if verbose:
        mf = APOL_CONSTRAINT_TOL if m_floor is None else m_floor
        print(f"[make_mixing_grid] base ng={ng} (aFac={aFac}) -> refined ng={len(grid)} "
              f"(+{n_added} tail nodes); target dlog={float(logspacing_target):.4f}, "
              f"m_floor={mf:.3f}", flush=True)
    return grid


def _cell_index(m_value, grid):
    """Lower-bracketing cell index of m_value on grid (the cell the 2-point TM lottery lands in),
    clipped to [0, len-2] exactly as tm_methods._build_period_tm does (searchsorted side='right')."""
    M = len(grid)
    idx = int(np.searchsorted(grid, m_value, side="right") - 1)
    return int(np.clip(idx, 0, M - 2))


def mnext(aPol, psi, xi, Rfree, Gamma):
    """The exact next-period m for one (aPol, psi, xi): Rfree*aPol/(psi*Gamma) + xi."""
    return Rfree * aPol / (psi * Gamma) + xi


def extract_employed_shock_psi(IncShkDstn_j):
    """Unique permanent-shock atoms (sorted) + a representative transitory value (prob-weighted mean
    transitory shock) from one Markov state's joint IncShkDstn. Var[psi]==0 => not a psi-mixing state."""
    perm = np.asarray(IncShkDstn_j.atoms[0], dtype=float)
    tran = np.asarray(IncShkDstn_j.atoms[1], dtype=float)
    pmv = np.asarray(IncShkDstn_j.pmv, dtype=float)
    psi_atoms = np.unique(np.round(perm, 12))
    xi_rep = float(np.sum(tran * pmv) / np.sum(pmv))  # E[xi]; psi's fan-out width is xi-independent
    return psi_atoms, xi_rep


def mixing_report(dist_mGrid, aPol_2d, Rfree_arr, PermGroFac_arr, IncShkDstn_list,
                  perm_std, k=SIGMA_BOUND, verbose=True):
    """Per-(Markov-state, m-node) mixing diagnostic, faithful to tm_methods._build_period_tm.

    For each Markov state j with a non-degenerate permanent shock, and each source m-node i:
      a = aPol_2d[j, i]
      (A continuous) psi in {inf, median, sup} of the k-sigma-truncated lognormal
      (B discretized) psi in {min, median, max} of the discretized perm atoms
      hold xi at the state's mean transitory shock; map each mNext to its dist_mGrid cell index.
      FLAG a low-side (psi=sup -> low m) collapse if cell(sup) == cell(median); high-side likewise.
    Also reports the Alt-3 closed-form log-spacing criterion vs the shock log-range.
    """
    M = len(dist_mGrid)
    log_grid = np.log(np.maximum(dist_mGrid, 1e-300))
    d_log = np.diff(log_grid)  # local log-spacing between adjacent nodes (M-1,)
    # exclude the degenerate aMin->node1 interval (log(aMin=0) ~ -690 poisons it)
    _ok = dist_mGrid[:-1] > 1e-9
    d_log_clean = d_log[_ok] if _ok.any() else d_log
    out = {"states": [], "sigma_bound_k": k, "perm_std": float(perm_std)}

    # Alt-3 closed-form shock log-ranges
    psi_inf0, _, psi_sup0 = bounded_perm_shock_bounds(perm_std, k)
    logrange_cont = float(np.log(psi_sup0 / psi_inf0))  # = 2*k*sigma

    for j in range(len(IncShkDstn_list)):
        psi_atoms, xi_rep = extract_employed_shock_psi(IncShkDstn_list[j])
        if len(psi_atoms) < 2 or np.ptp(psi_atoms) < 1e-9:
            continue  # degenerate psi (e.g. unemployment state) -> xi supplies mixing, not psi
        psi_min_a, psi_max_a = float(psi_atoms[0]), float(psi_atoms[-1])
        psi_med_a = float(np.median(psi_atoms))
        logrange_disc = float(np.log(psi_max_a / psi_min_a))
        psi_inf, psi_med_c, psi_sup = bounded_perm_shock_bounds(perm_std, k)

        R, G = float(Rfree_arr[j]), float(PermGroFac_arr[j])
        aPol = np.asarray(aPol_2d[j], dtype=float)

        collapse_A = np.zeros(M, dtype=bool)   # continuous inf/sup collapses onto median node
        collapse_B = np.zeros(M, dtype=bool)   # discretized min/max atom collapses onto median atom node
        gapA_lo = np.zeros(M, dtype=int); gapA_hi = np.zeros(M, dtype=int)
        gapB_lo = np.zeros(M, dtype=int); gapB_hi = np.zeros(M, dtype=int)
        for i in range(M):
            a = aPol[i]
            cmA = _cell_index(mnext(a, psi_med_c, xi_rep, R, G), dist_mGrid)
            ci_inf = _cell_index(mnext(a, psi_inf, xi_rep, R, G), dist_mGrid)  # psi small -> m large -> high idx
            ci_sup = _cell_index(mnext(a, psi_sup, xi_rep, R, G), dist_mGrid)  # psi large -> m small -> low idx
            gapA_hi[i] = ci_inf - cmA            # median->high-side spread (info only)
            gapA_lo[i] = cmA - ci_sup            # median->low-side spread (info only)
            # MODEST mixing condition (the GOAL): the row must not be a POINT MASS — at least one psi
            # realization must reach a cell different from another, i.e. the inf->sup fan-out straddles
            # >= COLLAPSE_GAP cell boundaries. This is exactly what irreducibility needs (one
            # off-diagonal edge per psi-operative row); it does NOT require every realization to connect,
            # nor both an up- and a down-edge at every node. Closed form: Delta_log(grid) < FULL log-range
            # (not half). EXCUSE grid-boundary truncation: a row whose entire fan-out is pinned in the top
            # cell (no grid above aMax) or the bottom cell is the tail / constraint cutoff (~0 mass, and
            # one-sided connectivity preserves irreducibility), not a failure.
            spanA = ci_inf - ci_sup              # # boundaries the inf->sup fan-out crosses
            collapse_A[i] = (spanA < COLLAPSE_GAP) and (ci_inf < M - 2) and (ci_sup > 0)

            cmB = _cell_index(mnext(a, psi_med_a, xi_rep, R, G), dist_mGrid)
            ci_minatom = _cell_index(mnext(a, psi_min_a, xi_rep, R, G), dist_mGrid)  # high idx
            ci_maxatom = _cell_index(mnext(a, psi_max_a, xi_rep, R, G), dist_mGrid)  # low idx
            gapB_hi[i] = ci_minatom - cmB
            gapB_lo[i] = cmB - ci_maxatom
            spanB = ci_minatom - ci_maxatom      # # boundaries the min-atom->max-atom fan-out crosses
            collapse_B[i] = (spanB < COLLAPSE_GAP) and (ci_minatom < M - 2) and (ci_maxatom > 0)

        # Gate by aPol: psi is the operative mixer only in the MULTIPLICATIVE regime of the recursion
        # mNext = R*aPol/(G*psi) + xi. psi moves mNext multiplicatively only once the R*aPol/G term
        # dominates the additive xi; below the crossover R*aPol/G = xi (i.e. aPol = xi*G/R) the
        # recursion is xi-dominated and psi's log-fan-out -> 0 (NO grid resolves it), so xi supplies
        # mixing and collapses there are EXPECTED, not failures. This crossover is a structural
        # property of the recursion (grid-independent), not a magic number. Keep the env floor as a
        # hard lower bound.
        apol_tol = max(APOL_CONSTRAINT_TOL, xi_rep * G / R)
        psi_op = aPol > apol_tol
        cA_op, cB_op = collapse_A & psi_op, collapse_B & psi_op   # the REAL (psi-operative) collapses
        cA_con, cB_con = collapse_A & ~psi_op, collapse_B & ~psi_op  # constraint-region (xi-handled)

        def _hi(mask):  # highest aPol / m at which a collapse still occurs (confinement)
            return (float(aPol[mask].max()), float(dist_mGrid[mask].max())) if mask.any() else (0.0, 0.0)
        maxapolA, maxmA = _hi(cA_op); maxapolB, maxmB = _hi(cB_op)

        st = {
            "markov_state": j, "n_psi_atoms": len(psi_atoms),
            "psi_atom_range": (psi_min_a, psi_max_a), "xi_rep": xi_rep,
            "logrange_cont_2ksig": logrange_cont, "logrange_disc_atoms": logrange_disc,
            "nA_collapse_op": int(cA_op.sum()), "nB_collapse_op": int(cB_op.sum()),
            "nA_collapse_constraint": int(cA_con.sum()), "nB_collapse_constraint": int(cB_con.sum()),
            "n_psi_operative": int(psi_op.sum()), "M": M, "apol_tol": float(apol_tol),
            "maxapol_collapse_A": maxapolA, "maxapol_collapse_B": maxapolB,
            "frac_dlog_gt_cont": float(np.mean(d_log_clean > logrange_cont)),
            "frac_dlog_gt_disc": float(np.mean(d_log_clean > logrange_disc)),
            "max_dlog": float(d_log_clean.max()), "median_dlog": float(np.median(d_log_clean)),
        }
        out["states"].append(st)
        if verbose:
            print(f"[state {j}] psi atoms={len(psi_atoms)} in [{psi_min_a:.4f},{psi_max_a:.4f}] "
                  f"(median {psi_med_a:.4f}); xi_rep={xi_rep:.4f}; {st['n_psi_operative']}/{M} nodes "
                  f"psi-operative (aPol>{apol_tol:.3f}=xi*G/R crossover)")
            print(f"   shock log-range: continuous 2k*sigma={logrange_cont:.4f}  "
                  f"discretized-atoms={logrange_disc:.4f} (binding)")
            print(f"   grid log-spacing (cleaned): median={st['median_dlog']:.4f} max={st['max_dlog']:.4f}"
                  f"  -> Alt-3: {st['frac_dlog_gt_disc']*100:.0f}% of intervals exceed the discretized range")
            print(f"   (A) continuous inf/sup point-mass rows: {st['nA_collapse_op']} in saving region "
                  f"+ {st['nA_collapse_constraint']} in constraint region (xi-handled)")
            print(f"   (B) discretized min/max point-mass rows: {st['nB_collapse_op']} in saving region "
                  f"+ {st['nB_collapse_constraint']} in constraint region (xi-handled)  [BINDING]")
            if st["nB_collapse_op"] == 0 and st["nA_collapse_op"] == 0:
                print(f"   => MIXING HOLDS wherever psi is the operative mixer (collapses confined to "
                      f"the constraint region). OK.")
            elif st["nB_collapse_op"] and st["nA_collapse_op"] == 0:
                print(f"   => (A) ok but (B) fails up to aPol={maxapolB:.3f} (m={maxmB:.1f}): shock "
                      f"discretization too coarse -> Alt 1 (more psi atoms)")
            else:
                print(f"   => (A) FAILS up to aPol={maxapolA:.3f} (m={maxmA:.1f}): asset grid too coarse "
                      f"in the saving region -> Alt 3 (design log-spacing) / refine")
    return out


# ---------------------------------------------------------------------------
def _build_solved_college_agent(aMax_env=None):
    """Build + solve one College agent (baseline, no AD) — mirrors adaptive_grid_tm.college_top_ergodic."""
    _here = os.path.dirname(os.path.abspath(__file__))
    _fpc = os.path.join(_here, "FromPandemicCode")
    if _fpc not in sys.path:
        sys.path.insert(0, _fpc)
    _saved = sys.argv
    sys.argv = [sys.argv[0]]
    try:
        import EstimParameters as ep
        from EstimParameters import init_college, init_ADEconomy, PermShkStd, UBspell_normal
        from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
        from HARK.distributions import DiscreteDistribution
    finally:
        sys.argv = _saved
    ag = AggFiscalType(**init_college); ag.cycles = 0
    eco = AggregateDemandEconomy(**init_ADEconomy); ag.get_economy_data(eco)
    Du = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnemp])])
    Dn = DiscreteDistribution(np.array([1.0]), [np.array([1.0]), np.array([ag.IncUnempNoBenefits])])
    ag.IncShkDstn = [[ag.IncShkDstn[0]] + [Du] * UBspell_normal + [Dn]]
    ag.IncShkDstn_base = ag.IncShkDstn
    ag.tm_a_indexed = True
    ag.interpretation = os.environ.get("HAFISCAL_INTERPRETATION", "ESC")
    eco.agents = [ag]
    eco.solve()
    return ag, float(PermShkStd[0])


if __name__ == "__main__":
    from HARK.utilities import make_grid_exp_mult
    aMax = float(os.environ.get("HAFISCAL_TM_AMAX", "1300"))
    aCount = int(os.environ.get("HAFISCAL_MIXING_ACOUNT", "200"))
    aFac = 3
    print(f"=== TM mixing diagnostic (methodization: k={SIGMA_BOUND} sigma, aCount={aCount}, "
          f"aMax={aMax}, aFac={aFac}) ===")
    ag, perm_std = _build_solved_college_agent()
    print(f"College PermShkStd={perm_std:.4f}  (psi-mixing is moot if 0)")
    J = ag.MrkvArray[0].shape[0]
    Rfree_arr = np.asarray(ag.Rfree[:J], dtype=float)
    PermGroFac_arr = np.asarray(ag.PermGroFac[0][:J], dtype=float)
    sol = ag.solution[0]
    Cratio = 1.0
    IncShkDstn_list = ag.IncShkDstn[0]

    def _aPol_on(grid):
        return np.vstack([grid - sol.cFunc[j](grid, Cratio * np.ones_like(grid)) for j in range(J)])

    print("\n----- (1) PRODUCTION exp-mult grid (current) -----")
    dist_mGrid = make_grid_exp_mult(0.0, aMax, aCount, aFac)
    mixing_report(dist_mGrid, _aPol_on(dist_mGrid), Rfree_arr, PermGroFac_arr, IncShkDstn_list, perm_std)

    # Alt-3 repair: target log-spacing = the binding (discretized) shock log-range (safety=1.0), so the
    # min->max fan-out straddles >=1 cell boundary => the row is not a point mass (the MODEST goal: one
    # off-diagonal edge per psi-operative row = irreducibility). NOT half — that would over-demand
    # two-sided per-node connectivity.
    logrange_disc, logrange_cont = shock_logrange(IncShkDstn_list, perm_std)
    safety = float(os.environ.get("HAFISCAL_MIXING_SAFETY", "1.0"))
    target = safety * logrange_disc
    print(f"\n----- (2) Alt-3 MIXING grid (target dlog = {safety:g} * logrange_disc "
          f"= {target:.4f}) -----")
    mix_grid = make_mixing_grid(0.0, aMax, aCount, aFac, target, verbose=True)
    mixing_report(mix_grid, _aPol_on(mix_grid), Rfree_arr, PermGroFac_arr, IncShkDstn_list, perm_std)
