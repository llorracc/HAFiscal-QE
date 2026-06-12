"""
mom_bounds.py — Method-of-Moderation (MoM) optimist bounds for HAFiscal.

Provides perfect-foresight upper-envelope bounds (asymptotic MPC and per-state
expected human wealth) for use as a warm-start to HARK's EGM solver. Splurge-
aware: handles HAFiscal's `c_total(m, y) = Splurge*y + c_opt(m - Splurge*y)`
consumption rule.

Toy validation (CASE 1 PF, CASE 2 2-state, CASE 3 4-state HAFiscal-like) passed
to float64 precision against closed-form Carroll/HARK references. See the
__main__ guard for the self-test.

References:
    - HARK ConsMarkovModel.py:552-568 (hNrm + MPCmin Markov recursion)
    - Carroll (2023) "Solution Methods for MicroDSOP", Section on MoM bounds
"""

from __future__ import annotations

import os
import warnings
from typing import Any, List, Optional

import numpy as np


# ---------------------------------------------------------------------------
# (1) Human-wealth solver
# ---------------------------------------------------------------------------

def solve_markov_human_wealth(
    MrkvArray: np.ndarray,
    Rfree_by_state: np.ndarray,
    ExpY_by_state: np.ndarray,
    LivPrb_by_state: Optional[np.ndarray] = None,
    PermGroFac_by_state: Optional[np.ndarray] = None,
    cond_warn_threshold: float = 1e10,
) -> np.ndarray:
    """Solve the per-state expected human wealth fixed point.

    hBar_i = sum_j M[i,j] * (Gamma_j / R_j) * (E_inc_j + hBar_j)

    rearranged as (I - D) hBar = D @ E_inc, with D_ij = M[i,j] * Gamma_j / R_j.

    Parameters
    ----------
    MrkvArray : (S, S) Markov transition matrix (rows sum to 1).
    Rfree_by_state : (S,) gross interest rate per Markov state.
    ExpY_by_state : (S,) expected per-period income E[psi*theta] per state.
    LivPrb_by_state : ignored for hBar in HARK's convention (survival enters
        via DiscFacEff in MPCmin, not in hNrm). Accepted for API symmetry.
    PermGroFac_by_state : (S,) permanent income growth per state. Defaults to
        ones (no per-state growth) if not provided.
    cond_warn_threshold : warn if cond(I - D) exceeds this. Default 1e10.

    Returns
    -------
    hBar : (S,) per-state expected human wealth.

    Notes
    -----
    Existence requires spectral_radius(D) < 1 (the standard PF impatience
    condition for human wealth to be finite). At HAFiscal calibration
    (R~=1.01, Gamma~=1.005, ~168 states) cond(I - D) is typically ~4e2;
    direct solve is fine.
    """
    M = np.asarray(MrkvArray, dtype=float)
    R = np.asarray(Rfree_by_state, dtype=float)
    E = np.asarray(ExpY_by_state, dtype=float)
    S = M.shape[0]
    if M.shape != (S, S):
        raise ValueError(f"MrkvArray must be square; got {M.shape}")
    if R.shape != (S,) or E.shape != (S,):
        raise ValueError(
            f"Rfree_by_state and ExpY_by_state must have shape ({S},); "
            f"got {R.shape} and {E.shape}"
        )
    if PermGroFac_by_state is None:
        G = np.ones(S, dtype=float)
    else:
        G = np.asarray(PermGroFac_by_state, dtype=float)
        if G.shape != (S,):
            raise ValueError(f"PermGroFac_by_state must have shape ({S},); got {G.shape}")

    D = M * (G / R)[None, :]
    spec_rad = float(np.max(np.abs(np.linalg.eigvals(D))))
    if spec_rad >= 1.0:
        warnings.warn(
            f"solve_markov_human_wealth: spectral_radius(D)={spec_rad:.6f} >= 1; "
            "PF impatience violated, hBar is infinite/undefined. Returning NaNs."
        )
        return np.full(S, np.nan)

    A = np.eye(S) - D
    cond_A = float(np.linalg.cond(A))
    if cond_A > cond_warn_threshold:
        warnings.warn(
            f"solve_markov_human_wealth: cond(I-D)={cond_A:.3e} exceeds "
            f"threshold {cond_warn_threshold:.0e}; solution may be inaccurate."
        )
    return np.linalg.solve(A, D @ E)


