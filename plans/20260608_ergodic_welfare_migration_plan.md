# Plan — Migrate the welfare experiment to the ergodic basis

**Decision (user, 2026-06-08):** move the published welfare to the **ergodic** initial
condition; treat the warm-start as the deliverable; **document the bridge so each step
between the old (cold) and new (ergodic) basis is navigable**; the goal is **validation**,
not magnitude; **cost is no object**.

---

## 0. The one finding that sets the scope

**β does NOT re-calibrate. The migration is the welfare experiment's init ONLY.**

| Pipeline step | Driver | MC init today | Ergodic already? |
|---|---|---|---|
| 1 — splurge ς | `Target_.../Estimation_BetaNablaSplurge.py` | cold init **but** sim settles (`T_sim=T_age*2`) | **yes** (confirm) |
| 2 — β estimation | `EstimAggFiscalMAIN.py` | cold init **but** sim settles (`T_sim=T_age*2`, Parameters.py:513) → Lorenz/median is the **stationary** cross-section | **yes** (confirm) |
| 3 — robustness (ς=0) | same as 2 | settles | **yes** |
| 4 — HANK/SAM | `HA-Fiscal-HANK-SAM.py` | TM/Jacobian, no MC | n/a |
| 5a — multipliers | `AggFiscalMAIN_reduced.py` | **TM-only** (`sim_method='TM'`); MC path defaults warm | **yes** |
| **5b — welfare-6** | `welfare6_scenario.py` | **COLD** — `make_history` runs `act_T=40`, starts a≈0 | **NO ← the only gap** |

The estimation **cold-starts but burns in `T_age*2` periods**, so its target cross-section is
the *stationary* (ergodic) wealth distribution — β is calibrated to the ergodic Lorenz. The
welfare experiment **cold-starts and does NOT burn in** (`act_T=40`), so it evaluates policy
on an a≈0 population the model's own calibration says shouldn't exist. **The published welfare
is internally inconsistent with its own β-calibration.** Moving welfare to ergodic *removes*
that inconsistency; it does not touch β.

→ **Step 1 of execution is to confirm this empirically** (estimation cross-section E[aNrm]≈0.31,
the ergodic) before anything else. If it somehow comes back cold, the scope expands to a β
re-estimation and this plan grows a calibration leg; I expect it will not.

## 1. Why the earlier ergodic effort didn't stick (investigation, 3 agents)

1. **Architectural isolation (root cause).** `welfare6_scenario.py` was created 2026-04-17
   (`26c012f9`) as a self-contained parallel runner mirroring `run_hybrid_welfare6.py` for
   bit-exact CRN. It **bypasses `Simulate.py`**, where the warm-start (`mc_use_tm_init`, added
   2026-03-23 `be9a8914`, default True) lives. The two paths never connected.
2. **The warm-start lowers welfare.** The ergodic init reduces welfare (~−0.07 pts at Baseline;
   `conclusions_private/2026-04-20_hark-017-can-reproduce-hafiscal-qe-bit-identical...md`
   attributes part of the QE→current "welfare drop" to `mc_use_tm_init`). Keeping welfare cold
   preserved the higher, QE-matching numbers.
3. **Deliberate opt-in.** When finally wired in (`ad9151e0`, 2026-06-08), it was opt-in,
   default off — "preserves the published cold-start." So it was a *decision*, not an oversight,
   but a decision made to protect QE-comparability, not on methodological grounds.

**Implication for "making it stick":** the blocker was never technical — it was (a) two code
paths and (b) a reluctance to move the published number. (a) is fixed by routing welfare
through the shared `tm_methods.initialize_mc_from_tm_ergodic`; (b) is exactly the decision the
user has now made. So "stick" = flip the default + lock it with a test + document the change.

## 2. Make it stick

1. **Default ON for welfare6 — the fix IS the default.** Flip `HAFISCAL_WELFARE6_TM_INIT` to
   `1` by default. This is an **error-fix** (BUG-052, a calibration inconsistency), so per the
   governance in §7 it is corrected by default, not left opt-in. The `=0` opt-OUT is the
   **toggle-off paper trail** — to isolate/measure the bug's per-cell effect — **NOT** a
   "reproduce QE" goal. (Keep the env name; invert the default.) Measure default already P.
2. **Regression test** (the lock): assert the welfare panel's t=0 `E[aNrm]` equals the TM
   ergodic (≈0.306, not 0.174), and assert it equals the β-estimation cross-section's E[aNrm].
   This test is the thing whose absence let the cold-start persist silently — it ties the
   welfare init to the calibration so they can't drift apart again.
3. **Single source of truth** — welfare6 and Simulate.py both call
   `tm_methods.initialize_mc_from_tm_ergodic` (done). No second copy.
4. **Document** (§4).

## 3. Validation (the point of the exercise, per the user)

Validation = the methods agree at the ergodic and the experiment is self-consistent — NOT
"how big is the change."

1. **Calibration consistency (the headline validation).** The welfare experiment's t=0
   cross-section must equal the β-estimation's stationary cross-section (same E[aNrm], same
   Lorenz). This is the property that was *violated* by the cold-start and is the real reason
   ergodic is correct. Assert it numerically.
2. **MC↔TM at the ergodic.** With the warm MC as a clean ergodic ground truth, re-test the
   bucketed-5D TM. The current **+0.95%** (warm MC 1.0196 vs bucketed-5D 1.0100) is now a
   *legitimate* method-gap to diagnose (grid A / 5-D joint / pLvl bucketing) — the cold-start
   no longer confounds it. (Separate workstream; the migration neither needs nor fixes it.)
