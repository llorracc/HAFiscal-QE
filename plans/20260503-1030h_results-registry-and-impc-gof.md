---
date: 2026-05-03
status: revised-per-user-directives-2026-05-03-1045
keywords: [registry, atomic-runs, manifest, iMPC, Fagereng, goodness-of-fit, configuration-tracking, sqlite]
related_bugs: []
related_plans:
  - 20260425-1015h_reproduce-self-documenting-runs.md  # existing run-manifest infrastructure
---

> **Revised 2026-05-03 per user direction:**
> 1. Run-id: date LAST in filename (`<commit>_<confighash>_<date>`)
> 2. Atomicity: per-OUTPUT (not per-run-directory)
> 3. Index: SQLite from day one (not JSON)
> 4. Backfill: in scope (Phase 5)
> 5. GoF thresholds: accepted as drafted
> 6. Always-computed metrics: include all 4 additional ones (wealth share by Ed/WQ, MPC by WQ, median LWPI per cohort)
> 7. Implementation order: registry FIRST, then ESC TM-a end-to-end run.

# Results registry, atomic per-run storage, and iMPC-Fagereng GoF

## Goal

Replace the current filename-suffix accretion (`_TM_a_ESC.txt`, etc.) with a structured registry that:

1. **Atomically stores** all outputs of a single run together (Step 1 + Step 2 + Step 5 + tables + logs + figures)
2. **Tracks all configuration dimensions explicitly** in a manifest, not implicit in filenames
3. **Extends gracefully** to new dimensions without breaking existing entries
4. **Indexes for fast lookup** so warm-start and comparison reports can find the right artifact in O(1)
5. **Computes iMPC-Fagereng goodness-of-fit on every run** as a standard quality metric

Replaces the suffix scheme designed earlier today (which composes only the `(interpretation × step2_method)` cross-section cleanly and silently overwrites on `gicx_mode` / `nm_start_from_saved` / `num_starts` changes).

## Configuration dimensions to track

This is the set of options whose values change the produced artifacts. New dimensions are added by appending to this list — registry entries with fewer dimensions remain readable.

| Dimension | Type | Source |
|---|---|---|
| `interpretation` | enum: CDC, ESC | `HAFISCAL_INTERPRETATION` |
| `step1_method` | enum: MC | (only one for now; placeholder) |
| `step2_method` | enum: MC, TM-a | `HAFISCAL_STEP2_METHOD` |
| `step5_method` | enum: MC, TM | `sim_method` in `AggFiscalMAIN_reduced.py` |
| `step5_scope` | enum: Smoke_Test, Reduced_Run, Baseline, ADElas, ... | `--baseline` / `--smoke-test` flag |
| `gicx_mode` | enum: legacy, hardcoded, twophase | `HAFISCAL_GICX_MODE` |
| `nm_start_from_saved` | bool | `HAFISCAL_NM_START_FROM_SAVED` |
| `num_starts` | int | `HAFISCAL_NUM_STARTS` |
| `parallel_multistart` | bool | `HAFISCAL_PARALLEL_MULTISTART` |
| `nm_xatol` | float | `HAFISCAL_NM_XATOL` |
| `nm_fatol` | float | `HAFISCAL_NM_FATOL` |
| `crra` | float | `Parameters.py` (currently 2.0) |
| `rfree` | float | `Parameters.py` (currently 1.01) |
| `inc_unemp` | float | env override; default 0.7 |
| `inc_unemp_no_benefits` | float | env override; default 0.5 |
| `splurge_value` | float (computed in Step 1) | `Result_AllTarget*.txt` |
| `cohort_set` | list[int] | `HAFISCAL_WRAPPER_EDTYPES` |
| `bug_fixes_applied` | list[str] | implicit via commit; explicitly listed in manifest |

(Future additions: `q_method`, `Harmenberg_neutral`, etc. — append without breaking schema.)

## Directory layout (revised — per-output, date-last)

Each output is independently versioned with its OWN file. SQLite indexes them all by config + output type.

