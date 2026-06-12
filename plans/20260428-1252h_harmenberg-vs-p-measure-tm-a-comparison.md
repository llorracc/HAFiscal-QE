# Plan: compare Harmenberg-neutral (Q-measure) vs P-measure TM-a results

**Created:** 2026-04-28
**Branch:** `bug034-035-cdc-consistency-cleanup`
**Author:** CDC + Claude Opus 4.7
**Related conclusions:**
- `conclusions_private/2026-04-28_cdc-esc-asset-rule-is-2pp-and-scales-with-beta.md` — Phase 2 multipliers (computed under P-measure)
- `conclusions_private/2026-04-15_bug033-tm-a-kernel-required-for-unbiased-multipliers.md` — TM-a kernel design

## 1. Question

By Harmenberg's identity `E_P[p · f(m)] = E_P[p] · E_Q[f(m)]`, P-measure and Q-measure should give **identical answers** for p-linear aggregates (consumption levels, income levels, asset levels, multipliers built from these). Q-measure typically has lower numerical noise because the `pLvl` dimension collapses.

**Question:** does the TM-a kernel implementation honor this identity to within numerical precision? If not, where's the bug?

This is a methodology hardening test for Phase 2's CDC↔ESC conclusions, not an experiment to change them. Phase 2 numbers are reported under P-measure (matching production Baseline default `tm_neutral_measure=False`). If P↔Q agree, Phase 2 conclusions are reinforced. If they disagree, that's a kernel bug that needs investigation BEFORE publication.

## 2. Background

- The TM-a kernel supports both measures via the `neutral_measure` boolean parameter, threaded through `propagate_experiment_tm_a` (`tm_methods.py:3401`), `compute_period_aggregates_tm_a` (`tm_methods.py:3187`), `build_experiment_period_tm_a` (`tm_methods.py:3310`), `compute_baseline_tm_data` (line 2169), and `run_experiment_tm_nonbase` (line 2256).
- Production `Simulate.py:131` defaults to `tm_neutral_measure = False`. Only `AggFiscalMAIN_reduced.py:49` sets `tm_neutral_measure = True` (Reduced_Run path).
- All Phase 2 drivers (`phase2_*_cdc_vs_esc.py`) hardcoded `neutral_measure=False`. The drivers can be re-run with `neutral_measure=True` by changing one constant per driver.
- For p-linear aggregates (the Phase 2 multipliers): P and Q should agree to numerical precision asymptotically.
- For non-p-linear aggregates (e.g. CRRA welfare with γ ≠ 1): P and Q differ by an `E[p^(1-γ)]` factor that must be tracked separately under Q. **This plan does NOT cover welfare** — sub-task 2.4 is postponed and welfare is a Q/P-different aggregate that requires care; treat separately when it's reactivated.

## 3. Cascade-gate structure

Each tier has:
- A **scope** (parametrization / number of types / scenario)
- An **expected result** (P vs Q agree within X)
- A **gate criterion** (the relative difference threshold; if exceeded, HALT and investigate)
- A **cost estimate**
- A **next-tier action** (escalate only on clean pass)

**Default gate (initial pass)** — unless tier overrides: for any p-linear aggregate compared at any time point t, the relative difference `|P_t − Q_t| / |P_t|` must be < **1%** (1e-2). For multiplier ratios, the absolute difference must be < **1pp** (i.e., 0.01 on a multiplier of order 1).

**Tightening pass:** if the initial 1% / 1pp cascade passes cleanly through Tier D, optionally redo with the tighter **0.1% / 0.1pp** gate to look for sub-percent kernel divergences. Only do the tightening pass if the initial pass succeeds.

**Why start loose:** observed MC↔TM grid effects in Phase 1 / production are at the 0.01-0.1% level at standard mCount, and CDC↔ESC effects we care about are at the ~1-2pp level. A 1% / 1pp gate confidently detects multiplier-relevant divergences without flagging numerical noise. The tighter 0.1% / 0.1pp gate is appropriate for kernel-correctness verification once the loose pass establishes baseline agreement.

