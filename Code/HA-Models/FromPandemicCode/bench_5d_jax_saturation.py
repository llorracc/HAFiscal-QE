"""
Phase B.2.bench — vmap-vs-iterate micro-benchmark for JAX-GPU on a
synthetic 5D kernel that mimics the memory traffic of
welfare6_tm_joint5d._step_period_5d.

The synthetic kernel is NOT the production kernel. It runs the
same TENSOR SHAPES and roughly the same number of memory passes per
step, so its bandwidth profile is representative of where GPU
saturation is reached. The PRECISION of these timings should be
within ~2× of the eventual production kernel.

Synthetic per-step ops (×10 per step, ×11 steps per "duration"):
  - dist5d: (A, A, A, J, J) tensor
  - Tensor contraction against (J, J, J, J) joint Markov → (A, A, A, J, J)
  - Element-wise product with broadcast (J,) cFunc tabulation
  - Welfare integration: reduce-sum over selected axes → scalar
"""
from __future__ import annotations
import os, time
import numpy as np

# Configure precision before JAX import
_PRECISION = os.environ.get('BENCH_PRECISION', 'fp32').lower()
_USE_FP64 = _PRECISION == 'fp64'
if _USE_FP64:
    import jax
    jax.config.update('jax_enable_x64', True)
import jax
import jax.numpy as jnp


J = 24  # micro state size for HS_Only bug_fix encoding
N_STEPS_PER_DUR = 11
N_OPS_PER_STEP = 10  # tensor contractions per step


def _make_kernel(A, J):
    """Build a JIT'd single-period synthetic step.

    State: (A, A, A, J, J) dist5d.
    Outputs: new dist5d (same shape), welfare scalar.
    """
    dtype = jnp.float64 if _USE_FP64 else jnp.float32

    @jax.jit
    def step_kernel(dist5d, joint_markov, cFunc_pol, cFunc_none, cFunc_b):
        # Op 1: Contract dist5d with joint_markov over (j_pn, j_b) axes.
        # dist5d: (A, A, A, j_pn_src, j_b_src)
        # joint_markov: (j_pn_src, j_b_src, j_pn_dst, j_b_dst)
        # result: (A, A, A, j_pn_dst, j_b_dst)
        d_next = jnp.einsum('IJKpq,pqrs->IJKrs', dist5d, joint_markov)

        # Op 2-3: Multiply with cFunc tabulations (separable per axis)
        d_next = d_next * cFunc_pol[None, None, None, :, None]
        d_next = d_next * cFunc_none[None, None, None, :, None]
        d_next = d_next * cFunc_b[None, None, None, None, :]

        # Op 4-5: Renormalize and reduce to compute welfare scalar
        total_mass = jnp.sum(d_next)
        d_next = d_next / (total_mass + 1e-12)
        welfare = jnp.sum(d_next * (cFunc_pol[None, None, None, :, None] -
                                     cFunc_none[None, None, None, :, None]))

        # Op 6-10: Repeat (memory traffic should dominate)
        for _ in range(5):
            d_next = d_next * 1.001 - 0.0001
        return d_next, welfare

    return step_kernel


def _build_inputs(A, J, n_batch=1):
    """Build synthetic test inputs of the right shape."""
    dtype = np.float64 if _USE_FP64 else np.float32
    rng = np.random.default_rng(42)
    if n_batch == 1:
        dist5d = rng.random((A, A, A, J, J), dtype=dtype)
    else:
        dist5d = rng.random((n_batch, A, A, A, J, J), dtype=dtype)
    # Make joint_markov a proper transition matrix (rows sum to 1)
    joint_markov = rng.dirichlet(np.ones(J*J), size=(J, J)).reshape(J, J, J, J).astype(dtype)
    cFunc_pol = rng.random(J, dtype=dtype) + 0.1
    cFunc_none = rng.random(J, dtype=dtype) + 0.1
    cFunc_b = rng.random(J, dtype=dtype) + 0.1
    return dist5d, joint_markov, cFunc_pol, cFunc_none, cFunc_b