```
Results/registry/
  registry.db                             # SQLite (see schema below)
  outputs/
    splurge/
      d7595e3d_a1b2c3_20260503-103045.txt
      8158e65c_b4c2e7_20260502-1932.txt
    step2_cal/
      d7595e3d_a1b2c3_20260503-103045.txt
      ...
    step2_per_cohort_d/
      d7595e3d_a1b2c3_20260503-103045.txt
      ...
    step2_per_cohort_h/
      ...
    step5_allresults/
      d7595e3d_a1b2c3_20260503-103045.txt
    step5_multiplier_baseline/
      d7595e3d_a1b2c3_20260503-103045.tex
    step5_multiplier_reduced/
      ...
    step5_figures_cumulative_multipliers/
      d7595e3d_a1b2c3_20260503-103045.pdf
    table_estim_betas/
      d7595e3d_a1b2c3_20260503-103045.ltx
    table_non_targeted_moments/
      ...
    log_step2_edType0/
      ...
  views/                                  # symlink dir for human browsing
    latest_by_config/
      ESC_TMa_hardcoded_warm/
        step2_cal -> ../../../outputs/step2_cal/d7595e3d_a1b2c3_20260503-103045.txt
        step5_multiplier_baseline -> ../../../outputs/step5_multiplier_baseline/...
        ...
      CDC_MC_hardcoded_warm/
        ...
    latest_by_run/
      d7595e3d_a1b2c3_20260503-103045/
        step2_cal -> ../../../outputs/step2_cal/d7595e3d_a1b2c3_20260503-103045.txt
        ...
```

**Per-output atomicity:** every write goes to `<path>.tmp`, then `os.rename()` (POSIX atomic) to the final path. SQLite `INSERT OR REPLACE` for the corresponding row is atomic. A torn write leaves a `.tmp` file that's not indexed; a successful write atomically becomes the new "current".

**Run-id format:** `<commit_short>_<config_hash_short>_<date_local>` — date LAST so chronological sorting is by date within each (commit, config) bucket. `commit_short` = first 8 chars of git SHA. `config_hash_short` = first 6 chars of SHA-256 over canonicalized config dict. `date_local` = `YYYYMMDD-HHMMSS` in local time (matches existing repo conventions).

## SQLite schema

`Results/registry/registry.db`:

```sql
CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
INSERT INTO schema_version VALUES (1);

-- One row per (config, commit, date) — represents a single estimation/simulation run.
CREATE TABLE runs (
  run_id          TEXT PRIMARY KEY,    -- <commit_short>_<config_hash>_<date>
  config_hash     TEXT NOT NULL,        -- 6-char short hash
  config_json     TEXT NOT NULL,        -- canonical JSON of full config dict
  commit_sha      TEXT NOT NULL,        -- full SHA
  branch          TEXT,
  date_iso        TEXT NOT NULL,        -- ISO 8601 with tz
  date_local      TEXT NOT NULL,        -- YYYYMMDD-HHMMSS local
  hark_version    TEXT,
  python_version  TEXT,
  wall_total_sec  REAL,
  status          TEXT NOT NULL,        -- 'complete', 'partial', 'failed'
  warm_start_run_id TEXT,               -- nullable; FK to runs.run_id
  notes           TEXT
);
CREATE INDEX idx_runs_config_hash ON runs(config_hash);
CREATE INDEX idx_runs_date ON runs(date_iso DESC);
CREATE INDEX idx_runs_status ON runs(status);

-- One row per output file produced. Per-output atomicity: each entry is
-- written atomically (file rename + INSERT OR REPLACE).
CREATE TABLE outputs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id          TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  output_type     TEXT NOT NULL,        -- e.g. 'step2_cal', 'step5_multiplier_baseline'
  cohort          INTEGER,              -- nullable; for per-cohort outputs (0|1|2)
  start_idx       INTEGER,              -- nullable; for per-multistart-point outputs
  path            TEXT NOT NULL,        -- relative to Results/registry/
  content_hash    TEXT NOT NULL,        -- sha256 of content
  size_bytes      INTEGER,
  created_iso     TEXT NOT NULL,
  UNIQUE(run_id, output_type, cohort, start_idx)
);
CREATE INDEX idx_outputs_type_run ON outputs(output_type, run_id);
CREATE INDEX idx_outputs_run ON outputs(run_id);
CREATE INDEX idx_outputs_hash ON outputs(content_hash);

-- Metrics table: one row per (run, metric_name). Scalar values in
-- metric_value; complex metrics (arrays, dicts) in metric_json.
CREATE TABLE metrics (
  run_id          TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  metric_name     TEXT NOT NULL,
  metric_value    REAL,                 -- nullable; populated for scalar metrics
  metric_json     TEXT,                 -- nullable; populated for complex metrics
  PRIMARY KEY (run_id, metric_name)
);
CREATE INDEX idx_metrics_name ON metrics(metric_name);
CREATE INDEX idx_metrics_run ON metrics(run_id);

-- Bug fixes recorded per run (many-to-many via membership).
CREATE TABLE run_bug_fixes (
  run_id   TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  bug_id   TEXT NOT NULL,                -- e.g. 'BUG-039', 'WQ-MPC-table-fix'
  PRIMARY KEY (run_id, bug_id)
);
```

