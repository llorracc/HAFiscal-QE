# HARK improvements proposal — upstream what HAFiscal had to custom-code

**Date:** 2026-05-18
**Audience:** HARK maintainers + user
**Context:** HAFiscal has accumulated 24 bug fixes + extensive `AggFiscalType` subclassing + a JAX-GPU MC pilot. Many of these represent gaps in HARK's stock capabilities. This document inventories them and proposes upstream contributions.

## Top-priority upstream contributions

Ranked by leverage (how many users would benefit × magnitude of benefit).

### 1. **JAX-GPU MC simulator** (highest leverage)
- **What HAFiscal had to build:** `jax_mc_minimal.py` (pilot, 2026-05-17→18). A pure-JAX kernel replacing HARK's OO `sim_one_period` for the inner simulation loop.
- **Demonstrated benefit:** 100–500× speedup on synthetic problems; 178× wall-time speedup vs HARK CPU MC on a HS_Only base scenario at N=1800.
- **Why this should be in HARK:** *Every* HARK user with N > 10k agents would benefit. The pattern (tabulate cFunc + run pure functions on JAX arrays + `lax.scan` over time) generalizes to any `AgentType` subclass.
- **Proposed PR:** A new `HARK.jax` module providing:
  - `tabulate_cfunc(agent, m_grid, t_cycle=None)` — flexible pre-tabulation
  - `simulate_jax(agent, T, seed)` — drop-in replacement for `agent.simulate(T)`, returning the same history dict
  - `@jax.jit`-friendly versions of `sim_one_period`, `get_states`, `get_controls`, `get_poststates`
  - Initial focus on `IndShockConsumerType` + `MarkovConsumerType` (the bases of `AggIndMrkvConsumerType`); extend to other AgentTypes incrementally.
- **Cost estimate:** 2–4 weeks of focused work. Most of the complexity is in refactoring `sim_one_period` from OO-mutating-`self` to pure-functional. Pilot proves the kernel logic is straightforward.
- **Validation requirement:** distributional match vs CPU MC within MC SE on a test suite of common `AgentType` examples.

### 2. **Stratified shuffle for `MarkovProcess.draw`** (ALREADY DONE — HARK PR #1776)
- HAFiscal BUG-044 found that the default `draw(shuffle=True)` in `HARK/distributions/base.py` breaks per-agent identity at the assignment step, biasing welfare measures by up to 8% on UI extension cells.
- The stratified-shuffle fix (sort agents by per-agent draws, assign in rank order) restores per-agent identity while preserving quota-exact counts.
- **Status:** upstreamed as HARK PR #1776. Verify merged and bump pin.

### 3. **`AggregateDemandEconomy` / aggregate-demand feedback loop** (medium leverage)
- **What HAFiscal had to build:** `AggregateDemandEconomy(Market)` in `AggFiscalModel.py`. Manages the outer aggregate-demand iteration (`mill_rule` updates `AggDemandFac`, agents re-solve with new `Cratio`, iterate to convergence).
- **Why this should be in HARK:** AD feedback is a common macro modeling pattern. Right now every project that wants AD has to roll its own.
- **Proposed PR:** A `HARK.macroeconomics.AggregateDemandMarket` class that:
  - Wraps any list of `AgentType` instances
  - Iterates `solve → simulate → update_aggregate → re-solve` until tolerance
  - Provides hooks for project-specific `mill_rule` and shock paths
- **Cost estimate:** 1–2 weeks once HAFiscal's logic is generalized. Tricky parts: the recursion between agent solve and market state, and the convergence criterion.

