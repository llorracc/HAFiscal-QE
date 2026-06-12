---
date: 2026-05-02
status: phases-A-through-E-complete-Phase-F-in-flight
keywords: [BUG-039, GICx, NM-optimization, Step-2, hardcoded-cap, two-phase, EstimAggFiscalMAIN, estim_phase2_tm_a, warm-start, multistart-parallelism]
related_bugs: [BUG-039, BUG-034, BUG-036]
related_plans: []
---

> **Execution status (2026-05-02 ~16:07 EDT):**
> - Phase A+B+C (HAFISCAL_GICX_MODE dispatch in both estimators + comments): ✅ landed in commit 5dbd1a63
> - Phase D Tier 0 (single-eval sanity for all 3 modes): ✅ passed
> - Phase D Tier 1 (HS hardcoded re-anchor): ✅ passed (β=0.9001, ∇=0.1068, distance=1.742, wall=63 min, -32% vs legacy 92 min). Documented in dossier §5.2.
> - Phase E (HS warm-start round-trip): ✅ passed (same β/∇, NM 38.9 min, total 46.8 min = -33% vs Tier 1). Landed in 38aaff32 + bug fix in 3a5a77a1. Documented in dossier §5.3.
> - Phase F (D parallel multistart): ⏳ in flight, 4 subprocesses running, expected completion ~17:55 EDT.
> - Phase G (default cut-over recommendation): draft pending Phase F results, see `conclusions_private/2026-05-02_BUG-039_phase-g-default-cutover-recommendation.md`.

# Fix BUG-039 + Step-2 estimation speedups

## Background

Per `BUGS_private/HAFiscal_BUG-039_GICx_unconditionally_optimized.md`,
the per-cohort Nelder-Mead optimizer in Step-2 estimation searches over
3-D `(β, ∇, GICx)`. The third dimension corresponds to a per-cohort GIC
cap factor that NM is allowed to choose — but NM has no economic
rationale for the choice; it just uses GICx as a generic fit knob.

The codebase has two clipping mechanisms (see BUG-039 §0):
- **Mechanism 1 (module load)**: `theGICfactor=0.999` constant; max β ≤
  99.9% of cusp; same for all cohorts; well-justified by mixing
  measurements in commit `f6b7a2d6`
- **Mechanism 2 (per-cohort NM)**: variable factor
  `exp(GICx)/(1+exp(GICx))`, NM-chosen, can be anywhere from 0% to
  100%; no mixing rationale, just a fit knob

This plan implements the core BUG-039 fix (eliminating Mechanism 2 in
favor of a single principled cap) AND adds several Step-2 estimation
speedups that are independently useful.

## Goal

Two deliverables:

1. **Core BUG-039 fix**: introduce `HAFISCAL_GICX_MODE = legacy |
   hardcoded | twophase` env var. **Option A (`hardcoded`) is the
   recommended path** — it drops GICx as a free parameter entirely,
   pinning the cap at the same `theGICfactor=0.999` used at module
   load. This eliminates Mechanism 2 cleanly. Options B and C from the
   BUG-039 dossier (twophase, document-only) are kept as alternatives.

2. **Companion estimation speedups** (independently useful, not
   strictly part of BUG-039):
   - **Smarter starting points**: warm-start NM from the most recent
     saved DiscFacEstim values when available (instead of hardcoded
     legacy defaults)
   - **Parallel multistart**: run multistart points within a cohort
     concurrently as subprocesses (currently sequential)

A separate plan
(`plans/20260502-1256h_reproduce-sh-profile-machinery.md`) covers the
`reproduce.sh --profile NAME` machinery that bundles the methodological
choices (BUG-039 GICx mode, interpretation, Step-2 method, etc.) into
named profiles. That plan is independent and can be executed without
this one (three of its five profiles have no BUG-039 dependency).

Solver-side speedups (Bellman warm-start) are already done — the
`AggregateDemandEconomy.solve(warm_start=True)` in `AggFiscalModel.py`
reuses the prior NM iteration's value function across NM steps. Some
additional levers exist (looser per-Bellman tolerance, skip-solve when
DiscFac change is tiny) but are out of scope for this plan; flagged as
future work in §"Out of scope" below.

