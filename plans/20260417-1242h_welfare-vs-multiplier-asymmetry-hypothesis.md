# Why does welfare change ~25-36% under splurge-in-budget when multipliers barely move?

**Status:** **REVISED — initial hypothesis partially rejected by MC evidence.**
The central *mathematical* identity survives, but the attribution of the 25-36%
welfare gap to BUG-031 alone is **wrong**. MC diagnostic shows BUG-031's
budget-identity fix contributes only ~1.5-1.7% of ΔW_6 in Reduced_Run UI
scenarios (with and without AD). The remaining ≫90% of the welfare gap
between Phase 6 and QE-published comes from other bug fixes — primarily
the Splurge re-estimation (ς: 0.318 → 0.261) and education-group β/∇
shifts through the Phase 2 estimation chain. Summary of evidence in §10.

**Author:** Claude + llorracc
**Date:** 2026-04-17 (revised after evidence)
**Related:** BUG-031 (splurge budget identity), BUG-032 (lottery-MPC splurge, ς re-estimation), BUG-033 (m-indexed TM ξ-variance collapse), Phase 5 production, Phase 6 welfare6.

---

## 1. The puzzle

Under the splurge-in-budget splurge fix, on the Baseline CRRA=2 parametrization:

|                          | QE published | Phase 5/6 (splurge-in-budget + TM_a) | Δ |
|---|---:|---:|---:|
| **Multiplier**, Check Rec+AD | 1.143 | 1.070 | **−6.4 %** |
| **Welfare6**, Check Rec+AD   | 1.35  | 1.01  | **−25 %**  |
| **Multiplier**, UI Rec+AD     | 1.167 | 1.139 | **−2.4 %** |
| **Welfare6**, UI Rec+AD       | 2.13  | 1.36  | **−36 %**  |
| **Multiplier**, TaxCut Rec+AD | 0.962 | 0.977 | **+1.6 %** |
| **Welfare6**, TaxCut Rec+AD   | 1.11  | 1.00  | **−10 %**  |

The welfare changes are **6-15× larger (proportionally) than the multiplier changes**. Why?

---

## 2. Definitions (from `Welfare.py:261-281`)

Let $c^{\text{pol}}_{i,t}$ and $c^{\text{base}}_{i,t}$ be the consumption of agent $i$ at time $t$ under the policy and no-policy experiments, respectively (both simulated on the same Common Random Numbers). Let $\Delta c_{i,t} \equiv c^{\text{pol}}_{i,t} - c^{\text{base}}_{i,t}$.

Let $\text{NPV}_{\text{cost}}$ be the net-present-value of the extra income given to the private sector by the policy. Let $R = \text{Rfree\_base[0]}$ and $\beta_{SP} = 1/R$.

### Multiplier (10-year cumulative)

$$
M_{10y} \;=\; \frac{\sum_{t=0}^{39}\sum_{i} \Delta c_{i,t} \, R^{-t}}{\text{NPV}_{\text{cost}}}
$$

### Welfare6