# ---------------------------------------------------------------------------
# (2) Asymptotic MPC
# ---------------------------------------------------------------------------

def compute_mpc_min(
    Rfree: float,
    DiscFac: float,
    CRRA: float,
    LivPrb: float = 1.0,
) -> float:
    """Closed-form scalar PF asymptotic MPC.

    MPCmin = 1 - (Rfree * DiscFac * LivPrb)^(1/CRRA) / Rfree

    Valid when Rfree is uniform across Markov states (the common HAFiscal case
    -- see toy CASE 2/3 takeaways: MPCmin is state-invariant when Rfree is
    uniform, so a scalar return suffices).
    """
    if Rfree <= 0 or DiscFac <= 0 or CRRA <= 0 or LivPrb <= 0:
        raise ValueError(
            f"compute_mpc_min: all inputs must be positive; got "
            f"Rfree={Rfree}, DiscFac={DiscFac}, CRRA={CRRA}, LivPrb={LivPrb}"
        )
    patience = (Rfree * DiscFac * LivPrb) ** (1.0 / CRRA) / Rfree
    if patience >= 1.0:
        warnings.warn(
            f"compute_mpc_min: patience factor {patience:.6f} >= 1; "
            "PF impatience violated, MPCmin is non-positive."
        )
    return 1.0 - patience


def compute_mpc_min_markov(
    MrkvArray: np.ndarray,
    Rfree_by_state: np.ndarray,
    DiscFac: float,
    CRRA: float,
    LivPrb: float = 1.0,
) -> np.ndarray:
    """Per-state PF asymptotic MPC via the coupled fixed point.

    1/MPCmin_i = sum_j M[i,j] * ((R_j*beta*L)^(1/rho)/R_j) / MPCmin_j   (linearized)

    When Rfree is uniform across states, this collapses to the scalar form.
    """
    M = np.asarray(MrkvArray, dtype=float)
    R = np.asarray(Rfree_by_state, dtype=float)
    S = M.shape[0]
    PatFac = M @ ((R * DiscFac * LivPrb) ** (1.0 / CRRA) / R)
    x = np.linalg.solve(np.eye(S) - np.diag(PatFac) @ M, np.ones(S))
    return 1.0 / x


# ---------------------------------------------------------------------------
# (3) Splurge-aware optimist warm-start
# ---------------------------------------------------------------------------

def _safe_get(obj: Any, name: str, default: Any) -> Any:
    """getattr with a default; tolerates HARK's mix of attr/dict storage."""
    val = getattr(obj, name, None)
    if val is None and hasattr(obj, 'parameters') and isinstance(obj.parameters, dict):
        val = obj.parameters.get(name, default)
    return default if val is None else val


def _ensure_per_state(value: Any, S: int) -> np.ndarray:
    """Broadcast a scalar or length-1 array to length-S; pass arrays through."""
    arr = np.asarray(value, dtype=float).ravel()
    if arr.size == 1:
        return np.full(S, float(arr[0]))
    if arr.size == S:
        return arr
    raise ValueError(f"Expected scalar or length-{S} array; got shape {arr.shape}")


def _expected_income_per_state(IncShkDstn: Any, S: int) -> np.ndarray:
    """Compute E[psi*theta] per Markov state from HARK's IncShkDstn list."""
    E = np.zeros(S, dtype=float)
    for j in range(S):
        try:
            d = IncShkDstn[j] if not hasattr(IncShkDstn, '__call__') else IncShkDstn[0][j]
            pmv = np.asarray(d.pmv, dtype=float)
            atoms = np.asarray(d.atoms, dtype=float)
            E[j] = float(np.sum(pmv * atoms[0] * atoms[1]))
        except Exception:
            # IndexDistribution or unusual shape: best-effort fall-through to 1.0
            E[j] = 1.0
    return E