## Out of scope

- Don't change the GIC formula itself (`GICmaxBetas` calculation)
- Don't change the cap-clipping logic in the objective (just change
  the factor used)
- Don't change the Mechanism 1 module-load default (`theGICfactor =
  0.999` stays as-is)
- Don't loosen per-Bellman solver tolerance (already-done speedups are
  good enough; further tightening this lever needs separate validation)
- Don't implement skip-solve-when-DiscFac-change-is-tiny optimization
  (delicate; could mis-cache stale cFunc; defer)

## Constraints

- Default behavior unchanged until validation passes
  (`HAFISCAL_GICX_MODE` defaults to `legacy`; warm-start-from-saved
  is opt-in via separate env var; multistart-parallelism is opt-in
  via separate env var)
- Same (β, ∇) within reasonable tolerance as legacy when GICx was
  non-binding under legacy
- May produce slightly different (β, ∇) when legacy GICx tightened
  beyond 0.999 (e.g., HS in 2026-05-02 re-anchor); empirical magnitude
  measured by validation
- Works for all 3 cohorts and both estimators
  (`EstimAggFiscalMAIN.py` and `estim_phase2_tm_a.py`)

## Approach

### Phase A: Implement Option A (hardcoded-cap) in EstimAggFiscalMAIN.py (~45 min)

Site: `EstimAggFiscalMAIN.py:1252-1310` (multistart / NM-call block).

```python
GICX_MODE = os.environ.get('HAFISCAL_GICX_MODE', 'legacy')

if GICX_MODE == 'hardcoded':
    # Option A: 2-D NM, cap fixed at theGICfactor=0.999 (matches module-load)
    from EstimParameters import theGICfactor
    GICx_fixed = np.log(theGICfactor / (1 - theGICfactor))   # logit(0.999)

    f_temp = lambda x : betas_obj_func_educ(x[0], x[1], GICx_fixed, educ_type=edType)
    _starts = [s[:2] for s in _starts]   # drop GICx from starting points

    for _k, _x0 in enumerate(_starts):
        _opt_2d = minimize_nelder_mead(f_temp, _x0, **_nm_kwargs)
        _opt = np.array([_opt_2d[0], _opt_2d[1], GICx_fixed])
        # ...rest of multistart bookkeeping unchanged

elif GICX_MODE == 'twophase':
    # Option B (alternative): 2-D first, conditional 3-D refinement if cap binds
    GICx_default = np.log(theGICfactor / (1 - theGICfactor))
    f_2d = lambda x: betas_obj_func_educ(x[0], x[1], GICx_default, educ_type=edType)
    opt_2d = minimize_nelder_mead(f_2d, _x0[:2], **_nm_kwargs)
    beta_p, spread_p = opt_2d
    dfs_p = Uniform(beta_p - spread_p, beta_p + spread_p).discretize(DiscFacCount)
    cap_p = GICmaxBetas[edType] * theGICfactor
    if max(dfs_p.atoms[0]) > cap_p:
        f_3d = lambda x: betas_obj_func_educ(x[0], x[1], x[2], educ_type=edType)
        _opt = minimize_nelder_mead(f_3d, [beta_p, spread_p, GICx_default], **_nm_kwargs)
    else:
        _opt = np.array([beta_p, spread_p, GICx_default])

else:  # 'legacy' or unknown
    # Current 3-D unconditional behavior (unchanged)
    f_temp = lambda x : betas_obj_func_educ(x[0], x[1], x[2], educ_type=edType)
    _opt = minimize_nelder_mead(f_temp, _x0, **_nm_kwargs)
