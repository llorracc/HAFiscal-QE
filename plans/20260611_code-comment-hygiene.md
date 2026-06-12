# Code-comment hygiene: stale/contradicted comments, comment-only-proven

**Status:** ACTIVE

**Date:** 2026-06-11 · **Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` · **Umbrella:** `20260611_doc-rationalization-overview.md`
**Premise:** Live code carries comments that have drifted from reality: forward-looking promises whose events already happened, claims contradicting decided methodology, unversioned hard numbers from superseded calibrations, paths to since-archived files. ~166 BUG-NNN refs + plan refs + phase refs exist with no staleness check. Function-docstring coverage ~55% in the big modules.
**Execution contract:** standalone, idempotent; every change is comment/docstring-only and **mechanically proven** (AST gate); contradictions surface to the owner, never silently fixed.

## Verdict classes + actions

1. **HISTORICAL-OK** — record of a past fix (most BUG-NNN refs). *No edit.*
2. **STALE-FORWARD-REF** — "X will happen after Y" where Y happened. Rewrite in past tense stating the current default + what resolved it + ref — only if the code's actual default matches; else escalate as class 3.
3. **CONTRADICTED** — comment contradicts a documented decision or the code. **Never edit silently.** Row in the findings doc (file:line, claim, contradicting source, behavior-implicated?) → owner triage → only then rewrite.
4. **ORPHAN-REF** — points at a moved/archived file → fix the path string.
5. **UNVERSIONED-CLAIM** — hard numbers without provenance → append `(as of <ref/date>)` or replace with a pointer to the source-of-truth; if the numbers are now *wrong*, escalate as class 3.

**OWNER RULINGS (2026-06-11) — all four PRE-APPROVED for unattended execution** (anything NEW found during execution still defaults to log-only/no-edit): (1) the UI comment rewrite, (2) the tm_a_indexed comment rewrite, (3) the GICx re-derive+stamp, (4) **docstring backfill — NAMED LIST ONLY (owner ruling)** — add missing docstrings to exactly these undocumented production entry points (other undocumented functions are COUNTED in the findings doc for a future sized pass, not filled) (`Welfare.Welfare_Results`, `Parameters.return_parameters`, `welfare6_scenario.build_and_solve`/`main`, `EstimAggFiscalMAIN` module+entry) — purely additive, AST-gate-exempt (the gate strips docstrings before comparing).

**Pre-seeded CONTRADICTED rows (found during planning, 2026-06-11) — rulings above apply:**
- `FromPandemicCode/Simulate.py:251-258` — "UI deprecated from headlines": **contradicts** the 2026-06-10 decision that `ui_rec`/`ui_rec_AD` ARE reportable (MC + stratified-shuffle; `conclusions_private/2026-06-10_welfare_method_unified_MC.md`). Entangled with BUG-050 income wiring — a **behavior question**; owner must rule on the comment AND confirm BUG-050 status separately.
- `FromPandemicCode/AggFiscalModel.py:308-311` — `tm_a_indexed` default-False "flipped to True after Phase 4 validation lands": the flip is now governed by `plans/20260610_post_merge_canonicalize_default_solution.md` (Plan B) + the do_all Step-5a a-indexed wiring (2026-06-11); comment should state that, not promise.
- `FromPandemicCode/Parameters.py:102-114` — GICx hard numbers written pre-BUG-053 (theGICfactor now 0.9995, shave on GPF not β); verify each number against the current calibration before stamping or rewriting.

## The mechanical comment-only gate (mandatory per touched file)

AST equality vs `git show HEAD:<file>` after stripping docstrings from both sides (docstrings are legal edits; ANY other AST change is forbidden). Inline snippet (embed verbatim in commits/CI):
```python
python - "$FILE" <<'EOF'
import ast, subprocess, sys
f = sys.argv[1]
def strip(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body = node.body[1:] or [ast.Pass()]
    return tree
new = ast.dump(strip(ast.parse(open(f).read())))
old = ast.dump(strip(ast.parse(subprocess.check_output(['git','show',f'HEAD:{f}']).decode())))
assert new == old, f"NON-COMMENT CHANGE in {f}"
print(f"comment-only OK: {f}")
EOF
```

## Phases

- **Phase A — inventory** (4 agents ∥, ~2 h). Grep battery over the live set, partitioned: (1) the production core (`AggFiscalMAIN_reduced.py`, `AggFiscalModel.py`, `ConsMarkovModel.py`, `EstimAggFiscalMAIN.py`, `EstimAggFiscalModel.py`, `Parameters.py`, `EstimParameters.py`, `Simulate.py`, `Welfare.py`, `Output_Results.py`, `FiscalTools.py`, `tm_methods.py`, `income_process_sst.py`, `welfare6_scenario.py`, `welfare6_tm.py`); (2) remaining live FromPandemicCode; (3) `Code/HA-Models/` top + `jax_mc_speedup/`; (4) `do_all.py` + `reproduce/`. Patterns: `BUG-[0-9]{3}` → check the matching `BUGS_private/*` `**Status:**` line; `plans/2026` → exists? SUPERSEDED per INDEX?; forward-looking (`after .* lands|once .* completes|will be|for now|temporar|TBD|TODO|FIXME`); `deprecated|superseded|headline` → check vs the 2026-06-10 decisions; hard numerics near `GIC|beta|cap|factor`. Output: verdict tables merged into **`Code/HA-Models/docs/COMMENT_AUDIT_FINDINGS.md`** (the only new file).
- **Phase B — owner triage gate** (owner + 1 agent, async). All CONTRADICTED rows presented for ruling (pre-seeded rows above first). Non-blocking for classes 2/4/5.
- **Phase C — fix application** (2-3 agents, serialized per file, ~3-4 h). Apply templates; flag-documenting comment blocks compress to "see docs/ENV_FLAGS.md#hafiscal_x" pointers where the registry exists (else leave). One commit per file batch; AST gate after each file.
- **Phase C2 — docstring backfill** (1 agent, ~2 h, pre-approved). Add docstrings to the entry points listed in the rulings (signature, role, inputs/outputs, side effects, refs); match each module's existing docstring style; AST gate still run per file (docstrings exempt by construction).
- **Phase D — acceptance.** Full gate + FINDINGS disposition column (fixed / owner-deferred / wontfix).

## Verification
Per-file AST gate (automated); `python -m py_compile` sweep; `pytest Code/ reproduce/ -m "not slow" -q` green; `bash reproduce_min.sh` once at end; `git diff` line-class review (comments/docstrings only).

## Risks / rollback
Biggest risk = semantic drive-by ("fixing" code while fixing comments) — the AST gate makes it unlandable. Mis-rewriting history → templates keep the original ref; uncertain verdicts default to no-edit + FINDINGS row. Rollback: per-file revert (comment-only commits are independent). **Effort:** ~8-12 agent-hours + owner triage. **Risk:** medium → low via the gate.
