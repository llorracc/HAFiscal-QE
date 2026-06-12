# Overnight execution plan — TM-vs-MC grid convergence (autonomous)

**User asleep; execute autonomously.** Each background task completion re-invokes me; I read
the result, follow this plan, launch the next task, commit locally (NO push), and append to the
running log (§9). Bar for "converged": **|MC−TM| < 0.25% AND multi-seed MC SE < 0.25%** per cell.
Scope: **build the norec TM**, **cascade HS_Only → Reduced_Run → College_Only → Baseline** if
converging, **deep-dive the method gap** if the grid doesn't fix it. Cost is no object.
HALT + report (don't rabbit-hole) only on ambiguous *failure* (errors, non-determinism, a
hypothesis space exhausted) — otherwise keep going.

Ground truth: ergodic MC check_rec (HS_Only, N=10k/4-seed) = **1.0196**. Wide-grid TM = 1.0100
(+0.95%). The running test `bppod1q2t`: aMax=2.08 (adapted) vs aMax=500 (control).

## 1. Grid test lands (bppod1q2t) — read both numbers vs 1.0196
- **C-guard first:** if control aMax=500 ≠ ~1.0105 (±0.05), or either run errored → the env
  override or determinism is broken. DEBUG that first (Type-A correctness; never paper over).
  Re-run the control without the env var to confirm 1.0105; fix the override; re-launch.
- **A) aMax=2.08 closes ≥ half of +0.95%** (TM ≥ ~1.0150) → boundaries were (part of) the cause → §2.
- **B) aMax=2.08 unchanged** (TM ~1.0105, |Δ|<0.1%) → method gap, not boundaries → §3 (deep dive).

## 2. Branch A — grid helps
0. **Discover the GLOBAL aMax — set by the COLLEGE most-patient cohort (user correction
   2026-06-08; NOT per-cohort).** Warm-MC the COLLEGE group and take its MOST-PATIENT cohort
   (highest β atom — largest aNrm); set **aMax = 1.5 × that cohort's simulated max(aNrm)** (use
   the max, not a percentile — coverage is the point). Use this SINGLE grid (HAFISCAL_TM_AMAX)
   for ALL cohorts/types/parametrizations (HS_Only, Reduced_Run, College_Only, Baseline), even
   though the impatient HS cohorts have a far lower aNrmMax. **Per-cohort grids are REJECTED.**
   Rationale (user): the grid must COVER the most-patient agents or the upper edge truncates
   (the K/Y bias the aMax=500 comment warns about), and one shared grid keeps the cross-cohort
   welfare aggregation consistent. The impatient cohorts' near-0 resolution then comes from the
   exp-spacing (dense near 0) + enough aCount (§2.1). aMin=0.
   - Implementation: get College_Only's per-cohort aNrm panels (warm base MC); max over the
     highest-β cohort; HAFISCAL_TM_AMAX = 1.5 × that. (The HS_Only aMax=2.08 grid test still
     stands as a resolution DIAGNOSTIC — but the production aMax is this college-max value, NOT 2.08.)
1. **aCount convergence (the resolution knob, given the single wide aMax):** with the global
   college-max aMax, re-run check_rec bucketed-5D at aCount ∈ {50, 100, 200, …}, nb=20, until the
   IMPATIENT (HS-like) cells converge to <0.25% of the ergodic MC (the impatient near-0 region
   needs enough points despite the wide aMax). Converged V*.
   - V* within <0.25% → grid (college-max bound + sufficient aCount) was the whole story. Proceed.
   - V* plateaus >0.25% even at high aCount → residual method gap → ALSO run §3, then proceed.
3. **Build the norec TM** (user wants full coverage of all 4 non-AD policy cells):
   - check_norec / taxcut_norec = the policy welfare in NON-recession. Reuse the bucketed-5D /
     5-D kernels with `EconomyMrkv_path = [0]*act_T` (no recession), check/taxcut at t=0. Add a
     `--norec` mode to welfare6_check_rec_bucketed5d (and the taxcut path) that swaps the path +
     the none-scenario to base. Validate vs the ergodic-MC norec cells (from the bridge runs:
     check_norec 0.9567, taxcut_norec 0.9830) at <0.25%.
