# Plan A — 5-D joint welfare-TM extension (check_rec / taxcut_rec)

**Goal:** close the within-cell **Jensen gap** (the non-AD MC↔TM ~2% diagnosed
2026-06-08, see `conclusions_private/2026-06-08_overnight_check_rec_reconciliation.md`)
by extending the 5-D joint welfare kernel from ui_rec to check_rec/taxcut_rec, so `u`
is evaluated over the full joint (E[u(c)], not u(E[c])). Validate **<0.25%** vs the MC
ground truth (shuffle+CRN, SE≈0.1%, `Results/tmp/shuffle/shuf_s0-3`).

## Scoping (3-agent, 2026-06-08)
- 5-D apparatus EXISTS (all in FromPandemicCode): `welfare6_tm_joint5d.py` (kernel,
  726 lines) + `welfare6_tm_joint5d_baseline.py` (caller) + `_batch` + `_full` +
  `_jax_kernel.py` (77 KB JAX). Standalone/diagnostic — NOT wired into `welfare6_tm.py`.
- Validated ONLY for ui_rec: 5-D=2.04 vs BUG-046-fixed MC=2.10 (**~3%**); the earlier
  "+27%" was vs the *biased* pre-BUG-046 MC. ui_rec is high-variance, so ~3% may be its
  MC noise — but **the 5-D has never been shown <0.25% on anything.** Hence the gate.
- 5-D state: (aᵖ, aⁿ, aᵇ, jᵖ⁼ⁿ, jᵇ); A³·J² ≈ 4.2M cells (HS_Only A=49); ~15-30 min/scenario CPU.
- **TaxCut: NO kernel change** (encoded in IncShkDstn_recessionTaxCut) — caller dispatch only.
- **Check: HARD** — the income phase-out φ(pLvl) is NOT a 5-D state. Needs a 6th dim
  (~63M cells, infeasible) OR a **bucketed-5D** (5-D joint per pLvl-bucket). The real build.

## Apparatus change (this session)
`welfare6_tm_joint5d_baseline.py`: `JOINT5D_POL_SHOCK` env var selects the pol scenario
(recessionUI/recessionTaxCut/recessionCheck), threaded to `switch_shock_type` + the
kernel's `shock_type_pol`. Backward-compatible (default ui_rec unchanged).

## Cascade (gate-by-difficulty, HALT on fail)
1. **GATE — taxcut_rec 5-D @ HS_Only A=50 vs MC 0.9832. <0.25%?**  [RUNNING b1i5e3kig]
   - PASS → 5-D reaches paper precision → proceed.
   - FAIL → diagnose the 5-D residual (the ~3% ui_rec issue: integrand at high-cᵇ cells)
     BEFORE building more. (A failed gate would mean Plan A needs kernel work first.)
2. taxcut_rec aCount convergence A=50→100 (confirm grid-converged, not a lucky A=50).
3. **check_rec — the bucketed-5D** (5-D joint per pLvl-bucket for the φ(pLvl) phase-out).
4. Escalate HS_Only → Reduced_Run → Baseline.
5. AD cells (rec_AD): 5-D + the AD loop (separate sub-effort).

## Running log
- 2026-06-08: scoped (3 agents); env-var policy selector added (backward-compat);
  taxcut_rec 5-D gate launched (b1i5e3kig, A=50, HS_Only). Clean start (3 scenarios
  solved incl recessionTaxCut; 11-duration Pool running).
- 2026-06-08: **taxcut_rec GATE PASSED** — 5D=0.9847 vs MC=0.9832 = **−0.15%**
  (bucket-TM was −2.34%, 234σ). A=100 confirms **grid-converged: −0.14%** (5 min @ A=50
  vs 61 min @ A=100 → A=50 is the working grid). **Plan A VALIDATED**: the 5-D joint
  closes the Jensen gap to paper precision. taxcut leg DONE.
- 2026-06-08: **check_rec bucketed-5D** built (welfare6_check_rec_bucketed5d.py;
  exposed E_check_nrm_b in tm_methods). Stale-docstring key fixed. nb=10 mechanism
  test running (b69rmhksw). Next: nb convergence sweep once nb=10 confirms direction.
- 2026-06-08: **check_rec bucketed-5D nb=10 = 1.0105 vs MC 1.0140 = +0.34%**
  (bucket-MEAN was +1.76%) — the bucketed-5D MECHANISM WORKS (closes the (a,j) Jensen).
  The +0.34% residual is the coarse pLvl-bucketing at nb=10; shrinks with more buckets.
  nb=20 escalation running (b86ph1wtm, 8 workers, ~1hr). Expect <0.25% by nb≈20-50.
  Runtime note: ~1 min/(bucket·dur·worker) → nb=50 ≈ 2.4 hr @ 8 workers (CPU); the
  JAX kernel (welfare6_tm_joint5d_jax_kernel.py) is the speedup lever if nb must go high.
- 2026-06-08: **check_rec nb=20 = 1.0100 = +0.39%** (nb=10 was +0.34%) — value moved
  AWAY from MC ⟹ CONVERGED in nb to ~+0.4%. The pLvl-bucketing is NOT the residual
  (77% closure from +1.76%, but plateaus above <0.25%). Residual is systematic; prime
  suspect = the A=50 asset grid (Check is a concentrated t=0 transfer → an asset-tail the
  coarse grid under-resolves; taxcut was diffuse and A-converged at A=50). A=30
  grid-sensitivity test running (bwg4z0917): coarser-A-more-biased ⟹ grid is the lever
  (finer A via the JAX/GPU kernel closes it); flat ⟹ diagnose the check injection.