### Standard metric names

These are recorded for every Step-5-eligible run (Phase 2):

| metric_name | Type | Description |
|---|---|---|
| `step2_distance_d` / `_h` / `_c` | scalar | NM-converged objective per cohort |
| `step2_distance_total` | scalar | sum across cohorts |
| `median_lwpi_pct_error_d` / `_h` / `_c` | scalar | (model − data) / data × 100 |
| `wealth_share_by_ed_pct_error_d` / `_h` / `_c` | scalar | (model − data) per Ed group |
| `wealth_share_by_wq_pct_error_q1` / `_q2` / `_q3` / `_q4` | scalar | (model − data) per quartile (q1=poorest) |
| `mpc_by_wq_pct_error_q1` / `_q2` / `_q3` / `_q4` | scalar | (model − data) per quartile |
| `impc_fagereng_l2` | scalar | sqrt(sum((model − data)²)) over 5 horizons |
| `impc_fagereng_l1` | scalar | sum(\|model − data\|) |
| `impc_fagereng_max_abs` | scalar | max horizon-wise abs error |
| `impc_fagereng_full` | json | per-horizon arrays + deltas + pct errors |
| `step5_multiplier_check_with_ad` | scalar | (also `_no_ad`, `_first_round_ad`) |
| `step5_multiplier_ui_with_ad` | scalar | likewise |
| `step5_multiplier_tax_with_ad` | scalar | likewise |
| `step5_share_recess_check` | scalar | (also `_ui`, `_tax`) |
| `wq_mpc_pattern_correct` | scalar | 1 if mpc[poor] > mpc[rich], else 0 (sanity check post the table-flip bug) |
| `wall_time_step2_min` / `_step5_min` | scalar | per-step wall |

### Standard output types

| output_type | File extension | Per-cohort? | Description |
|---|---|---|---|
| `splurge` | .txt | no | Step-1 result |
| `step2_cal` | .txt | no | merged β/∇/GICx for all cohorts |
| `step2_per_cohort` | .txt | yes (cohort) | per-cohort cal record |
| `step2_per_start` | .txt | yes (cohort+start) | per-multistart-point record |
| `step5_allresults` | .txt | no | full population stats |
| `step5_multiplier_<scope>` | .tex | no | scope ∈ {baseline, reduced_run, smoke_test, ...} |
| `step5_base_results_<scope>` | .csv | no | summary CSV |
| `step5_figure_<name>_<scope>` | .pdf | no | each named figure separately |
| `table_estim_betas` | .ltx | no | regenerated table |
| `table_non_targeted_moments` | .ltx | no | regenerated table |
| `log_step1` | .log | no | |
| `log_step2_edType<N>` | .log | yes | |
| `log_step5` | .log | no | |

## Always-computed GoF metrics

Per user direction, every Step-5-eligible run records the following metrics (all written to the SQLite `metrics` table):

### 1. iMPC-Fagereng goodness-of-fit

**Source target** (`Estimation_BetaNablaSplurge.py:212`): `Agg_MPCX_target = [0.5056845, 0.1759051, 0.1035106, 0.0444222, 0.0336616]` — Fagereng et al. Figure 2, year-0 through year-4 average MPC of a lottery win.

**Model source** (existing): `IMPCs over time = [...]` line in `AllResults_*.txt`, written by `EstimAggFiscalMAIN.py` after every Step-5-eligible run.

### 2. Wealth share by education (data vs model)

**Source target** (`EstimParameters.py:33`): `data_WealthShares = [0.8, 17.9, 81.2]%` (D, HS, C) — SCF 2004.

**Model source** (existing): `Wealth shares by Ed.= [...]` line in AllResults.

Per-Ed pct error: `(model_pct − data_pct)`.

### 3. Wealth share by wealth quartile (data vs model)

