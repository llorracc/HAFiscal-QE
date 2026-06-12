---
date: 2026-05-03
status: design-questions-resolved-2026-05-03; implementation-in-progress
keywords: [MC, TM-a, drift, ergodic-init, warm-start, companion-runs, registry]
related_bugs: []
related_plans: [20260503-1030h_results-registry-and-impc-gof.md]
---

> **User answers to design questions (2026-05-03):**
> 1. Drift threshold: **0.03**. Interpretation: **absolute log-diff for mean log(a)** (~3% multiplicative); **relative for variances** (`|Δvar|/var_TMa < 0.03`). Asymmetric because mean is level, variance is scale. (Awaiting confirmation; proceeding with this interpretation.)
> 2. HARD-FAIL by default. Make provision to switch to WARN later via env var `HAFISCAL_DRIFT_HARD_FAIL=0`.
> 3. **Both** per-cohort AND population-aggregate drift.
> 4. Drift companion applies to **Step 2 also** (not just Step 5). For Step 2, "drift" is between the TM-a-initialized MC and TM-a's analytical ergodic at the SAME (β, ∇).
> 5. **Backfill** existing CDC artifacts with TM-a companions (Phase 5).

# MC ⇄ TM-a companion runs + drift measurement + TM-a warm-start

## Goal

Implement the user's standing rule (memory `feedback_mc_requires_tma_companion.md`):

> "Whenever we do MC, we should always do the corresponding TM-a and test whether
> it looks like the MC (which should have been initialized with what TM-a says is
> the ergodic distribution) is drifting, either in the mean or in the variance of
> the log of a or variance in the log of p."

Three deliverables:

1. **MC initialization from TM-a ergodic** — replace HARK's default random init with sampling from TM-a's analytical ergodic distribution.
2. **Drift measurement** — at end of MC simulation, compare mean log(a), var log(a), var log(p) against TM-a's analytical baseline. Record in registry.
3. **TM-a warm-start (caching)** — when an identical-config TM-a build was done before, cache and reuse the agent solution + transition matrix instead of re-solving.

## What does TM-a "ergodic" mean for MC initialization?

The model has heterogeneity along multiple axes:
- Education group (D, HS, C) — fixed at agent creation
- Discount factor β atom (7 atoms per Ed group from the discrete approximation)
- Markov state (employment status: e_1, e_2, u_1, u_2)
- Asset holding `aNrm` (normalized to permanent income)
- Permanent income `pLvl` (level)

For each (education group, β atom), TM-a computes:
- An ergodic distribution over (Markov state, aNrm) — joint
- A separate ergodic for pLvl conditional on age (since pLvl is a martingale with permanent shocks; only quasi-ergodic via T_age=200 cutoff + replacement)

To initialize MC at TM-a's ergodic:
- For each (Ed, β-atom) sub-population:
  - Sample `AgentCount` agents
  - Each agent's (Markov state, aNrm) drawn from TM-a's joint ergodic
  - Each agent's pLvl drawn from TM-a's pLvl ergodic (or from age-conditional ergodic if T_age replacement is active)
- The aNrm and pLvl are then composed into aLvl = aNrm × pLvl

## Drift metrics

For each of the 3 quantities, compute at simulation end:

| Quantity | TM-a benchmark | MC empirical | Drift = MC − TM-a |
|---|---|---|---|
| mean log(a) | `E[log(a)]` from TM-a ergodic over (j, a) | `mean(log(state_now['aLvl']))` | scalar |
| var log(a) | `Var[log(a)]` from TM-a ergodic | `var(log(state_now['aLvl']))` | scalar |
| var log(p) | `Var[log(p)]` from TM-a pLvl ergodic | `var(log(state_now['pLvl']))` | scalar |

(Mean log(p) is also worth recording — but for a martingale-with-permanent-shocks process under death-replacement, the mean drifts naturally; what matters is the variance.)

Drift threshold for flagging:
- Each: |drift| < 0.05 (absolute, on log scale) — passes
- Else: warning logged + registry metric `drift_flag = 1`

The user can tighten/loosen via env var `HAFISCAL_DRIFT_THRESHOLD`.

## TM-a "warm-start" — what it can and cannot save

Within an estimator's NM optimization loop:
- Each NM eval changes β (and possibly ∇), which changes the agent's solution → changes CFunc → changes transition matrix
- → No caching benefit within NM convergence

Across runs of the SAME converged cal:
- Same (β, ∇, CRRA, R, IncShkDstn, MrkvArray, T_age, LivPrb, PermGroFac) ⇒ same CFunc ⇒ same TM matrix ⇒ same ergodic
- Reusing the cached TM matrix saves the dominant cost (CFunc construction via `agent.solve()` + matrix building)
- → Major caching benefit for: calcAllResults pass, multiplier pass, downstream re-runs

**Caching key:** SHA-256 hash of canonical (β, ∇, CRRA, R, IncUnemp, ..., MrkvArray-shape, IncShkDstn-hash, T_age, LivPrb, PermGroFac, aMin, aMax, aCount).

**Cache invalidation:** when HARK version changes; when any code path inside `build_tm_agg_fiscal_a` changes (track via commit SHA). Keep the cache scoped to a (HARK_version, code_commit) tuple.

**Cache location:** `Code/HA-Models/Results/registry/tm_a_cache/<cache_key>.pkl` — alongside the registry, gitignored.

## Implementation phases

### Phase 1: TM-a ergodic init for MC (~3-4 hr)

