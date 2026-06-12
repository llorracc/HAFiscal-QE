---
date: 2026-05-06
status: plan-active
phase_0_decisions:
  scope: B (side-by-side ESC-MC and CDC-TM as robustness check)
  perm_shocks_during_unemp: off (REVISED 2026-05-07 — exact-Markov formulas handle factorization-free case correctly; faster TM matrices)
  welfare_6: skip (defer; CDC paper carries MC welfare numbers in robustness column with caveat)
  calibration_strategy: warm-start from DiscFacEstim_CRRA_2.0_R_1.01_TM_a_ESC.txt
  profile_name: production_cdc_tm
phase_0_revision_2026-05-07:
  reason: |
    Original choice perm_shocks=on motivated by "pLvl ⊥ Markov-state factorization
    makes (1-u) analytical pLvl exact." But we built compute_log_p_moments_exact
    and compute_E_pLvl_exact during BUG-042 work — these handle perm_shocks=off
    via Markov-chain matrix iteration, equally exact. Switching to off saves
    ~5-7× wall (no TM-matrix-density blow-up from 49-atom unemployed shocks)
    AND matches QE convention exactly. Phase 2 ran for 11 hours under perm_shocks=on;
    re-launching with off projected ~1-2 hr.
phase_0_revision_2026-05-07_v2:
  reason: |
    Partial Phase 2 psdu=off results revealed multipliers are ~5-8% LOWER than
    psdu=on (UI AD: 1.144 vs 1.20; TaxCut AD: 0.933 vs 1.02). This is a real
    economic difference, not numerical. psdu=on vs off describes different model
    specifications (income risk during unemployment), not just numerical conventions.
    QE published used psdu=off, so psdu=off is the correct choice for QE-compatibility.
    Decision: CDC+TM+psdu=off is the migration target. Drop psdu=on entirely.
  alternative_to_evaluate: |
    User suggested "or maybe ESC+TM" — i.e., consider keeping ESC interpretation
    and just swapping MC→TM as the cleanest robustness column. This isolates the
    method effect (MC vs TM) without confounding with interpretation change
    (ESC→CDC). To-be-launched after current Phase 2 (CDC+TM+psdu=off) completes.
keywords: [migration, ESC, CDC, MC, TM-a, methodology, paper-baseline, BUG-040, BUG-041, BUG-042]
related_plans:
  - 20260506-1640h_edu_share_aggregation_correction.md
  - 20260504-1450h_qe_fidelity_fast_profile.md
  - 20260503-1655h_perm_shocks_during_unemp_config_split.md
related_conclusions:
  - 2026-05-06_FINAL_AD_loop_residual_is_finite_N_MC_artifact.md
  - 2026-05-06_FINAL_edu_share_aggregation_and_remaining_AD_residual.md
  - 2026-05-06_RESOLVED_per_cohort_drift_is_mc_sampling_noise.md
  - 2026-05-05_RESOLVED_mc_vs_tm_multiplier_mystery.md
  - 2026-05-04_qe_fidelity_full_vs_QE_published.md
related_bugs:
  - BUG-040 (HAFISCAL_PLVL_GROWS_DURING_UNEMP)
  - BUG-041 (HAFISCAL_TM_CFUNC_OFFSET)
  - BUG-042 (HAFISCAL_AGGREGATE_BY_EDU_SHARE)
related_memory:
  - project_mc_tm_mystery_resolved.md
  - project_bug042_edu_share_aggregation.md
  - project_shuffle_friendly_recalibration.md
  - feedback_no_default_reestimation.md
  - feedback_ui_multiplier_unreliable.md
  - reference_hafiscal_qe_baseline.md
---

# Migration plan: ESC + MC → CDC + TM-a

## Context for any subagent picking this up

**Read these first** (they encode hard-won context from Apr-May 2026):
- `conclusions_private/2026-05-05_RESOLVED_mc_vs_tm_multiplier_mystery.md`
  — explains the BUG-040+041 closure that got MC and TM agreeing within ~1.6%
