# Plan 2 (v3): Solve cache + baseline-work refactor

**Status:** Draft (revision of `asymptotic-equality-driver-baseline-cache-refactor_v2.md`)
**Scope:** Item **D** plus a **new headline target**: cache the agent-type × shock-type Bellman solves across every cell, every seed, and every phase invocation that uses the same parametrization.

**Prerequisite:** Read `plans/20260408-1028h_asymptotic-equality-driver-ladder-presets_v2.md` (Plan 1 v2). Plan 2 does **not** replace Plan 1; it optimizes **internal** structure after behavior and defaults are clear.

---

## Headline profile target: Bellman solves are duplicated across cells, seeds, and phases

The single largest source of waste in the test driver is *not* the TM-P + TM-Q baseline pair, *not* the within-seed baseline-vs-policy ordering, and *not* anything inside `compute_baseline_tm_data`. It is the fact that **every cell, every MC seed, and every phase invocation re-runs `economy.solve()` from scratch on agents whose Bellman problem is identical**.

### Why the solve is reusable

The consumption function is computed by `solve_agg_cons_markov_alt` (`AggFiscalModel.py:1165`) via backward Bellman induction. It depends entirely on:

- CRRA, β, R
- LivPrb, PermGroFac
- IncShkDstn (income shock distribution)
- MrkvArray (Markov transition matrix)

It does **not** depend on:

- whether the agent will be simulated via MC or TM
- MC `AgentCount` (N) — N affects only how many draws come from the resulting cFunc
- the number of MC seeds — seeds affect only the random sampling
- TM `mCount` — mCount affects only the post-solve discretization grid
- which `--ladder` cell or which phase invocation is currently running

The cFunc is therefore a pure function of `(agent_type, shock_type, parametrization)`, and `(parametrization)` is fixed for the entire run.

### Why each shock type is its own solve

`switch_shock_type` (`AggFiscalModel.py:678`) swaps in a different `MrkvArray` and `IncShkDstn` for each policy variant:

| `shock_type` | Bellman input that changed |
|---|---|
| `base` | no-recession Markov, baseline IncShkDstn |
| `recession` | recession Markov added |
| `recessionUI` (also `UI`) | recession + extended benefits |
| `recessionTaxCut` (also `TaxCut`) | recession + tax-cut income alteration |
| `recessionCheck` (also `Check`) | recession + stimulus check |

Each is a *different* Bellman problem and requires its own solve. But each is *uniquely determined* by the shock_type — solving `recessionUI` once gives a cFunc that is bit-identical to solving `recessionUI` again. The current driver re-solves it on every invocation.

### How many unique solves vs how many actual solves

For the **full non-AD test ladder** at one parametrization, the unique solves needed per agent type are at most 5 (`base`, `recession`, `recessionUI`, `recessionTaxCut`, `recessionCheck`). Multiplied by 3 education types in `Reduced_Run`, that's **15 unique solves total** for the entire test driver.

The current driver does dramatically more. From the smoke ladder log (`history/asymptotic-equality-test-plan_revised_ladder_smoke_20260408T1240.log`):

- `recession-policies` cell 1 alone shows three "TM ref" entries of 25.8s, 33.3s, 33.1s — each one is dominated by a fresh `setup_economy → solve` cycle for one shock type.
- That's ~92s of solve work per cell × 2 cells × 3 shock types = roughly 6× duplication for that one phase.
- Across all 8 phases × 2 cells × multiple seeds, the smoke ladder pays 30+ solves where ~15 would suffice.
- At ~30s per solve, that's roughly **12 minutes of pure solve waste per smoke run** — about a quarter of the wall-clock time.

A `--ladder careful` run (`MC-large` + `TM-50`, then `MC-xlarge` + `TM-100`) hits the same multiplier on much heavier individual cells. The absolute waste scales linearly.

### The AD exception

