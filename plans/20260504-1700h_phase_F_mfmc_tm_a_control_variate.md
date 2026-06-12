---
date: 2026-05-04
status: plan-draft
keywords: [speedup, MFMC, multifidelity-monte-carlo, control-variate, TM-a, bias-correction]
related_bugs: []
related_plans:
  - 20260504-1300h_qe_fidelity_speedup_systematic_test.md
  - 20260504-1450h_qe_fidelity_fast_profile.md
related_conclusions:
  - 2026-05-04_mc-tm-hybrid-literature-survey-and-proposals.md
  - 2026-05-04_qe_fidelity_full_vs_QE_published.md
related_results:
  - results_20260504_speedup-test-matrix.md
---

# Phase F: Use TM-a output to reduce MC compute (MFMC-style)

## Genesis

Per `conclusions_private/2026-05-04_mc-tm-hybrid-literature-survey-and-proposals.md` (Proposal A), the literature suggests Multifidelity Monte Carlo (Peherstorfer-Willcox-Gunzburger 2016/2018) as a way to combine the cheap-but-biased TM estimator with expensive-but-unbiased MC. We're already running both kernels in parallel for drift measurement; in principle the TM output could halve the MC cost.

**But there's a conceptual issue that needs first-principles examination before we commit to literal MFMC** — see §2.

## 1. Reference benchmark (recap)

- qe_fidelity_full Step-5a wall: **3 hr 13 min** at Baseline (commit `c6935969`)
- Headline multipliers: Check 1.216, UI 1.178, TaxCut 0.992
- TM-a kernel runs as drift companion (`HAFISCAL_TM_A_INDEXED=1`, `HAFISCAL_TM_A_CACHE=1`) — produces analytical multipliers but they're currently discarded after drift measurement
- Per recent feedback `feedback_ui_multiplier_unreliable.md`: UI multiplier is unreliable (small affected sample); decisions use Check + TaxCut

## 2. The conceptual challenge with literal MFMC for HAFiscal

Standard MFMC (Peherstorfer 2016) formula:

$$\hat{G} = G_{HF} + \alpha (G_{LF} - \mathbb{E}[G_{LF}])$$

where $G_{HF}$ is high-fidelity (MC), $G_{LF}$ is low-fidelity (TM-a), and the variance reduction comes from $G_{LF}$ being a NOISY estimator correlated with $G_{HF}$.

**For HAFiscal, TM-a is deterministic given the model + parameters.** There's no "$G_{LF}$ noise" to subtract; $\mathbb{E}[G_{LF}] = G_{LF}$ identically. The literal MFMC formula collapses to $\hat{G} = G_{HF}$ — no benefit.

The hybrid-survey author addresses this glancingly with "$G^{TM(\text{coupled})}$ runs the TM kernel using the same realized aggregate-shock sequence as MC" — but for HAFiscal's fiscal-multiplier experiments the aggregate shock sequence (EconomyMrkv_init) is **FIXED per scenario**, not random. So $G^{TM(\text{coupled})} = G^{TM}$ = the same constant.

Three workable adaptations of the spirit of MFMC for HAFiscal:

### Adaptation A: Bias-correction surrogate
- TM has systematic bias $b = G_{TM} - G_{MC}$ vs the true population mean
- Estimate $\hat b$ from ONE high-N MC run at calibration
- For subsequent runs at LOW-N MC, use $\hat G = G_{TM} + \hat b$
- **Speedup mechanism:** skip future high-N MC runs entirely — just run TM (cheap)
- **Risk:** assumes bias is stable across the things we vary

### Adaptation B: Cross-shock-type bias borrowing
- Compute $\hat b_{\text{Check}}$ from full MC + TM at one shock_type
- For the other 6 shock_types, use $\hat G_{\text{shock}} = G_{TM,\text{shock}} + \hat b_{\text{Check}}$
- **Speedup mechanism:** ~6× speedup (run full MC for 1 of 7 shock_types, infer the rest)
- **Risk:** assumes bias is roughly constant across shock_types (may be true since MC/TM error sources are mostly shock_type-independent: grid lottery, half-step timing, mass-at-zero representation)

### Adaptation C: MC noise reduction via antithetic variates (NOT TM-related)
- Within MC, sample shock realizations $(\epsilon, -\epsilon)$ paired
- Average: typically **1.5-3× variance reduction at fixed N**, OR same precision at half N
- **Speedup mechanism:** halve N
- **Risk:** doesn't depend on TM at all; orthogonal to A/B; can stack

## 3. Proposed phased experiment

### Phase F-0: Capture TM-a multipliers separately (~1 hr engineering)

Currently TM-a runs as drift companion but its multiplier outputs aren't extracted. Modify `Simulate.py` to pickle out the TM-a multipliers per shock_type alongside the MC multipliers. This gives us the data needed for everything below.

**Pass criterion:** for any test run, both `Tables/Baseline/Multiplier_MC.tex` and `Multiplier_TM_a.tex` exist with the per-scenario numbers.

### Phase F-1: Measure bias structure (~1 hr Baseline run)

