# splurge-in-budget implementation — concrete sequence

**Date drafted:** 2026-04-14 · **Revised:** 2026-04-15
**Depends on:**
- `plans/20260418-1136h_splurge-in-budget-a-indexed-TM.md` — design rationale, including the interpretation-A framing and why alternatives (joint $(m,\xi)$ state, m-indexed with correction, $E[\xi]$ plug-in) are rejected
- `BUGS_private/HAFiscal_splurge_budget_inconsistency/bound-pair-interpretation_response.ipynb` — argument that the codebase implements interpretation A, pinned by the K/Y diagnostic
- `history/20260413-20260414-option-C-D-splurge-overnight.md` — session context

**Target branch:** `splurge-in-budget-a-indexed-TM` (branched from `_matsya` at current HEAD)

This document turns the design in `splurge-in-budget-a-indexed-TM.md` into an ordered, committable sequence with acceptance criteria for each phase. The rationale doc explains WHY; this one focuses on WHAT to do and in WHICH ORDER.

**Sanity reminder on scope:** the refactor produces **one** a-indexed transition matrix per agent type, not $N_\xi$ matrices. The sum over transitory shocks happens inside the kernel-construction loop.

---

## Process requirement — BUGS_private bookkeeping at every phase

This sequence touches the calibration pipeline (lottery MPC, wealth estimation) and the simulation pipeline (TM, MC, welfare). To keep the audit trail reviewable, **every phase below MUST begin by creating or updating a dedicated entry in `BUGS_private/`** before any code change, and **the master bug index `BUGS_private/HARK+HAFiscal_TM_vs_MC_bug_index.md` MUST be updated to list the new BUG-NNN**.

Naming and structure follow the existing pattern:

- A single-file bug is named `BUGS_private/HAFiscal_BUG-NNN_<short_description>.md`.
- A bug whose writeup needs multiple documents (notebooks, comparison reports, MWE scripts) gets its own directory `BUGS_private/HAFiscal_<short_description>/` (no BUG-NNN in the directory name; the mapping is recorded in the bug index). The existing `HAFiscal_splurge_budget_inconsistency/` (= BUG-031) is the working template for this style.

Each new bug entry must contain at minimum:

1. **BUG-NNN identifier** at the top (with a line in the master bug index).
2. **Problem statement** — the specific behavior that is wrong, with file/line references to the code.
3. **Why it matters** — the downstream consequence: which moments, multipliers, welfare numbers, or calibrations are affected, and by approximately how much.
4. **Current thinking on resolution** — proposed fix, alternatives considered, and why the chosen approach was selected.
5. **Acceptance criteria** — concrete, testable outcomes (e.g., "parameter shift < X%", "TM matches MC within Y%").
6. **Upstream dependencies** — what other BUG-NNN entries this one depends on.
7. **Downstream consumers** — which subsequent phases or published results depend on this one.

At the end of each phase, the same entry must be updated with:

- the actual changes made, with commit hashes;
- observed results (parameter shifts, test outcomes);
- any follow-up issues that surfaced during the phase.

And the master bug index must be updated to reflect the new status (Open → Fixed, with the relevant commit hash).

Two purposes: (a) force explicit thought about each phase before coding; (b) produce a reviewable trail of why the paper's published calibration changed.

**The first splurge-in-budget-era bugs are already filed:**
- **BUG-031** (`HAFiscal_splurge_budget_inconsistency/`) — the root budget-identity issue, with the bound-pair-vs-within-household analysis and the splurge-in-budget decision.
- **BUG-032** (`HAFiscal_lottery_splurge_formula/`) — the lottery-MPC formula inconsistency that becomes visible once splurge-in-budget is adopted. Defines Phase 1 below.

Subsequent phases (a-indexed TM refactor, CRRA2 Baseline production, per-parametrization sensitivities, etc.) should each be assigned a new BUG-NNN and filed the same way.

---

## Prerequisites (before any phase)

**P0. Land the cherry-picks.** [Already done; preserved for audit.] Cherry-picks of splurge-in-budget docs, plan, MC patch, and estimation wealth correction from `option-d-in-tree` onto `_matsya`.

**P1. Verify MC under splurge-in-budget works.** [Already done.] `get_poststates` on MC uses realized `TranShk`; MC is the unbiased reference for all TM work that follows.

**P2. Create implementation branch.**

```bash
git checkout -b splurge-in-budget-a-indexed-TM
```

---

## Phase 1 — Lottery re-estimation under canonical splurge MPC formula

