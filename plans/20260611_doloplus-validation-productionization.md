# Dolo-plus validation harness: re-baseline + pytest-ify + extend coverage

**Status:** ACTIVE

**Date:** 2026-06-11 · **Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` · **Master:** `20260611_doloplus-integration-master.md`
**Premise:** `Code/HA-Models/dolo_plus_validation/` holds two one-shot validation scripts: `check_vs_hafiscal_code.py` (EGM↔HAFiscal-solver cFunc compare, rel<1e-3 gate, `EGM_FACTOR_MODE={standard|hafiscal_code}` toggle) and `test_euler_at_point.py` (Euler residual + cFunc agreement). Two problems: (1) **the reports are stale** — they predate the BUG-047 fix (FIXED default-ON 2026-06-04; `_permgrofac.py`), so `check_vs_hafiscal_report.txt` still shows MODE-standard FAIL 5.19e-2 from the pre-fix world; (2) **`test_euler_at_point.py` is a pytest-collection hazard** — 0 `def test_` functions, no `__main__` guard, module-level execution: `pytest Code/` runs a full solve at collection time.
**Execution contract:** standalone, idempotent; gates may only be *tightened* silently — any relaxation beyond 1e-3 is documented + flagged to the owner.

## Phases

### P1 — re-baseline FIRST (1 agent, 0.5-1 day; feeds ledger D-01/G1)
Run both scripts under today's defaults (`HAFISCAL_PERMGROFAC_FIX=1`, `HAFISCAL_INTERPRETATION=ESC`, the re-estimated calibration). Expected: `EGM_FACTOR_MODE=standard` now MATCHES production (pre-fix it failed because the *code* omitted the `PermGroFac^(-CRRA)` factor; the fix landed). Diagnose any residual >1e-3 — the pre-fix MODE-B residual was 2.84e-3, likely grid density/interpolation; bisect `aCount`/`aMax` to attribute it. Regenerate `check_vs_hafiscal_report.txt`; append a **post-fix reconciliation addendum** to `FINDING_permgrofac_marginal_value_factor.md` (this is the G1 evidence pack input). A legitimate FAIL for non-BUG-047 reasons → ledger finding, not a silent gate bump.

### P2 — pytest restructuring (1 agent, 1 day, ∥ with P1)
- `dolo_plus_validation/conftest.py`: fixtures — patch `sys.argv` **before** importing `Parameters` (CLAUDE.md rule), chdir to `FromPandemicCode/`, pin env flags per test, session-scoped solved-agent cache (explicit cache keys so regime-parameterized tests can't leak state).
- Convert `test_euler_at_point.py` → guarded `main()` + real `test_*` functions (**kills the collection hazard**; CLI invocation still works).
- Wrap `check_vs_hafiscal_code.py` machinery as importable; add `test_yaml_vs_code_cfunc.py`.
- Tiering: **fast tier** (YAML-driven EGM Euler residuals only — no HAFiscal solve, seconds, default-collected) vs `@pytest.mark.slow` (full `AggFiscalType` solve compares).

### P3 — coverage extension (2 agents ∥, 1-1.5 days)
- (a) cFunc compare over **all 6 micro states** (today: employed-only `cFunc[0]`) on a probe m-grid.
- (b) Euler-residual grid: z ∈ {0..5} × m ∈ {0.5, 1, 2, 5, 20} × macro ∈ {normal ADF=1; recession Cratio=0.9, κ=0.3} — keeps the ADF coupling numerically exercised (OPEN_QUESTIONS item 4).
- (c) Regime matrix: `HAFISCAL_PERMGROFAC_FIX=1` (default) = required-PASS; `=0` = skip-if the `_pgf_legacy/` calibration is absent (`_permgrofac.py.permgrofac_calib_path` raises by design — the matched-pair guard).

### P4 — wire docs (0.5 day)
Update `PLAN_yaml_vs_code_check.md` status; record gate values into the eqn-registry rows (`appendix:euler`, `yaml:arvl_to_dcsn` transition) if the registry exists.

## File targets
All inside `Code/HA-Models/dolo_plus_validation/`: new `conftest.py`, `test_yaml_vs_code_cfunc.py`; restructured `test_euler_at_point.py`; regenerated reports; FINDING addendum. Zero `FromPandemicCode/` changes.

## Verification
```
pytest Code/HA-Models/dolo_plus_validation -m "not slow" -q     # <~60 s, green
pytest Code/HA-Models/dolo_plus_validation -q                    # slow tier green
pytest Code/ reproduce/ --collect-only -q                        # NO module-level executions anymore
python Code/HA-Models/dolo_plus_validation/test_euler_at_point.py     # CLI still works
python Code/HA-Models/dolo_plus_validation/check_vs_hafiscal_code.py  # CLI still works
bash reproduce_min.sh
```

## Risks / rollback
Re-baseline may fail legitimately (non-BUG-047 residual) → becomes a ledger finding with bisection evidence. Solve-cache leakage across regimes → explicit cache keys. Rollback: the dir is self-contained; revert it. **Effort:** ~3-4 agent-days; ~2 days wall with 2-3 agents.
