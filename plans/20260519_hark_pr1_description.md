# HARK PR-1 — Draft PR Description

**Branch (local, not pushed):** `gpu-jax-pr1-interpolation` in `/home/shared/github/econ-ark/HARK`
**Commit:** see `git log -1 gpu-jax-pr1-interpolation` (drafted 2026-05-19 night)
**Diffstat:** 2 files changed, 466 insertions, 0 deletions

---

## Proposed Title

`Add HARK.interpolation_jax — opt-in JAX counterparts to interpolation primitives`

## Proposed Body

### Summary

Adds a new opt-in module, `HARK.interpolation_jax`, that ports the
interpolation primitives used by `ConsAggShockModel`-style solvers to JAX.
The new module is functional (data + query arguments, no classes) so the
functions can be `vmap`-ed, `jit`-ed, and differentiated — the building
blocks needed for a GPU EGM solver in a follow-up PR.

### Why

- HAFiscal (Carroll et al.) has a working JAX EGM solver kernel for HARK's
  `solve_agg_cons_markov_alt` that validates to <1e-3 vs HARK at recession
  scale. The interpolation primitives in that kernel have lived as
  `HAFiscal/jax_hark_interp.py`. This PR upstreams them in HARK-quality
  shape so any downstream project can reuse them.
- Sets the foundation for **PR-2** (`ConsIndShockModelJAX`) and **PR-3**
  (`ConsAggShockModelJAX`), which are sketched in `plans/20260519_hark_gpu_pr_design.md`.

### What this PR is

- New module **`HARK/interpolation_jax.py`** (192 lines) — JAX counterparts
  to:
  - `LinearInterp` → `linear_interp_1d`
  - `BilinearInterp` → `bilinear_interp`, `bilinear_interp_derX`
  - `LinearInterpOnInterp1D` (shared x) → `linear_interp_on_interp_1d_shared_xgrid`
  - `LinearInterpOnInterp1D` (per-y x) → `linear_interp_on_interp_1d_general`
  - `LowerEnvelope2D` → `lower_envelope_2d_apply`
  - `VariableLowerBoundFunc2D` → `variable_lower_bound_eval`
  - `MargValueFuncCRRA` helpers → `marg_value_to_consumption`,
    `consumption_to_marg_value`
- New test module **`tests/test_interpolation_jax.py`** (8 tests) —
  bit-precision parity at 1e-10 relative tolerance against the existing
  numpy/numba implementations. Tests skip cleanly when JAX is not
  installed.

### What this PR is NOT

- **Not** a change to any existing module — no behavior change for users
  who don't import the new module.
- **Not** a new core dependency — JAX is optional, gated by a try/except
  import guard with a helpful install message.
- **Not** a solver — solver lives in PR-2.

### Comparability constraint

Per the design discussion in
`plans/20260519_hark_gpu_pr_design.md`, every JAX function has a 1:1
counterpart in `HARK.interpolation`. The test file's structure mirrors
this 1:1 pairing — each test compares the JAX value to the numpy/numba
value on the same inputs.

### Test results (local, HAFiscal venv with JAX installed)

```
tests/test_interpolation_jax.py::TestLinearInterp1DJax::test_lower_extrap PASSED
tests/test_interpolation_jax.py::TestLinearInterp1DJax::test_no_lower_extrap PASSED
tests/test_interpolation_jax.py::TestBilinearInterpJax::test_derivativeX PASSED
tests/test_interpolation_jax.py::TestBilinearInterpJax::test_value PASSED
tests/test_interpolation_jax.py::TestLinearInterpOnInterp1DJax::test_per_y_xgrid PASSED
tests/test_interpolation_jax.py::TestLinearInterpOnInterp1DJax::test_shared_xgrid PASSED
tests/test_interpolation_jax.py::TestLowerEnvelope2DJax::test_element_wise_min PASSED
tests/test_interpolation_jax.py::TestCRRAHelpersJax::test_inverse_roundtrip PASSED
============================== 8 passed in 4.72s ===============================
```

### Risk

Zero. The module adds new files; no existing imports change. Users who
don't `import HARK.interpolation_jax` see no difference.

### Follow-ups (not in this PR)

- **PR-2:** `ConsIndShockModelJAX` — JAX EGM for the basic single-state
  consumer (3-5 days).
- **PR-3:** `ConsAggShockModelJAX` — JAX EGM for the Markov + aggregate-state
  variant (matches HAFiscal's solver structure; 3-5 days).

---

## Notes for the reviewer

- **API choice:** functional vs class-based. Chose functional to keep
  `vmap`/`jit` mechanical; a class-wrapper layer can be added in PR-2 if
  HARK's solver API requires it for `ConsIndShockModelJAX`.
- **Search semantics:** `linear_interp_1d` deliberately mirrors HARK's
  `searchsorted(x_grid[:-1], ...)` quirk so above-top queries linearly
  extrapolate from the last segment rather than NaN. Documented inline.
- **`derivativeX` only:** `BilinearInterp` also exposes `derivativeY`; not
  ported here because the HAFiscal solver doesn't use it. Trivial to add
  in a follow-up if anyone needs it.

---

## Operational status

This PR description is **drafted but NOT pushed**. Per the user's
instruction "lets finish everything that is non-HARK before we propose
HARK fixes," the branch lives only locally at:

```
/home/shared/github/econ-ark/HARK   (branch: gpu-jax-pr1-interpolation)
```

To push and open the PR (when authorized):

```bash
cd /home/shared/github/econ-ark/HARK
git push -u origin gpu-jax-pr1-interpolation
gh pr create --title "..." --body "..."   # use the body above
```
