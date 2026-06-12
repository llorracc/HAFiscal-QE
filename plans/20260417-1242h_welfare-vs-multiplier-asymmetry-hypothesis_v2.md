# Attributing the Phase 6 vs QE welfare gap in HAFiscal splurge-in-budget

**Author:** Claude + llorracc
**Date:** 2026-04-17
**Scope:** Decompose the 25-36% welfare change (Phase 6 splurge-in-budget vs HAFiscal-QE published) into its constituent sources and test the leading candidate attribution.
**Related code artifacts:** `Code/HA-Models/FromPandemicCode/run_hybrid_welfare6.py`, `mc_welfare_diagnostic.py`, `analyze_welfare_gap.py`; feature flag `HAFISCAL_SPLURGE_OLD` in `AggFiscalModel.get_poststates`.

---

## 1. The puzzle

Running the current Baseline (`--baseline`, 21 types) splurge-in-budget pipeline produces welfare6 and multiplier tables that differ from the published HAFiscal-QE results by **very different magnitudes**:

|                          | QE published | Phase 6 (splurge-in-budget + a-indexed TM) | Relative Δ |
|---|---:|---:|---:|
| **Multiplier**, Check Rec+AD | 1.143 | 1.070 | **−6.4 %** |
| **Welfare6**, Check Rec+AD   | 1.35  | 1.01  | **−25 %**  |
| **Multiplier**, UI Rec+AD     | 1.167 | 1.139 | **−2.4 %** |
| **Welfare6**, UI Rec+AD       | 2.13  | 1.36  | **−36 %**  |
| **Multiplier**, TaxCut Rec+AD | 0.962 | 0.977 | **+1.6 %** |
| **Welfare6**, TaxCut Rec+AD   | 1.11  | 1.00  | **−10 %**  |

Welfare moves **6-15× more** (proportionally) than multipliers. The question is where this asymmetry comes from.

Between QE and Phase 6, four splurge-in-budget-era bug fixes plus one parameter re-estimation were applied:

| Tag | Fix | Affects |
|---|---|---|
| **BUG-030** | Recession-state timing in `mill_rule` ADF | AD feedback at recession→recovery boundary |
| **BUG-031** | Splurge budget identity: $a = m - c_{\text{actual}}$ (splurge-in-budget) vs $a = m - \text{cFunc}(m)$ | Asset update only; solver unchanged |
| **BUG-032** | Lottery-MPC splurge formula + Step-1 re-estimation of ς | Splurge magnitude ς: 0.318 → 0.261 (−18%) |
| **BUG-033** | m-indexed TM collapses ξ-variance; fix = a-indexed TM | Phase 2 wealth targets → β/∇ calibration |
| Phase 2 | β/∇ re-estimation under splurge-in-budget / a-indexed TM | Education-specific discount factors (small shifts) |

Each of these could move welfare and multipliers by different proportions. We want to isolate which one is *the* driver of the 25-36% welfare gap.

---

## 2. Definitions

From `Welfare.py:261-281` and `run_hybrid_welfare6.py`: let $c^{\text{pol}}_{i,t}, c^{\text{base}}_{i,t}$ be per-agent, per-period consumption under the policy and the no-policy counterfactual, simulated on Common Random Numbers (identical shock draws). Let $\Delta c_{i,t} \equiv c^{\text{pol}}_{i,t} - c^{\text{base}}_{i,t}$ and let $c_{ss,t,i}$ be consumption in the no-policy, no-recession steady-state run (the one used to define marginal utilities for Method 6).

**Multiplier** (10-year and full-horizon):

$$M_{10y} = \frac{\sum_{t<40}\sum_i \Delta c_{i,t}\,R^{-t}}{\text{NPV}_{\text{cost}}}, \qquad M_\infty = \frac{\sum_{t,i}\Delta c_{i,t}\,R^{-t}}{\text{NPV}_{\text{cost}}}$$

where $\text{NPV}_{\text{cost}}$ is the discounted extra income given to the private sector by the policy.

**Welfare6 (Method 6, as implemented):**