**HALT criterion:** if any tier fails its gate, halt cascade and investigate. The investigation steps (per tier) are listed in §6.

## 4. Tier 0 — Fastest case (1 HS agent, baseline only)

**Scope:**
- 1 single HS agent (`phase2_check_cdc_vs_esc.py`'s `build_HS_economy` pattern: `AggFiscalType` from `init_highschool` with mid-β atom = 0.9302, AgentCount=1, `tm_a_indexed=True`)
- Just the macro-0 baseline trajectory under `propagate_experiment_tm_a` (no policy, no recession, no AD)
- Both interpretations (CDC, ESC) computed under both measures
- act_T = whatever the default is for Reduced_Run (~30 quarters)

**What's compared:**
- AggCons_pc[t] for all t — both methods should give the same number for every period
- AggIncome_pc[t] for all t

**Gate (initial):**
- Per-period rel diff `|P_t − Q_t| / |P_t|` < 1% for both AggCons and AggIncome
- For ALL t (not just t=0)
- Both interpretations

**Implementation:**
- Smallest possible standalone script: builds 1 agent, calls `compute_baseline_tm_data` and `propagate_experiment_tm_a` four times (CDC×P, CDC×Q, ESC×P, ESC×Q), prints rel diff per period and max rel diff.
- ~10 min code + ~1 min compute total. **This should run in under 10 min wall time end-to-end** including writing the script.

**Why Tier 0 first:** if 1-agent baseline P↔Q disagree by >1%, the kernel-level Q reweighting is fundamentally broken; no point running anything bigger until that's fixed. This is the strictest gate against an "obvious" implementation bug.

**If clean pass:** escalate to Tier A (Reduced_Run multi-cohort baseline).

**If fail:** investigate per §6.0 (it's a fundamental kernel bug):
- Check `_to_neutral_measure` reweighting formula (`tm_methods.py:406`).
- Print P-measure vs Q-measure IncShkDstn atoms side-by-side; verify pmv reweight is `psi^(-1) / E[psi^(-1)]`.
- Check that Q-measure ergodic integrates to 1.
- Verify `pLvl_factor` recurrence and `E[p]` level-aggregation in `compute_period_aggregates_tm_a` and `propagate_experiment_tm_a`.

## 5. Tier A — Reduced_Run multi-cohort baseline

**Scope:**
- Parametrization: `Reduced_Run` (single β atom per cohort, but all 3 cohorts: DO + HS + CO)
- 3 types total
- `tm_a_indexed=True`
- macro-0 baseline trajectory only

**What's compared:**
- Per-cohort AggCons_pc[t] AND population-aggregate AggCons_pc[t]
- AggIncome_pc[t]

**Gate:**
- Per-period rel diff < 1% for both AggCons and AggIncome
- Both per-cohort AND population-aggregate

**Cost:** ~10 min code (extends Tier 0 driver to 3 cohorts) + ~3 min compute = ~15 min total.

**If clean pass:** escalate to Tier B.

**If fail:** investigate per §6.A — likely cross-cohort interaction with Q reweighting (e.g., per-cohort `E[pLvl]` accounting differs under Q).

## 5. Tiers B through D

### Tier B — 7-atom HS baseline + one policy (no-recession Check)

**Scope:**
- `Baseline` parametrization, single HS cohort, all 7 β atoms
- Macro-0 baseline + no-recession Check via `phase2_multibeta_cdc_vs_esc.py` (HS-only)
- Both interpretations

**What's compared:**
- Baseline AggCons trajectories
- Check experiment AggCons / AggIncome trajectories
- Multiplier ratios (NPV(C diff) / NPV(Y diff))

**Gate:**
- Per-period rel diff < 1%
- Multiplier abs diff < 1pp (this matters because multipliers are bounded ratios)

**Cost:** ~20 min code + ~30 min compute (with within-scenario duration parallelism, but no-recession Check is short; ~5 min per scenario × 4 scenarios in parallel) = ~50 min total.

**If clean pass:** escalate to Tier C.

**If fail:** investigate per §6.B (likely β-atom interaction with Q-reweighting).

### Tier C — Full 21-type Baseline, no-recession only

**Scope:**
- `Baseline` parametrization, full 21-type population
- macro-0 baseline + 3 no-recession policies (Check, TaxCut, UI)
- Both interpretations
- 6 scenarios per measure (3 policies × 2 interpretations) × 2 measures = 12 runs

**What's compared:**
- All 6 no-recession multipliers under both measures
- Per-cohort decomposition (DO/HS/CO) optional but recommended

**Gate:**
- Per-period rel diff < 1%
- Multiplier abs diff < 1pp
- CDC↔ESC gap difference < 1pp (i.e., the Phase 2 conclusion about ~2pp ESC>CDC must be invariant to P/Q choice)

**Cost:** ~10 min code + ~3 hr compute (each multicohort no-rec scenario is ~50 min serial; with --n_workers 5 duration parallelism N/A here since we're in no-rec mode; running 6 scenarios in parallel = 50 min wall) = ~3 hr total.

**Implementation:** add `neutral_measure` arg to `phase2_multicohort_cdc_vs_esc.py` and `phase2_AD_one_scenario.py`, then re-run the Phase 2 #4 multicohort under Q-measure.

**If clean pass:** escalate to Tier D.

**If fail:** investigate per §6.C (likely interaction between population aggregation and Q reweighting; check `_to_neutral_measure` for any per-type assumption that breaks under multi-cohort).

### Tier D — Full 21-type Baseline + recession + AD-averaged (publication-grade)

**Scope:**
- `Baseline` parametrization, full 21-type
- All 6 strict-policy scenarios (3 policies × 2 interpretations)
- AD-amplified, full averaging across recession durations
- Equivalent to the Phase 2 #4 + AD-avg work that's already committed under P-measure

**What's compared:**
- All Phase 2 multiplier numbers (no-AD strict, AD-both, QE-style)
- The CDC↔ESC gap conclusion
- Comparison to published HAFiscal-QE expected: same as P-measure result for p-linear aggregates

**Gate:**
- Per-period rel diff < 1%
- Multiplier abs diff < 1pp
- CDC↔ESC gap difference < 1pp
- Published-QE gap unchanged (i.e., the +4-6pp TaxCut residual gap is not a P/Q artifact)

**Cost:** ~mod to existing `phase2_AD_one_scenario.py` (add `neutral_measure` arg) + ~6 hr compute (6 AD-avg scenarios in parallel, each ~110 min wall; or use within-scenario duration parallelism for ~50 min wall per scenario) = ~6 hr total.

**If clean pass:** publish-ready under either measure; reinforce Phase 2 conclusions with P/Q-invariance evidence.

**If fail:** investigate per §6.D (most likely recession-state interaction with Q reweighting; check `compute_baseline_tm_data` and `propagate_experiment_tm_a` for assumptions that break under recession-Markov + Q).

## 6. Investigation playbook on gate failure

### 6.0 — Tier 0 failure (1-HS-agent baseline P ≠ Q)

A fundamental problem; if the smallest possible case fails, something is wrong in the kernel's Q-reweighting itself.

**Diagnostic steps:**
1. Print P-measure vs Q-measure IncShkDstn atoms side-by-side. Check that `_to_neutral_measure` (`tm_methods.py:406`) reweights `pmv` by `psi^(-1) / E[psi^(-1)]` correctly.
2. Verify that the Q-measure ergodic distribution (from `find_ergodic_distribution`) integrates to 1.
3. Check the level-aggregation: under Q, `E_P[p·f(m)] = E_P[p] · E_Q[f(m)]`, so the kernel should multiply by `E[p]` somewhere. Verify in `compute_period_aggregates_tm_a` and `compute_type_aggregates_tm_a`.
4. Check whether `pLvl_factor` recurrence in `propagate_experiment_tm_a` (line 3489) is being applied consistently under both measures.
5. Compare against the BST Harmenberg notebook (`Code/HA-Models/Harmenberg-Four-Way-Comparison.ipynb` §8j — the "uncorrected 1D pitfall" example).

**Likely culprits:**
- `_to_neutral_measure` reweights by wrong moment (e.g., `psi` instead of `psi^(-1)`).
- Level aggregation forgets the `E[p]` factor under Q.
- `pLvl_factor` recurrence is double-applied or skipped under Q.

### 6.A — Tier A failure (Reduced_Run 3-cohort baseline P ≠ Q)

Tier 0 (single agent) passed but multi-cohort failed → cross-cohort interaction problem.

**Diagnostic steps:**
1. Run each cohort separately under Tier 0's 1-agent harness — identify which cohort(s) cause the failure.
2. Verify per-cohort `E[pLvl]` accounting in `compute_baseline_tm_data` is consistent under P and Q.
3. Check `data_EducShares` weighting in the population aggregator under both measures.

**Likely culprits:**
- Per-cohort `E[pLvl]` computed via analytical formula assumes P-measure; need MC-derived value or a Q-aware analog under Q.
- Cohort weighting interacts with `AgentCount`-based level scaling differently under Q.

### 6.B — Tier B failure (7-atom β P ≠ Q)

Single type and Reduced_Run multi-cohort passed but multi-β failed → β-atom-specific issue.

**Diagnostic steps:**
1. Run each of the 7 β atoms separately under both measures; identify which atom(s) cause the failure.
2. Check whether the high-β atoms (near the GIC boundary) interact with Q-reweighting in a numerically unstable way.
3. Verify per-type pmv weights are correctly applied under both measures (each type is a separate column in the population aggregate).

**Likely culprits:**
- Per-type aggregation uses different weighting under P vs Q.
- Numerical instability at high-β atoms under Q (e.g., reweighted ergodic mass concentrates at grid edge).

### 6.C — Tier C failure (multi-cohort P ≠ Q)

Single-cohort multi-β passed but cross-cohort failed → cohort interaction issue.

**Diagnostic steps:**
1. Run each cohort (DO, HS, CO) separately under both measures; check per-cohort agreement.
2. Verify `EducShares` weighting is identical under both measures (it should be cohort-independent).
3. Check whether `compute_baseline_tm_data` accumulates the per-cohort `bd` lists differently under Q (might leak per-cohort `E[pLvl]` accounting).

**Likely culprits:**
- `E[pLvl]` per cohort is computed differently (analytical vs from-MC) and the analytical formula assumes P-measure.
- `data_EducShares` weighting interacts with `AgentCount` reweighting under Q.

### 6.D — Tier D failure (recession + AD P ≠ Q)

All earlier tiers passed but recession+AD failed → recession-state or AD-specific issue.

**Diagnostic steps:**
1. Test recession baseline (no policy, recession path) under both measures; check agreement.
2. Test recession + policy WITHOUT AD under both measures; check agreement.
3. If recession-no-AD passes but recession-AD fails: AD machinery bug specific to Q.
4. Check `run_ad_tm` (`tm_methods.py:2455`) for any P-measure-specific assumption in the CFunc training loop.

**Likely culprits:**
- `run_ad_tm` Phase 1 training loop computes Cratio using P-measure denominators while Q-measure numerators are accumulated (or vice versa).
- The AD `Cratio` clipping `[0.8, 1.2]` interacts with Q-reweighted Cratios differently than P.
- `compute_baseline_tm_data` under Q produces a different `E[pLvl]` that `run_ad_tm` uses inconsistently.

## 7. Implementation notes

### Code modifications needed

1. **Tier 0:** new tiny standalone script (e.g., `harmenberg_tier0.py`) — builds 1 HS agent, runs 4 baseline propagations (2 interps × 2 measures), prints rel diff.
2. **Tier A:** extend the Tier 0 script to loop over 3 cohorts (`init_dropout`, `init_highschool`, `init_college` from `Reduced_Run`).
3. `phase2_check_cdc_vs_esc.py` (Tier B/C foundation): add `--neutral_measure` arg to threaded calls.
4. `phase2_multibeta_cdc_vs_esc.py` (Tier B): add `--neutral_measure` arg.
5. `phase2_multicohort_cdc_vs_esc.py` (Tier C): add `--neutral_measure` arg.
6. `phase2_AD_one_scenario.py` (Tier D): add `--neutral_measure` arg, threaded through `compute_baseline_tm_data`, `run_experiment_tm_nonbase`, `run_ad_tm`, `propagate_experiment_tm_a`.

### Output convention

Each tier writes JSON results to a separate path (e.g., `/tmp/harmenberg_tier_{A,B,C,D}.json`) with both P and Q trajectories for each scenario, plus a per-scenario `rel_diff_max` summary scalar. A single post-processing script generates a clean P-vs-Q comparison table.

### Parallelism

- Tier 0: serial (only 4 short runs — 2 interps × 2 measures, all on 1 agent). Total <2 min.
- Tier A: serial (4 runs × 3 cohorts = 12 short runs). Total ~5 min.
- Tier B: 8 runs (2 interps × 2 measures × 2 scenarios baseline+Check) in parallel; each ~5 min.
- Tier C: 12 runs in parallel (3 policies × 2 interps × 2 measures); each ~50 min wall using existing multicohort driver.
- Tier D: 12 runs in parallel using `--n_workers 5` for within-scenario duration parallelism; each ~50 min wall (Check) or ~15 min (TaxCut/UI).

Total wall time if all tiers pass: 0 (10 min) + A (15 min) + B (50 min) + C (3 hr) + D (6 hr) ≈ **10.3 hr** sequential, ~7 hr if Tiers C+D overlap.

Total compute: ~12-14 hr CPU.

## 8. Out of scope

- **Welfare aggregation**: CRRA welfare with γ ≠ 1 is not p-linear; P and Q give different answers naturally unless a separate `E[p^(1-γ)]` correction is tracked. Welfare is sub-task 2.4 (postponed). When it's reactivated, the P/Q comparison there requires the proper non-p-linear correction; treat as a separate plan.
- **MC↔TM convergence under Q**: this plan compares P-TM-a vs Q-TM-a, NOT TM-a vs MC. The MC↔TM convergence is established under both measures by Phase 1 (P-measure) and historically by the Reduced_Run welfare reproduction (Q-measure). A direct MC↔Q comparison at Phase 2 scale is a separate plan.
- **Switching production Baseline default to Q**: out of scope. This plan validates Q for kernel-level testing; the production default change is a separate decision for the team.

## 9. Success criteria

1. **Tier 0 pass:** TM-a kernel honors P↔Q identity at the simplest possible case (1 HS agent, baseline) → kernel implementation is correct in principle.
2. **Tier A pass:** Reduced_Run 3-cohort baseline does not break P↔Q → cross-cohort aggregation is correct under both measures.
3. **Tier B pass:** β heterogeneity does not break P↔Q → Phase 2 7-atom HS results are P/Q-invariant.
4. **Tier C pass:** Multi-cohort full-Baseline aggregation does not break P↔Q → Phase 2 21-type results are P/Q-invariant.
5. **Tier D pass:** Recession + AD machinery does not break P↔Q → Phase 2 publication numbers are P/Q-invariant; the asset-rule mechanism is the dominant CDC↔ESC driver, not measure choice.
6. **Failure at any tier:** identifies a kernel bug in the P↔Q identity that needs investigation BEFORE publishing Phase 2 numbers.

A clean cascade pass to Tier D reinforces all Phase 2 conclusions and validates the kernel under an alternative measure.

## 10. Conclusion-log entry

When the cascade completes (pass or halt), add an entry to `CONCLUSIONS_private.md`:
- If pass: "TM-a kernel honors P↔Q identity to <0.1% across {scope}. Phase 2 conclusions are P/Q-invariant."
- If halt: detail the failure, the investigation findings, and the fix (if found).