`solve_ad_recession` (`AggFiscalModel.py:1693`) is fundamentally an iterated solve: each AD iteration re-runs `economy.solve()` under an updated `Cratio` path, and the updated `Cratio` modifies the income process via `AggDemandFac`. So:

- A non-AD solve cache **cannot** be used directly for AD iterations.
- BUT: the *first* AD iteration starts from the same Bellman as the corresponding non-AD case. So even AD experiments can reuse a cached non-AD solve as the *initial* iterate, saving one solve per AD experiment.
- Subsequent AD iterations cannot be cached across cells because the `Cratio` path is endogenous to the policy under test.

---

## New headline goal

Add a **`SolveCache`** indexed by `(parametrization, agent_type_id, shock_type)` that:

1. Stores the post-solve agent state (most importantly `agent.solution`, but also any other Bellman-derived structures the rest of the pipeline reads from).
2. Lives at *module* scope in `test_asymptotic_equality_revised.py` so it persists across phases inside a single Python process (it does not need to persist across processes — the bash loops that spawn one `python` per phase are the wrong abstraction and should be replaced; see Goals below).
3. Is consulted by `setup_economy` and by every place that currently calls `economy.solve()` directly (the test driver does this in `setup_economy`, in the per-MC-seed loop, and possibly elsewhere — needs an inventory).
4. Is invalidated only by parametrization change (which the test driver doesn't do mid-run anyway).

The cache key must include:
- `Parametrization` (e.g. `Reduced_Run`, `Smoke_Test`, `HS_Only` if added)
- An identifier for the agent type (education group + discount factor index)
- `shock_type` (`base`, `recession`, `recessionUI`, `recessionTaxCut`, `recessionCheck`)

The cache value must include:
- `agent.solution` (the cFunc / vFunc / vPfunc tuple)
- Any other agent attributes that the solve mutates and that downstream code reads (likely `agent.MrkvArray`, `agent.IncShkDstn`, `agent.Rfree`, `agent.LivPrb`, `agent.PermGroFac` after `switch_shock_type`)

### Required process-level change

The current shell wrapper that runs `--ladder smoke` is:

```bash
for phase in harness baseline norec-check ...; do
    uv run python test_asymptotic_equality_revised.py --phase $phase --ladder smoke ...
done
```

Each `python` invocation is a fresh process and a fresh module-level cache. The cache only helps when the dispatcher runs multiple cells *and multiple phases* in one process. So either:

1. Change the wrapper to call `--phase all --ladder smoke`, letting `main()` dispatch every phase × every cell inside one Python process. The existing dispatcher already supports `--phase all`. **Recommended.**
2. Or persist the cache to disk between processes (more complex, more risk of stale-cache bugs).

Option 1 is one line of shell change for the test driver, plus a one-line change to `--ladder`'s startup banner so that "(8 phases) × (2 cells) = 16 dispatch invocations" runs as one Python process. This is a **prerequisite** for the cache to deliver its full benefit.

---

## Original Plan 2 v2 goals (still in scope)

(The headline target above is *new* in v3; the items below carry forward from v2.)

1. **Profile** the hot path under the *current* multi-grid defaults, before Plan 1 v2 simplifies them. Without profile data, the actual ordering of duplication targets after solve-caching is unclear — it might be the TM-P + TM-Q pair, it might be the per-seed `mc_burnin`, or it might be something not yet identified.
2. **Refactor** only where profiling shows clear duplication that the solve cache *doesn't* already eliminate.
3. **Preserve** numerical outputs to the tight per-period band defined in the Acceptance section (no longer "bit-identical").
4. **Hard requirement on `save_state` / `restore_state`** for any extracted helper, to forestall mutable-economy bugs.

---

## Tasks

1. ✓ **Profile-first instrumentation.** `profile_block` context
   manager added, gated by `HAFISCAL_PROFILE=1`. Wrappings cover:
   `setup_economy.solve(base)`, `run_mc_norec_experiment.solve` /
   `run_experiment` per shock_type, `run_mc_recession_experiment.solve`
   per shock_type, per-seed `setup_economy` /
   `compute_baseline_tm_data` / `mc_burnin` / `run_experiment(base)` /
   `policy_solve` in `_run_norec_experiment`,
   `_run_recession.setup_economy_tm` /
   `compute_baseline_tm_data_tm` / `run_experiment_tm(base, …)`.
   AD iteration sites are not yet instrumented (Phase 7 is a stub).

2. ✓ **Solve cache (the headline).** `SOLVE_CACHE: dict[(parametrization,
   shock_type), list[deepcopy(agent.solution)]]` and
   `solve_or_cache(economy, shock_type, parametrization=None)`
   helper. Wired into all `economy.solve()` call sites that follow
   a `switch_shock_type`, plus the base solve inside
   `setup_economy`. Set `HAFISCAL_NO_SOLVE_CACHE=1` to disable.
   `report_solve_cache_stats()` prints hit/miss summary at end of
   run. Smoke verification on `--phase norec-check --ladder smoke`
   measured **85.7% hit rate** (12 hits / 2 misses, 2 unique
   entries).

3. ☐ **Single-process dispatch.** Change the smoke-ladder shell
   wrapper to invoke `--phase all --ladder smoke` once, instead of
   looping `--phase X` per phase. Without this, the cache only
   survives within a single phase invocation; the cross-phase win
   remains unrealized. **Status:** the driver supports
   `--phase all`; the wrapper update is straightforward but not
   yet done. (Tracked separately under "history/ ladder scripts".)

4. ☐ **Extract `run_mc_baseline_then_policy`** helper *only if*
   profiling after the solve cache lands shows that the
   baseline-vs-policy ordering still has duplication worth
   removing. **Status:** profile data from the smoke-test run
   shows the cache hits eliminate ~85% of solve work; the helper
   extraction may be unnecessary. Re-evaluate after the
   single-process dispatch lands.

5. ☐ **Apply same caching to AD experiments' first iteration** if
   the AD code path is reachable from the test driver (currently
   the test driver's Phase 7 ad-loop is a stub; this task is
   contingent on Phase 7 being implemented).

6. ☐ **TM-P + TM-Q baseline pair** (Phase 1): keep as a profile
   target but it's now secondary. Only worth caching if profile
   data shows it dominating after the solve cache lands.

7. ☐ **Regression check** (per Acceptance section above): full
   per-period series at `rtol/atol = 1e-9`, multipliers at
   `rtol/atol = 1e-12`, covering at least one no-recession phase
   + one recession phase + one `--ladder smoke` cell + one
   `--ladder quick` cell at `MC-med + TM-100`. Compare cache-on
   vs `HAFISCAL_NO_SOLVE_CACHE=1`. **Status:** infrastructure for
   the cache disable is in place; the actual regression script
   has not yet been written.

---

## Non-goals

(Carried forward from v2.)

- Changing default `--mc`/`--tm` or adding `--ladder` (Plan 1 v2).
- Skipping the **policy** `solve()` for *uncached* shock types.
- **Caching `setup_economy` across MC seeds.** Per-seed `setup_economy` is intentional: it re-seeds the agent RNG so each seed produces an independent MC sample. The solve cache is **not** the same as caching `setup_economy` — the cache stores only the *Bellman result*, which is RNG-independent. Each MC seed still re-runs `mc_burnin` and `run_experiment` against fresh draws; only the cFunc is reused.
- Eliminating `[math-deriv]` print sites or letting `MATH_REFS` lookups go stale during refactor.

---

## Acceptance

### Numerical regression criterion (from v2 — direction matters, not bit-identity)

The acceptance band for numerical equality between cache-on and
cache-off (`HAFISCAL_NO_SOLVE_CACHE=1`) runs has **two tolerance
levels**:

1. **Tight band — full per-period series, not just NPV scalar.** For
   each phase exercised by the regression test, capture the
   per-period `AggCons` and `AggIncome` series (and per-type variants
   where the runner produces them) before and after the cache at a
   fixed seed, fixed `Parametrization`, fixed `--ladder` cell. Assert
   that **every per-period element** agrees to within
   `rtol = 1e-9` and `atol = 1e-9` (i.e. essentially numerical noise
   from associative re-ordering, but tighter than any
   floating-point-relevant statistic). This catches RNG-ordering
   shifts because such shifts produce differences orders of
   magnitude larger than `1e-9` even at small N.

2. **Loose band — multipliers and aggregates.** NPV multipliers,
   per-cell summary numbers, per-type moment tables: agree to
   `rtol = 1e-12, atol = 1e-12` (they should match exactly to double
   precision because they are derived from the per-period series via
   deterministic linear operations).

If the per-period series passes the tight band but the multipliers
fail the loose band, the bug is in the post-processing pipeline, not
the cache — investigate and fix before merging.

If the per-period series **fails** the tight band, the most likely
cause is RNG ordering or stale-cache state. Do **not** widen the
band — diagnose. Common causes:
- The cache is returning a shared object instead of a deepcopy, so
  later mutations leak into the cached version.
- A `save_state` / `restore_state` pair is missing around a code
  path that mutates `agent.solution` after the cache lookup.
- `pre_solve` / `post_solve` side effects are not being reproduced
  on cache hit.

### Coverage criterion (from v2)

The regression check must run on at least these combinations:

- One **no-recession** policy phase (e.g. `norec-taxcut`).
- One **recession** policy phase (e.g. `recession-policies` for
  `recessionCheck`). The recession path is the most fragile because
  `act_T` is restored after `switch_to_counterfactual_mode` and that
  ordering must be preserved.
- A `--ladder smoke` cell (paired-cell wiring; quick).
- A `--ladder quick` cell at `MC-med + TM-100` (large enough that
  RNG-ordering shifts stand out clearly above sampling noise).

For each combination, run the per-period series check and the
multiplier check. Document the seed used.

### Wall-clock criterion (from v2 + v3)

- Wall-clock time reduction documented in commit message (e.g. "~X%
  on `norec-taxcut --ladder smoke`").
- Code paths remain easier to follow than before (`solve_or_cache`
  helper documents the cache contract; explicit profile_block
  wrappers at every hot site).

### v3-specific acceptance

- **Solve count.** With `HAFISCAL_PROFILE=1` set, a
  `--phase all --ladder smoke --parametrization Reduced_Run`
  invocation must run **at most 15 unique solves** (3 education
  types × 5 shock types). Anything more indicates the cache is
  failing to hit.
- **Cache hit rate.** Single-phase --ladder runs should achieve
  ≥80% hit rate after the first cell. Smoke verification on
  `--phase norec-check --ladder smoke` measured **85.7%**
  (12 hits / 2 misses, 2 unique entries: base + Check). ✓ MET.
- **Wall-clock.** The same invocation should run **at least 15%
  faster** than the cache-disabled run. At smoke scale the solve
  is a smaller fraction of total time than at full scale, so 15%
  is a conservative floor; expect ~25–30% in practice. At
  `--ladder careful` scale, the saving could approach 50%.

---

## Risks

- **Stale cache from in-place mutation.** If any code mutates `agent.solution` or related fields after the cache stores them (e.g. AD loops, post-solve transformations), the cached version is wrong on the next read. Mitigation: store a *deepcopy* of the solution into the cache, and return a deepcopy on hit. The deepcopy cost is negligible compared to a fresh solve.
- **Cache key incompleteness.** If the solve depends on something not in the cache key (e.g. an agent attribute that varies between cells without being captured), the cache will quietly serve stale data and produce wrong multipliers. The regression check (Acceptance §1) is the safety net; if the per-period band fails after the cache lands, the cause is almost certainly an incomplete key.
- **Single-process dispatch hides phase failures.** When 8 phases run in one process and phase 4 crashes, phases 5–8 don't run. With the current per-phase shell loop, a crash in one phase still lets later phases proceed. Mitigation: wrap each phase invocation inside `main()` in a `try / except` that logs the failure and continues to the next phase (similar to what the shell wrapper does today).
- **Mutable economy state shared between baseline and policy.** (v2.) Refactors that rely on the caller having already called `save_state()` (or that mutate the economy in place between baseline and policy) can introduce subtle bugs. Hard requirement for any extracted helper: call `save_state()` itself before the baseline run and `restore_state()` (or deepcopy) before `switch_shock_type` — do not delegate this to the caller.

- **RNG-ordering shifts from helper extraction.** (v2.) The most likely failure mode of any helper extraction. The tight per-period band in the Acceptance section is designed specifically to catch this; do not loosen it without diagnosis.

- **Loss of `[math-deriv]` citations.** (v2.) Helpers extracted from phase runners may absorb the `print(f"  [math-deriv] ...")` calls, hiding them from the caller's output. The helper docstring must explicitly carry the `MATH_REFS` keys it consumes, and the print sites must remain at the same logical level (one print per comparison table, not buried inside a helper).

- **Profiling under post-Plan-1 defaults.** (v2.) If Plan 1 v2 lands first and the per-phase defaults are simplified (paired-cell), profiling will not exercise the multi-grid TM loop and any duplication there will go unnoticed. Already addressed by the profile-first instrumentation landing before any helper extraction.

---

## Dependencies

- **Plan 1 v2** should land first only for the user-visible behavior. Profiling for v3 should run against the *current* multi-grid defaults if those still exist; otherwise against the explicit `--mc MC-tiny MC-small --tm TM-50 TM-100` invocation that approximates them.
- Sequence:
  1. Add `profile_block` wrapping to all hot sites (Task 1).
  2. Run `HAFISCAL_PROFILE=1 ./reproduce/some_smoke.sh` and inspect timings.
  3. Confirm solves dominate (expected from log evidence above).
  4. Implement the solve cache (Task 2).
  5. Change to single-process dispatch (Task 3).
  6. Re-profile to confirm cache hit rate; check for new bottlenecks.
  7. Helper extraction (Task 4) only if still warranted.
  8. Regression check (Task 7) as the final gate.

---

## Why this version exists

This document supersedes `asymptotic-equality-driver-baseline-cache-refactor_v2.md`. Changes:

1. **New headline target: solve caching.** v2 framed the refactor around the within-seed baseline-vs-policy ordering and the TM-P + TM-Q duplication. Both are real, but profile-aware analysis (Plan 1 v2 implementation work + smoke ladder log inspection) shows that the dominant waste is the *Bellman solve*, which is identical across cells, seeds, and phases for any given `(agent_type, shock_type)`. The cFunc is a pure function of those keys; everything downstream of the solve (MC simulation, TM construction, multiplier computation) is post-processing that can use the same cFunc multiple times.

2. **Single-process dispatch is now a prerequisite.** v2 implicitly assumed the existing per-phase shell loop. v3 requires `--phase all --ladder X` to run in one Python process so the in-memory cache survives across phases and cells.

3. **The TM-P + TM-Q baseline pair is demoted** from "obvious cache target" (v2) to "secondary, only if profile shows it dominating after the solve cache lands". The solve dominates by 10–100× over TM construction at smoke scale; the TM duplication is real but small in absolute terms.

4. **v3 acceptance adds a solve-count criterion.** "At most 15 unique solves per `--phase all --ladder smoke` invocation at `Reduced_Run` (3 types × 5 shock types)" is a sharp, observable test of cache correctness that doesn't rely on wall-clock measurement noise.

5. **AD-iteration integration** is now explicitly listed as a future task (the first AD iterate can be served from the non-AD cache), even though it's blocked on Phase 7 ad-loop being implemented.