def _run_no_vmap(A, J, n_iters):
    """Single-instance: run step kernel n_iters times sequentially."""
    step = _make_kernel(A, J)
    dist5d, jm, cp, cn, cb = _build_inputs(A, J, n_batch=1)
    dist5d_j = jnp.asarray(dist5d)
    jm_j = jnp.asarray(jm)
    cp_j = jnp.asarray(cp)
    cn_j = jnp.asarray(cn)
    cb_j = jnp.asarray(cb)

    # Warmup
    d, _ = step(dist5d_j, jm_j, cp_j, cn_j, cb_j)
    d.block_until_ready()

    t0 = time.time()
    d = dist5d_j
    for _ in range(n_iters):
        d, _ = step(d, jm_j, cp_j, cn_j, cb_j)
    d.block_until_ready()
    return time.time() - t0


def _run_vmap(A, J, n_iters, n_batch):
    """vmap'd: run step kernel n_iters times with n_batch parallel instances."""
    step = _make_kernel(A, J)
    vstep = jax.jit(jax.vmap(step, in_axes=(0, None, None, None, None)))

    dist5d, jm, cp, cn, cb = _build_inputs(A, J, n_batch=n_batch)
    dist5d_j = jnp.asarray(dist5d)
    jm_j = jnp.asarray(jm)
    cp_j = jnp.asarray(cp)
    cn_j = jnp.asarray(cn)
    cb_j = jnp.asarray(cb)

    # Warmup
    d, _ = vstep(dist5d_j, jm_j, cp_j, cn_j, cb_j)
    d.block_until_ready()

    t0 = time.time()
    d = dist5d_j
    for _ in range(n_iters):
        d, _ = vstep(d, jm_j, cp_j, cn_j, cb_j)
    d.block_until_ready()
    return time.time() - t0


def main():
    print(f"=== Phase B.2.bench synthetic kernel saturation ===")
    print(f"  precision: {'FP64' if _USE_FP64 else 'FP32'}")
    print(f"  backend: {jax.default_backend()}")
    print(f"  devices: {jax.devices()}")
    print(f"  J={J}, steps_per_dur={N_STEPS_PER_DUR}")

    # n_iters represents "ops per duration" — total kernel invocations
    n_iters = N_STEPS_PER_DUR  # match the production kernel's per-duration step count

    # 22 = duration (11) × cell (2) — max useful vmap batch
    configs = [
        ('no-vmap', 1),
        ('cell-vmap(2)', 2),
        ('dur-vmap(11)', 11),
        ('full-vmap(22)', 22),
    ]

    bytes_per_elt = 8 if _USE_FP64 else 4
    peak_bandwidth_gbps = 716  # RTX 4080

    print()
    print(f"{'A':>4} {'config':>16} {'instance_GB':>12} {'batch_GB':>10} "
          f"{'iters':>7} {'wall_ms':>9} {'effective_GBps':>15} {'util%':>7}")
    print("-" * 100)

    for A in [50, 75, 100]:
        single_bytes = A**3 * J * J * bytes_per_elt
        single_gb = single_bytes / 1e9
        for label, n_batch in configs:
            batch_gb = single_gb * n_batch
            # Rough VRAM check: skip if > 14 GB (leave headroom)
            if batch_gb > 14:
                print(f"{A:>4} {label:>16} {single_gb:>12.3f} {batch_gb:>10.3f} "
                      f"{'-':>7} {'-':>9} {'OOM (skip)':>15} {'-':>7}")
                continue
            try:
                if n_batch == 1:
                    wall_s = _run_no_vmap(A, J, n_iters)
                else:
                    wall_s = _run_vmap(A, J, n_iters, n_batch)
                wall_ms = wall_s * 1000
                # Effective bandwidth: rough estimate of memory traffic per iteration
                # Each iteration reads dist5d, writes dist5d, plus ~10 more passes
                # ≈ 20 × batch_gb of traffic per iteration
                traffic_gb = 20 * batch_gb * n_iters
                eff_gbps = traffic_gb / wall_s
                util_pct = 100 * eff_gbps / peak_bandwidth_gbps
                print(f"{A:>4} {label:>16} {single_gb:>12.3f} {batch_gb:>10.3f} "
                      f"{n_iters:>7d} {wall_ms:>9.1f} {eff_gbps:>15.1f} {util_pct:>6.1f}%")
            except Exception as e:
                print(f"{A:>4} {label:>16}  ERR: {str(e)[:60]}")

    print()
    print("Interpretation:")
    print("  - util% > 70%: bandwidth-saturated; vmap won't help further")
    print("  - util% < 50%: not saturated; vmap should give speedup proportional to batch")
    print("  - util% between: partial benefit from vmap")


if __name__ == '__main__':
    main()
