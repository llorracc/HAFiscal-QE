# Plan: BUG-034 + BUG-035 — combined CDC consistency cleanup (Step-2 aggregator + Step-1 agent dynamics), re-anchor, merge to feature branch

**Date:** 2026-04-26 (combined-scope revision after BUG-035 reframing in commit `574c113f`; original plan was BUG-034-only)
**Status:** Planned
**Working branch:** `bug034-035-cdc-consistency-cleanup` (created off `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` HEAD at kickoff). Merges back to `_TM-vs-MC` after sign-off; from there merges into `feature/cdc-esc-configurable` per Step 6.
**Approach:** unilateral cleanup (no coauthor pre-coordination); audit-then-fix (whole-codebase audit before any fix); cost-tier gating from smallest-runnable-version up; both fixes packaged together so the expensive re-anchor cycle runs once with both fixes baked in.

**Combined scope:**
- **BUG-034** — Step-2 wealth-aggregation surface inconsistency in `EstimAggFiscalMAIN.py`. Drop the stale `(1-ς)` factor at 11 sites (10 `aLvl` + 1 `aNrm`) so the aggregator matches the CDC household-total semantics that `state_now["aLvl"]` already has under the BUG-031 patch on `AggFiscalType`.
- **BUG-035** — Step-1 agent state evolution not following CDC dynamics in `Estimation_BetaNablaSplurge.py`. Install a `CDCKinkedRConsumerType` subclass with a `get_poststates` override (parallel to `AggFiscalType`'s BUG-031 patch) so Step-1's simulator runs CDC household-rule dynamics period-to-period, not just produces a CDC-transformed cross-section.

The two bugs are addressed together because (i) they share the same upstream cause (BUG-031's incomplete extension across the pipeline), (ii) Step-1's ς feeds into Step-2's β/∇ estimation — sequential fixing would require two re-anchors, combined fixing requires one, and (iii) the re-anchor cost (~3-5 hr) dominates the per-fix code work (~30 min each).

**Related:**
- `plans/20260425-2102h_cdc-implementation-map.md` — implementation map (row 32.2 caught Step-1's lottery-MPC analog but missed both Step-1's agent type AND Step-2's aggregator)
- `plans/20260425-2137h_cdc-esc-configurable-refactor.md` — CDC↔ESC refactor (Phase B parameterization scope must extend to cover both BUG-034's Step-2 sites and BUG-035's Step-1 agent dispatch; this plan establishes the new post-cleanup CDC baseline against which Stage 1 must reproduce)
- `BUGS_private/HAFiscal_BUG-031_splurge_not_in_budget.md` — common upstream cause (CDC `get_poststates` patch installed on `AggFiscalType` but missed extension to Step-1's agent type and to Step-2's aggregator)
- `BUGS_private/HAFiscal_BUG-032_lottery_splurge_formula.md` — sibling fix to Step-1's lottery-MPC formula and cross-sectional wealth aggregation (`_lottery_consumption_under_cdc` + `_wealth_under_cdc`); this plan completes Step-1 by also fixing dynamics
- `BUGS_private/HAFiscal_BUG-034_step2_wealth_aggregation_inconsistency.md` — BUG-034 dossier
- `BUGS_private/HAFiscal_BUG-035_step1_agent_state_dynamics_not_cdc.md` — BUG-035 dossier
- `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md` §5.4 — formal CDC↔ESC wealth-aggregation specification

## 1. Background — what's broken

`Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py` (Step-2 of the calibration pipeline; estimates β/∇ per education group to match SCF wealth + MPC moments) computes wealth as:

```python
(1 - ThisType.Splurge) * ThisType.state_now["aLvl"]
```

at **11 call sites** (lines 112, 126, 134, 164, 170, 192, 276, 284, 404, 417, 420).

Per `models_CDC_and_ESC.md` §5.4 and the implementation map row 32.2, this is the **ESC formula** (`(1-ς) · aLvl_optimizer_per_capita = aLvl_household_total`).

But the production code uses the **CDC `get_poststates` patch** (BUG-031 fix) which makes `state_now["aLvl"]` already equal household-total assets. Multiplying by `(1-ς)` again then produces `(1-ς) · aLvl_household_total` ≈ 74% of household-total — a quantity with no clean economic interpretation.

The upshot: the β/∇ estimates currently in `Results/DiscFacEstim_CRRA_2.0_R_1.01_edType*.txt` were fit by matching this `(1-ς)`-shrunk model wealth distribution against SCF data that represents unshrunk household-total wealth. The optimizer compensated by adjusting β/∇.

The implementation map row 32.2 caught this pattern in `Estimation_BetaNablaSplurge.py` (Step-1) and the prep work extracted `_wealth_under_cdc` to package the CDC formula. Step-2 was missed entirely.

## 2. Why this matters now

Three converging consequences:

1. **The current CDC β/∇ estimates are stale** (calibrated against a wrong target). They "work" in that downstream multipliers and welfare cells come out reasonable, but they're not what CDC-correct estimation would produce.
2. **The CDC anchor `reproduce-20260425-comp-full-tm-only` is built on these stale estimates.** Multipliers and welfare cells in the anchor reflect the bug.
3. **The CDC↔ESC plan's Phase B parameterization scope is incomplete.** Phase B currently parameterizes only `Estimation_BetaNablaSplurge.py`. Step-2's `EstimAggFiscalMAIN.py` needs the same treatment. Until BUG-034 is fixed, the CDC↔ESC refactor would be propagating the bug into both interpretations (CDC keeps its current stale baseline; ESC inherits the same wrong aggregator).

The CDC↔ESC refactor work on `feature/cdc-esc-configurable` should pause until this fix lands and a new anchor is established.

## 3. Plan structure

Six steps, in order. The working branch `bug034-step2-wealth-aggregator-fix` is created at the start of Step 1 and merged back to `_TM-vs-MC` after Step 4 signs off.

### Step 1 — Codebase audit + BUG-034 documentation

#### 1.1 Whole-codebase audit (audit-then-fix discipline)

Two known bugs are in scope before the audit begins:
- BUG-034's 11 sites in `EstimAggFiscalMAIN.py` (10 `aLvl` + 1 `aNrm`)
- BUG-035's missing `get_poststates` override on Step-1's `KinkedRconsumerType` agent in `Estimation_BetaNablaSplurge.py`

The audit's purpose is to confirm these two bugs are the only manifestations of the BUG-031 incomplete-extension pattern, and to surface any OTHER missed sites (welfare-6 computation, multiplier post-processing, other downstream consumers of `state_now["aLvl"]` that may have analogous inconsistencies under CDC).

Audit method:
```bash
# Pattern 1: literal (1-Splurge)*aLvl style
grep -rn -E '\(1\s*-\s*[A-Za-z_.]*[Ss]plurge[A-Za-z_.]*\)\s*\*\s*[A-Za-z_.]*aLvl' Code/

# Pattern 2: same with aNrm
grep -rn -E '\(1\s*-\s*[A-Za-z_.]*[Ss]plurge[A-Za-z_.]*\)\s*\*\s*[A-Za-z_.]*aNrm' Code/

# Pattern 3: catch (1 - X.Splurge) variants
grep -rn -E '\(1\s*-\s*[A-Za-z]+\.Splurge\)' Code/

# Pattern 4: any aLvl/aNrm scaling by Splurge (broader)
grep -rn -E '[Ss]plurge.*\*.*a[LN](vl|rm)|a[LN](vl|rm).*\*.*[Ss]plurge' Code/
```

Output: a written audit report listing all matches with one-line classification per site:
- `BUG-034 (CDC fix needed)` — Step-2 aggregator pattern (drop the (1-ς) factor)
- `BUG-035 (CDC fix needed)` — Step-1 agent type missing CDC `get_poststates` override (located via structural audit, not the syntactic grep)
- `MPC aggregator (correct under both)` — annualization formulas like `Splurge + (1-Splurge)*MPC_Q` (already known-correct)
- `Lottery-MPC formula (already fixed in prep)` — the `_lottery_consumption_under_cdc` style sites
- `Other (investigate)` — any unexpected match needing case-by-case judgment; surfaces NEW potential bugs not yet documented

The audit report is committed as `BUGS_private/HAFiscal_BUG-034+035_cdc_consistency_audit.md` (a sibling to the BUG-034 and BUG-035 dossiers).

#### 1.2 BUG-034 + BUG-035 dossiers

Both dossiers already exist (filed in commits `528ac9d1` for the original framing and `574c113f` for BUG-035's reframing). This step verifies the dossiers' "Affected sites" and "Fix" sections are still current after the audit (Step 1.1) — and updates them if the audit surfaced new sites or changed the recommended fix.

Update `BUGS_private/HARK+HAFiscal_TM_vs_MC_bug_index.md`:
- Update the "Last updated" header to note the combined fix is in flight.
- Confirm BUG-034 and BUG-035 row entries reflect the combined-plan structure.

Also update the implementation map (`plans/20260425-2102h_cdc-implementation-map.md`):
- Add new rows (32.6 and 32.7, or as appropriate) for the Step-2 `EstimAggFiscalMAIN.py` wealth-aggregation sites (BUG-034) and the Step-1 `Estimation_BetaNablaSplurge.py` agent dispatch (BUG-035).
- Note that the prep work missed both sites and the CDC↔ESC refactor's Phase B must extend to cover both (see Step 6).

#### 1.3 Logging infrastructure for this bug-fix work

The CDC↔ESC refactor's logging helpers (`reproduce/cdc_esc_log.sh`, `cdc_esc_status.sh`, `cdc_esc_heartbeat.sh`) live on `feature/cdc-esc-configurable` and are not present on this branch. Re-create them here as `reproduce/bug034_log.sh`, `reproduce/bug034_status.sh`, `reproduce/bug034_heartbeat.sh` — same logic and format, just renamed so they coexist cleanly when this branch eventually merges into the feature branch.

The status file becomes `reproduce/logs/bug034-status.json` (gitignored). The main log becomes `reproduce/logs/bug034-fix.log` (already gitignored by `*.log`).

Monitoring commands for the user (during the Tier-3/4 long runs of Step 3):
```bash
tail -f reproduce/logs/bug034-fix.log
tail -f reproduce/logs/bug034-fix.log | grep --color=always -E '\[HALT \]|\[FAIL \]|\[BG   \]|\[DONE \]'
cat reproduce/logs/bug034-status.json | python -m json.tool
```

### Step 2 — Fix the bugs in code (two commits)

Two separate commits, one per bug, so each fix is independently revertable and reviewable. Both land before Step 3's re-anchor cycle so the new estimates reflect both fixes simultaneously.

#### Step 2a — BUG-034 fix (Step-2 aggregator)

Edit `Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py` (and any other Step-2 sites surfaced by Step 1.1's audit):

- **The 10 `aLvl` wealth-aggregation sites** (lines 112, 134, 164, 170, 192, 276, 284, 404, 417, 420): replace `(1-ThisType.Splurge)*ThisType.state_now["aLvl"]` with `ThisType.state_now["aLvl"]`.
- **The 1 `aNrm` wealth-aggregation site** (line 126): apply the SAME treatment — replace `(1-ThisType.Splurge)*ThisType.state_now['aNrm']` with `ThisType.state_now['aNrm']`. The reasoning is identical: under CDC, `aNrm = aLvl/pLvl` and `aLvl` is already household-total post-`get_poststates`, so `aNrm` is already the household-normalized quantity. The `(1-ς)` factor is the same ESC-direction artifact and gets dropped the same way.
- Add a `# CDC-MOD-BUG034: Step-2 wealth aggregation. ESC version: keep the (1-ς) factor (multiplied against ESC's optimizer-per-capita aLvl). See plans/20260425-2102h_cdc-implementation-map.md row [new].` marker at one of the sites (the others can be flagged with shorter `# CDC-MOD-BUG034` references).
- Document in the commit message: this fix changes the model's wealth aggregator under CDC, which will change the β/∇ that Step-2 estimates to match SCF moments.

The MPC-aggregation sites (lines 231, 239, 290, 301) are NOT the bug — those compute annualized household MPC from quarterly Optimizer MPC and are correct under both interpretations. Leave them alone.

**Commit:** one focused commit, "BUG-034 fix: Step-2 wealth aggregation drops (1-ς) factor under CDC". Push.

#### Step 2b — BUG-035 fix (Step-1 agent dynamics)

Edit `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py` (and any sibling helper module):

- **Add `CDCKinkedRConsumerType` subclass** with a CDC `get_poststates` override (~15 lines). Per the BUG-035 dossier §5:

  ```python
  class CDCKinkedRConsumerType(KinkedRconsumerType):
      """KinkedR consumer with CDC household-bargain asset rule (BUG-035 fix)."""
      def get_poststates(self):
          cNrm = self.controls['cNrm']
          TranShk = self.shocks['TranShk']
          cNrm_household = (1 - self.Splurge) * cNrm + self.Splurge * TranShk
          self.state_now['aNrm'] = self.state_now['mNrm'] - cNrm_household
          self.state_now['aLvl'] = self.state_now['aNrm'] * self.state_now['pLvl']
  ```
- **Replace `BaseType = KinkedRconsumerType(...)` with `BaseType = CDCKinkedRConsumerType(...)`** in the BaseType setup (around line 660).
- **Set `BaseType.Splurge = SplurgeEstimate`** at the top of `FagerengObjFunc` so each candidate ς in the optimizer's search is reflected in the simulator's dynamics, not just in the post-hoc `_wealth_under_cdc` transformation.
- **Add `# CDC-MOD-BUG035` marker** at the new subclass and at the `BaseType.Splurge = ...` line.
- **Optional but recommended:** simplify `_wealth_under_cdc` to either (a) be an algebraic identity (`return agent.state_now["aLvl"]`) since the simulator now produces CDC household-total directly, or (b) retain the formula as a runtime sanity check that asserts `aLvl_HARK − ς·pLvl·(TranShk − cNrm) ≈ aLvl` post-fix.

**Commit:** one focused commit, "BUG-035 fix: install CDCKinkedRConsumerType for Step-1 simulator CDC dynamics". Push.

#### Step 2c — Pin-test housekeeping (one commit)

Mark `test_cdc_simulation_pin` in `Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py` as `@pytest.mark.skip(reason="pending BUG-034+035 re-anchor; new pin values captured in Step 4")` so it doesn't fail in the gap between Step 2 and Step 4. The hash-based pin tests (`test_cdc_calibration_file_unchanged`) WILL fail after Step 3 produces new estimation files — that's expected; Step 4 re-pins them.

**Commit:** one focused commit, "test_cdc_baseline_pin: skip simulation pin pending BUG-034+035 re-anchor". Push.

### Step 3 — Re-anchor at four tiers (sequentially gated, smallest first)

The combined fix (BUG-034 aggregator + BUG-035 dynamics) invalidates the existing β/∇/ς estimates and the existing CDC anchor. To produce a new canonical CDC baseline that reflects BOTH fixes, re-run the calibration + reproduction pipeline at strictly-increasing scales. **Do NOT begin tier T+1 until tier T has signed off cleanly.** Each tier produces benchmark results that will be useful for the CDC↔ESC refactor's validation later.

Each tier validates BOTH fixes simultaneously: ς from Step-1 (now under CDC dynamics per BUG-035) and per-cohort β/∇ from Step-2 (now using CDC-correct aggregator per BUG-034). Sign-off requires both Step-1 and Step-2 outputs to be sane.

**Tier 1 — sanity (~minutes; no estimation; verify code still runs):**

- `./reproduce.sh --comp nano` — confirm pipeline still loads + creates agents (no estimation invoked at this scope; mostly tests that imports + `Parameters.return_parameters` survive the bug-fix code change).
- `pytest test_cdc_baseline_pin.py` — note: `test_cdc_simulation_pin` is skipped (per Step 2 marking); the four `test_cdc_calibration_file_unchanged` tests will still pass at this point because Step 3 hasn't re-estimated anything yet — they fail only once Step 3 Tier 4 lands and produces new calibration files.
- Tier 1 sign-off: nano exits 0; pytest produces no NEW failures.

**Tier 2 — single-type GLP-style smallest-runnable estimation (~tens of minutes):**

The smallest version of Step-2 that exercises the fixed wealth aggregator end-to-end. Two viable parametrizations:

- **`HS_Only`** (1 cohort = HS, 1500 agents, 1 β atom): the cleanest "GLP-style" Step-2 because it skips the multi-cohort outer loop entirely. Step-2's per-cohort β/∇ search runs once for HS only.
- **`Smoke_Test`** (3 cohorts, 100 agents each, 1 β atom): faster but tiny sample → moments are noisy; less informative for "did the fix work qualitatively?"

Recommendation: **use `HS_Only`** as the GLP-tier check. Cleanest interpretation of results.

```bash
HAFISCAL_PARAMETRIZATION=HS_Only python Code/HA-Models/do_all.py
```
(or whichever entry-point cleanly invokes Step-1 + Step-2 + Step-5 at HS_Only scope; if the existing `do_all.py` doesn't honor `HAFISCAL_PARAMETRIZATION`, write a small `do_all_HS_Only.py` wrapper analogous to the existing `do_all_reduced.py`).

Document the resulting β/∇ for HS and compare against the current HS estimate (`DiscFacEstim_CRRA_2.0_R_1.01_edType1.txt`). Expected outcome: β shifts modestly (the fix changes the wealth target by 1/(1-ς) ≈ 1.35×, so the optimizer compensates).

Tier 2 sign-off:
- The estimation completes (no numerical instability, no boundary-constraint hits).
- The shift in β is in a plausible range (~1-10%).
- A `--comp micro` or `--comp mini` reproduction at HS_Only scope produces sane multipliers (within ±20% of the existing HS-cohort multipliers).

If Tier 2 produces unreasonable numbers (β at boundary, multipliers wildly off), **HALT**. Investigate before committing to Tier 3.

**Tier 3 — Reduced_Run estimation + mini reproduction (~few hours):**

- Run estimation at Reduced_Run scope (3 cohorts × 1 β atom = 3 types, 5000 agents):
  ```bash
  HAFISCAL_PARAMETRIZATION=Reduced_Run python Code/HA-Models/do_all.py
  ```
  (or use the existing `do_all_reduced.py`; estimation should take minutes for Step-1 + tens of minutes for Step-2).
- Compare resulting β/∇ vs the pre-fix Reduced_Run estimates (if any). Document the percentage shift in each cohort's β.
- Run `./reproduce.sh --comp mini` (which uses Reduced_Run params for Step-5). Compare multipliers + welfare vs the pre-fix mini outputs.
- Tier 3 sign-off: estimation completes, mini reproduction produces sane multipliers, β shifts qualitatively consistent with Tier 2's HS-only direction.
- If Tier 3 produces unexpected results (β shifts much LARGER than HS-only would predict, or shifts in opposite direction), **HALT**. Investigate.

**Tier 4 — full Baseline estimation + full --tm-only anchor (~48-50 hours):**

- Run the full estimation pipeline:
  ```bash
  python Code/HA-Models/do_all.py    # default = Baseline scope
  ```
  This re-estimates Step-1 (~30 min) and Step-2 (~48 hr) under the fixed wealth aggregator. Outputs new `Result_AllTarget.txt` (Step-1 ς, expected to be very similar) and new `Results/DiscFacEstim_CRRA_2.0_R_1.01_edType*.txt` (Step-2 β/∇, expected to shift meaningfully).
- After estimation completes, run `./reproduce.sh --comp full --tm-only --auto-commit` to produce the new TM-only anchor on the fixed code + fixed estimates. Wall: ~25 min beyond the estimation.
- Compare resulting multipliers + welfare-6 cells vs the pre-fix anchor (`reproduce-20260425-comp-full-tm-only`). Document the deltas in the new anchor's commit message, attributing per-bug shifts where possible.
- The output is anchored as `reproduce-<date>-comp-full-tm-only-BUG034+035-fixed`.

Total tier-4 wall: ~3-5 hours of compute (per Apr-26 timing measurements; the originally-declared 48-hour figure in `do_all.py` is stale), mostly background. Use the `reproduce/bug034_*.sh` logging helpers (created in Step 1.3) and a heartbeat that polls Step-2's progress (`EstimAggFiscalMAIN.py` writes per-cohort iteration logs that the heartbeat can parse).

### Step 4 — Update CDC pin test

After Tier-3 lands, the pinned values in `Code/HA-Models/FromPandemicCode/test_cdc_baseline_pin.py` will be stale.

- Capture the new pin values from the Tier-3 production run (specific aLvl/aNrm values at chosen pin points).
- Update `test_cdc_baseline_pin.py` with the new values.
- Update the test's docstring to note the values reflect the post-BUG-034-fix calibration.
- Commit: "BUG-034 follow-up: update CDC pin test to post-fix calibration values."

### Step 5 — Merge fixes + new anchor + new estimates back to `_TM-vs-MC`

After all of the above lands on `bug034-035-cdc-consistency-cleanup`:

```bash
git checkout 0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC
git pull
git merge bug034-035-cdc-consistency-cleanup
git push origin 0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC
git push origin reproduce-<date>-comp-full-tm-only-BUG034+035-fixed
# Optional: delete the bug-fix branch since its content is now on _TM-vs-MC
git branch -d bug034-035-cdc-consistency-cleanup
git push origin --delete bug034-035-cdc-consistency-cleanup
```

### Step 6 — Merge into feature branch + expand CDC↔ESC plan

```bash
git checkout feature/cdc-esc-configurable
git pull
git merge 0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC
git push origin feature/cdc-esc-configurable
```

The feature branch now has:
- The BUG-034 fix
- The new β/∇ estimates and Result_AllTarget.txt
- The new TM-only anchor
- The new CDC pin test values
- (Plus: the cdc_esc_*.sh and bug034_*.sh helpers coexist cleanly under different names)

The CDC↔ESC refactor on the feature branch resumes against this new state:

- **Phase A is unaffected** by the BUG-034 fix because the fix is in `EstimAggFiscalMAIN.py` and Phase A only touched `AggFiscalModel.py`. Phase A's tier-1 evidence (CDC pin test) will pass against the new state because Step 4 of this plan re-pinned the test.
- **The pre-Stage-1 commit reference** (currently `a3ba1221` in `plans/20260425-2137h_cdc-esc-configurable-refactor.md`) needs updating after the merge. The new pre-Stage-1 commit is the merge commit itself; update the placeholder accordingly. Phase A's additive-only invariant continues to hold.
- **Phase B's scope must be expanded.** Add a Phase B' to `plans/20260425-2137h_cdc-esc-configurable-refactor.md` that parameterizes `EstimAggFiscalMAIN.py`'s wealth aggregator analogously to Step-1's (an `_wealth_under_cdc` helper on Step-2 paralleling Step-1's, plus an `_wealth_under_esc` sibling for the future ESC code path that keeps the (1-ς) factor against ESC's optimizer-per-capita aLvl, plus interpretation dispatch at the now-fixed sites).
- **The Phase F MC welfare-6 anchor** is unchanged by this plan — but the existing retroactive Apr-21 MC anchor (`reproduce-20260421-comp-full-mc-only-retroactive`) becomes "pre-BUG-034" and needs explicit annotation in its manifest's `provenance_caveats`. Phase F's tier-4 ESC anchor run will be done against post-BUG-034 code and will produce the canonical post-fix MC welfare numbers.

After all of this, the CDC↔ESC refactor resumes from Phase A as already landed; Phase B and B' work proper begin on a clean foundation.

## 4. Estimated total effort

| Step | Effort | Notes |
|---|---|---|
| 1.1 — Codebase audit | ~30 min | Run grep patterns + structural audit, classify matches, write audit report |
| 1.2 — Index + map updates (dossiers already filed) | ~30 min | Mechanical updates |
| 1.3 — bug034_*.sh helpers | ~15 min | Copy + rename from cdc_esc_* equivalents |
| 2a — BUG-034 fix (Step-2 aggregator: 11 sites + markers) | ~30 min | Tiny diff |
| 2b — BUG-035 fix (Step-1 CDCKinkedRConsumerType subclass + wiring) | ~30 min | New ~15-line class + 2-3 line edits to BaseType setup |
| 2c — Pin-test skip housekeeping | ~10 min | Single-line decorator |
| 3 Tier 1 — sanity (nano + pin test) | ~10 min | Verify code runs after both fixes |
| 3 Tier 2 — HS_Only GLP-style estimation | (deferred per session decision; HS_Only invocation mechanism not directly available) | Skipped pending HS_Only entry-point work |
| 3 Tier 3 — Reduced_Run estimation + mini reproduction | ~2-4 hours | Background; validates both fixes; gates Tier 4 |
| 3 Tier 4 — Baseline estimation + full --tm-only anchor | ~3-5 hours | Background; the heavy lift; per Apr-26 measured timing (the do_all.py 48-hour figure is stale post-NM-in-place speedups) |
| 4 — Update CDC pin test | ~30 min | After Tier 4 produces new pin values |
| 5 — Merge bug-fix branch → `_TM-vs-MC` + push tag | ~15 min | Mechanical |
| 6 — Merge `_TM-vs-MC` → `feature/cdc-esc-configurable` + update CDC↔ESC plan | ~30 min | Mechanical + adds Phase B' (covers BOTH BUG-034 and BUG-035 sites) |
| **Total** | **~5-9 hours of mostly-background compute + ~3-4 hours of focused work** | Single re-anchor cycle covers both fixes. |

The wall-clock is dominated by Tier 4 (Step-1 + Step-2 estimation, ~3-5 hr per Apr-26 measurements). Sequential bug-fixing would require this re-anchor twice (~6-10 hr); combining halves it.

The sequential gating between tiers means a HALT at any tier saves all later compute. If Tier 3 (Reduced_Run, ~2-4 hr) reveals a fix-related bug, you've spent ~hours discovering it instead of waiting longer for Tier 4 to fail.

## 5. Risk: what if the fix produces unreasonable numbers?

The fix changes the wealth target by a factor of 1/(1-ς) ≈ 1/0.74 ≈ 1.35. So Step-2 will be matching against wealth distributions that are ~35% larger than what it currently matches. Plausible outcomes:

- **β/∇ shift modestly** (most likely): the optimizer was already close to the right target, just compensating by a few percent on β. Fix produces marginally different β values, multipliers shift by 1-5%, welfare cells by similar.
- **β/∇ shift dramatically** (less likely): the (1-ς) shrinkage was masking a deep mis-calibration; un-shrinking exposes it. Some β estimates may hit boundary constraints (GICmaxBetas or minBeta caps) and need configuration adjustment.
- **Numerical instability** (unlikely but possible): the optimizer fails to converge under the new target. Investigate root cause; may need to widen β grid, adjust starting values, etc.

Mitigation: the four-tier sequential gating provides progressively-deeper early warning:
- Tier 1 (~minutes) catches gross syntax / import errors.
- Tier 2 HS_Only (~30-60 min) catches numerical-instability and boundary-constraint issues with one cohort's worth of compute.
- Tier 3 Reduced_Run (~2-4 hr) catches multi-cohort interactions before committing to the full 21-type Baseline.
- Only after Tier 3 signs off cleanly do we commit to Tier 4's ~48-hour Baseline run.

If any tier produces unreasonable numbers, **HALT** and investigate before proceeding. This is the cost-tier hierarchy from `plans/20260425-2137h_cdc-esc-configurable-refactor.md` §1.5 applied to this bug fix.

## 6. What this plan does NOT include (deferred)

- **MC welfare-6 anchor under the fix.** The Apr-21 retroactive MC welfare-6 anchor (`reproduce-20260421-comp-full-mc-only-retroactive`) becomes stale once the new β/∇ land, but re-running it is another ~6-12 hours. Defer to the CDC↔ESC plan's Phase F (which handles MC welfare-6 anyway). The retroactive anchor's manifest should be annotated in Step 6 to add a `provenance_caveats` entry noting "pre-BUG-034 calibration; superseded by `<new-anchor>`".
- **ESC-direction analog of the fix.** Under ESC, the formula `(1-ς)*aLvl_optimizer_per_capita` IS correct. The CDC↔ESC refactor's Phase B' (added by Step 6 above) will introduce an `_wealth_under_esc` helper that keeps the formula and dispatches by interpretation. No standalone ESC fix needed.
- **Audit findings beyond known-bug pattern.** Step 1.1's audit may surface additional sites that warrant investigation but aren't the BUG-034 pattern (e.g., other splurge-related formulas in welfare6 / multiplier code). Such findings get logged in the audit report's "Other (investigate)" section but are NOT fixed as part of BUG-034 — they spawn separate bugs (BUG-036, BUG-037, ...) if the user decides to pursue them. (BUG-035 is reserved for a different already-identified deeper structural issue; see §6.5.)

## 6.5. Why both bugs are addressed in one plan

BUG-034 and BUG-035 are sibling cleanups of the same upstream omission (BUG-031's CDC `get_poststates` patch was installed on `AggFiscalType` but did not extend to (a) the Step-1 agent type or (b) the Step-2 wealth aggregator). Three reasons they're packaged together:

1. **Coupled effects on parameter estimates.** Step-1 outputs ς; Step-2 takes ς as given and outputs cohort β/∇. If BUG-035 changes Step-1's ς, then Step-2's BUG-034-fixed estimation uses the new ς. Sequential fixing would require Step-2 to be re-anchored twice (once after BUG-034, once after BUG-035 lands and shifts ς). Combined fixing requires one re-anchor with both ς and β/∇ updated together.
2. **Re-anchor cost dominates.** The expensive part is the Tier-4 estimation cycle (~3-5 hr). Doing it once with both fixes baked in costs the same as doing it once with only one fix.
3. **Single canonical anchor.** One tag (`reproduce-<date>-comp-full-tm-only-BUG034+035-fixed`) is cleaner provenance than two intermediate anchors with cross-references.

After both fixes land:
- Step-1 agents simulate CDC dynamics period-to-period (BUG-035 fix; via `CDCKinkedRConsumerType`).
- Step-1 cross-sectional wealth is CDC-correct (already via prep work's `_wealth_under_cdc`; becomes algebraic identity post-BUG-035).
- Step-2 simulator produces CDC household-total `aLvl` (already via BUG-031 patch on `AggFiscalType`).
- Step-2 wealth aggregator uses that CDC household-total directly (BUG-034 fix).
- No surface inconsistency remains under CDC. The cFunc is the outside planner's advice (correctly modeled by the standard buffer-stock Bellman) and the household consumes a weighted blend of advice and splurge — that's the CDC story end-to-end.

(Historical note: BUG-035 was originally filed in commit `528ac9d1` under an incorrect framing — "CDC cFunc solves wrong Bellman" — that implied a structural Bellman-modification fix. After coauthor clarification, BUG-035 was reframed in commit `574c113f` to the correct narrower Step-1 dynamics issue, fixable with a small `get_poststates` patch parallel to BUG-031's.)

## 7. Acceptance criteria for declaring BUG-034 + BUG-035 fixed

- Codebase audit (Step 1.1) report exists in `BUGS_private/HAFiscal_BUG-034+035_cdc_consistency_audit.md` with all matches classified; no unexpected new sites surfaced (or, if surfaced, escalation decision recorded).
- BUG-034 dossier and BUG-035 dossier both exist in `BUGS_private/` (already filed in commits `528ac9d1` / `574c113f`), indexed in the bug-index summary table.
- Implementation map rows added documenting both the Step-2 wealth-aggregation sites (BUG-034) and the Step-1 agent-dispatch site (BUG-035).
- All 11 wealth-aggregation sites in `EstimAggFiscalMAIN.py` (10 `aLvl` + 1 `aNrm`) updated with consistent CDC-only formula. CDC-MOD-BUG034 markers in place.
- `CDCKinkedRConsumerType` subclass exists in `Estimation_BetaNablaSplurge.py` (or sibling helper module); `BaseType` instantiated as `CDCKinkedRConsumerType`; `BaseType.Splurge` set in `FagerengObjFunc`. CDC-MOD-BUG035 markers in place.
- New anchor `reproduce-<date>-comp-full-tm-only-BUG034+035-fixed` exists on `_TM-vs-MC` with manifest + recipe + tag, all pushed.
- New `Result_AllTarget.txt` (post-BUG-035 ς, β, ∇) and `DiscFacEstim_*.txt` (post-BUG-034 cohort β, ∇) committed alongside the new anchor.
- CDC pin test updated with new pin values; both `test_cdc_calibration_file_unchanged` and `test_cdc_simulation_pin` pass on the new code state.
- `bug034_*.sh` logging helpers exist on `_TM-vs-MC` (separate from `cdc_esc_*.sh` on the feature branch).
- Working branch `bug034-035-cdc-consistency-cleanup` merged into `_TM-vs-MC` and deleted.
- Feature branch `feature/cdc-esc-configurable` has the merge from `_TM-vs-MC`; Phase A's evidence checks still pass on the merged state.
- CDC↔ESC plan updated:
  - Add Phase B' covering BOTH `EstimAggFiscalMAIN.py` parameterization (BUG-034 site) AND `CDCKinkedRConsumerType` agent dispatch in `Estimation_BetaNablaSplurge.py` (BUG-035 site).
  - Update the pre-Stage-1 commit reference (currently `a3ba1221`) to the new merge-into-feature commit.
  - Annotate Apr-21 MC anchor's manifest as pre-BUG-034+035 / superseded.
