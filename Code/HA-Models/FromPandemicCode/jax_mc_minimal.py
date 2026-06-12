"""
jax_mc_minimal.py — standalone JAX MC simulator for HAFiscal welfare-6.

OVERNIGHT PILOT (2026-05-17): Proof-of-concept for GPU MC speedup. NOT a
production replacement for the HARK-based MC in AggFiscalModel. Pure
functions on JAX arrays; pre-tabulated cFunc; no AgentType class hierarchy.

Per-step logic mirrors AggFiscalModel.get_states + get_controls +
get_poststates, simplified:

  Inputs per period t:
    aNrm_prev  : (N,)  normalized assets at end of t-1
    pLvl_prev  : (N,)  permanent income level at end of t-1
    mrkv_prev  : (N,)  combined Markov state (int in [0, J))

  Per agent:
    death_draw, mrkv_draw, atom_draw  (categorical / uniform)
    Mortality: if die, replace with newborn (aNrm=newborn_aNrm, pLvl=newborn_pLvl)
    Mrkv transition: cumulative-prob categorical from MrkvArray[mrkv_prev]
    Income shock: draw atom k from IncShk_pmv[mrkv_now]; (psi_k, xi_k)
    bNrm = R * aNrm_prev / (PermGroFac * psi_k)
    mNrm = bNrm + xi_k * AggDemandFac   (AD=1, AggDemandFac=Cratio; AD=0, =1)
    cNrm = cFunc[mrkv_now](mNrm, Cratio)
    cLvl = cNrm * pLvl_prev * PermGroFac * psi_k
    cLvl_splurge = (1 - Splurge) * cLvl + Splurge * pLvl_prev * PermGroFac * psi_k * xi_k * AggDemandFac
    aNrm_next = mNrm - cLvl_splurge / (pLvl_prev * PermGroFac * psi_k)
    pLvl_next = pLvl_prev * PermGroFac * psi_k

Outputs:
    AggIncome[t]      : sum_agents (pLvl_prev * PermGroFac * psi * xi * ADF)
    AggCons[t]        : sum_agents (cLvl_splurge)
    cLvl_panel[t,n]   : per-agent cLvl_splurge (for welfare integrand)

NOT IMPLEMENTED in this pilot:
  - AD outer loop (Cratio iteration)
  - sim_birth's lognormal initial-state distribution (uses fixed newborn pool)
  - HARK 0.14.1 RNG-sync (JAX RNG produces different numbers — validate
    distributionally, not bit-identically vs HARK)
  - Per-period cFunc selection (uses single cFunc; HARK varies by t_cycle)
  - PHASE-R diagnostics, drift hard-fails, etc.
  - 6-state UI encoding nuances (treats Mrkv as opaque integer)
"""
from __future__ import annotations
import os
import numpy as np

# JAX import deferred (so numpy reference can be tested without JAX)
_HAS_JAX = False
try:
    import jax
    import jax.numpy as jnp
    from jax import lax, random
    _HAS_JAX = True
except ImportError:
    pass


# ============================================================
# Pure numpy reference implementation
# ============================================================

