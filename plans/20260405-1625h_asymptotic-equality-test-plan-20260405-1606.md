# Validation plan: TM vs MC method agreement

**Date:** 2026-04-05  
**Reference:** `plans/method-parity-map.md` (which results should agree under which methods)

---

## 1. Method parity classes

Every paper result falls into one of four classes. The validation infrastructure must test only valid comparisons within each class, and the convergence sweep must confirm that agreement improves with N and mCount.

| Class | What agrees (as N→∞, grid→continuous) | Examples |
|-------|--------------------------------------|---------|
| **A** ($p$-linear) | MC-P = MC-Q = TM-P = TM-Q | AggCons, AggIncome, NPV, multipliers, IRFs |
| **B** ($p$-nonlinear, within-measure) | MC-P = TM-P+kernel; MC-Q = TM-Q+kernel (but P ≠ Q) | Welfare $u(c)$, marginal utility $u'(c)$, welfare-per-dollar $\mathcal{G}$ |
| **C** (distributional) | MC-P only | Lorenz curve, wealth shares, MPC by group |
| **D** (check phase-out) | MC-P/Q, TM with $p$-buckets | Stimulus check effects (income-dependent phase-out) |

**Invalid comparisons (scripts must never report these as if they measure agreement):**
- MC-Q vs MC-P for Class B (P and Q give different answers for $k \neq 1$)
- "Average of all four" as reference for Class B
- TM without kernel for Class B (the naive plug-in has ~5% structural bias)

---

## 2. Per-type architecture

- `economy.agents[i]` is a separate economic type (education × $\beta$ bin).
- TM: one transition matrix per type via `build_tm_agg_fiscal(agent_i, ...)`.
- MC: each type simulates its own agents with its own seed.
- Index alignment: `baseline_tm_data[i]` matches `economy.agents[i]` always.
- Aggregation: MC concatenates level histories then sums; TM sums `AgentCount_i * E[p]_i * normalized_aggregate_i`.

---

## 3. Validation ladder

### 3.1 Gatekeeper — single type, baseline

**Runner:** `Code/HA-Models/Gatekeeper_Asymptotic_Equality.ipynb`  
**Code:** `verify_four_methods_agreement.py :: compare_four_methods`

**Current status:** Implemented and passing.

**What exists:**
- `compare_four_methods(periods, agents, t_start, ...)` runs a single education type (highschool) with `DualAggFiscalType`.
- Class A: four-way AggCons per capita comparison with `rtol`.
- Class B: within-measure TM-P kernel vs MC-P, TM-Q kernel vs MC-Q — uses `compute_kernels` with measure-consistent shocks and `E[p^k]` (BUG-020 fix). MC averages use `t_start` to exclude early Q-path transient.
- Init stability: early-period drift diagnostics for mNrm, pLvl, Var(log), employment, MU.
- MC-Q `pLvl_Q` initialized from Q-stationary distribution (not copied from P).
- Burn-in trace plot.

**Parameters:** `periods=300, agents=40000, t_start=100, warmup=24, mCount=100`.

**What does NOT exist yet (changes needed):**
- *None for the Gatekeeper step itself.* It is complete for single-type baseline.

---

### 3.2 Harness — multi-type wiring

**Code:** `test_asymptotic_equality_revised.py --phase harness`

**What exists:**
- `assert_tm_baseline_indexing` verifies `len(baseline_tm_data) == len(economy.agents)`.
- `restore_intended_act_T_after_counterfactual_switch` re-applies `act_T` after `switch_to_counterfactual_mode`.
- Per-cohort init stability via `diagnose_tm_init_stability`.
- `setup_economy` builds multi-type economy from Parameters.

