# HAFiscal full-pipeline component map

**Purpose:** Reference document tracing every subcomponent of the reproduction pipeline (`do_all.py` → `AggFiscalMAIN.py` → `Simulate.py` → `Output_Results.py` → `Welfare.py`) that could be tested in isolation. Used to assess coverage of `asymptotic-equality-test-plan_revised.md`.

**Date:** April 5, 2026

---

## Execution flow

```
do_all.py
│
├── Step 1: Splurge estimation
│   └── Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py
│
├── Step 2: Discount factor estimation (~48h)
│   └── EstimAggFiscalMAIN.py
│       ├── return_parameters(Parametrization, OutputFor='_Estim.py')
│       ├── Create 3 education types × DiscFacCount agents
│       ├── For each type: solve → simulate → calc targets
│       ├── Nelder-Mead on (beta, nabla) per education group
│       └── Output: DiscFacDstns → Results/*.txt
│
├── Step 3: Robustness (Splurge=0), same as Step 2
│
├── Step 4: HANK/SAM Jacobians
│   └── HA-Fiscal-HANK-SAM.py → HA-Fiscal-HANK-SAM-to-python.py
│
└── Step 5: Policy simulation
    └── AggFiscalMAIN.py
        ├── return_parameters(Parametrization, OutputFor='_Main.py')
        ├── Simulate(Run_Dict, figs_dir, Parametrization)
        ├── Output_Results(...)
        └── Welfare_Results(...)
```

---

## Testable components (numbered for cross-reference)

### A. Parameter and data loading

