# Forward-Improvement Agenda for HAFiscal — 2026-06-11

# >>> DRAFT FOR OWNER REVIEW — NOT AUTHORIZED UNTIL EDITED/APPROVED BY OWNER <<<

# Generated: 2026-06-11 by Phase B of `plans/20260611_docs-dedup-and-navigation.md`
# Template: `agenda_2026_06_03.md` (item-by-item audit of the old agenda:
# `Code/HA-Models/docs/COMMENT_AUDIT_FINDINGS.md` — 1 done, 3 superseded, 29 open)

## Context

We are on branch `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` (the canonical integration target per `plans/20260610_integration-target-TM-vs-MC.md`). Since the 2026-06-03 agenda, the work pivoted away from the speedup track entirely — none of its five Tier-1 items was started — into the method/correctness arc that is now settled:

- **Welfare method unified: MC for all cells (2026-06-10).** Canonical defaults are wired into `EstimParameters.py` (`HAFISCAL_MC_SHUFFLE=1`, `HAFISCAL_SHUFFLE_MRKV_TRANSITION=stratified`, `HAFISCAL_SHUFFLE_NEWBORN_FIX=transition`, `HAFISCAL_TM_AMAX=1300`), with `HAFISCAL_QE_FIDELITY=1` as the legacy escape hatch. UI rec cells are REPORTABLE again (ui_rec ≈ +0.05% bias under stratified-shuffle); only ui_norec stays excluded (0/0 structural). See `conclusions_private/2026-06-10_welfare_method_unified_MC.md`.
- **BUG-052** (welfare cold-start vs ergodic calibration) classified TYPE-A error; ergodic warm-start is the default. **BUG-053** (GIC shave on β not GPF) fixed and re-estimated 2026-06-09 with owner-set `theGICfactor=0.9995` (calibration-neutral for the College cap atom). Production TM grid `aMax=1300` via `production_aMax()`.
- **BUG-047** (solver PermGroFac^(−γ) factor) fixed default-ON; awaiting formal owner confirm (gate G1 below).
- **Mandate 1 (doc rationalization)** is executing unattended on side branch `…_TM-vs-MC_doc-rationalization` (4 plans; this draft is a Phase-B artifact). **Mandate 2 (dolo-plus integration)** plan set authored 2026-06-11 (`plans/20260611_doloplus-*`), execution not started.
- A **Baseline 4-seed welfare chain** is in flight on the sibling checkout (`HAFiscal-Latest`); its SEs are the acceptance evidence for the canonical-default welfare numbers.

## Constraints (do NOT violate)

Carried forward from 2026-06-03, with the UI line corrected per the 2026-06-10 decision:

- **No T_sim modifications.** User-explicit constraint.
- **No NEW code in `Code/HA-Models/FromPandemicCode/`.** New utilities live in `Code/HA-Models/` or a sibling subdirectory.
- **Paper-grade welfare correctness: ≤0.5% relative drift on welfare-6 cells.**
- **NEVER report `ui_norec`** (0/0 by construction) — but ui_rec/ui_rec_AD ARE reportable under MC+CRN+stratified-shuffle (canonical defaults). Do NOT re-deprecate UI; do not use plain `shuffle` (the +8.26% footgun).
- **Validation = asymptotic convergence**, not point-wise agreement.
- **Cascade-gate** any validation with a cost-scaling param: HS_Only → Reduced_Run → Baseline; HALT on failure.
- **Always CRN for MC; never report a bias without a multi-seed SE.**
- **Set `PYTHONUNBUFFERED=1`** for monitored background Python.
- **Default = no re-estimation; opt-in only.** Calibration files are fixed inputs (current set = BUG-053 re-estimation of 2026-06-09).
- **Matched triple:** {PermGroFac regime, calibration, interpretation (CDC/ESC)} move together — never mix caches/warm-starts/calibrations across regimes.
- **Every MC run needs a TM-a companion + 4-moment drift table** (mean/var-log(a), var-log(p)) surfaced in the headline.
- **QE comparisons** use tag `v2026-01-09-18-17` and open with the two-sided characterization (QE baseline vs current); methodologically-matched runs go through `HAFISCAL_QE_FIDELITY=1`.