def _mc_step_np(carry, t, *,
                cfunc_table, m_grid,
                Rfree, PermGroFac, MrkvArray,
                IncShk_psi, IncShk_xi, IncShk_pmv, IncShk_natoms,
                AggDemandFac, Cratio, Splurge, LivPrb,
                newborn_aNrm, newborn_pLvl, newborn_mrkv,
                rng_seeds_t):
    """One simulation period in pure numpy. carry = (aNrm, pLvl, mrkv)."""
    aNrm_prev, pLvl_prev, mrkv_prev = carry
    N = aNrm_prev.shape[0]
    J = MrkvArray.shape[0]

    # Per-period RNGs (using numpy RandomState with deterministic seeds)
    rs_death = np.random.RandomState(rng_seeds_t[0])
    rs_mrkv  = np.random.RandomState(rng_seeds_t[1])
    rs_atom  = np.random.RandomState(rng_seeds_t[2])

    # Mortality: which agents die this period
    death_draw = rs_death.uniform(size=N)
    alive_mask = death_draw < LivPrb   # True = alive, False = born this period

    # Mrkv transition: per-agent categorical draw from MrkvArray[mrkv_prev]
    mrkv_draw = rs_mrkv.uniform(size=N)
    cum_prob = np.cumsum(MrkvArray[mrkv_prev], axis=-1)   # (N, J)
    mrkv_now = (mrkv_draw[:, None] > cum_prob).sum(axis=-1)   # (N,)
    mrkv_now = np.clip(mrkv_now, 0, J - 1)

    # Replace dead agents with newborns (cycle through newborn pool by agent index)
    pool_idx = np.arange(N) % newborn_aNrm.shape[0]
    aNrm_carry = np.where(alive_mask, aNrm_prev, newborn_aNrm[pool_idx])
    pLvl_carry = np.where(alive_mask, pLvl_prev, newborn_pLvl[pool_idx])
    mrkv_now = np.where(alive_mask, mrkv_now, newborn_mrkv[pool_idx])

    # Income shock: per agent, draw atom by category from IncShk_pmv[mrkv_now]
    atom_draw = rs_atom.uniform(size=N)
    cum_atom = np.cumsum(IncShk_pmv[mrkv_now], axis=-1)   # (N, max_atoms)
    atom_idx = (atom_draw[:, None] > cum_atom).sum(axis=-1)
    natoms_now = IncShk_natoms[mrkv_now]
    atom_idx = np.minimum(atom_idx, natoms_now - 1)

    psi = IncShk_psi[mrkv_now, atom_idx]
    xi  = IncShk_xi[mrkv_now, atom_idx]

    # Asset / consumption
    R_now = Rfree[mrkv_now] if Rfree.ndim > 0 else Rfree
    G_now = PermGroFac[mrkv_now] if PermGroFac.ndim > 0 else PermGroFac

    bNrm = R_now * aNrm_carry / (G_now * psi)
    mNrm = bNrm + xi * AggDemandFac

    # cFunc lookup (linear interp on m_grid for each Mrkv state)
    cNrm = np.empty(N)
    for j in range(J):
        mask = mrkv_now == j
        if mask.any():
            cNrm[mask] = np.interp(mNrm[mask], m_grid, cfunc_table[j])

    pLvl_now = pLvl_carry * G_now * psi
    cLvl = cNrm * pLvl_now
    cLvl_splurge = (1.0 - Splurge) * cLvl + Splurge * pLvl_now * xi * AggDemandFac

    aNrm_next = mNrm - cLvl_splurge / pLvl_now

    # Aggregates this period
    income_now = pLvl_now * xi * AggDemandFac
    AggInc_t = float(income_now.sum())
    AggCons_t = float(cLvl_splurge.sum())

    new_carry = (aNrm_next, pLvl_now, mrkv_now)
    out_t = (AggInc_t, AggCons_t, cLvl_splurge.copy())
    return new_carry, out_t


def simulate_np(aNrm0, pLvl0, mrkv0,
                cfunc_table, m_grid,
                Rfree, PermGroFac, MrkvArray,
                IncShk_psi, IncShk_xi, IncShk_pmv, IncShk_natoms,
                AggDemandFac, Cratio, Splurge, LivPrb,
                newborn_aNrm, newborn_pLvl, newborn_mrkv,
                act_T, seed_base=0):
    """Run T-period MC sim in pure numpy. Returns AggInc[T], AggCons[T], cLvl_panel[T,N]."""
    N = aNrm0.shape[0]
    AggInc = np.zeros(act_T)
    AggCons = np.zeros(act_T)
    cLvl_panel = np.zeros((act_T, N), dtype=np.float64)
    carry = (aNrm0.copy(), pLvl0.copy(), mrkv0.copy())
    for t in range(act_T):
        seeds_t = (seed_base * 1000 + 3 * t,
                   seed_base * 1000 + 3 * t + 1,
                   seed_base * 1000 + 3 * t + 2)
        carry, (inc, cons, cls) = _mc_step_np(
            carry, t,
            cfunc_table=cfunc_table, m_grid=m_grid,
            Rfree=Rfree, PermGroFac=PermGroFac, MrkvArray=MrkvArray,
            IncShk_psi=IncShk_psi, IncShk_xi=IncShk_xi,
            IncShk_pmv=IncShk_pmv, IncShk_natoms=IncShk_natoms,
            AggDemandFac=AggDemandFac, Cratio=Cratio,
            Splurge=Splurge, LivPrb=LivPrb,
            newborn_aNrm=newborn_aNrm, newborn_pLvl=newborn_pLvl,
            newborn_mrkv=newborn_mrkv,
            rng_seeds_t=seeds_t,
        )
        AggInc[t] = inc
        AggCons[t] = cons
        cLvl_panel[t] = cls
    return AggInc, AggCons, cLvl_panel


