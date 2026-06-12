# Env-flag registry: single source + permanent guard test

**Status:** ACTIVE

**Date:** 2026-06-11 · **Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` · **Umbrella:** `20260611_doc-rationalization-overview.md`
**Premise:** 130 `HAFISCAL_*` environment flags control behavior; 122 are undocumented (94%). Existing partial docs are scattered: `FromPandemicCode/tm_methods.py:45-90`, `jax_mc_speedup/README.md` flag table, `do_all.py:25-41`, `solution_cache/__init__.py`, CLAUDE.md (8 flags), module docstrings. This is the #1 comprehensibility obstacle.
**Execution contract:** standalone, idempotent, documentation-only (plus one new guard test), green gate at end.

## Objective

One authoritative, machine-guarded registry: `Code/HA-Models/docs/ENV_FLAGS.md`, kept current forever by `Code/HA-Models/test_env_flag_registry.py` (a new flag without a registry entry fails `pytest Code/`).

## Registry format (decided)

One markdown file; one `### HAFISCAL_<NAME>` heading per flag, grouped in subsystem sections (TM kernel / MC+shuffle+CRN / JAX / welfare6 / estimation+interpretation / pipeline+infra / diagnostics). Required fields per heading:
```
### HAFISCAL_TM_CFUNC_OFFSET
**Default:** `mc`
**Values:** `mc` | `tm`
**Status:** live            <- live | diagnostic | deprecated | archived-only
**Read by:** Code/HA-Models/FromPandemicCode/tm_methods.py
**Purpose:** BUG-041 fix — which CFunc cell the TM ADF uses (1-period offset vs MC). Default matches MC.
**Refs:** BUGS_private/HAFiscal_BUG-041_*.md
```
Rejected alternatives: a 130-row md table (unreadable, agents mangle pipes); a Python introspection module (couples 100+ read sites to new code — a refactor, not documentation; `_interpretation.py` already exists for the one flag complex enough to deserve code-level enforcement).

## Guard test design

`Code/HA-Models/test_env_flag_registry.py` (regex scan, no imports, <1 s):
- Scan scope: `Code/HA-Models/**/*.py`, **excluding** `*_archive/` and `__pycache__`.
- Read-site patterns (all 4 occur; verified counts 134/7/8): `os.environ.get('HAFISCAL_X')`, `os.getenv(...)`, `os.environ['HAFISCAL_X']`, `'HAFISCAL_X' in os.environ` — including `_os.`-aliased forms (`tm_methods.py` does `import os as _os`).
- Assertions: **completeness** (every scanned flag has a `### HAFISCAL_<NAME>` heading); **no-zombies** (every heading with Status `live|diagnostic` appears in the scan; `deprecated|archived-only` exempt); **structure** (every heading carries the required fields).
- `ALLOWED_DYNAMIC` list for dynamically-constructed names (none known today — `HAFISCAL_RUN_STEP_1..5` are literal — but the hook must exist).

## Phases

- **Phase A — mechanical inventory** (1 agent, ~30 min). Run the read-site regexes; emit worklist: flag → read sites (file:line) → default expression → adjacent comment block. Cross-grep each flag in `plans/`, `BUGS_private/`, `conclusions_private/` for provenance. Output: scratch table (not committed).
- **Phase B — entry authoring** (4-6 agents ∥ by subsystem, ~1-2 h each). Batches: (1) `HAFISCAL_TM_*`; (2) MC/shuffle/CRN (`MC_SHUFFLE`, `SHUFFLE_MRKV_TRANSITION`, `SHUFFLE_NEWBORN_FIX`, agent counts…); (3) JAX (`USE_JAX_*`, `JAX_MC_*` incl. the flags documented only in `jax_mc_speedup/README.md`); (4) `WELFARE6_*`; (5) estimation/interpretation (`INTERPRETATION`, `UI_STATE_ENCODING`, `EDTYPES`, `PERMGROFAC_FIX`, `GICX_MODE`, `GIC_SHAVE_ON_GPF`, `SPLURGE_*`, `NM_*`); (6) pipeline/infra (`RUN_STEP_*`, `PARALLEL_SOLVE`, `SERIAL`, `NO_FORK`, `DUR_WORKERS`, `QE_FIDELITY`, cache flags). Each agent reads the read-site code + linked BUG/plan and writes its section. **Highest-blast-radius entries to get exactly right:** `HAFISCAL_INTERPRETATION` (point at `_interpretation.py` as the code-level source; matched-triple rule {PermGroFac, calibration, interpretation}), `UI_STATE_ENCODING` (default `bug_fix` per `EstimParameters.py:191`), `SHUFFLE_MRKV_TRANSITION` (canonical default `stratified` via the EstimParameters canonical block; plain `'shuffle'` is the +8.26%-UI footgun — cite `conclusions_private/2026-06-10_welfare_method_unified_MC.md`), `QE_FIDELITY` (the legacy escape hatch), `TM_AMAX` (=1300, the most-patient-College-atom rationale — copy the WHY from the EstimParameters canonical block).
- **Phase C — reconcile + enable guard** (1 integrator, ~1 h). Merge sections; resolve contested entries (semantically ambiguous flags get Status `diagnostic` + a `**Needs-owner-review:**` field — never guess); write + pass the guard test; add idempotent pointer lines to CLAUDE.md and `Code/HA-Models/README.md`; append "full registry: Code/HA-Models/docs/ENV_FLAGS.md" pointers to the four legacy doc blocks (do not delete them — that is comment-hygiene-plan territory).

## File targets

New: `Code/HA-Models/docs/ENV_FLAGS.md`, `Code/HA-Models/test_env_flag_registry.py`. Pointer-line edits: `CLAUDE.md`, `Code/HA-Models/README.md`, `FromPandemicCode/tm_methods.py` (comment-only), `jax_mc_speedup/README.md`, `solution_cache/__init__.py` (comment-only).

## Verification

```
pytest Code/HA-Models/test_env_flag_registry.py -v          # both assertions green
pytest Code/ reproduce/ --collect-only -q                    # collection count = before + 1
pytest Code/ reproduce/ -m "not slow" -q                     # green
git diff --stat                                              # only the new docs/test + pointer lines
```

## Risks / rollback

Regex misses an exotic read pattern → the pattern list is data; extend it. Rollback: delete the two new files + revert pointer lines (zero behavior surface). **Effort:** ~6-10 agent-hours, 1 session. **Risk: low.**
