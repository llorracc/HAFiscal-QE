---
date: 2026-05-12
revised: 2026-05-12 (post-BUG-044 stratified-shuffle resolution + tm_methods.py structural audit)
status: APPROVED 2026-05-12 — ready to begin implementation
keywords: [TM-a, 4-state, 6-state, BUG-043 Phase 3, BUG-044, validation, comparison]
related_task: #195 (BUG-043 Phase 3: Update TM-a code for 6-state UI)

decisions_locked:
  - "Q1 J-coupling: Option A (env-var-driven via agent.num_base_MrkvStates)."
  - "Q2 Validation tolerance: <3σ on every welfare-6 cell at production grid."
  - "Q3 Validation scope: STAGED — HS_Only first; on clean pass advance to Reduced_Run; on clean pass advance to full Baseline. HALT at current stage on failure (cascade-gate rule)."
  - "Q4 Version flag name: HAFISCAL_TM_A_WELFARE_METHOD={legacy_pre_bug043 | encoding_aware}; default = encoding_aware (new). Older paths preserved under legacy_pre_bug043."
  - "Q5 Timing: proceed NOW; do not wait on HARK PR #1776."
  - "Q6 Culling: mark old paths with `# CULL CANDIDATE (BUG-043 Phase 3): ...` comments BUT DO NOT REMOVE. Culling deferred to T.8 with explicit user authorization."
  - "Q7 Grid convergence (added 2026-05-12): perform full grid-resolution sweep (aCount, aMax, aFac) at HS_Only BEFORE any TM-vs-MC comparison. Joint stop criterion: BOTH ≤0.5% relative AND ≤3σ_MC. Sweep until N+1 ≈ N (i.e. don't stop because aCount=100 differs from aCount=50; only stop when adding more grid stops mattering AND the residual is below MC noise floor). Spot-check grid convergence again at each new scope (Reduced_Run, Baseline) before MC comparison."
  - "Q8 Harmenberg neutral measure (Q-measure) (added 2026-05-12): switch the welfare-6 TM-a path from default `neutral_measure=False` (P-measure) to `neutral_measure=True` (Q-measure). HAFiscal welfare-difference integrand factorizes as p·g(c_norm), which Harmenberg integrates exactly: E_P[p·g(c_norm)] = E_P[p]·E_Q[g(c_norm)]. Under Q-measure the c_norm ⊥ p assumption becomes exact, not approximate. Cohort log(pLvl) recurrence supplies the scalar E_P[p_t] factor unchanged. Diagnostic in T.2.5 measures the P-vs-Q gap as a regression check on prior P-measure TM-a results."
---

# Plan: Add TM-a 4-state and 6-state versions for cross-method comparison

## Goal

Enable TM-a (transition matrix analytical method) to run under both UI state
encodings — preserving all currently-saved (older) TM-a code paths in place
under explicit version flags so we can A/B them later before culling:

- **TM-a 4-state**: matches `HAFISCAL_UI_STATE_ENCODING=legacy` (= published QE)
- **TM-a 6-state**: matches `HAFISCAL_UI_STATE_ENCODING=bug_fix` (BUG-043 fix)

So we have these cross-comparable MC/TM combinations:

| Method | Encoding | Status (today) |
|---|---|---|
| MC non-shuffle | legacy (4-state) | works (= published QE) |
| MC non-shuffle | bug_fix (6-state) | works (4-seed Baseline data exists) |
| MC stratified-shuffle | legacy (4-state) | works, trusted via BUG-044 fix |
| MC stratified-shuffle | bug_fix (6-state) | works, trusted via BUG-044 fix (Baseline minA agrees with nshuf to 0.31% on every welfare-6 cell) |
| **TM-a 4-state** | legacy (4-state) | **target of this plan** (Phase 3 of BUG-043) |
| **TM-a 6-state** | bug_fix (6-state) | **target of this plan** (Phase 3 of BUG-043) |

This unlocks systematic cross-method comparison. If TM-a 4 = MC 4 and TM-a 6 = MC 6,
then any MC-vs-MC delta between encodings is purely a policy-encoding effect (not
a numerical artifact). Conversely, any TM-vs-MC gap at a fixed encoding localizes a
methodology issue rather than a bug.

