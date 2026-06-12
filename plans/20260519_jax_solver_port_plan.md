# JAX Solver Port — Implementation Plan

**Started:** 2026-05-19
**Goal:** Port `solve_agg_cons_markov_alt` (`AggFiscalModel.py:1704-1887`) to JAX. Unlock end-to-end ~40-60× speedup vs CPU baseline by eliminating the solver bottleneck (~94% of wall time at Baseline-5×).
**Reference feasibility report:** `conclusions_private/2026-05-19_hark_solver_jax_port_feasibility.md`
**Estimate:** 7-11 working days. Parallelism via background validation runs and 1-2 worktree sub-agents.

## Approach
**Substitution, not integration.** Replace the local 184-LOC numpy function with a JAX equivalent. Install via `agent.solve_one_period = solve_agg_cons_markov_jax` behind a flag. Keep numpy version as the bit-by-bit validation oracle. Zero HARK upstream changes.

## Phases

### P1. JAX interpolation utilities (1.0 day)
- `jax_hark_interp.py` — JAX implementations of:
  - `LinearInterp` 1-D: searchsorted + linear blend
  - `BilinearInterp` 2-D: 4-corner searchsorted + bilinear blend
  - `LinearInterpOnInterp1D` over Cgrid: bilinear via fixed (m, C) grid (skip per-Cratio func objects per feasibility risk 6.3)
  - `LowerEnvelope2D`: `jnp.minimum` wrapper
  - `VariableLowerBoundFunc2D`: subtract `BoroCnstNat(C)` inside wrapped call
  - `MargValueFuncCRRA` semantics: raise to `-1/ρ`
- Unit-test each vs HARK ref on random inputs (target 1e-10 rel-precision)
- **Parallelism opportunity:** spawn separate background tests per interp type

### P2. Standalone single-Markov-state EGM (1.0 day)
- `jax_solver_kernel.py` — single-state EGM (drop to Ccount=1)
- Validate vs `solve_one_period` on a stripped problem (single Markov state, no Cratio dim)
- Target: cFunc bit-comparable to numpy ref at single beta atom

### P3. Add Cratio dimension (1.5 days)
- Extend kernel to (aCount, Ccount) tensor cFunc
- 2-D EndOfPrdvP via `BilinearInterp` of `EndOfPrdvPnvrs` on (aXtraGrid, Cgrid)
- Vmap over Cgrid (only 3 points — trivial)
- Validate vs HARK at single Markov state, full (aCount, Ccount) cFunc table

### P4. Multi-Markov-state extension (1.5 days)
- Vmap outer (next-state j) and inner (this-state i) over StateCount=168
- Mask sparse transitions via `jnp.where(MrkvArray[i,j] > 0, ..., 0.0)` (no early-skip)
- Envelope/constraint ops: `jnp.minimum(cFunc_unconstrained, cFuncCnst)`
- Validate vs HARK on full per-period solve at Reduced_Run scale (StateCount=88)

### P5. Drop-in wrapper (1.5 days)
- `solve_agg_cons_markov_jax(...)` matching signature of numpy ref
- Backward-induction loop: `lax.scan` over cycles (for finite-horizon) or Python loop with warm-start (infinite-horizon, our case)
- cFunc table cached per period for downstream JAX MC consumption
- Hook: `agent.solve_one_period = solve_agg_cons_markov_jax` behind `HAFISCAL_USE_JAX_SOLVER=1` flag

### P6. Validation (1.5 days)
- Cases: {HS_Only, Reduced_Run, Baseline} × {recession, recessionCheck, recessionUI, recessionTaxCut} = 12 runs
- Targets: cFunc rel-diff <1e-4 on values; AD-iter convergence count diff ≤±1; final Cratio within MC noise
- **Parallelism opportunity:** Background validation runs as soon as P4 lands (single Markov state) and after P5 (full)
- Validation report: `conclusions_private/2026-05-19_jax_solver_port_validation.md`

### P7. Integration + production flag (0.5 day)
- Wire flag into `welfare6_scenario.py` and CLI
- Update CLAUDE.md JAX MC section
- Benchmark Baseline-5× end-to-end with solver + MC both on JAX

**Total:** 8.5 nominal days, +30% AD-convergence buffer → 11 days. With background parallelism: ~7 calendar days.

## Risks (from feasibility report §6)
- **R6.1:** AD-loop convergence under JAX numerics — mitigate via `enable_x64` (already standard)
- **R6.2:** Boundary handling in `VariableLowerBoundFunc2D` composition — unit-test boundaries explicitly in P1
- **R6.3:** `LinearInterpOnInterp1D` semantics with per-Cratio m-grid — sidestep by tabulating on fixed eval grid
- **R6.4:** Sparse Markov mask cost — 200M flops/cycle is GPU-friendly, no concern
- **R6.5:** `IncShkDstn` tensorization — materialize at solve entry, trivial
- **R6.6:** HARK regression — zero risk (pure substitution)
- **R6.7:** Validation cost — single-cohort first (3 min/case), full at end of P6

## First action
Start P1: JAX interp utilities. The success of #6 today (JAX kernel matching HARK to 0.18%) confirms the broader approach. Bilinear + LinearInterpOnInterp1D are the trickiest pieces — get them right with explicit boundary tests before building anything on top.