# ============================================================
# JAX implementation
# ============================================================

if _HAS_JAX:

    def _mc_step_jax(carry, scan_in, *,
                     cfunc_table, m_grid,
                     Rfree, PermGroFac, MrkvArray,
                     IncShk_psi, IncShk_xi, IncShk_pmv,
                     AggDemandFac, Splurge, LivPrb,
                     newborn_aNrm, newborn_pLvl, newborn_mrkv,
                     pLvl_unemp_mode='qe',
                     T_age_max=100,
                     ):
        """One simulation period in JAX.

        pLvl_unemp_mode (BUG-040 convention):
          'qe'    — DEFAULT. Matches HARK's QE-published default. For
                    unemployed agents (mrkv_now != 0), pLvl_next =
                    pLvl_prev (frozen, no growth, no shock).
                    Equivalent to setting PermShk=1.0 for unemp at
                    runtime, regardless of IncShkDstn value.
          'grows' — Unemployed agents grow at G (PermShk = G uniform).
                    Set HAFISCAL_PLVL_GROWS_DURING_UNEMP=on equivalent.
          'shock' — Unemployed agents draw PermShk from full distribution
                    (perm_shocks_during_unemployment=True equivalent).
        """
        """One simulation period in JAX. scan_in = rng_key for this period."""
        aNrm_prev, pLvl_prev, mrkv_prev, t_age_prev = carry
        rng_t = scan_in
        rng_death, rng_mrkv, rng_atom = random.split(rng_t, 3)
        N = aNrm_prev.shape[0]
        J = MrkvArray.shape[0]

        # Mortality: stochastic OR forced by T_age (HARK convention).
        # T_age forced death adds ~1%/period to mortality vs LivPrb alone.
        # Without this, JAX overshoots HARK AggInc by ~2.5% over 40 periods.
        death_draw = random.uniform(rng_death, (N,))
        stoch_die = death_draw >= LivPrb
        age_die = t_age_prev >= T_age_max
        alive_mask = ~(stoch_die | age_die)

        # Mrkv transition: cumprob categorical
        mrkv_draw = random.uniform(rng_mrkv, (N,))
        cum_prob = jnp.cumsum(MrkvArray[mrkv_prev], axis=-1)
        mrkv_now = jnp.sum(mrkv_draw[:, None] > cum_prob, axis=-1).astype(jnp.int32)
        mrkv_now = jnp.clip(mrkv_now, 0, J - 1)

        # Newborn replacement (always evaluated; gated by alive_mask)
        pool_idx = jnp.arange(N) % newborn_aNrm.shape[0]
        aNrm_carry = jnp.where(alive_mask, aNrm_prev, newborn_aNrm[pool_idx])
        pLvl_carry = jnp.where(alive_mask, pLvl_prev, newborn_pLvl[pool_idx])
        mrkv_now = jnp.where(alive_mask, mrkv_now, newborn_mrkv[pool_idx])

        # Income shock atom draw
        atom_draw = random.uniform(rng_atom, (N,))
        cum_atom = jnp.cumsum(IncShk_pmv[mrkv_now], axis=-1)
        atom_idx = jnp.sum(atom_draw[:, None] > cum_atom, axis=-1).astype(jnp.int32)
        max_atoms = IncShk_pmv.shape[-1]
        atom_idx = jnp.clip(atom_idx, 0, max_atoms - 1)

        psi = IncShk_psi[mrkv_now, atom_idx]
        xi  = IncShk_xi[mrkv_now, atom_idx]

        R_now = Rfree[mrkv_now]
        G_now = PermGroFac[mrkv_now]

        # BUG-040 pLvl-during-unemp handling
        is_employed = (mrkv_now == 0)
        if pLvl_unemp_mode == 'qe':
            # QE default: unemployed → effective PermShk = 1.0
            # (frozen pLvl, no growth, no shock)
            psi_eff = jnp.where(is_employed, psi, 1.0)
            G_eff = jnp.where(is_employed, G_now, 1.0)
        elif pLvl_unemp_mode == 'grows':
            # Unemployed: ψ=1.0, but G applies (uniform growth)
            psi_eff = jnp.where(is_employed, psi, 1.0)
            G_eff = G_now
        else:  # 'shock'
            # Unemployed draws full shock; G applies normally (current behavior)
            psi_eff = psi
            G_eff = G_now

        bNrm = R_now * aNrm_carry / (G_eff * psi_eff)
        mNrm = bNrm + xi * AggDemandFac

        # cFunc lookup — direct 2D gather (works for non-uniform m_grid).
        # Use jnp.searchsorted for general monotone grids (HARK's triple-log
        # nested grid is NON-uniform).
        M = m_grid.shape[0]
        i_lo = jnp.clip(jnp.searchsorted(m_grid, mNrm, side='right') - 1, 0, M - 2)
        i_hi = i_lo + 1
        m_lo = m_grid[i_lo]
        m_hi = m_grid[i_hi]
        w_hi = (mNrm - m_lo) / (m_hi - m_lo)
        c_lo = cfunc_table[mrkv_now, i_lo]   # (N,)
        c_hi = cfunc_table[mrkv_now, i_hi]   # (N,)
        cNrm = c_lo + w_hi * (c_hi - c_lo)

        pLvl_now = pLvl_carry * G_eff * psi_eff
        cLvl = cNrm * pLvl_now
        cLvl_splurge = (1.0 - Splurge) * cLvl + Splurge * pLvl_now * xi * AggDemandFac

        aNrm_next = mNrm - cLvl_splurge / pLvl_now

        income_now = pLvl_now * xi * AggDemandFac
        AggInc_t = jnp.sum(income_now)
        AggCons_t = jnp.sum(cLvl_splurge)

        # Age tracking: increment if alive, reset to 0 for newborns
        t_age_next = jnp.where(alive_mask, t_age_prev + 1, 0).astype(jnp.int32)
        new_carry = (aNrm_next, pLvl_now, mrkv_now, t_age_next)
        out_t = (AggInc_t, AggCons_t, cLvl_splurge)
        return new_carry, out_t

    # Top-level JIT'd simulate. Takes everything as JAX arrays.
    # All scalar params bound via static_argnames so they don't trigger re-trace.
    from functools import partial

    @partial(jax.jit, static_argnames=('act_T', 'pLvl_unemp_mode', 'T_age_max'))
    def _simulate_jax_core(carry0, period_keys,
                           cfunc_table, m_grid,
                           Rfree, PermGroFac, MrkvArray,
                           IncShk_psi, IncShk_xi, IncShk_pmv,
                           AggDemandFac, Splurge, LivPrb,
                           newborn_aNrm, newborn_pLvl, newborn_mrkv,
                           act_T, pLvl_unemp_mode='qe', T_age_max=100):
        def step(carry, key):
            return _mc_step_jax(
                carry, key,
                cfunc_table=cfunc_table, m_grid=m_grid,
                Rfree=Rfree, PermGroFac=PermGroFac, MrkvArray=MrkvArray,
                IncShk_psi=IncShk_psi, IncShk_xi=IncShk_xi, IncShk_pmv=IncShk_pmv,
                AggDemandFac=AggDemandFac, Splurge=Splurge, LivPrb=LivPrb,
                newborn_aNrm=newborn_aNrm,
                newborn_pLvl=newborn_pLvl,
                newborn_mrkv=newborn_mrkv,
                pLvl_unemp_mode=pLvl_unemp_mode,
                T_age_max=T_age_max,
            )
        _, outs = lax.scan(step, carry0, period_keys)
        return outs

    def simulate_jax(aNrm0, pLvl0, mrkv0,
                     cfunc_table, m_grid,
                     Rfree, PermGroFac, MrkvArray,
                     IncShk_psi, IncShk_xi, IncShk_pmv,
                     AggDemandFac, Cratio, Splurge, LivPrb,
                     newborn_aNrm, newborn_pLvl, newborn_mrkv,
                     act_T, seed_base=0, warmup_T=0,
                     pLvl_unemp_mode='qe',
                     t_age0=None, T_age_max=100):
        """T-period MC sim in JAX. Returns AggInc[T], AggCons[T], cLvl_panel[T,N].

        warmup_T: if >0, run that many discarded periods first (lets JAX
        agents converge to JAX's own steady-state distribution before
        recording the act_T periods of interest).
        """
        # Infer dtype from input arrays (supports both FP32 and FP64).
        fp_dtype = jnp.asarray(aNrm0).dtype
        N = aNrm0.shape[0]
        if t_age0 is None:
            # Sample from truncated geometric ergodic age distribution.
            # P(age <= k) = (1 - LivPrb^(k+1)) / (1 - LivPrb^(T_age_max+1))
            rs = np.random.RandomState(seed_base + 7919)
            cum_p = (1 - LivPrb ** (np.arange(T_age_max + 1) + 1)) / max(
                1 - LivPrb ** (T_age_max + 1), 1e-12)
            t_age0_arr = np.searchsorted(cum_p, rs.uniform(size=N)).astype(np.int32)
        else:
            t_age0_arr = np.asarray(t_age0, dtype=np.int32)
        carry0 = (
            jnp.asarray(aNrm0, dtype=fp_dtype),
            jnp.asarray(pLvl0, dtype=fp_dtype),
            jnp.asarray(mrkv0, dtype=jnp.int32),
            jnp.asarray(t_age0_arr, dtype=jnp.int32),
        )

        if warmup_T > 0:
            warmup_key = random.PRNGKey(seed_base * 2 + 17)
            warmup_keys = random.split(warmup_key, warmup_T)
            # Run warmup (discard outputs, keep final carry)
            _ = _simulate_jax_core(
                carry0, warmup_keys,
                cfunc_table, m_grid,
                Rfree, PermGroFac, MrkvArray,
                IncShk_psi, IncShk_xi, IncShk_pmv,
                AggDemandFac, Splurge, LivPrb,
                newborn_aNrm, newborn_pLvl, newborn_mrkv,
                warmup_T, pLvl_unemp_mode, T_age_max,
            )
            # Reconstruct final carry by running once more with warmup keys
            # (need to use _simulate_jax_warmup_final to extract carry; quick hack
            # via running act_T after warmup in single scan)
            # Simpler: just use longer scan with skip
            total_T = warmup_T + act_T
            master_key = random.PRNGKey(seed_base)
            period_keys = random.split(master_key, total_T)
            AggInc_full, AggCons_full, cLvl_full = _simulate_jax_core(
                carry0, period_keys,
                cfunc_table, m_grid,
                Rfree, PermGroFac, MrkvArray,
                IncShk_psi, IncShk_xi, IncShk_pmv,
                AggDemandFac, Splurge, LivPrb,
                newborn_aNrm, newborn_pLvl, newborn_mrkv,
                total_T, pLvl_unemp_mode, T_age_max,
            )
            AggInc_full.block_until_ready()
            # Discard warmup portion
            return AggInc_full[warmup_T:], AggCons_full[warmup_T:], cLvl_full[warmup_T:]
        else:
            master_key = random.PRNGKey(seed_base)
            period_keys = random.split(master_key, act_T)
            AggInc, AggCons, cLvl_panel = _simulate_jax_core(
                carry0, period_keys,
                cfunc_table, m_grid,
                Rfree, PermGroFac, MrkvArray,
                IncShk_psi, IncShk_xi, IncShk_pmv,
                AggDemandFac, Splurge, LivPrb,
                newborn_aNrm, newborn_pLvl, newborn_mrkv,
                act_T, pLvl_unemp_mode, T_age_max,
            )
            AggInc.block_until_ready()
            return AggInc, AggCons, cLvl_panel