### 4. **Splurge consumption model** (specialized but real)
- **What HAFiscal had to build:** `Splurge` parameter on `AggFiscalType`. Modifies the consumption rule: `c_actual = (1 - S)·c*(m) + S·y` (where `c*` is the optimizer's cFunc and `y` is current income). Used in HAFiscal to match the empirical MPC distribution.
- **HAFiscal complications:** BUG-031 (splurge not in budget constraint), BUG-046 (Jensen bias on splurge-corrected welfare integrand). Multiple interpretations (CDC vs ESC reading; see `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md`).
- **Why this might be HARK-worthy:** Splurge-style "behavioral consumption" is a known modeling pattern (Carroll-Toche, Kaplan-Violante use related ideas). Could be a `HARK.behavioral.SplurgeConsumerMixin`.
- **Proposed PR:** A mixin that:
  - Adds a `Splurge ∈ [0,1]` parameter
  - Overrides `get_controls` and `get_poststates` consistently (both budget AND welfare aggregation use the same `c_actual`)
  - Documents the CDC vs ESC reading explicitly
- **Cost estimate:** 1 week. Most work is documentation + tests + getting the budget identity right (HAFiscal's BUG-031 took weeks to settle).

## Medium-priority improvements

### 5. **Markov state encoding for unemployment-with-duration tracking**
- **What HAFiscal had to build:** the BUG-043 6-state UI encoding (employed / u1Q / u2Q / u3Q / u4Q / noBen) replacing the original 4-state encoding with the "freeze trick."
- **The general pattern:** any policy where eligibility depends on duration in a state needs explicit duration-state encoding.
- **Proposed HARK utility:** `HARK.markov.add_duration_states(MrkvArray, source_state, n_duration)` — automatically expands a single state into `n_duration` consecutive states with appropriate transitions.
- **Cost estimate:** 2–3 days. Small but high-clarity contribution.

### 6. **`HAFISCAL_PLVL_GROWS_DURING_UNEMP`-style flag for shock semantics**
- **What HAFiscal had to build:** Per BUG-040, three modes for how unemployed agents handle PermShk:
  - `'qe'` — frozen pLvl (default; matches HAFiscal-QE published)
  - `'grows'` — uniform G growth, no shock
  - `'shock'` — full shock distribution
- **Why this is HARK-worthy:** The default behavior (frozen pLvl) is a TM-a vs MC inconsistency waiting to bite anyone. Making the choice explicit at the `MarkovConsumerType` level would prevent recurrence.
- **Proposed PR:** Add `unemp_pLvl_mode` parameter to `MarkovConsumerType` with the three modes; default to `'frozen'` for backward compat with HAFiscal-QE.
- **Cost estimate:** 3 days.

### 7. **Welfare-6 framework (Jensen-corrected aggregator)**
- **What HAFiscal had to build:** `welfare6_mc` in `run_welfare6_parallel.py` (BUG-046 fix uses per-duration-then-aggregate to avoid Jensen bias of `u(E[c])`).
- **Why this might be HARK-worthy:** The Lucas-Welfare-equivalent framework is general. Could be in `HARK.welfare`.
- **Caveat:** Probably paper-specific enough that it should live in a HAFiscal companion package rather than HARK proper.

### 8. **Cohort/education-share aggregation** (low priority; very HAFiscal-specific)
- BUG-042 — edu-share weighting under cohort-N override. Highly specific to HAFiscal's 3-ed-type × 7-β-atom structure.
- Probably stays in HAFiscal.

## Lesson learned from JAX MC port — undocumented HARK conventions

A 4+ hour investigation traced a 2.5% systematic JAX-vs-HARK gap to HARK's `T_age=100` forced-death mechanism. The JAX kernel applied `LivPrb=0.99375` for mortality (matching the documented attribute) but missed the SECOND death mechanism: agents whose age reaches `T_age` are forced to die regardless of `LivPrb`.

Combined empirical mortality in HARK: **1.93%/period**, vs **0.625% from LivPrb alone**.

The `T_age` cap interacts non-trivially with `_initialize_ergodic_ages`: initial ages are drawn from a truncated-geometric ergodic, capped at `T_age`. Agents who hit the cap die each period.

**HARK improvement opportunity:** make this dual mechanism explicit in `AgentType` documentation:
- `LivPrb` is the per-period STOCHASTIC survival probability
- `T_age` is the AGE CAP for forced death
- Effective per-period mortality ≈ `(1-LivPrb) + 1/T_age × age_distribution_at_cap`

Without this clarity, any custom or accelerated MC implementation will silently undercount deaths and overstate aggregate income.

## Backward-compat infrastructure (worth documenting, not necessarily upstreaming)

### 9. **HARK 0.14.1 → 0.17.x RNG-sync helpers**
- HAFiscal carries a `rng_sync_with_014` flag and custom `sim_birth` / `reset_rng` overrides to reproduce HARK 0.14.1 numbers.
- **Recommendation:** publish this pattern as a HARK migration guide (not code), so other projects know how to handle the upgrade.

### 10. **The 24 BUG- fixes** (varies)
Of HAFiscal's BUG-001 through BUG-046, most are:
- HAFiscal-specific bugs (BUG-022 income atoms typo, BUG-023 cFunc indexing) — already fixed, not HARK issues
- HARK convention conflicts (BUG-040 pLvl-during-unemp, BUG-041 CFunc cell offset) — should be addressed by improvements #6 above
- HARK upstream gaps (BUG-044 shuffle bias) — already upstreamed
- HAFiscal economic-model bugs (BUG-043 UI under-delivery, BUG-046 Jensen welfare) — economic-model issues, stay in HAFiscal

A systematic "did this need to be a bug?" review would identify a handful more candidates for HARK improvements (#5, #6 above are examples).

## Sequencing recommendation

If we did one HARK PR per quarter:
- **Q1**: JAX-GPU MC (item 1). Highest leverage. Pilot proves it works.
- **Q2**: `AggregateDemandMarket` (item 3). Cleans up `AggregateDemandEconomy`.
- **Q3**: `unemp_pLvl_mode` (item 6) + `add_duration_states` utility (item 5). Small but high-clarity.
- **Q4**: `SplurgeConsumerMixin` (item 4). Tricky but generalizes a useful pattern.

**Alternative:** spin up a `HARK-contrib` repo for items 4–8 (more experimental, less stable API) while items 1–3 go to HARK core. This lets us move faster on the speedup contribution (which benefits everyone) without blocking on the design discussions for the others.

## Costs not counted above

- **Test coverage** for any HARK PR: a HARK contribution requires unit tests covering edge cases. Each PR roughly doubles in size when test coverage is added.
- **Documentation** in the HARK documentation framework (Sphinx + numpydoc).
- **CI/CD review** for each PR. Typical HARK PR cycle is 2-4 weeks.
- **Bilateral discussions** with HARK maintainers about API design. The pure-JAX kernel especially will need careful API discussion (how to expose to users? @jit by default or opt-in?).

## What I haven't included

- Anything that touches HAFiscal-specific paper logic (welfare-6 cells, the specific shock structure, etc.)
- Anything that requires HARK to depend on JAX (JAX should be optional — guarded behind `try: import jax`)
- Speculative items like "rewrite HARK in Rust" — out of scope

## Recommended first conversation with HARK maintainers

Before any PR work, have a 1-hour video call with `@mnwhite` (or whoever is shepherding HARK now) to discuss:

1. **Will HARK accept JAX as an optional dependency?** This is the gating question for items 1, 3, and 4.
2. **Is there appetite for an `AggregateDemandMarket` upstream?** Or should it live in a HARK companion?
3. **Are the BUG-040 / BUG-044 fixes' patterns ready to upstream?** Some are already done; others need API discussions.
4. **What's HARK's release cadence?** If the next major version is 6+ months out, our PRs are likely to languish; better to time the work for the release window.

If the answer to (1) is "yes, with JAX optional," we can ship item 1 as a PR in 2–4 weeks (the pilot is most of the work) and unblock a 100× speedup for the entire HARK user base.

If the answer is "no, HARK stays NumPy-only," then HAFiscal keeps its `jax_mc_*.py` files as a project-local accelerator and the contribution lives in a `HARK-jax` companion package instead.