Run ONE Baseline test (using existing qe_fidelity estimates, no Step-1/2). Extract:
- $G_{MC,\text{shock}}$ for each shock_type
- $G_{TM,\text{shock}}$ for each shock_type
- $b_{\text{shock}} = G_{MC,\text{shock}} - G_{TM,\text{shock}}$ for each
- $\rho_{\text{shock,shock'}}$ — correlation of $b$ across shock_types

**Decision criteria:**
- If $b$ is stable across shock_types (e.g., all within ±0.02 of common mean): Adaptation B is viable. **Proceed.**
- If $b$ varies wildly across shock_types: Adaptation B fails. Skip to F-3 alternative (Adaptation C antithetic).

### Phase F-2: Implement and validate Adaptation B (if F-1 passes)

Implementation (~1-2 days):
- Add a "calibration" mode: run full MC for a designated calibration shock_type (e.g., recession) + TM-a for all
- Add a "production" mode: skip MC for non-calibration shock_types, output $G_{TM} + \hat b$
- Validate: compare production-mode output to a fresh full-MC reference at a single shock_type (e.g., recessionCheck). Pass if multipliers match within ±3% on Check + TaxCut (UI deprecated).

### Phase F-3: Stack with Idea F + measure combined wall (~1 Baseline test)

If Adaptation B validates, combine with Idea F (loose AD tol) and run full Baseline test:
- `qe_fidelity_fast` profile + Adaptation B
- Compare wall vs qe_fidelity_full reference (3 hr 13 min)
- Compare multipliers vs qe_fidelity_full Check 1.216, TaxCut 0.992

**Pass criterion:** wall ≤ 1 hr (3× speedup) AND multipliers within ±3%.

### Phase F-4: Add to qe_fidelity_fast profile (if F-3 passes) (~30 min)

Update `plans/20260504-1450h_qe_fidelity_fast_profile.md` and `reproduce.sh` profile to include the calibration+production mode.

## 4. Antithetic variates (Adaptation C) as parallel/alternative track

If Adaptation B fails F-1's bias-stability test, fall back to Adaptation C:

- Implementation: in `Simulate.py`'s shock generation, sample $\epsilon$ for half the agents and use $-\epsilon$ (antithetic) for the other half
- ~1 day HARK-side or HAFiscal-side work (depending on where shock generation sits)
- Expected ~1.5-3× variance reduction → can halve N for same precision
- **Stackable** with Idea F and (independently) Adaptation B if B works

## 5. Realistic speedup expectations

| Combination | Projected Step-5a wall | Multiple of qe_fidelity_full ref |
|---|---|---|
| qe_fidelity_full reference | 3 hr 13 min | 1.0× |
| + Idea F (loose AD tol) | ~2 hr 15 min - 2 hr 35 min | 1.2-1.5× |
| + Adaptation B (TM bias-borrowed) | ~30-60 min | **3-6×** if bias stability holds |
| + Adaptation C (antithetic, halve N) | ~1 hr 30 min - 2 hr | 1.5-2× |
| All three combined | ~20-40 min | **5-10×** plausible if all work |

## 6. Risks

- **Bias stability assumption (Adaptation B):** untested for HAFiscal. F-1 measures it. If it fails, no harm done — we just skip B and pursue C.
- **TM-a multiplier extraction (F-0):** current TM-a code path may not naturally produce multipliers in the same format as MC. May need plumbing to align outputs.
- **Antithetic implementation (Adaptation C):** depends on where in HARK the shock generation lives and whether antithetic pairs cleanly map onto agent panels.
- **Welfare out of scope:** these techniques are for multipliers only. Welfare needs full MC (per existing rule).

## 7. Effort estimate

| Phase | Engineering | Wall (compute) | Output |
|---|---|---|---|
| F-0 | 1 hr | n/a | TM-a multiplier extraction |
| F-1 | 30 min | ~2-3 hr (1 Baseline test) | Bias structure measured |
| F-2 | 1-2 days | ~3-4 hr (validation runs) | Adaptation B implementation |
| F-3 | 30 min | ~1-2 hr (combined run) | Wall measurement |
| F-4 | 30 min | n/a | Profile updated |
| **Total** | **~2-3 days engineering** | **~6-9 hr compute** | **qe_fidelity_fast with stackable speedups** |

## 8. Dependencies and ordering

This plan should run AFTER landing Idea F in qe_fidelity_fast (so the combined-effect comparison in F-3 has a clean baseline). Suggested order:

1. Land Idea F per `20260504-1450h_qe_fidelity_fast_profile.md`
2. Validate qe_fidelity_fast (Idea F alone) at Baseline → records the F-only speedup
3. Then start this plan (F-0 through F-4)
4. If F-3 passes, qe_fidelity_fast becomes "F + Adaptation B" with a stronger speedup claim

## 9. Resolved decisions (2026-05-04)

Per user direction:

1. **Conceptual analysis confirmed:** literal MFMC doesn't apply for HAFiscal (TM-a is deterministic). Proceed with the three adaptations as described.

2. **Order of testing:** Adaptation B standalone first, then Adaptation C standalone, then B+C combined. (NOT picking one — doing all three in this order.)

3. **Don't wait for Idea F:** F-0 (TM-a multiplier extraction) starts immediately. F-3's combined-effect test will combine with Idea F when both ready, but the work proceeds in parallel.

## 10. Updated execution order (post-decision)

1. **F-0** — TM-a multiplier extraction. Modify drift companion to also extract per-scenario aggregate consumption from TM-a → multipliers offline. ~1 hr engineering.
2. **F-1** — Single Baseline-scope run with F-0 changes. Capture MC + TM-a multipliers for all 7 shock_types. Compute bias structure. ~2-3 hr compute.
3. **F-2 (Adaptation B standalone)** — implement bias-borrowing logic; validate at Reduced_Run + at Baseline (single shock_type cross-check). ~1-2 days engineering + few-hour compute.
4. **F-2-C (Adaptation C standalone)** — implement antithetic variates in MC shock generation. Validate at Reduced_Run + Baseline. ~1-2 days engineering + few-hour compute.
5. **F-3** — combined B+C test (and stacked with Idea F if F is landed by then). One Baseline test. Wall vs ref + multipliers vs ref.
6. **F-4** — update qe_fidelity_fast profile or create qe_fidelity_fast_v2 with the winning combination.