## What changed since the original (yesterday's) plan

1. **BUG-044 resolved.** MC stratified-shuffle is now a trusted production method.
   Originally we had only MC non-shuffle as the validation truth; now we have two
   independent MC references that agree with each other (Baseline minA: shuf-vs-nshuf
   bias <0.31% on every cell, including UI). This **strengthens** the validation
   target: TM-a should agree with both MC variants.
2. **TM-a structural audit complete.** Inspected all of `tm_methods.py` lines
   4766-5811 (the TM-a code path). Every site uses `J = agent.num_base_MrkvStates`
   or `J_micro = agent.num_base_MrkvStates`. **No hardcoded `4` constants** remain
   in the TM-a section. T.1 (audit) is therefore largely complete; the practical
   work is verifying end-to-end execution under bug_fix and validating against MC.
3. **`welfare6_scenario.py` already handles both encodings** for MC, including
   per-scenario IncShkDstn construction with the bug_fix's u3Q/u4Q/noBen income
   overrides. TM-a should pick this up via the same `agent.IncShkDstn` lookups.
4. **Reference values updated** to the BUG-043 bug_fix minA Baseline run
   (D=6300, H=12600, C=22680; 41,580 agents total) which is the current production
   data point and supersedes the small 1× quota run.

## Background — what TM-a currently does

`Code/HA-Models/FromPandemicCode/tm_methods.py` (5,811 lines). Key TM-a entry points:
- `build_tm_agg_fiscal_a(agent, ...)` (line 4766) — TM-a constructor
- `compute_period_aggregates_tm_a(...)` (line 5023) — per-period aggregator
- `propagate_experiment_tm_a(...)` (line 5295) — multi-period experiment runner
- `_build_period_tm_a(...)` (line ~5200) — single-period kernel
- (Note: TM-a does **not** have its own `run_experiment_tm_*` or `run_ad_tm`;
  it shares the TM-Q drivers, which take a `kernel='a'` switch via env var
  `HAFISCAL_TM_KERNEL`. Verify this in T.0.)

All TM-a aggregation indexes via `J_micro = agent.num_base_MrkvStates`. Under
`HAFISCAL_UI_STATE_ENCODING=bug_fix`, this attribute is dynamically 6 (vs 4 in
legacy), and `welfare6_scenario.py` constructs the IncShkDstn list with the
right length already.

Per the BUG-043 implementation plan, Phase 3 (TM-a update) was deferred because:
- TM-a is not in the welfare-6 production path (MC+CRN+IS is per
  conclusions_private/2026-05-10_decision_MC_IS_unified_welfare.md)
- Substantial refactor risk (now mostly invalidated by the structural audit)
- Validation easier once MC bug_fix is settled (it is now — BUG-044 closed
  the verification of bug_fix MC results)

## Phase T — TM-a 4-state and 6-state (this plan)

### T.0 — Locate the TM-a driver entry point (~30 min)

The TM-a kernel is exposed via `HAFISCAL_TM_KERNEL=a` (vs default `q`/`bst`).
Verify:
- Where the env-var is read (likely in `propagate_experiment_tm` or its callers)
- Whether `run_experiment_tm` or a separate `run_experiment_tm_a` exists
- Whether `run_ad_tm` already routes correctly to the TM-a kernel
- Whether welfare6 measurement currently has any code path that calls the TM-a
  driver — and if not, which orchestration script will need to be added/modified

Output: doc/note in `conclusions_private/2026-05-XX_tm_a_driver_audit.md`
listing (a) entry-point function, (b) its dependencies, (c) the call chain from
welfare6 down to the per-period kernel.

### T.1 — Confirm structural J-agnosticism (~30 min, mostly done)

Already verified via grep audit:
- All TM-a kernel sites use `J_micro = agent.num_base_MrkvStates`
- No hardcoded `4` constants in lines 4766-5811
- The TM-a build accepts `interpretation='CDC'` (the default for BUG-043)