```

**Why Option A is preferred**:
- Eliminates the structurally weird "free GICx" knob entirely
- Cap factor is now consistent everywhere in the pipeline (0.999)
- NM goes from 3-D to 2-D, saving ~25-30% iterations
- Reported calibration is unambiguous: `(β, ∇)` fit at the fixed 0.999 ceiling

**Alternatives if Option A creates trajectory issues** (deferred unless
Phase D validation surfaces problems):

- **Option H — Sigmoid reparameterization**: replace clip-in-objective
  with `β_top = 0.999 × cusp × sigmoid(z_top)`. NM searches over
  `(z_top, β_low)`; the constraint is automatic via the sigmoid.
  Converged optimum same as Option A (mathematically equivalent at
  the optimum), but trajectory is geometrically different —
  potentially slower when cap is binding tightly (sigmoid compresses
  gradient near saturation), potentially same/faster when cap is
  non-binding (smooth-everywhere objective).

- **Option I — scipy's bounded NM**: use `scipy.optimize.minimize`
  with `method='Nelder-Mead'` and explicit
  `bounds=[(β_lo, β_hi), (∇_lo, ∇_hi)]` for the box-bounded portion of
  the constraint. Bypasses HARK's `minimize_nelder_mead` wrapper
  (which uses the older `fmin` API without bounds support). Cleanest
  numerical handling at the box-bound boundaries. Does not natively
  support the LINEAR constraint `β + (6/7)∇ ≤ 0.999 × cusp` — that
  piece would still need clip-in-objective.

Speed expectations (per discussion in BUG-039 dossier §4 and the
2026-05-02 conversation): **all three within ~10-20% of each other**;
the dominant ~25-30% speedup is from going 3-D → 2-D, not from which
2-D variant is used. Start with Option A (smallest code change). If
validation shows trajectory issues (e.g., NM stuck on the boundary,
or unexplained convergence failures), promote H or I.

### Phase B: Mirror in estim_phase2_tm_a.py (~20 min)

Same `HAFISCAL_GICX_MODE` dispatch at site `estim_phase2_tm_a.py:225`.
Smaller diff because this script has no multistart support; just wrap
the single `minimize_nelder_mead` call.

### Phase C: Documentation (~15 min)

Update the in-place comments at both NM call sites (added in commit
`dcf1b3f6`) to describe the three modes.

### Phase D: Validation of Option A (~3 hours compute, parallel by cohort)

**Tier 0** (~10 min): single-eval sanity for all 3 modes at saved
post-re-anchor values for HS. Confirm `legacy` gives saved values;
`hardcoded` produces a slightly different output (since cap=0.999 is
LOOSER than NM's chosen 0.986); `twophase` correctly detects binding
and runs Phase 2.

**Tier 1** (~3 hours compute): full re-anchor for each cohort under
`HAFISCAL_GICX_MODE=hardcoded`. Compare to today's legacy re-anchor:

| Cohort | Legacy (β, ∇, GICx) | Hardcoded (β, ∇) | Δβ | Δdistance | Δwall |
|---|---|---|---|---|---|
| D  | (0.6628, 0.3839, 6.13) | TBD | TBD | TBD | TBD |
| HS | (0.8997, 0.1109, 4.26) | TBD | TBD | TBD | TBD |
| C  | (0.9782, 0.0274, 4.92) | TBD | TBD | TBD | TBD |

**Acceptance**: Δβ < 5% on all cohorts; distance increase < 50%;
wall time savings ~30 min/cohort. If hardcoded produces large shifts
(suggesting NM's tighter-cap flexibility was doing important work),
fall back to twophase.

### Phase E (NEW): Smarter starting points (~30 min implementation + Tier-1 validation)

Currently `_legacy_default = {0: [0.75, 0.3, 6], 1: [0.93, 0.07, 5], 2:
[0.98, 0.015, 6]}` are heuristic. Better: warm-start from the saved
`DiscFacEstim_CRRA_2.0_R_1.01.txt` when available.

```python
# Site: EstimAggFiscalMAIN.py near _legacy_default
USE_SAVED_AS_START = os.environ.get('HAFISCAL_NM_START_FROM_SAVED', '0') == '1'

if USE_SAVED_AS_START:
    saved = _read_saved_DiscFacEstim()  # parse the .txt file
    if saved is not None and edType in saved:
        warm_start = [saved[edType]['beta'], saved[edType]['nabla'], saved[edType]['GICx']]
        _starts.insert(0, warm_start)  # prepend so it's tried first in multistart
