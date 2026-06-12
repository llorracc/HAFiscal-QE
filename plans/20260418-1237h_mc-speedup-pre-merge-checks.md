# MC speedup: pre-merge validation checks

**Created:** 2026-04-18 12:19
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_matsya_MC-speedup-attempt`
**Depends on:** `plans/20260418_mc-speedup-measurements.md` (the speedup plan)
**Goal:** Close the remaining validation gaps so the speedup code can be merged into the main branch with confidence.

## Context

The speedup work adds six new files under `Code/HA-Models/FromPandemicCode/`:
`validate_mc_crn.py`, `run_mc_crn_validation.py`, `welfare6_scenario.py`,
`run_welfare6_parallel.py`, `validate_duration_pool.py`, `validate_solve_pool.py`.

Zero edits to existing files. Scenario-parallelism gave 9.88× on Baseline
(5 h 45 min → 35 min), welfare6 table matches serial at 2-decimal precision.

Four gaps surfaced in the audit:

1. **`sys.argv` clobber** in `welfare6_scenario.py` may silently break
   sensitivity parametrizations (CRRA1, CRRA3, Rfree variants, etc.)
   that override parameters via `sys.argv`.
2. **Idempotency** of the parallel pipeline across back-to-back runs
   has not been verified.
3. **CRN validations** haven't been re-run since the recent additions
   of `--ad-tolerance`, `--agent-count-total`, and `--solve-workers`.
4. **Artifact directories** (pickles, logs) are not in `.gitignore`.

Two more issues flagged in the audit but not required for merge:
- Subprocess crash handling (robustness, not correctness).
- NPV byte-identity (`np.cumsum` vs loop); user accepted 2-decimal precision as sufficient.

## Step 1 — Fix `sys.argv` handling in `welfare6_scenario.py`

### Problem

The script currently does, near the top of the module:

```python
_ORIG_ARGV = sys.argv[:]
sys.argv = ["welfare6_scenario"]
```

Later: `args = p.parse_args(_ORIG_ARGV[1:])`.

`Parameters.py` reads numeric overrides (Rfree, CRRA, IncUnemp) from
`sys.argv`. Sensitivity parametrizations (CRRA1, CRRA3, Rfree_1005,
Rfree_1015, ADElas, Rspell_4, LowerUBnoB, Splurge0) rely on this. My
clobber throws them away, so e.g. running
`python welfare6_scenario.py --scenario base --parametrization CRRA1`
produces a run at CRRA=2 instead of CRRA=1 — silently.

### Fix

Partition the original argv into (a) arguments our argparse consumes
and (b) everything else (which is what `Parameters.py` needs). Pass
(a) to argparse and leave (b) in `sys.argv`.

Simplest correct approach: run argparse in "known-args" mode and keep
the unknown args in `sys.argv`.

```python
# At module top, BEFORE Parameters is imported:
_ORIG_ARGV = sys.argv[:]
# We'll set sys.argv to the reduced form after argparse below.
sys.argv = ["welfare6_scenario"]   # placeholder so Parameters import
                                   # works with defaults while we
                                   # import HARK etc.

# In main():
args, remainder = p.parse_known_args(_ORIG_ARGV[1:])
sys.argv = ["welfare6_scenario"] + remainder
# (only safe if build_and_solve is called after this; currently it is)
```

But this doesn't help because `return_parameters` is called inside
`build_and_solve`, which runs after main()'s argparse. Simpler fix:
`return_parameters` accepts an additional `sys_argv_override` param
that my script can pass in. Even simpler: just set `sys.argv` to
`_ORIG_ARGV` minus my own flags before calling `build_and_solve`.

Adopt the simpler form: in main(), after argparse:

```python
# Rebuild sys.argv without our flags, preserving all others for
# Parameters.py's numeric overrides (Rfree, CRRA, IncUnemp).
_my_flags = {"--scenario", "--parametrization", "--baseline",
             "--solve-workers", "--duration-workers", "--ad-tolerance",
             "--agent-count-total", "--out-dir"}
_preserved = []
i = 1
while i < len(_ORIG_ARGV):
    tok = _ORIG_ARGV[i]
    if tok in _my_flags:
        # Skip this flag and its value (if any; --baseline is a flag
        # without a value).
        if tok == "--baseline":
            i += 1
        else:
            i += 2
    else:
        _preserved.append(tok)
        i += 1