- `conclusions_private/2026-05-06_FINAL_AD_loop_residual_is_finite_N_MC_artifact.md`
  — explains why TM-a is the production method, MC is cross-validation
- `conclusions_private/2026-05-04_qe_fidelity_full_vs_QE_published.md`
  — methodologically-matched ESC+MC reproduction of the published QE values
- `memory/project_shuffle_friendly_recalibration.md`
  — shuffle-quota-exact urates (D=0.090/HS=0.045/C=0.025) for MC variance reduction

**Profiles relevant to this migration** (in `reproduce.sh`):
- `qe_fidelity` — current paper-baseline (ESC + MC + perm_shocks=off + legacy GICx + tight NM)
- `qe_fidelity_fast` — quick check using cached estimates + TM Step-5
- `tm_throughout_fast` — partial migration target (CDC + TM-a Step-2 + TM Step-5 + perm_shocks=on + hardcoded GICx + warm-start NM)
- `production_current` / `production_fast` — CDC + MC variants

**Bug-fix env vars now defaulted to QE convention** (see `BUGS_private/`):
- `HAFISCAL_PLVL_GROWS_DURING_UNEMP=off` (BUG-040, default)
- `HAFISCAL_TM_CFUNC_OFFSET=mc` (BUG-041, default)
- `HAFISCAL_AGGREGATE_BY_EDU_SHARE=auto` (BUG-042, default)

These all default to the ESC+MC convention. The CDC+TM target may want different defaults — flagged in each phase below.

## Why migrate?

**ESC + MC** (current paper baseline):
- MC carries inherent ~1.5% finite-N bias on Check/TaxCut AD multipliers (per
  finite-N conclusion above)
- ESC interpretation makes pLvl-during-unemp ambiguous; QE chose perm_shocks=off
  (= pLvl frozen during unemployment), which uses a (1-u) approximation for
  the analytical pLvl distribution that is biased on D-cohort
- Step-2 MC takes ~5h36m at Baseline scale
- Step-5 MC takes ~3h13m at Baseline scale
- Total Baseline reproduction: ~10 hr

**CDC + TM-a** (proposed target):
- TM-a is analytically exact (no finite-N artifacts)
- CDC interpretation makes pLvl ⊥ Markov-state factorization explicit, so
  perm_shocks_during_unemp=True is theoretically clean (Harmenberg-style)
- Step-2 TM-a takes ~30-60 min at Baseline scale (per `tm_throughout_fast`)
- Step-5 TM takes ~30-60 min at Baseline scale (per `qe_fidelity_fast` measurement: 28.56 min Reduced_Run; ~30-60 min Baseline projection)
- Total Baseline reproduction: ~1-2 hr

**Trade-offs to expect:**
- Calibration deltas: TM-a Step-2 fits normalized-Lorenz against level-Lorenz target → ~5% β shift on D vs MC (per `tm_throughout_fast` profile WARNING)
- Multiplier deltas: ~1.5-3% on Check/TaxCut, larger on UI (per
  `2026-05-04_qe_fidelity_full_vs_QE_published.md`)
- Welfare-6: Step-5b currently needs MC; would need a TM-equivalent or
  acknowledge it stays MC

## Migration phases

### Phase 0: Decisions to make BEFORE starting

These are policy decisions, not technical questions. Surface them with the
user first.

1. **Single-method paper or comparison paper?**
   - Option A: replace ESC-MC with CDC-TM throughout. New paper baseline.
   - Option B: present BOTH side by side as methodology robustness check.
   
2. **perm_shocks_during_unemp = on (CDC clean) or off (QE legacy)?**
   - CDC + on: Harmenberg pLvl ⊥ state factorization holds; analytical pLvl
     distribution is exact; var_log_p drift threshold can be tight
   - CDC + off: keeps QE convention; (1-u) analytical pLvl approximation
     applies (now have exact alternative via `compute_log_p_moments_exact`,
     2026-05-06)
   