```

**Speedup**: 30-50% reduction in NM iterations when saved values are
close to the new optimum. Risk: if a code change has shifted the
optimum, warm-start could mis-converge — mitigated by combining with
multistart (other starting points still get tried).

**Validation**: re-run HS-only re-anchor with warm-start enabled vs
disabled; compare wall time and converged values. Expect same
converged values, ~30-50% fewer iterations.

### Phase F (NEW): Parallel multistart within a cohort (~1 hr implementation + validation)

Currently multistart points within a cohort run sequentially (per the
for-loop at `EstimAggFiscalMAIN.py:1306`). For Dropout with 4 starts,
this is 4× the wall time of a single start. Subprocess parallelism
(one subprocess per multistart point, similar to
`run_phase2_parallel.py`'s cross-cohort approach) reduces this to max
instead of sum.

**Implementation**: extend `run_phase2_parallel.py` to support
`HAFISCAL_WRAPPER_MULTISTART_POINTS` env var. Each combo of (cohort,
multistart-point) becomes its own subprocess; outputs go to
`*_edType{N}_start{K}.txt` files; wrapper merges by selecting the
best basin per cohort.

**Speedup**: D with 4 multistart points goes from ~6 hr to ~1.5 hr
wall (4× speedup on D, no change on HS/C since they have 3/2 starts
and aren't bottleneck).

**Memory cost**: 4× memory for D (4 simultaneous EstimAggFiscalMAIN
processes). HARK 0.17.x process is ~2-3 GB RAM each → 8-12 GB peak
for D alone. With existing cross-cohort parallelism (3 subprocesses
for D + HS + C), peak could be 10-15 GB. Should fit on most modern
workstations but worth measuring.

**Validation**: re-run BUG-036 multistart for D with parallel vs
sequential; compare wall time and converged best-basin parameters.
Expect same best basin selected, wall time ~25% of sequential.

### Phase G: Default cut-over (separate decision after Phase D + E + F validate)

After all validations pass, propose:
- `HAFISCAL_GICX_MODE = hardcoded` becomes default
- `HAFISCAL_NM_START_FROM_SAVED = 1` becomes default (with multistart
  fallback for safety)
- Multistart parallelism becomes default in `run_phase2_parallel.py`

Each is a separate decision; this plan stops at Phase F.

**Note**: an earlier draft of this plan included a Phase H covering
`reproduce.sh --profile NAME` machinery that bundles methodological
choices (BUG-039 GICx mode + interpretation + Step-2 method + warm-start
+ multistart parallelism, etc.) into named profiles like `qe_fidelity`,
`production_fast`, `tm_throughout_fast`. That work has been extracted
into a standalone plan: `plans/20260502-1256h_reproduce-sh-profile-machinery.md`.

The standalone plan can be executed independently of this one. Three of
its five profiles (`qe_fidelity`, `production_current`, `mc_throughout_validation`)
have no dependency on BUG-039; the other two (`production_fast`,
`tm_throughout_fast`) depend on Phases A, E, F here.

## Sequencing

```
Phase A (EstimAggFiscalMAIN GICX_MODE)  ──┐
                                          ├─→ Phase D (validation, ~3 hr)
Phase B (estim_phase2_tm_a GICX_MODE)   ──┘    │
                                                ↓
Phase C (docs) — interleave with D            (Phase G decision after D)

