# Plan: MC Simulation Speedup Experiments

**Date**: 2026-04-01
**Branch**: `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`
**System**: i9-13900K (16C/32T), 64GB DDR5, RTX 4080 16GB (CUDA 13.0)

---

## Motivation

Current MC runtimes for the full Baseline parametrization (21 agent types,
10,000 total agents, 400-period burn-in, 40-period counterfactual, up to
21 recession durations averaged) take roughly **50-60 minutes per seed**
for a full experiment suite. The TM method is ~7x faster for equivalent
experiments but lacks welfare calculations and has ~1-2% approximation
error. Improving MC speed would allow faster iteration, more seeds for
statistical precision, and remain the gold-standard validation target.

---

## System Resources

| Resource | Specification | Current Usage |
|----------|---------------|---------------|
| CPU | i9-13900K, 16C/32T, 3.0-5.8 GHz | Single-threaded MC |
| RAM | 64GB DDR5-4800 (30GB in WSL2) | ~3GB used |
| GPU | RTX 4080, 9728 CUDA cores, 16GB | **Idle** (CUDA toolkit not installed) |
| Storage | Samsung PM9A1 NVMe Gen4 1TB | Fast |

---

## Approach Summary

Five optimization strategies, ordered by expected impact/effort ratio:

| # | Strategy | Expected Speedup | Effort | Risk |
|---|----------|-----------------|--------|------|
| 1 | **Harmenberg neutral-measure MC** | 5-10x (fewer agents needed) | Medium | Low — HARK has built-in support |
| 2 | **CPU parallelization** (types/seeds) | 4-8x (16 cores) | Low | Low |
| 3 | **Numba JIT** for hot loops | 2-5x for targeted loops | Medium | Medium — interpolator calls |
| 4 | **GPU acceleration** (CuPy/Numba CUDA) | 2-10x for array ops | High | High — requires CUDA install + rewrite |
| 5 | **Combined** (Harmenberg + parallel) | 20-50x | Low once 1+2 done | Low |

---

## Strategy 1: Harmenberg Neutral-Measure MC (PRIMARY)

### Background

Harmenberg (2021) shows that by simulating under a change of measure Q
where probabilities are reweighted by permanent shocks ψ, aggregate
consumption can be computed without tracking permanent income heterogeneity:

    E_P[p · c(m,z)] = E_Q[c(m,z)] · E_P[p]

This dramatically reduces MC variance because the high-variance permanent
income dimension is removed. The practical benefit: **same accuracy with
5-10x fewer agents**, or much better accuracy with the same agent count.

### What Already Exists

1. **HARK built-in**: `IndShockConsumerType` has `neutral_measure=False`
   parameter. When `True`, `IncShkDstn` is constructed with Q-reweighted
   probabilities. `get_shocks()` draws from these automatically.
2. **HAFiscal TM**: `tm_methods._to_neutral_measure()` reweights shock
   distributions for TM; validated in `validate_neutral_measure.py`.
3. **HAFiscal local**: `ConsMarkovModel.harmenberg_income_process()` and
   `compute_steady_state(..., harmenberg=True)`.
4. **Math derivations**: Full treatment in
   `history/20260331-mathematical-derivations-harmenberg.md`.

### Implementation Steps

#### Step 1a: Baseline MC timing benchmark
- Run `AggFiscalMAIN.py` with `sim_method='MC'`, `Reduced_Run` parametrization
- Record: wall time, per-experiment time, agent counts
- Save multiplier tables for comparison baseline

#### Step 1b: Enable `neutral_measure=True` in AggFiscalType
- In `AggFiscalModel.py` or via Parameters, set `neutral_measure=True`
  when constructing income processes for MC simulation
- Key question: Does HARK's Markov income process constructor support
  `neutral_measure`? (Yes — `construct_markov_lognormal_income_process_unemployment`
  accepts it.) But HAFiscal **bypasses** HARK's constructors (`construct=False`)
  and builds `IncShkDstn` manually. So we need to:
  1. After building `IncShkDstn` manually in `Simulate.py`, apply the
     Q-reweighting to the employed state's shock distribution
  2. Leave unemployment states alone (degenerate shocks, ψ=1)
  3. This mirrors what `_to_neutral_measure()` already does in `tm_methods.py`

