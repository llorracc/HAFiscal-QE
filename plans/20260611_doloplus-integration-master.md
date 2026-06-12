# Dolo-plus integration — master plan (umbrella + Phase 0 + decision-gate protocol)

**Status:** ACTIVE

**Date:** 2026-06-11 · **Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`
**Premise:** Integrate the codebase with the dolo-plus DDSL model description and the mathematical-derivation md docs. Inventory (2026-06-11): canonical YAML = `HAFiscal-doloplus-draft.yaml` (175 lines, ESC optimizer-stage, 2026-06-03); build provenance = `matsya_turns/` (turn2..6 fragments+verdicts, `OPEN_QUESTIONS.md`); Bellman spec = `HAFiscal-bellman-for-matsya.md`; math-derive trio = `history/20260331-mathematical-derivations-{TM-MC-convergence,appendix,harmenberg}.md` (LaTeX `\tag{}`d; cited from code as `math-derive*(tag)` at ~50% coverage); validation harness = `Code/HA-Models/dolo_plus_validation/` (EGM↔solver compare + Euler check + the BUG-047 FINDING).
**Fact-corrections this planning round established (bake in everywhere):**
1. **BUG-047 is FIXED (default-ON, 2026-06-04)** — `_permgrofac.py` matched-pair (solver math + calibration path + regime stamp), production ESC calibration re-estimated, headline multipliers confirmed unchanged. The harness reports (`check_vs_hafiscal_report.txt` etc.) **predate the fix** and are stale.
2. `HAFiscal-doloplus-from-matsya.yaml` is a matsya session **transcript** (prose + embedded yaml block), not a competing spec.
3. `dolo_plus_validation/test_euler_at_point.py` has **0 `def test_` functions + module-level execution** → `pytest Code/` executes a full solve at collection time. Real hazard.

## The plan set (children)

| plan | scope | blocking deps |
|---|---|---|
| this file | Phase 0 canonicalization + gates + verification matrix | — |
| `20260611_doloplus-eqn-tag-registry.md` | Bidirectional tag registry (math-derive ↔ YAML ↔ code) + drift checker + citation backfill | Phase 0 |
| `20260611_doloplus-validation-productionization.md` | Re-baseline + pytest-ify + extend the validation harness | Phase 0 |
| `20260611_doloplus-spec-gap-ledger.md` | The 10 gaps + 4 overrides + BUG-047 reconciliation as evidence-packed, owner-gated ledger | Phase 0 (D-01 also consumes the re-baseline) |
| `20260611_doloplus-orchestrator-spec.md` | Normative spec of the out-of-YAML layer (AD loop, splurge, cohorts, demographics, measure) | Phase 0 |

Sequencing: Phase 0 (~0.5-1 day) → registry ∥ validation ∥ orchestrator-spec fully parallel; ledger spans (consumes validation P1 for D-01; owner gates async + non-blocking). The separate doc-rationalization plan set should link these artifacts (documentation map), not duplicate them.

## Phase 0 (1 agent, sequential)

1. **Canonicalize the YAML**: add a `STATUS: CANONICAL` comment-header block to `HAFiscal-doloplus-draft.yaml` — canonical ESC optimizer-stage spec; provenance `matsya_turns/`; companions `HAFiscal-bellman-for-matsya.md`, `HAFiscal-doloplus-spec-decisions.md` (forthcoming), `HAFiscal-doloplus-orchestrator.md` (forthcoming); validation gates in `Code/HA-Models/dolo_plus_validation/`. **Do not rename the file** — `test_euler_at_point.py:36` hardcodes the path. Verify: `python -c "import yaml; yaml.safe_load(open('HAFiscal-doloplus-draft.yaml'))"`.
2. **Demote the transcript**: `git mv HAFiscal-doloplus-from-matsya.yaml matsya_turns/turn1_from_matsya_transcript.yaml.md` (it is turn-1 provenance; `.md` reflects content). Grep-update referencing files (known: `plan_hafiscal_dolo_plus_v2.md`, `plan_hafiscal_dolo_plus_via_matsya.md`; re-grep at execution).
3. **Skeleton spec-decisions doc**: `HAFiscal-doloplus-spec-decisions.md` (repo root, co-located with YAML + bellman doc) — decision table schema: `ID | decision | status ∈ {ADOPTED, VALIDATED, OWNER-CONFIRM-PENDING} | evidence links | sign-off`. Stub rows D-01..D-05 (content filled by the ledger plan).
4. **Baseline snapshot**: record `pytest Code/ reproduce/ --collect-only -q` count, `bash reproduce_min.sh` exit, checksums of current `dolo_plus_validation/*report*.txt` — the "before" picture all seams diff against.

## Decision-gate protocol (normative for all children)

- **G1 — BUG-047 confirm-and-reconcile:** the owner signs that the default-ON fix is final. Agents then re-baseline the harness, append the post-fix addendum to `FINDING_permgrofac_marginal_value_factor.md`, and update YAML comments to note code now agrees by default. If the owner instead reverses the fix → **escalate out of this effort entirely** (re-estimation territory). Never executed silently.
- **O1-O4 — the four overrides re-examination** (owner explicitly requires re-examination; see memory `project_doloplus_four_overrides_reexamine`): O1 z-indexed `PermGroFac`; O2 state-contingent `IncShkDstn[z]`; O3 `z_d=z` / `z_nxt=z_d` carry; O4 ADF-applied-once. Each = an evidence-packed sign-off row (ledger plan produces the packs; recommendations lean KEEP, with O4 already numerically validated).
- All **inert** work (tags, registries, docs, schemas, pytest plumbing) proceeds regardless of gate state. Nothing behavior-affecting executes without a signed row. **Re-estimation is out of scope for the entire plan set.**

## Global verification matrix (phase boundaries; full set at final sweep)

```
pytest Code/ reproduce/ --collect-only -q                                  # no module-level executions
pytest Code/ reproduce/ -m "not slow" -q
pytest Code/HA-Models/dolo_plus_validation -q                              # slow tier
python Code/HA-Models/dolo_plus_validation/check_eqn_registry.py --strict
python Code/HA-Models/dolo_plus_validation/check_eqn_registry.py --assert-inert <touched FromPandemicCode files>
bash reproduce_min.sh
python -c "import yaml; yaml.safe_load(open('HAFiscal-doloplus-draft.yaml'))"
```

**Totals (set):** ~11-15 agent-days; ~4-6 days wall with 4-6 agents. **Phase-0 risk:** trivial (one gated file move). Rollback: revert branch commits.
