# Welfare-vs-multiplier asymmetry — reformulated plan (v3)

**Status.** This supersedes v1 and v2. Those plans were written before the pulled `BUGS_private/HAFiscal_splurge_budget_inconsistency/` documents (commit `9992697c`, 2026-04-17) and rested on the wrong parameter trajectory. In particular, v2's "Run C" (NEW assets, ς=0.318, current β/∇) was an off-manifold point that does not correspond to any jointly-estimated calibration, because under the bugfix the lottery-MPC formula and the asset update share the same accounting — ς, β, and ∇ are jointly determined. v3 rebuilds the plan around the actual parameter trajectory and the actual open question.

---

## 1. The asymmetry, correctly stated

Baseline CRRA2, Rec=1, AD=1 (paper Table 3/5 headline):

| Row | QE published | Phase 6 current | Δ |
|---|---:|---:|---:|
| 10y AD multiplier — Check | 1.228 | 1.070 | −13 % |
| 10y AD multiplier — UI    | 1.209 | 1.139 | −6 % |
| 10y AD multiplier — TC    | 0.975 | 0.977 | +0.2 % |
| Welfare-6 — Check | 1.35 | 1.01 | **−25 %** |
| Welfare-6 — UI    | 2.13 | 1.36 | **−36 %** |
| Welfare-6 — TC    | 1.11 | 1.00 | **−10 %** |

Sources: `BUGS_private/HAFiscal_splurge_budget_inconsistency/results.md` §§1,4.

The welfare moves are 2–6× larger than the multiplier moves. Explaining that gap is the object of this plan.

## 2. Parameter trajectory (the v2 error)

The full bugfix cascade moved parameters in two stages, not one:

| Stage | Solver / TM | ς | HS β | HS ∇ | College β | College ∇ | Dropout β | Dropout ∇ | Used by |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| **QE published** | m-indexed | 0.2461 | 0.9290 | 0.0708 | 0.9825 | ? | 0.7188 | 0.3177 | QE paper |
| **Phase 2 re-estim (m-TM)** | m-indexed | 0.2609 | 0.9298 | ~0.071 | 0.9835 | ~same | 0.6995 | ~same | **Phase 6 current** |
| **Phase 2-prime re-estim (a-TM)** | a-indexed | 0.2609 | 0.8961 | 0.1111 | ~similar central | ~2× | ~similar | (widens) | not yet run |

Numbers via `distilled-summary.md` §5 and `results.md` §§3,5,7.

**The crucial observation v2 missed.** Phase 6 current welfare6 was computed with *mixed-vintage* calibration: splurge-in-budget asset update + a-indexed TM solver + ς from the bugfix lottery-MPC formula, but **per-education (β, ∇) still from the m-indexed Phase 2 re-estimation**. The a-indexed Phase 2-prime re-estimation has *just* landed (commit `622f25b2`, arrived in `9992697c`) and shows HS β −3.5 % vs QE and HS/college ∇ roughly doubling. Those new (β, ∇) have not been fed through a production welfare run.

So the −25 / −36 / −10 % welfare gap is **not yet the endpoint**. It is an intermediate snapshot with an internally inconsistent calibration.

## 3. What actually drives the welfare gap (revised hypotheses)

Three channels, in order of *a priori* magnitude now:

**(H_∇)** Per-education ∇ re-estimation under a-indexed TM. HS and college ∇ roughly doubling means the within-education β distribution spreads out much more. Welfare-6 integrates nonlinearly over the wealth distribution, and wider within-group heterogeneity (i) shifts the ergodic mass toward more low-β / low-wealth / high-MPC agents, (ii) amplifies the $\mathcal Q^w$ concentration penalty in the $u'(c_{ss})$-weighted identity (v2 §2 derivation, still valid), and (iii) compresses AD amplification because a wider wealth distribution has a thinner right tail contributing to the AD feedback. This is the leading candidate for driving most of the remaining welfare gap — in either direction (towards QE or away from it).

**(H_asset)** The one-line asset-update fix (BUG-031). The Reduced_Run MC diagnostic (see `Code/HA-Models/FromPandemicCode/analyze_welfare_gap.py`) attributed ~1.5–1.7 % of ΔW₆ in UI scenarios to this directly. Small contribution confirmed.

**(H_ς)** The +6 % ς shift (0.2461 → 0.2609). v2 framed this as the primary driver; given the scale (6 %) and the structural role of ς in `c = (1-ς)cFunc(m) + ς·y`, it matters but is likely second-order to H_∇ now that we can see the Phase 2-prime shift. An upper bound on H_ς's contribution will emerge from the partially-completed v2 attribution runs if we ever want it, but it is no longer the primary question.

**Secondary:** any residual after (H_∇ + H_asset + H_ς) will point to either (i) AD-loop re-equilibration interacting with the new wealth distribution, or (ii) Jensen-type nonlinearities that the leading-order identity does not capture. The v1/v2 diagnostic showed cubic-term residuals up to ~67 % of |ΔW_6| at the *difference* level, so the leading-order decomposition is informative directionally but should not be expected to balance tightly.

## 4. The primary experiment