## Tier 1: Execute these in order

### T1.1 — Review Baseline 4-seed welfare SEs when the in-flight chain completes

**Goal**: Confirm the canonical-default (unified-MC, ergodic warm-start, aMax=1300, BUG-053 calibration) welfare-6 numbers at Baseline with multi-seed SEs; this is the acceptance evidence for the 2026-06-10 decision.

**Where**: chain running on the sibling checkout `HAFiscal-Latest` (do not disturb); results under `Code/HA-Models/FromPandemicCode/welfare6_scenario_results_*` / `reproduce/logs/`.

**Gate**: report per-cell mean ± SE (SD/√S over seed offsets); exclude ui_norec; include the 4-moment MC-vs-TM-a drift table in the headline. HALT and triage if any decisive cell SE > 0.5% rel or drifts vs the 2026-06-10 decision values.

### T1.2 — Plan H: QE / original-paper-matching analysis (the destination)

**Goal**: Complete the QE-matching under the canonical approach at current SCF-2004 urates, with `HAFISCAL_QE_FIDELITY=1` runs as the methodologically-matched legacy comparator. This is the owner's stated near-term destination.

**Where**: `plans/20260610_post_merge_canonicalize_default_solution.md` §Plan H (and its priority ladder: H gates I "friendly urates" and optional C "6-D TM-check").

**Gate**: QE-comparison report opens with the mandatory two-sided characterization; expected fidelity benchmark: qe_fidelity_full reproduces published QE within ±3% (`conclusions_private/2026-05-04_qe_fidelity_full_vs_QE_published.md`).

### T1.3 — Owner gates G1 + O1–O4 (sign-off packet)

**Goal**: Obtain the owner signatures that unblock all behavior-adjacent dolo-plus work.

- **G1 — BUG-047 confirm-and-reconcile**: owner signs that the default-ON PermGroFac fix is final → re-baseline harness, append post-fix addendum to `FINDING_permgrofac_marginal_value_factor.md`, update YAML comments. If reversed → escalate out (re-estimation territory).
- **O1–O4 — four-overrides re-examination** (owner explicitly required): O1 z-indexed `PermGroFac`; O2 state-contingent `IncShkDstn[z]`; O3 `z_d=z`/`z_nxt=z_d` carry; O4 ADF-applied-once. Each gets an evidence-packed sign-off row (ledger plan produces the packs; recommendations lean KEEP; O4 already numerically validated).

**Where**: `plans/20260611_doloplus-integration-master.md` §Decision-gate protocol.

### T1.4 — Execute Mandate-2 dolo-plus plan set

**Goal**: Run the five-plan dolo-plus integration set: `plans/20260611_doloplus-integration-master.md` + `…-eqn-tag-registry.md` + `…-spec-gap-ledger.md` + `…-orchestrator-spec.md` + `…-validation-productionization.md`.

**Gate**: inert work (tags, registries, docs, schemas, pytest plumbing) proceeds regardless of gate state; anything behavior-affecting waits on the signed G1/O1–O4 rows (T1.3). Re-estimation is out of scope for the entire plan set.

### T1.5 — BUG-050: recessionUI income wiring (open behavioral item — decision needed)

**Goal**: Decide and (if approved) implement the proper UI-extension income wiring under bug_fix 6-state encoding — `Simulate.py:249` copies `IncShkDstn_recession` so extension states U3/U4 pay no-benefits income, making the recessionUI multiplier 0/0 (nan; currently loudly GUARDED).

**Why now**: the 2026-06-03-era rationale for deferral ("UI deprecated as unreliable") was superseded 2026-06-10 — UI is reportable again, so the wiring fix is back on the critical path for any bug_fix-encoding UI multiplier. It is a research decision (changes UI numbers): owner authorization required; classify per the error-vs-sample governance rule.

**Where**: `BUGS_private/HAFiscal_BUG-050_recessionUI_income_not_wired.md` (status: GUARDED 2026-06-04, fix DEFERRED).

