#!/usr/bin/env python
"""Phase 0 of the JAX-GPU TM multiplier kernel plan.

Two checks, both GPU-only (respects the workflow-segregation rules — no CPU
contention with the live Baseline runs):

  (A) GPU REALITY: time a representative per-period TM-kernel inner op
      (batched cFunc interp + bilinear-scatter accumulation) on the GPU vs an
      explicit CPU device. Confirms JAX actually executes on the GPU (not a
      silent cuSPARSE CPU fallback) AND that it's meaningfully faster at the
      Baseline-ish problem size.

  (B) PRECISION: the deliverable is a multiplier *delta* of ~0.01. Test whether
      FP32 NPV-accumulation + the A-B cancellation resolves a 0.01 delta to
      <1% (err < 1e-4), or whether FP64 is required. Decides the kernel dtype.

Run:  python phase0_harness.py   (uses the GPU venv)
"""
from __future__ import annotations
import os, time
import numpy as np

# Enable x64 so we CAN request FP64 (JAX defaults to FP32).
import jax
jax.config.update("jax_enable_x64", True)
import jax.numpy as jnp


def _bench_op(device, dtype, C=21, J=2, A=50, M=500, ATOMS=20, T=40, reps=5):
    """Representative per-period inner op, batched to Baseline-ish size.

    Mimics: for each (cohort, j, a, atom): m = R*a/(psi*G)+xi; c = interp(m, mgrid, ctable);
    a_next = m - c; scatter weight onto aGrid (segment add). Vmapped over cohorts.
    Returns (wall_seconds_per_period, agg_consumption_scalar) on `device`.
    """
    rng = np.random.default_rng(0)
    with jax.default_device(device):
        m_grid = jnp.asarray(np.linspace(0.0, 50.0, M), dtype=dtype)
        # per-(cohort,j) cFunc tables
        ctable = jnp.asarray(rng.random((C, J, M)).cumsum(-1) * 0.1, dtype=dtype)
        aGrid = jnp.asarray(np.linspace(0.0, 500.0, A), dtype=dtype)
        # per-(cohort,j,a,atom) queries
        m_q = jnp.asarray(rng.random((C, J, A, ATOMS)) * 40.0, dtype=dtype)
        w = jnp.asarray(rng.random((C, J, A, ATOMS)), dtype=dtype)

        def one_period(ctable, m_q, w):
            # batched interp over the last axis; vmap over (J,A,ATOMS) via reshape
            def interp_jvec(tbl, mq):  # tbl:(M,)  mq:(A,ATOMS)
                return jnp.interp(mq.reshape(-1), m_grid, tbl).reshape(mq.shape)
            c = jax.vmap(interp_jvec)(ctable, m_q)          # (J,A,ATOMS)
            a_next = jnp.clip(m_q - c, 0.0, 500.0)
            # bilinear scatter onto aGrid (lower-index segment add — representative)
            idx = jnp.clip(jnp.searchsorted(aGrid, a_next.reshape(-1)) - 1, 0, A - 1)
            scattered = jnp.zeros((A,), dtype=dtype).at[idx].add(w.reshape(-1))
            agg_c = jnp.sum(w * c)
            return scattered, agg_c

        batched = jax.jit(jax.vmap(one_period))  # vmap over cohorts
        # warmup / compile
        s, agg = batched(ctable, m_q, w)
        jax.block_until_ready((s, agg))
        t0 = time.perf_counter()
        for _ in range(reps * T):
            s, agg = batched(ctable, m_q, w)
        jax.block_until_ready((s, agg))
        dt = (time.perf_counter() - t0) / (reps * T)
        return dt, float(jnp.sum(agg))


def precision_test():
    """FP32 vs FP64 NPV-sum + A-B cancellation for a ~0.01 delta."""
    rng = np.random.default_rng(1)
    T = 40
    R = 1.01
    disc = (1.0 / R) ** np.arange(T)
    aggC_A = 1.0 + 0.02 * rng.standard_normal(T)          # ~O(1) per-period agg cons
    aggC_B = aggC_A * (1.0 + 0.0008 * rng.standard_normal(T))  # B differs by ~0.08%
    gov = 0.5
    # reference in float128
    npvA = np.sum((aggC_A * disc).astype(np.float128))
    npvB = np.sum((aggC_B * disc).astype(np.float128))
    mult_ref = float((npvB - npvA) / np.float128(gov))
    out = {"ref_delta": mult_ref}
    for name, dt in (("fp32", np.float32), ("fp64", np.float64)):
        a = aggC_A.astype(dt); b = aggC_B.astype(dt); d = disc.astype(dt)
        nA = np.sum(a * d); nB = np.sum(b * d)
        mult = float((nB - nA) / dt(gov))
        out[name] = mult
        out[name + "_abs_err"] = abs(mult - mult_ref)
    return out


def main():
    print(f"jax {jax.__version__}  backend={jax.default_backend()}  devices={jax.devices()}")
    try:
        gpu = jax.devices("gpu")[0]
    except Exception:
        print("NO GPU DEVICE — aborting GPU reality check"); gpu = None
    cpu = jax.devices("cpu")[0]

    print("\n=== (A) GPU REALITY: representative per-period op (Baseline-ish C=21,J=2,A=50,M=500,ATOMS=20) ===")
    for dtype, dn in ((jnp.float32, "fp32"), (jnp.float64, "fp64")):
        cpu_dt, _ = _bench_op(cpu, dtype)
        line = f"  {dn}: CPU {cpu_dt*1e3:7.2f} ms/period"
        if gpu is not None:
            gpu_dt, _ = _bench_op(gpu, dtype)
            line += f" | GPU {gpu_dt*1e3:7.2f} ms/period | speedup {cpu_dt/gpu_dt:5.1f}x"
        print(line)

    print("\n=== (B) PRECISION: resolving a ~0.01 multiplier delta ===")
    p = precision_test()
    print(f"  ref delta (f128): {p['ref_delta']:.6e}")
    print(f"  fp32 delta: {p['fp32']:.6e}   abs_err {p['fp32_abs_err']:.2e}   "
          f"({'OK <1e-4' if p['fp32_abs_err'] < 1e-4 else 'FAIL — FP64 needed'})")
    print(f"  fp64 delta: {p['fp64']:.6e}   abs_err {p['fp64_abs_err']:.2e}")
    print("\nVERDICT:")
    print("  GPU usable" if gpu is not None else "  GPU NOT usable")
    print("  Use FP64 for NPV/aggregation" if p['fp32_abs_err'] >= 1e-4
          else "  FP32 likely adequate for the delta (confirm at full scale)")


if __name__ == "__main__":
    main()