**New module** `Code/HA-Models/_tm_a_init.py`:
- `compute_tma_ergodic(agent)` → returns dict with `ergodic_aNrm_by_jstate` (J × A array) and `ergodic_pLvl` (1D array).
- `initialize_agent_from_ergodic(agent, ergodic, AgentCount, seed=None)` → sets `agent.state_now` to a sample from the ergodic. Returns the modified agent.

**Hook in `AggFiscalModel.py` (or wherever `initialize_sim` is called)**:
- New env var `HAFISCAL_INIT_FROM_TMA=1` to enable the TM-a init.
- When enabled: after `agent.initialize_sim()` (which sets state to NaN), follow with `_tm_a_init.initialize_agent_from_ergodic(agent, ...)`.

**Validation:**
- Bit-identical CDC behavior when env var is unset (preserves all existing test outputs).
- New test `test_tma_init_matches_ergodic.py`: build TM-a ergodic; init MC at it; verify MC's empirical (mean log(a), var log(a)) matches TM-a's analytical within 1%.

### Phase 2: Drift measurement (~2 hr)

**New module** `Code/HA-Models/_tm_a_drift.py`:
- `compute_drift(agent, tma_ergodic)` → returns dict `{'mean_log_a': scalar, 'var_log_a': scalar, 'var_log_p': scalar}`.
- `assess_drift(drift_dict, threshold=0.05)` → returns dict with per-metric pass/fail booleans.

**Hook in `AggFiscalMAIN_reduced.py`** at end of script (after `Output_Results`):
- If `HAFISCAL_INIT_FROM_TMA=1` was set:
  - Re-build TM-a ergodic for the current cal
  - Compute drift for each agent group
  - Record metrics: `drift_mean_log_a_d`, `drift_var_log_a_d`, etc. (per-cohort)
  - Print drift summary in console
  - Write drift block to AllResults file (or a separate `drift.txt`)

Same hook in `EstimAggFiscalMAIN.py` after the calcAllResults block.

**Registry integration:** record all drift metrics in `metrics` table per the existing pattern.

### Phase 3: TM-a warm-start (caching) (~2 hr)

**New module** `Code/HA-Models/_tm_a_cache.py`:
- `cache_key(agent)` → SHA-256 of canonical config.
- `get_cached_tm(cache_key)` → returns `(tm_matrix, ergodic, dist_aGrid)` or None.
- `save_cached_tm(cache_key, tm_matrix, ergodic, dist_aGrid)` → atomic write to disk.
- `invalidate_cache_on_version_change()` → clears cache when HARK version changes.

**Hook in `tm_methods.py` `build_tm_agg_fiscal_a`**:
- At top: check cache. If hit: return cached. Else: build + save + return.

**Validation:**
- Bit-identical TM matrix vs no-cache run (cache hit must give same answer as cold build).
- Cache miss properly populates cache.
- HARK version change properly invalidates cache.

### Phase 4: Companion-run rule enforcement (~1-2 hr)

**Wrapper script** `Code/HA-Models/scripts/run_with_tma_companion.py`:
- Takes the same CLI as `AggFiscalMAIN_reduced.py` or `EstimAggFiscalMAIN.py`
- Detects whether the underlying script is configured for MC (`sim_method='MC'` or `HAFISCAL_STEP2_METHOD=mc`)
- If yes: also runs the TM-a companion automatically (in parallel where possible)
- Aggregates drift metrics into the registry

**Memory + plan reference**: this rule formalized in `feedback_mc_requires_tma_companion.md`.

## Validation plan (incremental)

Each phase includes a small standalone validation:

| Phase | Validation | How long |
|---|---|---|
| 1 | TM-a init produces empirical moments matching analytical ergodic within 1% | ~1 hr (smoke + 1-cohort full) |
| 2 | Drift measurement: a known-stationary process should report drift ≈ 0 | ~30 min |
| 3 | Cache hit produces bit-identical TM matrix vs cold build | ~30 min |
| 4 | End-to-end: companion run reports both MC + TM-a results, drift is recorded | ~1 hr |

If any validation fails: HALT and diagnose before proceeding. Per `feedback_cascade_gating.md`.

## Estimated total effort

~8-10 hr focused work + iterative debug. Phases 1+2 (init + drift) deliver ~80% of the value; Phase 3 (cache) is the biggest performance win for repeated runs; Phase 4 (rule enforcement) is the formalization layer.

## Open design questions for user

1. **Drift threshold default:** 0.05 (5% on log scale) reasonable? Tighter (0.01)? Looser (0.1)?
2. **Should the rule HARD-FAIL or just WARN?** I.e., if drift exceeds threshold, should the run abort (block downstream) or proceed with a flagged warning? My recommendation: WARN by default, HARD-FAIL behind an opt-in env var (`HAFISCAL_DRIFT_HARD_FAIL=1`).
3. **Per-cohort or population-aggregate drift?** I.e., do we measure drift separately for D / HS / C, or just at the population level? My recommendation: per-cohort + population (5 metrics × 2 levels = 10).
4. **What about Step 5 multipliers?** The drift test makes sense for Step 5 (which simulates over many quarters). But Step 2 (which is steady-state estimation, no extended simulation) doesn't have the same notion. The companion-rule can still apply: run TM-a Step 2 alongside MC Step 2 and compare converged cal values + medianLWPI fit. Drift metrics are Step-5-only.
5. **Existing CDC saved cal:** should we backfill TM-a companions for the existing CDC saved cal artifacts? My recommendation: no, that's history; apply the rule going forward.

## What this plan does NOT do

- Does not modify any current artifacts; this is purely additive infrastructure.
- Does not change how MC produces multipliers (Step 5 logic unchanged).
- Does not implement anything; this is a design document. Implementation pending user approval.