sys.argv = [_ORIG_ARGV[0]] + _preserved
```

### Verify

1. Run `welfare6_scenario.py --scenario base --parametrization CRRA1`
   and confirm that the output pickle reports `CRRA == 1.0`.
2. Run `welfare6_scenario.py --scenario base` with no extra args and
   confirm `CRRA == 2.0` (default).

### Acceptance

Both cases produce the expected CRRA in the pickle; no AttributeError
or unknown-arg issue.

## Step 2 — Idempotency check

### Protocol

Run `run_welfare6_parallel.py --parametrization Reduced_Run` twice in
a row, to separate output directories. Compare the pickles
element-wise. They must be byte-identical.

If they differ, it suggests some state leaks between runs (e.g., the
monkey-patched `AggregateDemandEconomy.solve`, leftover pool objects,
global RNG state).

### Verify

```
mkdir -p /tmp/idempotency_{A,B}
run_welfare6_parallel.py --parametrization Reduced_Run --out-dir /tmp/idempotency_A/pickles --table-dir /tmp/idempotency_A/tables
run_welfare6_parallel.py --parametrization Reduced_Run --out-dir /tmp/idempotency_B/pickles --table-dir /tmp/idempotency_B/tables
```

Then a small Python script that `pickle.load()`s each pair and
compares `np.array_equal` on the three arrays per scenario.

### Acceptance

All 12 × 3 = 36 pairs byte-identical.

## Step 3 — Re-run CRN validations after recent additions

### Protocol

Run the three validation scripts with their default scenarios, making
sure the output "VERDICT" is green:

1. `python run_mc_crn_validation.py --parametrization HS_Only`
2. `python run_mc_crn_validation.py --parametrization Reduced_Run`
3. `python run_mc_crn_validation.py --parametrization Reduced_Run --with-ad`
4. `python validate_duration_pool.py --scenario recessionUI_AD --parametrization Reduced_Run --workers 4`
5. `python validate_solve_pool.py --scenario recessionUI_AD --parametrization Reduced_Run --workers 3`

### Acceptance

All 5 report "VERDICT: … numerically safe" and all arrays compared
show `max|Δ| = 0.00e+00`. Same as on the runs we did earlier in the
session.

## Step 4 — `.gitignore` for artifact directories

### New entries to add

In the repo-root `.gitignore`:

```
# MC-speedup parallel harness artifacts (this branch)
Code/HA-Models/FromPandemicCode/welfare6_scenario_results_*/
Code/HA-Models/FromPandemicCode/welfare6_parallel_logs/
Code/HA-Models/FromPandemicCode/validate_duration_pool_*/
Code/HA-Models/FromPandemicCode/validate_solve_pool_*/
Code/HA-Models/FromPandemicCode/Tables/*_parallel/
Code/HA-Models/FromPandemicCode/validation_mc_crn_*.pkl
```

`*.log` is already covered by a repo-wide rule, so validation `.log`
files are already ignored.

### Verify

`git status` after running the parallel pipeline should show no new
untracked files under the listed paths.

## Step 5 — Clean up test artifacts locally

Before committing anything, delete any stale pickles and tables left
from this session's validations so they don't accidentally get staged.

```
rm -rf Code/HA-Models/FromPandemicCode/welfare6_scenario_results_*
rm -rf Code/HA-Models/FromPandemicCode/welfare6_parallel_logs
rm -rf Code/HA-Models/FromPandemicCode/validate_duration_pool_*
rm -rf Code/HA-Models/FromPandemicCode/validate_solve_pool_*
rm -f Code/HA-Models/FromPandemicCode/validation_mc_crn_*.pkl
rm -rf Code/HA-Models/FromPandemicCode/Tables/*_parallel
```

Confirm `git status` is clean except for the intentional new files
(the fix in Step 1 and the `.gitignore` additions).

## Step 6 — Commit

Two commits, logically grouped:

- **Commit A (fix):** the `sys.argv` preservation change in
  `welfare6_scenario.py`, so sensitivity parametrizations work
  through the parallel harness.

- **Commit B (hygiene):** `.gitignore` entries for the artifact
  directories.

## Out of scope for pre-merge

- Subprocess-crash handling (robustness improvement; not a correctness gap).
- Switching `calculate_NPV` to the loop-based form to get byte-identical
  welfare6 scalars (user accepted 2-decimal precision as sufficient).
- Integration into `run_all.py` (happens after merge).
- Harmenberg / Numba / GPU.

## Execution order

1–4 → 5 → 6.

Steps 2–3 can overlap with Step 1 development as sanity anchors but
must be re-run after Step 1 to confirm nothing regressed.