**Why first.** The splurge $\varsigma$ is an input to step 2 ($\beta$/$\nabla$ estimation), which is in turn an input to every subsequent simulation, multiplier, and welfare number. If the $\varsigma$ used downstream is inconsistent with splurge-in-budget, every downstream result carries that inconsistency. This phase fixes the upstream problem first.

**BUGS_private entry:** **BUG-032** — `BUGS_private/HAFiscal_lottery_splurge_formula/` (README already filed). Update with commit hashes and results at phase end; mark **Fixed** in the bug index when acceptance criteria are met.

### 1.1 Update the lottery-MPC routine in `Estimation_BetaNablaSplurge.py`

Current (lines ~306, 334–337):

```python
c_base[:, period] = ThisType.controls["cNrm"]                  # = cFunc(mNrm),  no splurge
m_adj       = ThisType.state_now["mNrm"] + Lnrm - SplurgeNrm   # = mNrm + (1-ς)·L
c_actu[:, period, k] = ThisType.solution[0].cFunc(m_adj) + SplurgeNrm  # = cFunc(mNrm+(1-ς)L) + ς·L
```

Canonical replacement (splurge-in-budget-consistent: solver unchanged, splurge applied to total income in both baseline and lottery):

```python
# Both baseline and lottery paths track their own splurge-in-budget assets;
# HARK's simulate(1) is used only to draw shocks — HARK's internal
# a = m − cFunc(m) update is ignored.
ThisType.simulate(1)
xi = ThisType.shocks["TranShk"]
psi = ThisType.shocks["PermShk"]
pLvl = ThisType.state_now["pLvl"]

if period == 0:
    m_base    = ThisType.state_now["mNrm"]       # initialize from HARK's post-init m
    m_lottery = m_base + Lnrm
else:
    # Death reset, R_kink by sign of a_prev, then:
    m_base    = a_base[:, period-1] * R_kink_base / psi + xi
    m_lottery = a_actu[:, period-1, k] * R_kink_actu / psi + xi + Lnrm

# splurge-in-budget consumption: c = (1-ς)·cFunc(m) + ς·income
c_base[:, period]    = (1 - ς) * cFunc(m_base)    + ς * xi
c_actu[:, period, k] = (1 - ς) * cFunc(m_lottery) + ς * (xi + Lnrm)

# splurge-in-budget asset update: a = m − c_actual
a_base[:, period]    = m_base    - c_base[:, period]
a_actu[:, period, k] = m_lottery - c_actu[:, period, k]
```

