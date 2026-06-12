# CDC implementation map: every place the CDC interpretation is implemented in the codebase

**Date:** 2026-04-25
**Status:** Inventory complete (3 passes done); in-code markers pending.
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` (the live CDC implementation)
**ESC baseline:** `origin/maintain_bound_pair_fix_splurge`
**Plan it implements:** `plans/20260425-2058h_cdc-anchors-in-codebase.md`
**Convention:** every CDC-anchor location is to receive an in-code marker of the form `# CDC-MOD-BUG<NN>: <summary>. ESC version: <alt>. See plans/20260425-2102h_cdc-implementation-map.md.` Stable greppable token: `CDC-MOD-`.

## Classification key

- **(I)** — interpretive: an ESC-faithful version would do something different here.
- **(B)** — bug fix: would persist under any interpretation.
- **(I+B)** — both: original code was wrong under both readings; CDC and ESC would each fix it differently.
- **(?)** — pending coauthor judgment (default; populated after a review pass).

**Empirical observation after the discovery passes (revised 2026-04-25 after cross-checking against `origin/maintain_bound_pair_fix_splurge`):** the inventory splits into two groups —

- **3-4 truly interpretive anchor groups (I or I+B)** — these are where CDC and ESC actually do something different in code:
    - **31.5** `get_poststates` override — **(I)**. CDC adds an override; ESC uses HARK's default (which IS the ESC-1 rule). The original (master) code had no override and was correct under ESC, wrong under CDC.
    - **32.2** `_option_d_wealth` correction — **(I+B)**. Under both interpretations, the original `WealthNow = aLvl_hark` was wrong, but the fixes differ: CDC subtracts `ς·pLvl·(TranShk−cNrm)`, ESC multiplies by `(1−ς)`.
    - **32.5** lottery-MPC formula — **(I+B)**. Original splurge-on-increment formula was wrong under both; CDC manually tracks `m_base`/`a_base` because HARK's default asset rule is wrong under CDC, ESC uses `ThisType.controls["cNrm"]` directly because HARK's default IS the ESC rule.
    - **33.4-33.9** the `_a` TM kernel functions — **(I+B)**. Original m-indexed TM was wrong under both (loses ξ-variance per BUG-033); a-indexed kernel formulas differ — CDC has `(1−ς)·[ξ − cFunc(...)]`, ESC has `ξ − cFunc(...)`.

- **~18 supporting anchors (B)** — shared infrastructure that both interpretations need to operate the interpretive sites:
    - **31.1, 31.2** state-var / track-var declarations for `cLvl_splurge` — both interpretations need them under aggregator A.
    - **31.3, 31.4** the `cLvl_splurge = (1−ς)·cLvl + ς·pLvl·TranShk·ADF` formula itself — *value* is the same under both readings (only the interpretation of `cLvl = cFunc(m)·pLvl` differs); line is identical in CDC and ESC.
    - **31.6, 31.7, 31.8** Q-track wiring, mill_rule, history concat for `cLvl_splurge` — shared aggregator-A plumbing.
    - **32.1, 32.3, 32.4** `FagerengObjFunc` entry point + manual state-propagation infrastructure — supports the (I+B) interpretive sites but isn't interpretive itself.
    - **33.1, 33.2, 33.3** `tm_a_indexed` flag, `Simulate.py` dispatch, `mc_use_tm_init` compatibility check — interpretation-independent infrastructure for the a-indexed kernel switch.

**Implication for the configurable refactor:** only **3-4 substitution sites** need a runtime switch (the (I) and (I+B) groups above). The other 18 anchors stay identical between CDC and ESC code paths.

## Architecture decision (2026-04-25)

The future configurable code path that runs *either* CDC or ESC will use a **class-hierarchy** approach, not a runtime env-var flag.

- `AggFiscalType` becomes either an interpretation-agnostic base class with the interpretive methods abstract, OR remains as `CDCAggFiscalType(AggFiscalType)`.
- A new `ESCAggFiscalType(AggFiscalType)` (or sibling) overrides the interpretive methods (`get_poststates`, the `_a` kernel hook, etc.) with ESC-direction implementations.
- Non-class anchors (`Estimation_BetaNablaSplurge.py`, `Simulate.py` dispatch) take an `interpretation` parameter — a tag or a small policy object — that selects which agent class to instantiate and which estimation routines to call.
- Each interpretation is solved/simulated/tested in isolation; no `if interp == 'CDC'` branches scattered through code.