# ============================================================
# Standalone test (validation only — small synthetic problem)
# ============================================================

def _synthetic_problem(seed=0, N=100, T=20, J=3, M_grid=200):
    """Build a tiny synthetic MC problem for testing."""
    rs = np.random.RandomState(seed)

    # cFunc table: monotone-increasing per-Mrkv-state consumption function
    m_grid = np.linspace(0.01, 50.0, M_grid).astype(np.float32)
    cfunc_table = np.empty((J, M_grid), dtype=np.float32)
    for j in range(J):
        # piecewise-linear: c = min(m, 0.5 + 0.3*j + 0.4*m) — different MPC by Mrkv
        cfunc_table[j] = np.minimum(m_grid, 0.5 + 0.3 * j + 0.4 * m_grid)

    # Initial states
    aNrm0 = rs.uniform(0.5, 2.0, size=N).astype(np.float32)
    pLvl0 = rs.uniform(0.8, 1.2, size=N).astype(np.float32)
    mrkv0 = rs.randint(0, J, size=N).astype(np.int32)

    # Parameters
    Rfree = np.full(J, 1.01, dtype=np.float32)
    PermGroFac = np.full(J, 1.005, dtype=np.float32)
    MrkvArray = np.tile(np.array([[0.9, 0.05, 0.05]], dtype=np.float32), (J, 1))
    MrkvArray = np.eye(J, dtype=np.float32) * 0.85 + 0.15 / J  # diag-heavy

    # IncShkDstn: 4 atoms per Mrkv state
    max_atoms = 4
    IncShk_psi = np.ones((J, max_atoms), dtype=np.float32)
    IncShk_xi  = np.array([[0.5, 0.9, 1.0, 1.1]] * J, dtype=np.float32)
    IncShk_pmv = np.array([[0.05, 0.25, 0.5, 0.2]] * J, dtype=np.float32)
    IncShk_pmv /= IncShk_pmv.sum(axis=-1, keepdims=True)
    IncShk_natoms = np.full(J, max_atoms, dtype=np.int32)

    AggDemandFac = 1.0
    Cratio = 1.0
    Splurge = 0.25
    LivPrb = 0.99

    # Newborn pool
    nb_N = 50
    newborn_aNrm = rs.uniform(0.0, 0.5, size=nb_N).astype(np.float32)
    newborn_pLvl = np.ones(nb_N, dtype=np.float32)
    newborn_mrkv = np.zeros(nb_N, dtype=np.int32)   # newborns all start employed

    return dict(
        aNrm0=aNrm0, pLvl0=pLvl0, mrkv0=mrkv0,
        cfunc_table=cfunc_table, m_grid=m_grid,
        Rfree=Rfree, PermGroFac=PermGroFac, MrkvArray=MrkvArray,
        IncShk_psi=IncShk_psi, IncShk_xi=IncShk_xi,
        IncShk_pmv=IncShk_pmv, IncShk_natoms=IncShk_natoms,
        AggDemandFac=AggDemandFac, Cratio=Cratio, Splurge=Splurge,
        LivPrb=LivPrb,
        newborn_aNrm=newborn_aNrm, newborn_pLvl=newborn_pLvl, newborn_mrkv=newborn_mrkv,
        act_T=T,
    )


