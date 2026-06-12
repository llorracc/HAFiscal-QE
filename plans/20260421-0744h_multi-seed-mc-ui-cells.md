# Plan: Multi-seed MC for welfare6 UI cells (variance reduction)

**Date:** 2026-04-20
**Status:** Infrastructure ready, execution pending
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_matsya_explore-further-speedups`
**Related plans:** `plans/20260419-1857h_welfare6-control-variate-implementation.md`
**Related history:** `history/20260419-welfare6-TM-within-state-cross-scenario-bias.md`

---

## 1. Context

The control-variate (CV) estimator implemented per `plans/20260419-1857h_welfare6-control-variate-implementation.md` works as designed — but only on **TaxCut and Check** cells. On the recession-UI cells (UI Rec=1 and UI Rec=1 AD=1), the CV is structurally limited (ρ ≈ 0.3, ~10% variance reduction) because the L2/L3-in-MC factorisations don't track the rare-event sub-population that drives W_MC variance. This matches companion-doc §6 prediction.

Final CV results (n_boot=500, j_pol bucketing, L2):

| Cell | rel SE (MC) | rel SE (CV) | ρ | Verdict |
|---|---:|---:|---:|---|
| Check Rec=0 | 0.61% | 0.61% | −0.12 | Already <1%; CV vacuous |
| UI Rec=0 | 12.80% | 8.74% | 0.73 | Partial; **>1% target** |
| TaxCut Rec=0 | 1.89% | **0.54%** | 0.96 | CV wins |
| Check Rec=1 | 0.72% | 0.72% | −0.02 | Already <1%; CV vacuous |
| **UI Rec=1** | 7.58% | 7.27% | 0.28 | CV ineffective; **>1% target** |
| TaxCut Rec=1 | 1.96% | **0.53%** | 0.96 | CV wins |
| Check Rec=1 AD=1 | 0.62% | 0.46% | 0.67 | Already <1% |
| **UI Rec=1 AD=1** | 6.45% | 6.01% | 0.36 | CV ineffective; **>1% target** |
| TaxCut Rec=1 AD=1 | 1.96% | **0.52%** | 0.96 | CV wins |

**The remaining problem**: three UI cells need the SE pushed below 1% (ideally) by means other than CV.

## 2. Goal

Reduce welfare6 utility-part SE on the three UI cells (Rec=0, Rec=1, Rec=1 AD=1) by **multi-seed MC** — the simplest, lowest-risk, predictable-cost path. SE scales as 1/√S where S is the number of independent seed-batches combined.

### Why multi-seed (vs. importance sampling, vs. TM L3)

Per session-end discussion (2026-04-20 status check):

| Approach | Effort | Risk | Expected UI Rec=1 SE |
|---|---:|---|---:|
| **Multi-seed MC** | **~1 day setup + N×1h CPU** | **None** | **~1% at S=58** |
| Importance sampling | 3–5 days | High (modifies HARK Markov draw) | ~1.5% (20× ESS, partly offset by weight variance) |
| Full TM L3 | 1–2 weeks | High (new TM code) | <1% (N-independent) |

Multi-seed is strictly dominant on cost-vs-risk for the UI-cell precision problem.

## 3. Infrastructure (already built — 2026-04-20)

Code changes already committed to the working tree:

### `Code/HA-Models/FromPandemicCode/welfare6_scenario.py`

- New `--seed-offset INT` CLI arg (default 0). Plumbed through `_MY_FLAGS_WITH_VALUE` so `EstimParameters.py`'s positional-argv reading isn't disturbed.
- `build_and_solve(parametrization, agent_count_total=None, seed_offset=0)` signature update.
- Per-agent-type seed shifted by `seed_offset * 10000` (line ~225).
- `IncShkDstn[0].seed` shifted by `seed_offset * 1` (line ~240).
- Stride of 10000 for the per-agent-type seed avoids collisions with the native `e * DiscFacCount + d` indexing (which never exceeds 3 × 7 = 21 in Baseline).

### `Code/HA-Models/FromPandemicCode/run_welfare6_parallel.py`

- New `--seed-offset INT` CLI arg, forwarded to each scenario subprocess.
- `launch_scenarios(..., seed_offset=0)` signature update.

### `Code/HA-Models/FromPandemicCode/combine_seed_pickles.py` (new)

- Reads multiple per-seed pickle dirs.
- Per scenario: concatenates per-agent panels (`cLvl_all_splurge`, `cLvl_all_splurge_bs`, `pLvl_all_bs`, `Mrkv_hist_bs`) along the agent axis; sums aggregates (`AggCons`, `AggIncome`); preserves scalars (`act_T`, `Rfree`, `CRRA`, `parametrization`); records `n_seeds_combined` and total `runtime_s`.
- Output dir is plug-compatible with all existing post-processing (`diag_welfare6_se.py`, `compute_welfare6_mc_l2.py`, `compute_welfare6_control_variate.py`) — they just see a bigger N.

### Symlink

- `welfare6_scenario_results_Baseline_seed0` → `welfare6_scenario_results_Baseline` (the existing seed_offset=0 batch).

### Smoke-tested

- Base scenario with `--seed-offset 1` produces different `cLvl_all_splurge` and `pLvl_all_bs` mean values from `--seed-offset 0` (28.5 vs 33.1; 27.9 vs 33.1).
- `combine_seed_pickles.py` on a single-seed input produces a valid combined dir.

## 4. Tiered execution plan

Rationale: there's diminishing return per extra seed (1/√S). Start with a small batch, measure, decide whether to escalate.

### Tier A — quick check (3 additional seeds → S=4 total)

**Wall-clock:** ~3 h sequential (each seed ~1 h, same as original regen).
**Expected UI SEs:** Rec=0: 6.4%, Rec=1: 3.8%, Rec=1 AD=1: 3.2%.
**Decision after:** if SE-scaling matches √S prediction, proceed to Tier B. If it doesn't (e.g., per-seed SE highly variable), debug before continuing.

### Tier B — overnight (4 more seeds → S=8 total)

**Wall-clock:** ~4 h sequential (after Tier A complete).
**Expected UI SEs:** Rec=0: 4.5%, Rec=1: 2.7%, Rec=1 AD=1: 2.3%.
**Decision after:** if any UI cell is ≤ 1.5%, accept and ship. Otherwise consider Tier C.

### Tier C — full target (8 more seeds → S=16 total)

**Wall-clock:** ~8 h sequential (after Tier B).
**Expected UI SEs:** Rec=0: 3.2%, Rec=1: 1.9%, Rec=1 AD=1: 1.6%.
**Decision after:** at S=16, all UI cells should be ≤ ~3%. If <1% target is desired, escalate to Tier D.

### Tier D — push to <1% (escalate further)

To reach 1% on UI Rec=0 (the worst-affected cell, ~12.8% rel SE at S=1) requires S ≈ 165. That's ~165 hours sequential (~7 days) or ~3 days if running 2 seeds in parallel with `--duration-workers 2` to fit cores. **Probably not worth it** — better to ship at S=16 with 2–3% UI SE and accept that as the empirical limit, OR escalate to TM L3 / importance sampling.

### Sequential vs. parallel seeds

Single-seed runs already use ~36 process-equivalents (12 scenarios × ~3 average duration_workers active) on 32 cores — slight oversubscription. Running 2 seeds in parallel (72 process-equivalents) is heavily oversubscribed and likely to thrash. **Default to sequential**. If wall-clock pressure justifies, run 2 in parallel with `--duration-workers 2` per seed (24 process-equivalents per seed, 48 total — still over but tolerable on 32 cores).

## 5. Execution recipe

Per seed-offset N (where N = 1, 2, 3, …):

```bash
cd Code/HA-Models/FromPandemicCode