3. **Welfare-6 method?**
   - Step-5b currently uses MC unconditionally
   - TM-equivalent for welfare-6 doesn't exist yet; would need to be implemented
   - Decision: keep welfare-6 in MC for now and accept the ~1.5% MC bias on
     welfare numbers? Or build TM welfare-6?

4. **Calibration update strategy?**
   - Current `DiscFacEstim_CRRA_2.0_R_1.01_ESC.txt` is the paper baseline
   - CDC-TM-a needs a new estimate file (no current cache exists for full
     3-edu-group CDC+TM-a)
   - Per `feedback_no_default_reestimation.md`: re-estimation is opt-in only,
     not default. So this is an explicit decision.

### Phase 1: Establish CDC-TM-a baseline calibration

**Subagent task:** Read `tm_throughout_fast` profile in `reproduce.sh:2596`.
Re-estimate Step-1 (splurge) and Step-2 (β/∇) under CDC + TM-a + chosen
perm_shocks setting.

**Steps:**
1. Run Step-1 (splurge estimation) under CDC. ~30 min wall.
   - Produces `Result_AllTarget_CDC.txt` (already exists from prior runs)
2. Run Step-2 (β/∇) under TM-a + CDC + chosen perm_shocks. Per
   `tm_throughout_fast` profile: hardcoded GICx + warm-start NM + tol 1e-2.
   - Per `feedback_no_default_reestimation.md`, this MUST be explicit.
   - Produces `DiscFacEstim_CRRA_2.0_R_1.01_TM_a_CDC.txt` (new file,
     doesn't exist yet — only `_TM_a_ESC.txt` and `_edType1_CDC.txt` exist)
   - Wall: ~30-60 min if warm-start, longer if cold-start
3. Validate: liquid-wealth Lorenz fit within 5% of QE-baseline Lorenz.

**Deliverable:** `DiscFacEstim_CRRA_2.0_R_1.01_TM_a_CDC.txt` committed.

**Cross-references:**
- `memory/feedback_no_default_reestimation.md` — get explicit user OK
- `memory/project_shuffle_friendly_recalibration.md` — consider whether
  to use shuffle-friendly urates (modest precision gain per H-0 results)
- `tm_throughout_fast` profile WARNING — TM-a Step-2 is normalized-Lorenz
  vs MC Step-2's level-Lorenz target; expect ~5% β shift on D

### Phase 2: Run Step-5 (multipliers) under CDC + TM

**Subagent task:** Step-5 only, using Phase 1's calibration.

**Steps:**
1. Set env: `HAFISCAL_INTERPRETATION=CDC`,
   `HAFISCAL_PERM_DURING_UNEMP=` (chosen value),
   `HAFISCAL_RUN_STEP_1=false`, `HAFISCAL_RUN_STEP_2=false`,
   `HAFISCAL_RUN_STEP_4=false`, `HAFISCAL_RUN_STEP_5B=?`
2. Run `--profile tm_throughout_fast --comp full` (or new profile, see Phase 5)
3. Wall: ~30-60 min Baseline
4. Output: multipliers (Check / UI / TaxCut at noAD / 1stAD / AD scopes)

**Validation:** compare to:
- ESC + MC published QE: Check 1.234, UI 1.211, TaxCut 0.978
- ESC + MC qe_fidelity_full reproduction (commit c6935969): Check 1.216,
  UI 1.178, TaxCut 0.992
- Document all 3 deltas: vs published, vs methodology-matched MC, vs prior
  CDC runs (if any)

**Cross-references:**
- `memory/procedure_qe_comparison_report.md` — required structure for any
  QE-comparison report (must include "QE baseline" and "Current version"
  characterization sections explicitly)
- `memory/reference_hafiscal_qe_baseline.md` — comparison reference is
  git tag `v2026-01-09-18-17` (NOT `resubmitted-to-QE`)

### Phase 3: Welfare-6 (Step-5b) decision and implementation

**Subagent task:** Decide on welfare-6 path.

**Options:**
- 3a. Keep MC welfare-6 as-is. Accept that welfare numbers carry the same
     ~1.5% finite-N MC bias as MC multipliers. Document this in the paper.
     Wall: +1 hr (existing parallel driver).
- 3b. Implement TM-based welfare-6. Requires new code (welfare-6 currently
     uses per-agent MC data via `welfare6_scenario.py` and
     `run_welfare6_parallel.py`). Substantial engineering effort (~1 week?).
     Out of scope for fast migration.
- 3c. Skip welfare-6 in the migration and document this as a Phase 6
     follow-up. The paper would then have TM multipliers + MC welfare,
     with the ~1.5% method gap acknowledged.

**Recommendation:** start with 3c (skip), revisit later. Don't block
multiplier migration on welfare engineering.

**Cross-references:**
- `Code/HA-Models/FromPandemicCode/welfare6_scenario.py` — existing welfare-6
- `Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py` — parallel driver

### Phase 4: Decompose deltas (CDC-TM vs ESC-MC)

**Subagent task:** Pure analysis. No re-estimation.

For each of {Check, UI, TaxCut} × {noAD, 1stAD, AD}, decompose the
ESC-MC → CDC-TM multiplier shift into:

| Component | Source | Estimable from |
|---|---|---|
| Calibration delta (β/∇/GICx) | TM-a Step-2 vs MC Step-2 | Phase 1 vs cached ESC |
| Method delta (TM vs MC) at fixed calibration | TM-a Step-5 vs MC Step-5 with same DiscFac | Phase 2 vs `qe_fidelity_full` |
| Interpretation delta (CDC vs ESC) at fixed method | TM with CDC vs TM with ESC | Phase 2 vs `tm_throughout_fast`-style ESC run |
| Residual (model + numerical) | What's left after above 3 | Subtraction |

**Deliverable:** decomposition table per shock × scope with attribution
to each component. Per `procedure_qe_comparison_report.md` rules:
characterize each "version" explicitly (interpretation, Step-2 method,
Step-5 method, profile, commit SHA).

**Cross-references:**
- `memory/procedure_qe_comparison_report.md` — mandatory structure
- `conclusions_private/2026-05-04_qe_fidelity_full_vs_QE_published.md` —
  reference table of QE-published vs methodology-matched ESC-MC

### Phase 5: New profile + reproduce.sh wiring

**Subagent task:** Add a new `production_cdc_tm` (or similar) profile.

**Profile spec:**
```bash
production_cdc_tm)
    export HAFISCAL_INTERPRETATION=CDC
    export HAFISCAL_PERM_DURING_UNEMP=on    # if Phase 0 chose 'on'
    export HAFISCAL_STEP2_METHOD=tm_a
    export HAFISCAL_GICX_MODE=hardcoded
    export HAFISCAL_NM_START_FROM_SAVED=1
    export HAFISCAL_NM_XATOL=1e-2
    export HAFISCAL_NM_FATOL=1e-2
    TM_ONLY=true
    log INFO "Profile production_cdc_tm: full CDC + TM-a pipeline"
    log INFO "  Wall time estimate: ~1-2 hours"
    log WARNING "  Step-5b welfare-6 still in MC (TM-equivalent not implemented)"
    ;;
```

**Validation:**
- Smoke test: run at Reduced_Run scope, verify multipliers within 2% of
  prior `tm_throughout_fast` run
- Update `--profile` valid list in args parsing

### Phase 6: Paper-text updates

**Subagent task:** Update `Subfiles/*.tex` and main `HAFiscal.tex`.

**Changes:**
1. Methodology section: describe TM-a as the production method, document
   the ~1.5% MC cross-validation residual as expected
2. Multiplier tables: replace with CDC-TM-a values
3. Welfare tables: keep MC values (Phase 3 decision), document caveat
4. Calibration table: replace with CDC-TM-a estimates
5. Robustness appendix: keep ESC-MC as a comparison column (or similar)

**Cross-references:**
- `HAFiscal.tex` (main)
- `Subfiles/Calibration.tex`
- `Subfiles/Comparing_policies.tex`
- `Subfiles/Welfare.tex`

### Phase 7: Documentation + memory updates

**Subagent task:** Update memory and conclusions.

**Updates:**
1. New conclusion: `conclusions_private/2026-MM-DD_migrated_to_CDC_TM.md`
   summarizing the migration
2. Update `memory/MEMORY.md` with new index entries
3. Update `memory/reference_hafiscal_qe_baseline.md` with note that the
   paper has migrated past QE-published methodology
4. Update `memory/procedure_qe_comparison_report.md` with new
   "characterization sections" template (if needed)
5. Mark this migration plan `status: resolved` once complete

## Subagent task assignment

Each Phase above is a discrete deliverable. Subagents (Plan / Explore /
general-purpose / claude-code-guide) can be assigned individual phases.

**For each subagent task, include in the prompt:**
- Reference to this plan file
- The specific phase number to execute
- Cross-reference list (memory + conclusions + bugs) for context
- Explicit reminder that BUG-040/041/042 fixes are defaulted to QE convention
  and may need flipping for CDC clean

## Risk & gating

**HALT criteria** (don't proceed past these without user check-in):
- Phase 1: if Step-2 TM-a calibration shifts β by >10% from ESC-MC, surface
  to user (β shift expected ~5% per `tm_throughout_fast` WARNING; >10%
  might indicate something wrong)
- Phase 2: if Check / TaxCut multiplier shifts by >5% vs ESC-MC published,
  surface to user (small shifts expected; large shifts need attribution)
- Phase 4: if decomposition has >2% residual after attributing all 3
  components, investigate before proceeding to Phase 5

**Reversibility:** preserve ESC-MC pipeline (don't delete `qe_fidelity` profile
or its calibration). The paper should be able to fall back to ESC-MC if needed.

## Wall budget summary

| Phase | Wall | Notes |
|---|---|---|
| Phase 0 (decisions) | 0 | Policy questions |
| Phase 1 (calibration) | ~1-2 hr | Step-1 + Step-2 TM-a |
| Phase 2 (multipliers) | ~30-60 min | Step-5 TM-only |
| Phase 3 (welfare) | 0 (recommendation 3c) or ~1 hr (3a) or ~1 wk (3b) | |
| Phase 4 (decompose) | ~1-2 hr analysis | Subagent or interactive |
| Phase 5 (profile) | ~30 min | Code change + smoke test |
| Phase 6 (paper) | ~1-2 days | Manual editing |
| Phase 7 (docs) | ~30 min | Memory + conclusion |

**Critical path: Phases 1 → 2 → 4 → 5 → 6 (recommendation 3c).** Phase 3
is parallel-or-skip. Total wall: ~3-4 hr engineering + ~2 days writing.

## Phase 0 decisions (RESOLVED 2026-05-06)

1. **Scope: Option B** — side-by-side ESC-MC and CDC-TM presentation as
   robustness check. Both pipelines preserved; paper carries both columns.
2. **perm_shocks_during_unemp: on** — CDC clean / Harmenberg-style. The
   pLvl ⊥ Markov-state factorization holds; analytical pLvl distribution is
   exact; tight 0.03 drift threshold applies.
3. **Welfare-6: skip (option 3c)** — CDC pipeline carries MC welfare numbers
   in robustness column with explicit caveat. TM welfare-6 deferred to a
   separate plan if/when needed.
4. **Calibration strategy: warm-start** — start NM from
   `DiscFacEstim_CRRA_2.0_R_1.01_TM_a_ESC.txt` and re-converge under CDC
   interpretation. Per `feedback_no_default_reestimation.md` this is an
   explicit, opted-in re-estimation.
5. **Profile name: `production_cdc_tm`** — accepted.