def _bench_one(N, T, J, M_grid, seed=42, verbose=False):
    """Run numpy + JAX at a given size, return (wall_np, wall_jax, agreement)."""
    import time
    p = _synthetic_problem(seed=seed, N=N, T=T, J=J, M_grid=M_grid)
    t0 = time.time()
    np_inc, np_cons, np_cls = simulate_np(
        p['aNrm0'], p['pLvl0'], p['mrkv0'],
        p['cfunc_table'], p['m_grid'],
        p['Rfree'], p['PermGroFac'], p['MrkvArray'],
        p['IncShk_psi'], p['IncShk_xi'], p['IncShk_pmv'], p['IncShk_natoms'],
        p['AggDemandFac'], p['Cratio'], p['Splurge'], p['LivPrb'],
        p['newborn_aNrm'], p['newborn_pLvl'], p['newborn_mrkv'],
        p['act_T'], seed_base=12345)
    wall_np = time.time() - t0

    if not _HAS_JAX:
        return wall_np, float('nan'), float('nan')

    # JAX: warm up JIT, then time second call
    jax_args = (
        jnp.asarray(p['aNrm0']), jnp.asarray(p['pLvl0']), jnp.asarray(p['mrkv0']),
        jnp.asarray(p['cfunc_table']), jnp.asarray(p['m_grid']),
        jnp.asarray(p['Rfree']), jnp.asarray(p['PermGroFac']),
        jnp.asarray(p['MrkvArray']),
        jnp.asarray(p['IncShk_psi']), jnp.asarray(p['IncShk_xi']),
        jnp.asarray(p['IncShk_pmv']),
        p['AggDemandFac'], p['Cratio'], p['Splurge'], p['LivPrb'],
        jnp.asarray(p['newborn_aNrm']), jnp.asarray(p['newborn_pLvl']),
        jnp.asarray(p['newborn_mrkv']),
    )
    # Warm-up (first call includes JIT compile)
    out = simulate_jax(*jax_args, p['act_T'], seed_base=12345)
    # Timed: re-run, block on device only (no numpy conversion)
    t0 = time.time()
    out = simulate_jax(*jax_args, p['act_T'], seed_base=12345)
    # Block until GPU finishes (out[0] is np.asarray'd inside simulate_jax — that's our cost too)
    wall_jax = time.time() - t0
    jax_inc, jax_cons, jax_cls = out

    rel_inc = abs(np_inc.mean() - jax_inc.mean()) / (abs(np_inc.mean()) + 1e-12)
    return wall_np, wall_jax, rel_inc