**Source target** (table generator's hardcoded data): `[0.14, 1.60, 8.51, 89.76]%` (WQ4 poorest → WQ1 richest).

**Model source**: `Wealth Shares by Wealth Q = [...]` line in AllResults.

### 4. MPC by wealth quartile (data not directly observed; model-only diagnostic)

**Model source**: `Average lottery-win-year MPCs by Wealth (incl. splurge) = [...]` line in AllResults — the post-table-fix correct ordering (poorest first).

**Sanity check** (`wq_mpc_pattern_correct`): assert `mpc[poorest] > mpc[richest]` — flags any future regression of the WQ-MPC table-flip bug. Stored as 0/1.

### 5. Median LW/PI per cohort (targeted moment fit quality)

**Source target** (`EstimParameters.py:28`): `data_medianLWPI = [4.64, 30.2, 112.8]` (D, HS, C).

**Model source**: `Median LW/PI-ratios: D = ...  H = ...  C = ...` line in AllResults.

Per-cohort pct error.

### Computation

```python
from numpy import array, sqrt, sum, abs, max as nmax

data_impc = array([0.5056845, 0.1759051, 0.1035106, 0.0444222, 0.0336616])
model_impc = parse_impc_from_allresults(path)  # 5-element array
delta = model_impc - data_impc
gof_impc = {
    "data": data_impc.tolist(),
    "model": model_impc.tolist(),
    "delta": delta.tolist(),
    "pct_error": (100 * delta / data_impc).tolist(),
    "l2": float(sqrt(sum(delta**2))),
    "l1": float(sum(abs(delta))),
    "max_abs": float(nmax(abs(delta))),
}
# Similar for wealth_share_by_ed, wealth_share_by_wq, mpc_by_wq, median_lwpi.
```

**Computed metrics** (recorded in manifest under `metrics.impc_fagereng_gof`):

```python
data = np.array([0.5056845, 0.1759051, 0.1035106, 0.0444222, 0.0336616])
model = np.array(parsed_impc_line)  # 5-element array

per_horizon_delta = model - data
per_horizon_pct = 100 * per_horizon_delta / data
l2 = np.sqrt(np.sum(per_horizon_delta ** 2))
l1 = np.sum(np.abs(per_horizon_delta))
max_abs = np.max(np.abs(per_horizon_delta))
```

**Why these (and not weighted/Chi-square):** Fagereng's Figure 2 doesn't report year-by-year SEs in a form we can lift directly without going to the paper appendix. L2 + L1 + per-horizon deltas are sufficient for cross-run comparison and for spotting basin-shift regressions. If the paper's SEs become available, add a chi-square field; existing entries continue to work.

**Threshold convention** (suggested, not enforced):
- `l2_distance < 0.05` → excellent fit
- `0.05 ≤ l2_distance < 0.10` → acceptable
- `l2_distance ≥ 0.10` → flag for investigation

Current saved cal model output is `[0.57, 0.161, 0.06, 0.038, 0.035]`, giving L2 ≈ 0.079 — borderline acceptable. Year-0 MPC is the largest drag (model 0.57 vs data 0.51); year-2 is the second (model 0.06 vs data 0.10).

## Implementation phases

### Phase 1: registry write infrastructure (~3 hr)

- New module `Code/HA-Models/_registry.py`:
  - `current_config()` — read all relevant env vars + Parameters.py values, return canonical dict
  - `config_hash(config)` — deterministic short hash
  - `make_run_dir()` — create timestamped temp directory, return path
  - `write_manifest(run_dir, config, metadata, metrics, outputs)` — atomic write
  - `update_index(run_id, manifest)` — atomic update of `index.json`
  - `register_outputs(run_dir, list_of_files)` — atomic copy/move into run dir
- Hook calls into `EstimAggFiscalMAIN.py` (after `calcAllResults` block) and `AggFiscalMAIN_reduced.py` (after `Output_Results` call) so any Step-2 or Step-5 run automatically registers.

### Phase 2: iMPC-Fagereng GoF computation (~1 hr)

- Add module `Code/HA-Models/_impc_gof.py`:
  - `parse_impc_from_allresults(path)` — read `IMPCs over time = [...]` line
  - `compute_gof(model_impc)` — return dict of per-horizon and summary metrics
- Wire into the registry write so `metrics.impc_fagereng_gof` is always populated.
- Print headline (`"iMPC-Fagereng L2 = 0.0786"`) at end of every Step-5 run.

### Phase 3: warm-start lookup (~1 hr)

- New helper `_registry.find_warm_start(target_config)`:
  - Look up `by_config_hash[target_config_hash].latest`
  - If exists: return path to `step2/cal.txt`
  - If not: return None (cold-start)
- Update `EstimAggFiscalMAIN.py` and `estim_phase2_tm_a.py` warm-start logic to prefer the registry over the suffix-named file. Keep suffix-named fallback for legacy reads (existing `..._ESC.txt` etc.).

### Phase 4: comparison report integration (~1 hr)

- Update the QE-comparison report procedure (memory: `procedure_qe_comparison_report.md`) to pull from the registry: instead of re-inferring the current configuration, read `index.json` and locate the run by hash.
- Add `Code/HA-Models/scripts/registry_compare.py` to print side-by-side comparisons of two registry entries.

### Phase 5: migration / backward compat (~1 hr)

- Suffix-named files continue to be written by existing code paths; the registry is additive.
- Optional one-time backfill script: scan existing `Results/*.txt` files, infer configuration from filename suffixes, populate registry entries.
- Document: future code adds NEW dimensions by appending to `config_dimensions`; old entries with fewer dimensions still match (missing dimensions = "any value").

### Phase 6: deprecate suffix scheme (~LATER)

- After registry is well-exercised, remove the suffix-construction logic from estimators and replace with direct registry writes. Symlinks under `by_config/` provide the human-readable equivalent of the old filenames.

## Per-output atomicity

Each `runs/<run_id>/` directory is the unit of atomicity:
- All outputs of one run live there
- Symlinks under `by_config/<bucket>/latest` point to the most-recent successful run
- Failed runs leave their directory in a `.partial` state; not pointed to by `latest`
- Reads always go through `latest` symlink (or by run_id) — never see partial state

Each individual output file inside a run dir is a regular file; not separately versioned within a run. (If you re-run the same configuration, you get a NEW run directory; the old one is preserved for diff/audit.)

## What the registry does NOT do

- Doesn't replace git for commit-level versioning. Each run records its commit; rollback uses git, not the registry.
- Doesn't enforce reproducibility. Two runs with identical `config_hash` should give identical metrics; if they don't, the difference is in the unrecorded environment (e.g., RNG seed, joblib cache, OS) — diagnose via the existing `reproduce/run-manifests/*_pip_freeze.txt` infrastructure.
- Doesn't replace the `reproduce/run-manifests/` infrastructure. That tracks `--comp` runs (full reproduction sweeps); this registry tracks individual estimator/Step-5 runs. They complement each other.

## Open questions for the user

1. **Run-id format**: I propose `<date>_<commit>_<config_hash>`. Any preference for shorter / longer / different fields?
2. **Atomicity granularity**: each run = one directory. Acceptable, or do you want per-output atomicity (each output its own versioned file)?
3. **Index format**: JSON for now. SQLite if the index ever exceeds a few hundred runs (faster lookup, transactional updates). Switch when?
4. **Backfill**: should Phase 5 backfill existing suffix-named files into the registry? Easy if names are parseable; null/manual otherwise.
5. **GoF thresholds**: are the suggested L2 thresholds (excellent <0.05; acceptable <0.10) what you'd want, or do you have established thresholds from the paper / lab notes?
6. **Other GoF metrics worth always computing**: cross-section MPC by wealth quartile (data vs model); median LW/PI per cohort; wealth share by education? Each is cheap to compute and worth recording. Just say what to add.

## Estimated effort

| Phase | Wall | Comment |
|---|---|---|
| Phase 1 (registry write) | ~3 hr | Most of the work; new module + hooks in 2 estimators |
| Phase 2 (iMPC GoF) | ~1 hr | Parse + compute + record |
| Phase 3 (warm-start lookup) | ~1 hr | Replace suffix-fallback warm-start with registry-based |
| Phase 4 (comparison integration) | ~1 hr | Update QE-comparison report procedure |
| Phase 5 (migration / backfill) | ~1 hr | Backfill optional |
| Phase 6 (suffix removal) | LATER | Deferred until registry well-exercised |
| **Total Phases 1-5** | **~7 hr** | |

Per-run overhead: <1 sec for index update; ~MB of disk per run (mostly cached AllResults + tables + figures).

## What this plan does NOT do

- Does not implement anything; this is a design document.
- Does not change the upcoming ESC TM-a end-to-end run (which still uses suffix-named files; registry can be added afterward).
- Does not modify `reproduce/run-manifests/` (that's a complementary, run-script-level mechanism).