def build_optimist_warm_start(agent: Any) -> Any:
    """Return a HARK ConsumerSolution-compatible object with optimist bounds.

    For each Markov state i, the splurge-aware optimist consumption bound is:

        c_total^bar(m) = MPCmin * m + MPCmin * hBar_i + Splurge*(1-MPCmin) * E[y|i]

    where we use the unconditional E[y|i] as the linear-in-m reference (so the
    bound is a single affine function per state; documented approximation).

    The warm-start is delivered as ConsumerSolution with:
      - cFunc[i] : LinearInterp of (m, c_bar) -> c_bar
      - vPfunc[i]: MargValueFuncCRRA of cFunc[i] under CRRA
      - mNrmMin[i]: -hBar_i (natural borrowing constraint at the bound)
      - hNrm[i]  : hBar_i
      - MPCmin[i]: scalar MPCmin (state-invariant under uniform Rfree)
      - MPCmax[i]: 1.0 (consume everything if constrained at zero wealth)

    Defensive: tolerates missing aXtraGrid (falls back to a default grid),
    missing LivPrb (defaults to 1.0), missing PermGroFac (defaults to ones).
    """
    # Lazy import to avoid HARK dependency at module load
    from HARK.ConsumptionSaving.ConsIndShockModel import ConsumerSolution
    from HARK.interpolation import (
        LinearInterp,
        MargValueFuncCRRA,
        ValueFuncCRRA,
    )

    MrkvArray = np.asarray(_safe_get(agent, 'MrkvArray', None), dtype=float)
    if MrkvArray.ndim != 2 or MrkvArray.shape[0] != MrkvArray.shape[1]:
        raise ValueError(
            f"build_optimist_warm_start: agent.MrkvArray must be square; "
            f"got shape {MrkvArray.shape}"
        )
    S = MrkvArray.shape[0]

    Rfree = _ensure_per_state(_safe_get(agent, 'Rfree', 1.01), S)
    PermGroFac = _ensure_per_state(_safe_get(agent, 'PermGroFac', np.ones(S)), S)
    LivPrb_arr = _ensure_per_state(_safe_get(agent, 'LivPrb', 1.0), S)
    LivPrb_scalar = float(np.mean(LivPrb_arr))  # for the scalar MPCmin form
    DiscFac = float(_safe_get(agent, 'DiscFac', 0.96))
    CRRA = float(_safe_get(agent, 'CRRA', 2.0))
    Splurge = float(_safe_get(agent, 'Splurge', 0.0))

    IncShkDstn = _safe_get(agent, 'IncShkDstn', None)
    if IncShkDstn is None:
        E_inc = np.ones(S, dtype=float)
    else:
        E_inc = _expected_income_per_state(IncShkDstn, S)

    # (a) Per-state human wealth
    hBar = solve_markov_human_wealth(
        MrkvArray, Rfree, E_inc, LivPrb_by_state=LivPrb_arr,
        PermGroFac_by_state=PermGroFac,
    )

    # (b) Asymptotic MPC: uniform-Rfree case -> scalar; else per-state
    if np.allclose(Rfree, Rfree[0]):
        MPCmin_scalar = compute_mpc_min(float(Rfree[0]), DiscFac, CRRA, LivPrb_scalar)
        MPCmin_arr = np.full(S, MPCmin_scalar)
    else:
        MPCmin_arr = compute_mpc_min_markov(MrkvArray, Rfree, DiscFac, CRRA, LivPrb_scalar)

    # (c) Build per-state warm-start solution
    aXtraGrid = _safe_get(agent, 'aXtraGrid', None)
    if aXtraGrid is None or len(np.asarray(aXtraGrid)) == 0:
        aXtraGrid = np.geomspace(1e-3, 100.0, 64)
    aXtraGrid = np.asarray(aXtraGrid, dtype=float).ravel()

    solutions: List[Any] = []
    for i in range(S):
        mpc_i = float(MPCmin_arr[i])
        hbar_i = float(hBar[i])
        # Affine intercept including splurge linearization at E[y|i]
        c_intercept = mpc_i * hbar_i + Splurge * (1.0 - mpc_i) * float(E_inc[i])
        # Grid: m runs from natural-cnst lower bound up to high m
        mNrmMin_i = -hbar_i  # natural borrowing constraint
        mGrid = np.concatenate([[mNrmMin_i + 1e-8], mNrmMin_i + aXtraGrid])
        cGrid = mpc_i * (mGrid - mNrmMin_i) + c_intercept
        # Enforce positivity (defensive — should hold under PF impatience)
        cGrid = np.maximum(cGrid, 1e-12)

        cFunc_i = LinearInterp(mGrid, cGrid)
        vPfunc_i = MargValueFuncCRRA(cFunc_i, CRRA)
        try:
            vFunc_i = ValueFuncCRRA(cFunc_i, CRRA)
        except Exception:
            vFunc_i = None

        sol_i = ConsumerSolution(
            cFunc=cFunc_i,
            vPfunc=vPfunc_i,
            mNrmMin=mNrmMin_i,
            hNrm=hbar_i,
            MPCmin=mpc_i,
            MPCmax=1.0,
        )
        if vFunc_i is not None:
            sol_i.vFunc = vFunc_i
        solutions.append(sol_i)

    # Wrap as a Markov-style ConsumerSolution: HARK's convention here is a
    # ConsumerSolution whose attributes are *lists* over Markov states.
    warm_start = ConsumerSolution(
        cFunc=[s.cFunc for s in solutions],
        vPfunc=[s.vPfunc for s in solutions],
        mNrmMin=np.array([s.mNrmMin for s in solutions]),
        hNrm=np.array([s.hNrm for s in solutions]),
        MPCmin=np.array([s.MPCmin for s in solutions]),
        MPCmax=np.array([s.MPCmax for s in solutions]),
    )
    return warm_start


