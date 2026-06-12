"""
JAX MC stratified-shuffle Mrkv transition.

Replicates HARK's _hit_with_recession_shock_shuffled + stratified-shuffle
(HARK PR #1776) semantics: per-state agent counts are deterministic (no
sampling noise), but per-agent identity assignment within each (src, dst)
bucket is randomized.

Approach B (from design doc): per-bucket masked permutation with J×J
static loop. For J=6, that's 36 inner iterations per step; each is
JIT-friendly via masked argsort.

Usage:
  mrkv_new = stratified_mrkv_transition(rng, mrkv_prev, MrkvArray, J)

Returns the new Mrkv micro state for each agent, with per-state counts
matching round(N_j * MrkvArray[j,k]) for each (j,k) pair (sum-adjusted
to N_j on the largest bucket per HARK's rounding rule).
"""
from __future__ import annotations
import numpy as np
import jax
import jax.numpy as jnp
from jax import lax, random
from functools import partial


@partial(jax.jit, static_argnames=('J',))
def stratified_mrkv_transition(rng, mrkv_prev, MrkvArray, J):
    """Stratified-shuffle Mrkv transition.

    Args:
      rng: JAX PRNG key (single key for per-agent permutation uniform draws)
      mrkv_prev: (N,) int32 — current micro Mrkv state per agent
      MrkvArray: (J, J) — transition probabilities from src to dst
      J: int (static) — number of micro states

    Returns:
      mrkv_new: (N,) int32 — destination micro state per agent, with per-state
                counts deterministically matching round(N_j * MrkvArray[j,k])
                (sum-adjusted to N_j on largest bucket).
    """
    N = mrkv_prev.shape[0]
    u = random.uniform(rng, (N,))  # one random number per agent — used as permutation key
    # Initialize destination as same-as-prev (will be overwritten)
    mrkv_new = mrkv_prev.astype(jnp.int32)

    # For each source state j: rank agents in source-j by u (gives random
    # permutation within the bucket), assign first N_j0 to dest 0, etc.
    for j in range(J):
        in_src_j = (mrkv_prev == j)
        N_j = jnp.sum(in_src_j).astype(jnp.int32)
        # Mask u to infinity for not-in-source-j agents, so argsort puts them last
        u_for_src = jnp.where(in_src_j, u, jnp.inf)
        # rank[i] = position of agent i within sorted u_for_src.
        # Avoid double-argsort (triggers JAX x64 int32/int64 scatter incompatibility).
        # Use scatter: sort_idx[k] = which agent ends up in sorted position k;
        # invert by scattering arange into sort_idx positions.
        sort_idx = jnp.argsort(u_for_src).astype(jnp.int32)
        N = u_for_src.shape[0]
        rank = jnp.zeros(N, dtype=jnp.int32).at[sort_idx].set(
            jnp.arange(N, dtype=jnp.int32))

        # Compute cumulative bucket sizes for source j
        Nj_probs = MrkvArray[j]  # (J,)
        N_jk_raw = jnp.round(N_j.astype(jnp.float32) * Nj_probs).astype(jnp.int32)
        diff = N_j - jnp.sum(N_jk_raw)
        largest_k = jnp.argmax(N_jk_raw).astype(jnp.int32)
        N_jk = N_jk_raw.at[largest_k].add(diff)

        # Cumulative threshold for state k
        cum_lo = jnp.concatenate([jnp.zeros(1, dtype=jnp.int32), jnp.cumsum(N_jk[:-1])])
        cum_hi = cum_lo + N_jk

        for k in range(J):
            assigned_to_k = in_src_j & (rank >= cum_lo[k]) & (rank < cum_hi[k])
            mrkv_new = jnp.where(assigned_to_k, k, mrkv_new)

    return mrkv_new