3. **Drift.** Confirm the welfare panel does not drift from the ergodic (E[aNrm] flat ≈0.306
   across the panel — already observed) and report the 4-moment drift (mean/var log a, var log p)
   vs the TM-a benchmark per the standing rule.
4. **Multi-seed SE on every reported cell** — never a bias off one seed (the lesson from this
   session: the single-seed "warm=1.0098 closes it" was noise).
5. **TaxCut init-insensitivity** — confirm (not assume) taxcut cells move ≪ check cells under
   cold→ergodic; that's the validation that the change is concentrated where MPC matters.

## 4. The navigable bridge (documentation deliverable)

Goal: a reader can walk from the **old published (cold) calibration** to the **new (ergodic)**
one and attribute every number-move to a named step, reproducing any rung.

**Design — a rung ladder, each rung = a reproducible config (git ref + flags), each emits the
full welfare table:**

| Rung | Config | What it isolates |
|---|---|---|
| R0 | QE-published ref (`v2026-01-09-18-17`), cold | the published baseline |
| R1 | + post-QE BUG fixes (031/025-030), cold | code-correctness deltas (already decomposed in the 2026-04-20 doc — *reuse it*) |
| R2 | + production N, cold | finite-N effect |
| **R3** | **+ ergodic init (HAFISCAL_WELFARE6_TM_INIT=1), P-measure** | **the ergodic step — the new change** |
| R3a | R3 with Q-measure | shows measure is inert (≈0) — a validation rung, not a move |
| R4 | R3, multi-seed | the SE band around R3 |

- R0→R1→R2 already exist as the QE-comparison decomposition (`fe4bd3c7`, the 2026-04-20 doc);
  the migration **extends** that ladder with R3. Do not rebuild R0–R2; cite + reuse.
- Each rung is a row in a `welfare_bridge.csv`: {rung, git_ref, flags, N, seeds, per-cell welfare,
  Δ-from-previous-rung, validation note}. The Δ column is the navigation: it says exactly what
  each step cost.
- A `bridge.sh` driver runs each rung from its flag set so any rung is reproducible by config,
  not by memory. Flags are the existing `HAFISCAL_*` switches + the ergodic flag.
- Output doc: `conclusions_private/2026-06-XX_ergodic_welfare_bridge.md` — the ladder table +
  a one-paragraph interpretation per rung (per `procedure_qe_comparison_report`: open with the
  explicit QE-baseline and new-version characterization).

## 5. Execution order (cost no object)

1. **Confirm β/splurge are ergodic** (§0 step 1) — estimation cross-section E[aNrm]≈0.31. GATE.
2. Flip welfare6 default ON + add the consistency regression test (§2).
3. Run the **full welfare table cold + ergodic**, all non-AD + AD cells, all parametrizations
   (HS_Only → Reduced_Run → Baseline), multi-seed. (This is the magnitude — but produced *as*
   the bridge's R2→R3 rungs, framed as validation.)
4. Diagnose the +0.95% MC↔TM ergodic gap against the warm ground truth (separate; §3.2).
5. Assemble `welfare_bridge.csv` + the bridge doc (§4).
6. Decide whether the paper's headline adopts R3 (ergodic) with R0 (cold) documented as the
   QE-reproduction rung.

## 6. Open / watch

- **+0.95% MC↔TM gap** is real and independent — do not let the migration "close" it by accident
  or conflate it. It's a TM-method question, not an init question.
- **Matched-pair guard**: ergodic welfare must run on the β solved under the SAME regime
  (PermGroFac/interpretation). The warm-start uses the base solution, so this holds, but the
  regression test should assert regime match (assert_regime already does at run_experiment).
- If §0 step 1 surprises (β cold), STOP and re-scope — the migration then includes a β
  re-estimation leg and a much bigger bridge.

## 7. Governance — classify every result-moving change (user, 2026-06-08)

Every change that moves a published number is one of two kinds; handle them differently and
NEVER conflate (memory: `error-vs-sample-result-changes`):

- **(A) ERROR** — the earlier result was wrong (a bug). Fix becomes the **DEFAULT**; write a BUG
  report (paper trail); keep a **toggle-OFF** so the fix's effect is isolable/measurable; add it
  to the QE-divergence ledger. **"It matched QE" is never a reason to keep a wrong answer** —
  record that QE had the bug.
- **(B) SAMPLE / convergence** — too-small N, coarse grid, MC noise. Resolve by **larger N /
  finer grid / more seeds**. A precision improvement, not a toggle-able fix, not a bug.

Tell A from B with the multi-seed-SE rule: a bias surviving a multi-seed SE is real (A); one
that doesn't is noise (B).

**Classification of the bridge rungs (§4):**
| Rung | Kind | Handling |
|---|---|---|
| R1 BUG fixes (031, 025-030, 047, 051, **052**) | **A** | defaults; each toggle-off-able; in the ledger |
| R2 N-size | **B** | resolve by production N; not a toggle |
| **R3 ergodic init** | **A** (BUG-052) | default ON; cold opt-out = the isolation toggle |
| +0.95% MC↔TM gap | **TBD** | diagnose → A (TM-method error) or B (grid convergence) |

So the cold-start move is logged as **BUG-052**, defaulted on, toggle-off-able, and entered in
the QE-divergence ledger — not preserved to match QE.