**Key points.**
1. Under splurge-in-budget, cFunc is evaluated at the *original* market resources `m` (solver is splurge-unaware). An alternative formulation — splurge-aware cFunc evaluated at `m − ς·ξ` — corresponds to BUG-031's Option A, not splurge-in-budget. The simulation's `AggFiscalModel.py::get_poststates` and the Phase 3 TM builder both use `cFunc(m)` directly; Phase 1 must match.
2. Both baseline and lottery paths must use splurge-in-budget's asset rule (`a = m − c_actual`). The pre-fix code relied on HARK's standard asset update (`a = m − cFunc(m)`) for the baseline path, which causes non-winner agents to produce spurious `c_actu − c_base ≠ 0` in period > 0 because the two trajectories drift apart. Tracking `a_base` explicitly (and skipping HARK's built-in state update) eliminates this bias.

### 1.2 Re-run step 1

```bash
cd Code/HA-Models/Target_AggMPCX_LiquWealth
python Estimation_BetaNablaSplurge.py  # refit ς
```

Record the new ς with a comparison to the published value (0.248). Commit the updated `Result_AllTarget_*` files.

### 1.3 Record results in the BUGS entry

Update `BUGS_private/HAFiscal_lottery_splurge_formula/README.md` with:

- new ς value and its delta from published;
- comparison of the model MPC-by-wealth-quartile under new ς vs. Fagereng targets;
- commit hash of the updated `Estimation_BetaNablaSplurge.py`.

**Acceptance:** step 1 converges; ς shift is quantified; the new ς is committed and documented.

**Stop/go checkpoint:** if |Δς| / ς > 10%, discuss with coauthors before proceeding to Phase 2 — the MC Reduced_Run and Baseline multiplier results already reported hold the published ς fixed and may need to be recomputed under the new ς.

---

## Phase 2 — Step-2 β/ν re-estimation with the new ς

**Why second.** With a new ς in hand, re-run step 2 (the β and ν estimation targeting SCF Lorenz + K/Y) to get a fully consistent calibration. Overnight runs holding ς fixed showed shifts ≤ 10⁻⁴, but the new ς may move the targets.

**BUGS_private entry:** extend `BUGS_private/HAFiscal_splurge_budget_inconsistency/` with a dedicated section covering step-2 re-estimation under splurge-in-budget + new ς, or create a new directory if results diverge from the original bug's narrative.

### 2.1 Run step 2

```bash
cd Code/HA-Models/FromPandemicCode
python EstimAggFiscalMAIN.py  # with splurge-in-budget wealth correction and new ς
```

### 2.2 Record results

Parameter shifts (β_center, ν_spread per education group) with deltas from published values.

**Acceptance:** step 2 converges; parameter shifts quantified; if all shifts < 1%, we proceed to Phase 3 with confidence. If any shift > 5%, discuss with coauthors — the calibration has materially moved.

---

## Phase 3 — Core a-indexed TM refactor (2-3 days)

**Approach decided 2026-04-15:** a-indexed TM, no $(m, \xi) \to$ a-indexed hybrid. Development correctness is verified against MC (the ground-truth reference) using narrow, fast asymptotic-style tests rather than full MC runs. See `plans/20260418-1136h_splurge-in-budget-TM-approach-comparison.md` §5 for the decision record and `plans/20260403-1253h_asymptotic-equality-test-plan.md` + `Code/HA-Models/Gatekeeper_Asymptotic_Equality.ipynb` for the test harness pattern to reuse.

**BUGS_private entry:** create `BUGS_private/HAFiscal_tm_a_indexed_refactor/README.md` articulating the m-indexed TM's loss of ξ-variance under splurge-in-budget, the a-indexed resolution (one matrix, not N), and the per-function implementation scope. Link to `plans/20260418-1136h_splurge-in-budget-a-indexed-TM.md` §3. Assign the next free BUG-NNN (probably BUG-033) in the master bug index.

All changes confined to `Code/HA-Models/FromPandemicCode/tm_methods.py` plus minor callers. The pattern is **parallel implementation**: each new function ends in `_a`. Old m-indexed functions stay untouched so tests and published pipelines still work during development.

### 3.1 Baseline TM builder — `build_tm_agg_fiscal_a`

**Input:** agent (with `Splurge`, `IncShkDstn`, `MrkvArray`, `Rfree`, `PermGroFac`, `LivPrb`, solution.cFunc), grid params (aCount, aMin, aMax, aFac).

**Procedure:**
```python
def build_tm_agg_fiscal_a(agent, aCount=100, aMin=0.0, aMax=50.0, aFac=3,
                          Cratio=1.0, neutral_measure=False):
    Splurge = float(agent.Splurge)
    MrkvArray = agent.MrkvArray[0]; J = MrkvArray.shape[0]
    Rfree = np.asarray(agent.Rfree[:J], dtype=np.float64)
    PermGroFac = np.asarray(agent.PermGroFac[0][:J], dtype=np.float64)
    LivPrb_eff = _effective_LivPrb(np.asarray(agent.LivPrb[0][:J]), agent.T_age)
    IncShkDstn = [agent.IncShkDstn[0][j] for j in range(J)]

    # a-grid (log-spaced above a_min)
    dist_aGrid = make_grid_exp_mult(aMin, aMax, aCount, aFac)
    A = len(dist_aGrid)

    # Kernel: TM[(a', j_next), (a, j_now)] = LivPrb * MrkvArray[j, j_next]
    #         * Σ_ξ p_ξ * lottery(a', g_{j_next}(a, ξ))
    #         + death-injection into NewBornDist
    TM = sp.lil_matrix((A*J, A*J))
    for j in range(J):
        for jn in range(J):
            trans = MrkvArray[j, jn]
            if trans < 1e-15:
                continue
            dstn = _to_neutral_measure([IncShkDstn[jn]])[0] if neutral_measure else IncShkDstn[jn]
            for k in range(len(dstn.pmv)):
                psi = dstn.atoms[0][k]; xi = dstn.atoms[1][k]; p = dstn.pmv[k]
                xi_eff = xi  # In baseline TM Cratio=1; in experiments may differ
                Phi = PermGroFac[jn] * psi
                for ia, a in enumerate(dist_aGrid):
                    m_next = (Rfree[jn] / Phi) * a + xi_eff
                    c_star = agent.solution[0].cFunc[jn](m_next, Cratio)
                    c_actual = (1.0 - Splurge) * c_star + Splurge * xi_eff
                    a_next = max(m_next - c_actual, 0.0)
                    lo, hi, w = _lottery(dist_aGrid, a_next)
                    TM[lo*J + jn, ia*J + j] += LivPrb_eff[jn] * trans * p * w
                    TM[hi*J + jn, ia*J + j] += LivPrb_eff[jn] * trans * p * (1 - w)

    # Add newborn injection (for dead mass)
    markov_erg = _solve_markov_ergodic(MrkvArray)
    for j in range(J):
        death_mass = (1.0 - LivPrb_eff[j])
        for ia in range(A):
            for jn in range(J):
                TM[0 * J + jn, ia * J + j] += death_mass * markov_erg[jn]

    return {
        'TranMatrix': TM.tocsr(),
        'dist_aGrid': dist_aGrid,
        'markov_ergodic': markov_erg,
    }
```

**Key sub-decisions:**
- **Lottery** (`_lottery(grid, value)`): linear interpolation onto grid — returns (lo_idx, hi_idx, weight_on_lo). Already in HARK utilities or easy to implement.
- **Newborn dist**: newborns start at `a = 0` with Markov-stationary `j`. Death mass is re-injected at this point.
- **Neutral measure (Harmenberg)**: `neutral_measure=True` rescales `ξ` atoms by `ψ / E[ψ]`. Apply in the atom loop (or via `_to_neutral_measure`).

**Acceptance:** ergodic distribution matches m-indexed TM's implied a-distribution to 4 decimal places when `Splurge=0`.

### 3.2 Baseline aggregation — `compute_type_aggregates_tm_a`

Aggregates over the `(a, j_t)` ergodic, integrating over `(j_{t+1}, ξ)` for period outcomes.

```python
def compute_type_aggregates_tm_a(agent, tm_data, ergodic):
    Splurge = float(agent.Splurge)
    dist_aGrid = tm_data['dist_aGrid']; A = len(dist_aGrid)
    J = agent.MrkvArray[0].shape[0]
    MrkvArray = agent.MrkvArray[0]
    IncShkDstn = [agent.IncShkDstn[0][j] for j in range(J)]
    Rfree = np.asarray(agent.Rfree[:J])
    PermGroFac = np.asarray(agent.PermGroFac[0][:J])

    C_nrm = 0.0
    C_splurge_nrm = 0.0
    Income_nrm = 0.0
    A_nrm = 0.0
    state_fractions = np.zeros(J)
    erg = ergodic.reshape(A, J)
    for j in range(J):
        for ia, a in enumerate(dist_aGrid):
            w = erg[ia, j]
            state_fractions[j] += w
            A_nrm += w * a
            for jn in range(J):
                trans = MrkvArray[j, jn]
                if trans < 1e-15: continue
                dstn = IncShkDstn[jn]
                for k in range(len(dstn.pmv)):
                    psi = dstn.atoms[0][k]; xi = dstn.atoms[1][k]; p = dstn.pmv[k]
                    Phi = PermGroFac[jn] * psi
                    m_next = (Rfree[jn] / Phi) * a + xi
                    c_star = agent.solution[0].cFunc[jn](m_next, 1.0)
                    c_actual = (1.0 - Splurge) * c_star + Splurge * xi
                    wt = w * trans * p
                    C_nrm += wt * c_star
                    C_splurge_nrm += wt * c_actual
                    Income_nrm += wt * xi
    return {'C_nrm': C_nrm, 'A_nrm': A_nrm,
            'C_splurge_nrm': C_splurge_nrm, 'Income_nrm': Income_nrm,
            'state_fractions': state_fractions}
```

**Acceptance:** with `Splurge=0`, `C_splurge_nrm == C_nrm` and matches the m-indexed aggregator to 4 decimals on CRRA2 baseline.

### 3.3 Per-period aggregation — `compute_period_aggregates_tm_a`

Analogous to `compute_period_aggregates_tm` but accepts `(dist, tm_data, IncShkDstn_list, Splurge, AggDemandFac, TranShk_addition)` and integrates over the same `(j_{t+1}, ξ)` tuples. `AggDemandFac` scales `ξ`. `TranShk_addition` (e.g., stimulus check) is added to `ξ` in both the splurge term and the income.

### 3.4 Experiment-period builder — `build_experiment_period_tm_a`

Takes `(a_t, j_t)` to `(a_{t+1}, j_{t+1})` for one period of the recession experiment.

**Differences from baseline:**
- Uses `agent.CondMrkvArrays[macro_next]` as the micro-Markov transition.
- `ad_tran_shk_scale` multiplies `ξ` atoms (AD factor).
- `employed_tran_shk_scale` multiplies `ξ` atoms for employed (tax cut timing).
- `mNrm_shift[j_next]` — shift enters as additional gross income; splurge applies to `(ξ + shift)`. So:
  ```
  m_{t+1}  = (R/Γ)·a_t + ξ·ad_scale·emp_tc + shift[j_next]
  c_actual = (1−ς)·c*(m, j_next, Cratio_t) + ς·(ξ·ad_scale·emp_tc + shift[j_next])
  a_{t+1}  = max(m_{t+1} − c_actual, 0)
  ```

Returns the transition kernel (sparse) and the per-period aggregates (C and Y integrated over the period).

### 3.5 Experiment propagator — update `propagate_experiment_tm`

Fewer changes than it looks. The outer loop and Cratio-path handling stay. The inline Check block (current lines ~1945–1990) becomes bucket-wise calls to `build_experiment_period_tm_a` and `compute_period_aggregates_tm_a`, with bucket-weighted aggregation.

### 3.6 Switching flag

Add to `AggFiscalType.__init__`:
```python
self.tm_a_indexed = True   # default ON once validated
```

Dispatch in `Simulate.py`:
```python
if getattr(ThisType, 'tm_a_indexed', False):
    tm_data = build_tm_agg_fiscal_a(ThisType, ...)
else:
    tm_data = build_tm_agg_fiscal(ThisType, ...)
```

**Commit granularity:** one commit per numbered sub-step (3.1, 3.2, ...). Each commit must compile & not break existing tests.

---

## Phase 4 — Validation (1 day)

**BUGS_private entry:** extend the TM refactor entry with a "validation" section; record all test outcomes there.

### 4.1 Equivalence with `Splurge = 0`

**Test:** set `agent.Splurge = 0`; compute ergodic via both methods; compare state moments (E[m], E[a], quartiles). Tolerance 1e-4.

### 4.2 TM_a ≈ MC under splurge-in-budget

Run CRRA2 TM_a + splurge-in-budget and CRRA2 MC + splurge-in-budget. Compare:
- AggCons at steady state
- AggCons path during recession
- Multiplier values for Check/UI/TC

Tolerance: within 0.5% (MC noise at N=10K).

### 4.3 Reduced_Run regression

`python AggFiscalMAIN_reduced.py` (TM-only with the a-indexed flag) should complete cleanly and produce a full Multiplier.tex with sensible values.

**Acceptance:** TM_a matches MC; policy ranking makes intuitive sense; no NaN/inf anywhere.

---

## Phase 5 — CRRA2 Baseline production (4 hours)

**BUGS_private entry:** new `BUGS_private/HAFiscal_baseline_CRRA2_optD_corrected/` summarizing the production-grade multiplier numbers against QE/published.

### 5.1 Full Baseline TM_a run

```bash
cd Code/HA-Models/FromPandemicCode
python AggFiscalMAIN_reduced.py --baseline
```

Produces `Tables/Baseline/Multiplier.tex` with the corrected (a-indexed + splurge-in-budget + updated ς) numbers.

### 5.2 Comparison

Extend `build_comparison.py` to include a column for TM_a + splurge-in-budget alongside the existing QE / Latest-preOC / Option C / splurge-in-budget-biased columns.

**Acceptance:** fresh Multiplier.tex + extended comparison report, committed to `_matsya`.

---

## Phase 6 — Baseline welfare analysis (ASAP, ~5h)

**Priority: highest after Phase 5.** Welfare numbers are required for the paper; robustness across alternative parametrizations is gravy.

**BUGS_private entry:** new `BUGS_private/HAFiscal_baseline_welfare6_optD/` summarizing Baseline welfare6 under splurge-in-budget + TM_a vs QE/published.

### 6.1 MC welfare6 for Baseline under splurge-in-budget

Preconditions: Phase 5 complete (Baseline TM_a multiplier results must exist for `run_hybrid_welfare6.py` to use).

```bash
cd Code/HA-Models/FromPandemicCode
python run_hybrid_welfare6.py --baseline
```

Uses standard MC (CRN-paired, no shuffle) because individual-level matching across experiments is required for welfare6 — TM cannot provide this. CRN cancels idiosyncratic noise in the treatment effect Δu. Expected runtime: ~5h at Baseline N.

Produces `Tables/Baseline/welfare6.tex` (and any companion welfare tables) with corrected splurge-in-budget values.

### 6.2 Comparison

Compare welfare6 numbers against QE/published (`Code/HA-Models/FromPandemicCode/Tables/CRRA2/welfare6.tex`). Flag any sign flips or large (>10%) shifts in the welfare ranking across policies.

**Acceptance:** fresh Baseline `welfare6.tex` committed to `_matsya`, comparison report in the BUGS_private entry.

---

## Phase 7 — Extended robustness (1-2 weeks)

Only after Phase 6 is clean. Each sub-phase gets its own BUGS_private entry (one per parametrization).

### 7.1 Sensitivity robustness

Run each parametrization (CRRA1, CRRA3, Rfree_*, ADElas, Rspell_4, LowerUBnoB, Splurge0) under splurge-in-budget + TM_a. Produces the full set of appendix tables.

### 7.2 MC welfare6 for sensitivity specs

Run `run_hybrid_welfare6.py` for each non-Baseline specification. ~5h per spec.

### 7.3 Paper revision

Update the paper's Tables and Figures with the corrected values. The headline narrative may change (e.g., Check vs UI ranking).

---

## Phase 8 — Deprecation (1 day)

Once TM_a is production-validated:
- Make `tm_a_indexed = True` the default.
- Move m-indexed functions to `tm_methods_legacy.py` or gate behind `tm_a_indexed = False`.
- Update tests.
- Remove Option C atom-scaling code (on `option-c-in-tree`) from consideration entirely.

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Phase 1 ς shift is large (>10%) and invalidates earlier preliminary results | Stop/go checkpoint after Phase 1; recompute MC Reduced_Run and Baseline under new ς before proceeding to Phase 3 |
| AD iteration fails to converge under TM_a | Cap iterations at 50; fall back to last-iter Cratio path; flag in logs |
| Sparse matrix memory blow-up (Baseline 21 types × 88 Mrkv states × 100 a-grid × 7 ξ atoms ≈ 130k nonzeros per type) | Use `scipy.sparse.csr_matrix`; confirm ≤ 1 GB for Baseline |
| Lottery on a-grid introduces numerical drift | Verify mass conservation to 1e-10 per period; log drift |
| Per-education heterogeneity (each type has different `cFunc`) | Build TM_a per type and combine via `state_fractions` weighted by education shares |
| Harmenberg Q-measure compatibility | Revisit `neutral_measure=True` flag in TM_a; test `(neutral=True) ≈ (neutral=False)` for Splurge=0 baseline |

---

## Estimated compute + wall clock

| Phase | Compute | Wall clock |
|---|---|---|
| Phase 1 (lottery re-estimation) | ~1-2h | 1 day |
| Phase 2 (step 2 re-estimation) | ~6-8h | 1 day |
| Phase 3 (TM refactor coding) | negligible | 2-3 days |
| Phase 4 (validation runs) | ~10h | ~1 day |
| Phase 5 (Baseline production) | 2-4h | same day |
| Phase 6 (extended) | 150-250h | 2 weeks |
| Phase 7 (deprecation) | negligible | 1 day |

---

## Definition of done

**Minimum**: CRRA2 Baseline splurge-in-budget multipliers published on `_matsya` with (a) updated ς from Phase 1, (b) updated β/ν from Phase 2, (c) a-indexed TM from Phase 3, matching MC within 0.5%. Comparison table committed to `BUGS_private/HAFiscal_baseline_CRRA2_optD_corrected/`.

**Full**: all sensitivity parametrizations under splurge-in-budget + TM_a, welfare recomputed, paper revised.

---

## Stop / go checkpoints for discussion with coauthors

1. **End of Phase 1**: show Edmund the ς shift and whether it invalidates the preliminary MC multiplier results. Decision: recompute those now (before Phase 2) or proceed and compute once at the end.
2. **End of Phase 2**: share β/ν shifts. If they're material, discuss whether the paper's wealth-Lorenz and K/Y match fares better or worse under the new calibration.
3. **End of Phase 4**: show TM_a ≈ MC agreement under splurge-in-budget. Confirms the correct fix works.
4. **End of Phase 5**: show revised CRRA2 Baseline multipliers. Decide:
    - "Publish with contemporaneous fix" — revise the paper's main table to use splurge-in-budget + TM_a + updated calibration
    - "Publish unchanged with a note" — describe the issue and magnitude in the online appendix
    - "Pause for full robustness" — only move forward after Phase 6
5. **End of Phase 6**: decide whether changes propagate to the paper's narrative (e.g., Check-vs-UI policy ranking flip).