- 2026-06-08: **conditional-init (j|pLvl) REFUTED; cause is (a|pLvl).** Built
  welfare6_jpLvl.py (analytical (j,pLvl) joint). It + the MC cross-section both show
  the marginal (j|pLvl) correlation is ~0 (E[pLvl|unemployed]=+0.9%/+1.2% in MC, NOT
  the scout's −3..−7% — that was AGE-conditional, washes out marginally; unemployed
  piles are frozen copies of the stationary employed dist). So the cheap (j|pLvl)
  re-weight does nothing. BUT the MC shows a STRONG (a|pLvl) correlation:
  E[aNrm|pLvl-bucket] runs −13%..+49% (high-pLvl agents hold high normalized assets).
  The bucketed-5D's marginal-a init over-assigns assets to low-pLvl/high-check agents
  → understates their MPC → +0.4% (right sign). The fix needs the (a,pLvl) joint
  ergodic (a new 2-D solve), NOT a cheap same-kernel re-weight. Per user stop+report:
  options = (a,pLvl) joint init (moderate) | full 6-D (large, provable) | bank +0.4%.

- 2026-06-08: **REFRAMED — the +0.4% is the MC's COLD-START init, NOT a factorization.**
  Built welfare6_ajpLvl_build.py (analytical (a,j,pLvl) joint). It correctly replicates
  the TM-a ergodic (E[aNrm] 0.309 ≈ bd 0.301, cFunc sane) and shows the ERGODIC (a|pLvl)
  is FLAT. The MC welfare panel COLD-STARTS: E[aNrm] 0.174(t0)→0.281(t5)→0.311(t39); the
  t=0 (a|pLvl) (−13..+49%) is a settling TRANSIENT that washes out to flat (−7..+5%) by
  t39 = the ergodic the TM-a inits at. So TM-a 5-D (ergodic init) vs MC (cold-start)
  differ at t=0; the MPC-sensitive one-shot Check sees it (+0.4%), diffuse TaxCut doesn't
  (matched). The (a,pLvl) joint INIT is moot (ergodic is flat). OPEN: should the welfare
  experiment be ergodic (→ TM-a 0.9965 is MORE correct; MC cold-start is the bias) or
  cold-start (→ init the 5-D from the MC t=0)? Check welfare6_scenario t=0 init. Kernel
  gained backward-compat initial_aJ_dist (useful for the cold-start-init option). Awaiting
  user steer (i: investigate MC init / ii: init from MC t=0 / iii: bank it).

- 2026-06-08: **WARM-START FIX VALIDATED — closes the check_rec cold-start gap.** Routed
  the existing Simulate.py TM-ergodic warm-start into welfare6: extracted to
  tm_methods.initialize_mc_from_tm_ergodic; welfare6_scenario opt-in HAFISCAL_WELFARE6_TM_INIT,
  injected AFTER make_history / BEFORE save_state so run_experiment's use_prestate
  (AggFiscalModel:541-542) restores the ergodic prestate. Validated: experiment now starts
  at the ergodic (t=0 E[aNrm]=0.306 vs cold 0.170). check_rec MC (HS_Only N=2000 1-seed):
  cold=1.0129, warm=1.0098 → CRN-clean shift −0.31%; the warm MC lands on the Jensen-closed
  bucketed-5D TM (1.0100). CORRECTION: the earlier "TM-a 5D=0.9965" was the OLD bucket-MEAN
  (Jensen-collapsed, +1.76%); the real TM-a 5-D = bucketed-5D = 1.0100. So the +0.4% check_rec
  gap WAS the MC cold-start; warm-starting closes it. Multi-seed N=10k SE pending. Default off
  preserves the published cold-start.

- 2026-06-08: **CORRECTION (multi-seed) — warm-start does NOT close check_rec; cold-start
  was a red herring.** The N=2000 single-seed "warm=1.0098 closes it" was noise (violated
  the multi-seed-SE rule). Robust multi-seed N=10k (4 seeds): ergodic warm MC check_rec =
  1.0196 ± 0.0006, IDENTICAL for P and Q ergodic init (the (a,j) ergodic is measure-indep
  when a⊥pLvl; pLvl sampled analytically — so the "measure bug" was also a red herring).
  1.0196 is ABOVE both cold MC (1.0140) and bucketed-5D TM (1.0100): warm-starting moved
  the MC +0.55% the WRONG way. So the cold-start was coincidentally masking a +0.95%
  ERGODIC MC-vs-TM method gap (bucketed-5D under-estimates the ergodic check welfare).
  What stands: (1) warm-start mechanism works (ergodic init, t=0 E[aNrm]=0.306); (2) clean
  ergodic ground truth = 1.0196 to validate the TM against. The bucketed-5D check_rec leg
  is NOT closed (+0.95% vs the ergodic MC). Next: diagnose the +0.95% (grid A / 5-D joint /
  bucketing) vs the new ergodic ground truth. measure default set to P (matches Simulate.py).