# Run the 12-scenario pipeline for this seed
python run_welfare6_parallel.py --baseline \
    --seed-offset N \
    --max-parallel 12 \
    --duration-workers 4 \
    --out-dir welfare6_scenario_results_Baseline_seed${N}
```

Per-seed pickles land in their own `_seed${N}` directory.

After all desired seeds finish, combine and analyse:

```bash
# Combine S seeds (replace 0..3 with the actual range)
python combine_seed_pickles.py \
    --input welfare6_scenario_results_Baseline_seed0 \
            welfare6_scenario_results_Baseline_seed1 \
            welfare6_scenario_results_Baseline_seed2 \
            welfare6_scenario_results_Baseline_seed3 \
    --output welfare6_scenario_results_Baseline_combined_S4

# Run analysis on the combined dir.  diag_welfare6_se.py & control-variate
# scripts read from welfare6_scenario_results_Baseline/ by default; either
# symlink the combined dir over (preserving original) or override DIR
# variable in the scripts.

# Easiest: symlink the combined dir over the canonical name temporarily.
mv welfare6_scenario_results_Baseline welfare6_scenario_results_Baseline_BAK_$(date +%s)
ln -sfn welfare6_scenario_results_Baseline_combined_S4 \
        welfare6_scenario_results_Baseline

