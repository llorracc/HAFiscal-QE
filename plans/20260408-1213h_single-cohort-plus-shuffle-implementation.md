# Plan: Single-cohort parametrization + deterministic Markov shuffle

**Date:** 2026-04-08
**Goal:** Make MC sampling variance on per-period AggCons *essentially zero*
at smoke / parity scale by combining (a) a single-cohort parametrization
that reduces the binding "rarest agent type" share to 1.0, with (b) a
deterministic Markov shuffle that replaces stochastic micro-state draws.

**Why both pieces are needed.** The shuffle alone doesn't help if the
rarest cohort × β-bin has too few agents — then the rare states fall back
to stochastic draws and you keep the variance you were trying to eliminate.
The single-cohort parametrization alone doesn't help if the underlying
state-transition draws are still stochastic. Together, at `N ≈ 1,500`
they admit a fully deterministic per-period micro-state evolution.

**Estimated total effort:** 1–2 days. Plan is split into 4 phases that
land independently.

---

## The threshold reminder

From `plans/20260408-1024h_minimum-replicates-for-shuffle.md` and the four-element
decomposition:

$$N_{\text{total}}^{\text{perfect}} \;\geq\; \frac{J_{\min} \cdot n_\beta}{s_{\min} \cdot \pi_{\min}}$$

with `J_min ≈ 6` (Rspell=6), `s_min ≈ 0.005` (state 3 ergodic share),
`π_min` = rarest type's population share, `n_β` = discount-factor bins
per education group.

| parametrization | `π_min` | `n_β` | `N_total^perfect` |
|---|---|---|---|
| Reduced_Run (3 educ × 1 β) | 0.093 (dropouts) | 1 | ~12,900 |
| Baseline (3 educ × 7 β) | 0.013 (dropout × 1 β bin) | 7 | ~90,300 |
| **HS_Only (proposed)** | **1.0** | 1 | **~1,200** |

A single-cohort parametrization at `N ≈ 1,500` is in the regime where
*every* source state has ≥ J_min = 6 agents — the floor allocation is
non-degenerate everywhere and the shuffle delivers full benefit.

---

## Phase 1 — `HS_Only` parametrization (Strategy A)

**Goal:** Add the parametrization without breaking the existing 3-cohort
structure.

**Approach:** Strategy A from the prior `HS_Only` scoping. Override
`data_EducShares` to `[0.0, 1.0, 0.0]` for `HS_Only`, leave the
3-`BaseTypeList` infrastructure intact, accept that the dropout and
college types still get *constructed and solved* but contribute zero
agents to the simulation. Cleanest for blast radius; minor wall-clock
cost from the two unused solves.

**Files touched:**

- `Code/HA-Models/FromPandemicCode/Parameters.py`:
  - line 271 area: add `HS_Only` to the
    `Reduced_Run`/`Smoke_Test` group (same horizons, same DiscFacCount=1).
  - line 593 area: add `HS_Only` branch with `AgentCountTotal = 1500`
    (or whatever N you want; 1500 leaves headroom above the 1,200
    threshold).
  - return-tuple area: override `data_EducShares` with `[0.0, 1.0, 0.0]`
    when `Parametrization == "HS_Only"`. This keeps the import from
    `EstimParameters.py` unchanged for everything else.

- `Code/HA-Models/FromPandemicCode/test_asymptotic_equality_revised.py`:
  - `setup_economy` (around line 320): the existing
    `for e in range(3)` loop already does
    `AgentCount = floor(N * data_EducShares[e])`, which yields 0 for
    masked-out cohorts. Replace the `max(AgentCount, 1)` guard with
    `if AgentCount == 0: continue` so dropout / college types are
    skipped entirely instead of getting a forced 1-agent slot.

**Acceptance:**

- `uv run python test_asymptotic_equality_revised.py --phase harness --parametrization HS_Only`
  prints `EducationGroup: 1 , betaDistr : [0.9248]` only (one line).