if __name__ == '__main__':
    import time

    print("=== JAX MC minimal kernel — standalone validation ===")
    p = _synthetic_problem(seed=42, N=1000, T=30, J=4, M_grid=200)

    print(f"\n[1/3] Numpy reference sim (N={p['aNrm0'].shape[0]}, T={p['act_T']}, J={p['MrkvArray'].shape[0]})...")
    t0 = time.time()
    np_inc, np_cons, np_cls = simulate_np(
        p['aNrm0'], p['pLvl0'], p['mrkv0'],
        p['cfunc_table'], p['m_grid'],
        p['Rfree'], p['PermGroFac'], p['MrkvArray'],
        p['IncShk_psi'], p['IncShk_xi'], p['IncShk_pmv'], p['IncShk_natoms'],
        p['AggDemandFac'], p['Cratio'], p['Splurge'], p['LivPrb'],
        p['newborn_aNrm'], p['newborn_pLvl'], p['newborn_mrkv'],
        p['act_T'], seed_base=12345)
    wall_np = time.time() - t0
    print(f"  wall={wall_np:.3f}s")
    print(f"  AggInc[0..4]={np_inc[:5]}")
    print(f"  AggCons[0..4]={np_cons[:5]}")
    print(f"  AggInc.mean={np_inc.mean():.3f}, AggCons.mean={np_cons.mean():.3f}")

    if not _HAS_JAX:
        print("\nJAX not available — skipping JAX validation.")
    else:
        print(f"\n[2/3] JAX sim (same problem, same seed)...")
        # First call: includes JIT compile
        t0 = time.time()
        jax_inc, jax_cons, jax_cls = simulate_jax(
            p['aNrm0'], p['pLvl0'], p['mrkv0'],
            jnp.asarray(p['cfunc_table']), jnp.asarray(p['m_grid']),
            jnp.asarray(p['Rfree']), jnp.asarray(p['PermGroFac']),
            jnp.asarray(p['MrkvArray']),
            jnp.asarray(p['IncShk_psi']), jnp.asarray(p['IncShk_xi']),
            jnp.asarray(p['IncShk_pmv']),
            p['AggDemandFac'], p['Cratio'], p['Splurge'], p['LivPrb'],
            jnp.asarray(p['newborn_aNrm']), jnp.asarray(p['newborn_pLvl']),
            jnp.asarray(p['newborn_mrkv']),
            p['act_T'], seed_base=12345)
        wall_jax_first = time.time() - t0
        print(f"  wall (first call, includes JIT compile)={wall_jax_first:.3f}s")

        # Second call: cached
        t0 = time.time()
        jax_inc2, jax_cons2, jax_cls2 = simulate_jax(
            p['aNrm0'], p['pLvl0'], p['mrkv0'],
            jnp.asarray(p['cfunc_table']), jnp.asarray(p['m_grid']),
            jnp.asarray(p['Rfree']), jnp.asarray(p['PermGroFac']),
            jnp.asarray(p['MrkvArray']),
            jnp.asarray(p['IncShk_psi']), jnp.asarray(p['IncShk_xi']),
            jnp.asarray(p['IncShk_pmv']),
            p['AggDemandFac'], p['Cratio'], p['Splurge'], p['LivPrb'],
            jnp.asarray(p['newborn_aNrm']), jnp.asarray(p['newborn_pLvl']),
            jnp.asarray(p['newborn_mrkv']),
            p['act_T'], seed_base=12345)
        wall_jax2 = time.time() - t0
        print(f"  wall (second call, cached)={wall_jax2:.3f}s")
        print(f"  speedup numpy/JAX = {wall_np/wall_jax2:.1f}x")

        print(f"\n[3/3] Distributional comparison numpy vs JAX (different RNGs, so not bit-identical):")
        print(f"  AggInc mean: np={np_inc.mean():.3f}, jax={jax_inc.mean():.3f}, rel diff={abs(np_inc.mean()-jax_inc.mean())/abs(np_inc.mean()):.3%}")
        print(f"  AggCons mean: np={np_cons.mean():.3f}, jax={jax_cons.mean():.3f}, rel diff={abs(np_cons.mean()-jax_cons.mean())/abs(np_cons.mean()):.3%}")
        # Expect agreement within MC noise (~1/sqrt(N))
        rel_inc = abs(np_inc.mean()-jax_inc.mean())/abs(np_inc.mean())
        if rel_inc < 0.05:
            print(f"  ✓ AggInc agrees within 5% — distributional match plausible")
        else:
            print(f"  ⚠ AggInc differs by {rel_inc:.3%} — investigate")

    # Speedup sweep at HS_Only-like dimensions (T=40 J=6 M=200)
    print("\n=== Speedup sweep — small (T=40 J=6 M=200) ===")
    print(f"{'N':>8}  {'np wall':>10}  {'jax wall':>10}  {'speedup':>8}  {'rel diff':>10}")
    print('-' * 60)
    for N in [1000, 5000, 10000, 50000, 100000]:
        w_np, w_jax, rel = _bench_one(N=N, T=40, J=6, M_grid=200)
        sp = w_np / w_jax if w_jax > 0 else float('nan')
        print(f"{N:>8}  {w_np:>10.3f}s  {w_jax:>10.3f}s  {sp:>7.1f}x  {rel:>10.3%}")

    # Speedup sweep at HAFiscal-realistic dimensions (T=100 J=6 M=500)
    print("\n=== Speedup sweep — HAFiscal-realistic (T=100 J=6 M=500) ===")
    print(f"{'N':>8}  {'np wall':>10}  {'jax wall':>10}  {'speedup':>8}  {'rel diff':>10}")
    print('-' * 60)
    for N in [1800, 5940, 10000, 41580, 100000]:
        w_np, w_jax, rel = _bench_one(N=N, T=100, J=6, M_grid=500)
        sp = w_np / w_jax if w_jax > 0 else float('nan')
        print(f"{N:>8}  {w_np:>10.3f}s  {w_jax:>10.3f}s  {sp:>7.1f}x  {rel:>10.3%}")

    # Speedup sweep at larger-Mrkv (Baseline-like J — full has 168 combined states)
    # but for synthetic test use a more modest J=24 to keep numpy tractable
    print("\n=== Speedup sweep — many-Mrkv (T=100 J=24 M=500) ===")
    print(f"{'N':>8}  {'np wall':>10}  {'jax wall':>10}  {'speedup':>8}  {'rel diff':>10}")
    print('-' * 60)
    for N in [1800, 10000, 41580]:
        w_np, w_jax, rel = _bench_one(N=N, T=100, J=24, M_grid=500)
        sp = w_np / w_jax if w_jax > 0 else float('nan')
        print(f"{N:>8}  {w_np:>10.3f}s  {w_jax:>10.3f}s  {sp:>7.1f}x  {rel:>10.3%}")