**Tradeoff accepted:** ~1-2 days of focused refactor to convert the current inline patches into method overrides; in exchange, the result is testable and clean rather than branchy.

**Alternative considered, rejected:** runtime env-var flag (`HAFISCAL_INTERPRETATION=CDC|ESC`). Faster to bootstrap but creates branchy code that's harder to test and harder to compare CDC↔ESC side-by-side in one process.

## How to use this map

For each anchor row: the file:line pinpoints the change in the live code, the *Summary* says what it does in CDC, the *ESC version* says what an ESC-faithful version would do (per `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md` §5 or per `origin/maintain_bound_pair_fix_splurge`), and *Source* points to the BUG dossier or doc that motivated the change.

Future ESC-revival work: the **(I)** rows are where a runtime switch is needed; **(I+B)** rows need both alternatives implemented; **(B)** rows stay as-is.

---

## Pass 1 — BUGS dossier walk (complete)

### From `BUGS_private/HAFiscal_BUG-031_splurge_not_in_budget.md`

Splurge-in-budget asset-update fix. Central CDC interpretive substitution.

| # | File:line | Class | Summary | ESC version | Source |
|---|---|---|---|---|---|
| 31.1 | `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:262` | (?) | `state_vars += ['cNrm', 'cLvl_splurge', 'cLvl']` — adds CDC bookkeeping state vars on `AggFiscalType` | ESC needs the same state vars under aggregator A; may not require `cNrm` separately | BUG-031 |
| 31.2 | `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:827` | (?) | `track_vars` augmented with `cLvl_splurge` for history tracking | Same — aggregator A is shared | BUG-031 |
| 31.3 | `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:1032` (`get_controls`) | (I) | Computes per-agent `cLvl_splurge = (1−ς)·cFunc(m)·p + ς·p·ξ·ADF` (CDC's weighted-average actual consumption, eq. CDC-1 RHS) | ESC: same formula but interpreted as Optimizer-mass-weighted Optimizer consumption + Splurger-mass-weighted Splurger consumption (per `models_CDC_and_ESC.md` §5.4); the *value* coincides — the *interpretation* of `cFunc(m)` differs (household-budget m vs Optimizer-per-capita m). The line itself can stay; only the surrounding interpretation/comments change. | BUG-031, `models_CDC_and_ESC.md` §4.3 |
| 31.4 | `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:1054-1055` | (I) | The actual `cLvl_splurge` formula line | (Same as 31.3 — same line, more granular) | BUG-031 |
| 31.5 | `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:1057` (`get_poststates` override) | (I+B) | **Central CDC patch.** Override of HARK's default `aNrm = mNrm − cNrm` with `aNrm = mNrm − cLvl_splurge / pLvl` (subtract realized weighted consumption per CDC-1) | ESC: `aNrm = mNrm − cNrm` (HARK default; subtracts only the Optimizer's `cFunc(m)` because under ESC's per-Optimizer normalization that *is* the Optimizer's whole consumption — the `ς·y` is the Splurger's separate ledger and never touches the Optimizer's a). Per `models_CDC_and_ESC.md` §5.2 (ESC-1). | BUG-031, `models_CDC_and_ESC.md` §4.2 + §5.2 |
| 31.6 | `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:1110-1119` | (?) | Q-track splurge handling (Harmenberg neutral measure track) | If ESC adopts the Q-track, will need an analogous derivation; Q-track itself is independent of CDC↔ESC | BUG-031 (downstream) |
| 31.7 | `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:1160` | (?) | `state_now_Q['cLvl_splurge']` — Q-track per-period write | Same as 31.6 | BUG-031 (downstream) |
| 31.8 | `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:1573, 1580, 1587, 1692, 1696, 1727` | (?) | Aggregator wiring for `cLvl_splurge` (mill_rule, history concatenation, AggCons sum) | ESC uses aggregator A (per `models_CDC_and_ESC.md` §3); the *value* of `cLvl_splurge` is the same household-total under either reading. These lines likely stay; flag for review. | BUG-031 (downstream) |