Remaining T.1 task:
- Audit shared utilities called BY the TM-a kernel (e.g.
  `_solve_markov_ergodic`, `compute_TranMatrix_*`) for any J=4 assumption.
- Audit any "scratch" buffers allocated outside the kernel (e.g. dist arrays
  initialized in welfare6_scenario.py before TM-a is called).
- Spot-check the off-the-grid extrapolation logic: TM-a's mGrid spline uses
  cFuncs `[cfunc_offset + j for j in range(J_micro)]` which auto-scales.

Output: short check-list note appended to T.0 audit doc, marking
"already-verified" vs "newly-found".

### T.2 — End-to-end smoke test under bug_fix encoding (~1 hr)

Build a minimal HS_Only test:
- `HAFISCAL_UI_STATE_ENCODING=bug_fix`
- `HAFISCAL_TM_KERNEL=a`
- `HAFISCAL_INTERPRETATION=CDC`
- HS-only cohort (1 of 3, fastest)
- Construct agent → expects `agent.num_base_MrkvStates == 6`
- Run `build_tm_agg_fiscal_a(agent)` → must succeed without shape mismatches
- Run `propagate_experiment_tm_a(...)` for `shock_type='base'` →
  must produce sensible AggIncome/AggCons series of expected length

If T.2 fails: triage which assumption broke. Likely candidates:
- An array initialized with size 4 somewhere upstream
- A cFunc list of length 4 reached by a TM-a code path
- An IncShkDstn list of length 4 ditto

Output: working bug_fix HS_Only TM-a base run, OR a fix-list of code sites
to address before continuing.

### T.2.5 — Grid-resolution convergence study at HS_Only (~3 hr)

**Performed BEFORE T.3/T.4** so the production grid is justified before any
TM-vs-MC comparison. Otherwise a TM/MC gap could be undersized grid rather than
methodology.

Cascade-gate the grid sweep itself: increase the parameter until consecutive
levels agree within a tight tolerance, then stop. Tolerance for "grid-converged"
is **≤0.5% relative change on every welfare-6 cell** (tighter than the <3σ
TM-vs-MC tolerance, since grid noise should be smaller than methodology gap).

**Joint stop criterion** for every sweep below: continue if EITHER the
relative diff is >0.5% OR the diff is >3σ_MC (where σ_MC is the standard
error of the MC reference cell at the validation scope). Stop only when
BOTH ≤0.5% AND ≤3σ_MC. Rationale: don't waste compute reducing TM-a grid
error below the MC noise floor (3σ already covers it), but don't allow grid
error to grow above the absolute precision we want for paper figures.

**SCOPE for grid sufficiency**: HS_Only is NOT sufficient. The binding
test is **College_Only with full beta heterogeneity (7 atoms)** — that's
the configuration where a small number of high-beta agents end up at very
high aNrm, stressing the upper end of the asset grid. The TaxCut case is
where this matters most (employed-with-savings agents are the marginal
welfare-affected subpopulation). See
`feedback_grid_convergence_test_in_college_beta_het.md` for the full rule.

HS_Only sweep is allowed as a CHEAP SANITY CHECK (verify the kernel runs;
get an order-of-magnitude grid baseline) but is NOT decisive. The
binding-test sweep MUST be the College+beta-heterogeneity case below.