| # | Component | File | What to test |
|---|-----------|------|-------------|
| A1 | `return_parameters()` | Parameters.py | Returns correct structure for each Parametrization (Baseline, Reduced_Run, Smoke_Test, CRRA variants, etc.) |
| A2 | Discount factor loading | Parameters.py | DiscFacDstns loaded from Results/*.txt match Step 2 output |
| A3 | Income shock construction | AggFiscalModel.py | `IncShkDstn` built correctly with `construct=False` for each micro state; employed vs unemployed distributions differ as intended |
| A4 | SST income process | income_process_sst.py | `build_PermGroFac_micro`, `effective_pLvl_growth`, `build_unemployed_inc_shk_dstn` produce correct per-state parameters |
| A5 | Splurge file loading | Parameters.py | `Splurge_estimate.txt` loaded correctly from the right path |

### B. Agent construction and solving

| # | Component | File | What to test |
|---|-----------|------|-------------|
| B1 | `AggFiscalType` construction | AggFiscalModel.py | Agent created with correct parameters per education type; `construct=False` doesn't break IncShkDstn |
| B2 | Solver (`solveAggConsMarkovALT`) | AggFiscalModel.py | Consumption function is concave, satisfies Euler equation, BoroCnstNat computed correctly (BUG-001 fix intact) |
| B3 | `DualAggFiscalType` | AggFiscalModel.py | Dual-measure plumbing: Q-states tracked correctly, `cLvl_splurge_Q` consistent with P-states |
| B4 | `AggregateDemandEconomy` construction | AggFiscalModel.py | Economy links agents, `get_economy_data` distributes parameters, market-level variables initialized |

### C. TM infrastructure

| # | Component | File | What to test |
|---|-----------|------|-------------|
| C1 | `build_tm_agg_fiscal` | tm_methods.py | Grid construction, transition matrix column-stochastic, handles all J micro states |
| C2 | `_build_period_tm` | tm_methods.py | Death/rebirth via `(1-LivPrb) * NewBornDist`; survival transitions; neutral-measure reweighting |
| C3 | `find_ergodic_distribution` | tm_methods.py | Ergodic sums to 1, is a fixed point of T |
| C4 | `compute_baseline_tm_data` | tm_methods.py | Per-type: ergodic, dist_mGrid, E_pLvl, u_ergodic all consistent |
| C5 | `compute_pLvl_distribution` | tm_methods.py | Correct variance: `(1-u)*k*sigma_psi_sq` (BUG-019 fix); matches MC cross-section |
| C6 | `compute_analytical_mean_pLvl` | tm_methods.py | Matches `compute_pLvl_distribution` first moment and MC E[pLvl] |
| C7 | `run_experiment_tm` (baseline) | tm_methods.py | AggCons matches MC within tolerance at sufficient mCount |
| C8 | `run_experiment_tm_nonbase` | tm_methods.py | Handles recession/policy Markov transitions; time-varying distributions propagated correctly |
| C9 | `run_ad_tm` | tm_methods.py | AD iteration converges; Cratio path reasonable; result matches MC-AD (BUG-017 open) |
| C10 | `mean_marginal_utility_tm_kernel` | verify_four_methods_agreement.py | Kernel achieves ~0.2% error vs MC for E[u'(c_splurge)] |
| C11 | `mean_marginal_utility_tm_independent_p` | verify_four_methods_agreement.py | Product-measure estimate; known ~5% bias (used as baseline comparison) |

### D. MC simulation

| # | Component | File | What to test |
|---|-----------|------|-------------|
| D1 | `initialize_sim` / TM-init | AggFiscalModel.py + Simulate.py | Agents drawn from TM ergodic; pLvl from corrected distribution; warmup convergence |
| D2 | `run_experiment` (MC) | AggFiscalModel.py | Returns correct keys (AggCons, AggIncome, cLvl_all_splurge, etc.); Full_Output modes work |
| D3 | Shock type switching | AggFiscalModel.py | `switch_to_counterfactual_mode`, `update_mrkv_array` produce correct MrkvArray for each shock; act_T restored |
| D4 | Recession shock application | AggFiscalModel.py | `hit_with_recession_shock` / fixed shock histories consistent with TM recession Markov states |
| D5 | Dual-MC P-Q consistency | AggFiscalModel.py | `AggCons_Q` from Q-weights matches P-measure AggCons for p-linear aggregates |

### E. Experiment orchestration

| # | Component | File | What to test |
|---|-----------|------|-------------|
| E1 | Baseline run (MC and TM) | Simulate.py | Both methods produce AggCons; NPV computed correctly |
| E2 | Non-recession policies | Simulate.py | Check/UI/TaxCut: income shocks changed correctly; IncShkDstn modified per policy |
| E3 | Recession experiments | Simulate.py | Multiple recession durations run; averaged with recession_prob_array weights |
| E4 | AD iteration (MC) | AggFiscalModel.py | `solve_ad_recession` converges; economy re-solved at each iteration |
| E5 | Per-type loop alignment | Simulate.py | `baseline_tm_data[i]` ↔ `economy.agents[i]` for all i |

### F. Post-processing

| # | Component | File | What to test |
|---|-----------|------|-------------|
| F1 | NPV calculation | tm_methods.py | `calculate_NPV` correct for known series |
| F2 | Multiplier computation | Output_Results.py | `get_npv_multiplier` = NPV(ΔCons) / NPV(ΔIncome); reasonable range (0–2) |
| F3 | IRF computation | Output_Results.py | `get_simulation_percent_diff` produces correct percentage differences |
| F4 | Welfare (CRRA felicity) | Welfare.py | `felicity(c)` correct for CRRA≠1 and CRRA=1; per-agent welfare aggregated correctly |
| F5 | Welfare by policy | Welfare.py | Welfare impact: Check > TaxCut (standard ordering); recession averaging weighted correctly |
| F6 | Figure generation | Output_Results.py | All figures generate without error; reasonable axis ranges |

### G. Estimation (Step 2)

| # | Component | File | What to test |
|---|-----------|------|-------------|
| G1 | Target computation | EstimAggFiscalModel.py | Lorenz points, LW/PI, MPC by education match data targets structure |
| G2 | GIC check | EstimAggFiscalModel.py | `check_disc_fac_distribution` validates that discount factors satisfy growth-impatience condition |
| G3 | Optimization convergence | EstimAggFiscalMAIN.py | Nelder-Mead converges for each education type |

---

## Coverage assessment: revised test plan vs component map

### Well covered

| Plan step | Components covered |
|-----------|-------------------|
| **Gatekeeper** | C1, C2, C3, C5, C6, C7, C10, C11, D1, D2, D5 |
| **Harness** | D3 (act_T), E5 (index alignment) |
| **Multi-type baseline** | C4, E1, E5 |
| **No-recession policies** | E2 |
| **Recession suite** | C8, E3 |
| **AD feedback loop** | C9, E4 (both marked as stubs/open) |
| **Convergence sweep** | Grid/N scaling of C1, C7 |

### Gaps

| # | Gap | Severity | Notes |
|---|-----|----------|-------|
| **G1** | **Estimation pipeline (Steps 1–3) not tested** | High | The calibrated parameters are the foundation. If the estimation is wrong, correct simulation code produces wrong paper results. The test plan assumes Step 2 output is correct. |
| **G2** | **Income shock construction (A3) not tested** | High | `IncShkDstn` is built manually (`construct=False`) with per-state unemployed distributions from SST. A wrong distribution propagates to both TM and MC. The Gatekeeper compares methods but won't catch a bug that affects both identically. |
| **G3** | **Welfare.py (F4, F5) not tested** | High | The paper's welfare results are a primary output. Welfare uses `cLvl_all_splurge` (agent-level), not AggCons. The test plan mentions "level distribution & welfare" as a Gatekeeper extension but it's unimplemented and the description focuses on marginal utility agreement, not the actual Welfare.py calculations. |
| **G4** | **Output_Results.py (F2, F3, F6) not tested** | Medium | Multiplier and IRF computations are untested. These are simple arithmetic but depend on the pickle structure. |
| **G5** | **Recession duration averaging (E3 detail)** | Medium | `recession_prob_array` weighting is a critical aggregation step that the plan's "Recession suite" doesn't specifically verify. |
| **G6** | **Shock type switching correctness (D3 detail)** | Medium | The plan tests that act_T is restored but not that MrkvArray, IncShkDstn, and shock histories are correctly transformed per shock type. Each shock type (UI, TaxCut, Check) modifies different parameters. |
| **G7** | **Parameter consistency across parametrizations (A1)** | Medium | The plan uses Reduced_Run and Smoke_Test but doesn't verify these produce the same qualitative structure as Baseline. |
| **G8** | **Solver correctness (B2)** | Low | Implicitly tested by method agreement, but a solver bug that affects both MC and TM identically wouldn't be caught. |
| **G9** | **HANK/SAM comparison (Step 4)** | Low | Outside scope of TM-vs-MC validation; tested separately. |
| **G10** | **Covariance kernel in welfare context (C10 + F4)** | Medium | The kernel is tested for mean u' but not integrated into Welfare.py's actual calculations. If welfare computations use the naive TM for u', they inherit the ~5% bias. |

### Recommended additions to the test plan

**Priority 1 (add before scaling up):**

1. **Income shock distribution sanity check** — For each education type and shock type, verify: E[PermShk]=1 (employed), E[TranShk] matches calibration, unemployed distributions match SST flags. This is a unit test, not a multi-step integration test.

2. **Welfare.py integration test** — Run a minimal Simulate + Welfare pipeline (Reduced_Run, baseline + one policy) and verify: welfare is finite, welfare impact has correct sign, felicity function matches CRRA.

3. **Shock-type switching test** — After each `switch_to_counterfactual_mode` / `update_mrkv_array`, verify that MrkvArray dimensions, IncShkDstn structure, and shock history arrays have the expected shape and content. Currently only act_T is checked.

**Priority 2 (add for full confidence):**

4. **Recession averaging test** — Verify `recession_prob_array` sums to 1 and the weighted average of known constant results recovers the constant.

5. **Parameter round-trip test** — `return_parameters('Baseline')` vs `return_parameters('Reduced_Run')`: verify key structural parameters (num_base_MrkvStates, T_age, PermGroFac structure) are identical; only scale parameters (AgentCount, act_T, mCount) differ.

6. **Output_Results arithmetic test** — Feed known synthetic results through `get_npv_multiplier` and `get_simulation_percent_diff`; verify output.

**Priority 3 (for completeness):**

7. **Estimation smoke test** — Run Step 2 with very loose tolerance and 1 iteration to verify the estimation loop doesn't crash with current HARK.

8. **Kernel ↔ Welfare integration** — When Welfare.py needs E[u'] for welfare comparisons, it should use the kernel (or at least document that it uses MC, which is correct but noisy).