#### Step 1c: Adjust aggregation for neutral measure
- Under Q, aggregate consumption = E_Q[c_nrm] · E_P[p] · PopCount
- E_P[p] can be computed analytically (geometric series with PermGroFac,
  LivPrb, pLvlInitMean) — already done in `compute_analytical_mean_pLvl()`
- Modify `run_experiment()` aggregation:
  - Old: `AggCons = sum(pLvl * cNrm)` across agents
  - New: `AggCons = sum(cNrm) * analytical_mean_pLvl` (per type)
- Income aggregation similarly adjusted

#### Step 1d: Reduce agent count and validate
- Run with `AgentCountTotal=2000` (5x reduction) under neutral measure
- Compare multipliers against full 10K MC baseline from Step 1a
- Acceptance criterion: multipliers within 1% of non-neutral 10K baseline
- If successful, try `AgentCountTotal=1000` (10x reduction)

#### Step 1e: Full Baseline run with neutral measure
- Run full Baseline parametrization (21 types) with neutral measure
- Compare all multiplier tables against existing MC results
- Document speedup and accuracy trade-off

### Expected Outcome
- 5-10x speedup from agent count reduction alone
- Full Baseline experiment suite in ~5-10 minutes instead of ~50-60

---

## Strategy 2: CPU Parallelization Across Types and Seeds

### Background

The i9-13900K has 16 cores (32 threads). Currently, the MC simulation
runs 21 agent types serially within each `make_history()` period loop.
While within-period parallelism is limited (types interact via aggregate
demand), several levels of parallelism are available:

### Implementation Steps

#### Step 2a: Parallel recession duration averaging
- The 21 recession duration runs in `run_experiments_all_recessions` are
  **independent** (each is a full `run_experiment` with different
  `EconomyMrkv_init`)
- Use `multiprocessing.Pool` or `joblib.Parallel` to run these in parallel
- Expected speedup: min(21, 16) ≈ **16x for recession averaging**
- Each run needs its own deepcopy of the economy (already done)

#### Step 2b: Parallel seed averaging
- Multiple MC seeds can run independently
- Launch N_seeds processes, each running the full experiment suite
- Combine results at the end
- Expected speedup: linear in cores used

#### Step 2c: Parallel type solving
- HARK's `multi_thread_commands` already supports parallel `solve()`
- Enable it for `AggDemandEconomy.solve()`: solve all 21 types in parallel
- The solve step takes ~12 minutes for cold starts (dominant cost in TM-AD)

### Expected Outcome
- Recession averaging: 21 durations × 40 periods in ~1/16 the time
- Seed parallelism: N seeds at near-zero marginal cost
- Combined with Strategy 1: massive compound speedup

---

## Strategy 3: Numba JIT for Hot Loops

### Background

Numba is already in the environment. The MC hot path includes:

1. `get_controls()`: loops over Markov states J and calls `cFunc[j](...)`
2. `hit_with_recession_shock()`: Python loop over agents for check amounts
3. Markov transition updates in `get_shocks()`

### Implementation Steps

#### Step 3a: Profile the MC hot path
- Use `cProfile` on a Reduced_Run MC simulation
- Identify top 5 functions by cumulative time
- Focus on functions where Numba JIT is applicable (pure NumPy operations)

#### Step 3b: JIT-compile inner loops
- Target `hit_with_recession_shock` agent loop (currently pure Python)
- Target Markov boolean mask construction in `get_controls()`
- Note: `cFunc[j]()` calls are HARK interpolator objects — these cannot
  be directly JIT-compiled without rewriting the interpolation

#### Step 3c: Validate numerical equivalence
- Run JIT vs non-JIT on Reduced_Run
- Compare all outputs to machine precision

### Expected Outcome
- Modest (2-3x) speedup for targeted loops
- Limited by interpolator calls which dominate `get_controls()`

---

## Strategy 4: GPU Acceleration

### Prerequisites

CUDA toolkit is NOT yet installed in WSL2. The RTX 4080 is accessible
via `/dev/dxg` (GPU paravirtualization). Installation steps:

```bash
wget https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update
sudo apt install -y cuda-toolkit-12-6
# Then: pip install cupy-cuda12x  (or via uv)
```

### Feasibility Assessment