**Sweep aCount** (per user pattern: don't stop until N+1 ≈ N):
- Run aCount = 50, 100, 150, 200, 300, 500 (build_tm_agg_fiscal_a default = 200)
- For each level, compute welfare-6 and compare to the previous level
- Apply the joint stop criterion above
- Pick the smallest aCount that converged

**Sweep aMax** (heavy-tail sensitivity):
- aMax_default = ergodic-driven autodetect (current behavior when aMax=None)
- Test multipliers {1.0, 1.5, 2.0, 3.0} of the autodetect
- Welfare integrals should be insensitive to the upper bound if grid covers
  the ergodic tail; if not, autodetect underestimates the tail.
- Apply the joint stop criterion above
- Pick the smallest multiplier where adding more aMax meets it

**Sweep aFac** (near-zero density, since MU(c) explodes near c→0):
- aFac controls nesting density toward aMin; default = 3
- Test aFac ∈ {2, 3, 4, 5}
- Welfare cells most sensitive to constrained (low-a) agents — esp. ui_rec
  and ui_rec_AD, where the marginal recipient is asset-constrained — should
  reveal aFac sensitivity here if anywhere
- Apply the joint stop criterion above
- Pick the smallest aFac where ↑aFac meets it

**Cross-cut sweep** (only if any individual sweep showed >0.5% sensitivity):
- 2-D grid at the converged values × ±1 step on the second dimension
- Catches the case where aCount and aMax are individually converged but the
  **product** (effective tail resolution) isn't

#### T.2.5-COLLEGE — Binding grid-sufficiency test (College_Only + beta heterogeneity, TaxCut focus)

After the cheap HS_Only sanity-check sweep (above), the **decisive
grid-sufficiency test** is in the College_Only-with-beta-heterogeneity
configuration:

- **Parametrization**: Baseline (provides 7 beta atoms per cohort) but
  filtered to College cohort only (edType=2). Mechanism: either
  `HAFISCAL_WRAPPER_EDTYPES=2` env var or post-build agent-list
  filtering, whichever the welfare6_tm.py supports.
- **Scenarios under test**: ALL TaxCut variants (`TaxCut`,
  `recessionTaxCut`, `recessionTaxCut_AD`) since this is where high-aNrm
  agents drive the welfare-affected subpopulation.
- **Sweep**: aCount ∈ {50, 100, 150, 200, 300}; aMax_mult ∈ {1.0, 1.5, 2.0, 3.0};
  aFac ∈ {2, 3, 4, 5}.
- **Joint stop criterion** (same as above): ≤0.5% AND ≤3σ_MC on every
  TaxCut welfare-6 cell.
- **Decision**: the converged (aCount, aMax_mult, aFac) from THIS test
  becomes the **production default** for ALL parametrizations going forward
  (HS_Only, Reduced_Run, Baseline). HS_Only's earlier "A=50 sufficient"
  conclusion is recorded as a partial finding but is not binding.

**Output**: `conclusions_private/2026-05-XX_tm_a_grid_College_beta_het.md`
documenting the converged grid + the decision values to use as production
defaults.

After T.2.5-COLLEGE establishes the production grid, all subsequent T.3 and
T.4 (and T.7) runs use those grid values — NOT a cheaper grid based on
HS_Only convergence.

**No pLvl grid sweep needed for `encoding_aware`.** TM-a's welfare integration
uses normalized consumption c_norm = c/p on the (a) grid, then multiplies by
`E[p_t]` (or `E[p_t^(1-ρ)]`) from the analytical cohort-specific log-pLvl
recurrence (`income_process_sst.compute_log_p_moments_exact` +
`effective_pLvl_growth`). There is no pLvl axis to discretize.

#### Harmenberg neutral measure (Q-measure) — recommended switch

**Audit finding**: every TM-a entry point currently defaults to
`neutral_measure=False` (P-measure), and no welfare-6 call site sets it
to True. This means c_norm and p are NOT independent in the cross-section
TM-a integrates over, so the formula
`E_P[u(c)] = E_P[p^(1-ρ)] · E_P[c_norm^(1-ρ)]` is approximate (depends on
how strongly c_norm correlates with p).

**Math-driven recommendation**: switch the welfare-6 TM-a path to
`neutral_measure=True`. The HAFiscal welfare-difference integrand
factorizes as `p · g(c_norm)` (degree-1 homogeneous in (c, p)), because
for paired counterfactuals with same `p` and same anchor:

```
[u(c_pol) - u(c_base)] / u'(c_anchor)
  = p · [c_norm,pol^(1-ρ) - c_norm,base^(1-ρ)] / c_norm,anchor^(-ρ)
```

(The `p^(1-ρ)` from u(c) cancels against the `p^(-ρ)` from u'(c_anchor),
leaving exactly one `p`.) Harmenberg integrates exactly:
`E_P[p · g(c_norm)] = E_P[p] · E_Q[g(c_norm)]`. Under Q-measure:
- `E_P[p_t]` per cohort per period comes from the **same** analytical cohort
  log(pLvl) recurrence we already have. No change to that machinery.
- `E_Q[g(c_norm)]` integrates `g` over the **Q-stationary (a)-distribution**
  with no pLvl axis. The c_norm ⊥ p assumption becomes exact (true by
  construction of the Q-cross-section), not approximate.
- The (a) grid sweep is the only finite-sample concern; pLvl handling is
  exact, no `c_norm ⊥ p` diagnostic needed.

**Interaction with cohort log(pLvl) tracking**: zero conflict — they
**combine cleanly**. Q-measure handles the cross-sectional `c_norm`
distribution exactly (no approximation in the marginal-of-p factor for
welfare differences), and the cohort log(pLvl) recurrence supplies the
scalar `E_P[p_t]` factor. Each does what it's good at.

**Implementation**: route the welfare-6 TM-a path through
`neutral_measure=True`. This is a one-line change at the TM-a call site
in `welfare6_scenario.py` (or the new TM-a-aware welfare-6 driver), plus
verification that `_to_neutral_measure` correctly handles `bug_fix`'s
6-state IncShkDstn (which it should, since it operates on each state's
distribution independently — but T.2 should explicitly test this).

**Validation diagnostic in T.2.5**: instead of the `c_norm ⊥ p` test (no
longer needed under Q-measure), compute welfare-6 BOTH ways at HS_Only:
  (i) `neutral_measure=True` (Q-measure, recommended path)
  (ii) `neutral_measure=False` (P-measure, current default)
If the gap is >0.5% on any cell, that quantifies the bias in the historical
P-measure path — useful as a regression check on prior TM-a results and as
an audit point.

**Edge case to verify in T.2**: under `HAFISCAL_UI_STATE_ENCODING=bug_fix`,
the noBen state has `IncShkDstn` with deterministic ψ=1 (no permanent shock,
since the agent is unemployed). The Q-measure reweighting `ψ/E[ψ]` is then
the trivial `1/1 = 1` for that state — Q and P agree on noBen's marginal,
which is correct. Confirm this is what `_to_neutral_measure` does and not
some divide-by-zero path.

Output: `conclusions_private/2026-05-XX_tm_a_grid_convergence_HS_Only.md`
documenting the converged (aCount, aMax_mult, aFac) for both legacy and
bug_fix encodings (computed under Q-measure), AND the size of the
P-vs-Q gap per welfare-6 cell as the regression check on prior TM-a results.

This converged grid becomes the **production grid** used in T.3 and T.4. If
T.3b/T.4b (Reduced_Run stage) shows >0.5% sensitivity to bumping aCount by 1.5×
on the new cohort mix, repeat T.2.5 at Reduced_Run scope before T.3c/T.4c.

### T.3 — TM-a 4-state validation vs MC 4-state (STAGED, ~2 hr/stage)

Under `HAFISCAL_UI_STATE_ENCODING=legacy`, using the converged grid from T.2.5.
Cascade-gated:

**T.3a — HS_Only stage** (cheap, ~10 min compute, grid from T.2.5 legacy):
- Run TM-a (a-kernel) for all welfare-6 scenarios on HS_Only
- Compare to MC nshuf legacy HS_Only and MC stratified-shuffle legacy HS_Only
- Acceptance: <3σ agreement on every welfare-6 cell (skip ui_norec — 0/0 by construction)
- **HALT** if fail. Else advance to T.3b.

**Grid spot-check at each new scope**: when entering T.3b or T.3c, run TM-a
once at the converged grid AND once at 1.5× aCount (smallest grid bump).
If those two TM-a runs differ by >0.5% on any cell, repeat T.2.5 sweep at
the new scope before MC comparison.

**T.3b — Reduced_Run stage** (mid-cost, ~30 min compute):
- Grid spot-check first (per the inset above): TM-a at converged grid vs 1.5× grid.
  If >0.5% delta → re-sweep T.2.5 at Reduced_Run scope before MC comparison.
- 3-cohort weighted run as in BUG-044 Reduced_Run validations
- Same <3σ acceptance criterion vs MC nshuf and MC strat-shuf
- **HALT** if fail. Else advance to T.3c.

**T.3c — Full Baseline stage** (expensive, opt-in only — see T.7 wording):
- Grid spot-check first (TM-a converged vs 1.5× grid); re-sweep T.2.5 at
  Baseline scope if delta >0.5%
- Production grid; cohort N matching MC stratified-shuffle Baseline minA
- Compare vs MC nshuf 4-seed (ui_rec ≈ 1.5652) and MC strat-shuf Baseline minA legacy
- Same <3σ acceptance criterion

### T.4 — TM-a 6-state validation vs MC 6-state (STAGED, ~2 hr/stage)

Under `HAFISCAL_UI_STATE_ENCODING=bug_fix`, using the **bug_fix-specific**
converged grid from T.2.5 (the 6-state encoding may need higher aCount or aFac
because the noBen state moves more agents to deep low-c, where MU-inv weighting
amplifies grid noise). Same staged cascade as T.3, with grid spot-check at
each scope:

**T.4a — HS_Only stage**:
- Grid spot-check first (TM-a bug_fix converged vs 1.5× grid)
- Compare to MC nshuf bug_fix HS_Only and MC strat-shuf bug_fix HS_Only
- <3σ acceptance, HALT if fail.

**T.4b — Reduced_Run stage**:
- Grid spot-check first
- 3-cohort weighted, vs MC nshuf bug_fix and MC strat-shuf bug_fix Reduced_Run
- <3σ acceptance, HALT if fail.

**T.4c — Full Baseline stage** (opt-in, T.7):
- Grid spot-check first
- Compare to MC nshuf bug_fix 4-seed reference (ui_rec ≈ 1.4071±0.0041) and
  MC stratified-shuffle bug_fix Baseline minA (ui_rec ≈ 1.4055, ui_rec_AD ≈ 1.7576)

### T.5 — Cross-comparison table (~1 hr)

Compute the six-way comparison for each welfare-6 cell at HS_Only:

|  | TM-a 4-state | TM-a 6-state | MC nshuf 4-state | MC nshuf 6-state | MC strat-shuf 4-state | MC strat-shuf 6-state |
|---|---:|---:|---:|---:|---:|---:|
| check_norec | ? | ? | 0.9582 | 0.9582 | (TBD) | (TBD) |
| check_rec | ? | ? | (4-seed) | (4-seed) | (TBD) | (TBD) |
| check_rec_AD | ? | ? | (4-seed) | (4-seed) | (TBD) | (TBD) |
| ui_rec | ? | ? | 1.5652 | 1.4071 | (TBD) | 1.4055 (Baseline minA) |
| ui_rec_AD | ? | ? | 1.8904 | 1.7806 | (TBD) | 1.7576 (Baseline minA) |
| taxcut_rec | ? | ? | (4-seed) | (4-seed) | (TBD) | (TBD) |
| taxcut_rec_AD | ? | ? | (4-seed) | (4-seed) | (TBD) | (TBD) |

(For T.5 at HS_Only we'd want HS-only versions of these references too — but
those are quick to produce since we have the seed-0 minA pickle.)

Diagnostic interpretation:
- All six columns agree → cell is encoding-invariant + method-agreed
- TM-a 4 = MC 4, TM-a 6 = MC 6, but 4 ≠ 6 → **encoding effect** (= BUG-043 fix
  works as intended; both methods see the same change)
- TM-a ≠ MC at same encoding → **methodology gap** (warrants investigation)
- MC strat-shuf ≠ MC nshuf at same encoding → **shuffle bug regression**
  (BUG-044 should have closed this; it's our regression check)

### T.6 — Implementation hardening + version-flag preservation (~3-5 hr)

Goal: enable both new TM-a versions while **preserving the existing TM-a code
paths in place under explicit flags**. Three-axis flag scheme:

```
HAFISCAL_TM_KERNEL=a                                        # selects TM-a (already exists)
HAFISCAL_UI_STATE_ENCODING={legacy | bug_fix}               # already exists; selects 4-vs-6
HAFISCAL_TM_A_WELFARE_METHOD={legacy_pre_bug043 |           # NEW — default = encoding_aware
                              encoding_aware}
```

J-coupling: **Option A** (LOCKED) — TM-a always uses
`agent.num_base_MrkvStates`, so one TM-a binary handles both 4 and 6 micro
states; encoding selected via `HAFISCAL_UI_STATE_ENCODING`.

`HAFISCAL_TM_A_WELFARE_METHOD` semantics:
- **`encoding_aware`** (NEW, **default**): the J-agnostic welfare measurement
  that handles both 4- and 6-state encodings via `num_base_MrkvStates`. This
  is what T.3-T.5 validate. Required for any bug_fix run.
- **`legacy_pre_bug043`**: dispatches to whichever pre-existing TM-a welfare
  paths exist before this work (per-bucket aggregation, joint-distribution
  code paths from May 10 exploration, etc.). 4-state-only by construction.
  Preserved for A/B comparison and historical reproducibility.

If a `legacy_pre_bug043` run is invoked with `HAFISCAL_UI_STATE_ENCODING=bug_fix`,
fail loudly with a clear error message ("legacy_pre_bug043 only supports 4-state
legacy encoding; set HAFISCAL_UI_STATE_ENCODING=legacy or use encoding_aware").

**Cull-marking** (per user directive — DO NOT REMOVE, only mark):
- Tag every site touched by `legacy_pre_bug043` dispatch with a comment:
  ```python
  # CULL CANDIDATE (BUG-043 Phase 3): legacy_pre_bug043 path. Superseded by
  # encoding_aware. Removal gated on T.8 approval. <date>
  ```
- Same tag on the pre-BUG-041 `Cratio_path[t]` legacy CFunc indexing (already
  under `HAFISCAL_TM_CFUNC_OFFSET=tm`)
- Same tag on the "approx" iid-Bernoulli unemployment legacy
- Same tag on the `'bst'` ergodic path of `compute_period_aggregates_tm` (line ~2486)
- Build a manifest of cull candidates at
  `conclusions_private/2026-05-XX_tm_a_cull_candidates.md` listing each tagged site
  with file:line, the activating env-var combination, and a one-line rationale.

Document any code changes in:
- Memory entries (update `project_welfare6_tm_repagent_works.md`,
  add `project_tm_a_4state_6state_implementation.md`)
- BUGS_private/HAFiscal_BUG-043_*.md (Phase 3 status: complete or in-progress)
- Test scripts in `Code/HA-Models/FromPandemicCode/test_tm_a_encoding.py`
  covering both 4- and 6-state runs at HS_Only, plus a smoke test that
  `legacy_pre_bug043` still produces the prior values when invoked at the
  legacy encoding.

### T.7 — Production validation (~2 hr wall + compute) — OPT-IN

**Per "Default = no re-estimation; opt-in only" memory rule:** we will NOT auto-rerun
welfare-6 at Baseline production scale via TM-a. Output of T.4-T.6 should be
sufficient to declare TM-a 4/6-state working.

If user explicitly requests Baseline-scale TM-a production validation:
- Run welfare6 via TM-a (both encodings) at production aCount/aPCount and
  cohort_N matching the MC stratified-shuffle Baseline minA
- Compare to MC pickles (both nshuf and strat-shuf)
- Update the morning README's headline table to include TM-a column

### T.8 — Decision on culling (deferred, NOT in this plan)

After T.5 cross-comparison shows TM-a 4 and TM-a 6 are validated, propose
to user which older TM-a code paths can be removed. **Do NOT cull until
explicitly authorized.** The set of older paths to consider includes:
- The pre-BUG-041 `Cratio_path[t]` legacy CFunc indexing (kept under
  `HAFISCAL_TM_CFUNC_OFFSET=tm`; default is `mc` per BUG-041 fix)
- The "approx" iid-Bernoulli unemployment legacy (kept under env-var per
  line 174 of tm_methods.py)
- The `'bst'` ergodic path of `compute_period_aggregates_tm` (line 2486)
- Any TM-a per-bucket / joint-distribution welfare measurement variants

## Total estimated effort

T.0+T.1 = 1 hr (audit completion)
T.2 = 1 hr (HS_Only smoke test under bug_fix)
T.3+T.4 = 4 hr (validate against MC at both encodings, both shuf and nshuf)
T.5 = 1 hr (cross-comparison summary, six-column table)
T.6 = 3-5 hr (implementation + version-flag preservation + tests)
T.7 = 2 hr (opt-in Baseline production validation)
T.8 = deferred until validation passes + user authorization

Total: ~10-12 hr of focused work + 4-8 hr wall for compute (mostly T.7 if requested)

## Risks (revised)

| Risk | Likelihood | Mitigation |
|---|---|---|
| TM-a 6-state has a hidden hardcoded J=4 site upstream of the kernel | Low (was Medium) | T.1 + T.2 catch this via shape error |
| TM-a doesn't converge to MC under bug_fix at finite grid | Medium | Document gap; cell-by-cell. Likely candidate: aMax / aCount inadequate for the heavier-tailed bug_fix asset distribution |
| TM-a 6-state requires changing CFunc/Income setup | Low | welfare6_scenario.py already handles both encodings end-to-end |
| TM-a 6-state exposes a NEW bug | Low | Diagnostic; resolve via cross-comparison |
| Older TM-a logic regression under refactor | Low | Version flag `HAFISCAL_TM_A_VERSION` preserves old paths |
| BUG-044-style "looks right but is wrong" stays hidden | Low | Six-column comparison provides triangulation that two-method comparison cannot |

## Sequencing relative to current state

This plan is now the natural next step:
- BUG-043 (UI under-delivery) implementation: complete
- BUG-044 (shuffle bias): resolved; HARK PR #1776 awaiting Matt's review
- HAFiscal welfare-6 production: settled on MC + CRN + IS via the unified plan
- This plan: optionally add a second analytical method (TM-a) as cross-check

If the HARK PR review surfaces a need to revise the stratified algorithm, the
T.3/T.4/T.5 validation here will catch any downstream impact since TM-a's
analytical computation is independent of the shuffle algorithm.

## What I will NOT do without user approval

- Begin implementation (only T.0 + T.1 are reading code, no code changes)
- Run any TM-a code at Baseline production scale (T.7)
- Cull any older TM-a code paths (T.8)
- Modify the morning README's headline 4-seed table (currently MC-based)
- Make any cross-cutting changes to tm_methods.py beyond what's needed
  to make it J-agnostic AND preserve old paths under `HAFISCAL_TM_A_VERSION`

## Decisions locked in by user 2026-05-12

1. **Option A** — env-var-driven J via `agent.num_base_MrkvStates`.
2. **<3σ** acceptance tolerance on every welfare-6 cell.
3. **Staged validation**: HS_Only → Reduced_Run → full Baseline; advance only on
   clean pass at the previous stage; HALT at the failing stage if not (cascade-gate).
4. **Flag**: `HAFISCAL_TM_A_WELFARE_METHOD={legacy_pre_bug043 | encoding_aware}`,
   default = `encoding_aware` (the NEW J-agnostic code).
5. **Now** — proceed without waiting on HARK PR #1776.
6. **Mark for culling using `# CULL CANDIDATE (BUG-043 Phase 3): ...` comments;
   DO NOT REMOVE.** Culling deferred to T.8 with explicit user authorization.

## Deliverables checklist

When this plan is fully executed:
- [ ] T.0 audit doc in `conclusions_private/`
- [ ] T.1 J-agnostic audit confirmation
- [ ] T.2 HS_Only bug_fix smoke test passes
- [ ] T.3 TM-a 4-state vs MC 4-state agreement table
- [ ] T.4 TM-a 6-state vs MC 6-state agreement table
- [ ] T.5 six-column cross-comparison table
- [ ] T.6 `HAFISCAL_TM_A_VERSION` flag implemented; tests in `test_tm_a_encoding.py`
- [ ] Memory entry: `project_tm_a_4state_6state_implementation.md`
- [ ] BUG-043 dossier updated: Phase 3 status
- [ ] (T.7 optional) Production-scale Baseline validation
- [ ] (T.8 deferred) Culling proposal for older TM-a paths
