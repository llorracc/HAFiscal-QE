# Equation-tag registry: math-derive ↔ YAML ↔ code, machine-checked

**Status:** ACTIVE

**Date:** 2026-06-11 · **Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` · **Master:** `20260611_doloplus-integration-master.md`
**Premise:** The three math-derive docs carry consistent LaTeX `\tag{...}`s (~28 main + 14 appendix + ~20 harm); code cites them with a regular grammar (`math-derive (tag)`, `math-derive-appendix (tag)`, `math-derive-harm (tag/§)`) — but coverage is ~50% and nothing checks drift. The YAML's equation blocks are unbound to either. This plan formalizes the EXISTING convention into a bidirectional, machine-checked registry and raises citation coverage to ~100% via comment-only edits.
**Execution contract:** standalone, idempotent, numerically inert (comment-only in production files; all tooling in `dolo_plus_validation/`); no new .py in `FromPandemicCode/`.

## Registry design

`Code/HA-Models/dolo_plus_validation/eqn_registry.yaml`; key = namespaced tag (`main:` / `appendix:` / `harm:` / `yaml:`):
```yaml
- id: appendix:euler
  doc: history/20260331-mathematical-derivations-appendix.md
  anchor: "#5-euler-equation-and-egm"
  yaml_ref: equations.cntn_to_dcsn_mover.InvEuler     # dotted path into HAFiscal-doloplus-draft.yaml; null if N/A
  code:
    - {file: Code/HA-Models/FromPandemicCode/AggFiscalModel.py, symbol: solve_agg_cons_markov_alt, cite: "math-derive-appendix (euler)"}
  status: bound        # bound | code-only | doc-only | pending-decision
  decision: null       # e.g. D-01 when gated
```
**Bindings use (file, symbol, cite-string) — never line numbers** — resolved by AST walk, so the checker is drift-robust under edits and alarms loudly on symbol renames (desired).

## Checker

`Code/HA-Models/dolo_plus_validation/check_eqn_registry.py` + thin pytest wrapper `test_eqn_registry.py` (fast tier, <5 s, no solves):
- **Forward:** each entry's tag exists in its doc (`\tag{...}` or anchor); `yaml_ref` resolves in the parsed canonical YAML; each code ref's `symbol` exists (Python `ast`) and its `cite` string appears within that symbol's source span.
- **Reverse:** regex `math-derive(-appendix|-harm)? \(([A-Za-z0-9-]+)\)` over `FromPandemicCode/*.py` + `dolo_plus_validation/*.py`; any citation absent from the registry → error under `--strict`.
- `--bootstrap`: scrape all `\tag{}`s from the three docs + all existing in-code citations into a draft registry (~60 entries) for curation.
- `--assert-inert FILE...`: the AST comment-only proof (docstring-stripped `ast.dump` vs `git show HEAD:`) — used by every backfill commit.
- Coverage report: % doc tags bound to code; % YAML equation blocks bound to tags.

## Phases

- **P1 — checker + bootstrap** (1 agent, 1-1.5 days): build checker, run `--bootstrap`, write the pytest wrapper, get `--strict` passing on the bootstrapped (partial-coverage) registry.
- **P2 — curation + citation backfill** (4 agents ∥, single-file-owner each to avoid conflicts; 0.5-1 day each):
  - **R1** `AggFiscalModel.py`: solver bindings (`appendix:euler` — annotate the BUG-047 site with the post-fix regime note, wording gated on G1), budget `(m-budget)`, `(AD-factor)`, AD outer loop, MC-agg, NPV.
  - **R2** `Simulate.py` + `tm_methods.py`: `(L-eff)`, `(recession-duration)`, TM-agg, splurge, harm-tags around the TM/Q machinery.
  - **R3** `Welfare.py` + `welfare6_scenario.py` + `welfare6_tm.py`: `(CRRA-utility)`, `(SP-welfare)`, `(welfare-per-dollar)`, `(MRS-welfare)`, `(fiscal-multiplier)`.
  - **R4** `Parameters.py` + `EstimParameters.py` + `income_process_sst.py`: `(emp-persist)`, `(recession-duration)`, `(E-p-init)`, `(pLvl-cohort)`; **plus YAML-side**: add `# tag: appendix:euler`-style comment tags to each equation block of `HAFiscal-doloplus-draft.yaml`.
  Every backfill commit runs `--assert-inert` on its file.
- **P3 — reconcile** (1 agent, 0.5 day): merge, run `--strict`, publish the coverage report into this plan file's execution log.

## Verification
```
python Code/HA-Models/dolo_plus_validation/check_eqn_registry.py --strict     # exit 0
python ... --assert-inert <every touched production file>                      # comment-only proven
pytest Code/ reproduce/ -m "not slow" -q                                       # green
python -c "import yaml; yaml.safe_load(open('HAFiscal-doloplus-draft.yaml'))"  # YAML re-parses
```

## Risks / rollback
Symbol renames break bindings loudly (that IS the drift alarm). Merge conflicts in the 6k-LOC `tm_methods.py` → single-owner rule. Tag-name collisions across docs → namespacing. Rollback: registry+checker are additive; comment backfills revert per-file. **Effort:** ~3-5 agent-days; ~2 days wall with 4 agents.