| Operation | GPU-suitable? | Notes |
|-----------|--------------|-------|
| Shock draws | Yes | CuPy random, large batches |
| Markov transitions | Yes | Matrix-vector on GPU |
| Budget constraint (mNrm = bNrm + TranShk·ADF) | Yes | Element-wise |
| Policy evaluation cFunc[j](mNrm) | **Difficult** | HARK interpolators are CPU objects |
| Aggregation (sum across agents) | Yes | CuPy reduction |

The bottleneck is policy evaluation. Options:
- **Option A**: Precompute cFunc on a fine grid, use GPU texture lookup
- **Option B**: Rewrite linear interpolation as a CUDA kernel
- **Option C**: Keep cFunc on CPU, move everything else to GPU (limited benefit)

### Implementation Steps

#### Step 4a: Install CUDA toolkit and CuPy
#### Step 4b: Benchmark GPU array operations vs NumPy
- Element-wise ops, reductions, random draws on agent-sized arrays
- Determine if array sizes (10K-100K) are large enough for GPU benefit

#### Step 4c: GPU-accelerated shock drawing
- Replace NumPy random draws with CuPy equivalents
- Benchmark improvement

#### Step 4d: GPU policy lookup table (if Steps 4b-c show promise)
- Precompute cFunc values on GPU-resident grid
- Use linear interpolation kernel for policy evaluation
- Validate against CPU interpolator

### Expected Outcome
- Uncertain — array sizes may be too small for GPU overhead
- Best case: 2-5x for shock/transition operations
- Policy evaluation is the hard part

---

## Strategy 5: Combined Approach

### The Sweet Spot: Harmenberg + Parallel Seeds

1. Enable neutral measure (Strategy 1) → reduce agents 5-10x
2. Parallelize recession durations (Strategy 2a) → 16x for that component
3. Parallelize across seeds (Strategy 2b) → N_seeds at ~1x marginal cost

### Expected Total Speedup

| Component | Baseline | Optimized | Speedup |
|-----------|----------|-----------|---------|
| Agent count | 10,000 | 1,000-2,000 | 5-10x |
| Recession averaging | 21 serial | 16 parallel | ~16x |
| Per-seed time | ~50 min | ~0.5-1 min | 50-100x |
| 3-seed total | ~150 min | ~1-2 min | 75-150x |

---

## Execution Order

### Phase 1: Establish MC Baselines (est. 1-2 hours)
- [ ] Run Reduced_Run MC, save timing + results
- [ ] Run full Baseline MC (if not already available), save timing + results
- [ ] Profile hot path with cProfile

### Phase 2: Harmenberg Neutral Measure MC (est. 1 day)
- [ ] Implement Q-reweighting for HAFiscal's manually-built IncShkDstn
- [ ] Implement adjusted aggregation (analytical E_P[p])
- [ ] Validate on Reduced_Run: compare multipliers at full agent count
- [ ] Validate agent-count reduction: 2K, 1K agents vs 10K baseline
- [ ] Run full Baseline with neutral measure, compare tables

### Phase 3: CPU Parallelization (est. 0.5 day)
- [ ] Parallelize recession duration loop
- [ ] Validate numerical equivalence (parallel vs serial)
- [ ] Benchmark speedup

### Phase 4: Combine and Document (est. 0.5 day)
- [ ] Run full suite with Harmenberg + parallel
- [ ] Generate comparison tables vs existing MC results
- [ ] Write summary report

### Phase 5 (Optional): GPU Exploration (est. 1-2 days)
- [ ] Install CUDA toolkit
- [ ] Benchmark CuPy on representative array sizes
- [ ] Prototype GPU shock drawing
- [ ] Assess whether further GPU work is worthwhile

---

## Validation Protocol

At every step, compare against the existing MC baseline:

1. **Multiplier tables**: Check/UI/TaxCut multipliers for noAD/AD/1stAD
2. **NPV values**: Discounted cumulative treatment effects
3. **Per-period paths**: First 25 periods of treatment effect time series
4. **Acceptance criterion**: Within 2% of baseline MC (accounting for MC noise)
5. **Statistical test**: For reduced-agent runs, use 10+ seeds to compute
   confidence intervals and verify baseline falls within them

---

## References

- Harmenberg (2021), "Aggregating heterogeneous-agent models with
  permanent income shocks", *Journal of Economic Dynamics and Control*
- `history/20260331-mathematical-derivations-harmenberg.md` — full math
- `validate_neutral_measure.py` — existing TM neutral-measure validation
- `history/20260401-TM-vs-MC-comparison-summary.md` — current MC benchmarks