def stratified_mrkv_transition_np(mrkv_prev, MrkvArray, rng=None):
    """Numpy reference implementation for validation (matches the JAX version)."""
    rng = rng or np.random.default_rng(42)
    N = len(mrkv_prev)
    J = MrkvArray.shape[0]
    u = rng.uniform(size=N)
    mrkv_new = mrkv_prev.copy().astype(np.int32)

    for j in range(J):
        in_src_j = (mrkv_prev == j)
        N_j = int(in_src_j.sum())
        if N_j == 0:
            continue
        # Rank within source j
        u_for_src = np.where(in_src_j, u, np.inf)
        rank = np.argsort(np.argsort(u_for_src))

        Nj_probs = MrkvArray[j]
        N_jk_raw = np.round(N_j * Nj_probs).astype(np.int32)
        diff = N_j - int(N_jk_raw.sum())
        largest_k = int(np.argmax(N_jk_raw))
        N_jk = N_jk_raw.copy()
        N_jk[largest_k] += diff
        cum_lo = np.concatenate([[0], np.cumsum(N_jk[:-1])])
        cum_hi = cum_lo + N_jk

        for k in range(J):
            assigned_to_k = in_src_j & (rank >= cum_lo[k]) & (rank < cum_hi[k])
            mrkv_new = np.where(assigned_to_k, k, mrkv_new)

    return mrkv_new


def main():
    """Quick validation: check per-state counts match expected, multiple times."""
    np.random.seed(0)
    J = 6
    N = 1800

    # Realistic MrkvArray for HAFiscal (6 micro states under bug_fix)
    # Build one that mimics recession Mrkv structure
    MrkvArray = np.array([
        [0.93, 0.07, 0.00, 0.00, 0.00, 0.00],  # employed → mostly stay employed
        [0.50, 0.00, 0.50, 0.00, 0.00, 0.00],  # u1Q → either back to employed or u2Q
        [0.50, 0.00, 0.00, 0.50, 0.00, 0.00],  # u2Q → either back to employed or u3Q
        [0.50, 0.00, 0.00, 0.00, 0.50, 0.00],  # u3Q → either back to employed or u4Q
        [0.50, 0.00, 0.00, 0.00, 0.00, 0.50],  # u4Q → either back to employed or noBen
        [0.50, 0.00, 0.00, 0.00, 0.00, 0.50],  # noBen → either back to employed or stay noBen
    ])

    # Random initial Mrkv distribution: most employed, some unemployed
    init_probs = [0.92, 0.025, 0.02, 0.015, 0.01, 0.01]
    mrkv_prev = np.random.choice(J, size=N, p=init_probs).astype(np.int32)

    print(f"N={N}, J={J}")
    print(f"Initial Mrkv counts: {[int((mrkv_prev == j).sum()) for j in range(J)]}")

    # NumPy reference
    mrkv_new_np = stratified_mrkv_transition_np(mrkv_prev, MrkvArray,
                                                 np.random.default_rng(0))
    print(f"\nNumpy transition output counts: {[int((mrkv_new_np == k).sum()) for k in range(J)]}")

    # Per-source-state expected counts
    print(f"\nPer-source expected vs actual transition counts:")
    for j in range(J):
        N_j = int((mrkv_prev == j).sum())
        if N_j == 0:
            continue
        N_jk_raw = np.round(N_j * MrkvArray[j]).astype(int)
        diff = N_j - N_jk_raw.sum()
        largest_k = int(np.argmax(N_jk_raw))
        N_jk = N_jk_raw.copy()
        N_jk[largest_k] += diff
        actual = []
        for k in range(J):
            actual.append(int(((mrkv_prev == j) & (mrkv_new_np == k)).sum()))
        match = '✓' if list(actual) == list(N_jk) else '✗'
        print(f"  src={j} N_j={N_j} expected={N_jk.tolist()} actual={actual} {match}")

    # JAX version
    rng = random.PRNGKey(0)
    mrkv_new_jax = np.asarray(stratified_mrkv_transition(
        rng, jnp.asarray(mrkv_prev), jnp.asarray(MrkvArray, dtype=jnp.float32), J))
    print(f"\nJAX transition output counts: {[int((mrkv_new_jax == k).sum()) for k in range(J)]}")
    # JAX and numpy use different RNG, so per-agent assignments differ; per-state counts must match
    for j in range(J):
        N_j = int((mrkv_prev == j).sum())
        if N_j == 0:
            continue
        actual = [int(((mrkv_prev == j) & (mrkv_new_jax == k)).sum()) for k in range(J)]
        N_jk_raw = np.round(N_j * MrkvArray[j]).astype(int)
        diff = N_j - N_jk_raw.sum()
        largest_k = int(np.argmax(N_jk_raw))
        N_jk = N_jk_raw.copy()
        N_jk[largest_k] += diff
        match = '✓' if list(actual) == list(N_jk) else '✗'
        print(f"  src={j} JAX expected={N_jk.tolist()} actual={actual} {match}")


if __name__ == '__main__':
    main()