Phase E (warm-start from saved) ─→ E-validation ─→ (Phase G decision)
Phase F (parallel multistart)   ─→ F-validation ─→ (Phase G decision)
```

Phases A, B, E, F can all proceed in parallel after Phase A skeleton
is in place (they don't share files except for shared-config edits in
EstimAggFiscalMAIN.py).

## Estimated total: ~5-6 hours focused work + ~5-6 hours background compute

| Phase | Wall time | Parallelizable? |
|---|---|---|
| A: EstimAggFiscalMAIN GICX_MODE dispatch | 45 min | Yes — parallel with B/E/F |
| B: estim_phase2_tm_a GICX_MODE dispatch | 20 min | Yes — parallel with A/E/F |
| C: Documentation | 15 min | Yes — interleave with D |
| D: GICx validation (Tier 0+1) | ~3 h compute | Tier 1 cohorts can parallelize |
| E: Warm-start from saved | 30 min impl + ~1 h validation | Yes |
| F: Parallel multistart | ~1 h impl + ~1.5 h validation | Yes |

## Commit strategy

Five commits (one per phase + per validation tier):

1. `BUG-039 Phase A+B+C: implement HAFISCAL_GICX_MODE dispatch`
   (with `legacy` default for safety; both estimators)
2. `BUG-039 Phase D Tier 0: single-eval sanity for all 3 GICx modes`
3. `BUG-039 Phase D Tier 1: 3-cohort hardcoded re-anchor + comparison`
4. `BUG-039 Phase E: warm-start NM from saved DiscFacEstim`
5. `BUG-039 Phase F: parallel multistart in run_phase2_parallel.py`

A future PR can flip the defaults (Phase G) once each phase's
validation passes.

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Hardcoded cap (0.999) is meaningfully looser than NM's chosen factors → fit deteriorates more than expected | Med | Phase D Tier 1 measures the residual increase per cohort; if > 50% on any cohort, reconsider whether to keep Mechanism 2 as an option (i.e., promote twophase mode to default for that cohort) |
| Option A's clip-in-objective creates trajectory problems (NM stuck on boundary) | Low | Promote Option H (sigmoid) as fallback; mathematically equivalent at the optimum |
| Warm-start-from-saved leads to stale-basin lock-in | Med | Always run multistart in parallel with warm-start; the warm-start is added as ONE of the multistart points, not the only one |
| Parallel multistart OOMs (subprocess memory × 4 for D) | Med | Measure peak memory; if > available RAM, reduce parallelism (do 2 multistart in parallel × 2 sequential rounds) |
| Sentinel GICx in twophase mode breaks downstream readers | Low-Med | Downstream uses (β, ∇) for clipping; if not binding, sentinel reproduces same atom distribution. Confirm via Step-5 multiplier comparison |
| Phase F changes the canonical merge semantics in run_phase2_parallel.py | Low | Backwards-compat: if HAFISCAL_WRAPPER_MULTISTART_POINTS is unset, behave exactly as today |

## What this plan does NOT do

- Doesn't re-derive GICmaxBetas formula (BUG-034-era work; out of scope)
- Doesn't loosen per-Bellman solver tolerance (orthogonal speedup;
  needs separate validation; flagged as future work)
- Doesn't implement skip-solve-when-DiscFac-change-is-tiny (delicate
  caching; could go stale; deferred)
- Doesn't implement intrinsic-constraint reparameterization (Options
  H and I) in this iteration; available as fallbacks if Option A
  creates issues
- Doesn't change the cohort-level multistart logic itself (BUG-036)

## References

- BUG-039 dossier: `BUGS_private/HAFiscal_BUG-039_GICx_unconditionally_optimized.md`
  (especially §0 for the two-mechanism distinction and §4 for option discussion)
- BUG-034 dossier: `BUGS_private/HAFiscal_BUG-034_step2_wealth_aggregation_inconsistency.md`
- BUG-036 (multistart context): `BUGS_private/HAFiscal_BUG-036_dropout_step2_local_minima.md`
- TM-vs-MC methodology note: `conclusions_private/2026-05-02_tm-vs-mc-methodology-distinction-for-step-2-fit.md`
- Source commit for `theGICfactor=0.999` mixing rationale: `f6b7a2d6`
- 2026-05-02 re-anchor results showing NM-chosen factors 98.6%-99.78%:
  `Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01.txt`
- Existing parallel-cohort wrapper (basis for Phase F's parallel-multistart
  extension): `Code/HA-Models/FromPandemicCode/run_phase2_parallel.py`
- Existing Bellman warm-start (the solver-side speedup that's already done):
  `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:1917`
  (`AggregateDemandEconomy.solve(warm_start=True)`)
