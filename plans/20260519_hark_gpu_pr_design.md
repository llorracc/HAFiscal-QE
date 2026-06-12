# HARK GPU PR — Design Discussion

**Date:** 2026-05-19 (drafted while parallel-solve benchmark running)
**Goal:** Per user's request, design a PR to HARK that adds GPU-accelerated solver, structured so that:
  - (a) Available but **not** the default — existing HARK uses unchanged
  - (b) Structured for **direct comparisons** to existing HARK methods

## Tech-stack choice

User mentioned numba.cuda OR cupy as candidates. Adding JAX as a third option since we already have a validated JAX solver kernel from #7 P1-P6.

| Option | Pros | Cons | Validated? |
|---|---|---|---|
| **JAX** | GPU+CPU+TPU portable; auto-grad available; already-validated kernel from #7 P1-P6; modern PyData alignment | New HARK dep; JIT overhead on small problems | Yes — kernel matches HARK <1e-3 |
| **numba.cuda** | Closest to HARK's existing numba pattern (`ConsIndShockModelFast`); explicit GPU kernels; can be very fast | Requires NVIDIA-only; explicit CUDA programming; restricted Python subset | No |
| **cupy** | numpy-API on GPU (cleanest API change); minimal code rewrites | No JIT/compile-time optimization; less flexible than JAX | No |

**Recommendation: JAX**. We have ~95% of the work done already (#7 P1-P6 ships the validated kernel + drop-in wrapper). Numba.cuda would mean rewriting everything; cupy gives less optimization headroom.

## PR architecture (mirrors HARK's existing pattern)

HARK already has `ConsIndShockModelFast` as a numba-accelerated opt-in alternative to `ConsIndShockModel`. We follow the same pattern:

```
HARK/
├── interpolation.py              # existing — numpy LinearInterp, BilinearInterp, etc.
├── interpolation_jax.py          # NEW — JAX equivalents (from jax_hark_interp.py)
├── ConsumptionSaving/
│   ├── ConsIndShockModel.py      # existing — default solver
│   ├── ConsIndShockModelFast.py  # existing — numba-accelerated opt-in
│   ├── ConsIndShockModelJAX.py   # NEW — JAX-accelerated opt-in (CPU+GPU)
└── tests/
    ├── test_interpolation.py     # existing
    ├── test_interpolation_jax.py # NEW — bit-precision parity vs numpy
    └── test_ConsIndShockModelJAX.py  # NEW — vs ConsIndShockModel parity + benchmark
```

**Key principle:** every JAX class/function has a 1:1 counterpart in the numpy/numba version. Tests compare element-wise.

## Suggested PR sequencing

### PR-1: `interpolation_jax` (smallest, cleanest)
- Scope: just the interp primitives (LinearInterp, BilinearInterp, +derX, LinearInterpOnInterp1D shared & general, LowerEnvelope2D, MargValueFuncCRRA)
- Code: `interpolation_jax.py` ports `jax_hark_interp.py` from HAFiscal
- Tests: 8 bit-precision parity tests vs existing HARK interp (we have these working at 1e-10)
- Risk: zero — adds new opt-in module, no existing code changes
- Effort: 1 day (mostly polishing for HARK code style + docstrings)

### PR-2: `ConsIndShockModelJAX` (single-state EGM)
- Scope: JAX EGM solver for the basic ConsIndShockModel (single Markov state, no aggregate state)
- Code: `ConsIndShockModelJAX.py` with `ConsIndShockModelJAXSolver` class
- Tests: bit-precision parity vs `ConsIndShockModel` on standard test problems + benchmark
- Risk: medium — exposing JAX solver in HARK requires careful API matching
- Effort: 3-5 days

### PR-3: `ConsAggShockModelJAX` (Markov + aggregate state) — optional follow-up
- Scope: JAX solver for the Markov + aggregate-state version
- Closer to what HAFiscal needs (Cratio + ADF still HAFiscal-specific)
- Effort: 3-5 days

For HAFiscal: PR-1 gets us the interp primitives. The HAFiscal solver
(jax_solver_kernel.py) stays in HAFiscal but uses HARK's PR-1
`interpolation_jax` instead of `jax_hark_interp.py`.

## Comparability constraints (user's (b))

For direct comparisons, EVERY component must have a 1:1 numpy counterpart:

- `interpolation_jax.linear_interp_1d(x_grid, y_vals, x_query)` ↔ `HARK.interpolation.LinearInterp(x_grid, y_vals)(x_query)`
- `interpolation_jax.bilinear_interp(f, x, y, xq, yq)` ↔ `HARK.interpolation.BilinearInterp(f, x, y)(xq, yq)`
- `ConsIndShockModelJAX.solve_one_period_jax(...)` ↔ `ConsIndShockModel.solve_one_period(...)`

Test pattern (mirroring HARK convention):
```python
def test_LinearInterp_parity_jax_vs_numpy(self):
    x_grid = np.linspace(0, 10, 20)
    y_vals = np.sin(x_grid)
    x_query = np.linspace(1, 9, 100)
    np_val = LinearInterp(x_grid, y_vals)(x_query)
    jax_val = np.asarray(linear_interp_1d(x_grid, y_vals, x_query))
    np.testing.assert_allclose(jax_val, np_val, rtol=1e-10)
```

## "Available but not the default" mechanism

Standard Python import idiom:

```python
# User code (unchanged HARK behavior — default)
from HARK.ConsumptionSaving.ConsIndShockModel import ConsIndShockType
agent = ConsIndShockType(**params)
agent.solve()  # uses default numpy solver

# Opt-in JAX (explicit)
from HARK.ConsumptionSaving.ConsIndShockModelJAX import ConsIndShockTypeJAX
agent = ConsIndShockTypeJAX(**params)  # same API
agent.solve()  # uses JAX solver
```

JAX is in `requirements-optional.txt` (not core dependencies). Import of `ConsIndShockModelJAX` fails with helpful error if JAX not installed:
```python
try:
    import jax
except ImportError:
    raise ImportError(
        "ConsIndShockModelJAX requires JAX. Install with: pip install jax"
    )
```

## Recommendation

**Start with PR-1 (interpolation_jax).** It's tiny, low-risk, validated, and gives HAFiscal everything it needs for clean upstream dependency. PR-2/PR-3 can follow once PR-1 lands.

PR-1 estimated effort: ~1 day (polish docstrings, add tests, write PR description).