$$
\boxed{\mathcal{W}_6 \;=\; \underbrace{\frac{1}{\text{NPV}_{\text{cost}}}\sum_{t=0}^{T-1} R^{-t} \sum_{i} \frac{u(c^{\text{pol}}_{i,t}) - u(c^{\text{base}}_{i,t})}{u'(c^{\text{base}}_{i,t})}}_{\displaystyle \equiv\; \mathcal{W}^U\;\text{(utility part)}} + \underbrace{\frac{\text{NPV}_{\text{cost}} - \text{NPV}_{\Delta c}}{\text{NPV}_{\text{cost}}}}_{\displaystyle \equiv\; \mathcal{W}^B\;\text{(budget residual)}}}
$$

Here $T$ is the full simulation horizon (longer than 40 periods — see `periods = act_T` in `run_hybrid_welfare6.py`) and $\text{NPV}_{\Delta c} = \sum_{t,i}\Delta c_{i,t} R^{-t}$. Under splurge-in-budget + AD the full-horizon multiplier $M_{\infty} \equiv \text{NPV}_{\Delta c}/\text{NPV}_{\text{cost}}$ generally exceeds $M_{10y}$ because AD amplification extends beyond 10 years; $\mathcal{W}^B = 1 - M_{\infty}$.

### CRRA closed form

For $\gamma \neq 1$:

$$
\frac{u(c^{\text{pol}}) - u(c^{\text{base}})}{u'(c^{\text{base}})} \;=\; \frac{c^{\text{base}}}{1-\gamma}\left[\Big(\frac{c^{\text{pol}}}{c^{\text{base}}}\Big)^{1-\gamma} - 1\right]
$$

For the baseline $\gamma = 2$:

$$
\frac{u(c^{\text{pol}}) - u(c^{\text{base}})}{u'(c^{\text{base}})} \;=\; c^{\text{base}}\left(1 - \frac{c^{\text{base}}}{c^{\text{pol}}}\right) \;=\; \frac{\Delta c}{1 + \Delta c / c^{\text{base}}}
$$

The per-agent, per-period **consumption-equivalent welfare gain**.

---

## 3. Key identity: the welfare–multiplier gap

Expanding the CRRA=2 expression around $\Delta c = 0$:

$$
\frac{\Delta c}{1 + \Delta c/c^{\text{base}}} \;=\; \Delta c - \frac{(\Delta c)^2}{c^{\text{base}}} + \frac{(\Delta c)^3}{(c^{\text{base}})^2} - \cdots
$$

Summing over agents and time, and dividing by $\text{NPV}_{\text{cost}}$:

$$
\mathcal{W}^U \;=\; M_{\infty} \;-\; \underbrace{\frac{1}{\text{NPV}_{\text{cost}}}\sum_{t,i} \frac{(\Delta c_{i,t})^2}{c^{\text{base}}_{i,t}}\, R^{-t}}_{\equiv\; \mathcal{Q}} \;+\; O\!\left(\frac{(\Delta c)^3}{c^2}\right)
$$

And therefore (using $\mathcal{W}^B = 1 - M_{\infty}$):

$$
\boxed{\mathcal{W}_6 \;=\; 1 \;-\; \mathcal{Q} \;+\; O\!\left(\frac{(\Delta c)^3}{c^2}\right)}
$$

**This is the central identity.** To leading order in $\Delta c/c$:

- The multiplier $M_{\infty}$ cancels out: welfare is **not** driven by aggregate consumption response.
- Welfare is driven by the **concentration measure** $\mathcal{Q} = \frac{1}{\text{NPV}_{\text{cost}}}\!\sum_{t,i}\!(\Delta c_{i,t})^2 / c^{\text{base}}_{i,t} \cdot R^{-t}$.

Changes in $\mathcal{Q}$ are NOT bounded by changes in $M_{\infty}$. They depend on the **joint distribution** of $(\Delta c, c^{\text{base}})$ across agents and time, which can shift dramatically under splurge-in-budget while the aggregate $\sum \Delta c$ stays roughly fixed.

---

## 4. Primary hypothesis

**(H1)** The splurge-in-budget fix redistributes $\Delta c$ across $(i, t)$ in a way that changes $\mathcal{Q}$ much more than it changes $M_{\infty}$.

Specifically:

**(H1a) Cross-sectional redistribution.** Under the old (buggy) splurge accounting, $\Delta c$ was over-concentrated on low-$c^{\text{base}}$ (hand-to-mouth, high-MPC) agents. The splurge-in-budget fix spreads $\Delta c$ more evenly across the wealth distribution. Since $\mathcal{Q}$ weights $(\Delta c)^2$ by $1/c^{\text{base}}$, concentrating $\Delta c$ on low-$c^{\text{base}}$ agents inflates $\mathcal{Q}$. Fixing this concentration reduces $\mathcal{Q}$ → reduces $\mathcal{W}_6$.

**(H1b) Inter-temporal smoothing.** Under the old code, the "splurge" portion of income support was booked as period-0 consumption (high $\Delta c_{i,0}$), then fully absorbed by the solver's decision rule in period 1. Under splurge-in-budget, the splurge still appears in period 0 but the resulting asset path is correctly updated, so subsequent periods have higher $c^{\text{pol}}$ than under the old code — meaning $\Delta c$ is smoothed across time. A smoother time-path has smaller $\sum_t (\Delta c_t)^2$ at fixed $\sum_t \Delta c_t$ (Jensen).

**(H1c) ξ-variance restoration.** BUG-033 (m-indexed TM ξ-variance collapse) underestimated the variance of realized income $\xi$ across agents. Under splurge-in-budget + a-indexed TM, the true cross-sectional $\xi$-variance is preserved. For the MC welfare6 calculation this specifically affects the recession+AD scenario because the AD feedback loop responds to realized aggregate consumption, which under the old accounting was systematically over-amplified by the $\xi$-variance bias.

**Prediction.** Under CRN-paired old-vs-new MC runs, we should observe:

1. $M_{\infty}^{\text{new}} / M_{\infty}^{\text{old}} \approx 1 \pm 0.05$ (small change, consistent with the 2-6% observed multiplier shift).
2. $\mathcal{Q}^{\text{new}} / \mathcal{Q}^{\text{old}} < 0.8$ (substantial reduction, consistent with the 25-36% welfare reduction).
3. The reduction in $\mathcal{Q}$ comes primarily from (a) the concentration ratio $\sum_i (\Delta c_i)^2 / \sum_i \Delta c_i$ (cross-sectional), (b) the time-concentration $\sum_t (\Delta c_t)^2 / \sum_t \Delta c_t$ (inter-temporal), or (c) both.
4. The $\mathcal{Q}$ reduction is largest in the UI Rec+AD scenario (where welfare fell 36%) and smallest in TaxCut Rec+AD (where welfare fell only 10%).

---

## 5. Minimal MC experiment to test H1

### 5.1 Design

**Goal.** Run the identical agent population under (old splurge code, new splurge code) with Common Random Numbers, save full panel data $\{c_{i,t}, a_{i,t}, \xi_{i,t}\}$, and decompose the $\mathcal{Q}$ difference into H1a/H1b/H1c components.

**Parallel code versions.**
- "NEW": current `_matsya` branch, splurge-in-budget splurge, Phase 2 β/∇.
- "OLD": same branch, but with the splurge-in-budget fix reverted to the pre-fix splurge formula. The key line is in `AggFiscalModel.py` (or wherever `c_actual` is computed per period). We need a feature flag `HAFISCAL_SPLURGE_OLD=1` that routes through the old formula for this diagnostic run only.

**Shared state.**
Same $\beta/\nabla$, same $\varsigma = 0.2609$, same seed, same agent count, same MrkvArray, same IncShkDstn. The ONLY difference is the splurge accounting formula. Both runs share the identical draws of $\xi_{i,t}$ and $\psi_{i,t}$ because HARK's RNG is seeded deterministically per agent.

**Scenarios.**
Start small: just **UI extension, Rec=1, AD=1** (the scenario with the largest welfare gap). Expand to Check/TaxCut if the UI result is inconclusive.

**Scale.**
- 1 education type (HS, where β/∇ estimation has highest quality)
- 1000 agents × 7 DiscFac atoms = 7000 agents
- T = 100 periods (25 years — enough for welfare6 integrals to converge within 0.1%)

A single scenario should run in ~3-5 min per version → ~10 min total for old+new.

### 5.2 Data saved per run

For each $(i, t)$:
- $c^{\text{pol}}_{i,t}, c^{\text{base}}_{i,t}, \Delta c_{i,t}$
- $a^{\text{pol}}_{i,t}, a^{\text{base}}_{i,t}$
- $\xi_{i,t}, \psi_{i,t}$ (the raw shocks — identical across old/new)
- $m_{i,t}$, MrkvState $j_{i,t}$, pLvl$_{i,t}$

Saved as NumPy `.npz` files per (version, scenario).

### 5.3 Diagnostics

Compute the following quantities under BOTH versions:

| Symbol | Formula | Interpretation |
|---|---|---|
| $M_{10y}$ | $\sum_{t<40,i} \Delta c_{i,t} R^{-t} / \text{NPV}_{\text{cost}}$ | 10-year multiplier |
| $M_{\infty}$ | $\sum_{t,i} \Delta c_{i,t} R^{-t} / \text{NPV}_{\text{cost}}$ | Full-horizon multiplier |
| $\mathcal{Q}$ | $\sum_{t,i} (\Delta c_{i,t})^2 / c^{\text{base}}_{i,t} \cdot R^{-t} / \text{NPV}_{\text{cost}}$ | Welfare-multiplier gap (leading order) |
| $\mathcal{W}^U$ | exact CRRA formula | Utility-part welfare |
| $\mathcal{W}^B$ | $1 - M_{\infty}$ | Budget residual |
| $\mathcal{W}_6$ | $\mathcal{W}^U + \mathcal{W}^B$ | Total welfare |
| $\mathcal{C}_x$ | $\text{Var}_i(\Delta c_{i,\cdot}) / (\text{mean}_i \Delta c_{i,\cdot})^2$ | Cross-sectional concentration |
| $\mathcal{C}_t$ | $\text{Var}_t(\Delta c_{\cdot, t}) / (\text{mean}_t \Delta c_{\cdot, t})^2$ | Inter-temporal concentration |
| $\mathcal{Q}_{\text{lo}}/\mathcal{Q}_{\text{hi}}$ | Fraction of $\mathcal{Q}$ from bottom/top quintile of $c^{\text{base}}$ | H1a diagnostic |
| $\rho_{\Delta c, 1/c^{\text{base}}}$ | correlation | H1a diagnostic |

### 5.4 Hypothesis tests

**Test 1 (primary).** Is $\Delta \mathcal{W}_6 \approx -\Delta \mathcal{Q}$ to within higher-order corrections?

$$
\frac{(\mathcal{W}_6^{\text{new}} - \mathcal{W}_6^{\text{old}}) - (-\mathcal{Q}^{\text{new}} + \mathcal{Q}^{\text{old}})}{\mathcal{W}_6^{\text{old}}} \stackrel{?}{<} 0.05
$$

If YES, the identity $\mathcal{W}_6 \approx 1 - \mathcal{Q}$ explains the bulk of the welfare change → H1 confirmed.

If NO, higher-order terms matter and we need to look at $\sum (\Delta c)^3 / c^2$ (H2 below).

**Test 2 (H1a — cross-sectional).**
$$
\frac{\mathcal{Q}_{\text{lo}}^{\text{old}} - \mathcal{Q}_{\text{lo}}^{\text{new}}}{\mathcal{Q}^{\text{old}} - \mathcal{Q}^{\text{new}}} \stackrel{?}{>} 0.5
$$
"Is most of the $\mathcal{Q}$ change explained by the bottom-$c^{\text{base}}$ quintile?"

**Test 3 (H1b — inter-temporal).**
$$
\frac{\mathcal{C}_t^{\text{new}}}{\mathcal{C}_t^{\text{old}}} \stackrel{?}{<} 0.9
$$
"Does splurge-in-budget smooth $\Delta c$ across time?"

**Test 4 (H1c — ξ-variance).**
Compute the cross-sectional variance of $\xi$-induced consumption response at $t=0$:
$$
\text{Var}_i\big[c^{\text{pol}}_{i,0}(\xi_{i,0}, \text{other}) - c^{\text{pol}}_{i,0}(E[\xi], \text{other})\big]
$$
This should be larger under NEW than under OLD (because OLD suffered from BUG-033 ξ-collapse in TM but NOT in MC — so H1c is actually NOT tested by this MC experiment; it's a TM-specific issue. **Noted limitation.**).

Actually: H1c is about TM vs MC behavior; since this experiment uses MC for both OLD and NEW, H1c cannot be directly tested here. H1c can be separately tested by running the SAME welfare6 computation under MC (current) vs TM (experimental a-indexed path if we add welfare6 to TM, which is hard per the "Skipping welfare tables" note). **We'll focus on H1a and H1b.**

---

## 6. Fallback hypotheses (if H1 fails)

**(H2) Sign flips matter.** If $\Delta c_{i,t}$ changes sign for some $(i, t)$ between OLD and NEW (i.e., some agents' consumption response reverses direction), then the unsigned quantities $\mathcal{Q}$ could move substantially. Diagnose by counting $|\{(i,t) : \text{sign}(\Delta c^{\text{old}}) \neq \text{sign}(\Delta c^{\text{new}})\}|$.

**(H3) MPC-out-of-transitory vs permanent mismatch.** The splurge formally applies only to transitory income. If the old code inadvertently treated permanent income shocks as partially "splurgeable", then policies that hit $\psi$ vs $\xi$ differently (e.g., TaxCut affects persistent income while Check affects transitory) would have differently biased welfare. Diagnose by checking whether the $\mathcal{Q}$ change is concentrated in $\psi$-high vs $\xi$-high sub-samples.

**(H4) Solver-splurge interaction.** The old formula $c = (1-\varsigma)\text{cFunc}(m + \varsigma\xi) + \varsigma\xi$ evaluates cFunc at a shifted grid point. If the solver's cFunc has material curvature between $m$ and $m + \varsigma\xi$, then the old formula and splurge-in-budget give different per-agent consumption levels AT THE FIRST ORDER (not just in decomposition). Diagnose by computing $c^{\text{old}}_{i,t} - c^{\text{new}}_{i,t}$ directly on the base no-policy path (where $\Delta c$ is irrelevant).

---

## 7. Implementation plan

### 7.1 Add `HAFISCAL_SPLURGE_OLD` feature flag

1. Locate the splurge formula in `AggFiscalModel.py` (search for `Splurge` in the agent's per-period update method).
2. Add a guarded branch: if `os.environ.get("HAFISCAL_SPLURGE_OLD", "0") == "1"`, use the old formula; else splurge-in-budget.
3. Document the old formula exactly — check `git log -p` on `AggFiscalModel.py` around the splurge-in-budget fix commit to recover it.

### 7.2 Write `mc_welfare_diagnostic.py`

1. Small script that runs ONE scenario (UI Rec=1, AD=1), with full panel save.
2. Accepts `--version={old,new}` flag; toggles the env var; otherwise identical.
3. Saves NPZ to `/tmp/welfare_diag/{version}/UI_Rec1_AD1.npz`.
4. Uses N=7000 agents, T=100 periods.

### 7.3 Write `analyze_welfare_gap.py`

1. Loads both NPZ files.
2. Computes all diagnostic quantities from §5.3.
3. Runs the 4 tests from §5.4.
4. Writes a concise report to `/tmp/welfare_diag/report.txt`.

### 7.4 Iterate

- If H1 tests pass with >95% variance explained by $\mathcal{Q}$, revise this document to "summary + evidence" form and commit.
- If H1 tests fail, examine diagnostic output and check H2/H3/H4. Revise hypotheses and rerun if needed.

### 7.5 Expected timeline

- Flag addition: 30 min (finding the right place + git archaeology for old formula)
- Diagnostic scripts: 45 min (MC runner + analyzer)
- Runs: 10 min
- Interpretation: 30 min
- Doc revision: 30 min
- **Total: ~2.5 hours**

---

## 8. Current limitations / caveats

1. **H1c cannot be tested here.** BUG-033 is a TM-only bug; since welfare6 is computed via MC, the ξ-variance story does not apply. The 25-36% welfare change must be attributable to BUG-031 (budget identity) alone in the welfare MC path.

2. **Phase 6 β/∇ came from m-indexed Phase 2.** If Phase 2-prime (currently running in background, PIDs 673928-30) gives materially different β/∇, the Phase 6 welfare numbers shift too. We should re-run Phase 6 with refreshed β/∇ BEFORE finalizing conclusions in §6.

3. **The old formula is not uniquely defined.** There were at least two buggy variants pre-fix: (a) $c = (1-\varsigma)\text{cFunc}(m+\varsigma\xi)+\varsigma\xi$ (Option-A-like), (b) inconsistent $a$-update. The git log around the splurge-in-budget fix commit will tell us which was live in the QE production run.

4. **Policy-cost timing.** $\text{NPV}_{\text{cost}}$ might be computed differently under OLD vs NEW if the cost is derived from the same code path as consumption. Sanity check by hard-coding the policy cost from the design, not extracting it from the simulated paths.

---

## 9. Decision point after MC experiment

- **If $\Delta \mathcal{W}_6 \approx -\Delta \mathcal{Q}$ holds (H1 confirmed):** Document the identity cleanly, show the decomposition by wealth quintile / time window, and declare closure. No further investigation needed.
- **If the identity fails but H2/H3/H4 explains it:** Extend the document with the additional mechanism and its math.
- **If none explain:** stop and seek a fourth hypothesis; possibly engage @llorracc to discuss whether there's a structural source I'm missing.

---

## 10. Evidence from MC experiment (2026-04-17)

### 10.1 Corrected identity

The identity in §3 assumed $u'(c^{\text{base}})$ weighting. The code (`run_hybrid_welfare6.py`) actually uses $u'(c_{ss})$ (steady-state no-policy) weighting. For CRRA $\gamma=2$, a careful expansion gives

$$\frac{u(c^{\text{pol}}) - u(c^{\text{base}})}{u'(c_{ss})} = \left(\frac{c_{ss}}{c^{\text{base}}}\right)^{\!2}\!\frac{\Delta c}{1 + \Delta c/c^{\text{base}}} = R_{ti}\bigl[\Delta c - (\Delta c)^{2}/c^{\text{base}} + O(\Delta c^{3})\bigr]$$

with $R_{ti} \equiv (c_{ss}/c^{\text{base}})^2$. Summing and defining weighted analogues of the multiplier and the concentration measure,

$$M_{\infty}^{w} \;\equiv\; \frac{1}{\text{NPV}_{\text{cost}}}\sum_{t,i} R_{ti}\,\Delta c_{ti}\,R^{-t}, \qquad \mathcal{Q}^{w} \;\equiv\; \frac{1}{\text{NPV}_{\text{cost}}}\sum_{t,i} R_{ti}\,\frac{(\Delta c_{ti})^{2}}{c^{\text{base}}_{ti}}\,R^{-t},$$

the corrected central identity is

$$\boxed{\mathcal{W}_{6} \;=\; 1 + (M_{\infty}^{w} - M_{\infty}) - \mathcal{Q}^{w} \;+\; O((\Delta c)^{3}/c^{2})}$$

The extra term $M_{\infty}^{w} - M_{\infty}$ is a "recession-rescaling" correction that vanishes only when $c_{ss} = c^{\text{base}}$ everywhere (no recession).

### 10.2 Experiment

MC runs on `Reduced_Run` parametrization (3 education types × 7 $\beta$ atoms), single recession duration (0), both OLD ($a = m - \text{cFunc}(m)$) and NEW (splurge-in-budget, $a = m - c_{\text{actual}}$) splurge accounting, CRN-paired by setting `HAFISCAL_SPLURGE_OLD` env flag in `AggFiscalModel.get_poststates`. Panel data saved from `Full_Output=True`. Analyzer computes $M_{10y}, M_\infty, M_\infty^w, W_U, W_B, W_6, \mathcal{Q}^w$, plus decompositions.

Scripts: `Code/HA-Models/FromPandemicCode/mc_welfare_diagnostic.py`, `analyze_welfare_gap.py`.

### 10.3 Results

| Scenario | Quantity | OLD | NEW | NEW − OLD |
|---|---|---:|---:|---:|
| UI Rec=1 AD=0 | $M_\infty$ | 0.9960 | 0.9891 | −0.69% |
|               | $\mathcal{W}_6$ | 1.6080 | 1.5803 | **−1.72%** |
|               | $\mathcal{Q}^w$ | 0.5205 | 0.4633 | −11.0% |
| UI Rec=1 AD=1 | $M_\infty$ | 0.9841 | 0.9723 | −1.20% |
|               | $\mathcal{W}_6$ | 1.4487 | 1.4277 | **−1.45%** |
|               | $\mathcal{Q}^w$ | 0.3808 | 0.3386 | −11.1% |

- **Absolute identity** holds well: $\mathcal{W}_6 \approx 1 + (M_\infty^w - M_\infty) - \mathcal{Q}^w$ with residual 6-9% of $\mathcal{W}_6$ (higher-order terms).
- **Differential identity** ($\Delta \mathcal{W}_6 \approx \Delta(M_\infty^w - M_\infty) - \Delta \mathcal{Q}^w$) has residual ≈67% of $|\Delta \mathcal{W}_6|$ — the cubic and higher terms matter substantially for *changes* even when they are small for *levels*.
- **H1a (cross-sectional bottom-quintile)**: REJECTED. $\mathcal{Q}^w$ reduction is concentrated in the top two quintiles (q3 + q4 together account for ~77% of $|\Delta \mathcal{Q}^w|$), not the bottom quintile as hypothesized.
- **H1b (inter-temporal smoothing)**: REJECTED. The coefficient of variation of aggregate $\Delta c_t$ across $t$ is HIGHER under NEW (13.53) than OLD (12.84) — NEW is more concentrated in time, not smoother.

### 10.4 Attribution of the 25-36% Phase 6 vs QE gap

**The initial framing was wrong.** BUG-031 (budget-identity fix) produces only ~1.7% ΔW_6 in Reduced_Run UI scenarios. The 25-36% gap between Phase 6 NEW and QE published must therefore come from a combination of:

| Bug fix | Parameter shift | Expected direction of welfare effect |
|---|---|---|
| **BUG-032 Phase 1** (lottery-MPC splurge formula + re-estimation) | ς: 0.318 → 0.261 (−18%), β̄: 0.978 → 0.961, ∇̄: 0.026 → 0.067 | Large — a smaller splurge reduces the high-MPC mass that drives concentration in $\Delta c$ |
| **BUG-031 splurge-in-budget** (budget identity) | Asset update formula only | Small (~1.7% measured here) |
| **Phase 2 education β/∇** re-estimation | Minor shifts (<3% each) | Small |
| **BUG-033 a-indexed TM** | Affects Phase 2 estimation targets (wealth moments) | Indirect — changes calibrated β/∇ |
| **BUG-030 RecState timing** | Recession-transition AggDemandFac | Small on welfare; moderate on multipliers |

The **dominant driver** is almost certainly the Splurge re-estimation from ς ≈ 0.318 (QE) to ς ≈ 0.261 (current splurge-in-budget + BUG-032). Lower ς means a smaller fraction of policy transfers passes through as mechanical period-0 consumption, so $\Delta c$ is less front-loaded and less concentrated on high-MPC agents → smaller $\mathcal{Q}^w$ → smaller $\mathcal{W}_6$.

### 10.5 Status of the original hypothesis H1

- **Mathematical identity (§3 corrected to §10.1)**: **confirmed at level** (within 6-9%), informative.
- **H1a (cross-sectional bottom-quintile concentration)**: **rejected** — the action is in the upper quintiles.
- **H1b (inter-temporal smoothing)**: **rejected** — NEW is not smoother across time.
- **H1 (BUG-031 explains the 25-36% gap)**: **rejected** — it explains ≤2 percentage points of that 25-36%.

### 10.6 Revised follow-up

To complete the decomposition, a future test should toggle ς between 0.261 (current) and 0.318 (QE) at fixed β/∇ — or more rigorously, pair the ς-rollback with the corresponding pre-splurge-in-budget β/∇ triplet. Expected outcome: most of the remaining welfare gap should close. This is out of scope for the current §7 exercise but would definitively close the attribution question.