4. **Cascade** (each: warm-MC ground truth at N=10k/4-seed + auto-aMax TM, all 4 non-AD cells,
   per-group where the param is single-group; aggregated for mixed):
   HS_Only → Reduced_Run → College_Only → Baseline. For each cell, record MC, TM, |Δ|, SE, PASS/FAIL
   vs the bar. **Baseline bucketed-5D is slow (21 cohorts × 5-D); it may not finish by morning —
   that's fine, leave it running and report progress.**
5. Emit the convergence table (§9) — per param, per policy, per group: the headline deliverable.

## 3. Branch B / residual — method-gap deep dive (user: deep dive)
The bucketed-5D vs the ergodic MC, both ergodic, grid-converged. Test hypotheses in order; each is
a cheap, single-variable check at HS_Only against 1.0196:
1. **pLvl bucketing granularity:** nb ∈ {20 (have), 50, 100}. Converges to 1.0196? If yes → it was
   bucket coarseness (raise nb). If it plateaus at ~1.0100 → not bucketing.
2. **Within-bucket (a,j) factorization:** the bucketed-5D inits each bucket from the marginal (a,j).
   Test the conditional (a,j|bucket) init (the (a,pLvl) joint, welfare6_ajpLvl_build) — does it move
   the TM toward 1.0196? (We earlier found ergodic (a|pLvl) flat, so expect small — confirm.)
3. **The check-amount bucketing** (E_check_nrm_b): finer φ(pLvl) resolution within buckets.
4. **5-D integration / kernel:** compare the bucketed-5D integrand to a brute-force within-bucket
   per-agent evaluation on a small bucket (does the kernel reproduce the MC's mean-u per cell?).
5. **pLvl×(a,j) covariance** dropped by bucketing: estimate its size from the MC joint.
HALT + report when 1.0196 is reached (identify the cause) OR all five are exhausted (report the
decomposition of the +0.95% across them).

## 4. Determinism / safety
- Always HAFISCAL_USE_SOLUTION_CACHE=0 (avoid the write-race), --max-gpu-slots 0 (no GPU libs),
  --duration-workers 1 (avoid OOM, esp. Baseline). PYTHONUNBUFFERED=1.
- Multi-seed (≥4 seed-offsets) for every MC SE; never report a bias off one seed.
- Per-cohort aMax build: smoke on Reduced_Run before Baseline.

## 5. Halt conditions (report, don't churn)
- Control mismatch / non-determinism (§1 C-guard) unresolved after one fix attempt.
- A parametrization's solve/run errors twice with the same cause.
- Deep-dive hypotheses exhausted without reaching 1.0196.
- Per-cohort aMax build fails its Reduced_Run smoke.
In all cases: write the state + the blocker to §9 and stop launching new work.

## 6. Open question for the morning (not blocking)
The AD cells remain parked (JAX-AD-MC vs HARK-AD method confound). If the non-AD cascade finishes
early, do NOT touch AD — it needs the method isolated first (user direction). Flag it for the user.

## 9. Running log (append-only; the morning report)
- 2026-06-08 ~bedtime: plan written. bppod1q2t (grid test aMax 2.08 vs 500, HS_Only check_rec) RUNNING.
  Answers: bar <0.25%/SE<0.25%; build norec TM; cascade through Baseline; deep-dive on method gap.

- 2026-06-09 (overnight): **GRID TEST DONE — boundary hypothesis REFUTED.** aMax=2.08=1.0107 vs
  aMax=500=1.0105 (Δ +0.02%, no movement); +0.86% (nb=10) vs ergodic MC 1.0196 is a METHOD GAP,
  not grid under-resolution → Branch §3 deep dive. Hyp 1 (nb) already refuted (nb=10→20 goes
  1.0105→1.0100, AWAY from 1.0196). Hyp 2/5 (factorization/covariance) ~0 (ergodic (a|pLvl) flat,
  (j|pLvl)~0). Remaining: hyp 3 (check-amount bucketing) + hyp 4 (5-D integration/kernel).
  Starting deep dive with the component decomposition (NPV_w / NPV_AI / NPV_AC: bucketed-5D vs
  MC) to localize the gap. College-max discovery (ba0wg7oxt) continues — still needed for the
  PRODUCTION grid coverage once the method gap is resolved (the cascade is blocked until then).

- 2026-06-09 (deep dive): **COMPONENT DECOMPOSITION — gap is the φ(pLvl) BUCKETING, structural.**
  pLvl MATCHES (MC mean 14.94 vs TM 15.00, ratio 1.005) → not a pLvl mismatch. MC vs TM(nb10):
  term1 (welfare/check) 0.99834 vs 0.98004; term2 (saved) 0.02249 vs 0.03051; cell 1.0208 vs
  1.0106. TM under-states the consumption response to the check (saves more, less welfare/check).
  All TM components ~1.4× MC's (normalization that cancels in the ratio) but scale by DIFFERENT
  factors (NPV_w 1.383×, NPV_AI 1.409×, NPV_AC 1.397×) — the differential = the cell gap. nb sweep
  CONVERGES to 1.0100 (away from MC 1.0196) → structural, not resolution. taxcut (5-D, no
  bucketing) matched MC → 5-D kernel is fine; the φ(pLvl) BUCKETING is the gap. Next: per-bucket
  MC-vs-TM to localize which pLvl region + whether within-bucket.

- 2026-06-09: **COLLEGE-MAX DISCOVERY DONE.** College_Only aNrm support (base+rec+recCheck):
  MAX=866.68, p99.99=690.81, p99.9=334.29. Production **aMax = 1.5×max = 1300** (user formula),
  HAFISCAL_TM_AMAX=1300 for ALL parametrizations. NOTE: the old default aMax=500 TRUNCATES the
  college most-patient (support 867 > 500) — minor (~0.1% of college mass above 500), but the
  user's full-coverage grid (1300) fixes it. SEPARATE from the +0.86% bucketing gap (which is
  grid-independent — confirmed by the grid test). Deep dive on the bucketing continues
  (per-bucket re-run beepj0303).

