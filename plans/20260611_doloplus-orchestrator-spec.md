# Orchestrator spec: the normative out-of-YAML layer

**Status:** ACTIVE

**Date:** 2026-06-11 · **Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` · **Master:** `20260611_doloplus-integration-master.md`
**Premise:** The canonical YAML (`HAFiscal-doloplus-draft.yaml`) deliberately encodes only the optimizer **stage**; everything else — splurge accounting, the AD outer loop, the 21-cohort sweep, demographics, measure choice — is "orchestrator-level, out of scope" with no normative description anywhere. Result: (YAML stage) + (nothing) ≠ the model. This plan writes the missing half: **`HAFiscal-doloplus-orchestrator.md`** (repo root, co-located with the YAML and `HAFiscal-bellman-for-matsya.md`), so (YAML stage) + (orchestrator spec) = the whole model. Closes gaps G-02/03/04/07/08/09/10 of the spec-gap ledger.
**Execution contract:** standalone, idempotent, doc-only outside `dolo_plus_validation/` (optional comment cross-refs in production files follow the eqn-registry plan's `--assert-inert` rule).

## Section blueprint
Each section = normative statement + code refs as `file::function` (verified against the working tree, never line numbers) + math-derive tag bindings + eqn-registry IDs:

1. **Scope & relation to the YAML stage** — Convention 1; optimizer-only mass (1−ς); what "out of scope" means operationally.
2. **Interpretations: ESC vs CDC** — `Code/HA-Models/_interpretation.py` singleton; exactly what differs (the out-of-YAML simulation asset rule); the matched-triple rule {PermGroFac regime, calibration, interpretation}.
3. **Splurge accounting** — bound-pair: `C_tot = c_opt·(1−ς)·p + ς·Y_tot` lineage; (1−ς) normalization cancellation; ς provenance per education group (cross-ref ledger D-06 — do NOT silently pick a value).
4. **AD outer loop** — pseudo-code of the fixed point (`AggFiscalModel.py::solve` AD iteration: max iters, tolerance, damping/stepsize `Cfunc_iter_stepsize`), CRule update from realized Cratio, **realized-vs-perceived** Cratio distinction (G-04, G-10); the TM-side mirror (`tm_methods.py::run_ad_tm` Phase-1 training / Phase-2 CFunc-propagated evaluation, incl. the 2026-06-11 forked durations loop).
5. **Macro-state machinery** — hierarchical Mrkv encoding (`Mrkv = num_micro_states·Macro + Micro`; 6 micro under `bug_fix`), RecState mapping, recession-duration weighting (`math-derive-appendix (recession-duration)`), and a **recession calibration schema** (G-03).
6. **21-cohort β×education sweep** — DiscFacDstns provenance (`Results/DiscFacEstim_*`), GIC cap (BUG-053: shave on GPF, theGICfactor=0.9995), and a **cohort calibration-file schema** at `Code/HA-Models/dolo_plus_validation/schemas/cohort_calibration_schema.md` (G-07).
7. **Demographics** — LivPrb perpetual-youth discount; T_age=200 forced-death = simulator-only cap (G-08); newborn pLvl init distribution (G-09); tags `(L-eff)`, `(E-p-init)`, `(pLvl-cohort)`.
8. **Measure: P vs Harmenberg-Q** — YAML is P-only by design; where Q enters (`tm_methods.py` neutral-measure construction; `Simulate.py` Run_Dict flag); pointers into math-derive-harm (G-02).
9. **pLvl-growth-during-unemployment** — flag semantics (`HAFISCAL_PLVL_GROWS_DURING_UNEMP`, default off = QE-style; BUG-040 lineage) (G-06).
10. **Aggregation & outputs** — TM-agg / MC-agg / NPV / fiscal-multiplier chain (`Simulate.py`, `tm_methods.py::calculate_NPV`, `Welfare.py`); the welfare-6 formula and the canonical MC+CRN+stratified-shuffle method (cite `conclusions_private/2026-06-10_welfare_method_unified_MC.md`).

## Phases
- **P1 — section drafting** (3 agents ∥, ~1 day each): S1 = §2-4 (interpretation/splurge/AD; `AggFiscalModel.py`-heavy); S2 = §5-7 (Markov/cohorts/demographics; `Parameters.py`/`EstimParameters.py` + schemas); S3 = §8-10 (measure/aggregation; `tm_methods.py`/`Simulate.py`/`Welfare.py`). **Every claim carries a code citation verified against the working tree.**
- **P2 — integration** (1 agent, 0.5-1 day): merge; deduplicate against `HAFiscal-bellman-for-matsya.md` (link, don't restate); add eqn-registry rows; cross-link from the YAML header.
- **P3 — consistency audit** (1 agent, 0.5 day): run the validation suite; spot-verify ≥3 quantitative claims per section against code (AD tol/iters, T_age, ς, urates, theGICfactor).

## File targets
New: `HAFiscal-doloplus-orchestrator.md` (root); `Code/HA-Models/dolo_plus_validation/schemas/{cohort_calibration_schema.md, recession_state_schema.md}`. Edits: eqn-registry rows; one pointer line in the YAML header. No production `.py` beyond optional `--assert-inert`-proven comment cross-refs.

## Verification
```
git diff --stat            # doc-only outside dolo_plus_validation/
python Code/HA-Models/dolo_plus_validation/check_eqn_registry.py --strict   # incl. new rows
pytest Code/ reproduce/ -m "not slow" -q
bash reproduce_min.sh
```

## Risks / rollback
Drift vs the 2.5k/6k-LOC modules under active development → registry bindings are the alarm; symbols not lines. The ς discrepancy is a ledger row (D-06), never silently resolved. Rollback: docs are additive. **Effort:** ~3.5-4.5 agent-days; ~2 days wall with 3 agents + integrator.