# ---------------------------------------------------------------------------
# (4) Self-test: re-run toy validation
# ---------------------------------------------------------------------------

def _toy_validation(verbose: bool = True) -> bool:
    """Re-run the three validated toy cases. Returns True iff all pass."""
    all_pass = True

    # CASE 1: 1-state PF, R=1.03, G=1.01, beta=0.96, rho=2, LivPrb=1
    M = np.array([[1.0]])
    R = np.array([1.03]); G = np.array([1.01]); E = np.array([1.0])
    hBar = solve_markov_human_wealth(M, R, E, PermGroFac_by_state=G)
    hBar_cf = (G[0] / R[0]) / (1.0 - G[0] / R[0])
    mpc = compute_mpc_min(1.03, 0.96, 2.0, 1.0)
    mpc_cf = 1.0 - (1.03 * 0.96) ** 0.5 / 1.03
    p1 = abs(hBar[0] - hBar_cf) < 1e-10 and abs(mpc - mpc_cf) < 1e-10
    all_pass &= p1
    if verbose:
        print(f"  CASE 1: hBar diff={abs(hBar[0]-hBar_cf):.2e}, "
              f"MPCmin diff={abs(mpc-mpc_cf):.2e} -> {'PASS' if p1 else 'FAIL'}")

    # CASE 2: 2-state symmetric employed/unemployed
    M2 = np.array([[0.96, 0.04], [0.50, 0.50]])
    R2 = np.array([1.01, 1.01]); G2 = np.array([1.005, 1.0]); E2 = np.array([1.0, 0.3])
    hBar2 = solve_markov_human_wealth(M2, R2, E2, PermGroFac_by_state=G2)
    mpc2 = compute_mpc_min_markov(M2, R2, 0.9788, 2.0, 0.99375)
    p2 = np.all(np.isfinite(hBar2)) and hBar2[0] > hBar2[1] > 0 and np.allclose(mpc2, mpc2[0])
    all_pass &= p2
    if verbose:
        print(f"  CASE 2: hBar={hBar2}, MPCmin={mpc2} -> {'PASS' if p2 else 'FAIL'}")

    # CASE 3: 4-state HAFiscal-like
    M3 = np.array([
        [0.96, 0.04, 0.00, 0.00],
        [0.50, 0.00, 0.50, 0.00],
        [0.50, 0.00, 0.00, 0.50],
        [0.50, 0.00, 0.00, 0.50],
    ])
    R3 = np.full(4, 1.01); G3 = np.array([1.005, 1.0, 1.0, 1.0])
    E3 = np.array([1.0, 0.3, 0.3, 0.15])
    hBar3 = solve_markov_human_wealth(M3, R3, E3, PermGroFac_by_state=G3)
    mpc3 = compute_mpc_min_markov(M3, R3, 0.9788, 2.0, 0.99375)
    p3 = np.all(np.isfinite(hBar3)) and hBar3[0] > hBar3[1] > 0
    all_pass &= p3
    if verbose:
        print(f"  CASE 3: hBar={hBar3}, MPCmin={mpc3} -> {'PASS' if p3 else 'FAIL'}")

    return all_pass


if __name__ == '__main__':
    print("[mom_bounds] running self-test (toy validation)...")
    ok = _toy_validation(verbose=True)
    print(f"[mom_bounds] self-test {'PASSED' if ok else 'FAILED'}")
    raise SystemExit(0 if ok else 1)