- `economy.agents` after `setup_economy` has length 1, all 1500 agents.
- `--phase baseline --ladder smoke --parametrization HS_Only` runs
  without errors.

**Risks:**

- The print statements in the per-cohort iteration may emit empty
  output for the masked types — cosmetic, not blocking.
- `Welfare.py` and `Output_Results.py` may iterate
  `for e in range(3)` somewhere; not a problem for the test driver but
  blocks future use of `HS_Only` through the full reproduction
  pipeline. Out of scope here; flag if hit.
- `EstimParameters.py` constants (`num_types = 3`) are out of scope;
  estimation pipeline uses its own loop and doesn't need `HS_Only`.

**Effort estimate:** 1–2 hours including verification.

---

## Phase 2 — Diagnostic: `compute_min_agents_for_shuffle()`

**Goal:** Before implementing the shuffle, compute and report which
(type, source-state) pairs in a given economy fall below the
`J_min(j)` threshold. This makes Phase 3 testable and gives a clear
"go / no-go" signal for any future N tier.

**Approach:** A standalone helper that takes an `AggregateDemandEconomy`
and returns a list of `(type_idx, source_state, expected_N_j, J_min_j,
viable: bool)` tuples. Iterate over each agent type, compute the ergodic
distribution from `compute_baseline_tm_data` (or, simpler, from the
agents' analytical formulas), multiply by `agent.AgentCount`, and compare
against `ceil(1 / min(p_jk for p_jk > 0))` for each row of
`CondMrkvArrays[macro_state=0]` (no recession).

**Files touched:**

- New file: `Code/HA-Models/FromPandemicCode/markov_shuffle_diag.py`
  with `compute_min_agents_for_shuffle(economy)` and a `print_report`
  helper.
- Optionally a `--shuffle-diag` CLI flag in the test driver that
  prints the report at startup.

**Acceptance:**

- For `Reduced_Run` at `N=1000`:
  - dropout state 3 expected ≈ 0.5% × 1000 × 0.093 ≈ 0.5 agents → NOT viable
  - HS state 3 expected ≈ 0.5% × 1000 × 0.527 ≈ 2.6 agents → NOT viable
- For `HS_Only` at `N=1500`:
  - HS state 3 expected ≈ 0.5% × 1500 × 1.0 ≈ 7.5 agents → ✓ viable
  - HS state 0 (employed) ~1430 agents → ✓ viable (trivially)
- For `Baseline` at `N=10000`:
  - dropout × 1 β bin state 3 ≈ 0.5% × 10000 × 0.093/7 ≈ 0.07 → NOT viable
- The diagnostic must print the binding (type, state) pair and the
  recommended `N_total` to fix it.

**Risks:**

- Getting the ergodic state shares right requires the right unemployment
  rate; use the per-type `Urate_normal_*` (already in `EstimParameters`)
  rather than a global average.

**Effort estimate:** 2–3 hours.

---

## Phase 3 — Wire the deterministic shuffle into `get_micro_markv_states_guts`

**Goal:** Replace the per-agent `np.searchsorted(Cutoffs[j,:], unemployment_draw[these])`
draws in `AggFiscalModel.py:763–769` with a deterministic floor-plus-leftover
allocation when the source-state agent count is large enough.

**Approach:** For each `(macro state i, source state j)` group of
size `N_j`, instead of drawing `N_j` uniform samples and bucketing by
cumulative-probability cutoffs:

1. Compute exact `floor_assignment[k] = floor(N_j × p_jk)` for each
   destination `k`.
2. Compute `leftover_count = N_j - sum(floor_assignment)`.
3. Allocate the leftover deterministically:
   - Either always to the destination(s) with the largest fractional
     remainder (Hamilton method, which minimises the
     allocation-error), or
   - To the first destinations in row order until exhausted (simpler
     but biased — only acceptable if leftover is small relative to
     `min(N_j × p_jk)`).
4. Replace the random `unemployment_draw[these]` lookup with a
   deterministic permutation of agent indices into the destination
   slots — *but use the same RNG-driven permutation* as the current
   code so the assignment of *specific agents* to destinations remains
   reproducible. Only the *count* per destination becomes deterministic.

**Critical guard:** if `N_j < J_min(j)`, fall back to the current
stochastic draw. This is the "adaptive shuffle" from
`plans/20260408-1024h_minimum-replicates-for-shuffle.md` §3.2.

**Files touched:**

- `Code/HA-Models/FromPandemicCode/AggFiscalModel.py`:
  - `get_micro_markv_states_guts` (line 750): the inner double loop
    over `(i, j)` pairs is the only site that needs to change.
  - The current threshold check
    `if these.sum() >= J` (where J = number of states)
    is too lax — change to `if N_j >= J_min(j)`.

**Acceptance:**

- Bit-identical AggCons at the *aggregate* level when comparing
  shuffle-on vs shuffle-off at large N (where the shuffle's leftover
  is negligible). The per-period AggCons series should agree to
  `rtol = 1e-3` because the only difference is which specific agents
  occupy which states, and `c(m, j)` is smooth in m.
- For `HS_Only` at N=1500, all source-state populations exceed
  `J_min(j) = 6`, so every transition uses the shuffle (no stochastic
  fallback). Verify with the Phase 2 diagnostic.
- Run two seeds with `HS_Only` at N=1500. The per-period AggCons
  series should agree across seeds **to within numerical noise from
  the leftover-allocation step only**, *not* to within MC sampling
  variance. Concretely: across seeds, AggCons at every period should
  agree to `rtol < 1e-3`. (The cross-seed difference is what would
  be MC noise without the shuffle; with the shuffle it shrinks to
  the leftover-allocation jitter, which is at most one agent per
  destination per period.)

**Risks:**

- **The leftover allocation introduces a deterministic but
  parametrization-sensitive bias.** If you allocate leftover to row
  index 0 always, the resulting state distribution is biased toward
  state 0. The Hamilton method (allocate to largest fractional
  remainders) minimises this. Use Hamilton.
- **RNG ordering**: the current code uses `unemployment_draw` for
  per-agent assignment, which is RNG-dependent. The shuffle should
  preserve this — only the *count* per destination is deterministic;
  the *which agent goes where* is still RNG-driven. This avoids
  cross-seed correlation.
- **Smoke at small N**: if you try to run `Reduced_Run` at N=1000
  with the shuffle wired in, the rare states will fall back to
  stochastic and you'll get LESS variance reduction than promised
  (because some states are in the shuffle regime and others are not).
  The diagnostic from Phase 2 makes this visible.

**Effort estimate:** 4–6 hours including the cross-seed AggCons
verification.

---

## Phase 4 — Verification: zero-MC-variance smoke test

**Goal:** Demonstrate that under `HS_Only` at `N=1500` with the shuffle
enabled, two MC seeds produce identical per-period AggCons (modulo the
sub-1% leftover-allocation jitter).

**Approach:** A new test phase or a stand-alone script that:

1. Runs `setup_economy(Parametrization="HS_Only")` with `AgentCountTotal=1500`.
2. Runs the diagnostic from Phase 2 and asserts every (type, state)
   pair is viable.
3. Runs the baseline experiment with `seed_offset = 0`, captures the
   per-period `AggCons` series.
4. Repeats with `seed_offset = 100`, captures the second series.
5. Asserts `np.allclose(series_0, series_1, rtol=1e-3)`. (Tighter
   tolerance is possible if the Hamilton allocation is deterministic
   in the seed-independent sense.)
6. For comparison, runs the same test with the shuffle disabled
   (use a `HAFISCAL_NO_SHUFFLE=1` env var to gate the new code) and
   shows the cross-seed gap is now ~3% (the un-reduced MC noise
   floor at N=1500 single-seed).

**Files touched:**

- New: `Code/HA-Models/FromPandemicCode/test_perfect_shuffle.py`
  (or a new phase in `test_asymptotic_equality_revised.py`).

**Acceptance:**

- `python test_perfect_shuffle.py` exits 0 and reports
  `cross-seed AggCons relative gap: < 0.1%` with shuffle on.
- `HAFISCAL_NO_SHUFFLE=1 python test_perfect_shuffle.py` reports
  `cross-seed AggCons relative gap: ~3%` (un-reduced).
- The ratio of those two numbers documents the shuffle's variance
  reduction at this scale.

**Risks:**

- If Phase 3 introduces a leftover-allocation bias that's not seed-
  independent (e.g., the Hamilton tiebreaker depends on insertion
  order, which depends on agent labelling, which depends on seed),
  the cross-seed gap won't shrink to zero. Diagnose by running the
  Hamilton step at higher precision and verify the per-state allocation
  counts are seed-independent.

**Effort estimate:** 2–3 hours.

---

## Phase ordering and what each phase unlocks on its own

| Phase | Standalone benefit |
|---|---|
| 1 | `HS_Only` parametrization usable for any test, even before the shuffle lands. ~10× faster smoke runs because only 1 type instead of 3 (per-cohort N at N_total=1500 is ~1500 instead of ~140). |
| 2 | Diagnostic reports work for *any* parametrization, not just HS_Only. Tells you when an existing run is in the "shuffle would help" regime. |
| 3 | Variance reduction for *all* runs, not just HS_Only. The biggest cohort (employed at 95.6%) gets the shuffle even at small N. |
| 4 | Acceptance evidence for a "perfect" config. If we ever want to make a strong reproducibility claim, this is the run that backs it. |

Phases 1, 2, 3 are independent and can land in any order. Phase 4
depends on all three.

---

## Out of scope (deferred)

- **Wiring `HS_Only` through the full reproduction pipeline**
  (`reproduce.sh --comp full --hs-only`). The full pipeline goes
  through `Welfare.py` and the multi-cohort tables, both of which
  assume 3 types. Out of scope; the test driver path is enough for
  the validation goal.
- **Larger-N shuffle for `Reduced_Run` / `Baseline`.** Even with the
  threshold check in Phase 3, those parametrizations need
  `N_total ≥ 13,000` / `≥ 90,000` for the perfect regime. That's a
  separate scaling project.
- **Changing the calibration** to relax `J_min` (e.g., shorter
  `Rspell`). Not on the table; calibration is fixed by the paper.
- **Quasi-Monte Carlo for permanent / transitory shocks.** The shuffle
  only addresses Markov-state transitions. The `PermShk` and `TranShk`
  draws inside each state are still stochastic. Reducing those is a
  separate variance-reduction project (low-discrepancy sequences,
  antithetic variates, etc.).

---

## Decision points before starting

1. **Which cohort?** HS is the recommended choice (52.7% of population,
   median calibration parameters). If for some reason you want
   college (38.0%) or dropout (9.3%), the parametrization name and
   the index in `data_EducShares` change accordingly.

2. **What `N_total` for HS_Only?** Plan defaults to 1500. The minimum
   "perfect" N is 1200; 1500 leaves a 25% headroom. If wall-clock
   matters, 1200 works. If you want margin, 2000 is fine.

3. **Hamilton vs largest-row leftover allocation?** Plan defaults to
   Hamilton (largest fractional remainder). It's only ~5 lines more
   than naive but eliminates a known bias direction.

4. **Where does the diagnostic live?** Plan suggests
   `markov_shuffle_diag.py`. Could also live inside `tm_methods.py`
   or as a method on `AggregateDemandEconomy`. Bikeshed; not blocking.

5. **Do we want a `HAFISCAL_NO_SHUFFLE=1` escape hatch?** Plan
   includes it for the regression check in Phase 4. Optional but
   recommended; symmetric with `HAFISCAL_NO_SOLVE_CACHE=1`.