**Open question for 31.5:** the K/Y aggregator under CDC (Σ aLvl / Σ pLvl·TranShk, no `(1−ς)` factor) vs ESC ((1−ς)·Σ aLvl / Σ pLvl·TranShk per `models_CDC_and_ESC.md` §5.4). Per `models_CDC_and_ESC.md` §6 ("Side-by-side: the differences"), this *is* a CDC-vs-ESC difference. Need to find the actual K/Y aggregator location in code (not enumerated in BUG-031). Pass 3 candidate.

### From `BUGS_private/HAFiscal_BUG-032_lottery_splurge_formula.md`

Step-1 lottery $\varsigma$ re-estimation under canonical splurge-on-total-income formula.

| # | File:line | Class | Summary | ESC version | Source |
|---|---|---|---|---|---|
| 32.1 | `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py:173` (`FagerengObjFunc`) | (?) | Objective function entry point (not changed itself, but everything that follows in this function is the CDC re-estimation harness) | ESC would call its own version; structure same | BUG-032 |
| 32.2 | `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py:219-229` (`_option_d_wealth` correction in aLvl_hark) | (I+B) | Splurge-in-budget wealth correction: `aLvl_actual = aLvl_hark − ς·pLvl·(TranShk − cNrm)` to apply the splurge-in-budget asset rule retroactively to HARK's simulated wealth (so the K/Y / Lorenz fit uses post-splurge wealth) | ESC: under per-Optimizer accounting, HARK's `aLvl_hark` (= Optimizer's `aNrm·pLvl`) is the Optimizer-side asset; the household-total is `(1−ς)·aLvl_hark`. So an ESC version of this correction would multiply by `(1−ς)`, not subtract `ς·pLvl·(TranShk−cNrm)`. | BUG-032 + `models_CDC_and_ESC.md` §6 (K/Y aggregator row) |
| 32.3 | `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py:287` | (I+B) | `a_base = np.zeros((AgentCount, N_Quarter_Sim))` — explicit allocation for splurge-in-budget-tracked baseline assets (does not reuse HARK's internal state) | ESC: would still need an `a_base`-equivalent if it uses splurge-in-budget; but the formula at line 343 differs. | BUG-032 |
| 32.4 | `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py:304-322` | (I+B) | Manual state propagation skipping HARK's default — death reset, `R_kink` by sign of `a_prev`, then `m_base = a_base[period-1] * R_kink_base / psi + xi`; same logic for `m_lottery`. Avoids HARK's `a = m − cFunc(m)` rule. | ESC: would similarly need to skip HARK's default if it uses splurge-in-budget; the asset update formula differs. | BUG-032 |
| 32.5 | `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py:341-347` | (I) | **Central BUG-032 patch.** `c_base = (1−ς)·cFunc(m_base) + ς·xi`, `a_base = m_base − c_base`; `c_actu = (1−ς)·cFunc(m_lottery) + ς·(xi+L)`, `a_actu = m_lottery − c_actu`. CDC-direction: splurge applies to total income; baseline asset update follows splurge-in-budget. | ESC: lottery-MPC formula would be `c = (1−ς)·cFunc(m_opt) + ς·(per-Splurger income)` with m_opt = household m / (1−ς); the asset update is on the Optimizer's a, not household-total. Different formula even though structurally similar. | BUG-032 + `models_CDC_and_ESC.md` §5 |

### From `BUGS_private/HAFiscal_BUG-033_tm_a_indexed_refactor.md`

a-indexed TM kernel — the TM-side equivalent of BUG-031, needed because under splurge-in-budget post-consumption assets depend on realized $\xi$.

| # | File:line | Class | Summary | ESC version | Source |
|---|---|---|---|---|---|
| 33.1 | `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:277-278` | (I) | `self.tm_a_indexed = bool(kwds.get('tm_a_indexed', False))` — dispatch flag added to `AggFiscalType.__init__` | ESC: a-indexed kernel still applies (any splurge-in-budget interpretation needs it). But the formula INSIDE the kernel (`c = (1−ς)·cFunc(m) + ς·ξ` and `a = m − c`) is CDC-direction; ESC would need an analogous kernel built around the ESC asset rule. | BUG-033 |
| 33.2 | `Code/HA-Models/FromPandemicCode/Simulate.py:290-296` | (?) | Dispatch wiring: read `Run_Dict['tm_a_indexed']`, set on each agent, log via progress | Same dispatch needed for ESC; flag value is independent of CDC↔ESC | BUG-033 |
| 33.3 | `Code/HA-Models/FromPandemicCode/Simulate.py:343-353` | (?) | Error/check: `tm_a_indexed=True` requires `mc_use_tm_init=False` (or vice versa) | Same compatibility constraint regardless of interpretation | BUG-033 |
| 33.4 | `Code/HA-Models/FromPandemicCode/tm_methods.py:2696` (`_build_period_tm_a`) | (I) | Helper kernel: integrates over $\xi$ to produce a-to-a transition matrix using the CDC asset rule `g(a, ξ) = (R/Γ)·a + (1−ς)·[ξ − cFunc((R/Γ)·a + ξ)]` | ESC: `g(a, ξ)` would use ESC's per-Optimizer asset rule. Structurally similar; formula inside the kernel differs. | BUG-033 |
| 33.5 | `Code/HA-Models/FromPandemicCode/tm_methods.py:2912` (`build_tm_agg_fiscal_a`) | (I) | Baseline a-indexed TM builder | ESC analogue would call `_build_period_tm_a_esc` (TBD) | BUG-033 |
| 33.6 | `Code/HA-Models/FromPandemicCode/tm_methods.py:2968` (`compute_type_aggregates_tm_a`) | (I) | Type aggregator over a-indexed ergodic | Aggregator A is shared between CDC and ESC; the a-grid argument changes interpretation (CDC: $a_{tot}$; ESC: $a_{opt}$) | BUG-033 |
| 33.7 | `Code/HA-Models/FromPandemicCode/tm_methods.py:3082` (`compute_period_aggregates_tm_a`) | (I) | Per-period aggregator used in experiment loop | Same as 33.6 | BUG-033 |
| 33.8 | `Code/HA-Models/FromPandemicCode/tm_methods.py:3184` (`build_experiment_period_tm_a`) | (I) | Experiment-period builder (Cratio scaling, AD, scenario shocks) | ESC analogue with per-Optimizer accounting | BUG-033 |
| 33.9 | `Code/HA-Models/FromPandemicCode/tm_methods.py:3268` (`propagate_experiment_tm_a`) | (I) | Top-level experiment propagator wrapping the a-indexed path | ESC analogue | BUG-033 |

**Note on m-indexed TM functions** (`_build_period_tm`, `build_tm_agg_fiscal`, etc., at lines 435, 574, 724, 1400, 1581, 1708): these are the *legacy* m-indexed kernel that was the *original* implementation under both interpretations (pre-splurge-in-budget). They remain in the file as a parallel implementation. They are *not* CDC-MOD anchors — they pre-date the CDC↔ESC split. Per BUG-033, the m-indexed kernel collapses ξ-variance under any splurge-in-budget interpretation, so it's broken under either CDC or ESC; the a-indexed kernel is the splurge-in-budget-correct rewrite. The CDC anchors are *only* the new `_a` versions.

---

## Pass 2 — `models_CDC_and_ESC.md` §4.3 cross-ref (complete)

Of the 7 rows in §4.3:
- 4 are interpretation labels, not patches (`pLvl`, `TranShk*AggDemandFac`, `mNrm = bNrm+...`, `cNrm = cFunc(mNrm)`).
- `cLvl_splurge = ...` is anchor 31.4.
- `get_poststates` override is anchor 31.5.
- **K/Y aggregator `Σ aLvl / Σ (pLvl·TranShk)`** — not enumerated in any BUG dossier as a separate patch. Located during Pass 3 (see below): the K/Y *computation* is at `Estimation_BetaNablaSplurge.py:475` (`CapAggj = np.sum(EstTypeList[j].state_now["aLvl"])`) but the *interpretive choice* lives upstream at line 219-229 — where `aLvl` is corrected by `aLvl_hark - ς·pLvl·(TranShk - cNrm)` to apply the CDC splurge-in-budget asset rule. The K/Y sum at line 475 is not interpretive in itself; it's downstream of the CDC-corrected `aLvl`. So **K/Y is covered by anchor 32.2** (the splurge-in-budget wealth correction). The ESC version of K/Y would use uncorrected `aLvl_hark` and multiply by `(1−ς)` — substituting at line 219-229 is sufficient.

## Pass 3 — full diff pass (complete)

`git diff --stat origin/maintain_bound_pair_fix_splurge...HEAD -- Code/HA-Models/` shows 74 files changed (3272 insertions, 132 deletions). Most are *not* CDC anchors: diagnostic scripts (`diag_*.py`), validation harnesses (`validate_*.py`), tests (`test_*.py`), launch scripts, notebooks, docs, and the calibration `.txt` outputs. Per-file classification of the substantive code files:

| File | Change scope | CDC anchors? |
|---|---|---|
| `AggFiscalModel.py` | Already covered Pass 1: 8 anchors (31.1–31.8, 33.1) | ✓ |
| `tm_methods.py` | Already covered Pass 1: 6 anchors (33.4–33.9) | ✓ |
| `Estimation_BetaNablaSplurge.py` | Already covered Pass 1: 5 anchors (32.1–32.5) | ✓ |
| `Simulate.py` | Already covered Pass 1: 2 anchors (33.2, 33.3) | ✓ |
| `Welfare.py` | **Empty diff** — confirms `models_CDC_and_ESC.md` §3 claim that the welfare aggregator is shared between CDC and ESC | (none) ✓ |
| `Output_Results.py` | **Empty diff** — no CDC-direction reporting changes | (none) ✓ |
| `Parameters.py` | Diff is plans/ path-rename comments only; no CDC code logic. The CDC calibration is selected via the file pointers it loads (covered in §Calibration artifacts below). | (none in code; calibration via file-pointers) |
| `EstimAggFiscalMAIN.py` | 129-line diff is variance-reduction shuffle flags (`HAFISCAL_MC_SHUFFLE`, `HAFISCAL_INCOME_SHUFFLE`) and in-place NM iteration warm-start (`HAFISCAL_NM_IN_PLACE`). All performance/reproducibility infrastructure; no interpretive logic. | (none) |
| `do_all.py` | Step-skip env vars + Step 5 split into 5a/5b; orchestration. | (none) |
| `do_all_reduced.py` | New file — reduced-pipeline orchestrator. Calls into the same CDC anchor functions. | (none — calls anchored code) |
| `AggFiscalMAIN_reduced.py` | Reduced-pipeline entry point. | (none — invokes anchored code) |
| `run_welfare6_parallel.py`, `run_hybrid_welfare6.py`, `welfare6_scenario.py`, `compute_welfare6_*.py` | Welfare-6 reporting infrastructure; uses the shared aggregator A. | (none — uses anchored `cLvl_splurge`) |

Pass 3 yielded zero new CDC anchors beyond the Pass-1 inventory. **Total: 22 anchors across 4 files**.

---

## Reconciliation (complete)

All three passes converged on the same inventory of 22 anchors across 4 files:
- `Code/HA-Models/FromPandemicCode/AggFiscalModel.py` — 8 anchors (BUG-031 + BUG-033 dispatch flag)
- `Code/HA-Models/FromPandemicCode/tm_methods.py` — 6 anchors (BUG-033, the new `_a`-suffixed functions)
- `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py` — 5 anchors (BUG-032)
- `Code/HA-Models/FromPandemicCode/Simulate.py` — 2 anchors (BUG-033 dispatch + compatibility check)

No anchor appears in only one pass; high confidence on the inventory. The K/Y aggregator interpretive choice is covered by anchor 32.2 (Pass 2 cross-ref against `models_CDC_and_ESC.md` §6; verified in Pass 3 by tracing where `aLvl` gets corrected before the K/Y sum).

## In-code marker insertion (pending)

After reconciliation, insert `# CDC-MOD-BUG<NN>: <summary>. ESC: <alt>. See plans/20260425-2102h_cdc-implementation-map.md.` above each anchor.

The marker text is short (one line); the *full* rationale lives in this map and in the BUG dossiers.

## Validation (pending)

Final check:
- `grep -rn 'CDC-MOD-' Code/` — count should match the row count in this map (excluding the calibration-artifacts section which has no code anchors).
- For each anchor, the cited file:line should contain the marker on the line above the documented patch.
- Round-trip sanity: a hypothetical "revert all CDC-MOD- patches" exercise should produce a state approximately matching `origin/maintain_bound_pair_fix_splurge` (modulo HARK-upgrade fixes that are independent of CDC↔ESC).

---

## Calibration artifacts (CDC-calibrated outputs, not code anchors)

For completeness — these `.txt` files are *outputs* of the estimation pipeline and contain the CDC-calibrated parameter triples. They are not code anchors but are referenced by `Parameters.py`, so they need to be swappable when the future ESC-runnable path is built.

| File | Content | CDC value | ESC value (per `models_CDC_and_ESC.md` §7) |
|---|---|---|---|
| `Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt` | `{splurge, beta, nabla}` from Step 1 | `{0.2609, 0.9611, 0.0668}` | `{0.2672, 0.9715, 0.0589}` (on `origin/maintain_bound_pair_fix_splurge`) |
| `Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01.txt` | Per-education $(\bar\beta, \nabla)$ from Step 2 | CDC-fitted | ESC-fitted (on `origin/maintain_bound_pair_fix_splurge`) |
| `Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01_edType[012]*.txt` | Per-education sub-files | CDC-fitted | ESC-fitted |

The future ESC-runnable path will need a way to select which calibration set to use, e.g., a `HAFISCAL_INTERPRETATION=CDC|ESC` env var or a `Parametrization` flag (per the §Architecture decision above, this should be a class-instantiation choice, not an inline env-var check).

---

## Paired alternatives — what each interpretive anchor's ESC version is

For each interpretive anchor in the inventory, this section records the literal ESC-direction code (extracted from `origin/maintain_bound_pair_fix_splurge` or derived from `models_CDC_and_ESC.md` §5) so the future configurable refactor becomes a mechanical apply-the-spec exercise rather than re-derivation.

### Anchor 31.5 — `get_poststates` override (the central CDC patch) — `(I+B)`

**Current CDC code** in `Code/HA-Models/FromPandemicCode/AggFiscalModel.py:1057-1083`:

```python
def get_poststates(self):
    if os.environ.get("HAFISCAL_SPLURGE_OLD", "0") == "1":
        self.state_now['aNrm'] = self.state_now['mNrm'] - self.state_now['cNrm']
        self.state_now['aLvl'] = self.state_now['aNrm'] * self.state_now['pLvl']
    else:
        # CDC asset rule: subtract realized weighted consumption (CDC-1)
        self.state_now['aNrm'] = self.state_now['mNrm'] - self.state_now['cLvl_splurge'] / self.state_now['pLvl']
        self.state_now['aLvl'] = self.state_now['aNrm'] * self.state_now['pLvl']
    AggIndMrkvConsumerType.get_poststates(self)
```

**ESC equivalent**: there is *no override* in `origin/maintain_bound_pair_fix_splurge` (verified). HARK's default `get_poststates` runs, computing `aNrm = mNrm − cNrm` (where `cNrm = cFunc(mNrm)` is the Optimizer's per-Optimizer consumption per ESC-1). Under the ESC class, the `get_poststates` method is simply not overridden:

```python
class ESCAggFiscalType(AggFiscalType):
    # No get_poststates override — uses HARK default a = m − cFunc(m), which IS the ESC-1 rule.
    pass
```

### Anchor 32.2 — `_option_d_wealth` correction in `Estimation_BetaNablaSplurge.py:225-230` — `(I+B)`

**Current CDC code:**

```python
def _option_d_wealth(agent):
    aLvl_hark = agent.state_now["aLvl"]
    cNrm = agent.controls.get("cNrm", agent.state_now.get("cNrm"))
    return aLvl_hark - SplurgeEstimate * agent.state_now["pLvl"] * (agent.shocks["TranShk"] - cNrm)
WealthNow = np.concatenate([_option_d_wealth(ThisType) for ThisType in EstTypeList])
```

**ESC equivalent** (from `origin/maintain_bound_pair_fix_splurge:Estimation_BetaNablaSplurge.py:219`):

```python
WealthNow = np.concatenate([(1-SplurgeEstimate)*ThisType.state_now["aLvl"] for ThisType in EstTypeList])
```

Notes: Under ESC, HARK's `aLvl_hark` IS the Optimizer's per-Optimizer asset (which equals the household's `aLvl_tot`/(1−ς)), so multiplying by `(1−ς)` recovers the household total. Under CDC, HARK's `aLvl_hark` is `pLvl*(mNrm−cNrm)` (using the optimizer's *proposal*, not the realized consumption), so the splurge wedge `ς·pLvl·(TranShk−cNrm)` must be subtracted. The same pattern (multiply by `(1−ς)` vs subtract the wedge) appears in **Estimation_BetaNablaSplurge.py:228, 230, 461** — the K/Y aggregator and the per-quartile counts.

### Anchor 32.5 — lottery MPC formula in `Estimation_BetaNablaSplurge.py:341-349` — `(I)`

**Current CDC code** (after the manual state-tracking refactor):

```python
# (after the manual a_base / m_base setup in lines 287-339)
cFunc = ThisType.solution[0].cFunc
c_base[:,period] = (1 - SplurgeEstimate) * cFunc(m_base) + SplurgeEstimate * xi_hark
a_base[:,period] = m_base - c_base[:,period]
c_actu[:,period,k] = (1 - SplurgeEstimate) * cFunc(m_lottery) + SplurgeEstimate * TotIncNrm
a_actu[:,period,k] = m_lottery - c_actu[:,period,k]
```

**ESC equivalent** (from `origin/maintain_bound_pair_fix_splurge:Estimation_BetaNablaSplurge.py:293, 323, 334`):

```python
# No manual a_base / m_base — uses HARK's internal state directly:
c_base[:,period] = (1-SplurgeEstimate) * ThisType.controls["cNrm"] + SplurgeEstimate * ThisType.shocks["TranShk"]
# ... (lottery branch builds c_opt = cFunc(m_lottery) and):
c_actu[:,period,k] = (1-SplurgeEstimate) * c_opt + SplurgeEstimate * (ThisType.shocks["TranShk"] + Lnrm)
```

Notes: ESC works under HARK's standard simulate because HARK's default asset rule (`a = m − cFunc(m)`) IS the ESC-1 rule. CDC requires the manual state tracking because HARK's simulate would use the wrong asset rule under CDC; the manual block computes `m_base`, `c_base`, `a_base` from the previous period's CDC-consistent `a_base`. Under the future class hierarchy, `CDCAggFiscalType` would expose its own simulate-equivalent that uses the CDC asset rule, eliminating the manual tracking.

### Anchors 33.4-33.9 — the `_a` TM kernel functions in `tm_methods.py` — `(I)`

**Current CDC kernel** (the asset-update inside `_build_period_tm_a` at line 2696):

```python
g_j_prime(a, xi) = (R/Gamma_j_prime) * a + (1-varsigma) * (xi - cFunc_j_prime((R/Gamma_j_prime) * a + xi))
```

(Implements CDC-1: `a_next = m − (1−ς)·cFunc(m) − ς·ξ` where `m = (R/Γ)·a + ξ`.)

**ESC equivalent**: the corresponding kernel function would use ESC-1 instead:

```python
# ESC: a is the Optimizer's per-Optimizer asset; the kernel evolves only the Optimizer's ledger.
# The ς·ξ Splurger consumption is paid out of the Splurger's separate income stream and
# never enters the Optimizer's a — so the kernel simplifies to:
g_j_prime(a, xi) = (R/Gamma_j_prime) * a + (1 * xi) - cFunc_j_prime((R/Gamma_j_prime) * a + xi)
```

(That is, no `(1−ς)` factor on the `ξ` minus consumption term — the Optimizer's own income share is `(1−ς)·ξ` per `models_CDC_and_ESC.md` §5.1, and `cFunc(...)` is the Optimizer's full consumption out of its own resources, so the Optimizer's per-period budget closes simply: `a_next = m_opt − cFunc(m_opt)`.) Under the class hierarchy, this would be an `ESCAggFiscalType._build_period_tm_a` (or equivalent) that the dispatch in `Simulate.py` selects when `interpretation = 'ESC'`.

The `_a` indexing itself (vs `_m`) is *not* CDC-specific — it's required under any splurge-in-budget reading because the asset depends on realized ξ. So the *infrastructure* (a-grid, ergodic, propagator) is shared between CDC and ESC; only the kernel formula differs.

---

## Pinned baselines (2026-04-25)

Numerical baselines for the headline outputs under each interpretation. The future configurable version's tests should reproduce these to within MC sampling noise (~0.5% on multipliers).

### Calibration triples

| Parameter | CDC (`_TM-vs-MC`) | ESC (`maintain_bound_pair_fix_splurge`) |
|---|---|---|
| ς (splurge) | 0.26088 | 0.26718 |
| β (aggregate) | 0.96108 | 0.97148 |
| ∇ (β-spread) | 0.06684 | 0.05892 |

### Per-education-group calibration (CRRA=2.0, R=1.01)

| Group | CDC β | CDC ∇ | CDC GICx | ESC β | ESC ∇ | ESC GICx |
|---|---|---|---|---|---|---|
| 0 (Dropout) | 0.6995 | 0.3398 | 6.07 | 0.6995 | 0.3398 | 6.07 |
| 1 (HighSchool) | 0.9302 | 0.0705 | 5.10 | 0.9298 | 0.0708 | 4.20 |
| 2 (College) | 0.9835 | 0.0129 | 6.69 | 0.9835 | 0.0129 | 6.69 |

Notes: groups 0 and 2 are essentially identical between CDC and ESC; group 1 (HighSchool) shows a small but nonzero β/∇/GICx difference. This is consistent with `models_CDC_and_ESC.md` §7's general claim (similar parameters at independently-fit calibrations).

### Baseline multipliers (CDC, from `Tables/Baseline/Multiplier.tex`, run `reproduce-20260425-comp-full-tm-only`)

| Policy | No-AD | With AD |
|---|---|---|
| Stimulus check | 0.895 | 1.093 |
| UI extension | 0.924 | 1.157 |
| Tax cut | 0.879 | 0.999 |

Other Baseline-table values:
- Share of policy expenditure during recession: Check 100.0%, UI 79.7%, TaxCut 57.6%
- Share of policy consumption stimulus during recession: Check 72.2%, UI 78.2%, TaxCut 44.7%

ESC multipliers under the *current code* are **not yet measured**; would require running the codebase under `ESCAggFiscalType` (which doesn't exist yet) or running `origin/maintain_bound_pair_fix_splurge` independently (deferred per `proposed_path_forward_20260424.md` §1).

### Baseline welfare-6 (CDC, from `Tables/Baseline/welfare6.tex`)

| Policy | $\mathcal{W}(\text{Rec=0, AD=0})$ | $\mathcal{W}(\text{Rec=1, AD=0})$ | $\mathcal{W}(\text{Rec=1, AD=1})$ |
|---|---|---|---|
| Stimulus check | 0.97 | 1.01 | 1.34 |
| UI extension | 0.86 | 1.46 | 1.73 |
| Tax cut | 0.99 | 1.00 | 1.13 |

ESC welfare-6 not yet measured (same reason as multipliers).

### Reproduction anchor

CDC multipliers above are reproducible from git tag `reproduce-20260425-comp-full-tm-only` per the self-documenting-runs machinery (commit hash `db6e4d92` on `_TM-vs-MC`; recipe at `reproduce/run-manifests/comp_full_*_tm-only.reproduce-recipe.sh`).