python diag_welfare6_se.py
python compute_welfare6_control_variate.py --n-boot 500
```

## 6. Stopping criteria

After each tier, evaluate against:

1. **Per-cell SE target.** Default goal: <1% rel SE on all 9 cells. Acceptable fallback: <2% on UI cells (the structurally-hard ones) with <1% on the other 6.
2. **Diminishing returns.** If going from S → 2S drops UI Rec=1 SE by less than the expected √2 ≈ 1.41× factor, something's wrong — investigate before adding more seeds.
3. **Time budget.** Seed-batch wall-clock is ~1 h each. Stop when the marginal hour stops paying off in measurable precision improvement on cells that matter.

## 7. Deliverables

- [ ] Tier A: 3 additional pickle dirs (`_seed1`, `_seed2`, `_seed3`); combined `_combined_S4`; updated SE table.
- [ ] Tier B (optional): `_seed4..7`; `_combined_S8`; updated SE table.
- [ ] Tier C (optional): `_seed8..15`; `_combined_S16`; updated SE table.
- [ ] Final report: side-by-side comparison of S=1, S=4, S=8 (or whatever final S), confirming √S scaling and reporting final per-cell SEs.

## 8. Risks and gotchas

- **CRN within-seed preserved by construction.** All 12 scenarios in a single seed-offset subprocess share the same `_MY_FLAGS_WITH_VALUE`-derived RNG state, so per-agent PermShk/TranShk/UnempDraw arrays match across pol/none/base. Don't break this when modifying the pipeline.
- **Across-seed independence.** Stride 10000 for `t.seed` and stride 1 for `IncShkDstn[0].seed` is ample to ensure no overlap in the pseudo-random streams. `np.random` uses Mersenne Twister with very long period; collision risk is negligible.
- **Disk usage.** Each seed dir is ~120 MB (12 pickles × ~10 MB). S=16 → ~2 GB. Cleanup old `.prev` and intermediate combined dirs once verified.
- **The j^pol vs j^base CV bootstrap step is slow on large combined N.** At N=10K bootstrap took ~55 s for n_boot=500. At N=160K (S=16), expect ~15 min. Manageable but worth knowing.
- **The plug-in TM-L2 ≈ MC-L2 design** doesn't change with combined N. CV still doesn't help UI-Rec cells; only the underlying MC SE drops. Don't expect ρ to magically improve at higher S — it's structurally low.
- **Baseline parametrization only.** All multi-seed runs use Baseline. Sensitivity parametrizations (CRRA1, CRRA3, ADElas, etc.) would need separate multi-seed campaigns.

## 9. After multi-seed: path forward for UI cells

If S=16 leaves UI Rec=0 above 2% rel SE, the remaining options (in cost order, cheapest first):

1. **Run more seeds** (linear cost: 1h per seed, √S precision). At some point the marginal hour isn't worth it.
2. **Importance sampling** (3–5 d effort, modifies HARK Markov machinery, ~20× ESS gain on UI). See companion doc §12.2 Approach 3.
3. **TM L3** (1–2 weeks, foundational improvement, N-independent precision). See companion doc §12.3.

These are deferred decisions to be revisited once Tier A/B/C results are in.