**Single run, not a 4-cell A/B/C/D.**

Run `run_hybrid_welfare6.py --baseline` with:

- splurge-in-budget asset update active (`HAFISCAL_SPLURGE_OLD` unset).
- a-indexed TM solver (default now).
- ς = 0.2609 (current).
- **(β, ∇) from Phase 2-prime a-TM re-estimation** via `HAFISCAL_DISCFAC_FILE=<path to Phase 2-prime DiscFacEstim_CRRA_2.0_R_1.01.txt>`.

This is literally the operational "next step" item in `BUGS_private/.../what-to-do.md` §"What we need operationally": *"Finish the a-indexed TM production run for Baseline CRRA2"* under the a-TM (β, ∇). The A/B/C/D attribution was a detour.

Output: `Tables/Baseline/welfare6.tex` and the matched multiplier rerun.

**Cost.** ~3 h MC welfare (per the just-killed Run B pace) + whatever TM multiplier cost (~7 h per `results.md` §"Status" note of 9h 29m total).

## 5. Interpretation matrix

Let $\mathcal W_6^{\text{UI, AD=1}}$ be the new UI welfare-6 under Phase 2-prime (β, ∇).

| Outcome | Interpretation | Follow-up |
|---|---|---|
| $\mathcal W_6^{\text{UI}} \geq 1.9$ | Most of the welfare gap vs QE closes once β/∇ are jointly consistent with a-TM. H_∇ confirmed as dominant; Phase 6 current understates welfare because it uses a stale calibration. | Regenerate sensitivity parametrizations under Phase 2-prime (β, ∇); revise paper tables. |
| $1.5 \leq \mathcal W_6^{\text{UI}} < 1.9$ | Modest narrowing; H_∇ contributes but is not dominant. | Add a targeted diagnostic: compute $\mathcal Q^w$ per education group to localize which group drives the residual. |
| $\mathcal W_6^{\text{UI}} \approx 1.36$ | Phase 2-prime β/∇ barely move welfare. H_∇ rejected as dominant; the gap is genuinely stable at the bugfix calibration. | Accept the Phase 6 numbers as the bugfix endpoint for Baseline CRRA2 and proceed to what-to-do.md §options (a)/(b)/(c). |
| $\mathcal W_6^{\text{UI}} < 1.3$ | The widened ∇ pushes welfare *further* from QE. | Investigate whether Phase 2-prime β/∇ needs re-examination (target fit? local minimum?) before accepting as the bugfix calibration. |

The 1.9 / 1.5 / 1.3 thresholds are calibrated to the half-way and three-quarter points of the QE→Phase-6 interval (1.36 ↔ 2.13).

## 6. Secondary experiments (conditional)

Run only if §4 leaves a meaningful residual to explain:

- **H_asset isolation at Baseline scope.** Repeat the Reduced_Run MC diagnostic at Baseline 21-type to confirm the ~1.7 % attribution holds at full scope.
- **Per-education $\mathcal Q^w$ decomposition.** Extend `analyze_welfare_gap.py` to emit $\mathcal Q^w$ contribution by education group. If HS / college ∇-widening is the driver, $\mathcal Q^w$ should load almost entirely on those two groups post-Phase-2-prime.
- **Steady-state moment check.** Re-measure K/Y and aggregate MPC under Phase 2-prime (β, ∇) to confirm they still hit SCF targets (6.60 and 0.51). Large ∇ shifts with unchanged central β *should* preserve cohort-weighted K/Y but this is worth verifying, per `results.md` §5 flag.

## 7. Why v2's A/B/C/D is abandoned

- v2 Run C (ς=0.318, current β/∇) uses a ς value that is not the QE published value (the QE value is 0.2461, not 0.318 — v2's number came from a misreading of an earlier intermediate ς). So Run C did not actually probe "ς rollback to QE".
- v2 Run D (ς=0.318, pre-splurge-in-budget β/∇) re-runs essentially the QE configuration. Outcome is known: it reproduces QE. No new information.
- Under the bugfix, ς and (β, ∇) are jointly estimated; pairing splurge-in-budget ς=0.2609 with QE (β, ∇) — or QE ς=0.2461 with Phase-2 (β, ∇) — are off-manifold in parameter space. The welfare numbers from such pairings are not economically meaningful.
- The operational question is whether Phase 2-prime (β, ∇) moves welfare. v2's design did not test that.

## 8. Deliverables

1. **Baseline welfare6 + Multiplier under Phase 2-prime (β, ∇).** Primary experiment per §4. Main output: Tables/Baseline/welfare6.tex and Multiplier.tex with the jointly-consistent a-TM calibration.
2. **Short addendum to `results.md` §7** reporting the new numbers alongside QE and current Phase 6. This is what `what-to-do.md` calls for.
3. **Conditional on §5 interpretation.** Either (a) accept Phase 6 + Phase 2-prime numbers as the bugfix endpoint and move to sensitivity parametrizations, or (b) investigate the Phase 2-prime calibration further if the welfare numbers move in an unexpected direction.

No attribution table is required for the headline result. The per-channel decomposition has diagnostic value for the online appendix / erratum note but is not on the critical path.