- 2026-06-09 (DEEP DIVE — CONCLUSION + HALT). The +0.86% check_rec MC-vs-TM gap is a STRUCTURAL
  error in the bucketed-5D's φ(pLvl) BUCKETING. RULED OUT (each tested): grid/aMax (grid test:
  2.08 vs 500 both 1.010x), pLvl distribution (matches, ratio 1.005), 5-D kernel (taxcut_rec via
  5-D matched MC), the (a,j) factorization / marginal init (E[a|pLvl] flat 0.29-0.33 AND
  constrained fraction P(a<0.1) flat 0.22-0.28 across pLvl buckets), nb resolution (CONVERGES to
  1.0100, AWAY from MC 1.0196 — structural, not coarseness). Per-bucket cells monotonic in pLvl
  (b0=0.978 → b9=1.058); the bucketing under-states the welfare-per-check (component decomp:
  TM term1=0.980 vs MC 0.998). [Open detail: all 3 TM NPVs ~1.4x the MC's — a normalization that
  mostly cancels; the residual differential NPV_w 1.383x vs NPV_AI 1.409x is the cell gap.]
  CONCLUSION: the bucketed-5D TM CANNOT reach <0.25% for the CHECK cells (structural +0.86%
  bucketing). For CHECK cells use the warm-MC (ground truth, 1.0196). For TAXCUT cells the 5-D TM
  matches the MC (converged, -0.14%). The provable TM fix for check = the 6-D (pLvl as a real grid
  axis) — a big build, NOT attempted (user had deferred it). Cascade is BLOCKED for check cells;
  taxcut converged. HALTING the deep dive per the plan (cause identified, hypotheses exhausted).