**What does NOT exist yet:**
- **The harness does not test Class B (nonlinear).** `test_asymptotic_equality_revised.py` compares AggCons (Class A) but does not invoke `compute_kernels` for welfare/MU per type. **Change needed:** add a per-type kernel evaluation after the baseline TM build, comparing per-type TM kernel to per-type MC cross-section for E[u'] and E[u]. This requires calling `compute_kernels` with per-type `tm_data[i]` and `agent[i]`.
- **No Q-path `pLvl_Q` initialization for multi-type.** The Q-init fix in `_mc_burnin_tm_init` is in `verify_four_methods_agreement.py` but `test_asymptotic_equality_revised.py :: mc_burnin` has its own init code. **Change needed:** either share `_mc_burnin_tm_init` or port the Q-init logic to `mc_burnin`.

---

### 3.3 Multi-type baseline

**Code:** `test_asymptotic_equality_revised.py --phase baseline`

**What exists:**
- Per-type TM ergodic moments vs MC cross-section (E[mNrm], E[cNrm], employment share).
- Economy-wide AggCons summed across types (Class A).

**What does NOT exist yet:**
- **Per-type Class B comparison.** The phase 1 code computes TM AggCons per type but not TM kernel welfare per type. **Change needed:** for each type, call `compute_kernels(agent_i, tm_data_i, erg_i, [-CRRA, 1-CRRA], CRRA)` and compare to the MC cross-section's per-type mean u' and mean u(c). Report as within-measure (TM-P vs MC-P per type).
- **Per-type `compute_pLvl_distribution` validation.** Verify that the analytical E[p] and Var[log p] per type match the MC cross-section. This catches BUG-019-like issues per education group.

---

### 3.4 No-recession policies (Check, UI, TaxCut)

**Code:** `test_asymptotic_equality_revised.py --phase norec-check`, `--phase norec-ui`, `--phase norec-taxcut`

**What exists:**
- MC runs each policy experiment via `run_mc_norec_experiment`.
- TM runs via `run_experiment_tm_nonbase` for the same shock types.
- Comparison on AggCons and NPV (Class A).

**What does NOT exist yet:**
- **`run_experiment_tm_nonbase` does not support `compute_welfare`.** The `compute_welfare` flag exists only in `run_experiment_tm` (baseline). **Change needed:** add `compute_welfare` support to `run_experiment_tm_nonbase`. This requires evaluating the kernel at each period's time-varying distribution `π_t(m,j)` (not just the ergodic). Cost: one kernel evaluation per period per type — still fast.
- **Class D (check phase-out) welfare.** The consumption multiplier for the check uses `_compute_check_buckets` ($p$-buckets). The welfare impact of the check needs both the kernel AND $p$-buckets. **Change needed:** extend `_compute_check_buckets` to also compute felicity-weighted effects, or compute check welfare from MC-P only and document the limitation.
- **Shock-type switching validation.** After each `switch_to_counterfactual_mode` / `update_mrkv_array`, the test should verify MrkvArray dimensions, IncShkDstn structure (not just act_T). **Change needed:** add assertions on MrkvArray shape and IncShkDstn[j] atom counts after switching.

---

### 3.5 Recession suite

**Code:** `test_asymptotic_equality_revised.py --phase recession-baseline`, `--phase recession-policies`

**What exists:**
- MC recession experiments via `run_mc_recession_experiment` with multiple durations.
- TM recession via `run_experiment_tm_nonbase` with time-varying Markov states.
- Recession-duration averaging with `recession_prob_array`.

**What does NOT exist yet:**
- **Kernel welfare for recession experiments.** Same issue as §3.4: `run_experiment_tm_nonbase` needs `compute_welfare` support for time-varying distributions.
- **Recession-averaging sanity check.** Verify `recession_prob_array` sums to 1. Verify that averaging a constant gives the constant. **Change needed:** add a unit test.
- **Index alignment audit during shock switching.** After `hit_with_recession_shock`, verify `baseline_tm_data[i]` still aligns with the modified `economy.agents[i]`.

---

### 3.6 AD feedback loop

**Code:** `test_asymptotic_equality_revised.py --phase ad-loop`

**What exists:**
- `run_ad_tm` iterates on Cratio to find the GE fixed point (Class A).
- MC-AD via `solve_ad_recession` (iterative solve).

**What does NOT exist yet:**
- **TM-AD is marked BUG-017 (open): produces zero amplification.** The AD loop does not produce meaningful results. **Change needed:** debug BUG-017. Until fixed, AD validation should be skipped or marked as known-failing.
- **Kernel welfare inside AD loop.** Once AD works, welfare at the converged Cratio needs the kernel evaluated at each period's distribution with the converged Cratio path. **Change needed:** pass `compute_welfare=True` through the AD iteration.

---

### 3.7 Convergence sweep

**What exists:**
- The Gatekeeper can be run at different (N, mCount) by changing parameters.

**What does NOT exist yet:**
- **An automated sweep script.** There is no script that runs the Gatekeeper at multiple (N, mCount) pairs and collects the gaps into a table. **Change needed:** write `convergence_sweep.py` that:
  1. Loops over N ∈ {5000, 10000, 20000, 40000} and mCount ∈ {40, 70, 100, 150}.
  2. At each (N, mCount), runs `compare_four_methods` and records:
     - Class A gap: max |method - ref| across all four methods.
     - Class B gap: |TM-P kernel - MC-P| and |TM-Q kernel - MC-Q|.
  3. Produces a table showing gaps decrease monotonically with N and mCount.
  4. Optionally: fit convergence rates (Class A MC noise ∝ 1/√N; TM grid error ∝ 1/mCount² or similar).

---

## 4. Reporting

Each step emits a Markdown report under `history/`:

```
asymptotic-equality-test-plan_<step_name>_<YYYYMMDDTHHMM>.md
```

**Required content:** date, parametrization, pass/fail, key numbers organized by class (A, B, C, D), tolerances, interpretation.

**Reports must separate Class A and Class B results.** A report that mixes cross-measure comparisons for nonlinear objects is invalid.

**Footer:** `## Step timing` with wall-clock start/end and duration.

**Progress tracker:** `history/asymptotic-equality-test-plan_progress.md` — one row per step.

---

## 5. Scale configurations

| Configuration | N (total) | mCount | periods | t_start | Purpose |
|--------------|-----------|--------|---------|---------|---------|
| Smoke_Test | 100 | 35 | 20 | 0 | Crash/wiring only |
| Reduced_Run | 5,000 | 50 | 100 | 0 | Fast iteration |
| Gatekeeper | 40,000 | 100 | 300 | 100 | Method-agreement gates |
| Publication | 40,000+ | 150 | 300 | 100 | Final paper numbers |

`t_start > 0` is needed for Class B (nonlinear) because MC-Q pLvl needs time to reach Q-stationarity even with Q-init. For Class A, `t_start=0` is fine (Harmenberg identity holds period-by-period).

---

## 6. Summary of code changes needed

| Change | Files affected | Blocks on |
|--------|---------------|-----------|
| Add `compute_welfare` to `run_experiment_tm_nonbase` | `tm_methods.py` | Steps 3.4, 3.5 |
| Port Q-path `pLvl_Q` init to `test_asymptotic_equality_revised.py :: mc_burnin` | `test_asymptotic_equality_revised.py` | Step 3.2 |
| Per-type kernel comparison in multi-type harness | `test_asymptotic_equality_revised.py` | Step 3.3 |
| Shock-type switching assertions (MrkvArray, IncShkDstn) | `test_asymptotic_equality_revised.py` | Step 3.4 |
| Recession-prob-array sanity test | New unit test | Step 3.5 |
| Debug BUG-017 (TM-AD zero amplification) | `tm_methods.py :: run_ad_tm` | Step 3.6 |
| Automated convergence sweep script | New: `convergence_sweep.py` | Step 3.7 |
| Check welfare with kernel + p-buckets | `tm_methods.py` | Step 3.4 (Class D) |

---

## 7. Key files

| File | Role |
|------|------|
| `verify_four_methods_agreement.py` | Gatekeeper: `compare_four_methods` with within-measure Class B comparisons |
| `tm_methods.py :: compute_kernels` | Covariance kernel for Class B TM evaluation |
| `tm_methods.py :: compute_pLvl_distribution_Q` | Q-measure E[p^k] for TM-Q kernel |
| `tm_methods.py :: run_experiment_tm` | Baseline TM with optional `compute_welfare` |
| `tm_methods.py :: run_experiment_tm_nonbase` | Non-baseline TM (**needs `compute_welfare`**) |
| `tm_methods.py :: run_ad_tm` | AD iteration (**BUG-017 open**) |
| `Gatekeeper_Asymptotic_Equality.ipynb` | Gatekeeper notebook runner |
| `test_asymptotic_equality_revised.py` | Multi-type harness (named phases; legacy `0`–`7`) |
| `plans/method-parity-map.md` | Which methods agree on which results |
| `plans/kernel-integration-spec.md` | Kernel integration architecture |
