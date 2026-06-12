# HARK PR-2 — `ConsIndShockModelJAX` Scaffolding Plan

**Drafted:** 2026-05-19 night (overnight session)
**Status:** worktree set up, NOT pushed; awaiting user authorization at 9 AM.

## Worktree

```
/home/shared/github/econ-ark/HARK-pr2-ConsIndShockModelJAX
  branch: gpu-jax-pr2-ConsIndShockModelJAX
  base:   gpu-jax-pr1-interpolation  (PR-1 must merge first or this PR rebases)
```

Why a worktree: switching branches in the main HARK checkout breaks
HAFiscal (it imports `AggIndMrkvConsumerType` which exists only on
`bug-stratified-draws-mode`). The worktree leaves main HARK checkout
untouched.

## Scope (matches design doc `plans/20260519_hark_gpu_pr_design.md`)

JAX EGM solver for the **basic** `ConsIndShockModel` — single Markov state,
no aggregate state. Mirrors the existing `ConsIndShockModelFast.py` numba
opt-in pattern.

### Files to add

```
HARK/ConsumptionSaving/
  ConsIndShockModelJAX.py             # main module — ConsIndShockModelJAXSolver
                                      # + ConsIndShockTypeJAX wrapper class
tests/
  test_ConsIndShockModelJAX.py        # parity vs ConsIndShockModel + benchmark
```

### Class API (to match existing HARK pattern)

```python
# Reference (existing):
from HARK.ConsumptionSaving.ConsIndShockModel import ConsIndShockType
agent_ref = ConsIndShockType(**params)
agent_ref.solve()  # numpy/numba solver

# New (this PR):
from HARK.ConsumptionSaving.ConsIndShockModelJAX import ConsIndShockTypeJAX
agent_jax = ConsIndShockTypeJAX(**params)  # same API
agent_jax.solve()  # JAX solver
# Test: per-grid evaluation of agent_jax.solution[t].cFunc(m) matches
#       agent_ref.solution[t].cFunc(m) to 1e-6 or tighter
```

### Test pattern

```python
class TestConsIndShockModelJAXParity(unittest.TestCase):
    def test_steady_state_cfunc(self):
        """JAX vs numpy solver produce same cFunc at convergence."""
        # Use SmallTest params from existing ConsIndShockModel tests
        agent_np = ConsIndShockType(**params)
        agent_jax = ConsIndShockTypeJAX(**params)
        agent_np.solve()
        agent_jax.solve()
        m_grid = np.linspace(0.5, 50, 100)
        for t in range(len(agent_np.solution)):
            np_c = agent_np.solution[t].cFunc(m_grid)
            jax_c = np.asarray(agent_jax.solution[t].cFunc(m_grid))
            np.testing.assert_allclose(jax_c, np_c, rtol=1e-6)
```

## What's in PR-2 (vs PR-1 and HAFiscal)

| Component | PR-1 | PR-2 (this) | HAFiscal |
|---|---|---|---|
| Interp primitives | ✓ | — | uses PR-1 |
| EGM solver for ConsIndShockModel | — | **NEW** | — |
| EGM solver for AggIndMrkvModel | — | (PR-3) | uses HAFiscal-local `jax_solver_kernel.py` |
| Solver iteration loop | (HARK existing) | (HARK existing, Python) | (HARK existing, Python) |
| GPU device | — | (works via JAX) | — |

## Why this is non-trivial (estimate: 3-5 days)

1. **Class API mirroring.** HARK's `ConsIndShockType` has many config knobs;
   `ConsIndShockTypeJAX` must accept the same ones and produce a `solution`
   list with the same per-period structure. The JAX solver kernel itself
   is the easy part — the wrapper is what takes time.
2. **Per-period cFunc representation.** HARK stores `MetricObject`-derived
   `LinearInterp` instances. JAX equivalent must either:
   (a) wrap a JAX cFunc in a `LinearInterp`-compatible callable, or
   (b) provide a separate `LinearInterpJAX` class. Option (a) is simpler
   for parity but loses JAX's `jit` benefit at evaluation. Option (b)
   needs design.
3. **Validation matrix:** parity for at least three standard parameter
   sets (`PFexample`, `IndShockExample`, lifecycle), each at multiple
   timesteps, plus the existing HARK test fixtures.
4. **Benchmark.** PR description should include cold-start and
   warm-iteration timings, CPU and (if available) GPU.

## What's set up tonight (ready for 9 AM)

- Worktree at `HARK-pr2-ConsIndShockModelJAX`, branch
  `gpu-jax-pr2-ConsIndShockModelJAX` based on `gpu-jax-pr1-interpolation`.
- This plan doc (sketches the scope and test pattern).
- No code yet — this is genuinely 3-5 days of work and shouldn't be
  rushed overnight.

## Recommended next steps for user (at 9 AM)

1. **First decision:** push PR-1 to GitHub? It's done and tested. Open a
   PR using `plans/20260519_hark_pr1_description.md` as the body.
2. **Second decision:** authorize PR-2 work. If yes:
   - Hand the worktree to me with explicit "go ahead with PR-2."
   - Confirm: option (a) `LinearInterp` wrapper, or option (b) separate
     `LinearInterpJAX` class for the cFunc representation question above.
3. **Third decision:** PR-3 (`ConsAggShockModelJAX`) is the one HAFiscal
   actually consumes (it has aggregate Markov state). PR-2 is mostly a
   stepping stone. If we want to get to the HAFiscal-relevant solver
   fast, we could skip PR-2 and go straight to PR-3 — at the cost of a
   larger, harder-to-review PR.

## Files this plan references

- `plans/20260519_hark_gpu_pr_design.md` — overall 3-PR sequencing design
- `plans/20260519_hark_pr1_description.md` — PR-1 description draft
- `plans/20260519_jax_solver_port_plan.md` — original JAX solver porting plan
  (HAFiscal-local kernel that's been validated P1-P6)
- `conclusions_private/2026-05-19_overnight_session_summary.md` — overnight
  session log