### T1.6 — Merge-back decision: doc-rationalization side branch (owner gate)

**Goal**: At Mandate-1 completion (env-flag registry, docs-dedup/navigation, family manifests, comment hygiene — all green-gated), ASK the owner whether to merge `…_TM-vs-MC_doc-rationalization` into `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` (the ONLY merge target — never master). Rebase onto the parent first if it has advanced.

**Where**: `plans/20260611_doc-rationalization-overview.md` §OWNER PRE-AUTHORIZATION (merge-back is a GATE, not automatic).

## Tier 2: Carried-over operational items (from 2026-06-03 Tier 1/2 — all audited open, none started)

Resume only after Tier 1 settles, or opportunistically; original specs in `agenda_2026_06_03.md` remain the reference.

- **T2.1 — Welfare-6 pickle-diff CLI** (was T1.1): `Code/HA-Models/welfare6_diff.py`; effort cap 8 h.
- **T2.2 — Reduced_Run smoke gate `make smoke`** (was T1.2): depends on T2.1; effort cap 1 day.
- **T2.3 — JAX persistent compilation cache** (was T1.3): `_build_child_env()`; effort cap 4 h.
- **T2.4 — Diagnose "GPU slot at 0% util" routing** (was T1.4): may be a benign AD-cache-HIT quirk; effort cap 1 day diagnosis.
- **T2.5 — Auto-registry on bench completion** (was T1.5): effort cap 6 h.
- **T2.6 — RAM upgrade +64 GB DDR5** (was T2.1): awaiting PI capex signoff (~$300); host still 54 GiB.
- **T2.7 — duration_workers hard fix** (promoted from Tier-3: deferral trigger FIRED): 2 OOM kills 2026-06-03, ~16 GB per duration-worker fork at Baseline; workaround `--duration-workers 1` documented, auto-budgeter still defaults dw=2 (`conclusions_private/2026-06-03_duration_workers_resource_constraint.md`).
- **T2.8 — Seed-parallel unified job board / wrapper polish / 2A vmap revisit** (was T2.2–T2.4): unchanged specs; T2.4-routing gate still applies to the vmap revisit.

## Tier 3: Deferred — do NOT pursue without explicit user trigger

Carried from 2026-06-03 minus: AD-first/LPT scheduling (done, `afa7d7e9`), joint-distribution UI welfare TM-a (superseded — UI reportable via MC; TM 5-D exact exists as validation), duration_workers cap (promoted to T2.7). Plus new rows:

| Item | Reason deferred | Trigger to revisit |
|------|-----------------|-------------------|
| Cross-parametrization cache reuse | Foundational premise false | Never (reframe as same-param warm-start only) |
| Cache base eco-state | <2% Baseline wall savings | Profile shows imports/setup >30s |
| MoM optimist warm-start | Finite-horizon backward induction; no iter count to cut | Model becomes infinite-horizon |
| JAX-native AD outer loop | Rejected 2026-05-22; 14–47s gain over 2–3 weeks | VRAM ceiling raised AND compile cache + 2A vmap saturated |
| vm.swappiness / cgroup MemoryMax | Fixed at orchestrator-concurrency layer | Post-fix thrash episode orchestrator can't address |
| GPU upgrade (4090/5090) | Compute-saturated not VRAM-limited; capex unjustified | >85% util on W=1 AND PI signoff |
| Cache LRU pruning | 135 MB vs 375 GB free | Cache >10 GB or >100-entry sweep queued |
| Pre-build eco_ref at session start | Cache HIT already 0.8s | MISS regime >50% of runs |
| Ref-sim init_panels disk cache | Dominated by `cached_solve_ad_recession` | AD-cache MISS + ref-sim HIT pattern emerges |
| GPU async/multi-stream post-AD | Cited loop is TM/numpy, not JAX | New post-AD JAX kernel with independent dispatches |
| Empirical slot tuning (2 CPU / 3 GPU) | 3 GPU infeasible at 16 GB VRAM | T2.6 RAM lands AND GPU upgrade |
| Share eco_ref.solve across recession scenarios | Structurally invalid for TaxCut | Check-only sharing + CRN-preserving method exist |
| 6-D TM-check (provable TM check_rec) | Bucketed-5D φ(pLvl) limit is structural; MC is the method for Check | Paper wants a second-method Check validation (Plan C) |
| Shuffle-friendly urate recalibration (Plan I) | Quota-exact urates want a re-estimation | After Plan H; next discount-factor re-estimation |
| `TODO_HARK_0171_UPDATE.md` rewrite/retire | Path superseded (0.17.1 released 2026-02-02 but branch needs newer pinned SHA); audited in `COMMENT_AUDIT_FINDINGS.md` | Merge-to-master event (its Step 3/4) |
| HARK re-pin bump `d15660d5` → `ce0cb5d6`+ in pyproject | Local editable HARK in dev; pin only matters for clean clones | Next release-tag push (REQUIRED then — clone ImportErrors otherwise) |