$$\mathcal{W}_6 \;=\; \underbrace{\frac{1}{\text{NPV}_{\text{cost}}}\sum_{t,i} \frac{u(c^{\text{pol}}_{i,t}) - u(c^{\text{base}}_{i,t})}{u'(c_{ss,t,i})}\,R^{-t}}_{\mathcal{W}^U\;\text{(utility part, with steady-state MU weights)}}
\;+\; \underbrace{\frac{\text{NPV}_{\text{cost}} - \text{NPV}_{\Delta c}}{\text{NPV}_{\text{cost}}}}_{\mathcal{W}^B \;=\; 1-M_\infty}$$

The $u'(c_{ss})$ weighting is the crucial detail: marginal utility is evaluated at the *no-recession* steady state, not at the recession base path. This decouples the welfare valuation from the recession severity.

---

## 3. The central identity (derived correctly for $u'(c_{ss})$ weighting, CRRA $\gamma=2$)

Using $u(c) = -1/c$ and $u'(c) = c^{-2}$:

$$\frac{u(c^{\text{pol}}) - u(c^{\text{base}})}{u'(c_{ss})} \;=\; \frac{c_{ss}^{2}}{c^{\text{base}}(c^{\text{base}} + \Delta c)} \cdot \Delta c
\;=\; \underbrace{\left(\frac{c_{ss}}{c^{\text{base}}}\right)^{\!2}}_{\displaystyle \equiv\; \mathcal R_{ti}} \cdot \frac{\Delta c}{1 + \Delta c/c^{\text{base}}}$$

Expanding the second factor in powers of $\Delta c/c^{\text{base}}$,

$$\frac{u(c^{\text{pol}}) - u(c^{\text{base}})}{u'(c_{ss})} = \mathcal R_{ti}\left[\Delta c - \frac{(\Delta c)^{2}}{c^{\text{base}}} + \frac{(\Delta c)^{3}}{(c^{\text{base}})^{2}} - \cdots\right].$$

Define the **recession-rescaled multiplier** and **concentration measure**:

$$M_\infty^{w} \equiv \frac{1}{\text{NPV}_{\text{cost}}}\sum_{t,i} \mathcal R_{ti}\,\Delta c_{ti}\,R^{-t}, \qquad \mathcal Q^{w} \equiv \frac{1}{\text{NPV}_{\text{cost}}}\sum_{t,i} \mathcal R_{ti}\,\frac{(\Delta c_{ti})^{2}}{c^{\text{base}}_{ti}}\,R^{-t}.$$

The identity for $\mathcal W_6$ is then

$$\boxed{\mathcal W_6 \;=\; 1 + (M_\infty^{w} - M_\infty) \;-\; \mathcal Q^{w} \;+\; O\!\big((\Delta c)^{3}/c^{2}\big).}$$

Three terms:

1. **$1$** — the budget residual when the policy ultimately gets spent ($M_\infty=1$) and $c_{ss}=c^{\text{base}}$ everywhere. In that limit $\mathcal W_6 \to 1$ is the "well-timed transfer" benchmark.
2. **$M_\infty^{w} - M_\infty$** — a *recession premium*. In a recession, $c^{\text{base}} < c_{ss}$, so $\mathcal R_{ti} > 1$ for most $(t,i)$, which up-weights period/agent pairs where base consumption is below normal. If $\Delta c$ correlates positively with "below-normal" states, $M_\infty^w > M_\infty$ and the identity gains a positive term. For UI in a recession this effect is substantial (MC measured: $+0.66$ in UI Rec+AD at Reduced_Run scope).
3. **$- \mathcal Q^{w}$** — a *concentration penalty*. This is the central insight. For fixed $\sum \Delta c$, the welfare cost to the planner is larger when $\Delta c$ is concentrated on $(t,i)$ pairs with low $c^{\text{base}}$ and high $\mathcal R$ — i.e., when a disproportionate share of the stimulus lands on hand-to-mouth agents in deep recession periods. $\mathcal Q^w$ measures that concentration directly.

**Leading-order implication.** If $M_\infty$ changes by a small amount between two versions of the model but $\mathcal Q^w$ changes by a larger amount, $\mathcal W_6$ is dominated by the $\mathcal Q^w$ channel — and that channel is *not* bounded by the multiplier change. This is why welfare can move an order of magnitude more than the multiplier.

---

## 4. What we already know

### 4.1 The identity holds at the level but not at differences

In an MC diagnostic run at `Reduced_Run` scope (3 education types × 7 β atoms × 10K agents, single recession duration, CRN pairs), with a feature flag `HAFISCAL_SPLURGE_OLD=1` that reverts the asset update to pre-splurge-in-budget, we measured:

| Scenario | Quantity | pre-splurge-in-budget | splurge-in-budget | Δ |
|---|---|---:|---:|---:|
| UI Rec=1 AD=0 | $M_\infty$ | 0.996 | 0.989 | −0.69 % |
|               | $\mathcal W_6$ | 1.608 | 1.580 | **−1.72 %** |
|               | $\mathcal Q^w$ | 0.521 | 0.463 | −11 % |
| UI Rec=1 AD=1 | $M_\infty$ | 0.984 | 0.972 | −1.20 % |
|               | $\mathcal W_6$ | 1.449 | 1.428 | **−1.45 %** |
|               | $\mathcal Q^w$ | 0.381 | 0.339 | −11 % |

- **Absolute level of the identity** $\mathcal W_6 \approx 1 + (M_\infty^w - M_\infty) - \mathcal Q^w$ holds within 6-9% (the residual is cubic and higher-order terms).
- **Differences** between the two versions are dominated by cubic terms: the linear+quadratic prediction captures only ~30-35% of $\Delta \mathcal W_6$. This is important: the identity is *descriptive* of the level of welfare but cannot by itself be used for small-shift comparative statics without including $(\Delta c)^3/c^2$ corrections.

### 4.2 BUG-031 alone explains only a small fraction of the Phase 6 vs QE gap

The 1.5-1.7% $\Delta \mathcal W_6$ from the BUG-031 toggle above is an order of magnitude smaller than the observed 25-36% Phase 6 vs QE welfare gap. **BUG-031 is not the dominant source.**

### 4.3 The cross-sectional concentration story is also weak

$\mathcal Q^w$ by c_ss quintile shows that under both pre-splurge-in-budget and splurge-in-budget, about 77% of $|\Delta \mathcal Q^w|$ between the two versions is explained by the top two quintiles, not the bottom — the opposite of what a "fix over-concentration on hand-to-mouth agents" story would predict. Inter-temporal concentration of aggregate $\Delta c$ is also slightly *higher* (not lower) under splurge-in-budget. So the mechanism through which any parameter change moves welfare is not primarily about redistributing the stimulus away from low-$c^{\text{base}}$ agents.

### 4.4 What changed between QE and Phase 6 besides BUG-031

Tracing the Splurge parameter across commits:

| commit | status | ς | β (pooled) | ∇ (pooled) |
|---|---|---:|---:|---:|
| `2315cedf` | Option C in-tree (published-comparable) | **0.318** | 0.978 | 0.026 |
| `93a22a3e` | "Edmunds run" post-Option-C | 0.246 | 0.968 | 0.058 |
| `7e1a6b11` | splurge-in-budget Step 1 re-estimation | 0.246 | 0.968 | 0.058 |
| `7d92b487` | BUG-032 Phase 1 (lottery-MPC) | **0.261** | 0.961 | 0.067 |

The splurge re-estimation under splurge-in-budget dropped ς by **~18% relative to QE** (0.318 → 0.261). Education-specific β/∇ drifted by ≤3%, much smaller. Under the identity in §3, ς is a multiplier on the transitory-income share of consumption, so halving ς cuts the high-MPC response that drives both $\mathcal Q^w$ (via concentration) and $M_\infty^w - M_\infty$ (via the $c_{ss}/c^{\text{base}}$ leverage on the splurge spike in period 0).

---

## 5. Revised primary hypothesis

**(H1)** The dominant contributor to the Phase 6 vs QE welfare gap is the Splurge re-estimation under splurge-in-budget: **ς: 0.318 → 0.261**.

**Mechanism.** The splurge term in the per-period budget — $c_{\text{actual}} = (1-\varsigma)\,c_{\text{HARK}}(m) + \varsigma\,y$ — routes a fraction ς of transitory income directly into period-0 consumption, bypassing the smoothing of the Euler equation. Lower ς means:

1. **Smaller period-0 $\Delta c$ pulse** in response to transitory transfers (Check, UI), because only $\varsigma \cdot y_{\text{transfer}}$ is mechanically absorbed as consumption; the rest goes through cFunc smoothing.
2. **Lower cross-sectional variance of $\Delta c$** at fixed $\sum \Delta c$, because the agents who most benefit (deep HtM) get a smaller mechanical pulse.
3. Therefore **smaller $\mathcal Q^w$**, which in the identity directly lowers $\mathcal W_6$.

**Prediction.** In a counterfactual MC run holding the splurge-in-budget budget identity fixed but rolling Splurge back to ς=0.318 (with or without the matching pre-splurge-in-budget β/∇ triplet), welfare6 should recover much of the distance from 1.36 (Phase 6) to 2.13 (QE) in the UI Rec+AD cell — on the order of $\Delta \mathcal W_6 \approx +0.6$ to $+0.8$.

### 5.1 Subsidiary hypotheses

**(H2)** BUG-031 (budget identity) contributes ~1.5-2% of $\Delta \mathcal W_6$. *Measured; see §4.1.*

**(H3)** BUG-032's change in the *lottery-MPC splurge formula* (the Step-1 estimation target, not just the ς value) is a separable second-order contributor. If H1 is confirmed with the ς toggle alone, H3 is subsumed. If H1 falls short, H3 is the next candidate.

**(H4)** BUG-033 (a-indexed TM ξ-variance) affects Phase 2 β/∇ estimation and therefore propagates into welfare indirectly. The β/∇ shifts are small (<3%), so this should be a minor contributor. Phase 2-prime (currently running under a-indexed TM) will quantify the β/∇ change directly.

**(H5)** BUG-030 (RecState timing) affects the AD amplification channel, which enters $\mathcal W^B = 1 - M_\infty$ and leaks into $\mathcal W_6$ via the concentration-penalty term. Plausibly ≤1% on welfare.

---

## 6. Proposed MC experiment (decisive test of H1)

### 6.1 Design

Run the full Phase-6 welfare pipeline (`run_hybrid_welfare6.py`) in four configurations and compute welfare6 for all three scenarios (Check, UI, TaxCut) × three Rec/AD combos × two parametrizations:

| Run | `HAFISCAL_SPLURGE_OLD` | ς | β/∇ | Interpretation |
|---|---|---:|---|---|
| **A** | 0 | 0.261 | current Phase 2 | current Phase 6 (reference, already have) |
| **B** | 1 | 0.261 | current Phase 2 | BUG-031 alone rolled back |
| **C** | 0 | 0.318 | current Phase 2 | ς rollback, β/∇ current (quick test of H1 magnitude) |
| **D** | 1 | 0.318 | pre-splurge-in-budget (commit 93a22a3e) | full QE-side rollback (tests whether the stack closes the gap) |

Run D should, if the story is complete, reproduce QE welfare6 numbers within Monte-Carlo noise (~1-2% SE at Baseline N). If there's a gap between D and QE, a residual bug remains to be identified (H6).

### 6.2 Implementation

Three additions to existing infrastructure:

1. **Splurge override flag.** In `AggFiscalModel.py`, accept `HAFISCAL_SPLURGE_OVERRIDE=<float>` and set `self.Splurge = float(os.environ["HAFISCAL_SPLURGE_OVERRIDE"])` during `__init__` (or in `Parameters.py` so it's applied consistently to all agent types).

2. **β/∇ override.** In `Parameters.py` where `DiscFacDstns` is constructed from `DiscFacEstim_...txt`, add an `HAFISCAL_DISCFAC_FILE=<path>` override. Point Run D at `git show 93a22a3e:Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01.txt`.

3. **Shell script** `run_welfare_attribution.sh` that runs A, B, C, D and writes all 4 welfare6.tex + Multiplier.tex tables to `Tables/Attribution/<run>/`.

### 6.3 Expected output

A 4-row × 9-column table (3 scenarios × 3 Rec/AD combos) showing how $\mathcal W_6$ moves across A → B → C → D. Each step attributes a specific fix to a specific welfare shift. Side-by-side with QE published values (from the 3-column Multiplier.tex and the 3-column welfare6.tex in `Tables/CRRA2/`).

**Acceptance criterion for H1.** Run C's welfare6 for UI Rec+AD should be at least 1.8 (halfway between 1.36 and 2.13). If it gets to 2.0+, H1 is strongly confirmed. If it stays below 1.5, H1 is wrong and we move to H3.

**Sanity check on M.** Multipliers should barely change A → C (the mechanical pulse via ς is small in NPV_cost-relative terms). If multipliers also move 10%+ from ς alone, the story in §5 is incomplete.

### 6.4 Cost

- Run C: `run_hybrid_welfare6.py --baseline` with a ς-override env var. ~45-60 min on the current machine (same cost as Phase 6).
- Run D: same plus discfac-file override. ~45-60 min.

Total ~2-2.5 hours of compute. Negligible engineering time once the two overrides are wired (≈30 min).

---

## 7. Secondary experiment (for completeness)

If H1 is confirmed by runs A→C, **run E** applies only BUG-030's RecState timing flag (the existing `recstate_timing=` option) at ς=0.261 to verify the BUG-030 contribution to multipliers is in line with the BUG-030 commit message (~11% AD amplification change in MC). This closes the multiplier-side of the attribution.

---

## 8. Limitations

1. **CRN within a run, not across runs.** Runs A-D use the same seeds (765607780, etc.) so shocks are fixed; but changes in ς change the *state dynamics* of each agent (different $a$ path → different $m$ → different $c$), so per-$(i,t)$ $\Delta c$ differs across runs even at identical draws. This is a feature, not a bug — the comparison is across *policy-rule environments*, not across shock realizations.

2. **Cubic and higher-order corrections in the identity.** At the *differences* between runs, the leading-order identity $\Delta \mathcal W_6 \approx \Delta(M_\infty^w - M_\infty) - \Delta \mathcal Q^w$ only captures ~30-40% of the welfare change. The remainder is cubic terms that depend on the joint distribution of $(\Delta c, c^{\text{base}})$ at the per-$(t,i)$ level. This means attribution via identity decomposition is approximate; attribution via direct re-simulation (runs A-D) is exact and is the gold standard.

3. **β/∇ pairing (run D).** The pre-splurge-in-budget β/∇ estimates at commit 93a22a3e were calibrated to wealth moments under the buggy budget identity (and potentially under the buggy lottery-MPC target). Using them with splurge-in-budget ON will produce a model whose empirical moments don't match the targets — but that's the point: we're asking "what does the QE-era parameter stack produce under the splurge-in-budget pipeline?" If the welfare result matches QE, the pipeline was consistent; if not, the calibration-target mismatch is non-trivial for welfare and we'd want to re-estimate under splurge-in-budget with the pre-splurge-in-budget lottery-MPC formula (which is BUG-032's inverse).

4. **Pool vs. heterogeneity in ς.** The splurge re-estimation shifted ς pooled across education groups. If ς should be education-specific (as β/∇ is), a pooled override won't recover per-group welfare correctly. The current codebase uses one ς for all groups; this limitation is therefore inherited from the model spec, not the experiment.

---

## 9. Decision protocol after running experiment

| Outcome of Run C (UI Rec+AD welfare6) | Conclusion | Next step |
|---|---|---|
| $\mathcal W_6 \geq 2.0$ | H1 strongly confirmed | Run D for full closure; commit attribution table |
| $1.6 \leq \mathcal W_6 < 2.0$ | H1 partially confirmed; β/∇ + other fixes explain the residual | Run D; decompose residual |
| $1.36 < \mathcal W_6 < 1.6$ | H1 small effect; dominant driver elsewhere | Investigate H3 (lottery-MPC formula change itself), H4 (β/∇), H5 (BUG-030) sequentially via further flag toggles |
| $\mathcal W_6 \leq 1.36$ | H1 rejected (ς rollback doesn't help or hurts) | Return to the identity and examine the $(\Delta c)^3/c^2$ contribution directly; possibly a solver-interaction effect |

---

## 10. Summary

The 25-36% welfare gap between Phase 6 (splurge-in-budget) and HAFiscal-QE is **not** driven by the splurge-in-budget budget-identity fix (BUG-031), which moves welfare by only ~1.5-1.7% in MC diagnostic at Reduced_Run scope. The leading candidate is the **Splurge re-estimation ς: 0.318 → 0.261** under BUG-032 Phase 1, which acts through the $\mathcal Q^w$ concentration channel of the $u'(c_{ss})$-weighted welfare identity. A decisive MC test is proposed in §6: run `run_hybrid_welfare6.py --baseline` in four configurations (A/B/C/D) crossing the BUG-031 flag with a ς-override (0.261 vs 0.318), optionally paired with the pre-splurge-in-budget β/∇ file. Expected cost ~2-2.5 hours compute. Acceptance criterion: Run C's UI Rec+AD welfare6 should exceed 1.8 (vs Phase 6's 1.36 and QE's 2.13).
