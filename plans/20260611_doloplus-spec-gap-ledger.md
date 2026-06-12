# Spec-gap ledger: every YAML↔code divergence, evidence-packed and owner-gated

**Status:** ACTIVE

**Date:** 2026-06-11 · **Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` · **Master:** `20260611_doloplus-integration-master.md`
**Premise:** Known divergences/gaps between the dolo-plus spec world (YAML + bellman doc + math-derive) and the code live scattered across `matsya_turns/OPEN_QUESTIONS.md`, `dolo_plus_validation/FINDING_*.md`, memories, and heads. They need ONE auditable ledger with evidence packs and explicit owner gates — populating `HAFiscal-doloplus-spec-decisions.md` (skeleton created by master Phase 0).
**Execution contract:** standalone, idempotent, **doc-only** (zero production diffs); owner gates async and non-blocking for all other work.

## Ledger rows

### Decision rows (owner sign-off required)
| ID | item | closure vehicle | gate |
|---|---|---|---|
| **D-01** | **BUG-047 reconciliation** — fix is FIXED default-ON 2026-06-04 (`_permgrofac.py` matched-pair: solver math + calibration path + regime stamp; calibration re-estimated; headline multipliers unchanged) | Evidence pack: `BUGS_private/HAFiscal_BUG-047_*.md` + `Code/HA-Models/_permgrofac.py` + the **re-baselined** harness report (validation plan P1) + YAML comment noting code now agrees by default | **G1**: owner signs the resolution is final; reversal escalates out of the whole effort |
| **D-02** | z-indexed `PermGroFac` (override O1) | Evidence: `Parameters.py` PermGroFac construction + `PLVL_GROWS_DURING_UNEMP` default + harness-extracted vector `[1.00453, 1.0×5]` matching the YAML | O1 sign-off (recommend KEEP — QE-faithful) |
| **D-03** | state-contingent `IncShkDstn[z]` (O2) | Evidence: the manual IncShkDstn build (`construct=False` pattern) + ConsMarkov canonical precedent + harness construction parity | O2 sign-off (recommend KEEP) |
| **D-04** | `z_d = z` / `z_nxt = z_d` carry (O3) | Evidence: AST-trace of expectation row-indexing in `solve_agg_cons_markov_alt` + the EGM↔HARK agreement already obtained under this convention | O3 sign-off (recommend KEEP) |
| **D-05** | ADF-applied-once (O4) | Evidence: already numerically VALIDATED (recession-point Euler residual PASS, `validation_report.txt`); explain the two HARK-side sites (budget vs ADFunc) as solver-vs-simulator paths, not double-count (OPEN_QUESTIONS §4) | O4 sign-off (recommend KEEP; mark VALIDATED) |
| **D-06** | splurge ς value reconciliation — ESC ≈ 0.2672 (`Result_AllTarget_ESC.txt` lineage) vs bellman-doc baseline ≈ 0.246 | Evidence: both provenances; statement of which is current and why | owner confirms the documented value |

### Gap rows (inert; no gate)
G-01..G-10 = the documented YAML↔code gaps, each with: gap statement · closure vehicle ∈ {YAML comment, orchestrator-spec section, schema file} · owning plan · done-criterion:
1. **G-01** PermGroFac indexing semantics (z-indexed within cohort; macro-state does NOT separately index) → YAML comment (cross-ref D-02).
2. **G-02** Harmenberg-Q wiring — YAML is P-measure-only by design → orchestrator-spec §measure.
3. **G-03** recession macro-state calibration files un-schema'd → schema file (orchestrator plan).
4. **G-04** AD outer-loop closure (realized Cratio → CRule update, damping) external to YAML → orchestrator-spec §AD.
5. **G-05** varsigma not in YAML calibration (intentional; out-of-stage) → YAML comment + D-06.
6. **G-06** pLvl-growth-during-unemployment assumption implicit → YAML comment + orchestrator-spec §flags.
7. **G-07** 21-cohort calibration-file schema absent → schema file.
8. **G-08** T_age=200 simulator-only cap → orchestrator-spec §demographics.
9. **G-09** newborn pLvl init distribution absent from YAML → orchestrator-spec §demographics.
10. **G-10** realized-vs-perceived Cratio feedback → orchestrator-spec §AD.

### ADOPTED/VALIDATED distillation
Distill the `matsya_turns/turn{2..6}_verdict.md` + `OPEN_QUESTIONS.md` conclusions into the spec-decisions doc's settled sections: Convention 1 (permanent-income normalization, Γ̂ factors inside expectations), ESC bound-pair reading, splurge-out-of-YAML, level-linear CRule, flat joint-Markov indexing, perpetual-youth LivPrb. One signing surface; turn files remain provenance.

## Phases
- **P1** (1 agent, 0.5 day): write all rows + the distillation into `HAFiscal-doloplus-spec-decisions.md`.
- **P2** (up to 6 agents ∥, 0.25-0.5 day each): one evidence pack per D-row — self-contained section with file:symbol citations + the verifying command. **Evidence must cite CURRENT post-fix code (re-grep; never copy from pre-2026-06-04 docs).**
- **P3** (owner, async, zero agent cost): review; status flips recorded in place; eqn-registry `decision:` fields updated where bound.

## Verification
Every D/G row has evidence + a runnable verifying command; `check_eqn_registry.py --strict` passes with `pending-decision` allowed only on unsigned rows; `git diff` shows doc-only changes.

## Risks / rollback
Owner latency → explicitly non-blocking. Stale-evidence risk → the re-grep rule above. Rollback: it's one md file. **Effort:** ~1.5-2.5 agent-days.