## Validation cascade (per cascade-gate memory rule)

Unchanged from 2026-06-03 — for any item with numerical implications:

1. **Smoke gate (T2.2 once available)**: <8 min at Reduced_Run, Check+TaxCut. HALT if any decisive cell drifts >0.5%.
2. **HS_Only full welfare-6 (excl. ui_norec)**: ~15–30 min. HALT on >0.5% decisive drift.
3. **Reduced_Run full welfare-6**: ~45–90 min. HALT on >0.5% decisive drift.
4. **Baseline 1× quota (D=4900/HS=9800/C=17640)**: ~60 min; paper-precision; 4-moment drift table in headline.
5. **Baseline 5× brute-force (`HAFISCAL_AGENTCOUNT_TOTAL=160000`)**: ~5 h; only on explicit request for paper-grade SE.

## Success metric

**Primary**: Plan H QE-matching report delivered under the canonical approach, with the `HAFISCAL_QE_FIDELITY=1` comparator within ±3% of published QE, and Baseline 4-seed welfare SEs ≤0.5% rel on decisive cells.

**Secondary**: G1 + O1–O4 sign-off rows recorded; Mandate-1 merge-back decision made; Mandate-2 inert deliverables (registries/specs/ledgers) landed; BUG-050 disposition decided (not necessarily implemented).

## Failure handling

- **T1.1 SEs exceed gate**: do NOT re-estimate; diagnose seed-level variance first (more seed offsets), then escalate to owner with the multi-seed table.
- **T1.2 QE gap exceeds ±3% under QE_FIDELITY**: stop, characterize per the QE-comparison report procedure (both-sided header), file divergence in the QE ledger; never tune toward QE.
- **T1.3 G1 reversed by owner**: escalate out of the dolo-plus effort entirely (re-estimation territory); freeze behavior-affecting children.
- **T1.5 BUG-050 fix moves UI numbers**: expected (legacy ~1.34 → different under correct wiring); classify ERROR vs SAMPLE per governance rule; default-ON fix + toggle-off + ledger entry if ERROR.
- **T1.6 parent advanced with conflicts**: rebase side branch first; if conflicts touch generated artifacts, regenerate rather than hand-merge.

## Open questions for user judgment

1. **BUG-050 fix authorization (T1.5)?** Research decision — changes UI numbers now that UI is reportable again. Approve implementation, or keep GUARDED-nan until after Plan H?
2. **RAM upgrade capex (~$300, T2.6)?** Carried from 2026-06-03 Q1, still unanswered; host at 54 GiB.
3. **Make `HAFISCAL_USE_SOLUTION_CACHE=1` default-on?** Carried Q3; Option D harness sets it, global default would be a polish item.
4. **Speedup track: resume or keep parked?** Carried Q4 — Tier-2 items (T2.1–T2.5) are all open; confirm whether any should run alongside Plan H or stay parked until after it.
5. **`TODO_HARK_0171_UPDATE.md` + `INTERIM_REPRODUCTION_INSTRUCTIONS.md` disposition**: rewrite to the pinned-SHA reality now, or leave as-is until the merge-to-master event their Step 3/4 anticipates?
