# Plan: build a flag-controlled CDC/ESC pipeline alongside the current code

**Date:** 2026-04-23 (revised 2026-04-25)
**Branch target:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` (same branch; v2 pipeline runs side-by-side with the existing code, no existing code modified)

## 1. Goal

Build a successor pipeline that can produce **either** the CDC (household-bargain) **or** the ESC (Campbell–Mankiw bound-pair) results — or **both** in a single run — depending on an `interpretation` flag. The existing code path that produces the current CDC results is **not** modified; it stays as-is and continues to serve as the canonical CDC reference. The new flag-controlled pipeline is the next-generation implementation that can be exercised in either direction. After the v2 pipeline runs, we produce side-by-side comparison tables that let us see exactly which outputs coincide (targeted moments and aggregates dominated by them) and which diverge (tail-sensitive objects).

The v2 pipeline subsumes what the prior version of this plan (2026-04-23) called "an ESC-only parallel pipeline." Rather than duplicating files solely for ESC, the new code parameterizes the few places where CDC and ESC genuinely differ, with the existing CDC code retained byte-for-byte as the reference implementation.

## 2. Design principle: don't touch existing code OR existing results; new code is flag-controlled

The no-touch guarantee covers two distinct things, and **both** must hold strictly:

**(a) No existing source file is modified.** Every file currently in the estimation/simulation pipeline — `AggFiscalModel.py`, `Estimation_BetaNablaSplurge.py`, `AggFiscalMAIN.py`, `Simulate.py`, `Welfare.py`, `Output_Results.py` — stays byte-identical. The v2 pipeline lives in parallel new files (suffix `_v2`) and is never imported by anything on the current code path.

**(b) No existing result file is overwritten or modified.** This is enforced **mechanically**, not by trust: every output file written by the v2 code (estimation parameters, simulation tables, figures, logs, pickles, JSONs — anything) must contain either the literal string `_CDC` or the literal string `_ESC` somewhere in its filename. Existing-pipeline output files don't have those tags, so the filename rule alone makes it impossible for a v2 write to clobber an existing-pipeline result, regardless of which directory the write lands in. (Directory-level segregation under `Results_v2_<interp>/`, `Tables/Baseline_v2_<interp>/`, etc. — see §5 — is a second layer of protection.)

These guarantees together mean: the current pipeline continues to produce the calibrated CDC results that go to QE; the v2 pipeline produces sibling output sets — under either interpretation, or both at once — that cannot collide with the existing results.

This approach gives us:

1. **Strict no-touch guarantee** for both existing code AND existing results (replicability anchor preserved).
2. **One new code base** that handles both interpretations rather than two new code bases (less duplication than the prior ESC-only-fresh-files design).
3. **A validation test for free**: running the v2 pipeline with `interpretation="CDC"` must reproduce the existing pipeline's outputs to machine precision (or a tight, justifiable tolerance). Any divergence is a v2 bug.

## 3. Concrete differences the v2 pipeline switches on

Based on our analysis and Edmund's `origin/maintain_bound_pair_fix_splurge` branch:

### 3.1 Asset-update rule

- **CDC flag (current behavior):** `AggFiscalType.get_poststates` overrides the HARK default to compute `cNrm_actual = (1−ς)·cNrm + ς·TranShk·ADF` and then `aNrm = mNrm − cNrm_actual`.
- **ESC flag:** no override. Use HARK's inherited `aNrm = mNrm − cNrm` (the optimizer's per-capita budget).

In v2, the override is gated by an instance attribute `self.interpretation in {"CDC", "ESC"}`.

### 3.2 K/Y aggregator in estimation

- **CDC flag:** `K/Y = Σ aNrm·pLvl / Σ TranShk·pLvl` (treats `aLvl` as household wealth).
- **ESC flag:** `K/Y = Σ (1−ς)·aNrm·pLvl / Σ TranShk·pLvl` (treats `aLvl` as optimizer-per-capita; bound-pair household wealth is `(1−ς)·aLvl`).

In v2, the aggregator function takes the `interpretation` flag and applies the `(1−ς)` rescaling conditionally.

### 3.3 Wealth-distribution moments (Lorenz, quartiles) in estimation

- **CDC flag:** use `aLvl` directly.
- **ESC flag:** use `(1−ς)·aLvl`.

Same conditional pattern.

### 3.4 Welfare aggregator

- **Both flags identical:** `u(cLvl_splurge/pLvl)` per Edmund's Apr 23 clarification (and what the current code computes). No flag dependence.

### 3.5 Everything else

Consumption-function solve, shock construction, Markov machinery, multiplier computation, AD loop — all identical between CDC and ESC. The only flag-dependent code paths are §§3.1–3.3 above.

## 4. New files to create

Under `Code/HA-Models/FromPandemicCode/`:

| New file | Purpose | Structure |
|---|---|---|
| `AggFiscalModel_v2.py` | v2 agent / market classes | Defines `AggFiscalType_v2` taking an `interpretation` kwarg ("CDC" or "ESC"). The `get_poststates` override applies conditionally on `interpretation == "CDC"`. Otherwise pass-through to HARK default. |
| `Simulate_v2.py` | v2 simulation orchestrator | Mirrors `Simulate.py` but imports v2 classes; takes `interpretation` from a top-level config and forwards it to agent construction. |
| `AggFiscalMAIN_v2.py` | v2 driver | Mirrors `AggFiscalMAIN.py`. Adds an `interpretation` field to `Run_Dict`; supports the values `"CDC"`, `"ESC"`, and `"both"` (the last loops over the two and writes outputs to interpretation-tagged paths). |
| `Welfare_v2.py` | v2 welfare wrapper | Pass-through (welfare aggregator is flag-independent). Created for symmetry and to allow future flag-dependent welfare variants without retroactive edits. |
| `Output_Results_v2.py` | v2 output/reporting | Mirrors `Output_Results.py`. Takes `interpretation` and writes to `Tables/Baseline_<interpretation>/` and `Figures/Baseline_<interpretation>/`. |

Under `Code/HA-Models/Target_AggMPCX_LiquWealth/`:

| New file | Purpose |
|---|---|
| `Estimation_BetaNablaSplurge_v2.py` | v2 estimation. Aggregator functions accept the `interpretation` flag and apply the `(1−ς)` rescaling for K/Y and Lorenz only when `interpretation == "ESC"`. |

Under `Code/HA-Models/`:

| New file | Purpose |
|---|---|
| `do_all_v2.py` | v2 orchestration (Steps 1–5). Reads the `interpretation` value (or "both") from a CLI flag or config, then runs the pipeline accordingly. |

## 5. Output paths and the filename-tag rule

### 5.1 Sibling directories

v2 outputs go to interpretation-tagged sibling directories that don't clobber the current pipeline:

- `Code/HA-Models/Target_AggMPCX_LiquWealth/Results_v2_<interp>/` — estimation output for each interpretation (β̄, ∇, ς per education group); the canonical parameter store, see §6.
- `Code/HA-Models/FromPandemicCode/Tables/Baseline_v2_<interp>/` — multiplier / welfare / MPC tables.
- `Code/HA-Models/FromPandemicCode/Figures/Baseline_v2_<interp>/` — figures.
- `history/20260425_v2_pipeline/` — per-step logs, diagnostics, comparison artifacts.

Where `<interp>` is `CDC` or `ESC`. When `interpretation="both"`, the driver writes both directory sets in one run.

### 5.2 Mandatory `_CDC` / `_ESC` tag in every output filename

In addition to the sibling-directory layout, **every file written by the v2 code must contain the literal substring `_CDC` or `_ESC` somewhere in its filename**. Examples:

- `Results_v2_CDC/estimated_parameters_CDC.json` (not `estimated_parameters.json`).
- `Tables/Baseline_v2_CDC/multipliers_CDC.tex` (not `multipliers.tex`).
- `Figures/Baseline_v2_ESC/wealth_lorenz_ESC.pdf`.
- `history/20260425_v2_pipeline/phase1_estimation_log_CDC.txt`.
- Any pickle / JSON / NPZ intermediate written by v2: same rule.

This is enforced two ways:

1. **In code:** every v2 helper that writes a file takes the `interpretation` value and incorporates `_<interpretation>` into the filename it constructs. There is no v2 path that calls `open(..., "w")` (or `pd.to_csv`, `pickle.dump`, etc.) with a filename that doesn't include the tag.
2. **In a guard test:** a small repo-wide test (run as part of CI / sign-off) walks all `_v2`-prefixed source files, greps for write calls (`open` with mode `w`/`wb`/`a`, `to_csv`, `to_pickle`, `np.save`, `json.dump`, `plt.savefig`, etc.), and flags any filename literal or f-string that doesn't include `_CDC` or `_ESC` (or a variable that obviously will). False positives can be silenced with an explicit `# noqa: v2-tag` annotation that's reviewable.

The motivation is belt-and-suspenders. Even if a v2 script glitched and wrote into a non-`_v2` directory (a coding error), the filename tag alone would prevent it from overwriting an existing-pipeline result file — because no existing-pipeline file has `_CDC` or `_ESC` in its name.

## 6. Canonical parameter storage and load-or-halt simulation behavior

Estimation is expensive (hours of compute); simulation is cheaper but non-trivial. Each interpretation requires its **own** (β̄, ∇, ς) triple per education group, and re-estimating just to redo a simulation is wasteful. The v2 pipeline therefore cleanly separates estimation from simulation via canonical parameter files: estimation writes them; simulation reads them; nothing else.

### 6.1 Canonical parameter file paths

For each interpretation, the estimation phase writes to (and the simulation phase reads from):

- `Code/HA-Models/Target_AggMPCX_LiquWealth/Results_v2_CDC/estimated_parameters_CDC.json`
- `Code/HA-Models/Target_AggMPCX_LiquWealth/Results_v2_ESC/estimated_parameters_ESC.json`

(Both filename and directory carry the interpretation tag, per the §5.2 rule. Format is JSON — *not* `repr`/`eval` of a Python literal as the existing code uses, which is unsafe and metadata-free; see §6.6 below.)

**Schema** — designed to be a *complete* reproducibility record. Every field below is mandatory; an estimation run that fails to populate any of them aborts before writing the file.

```json
{
  "schema_version": "1",
  "interpretation": "CDC",

  "estimated_at": "2026-04-25T14:30:00Z",
  "estimated_by_user": "ccarroll",
  "estimated_on_host": "<hostname>",

  "code_state": {
    "branch": "0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC",
    "git_commit": "<sha at estimation time>",
    "git_dirty": false,
    "git_status_summary": "<output of `git status --short`; required to be empty for a 'clean' record>",
    "hark_version": "<HARK.__version__ at runtime>",
    "hark_git_commit": "<HARK source SHA if installed from git>",
    "python_version": "3.11.x",
    "numpy_version": "1.26.x",
    "scipy_version": "1.11.x",
    "platform": "darwin-arm64"
  },

  "model_config": {
    "CRRA": 2.0,
    "Rfree": 1.01,
    "IncUnemp": 0.30,
    "IncUnempNoBenefits": 0.15,
    "Rspell": 4,
    "T_age": 200,
    "T_cycle": 1,
    "LivPrb": 0.99375,
    "PermGroFac": 1.00453,
    "PermShkStd": 0.06,
    "TranShkStd": 0.20,
    "UnempPrb": 0.07,
    "UnempPrbRet": 0.0005,
    "unemp_pLvl_grows_like_employed": false,
    "perm_shocks_during_unemployment": false,
    "...": "every other Parameters.py setting that can affect the result"
  },

  "estimation_config": {
    "optimizer": "scipy.optimize.minimize",
    "method": "Powell",
    "bounds": [[0.0, 0.9], [0.7, 1.1], [0.0, 0.4]],
    "starting_point": [0.27, 0.96, 0.03],
    "xtol": 0.0001,
    "ftol": 0.0001,
    "objective_weights": {"K_Y": 1.0, "lorenz": 1.0, "agg_MPC": 1.0}
  },

  "targets": {
    "K_Y": 6.60,
    "lorenz_data_file": "LiquWealth_Distribution_a.xlsx",
    "lorenz_data_sha256": "<sha256 of the file as read>",
    "lorenz_percentiles": [0.20, 0.40, 0.60, 0.80],
    "lorenz_target_values": [0.0011, 0.0098, 0.0376, 0.0952],
    "agg_mpc_data_file": "Data_AggMPC_LotteryWin.xlsx",
    "agg_mpc_data_sha256": "<sha256>",
    "agg_mpc_target_values_by_year": {"0": 0.505, "1": 0.175, "2": 0.103, "3": 0.045, "4": 0.032}
  },

  "estimation_input_hash": "<sha256 over (code_state + model_config + estimation_config + targets), used as the freshness key for §6.4>",

  "results": {
    "splurge": 0.2609,
    "by_education": {
      "dropout":   {"beta_bar": 0.6995, "nabla": 0.340},
      "highschool":{"beta_bar": 0.9302, "nabla": 0.0705},
      "college":   {"beta_bar": 0.9834, "nabla": 0.0129}
    },
    "objective_at_optimum": <float>,
    "fit_quality": {
      "K_Y_model":  <float>,
      "lorenz_distance": <float>,
      "agg_mpc_distance": <float>
    },
    "wall_clock_seconds": <int>
  }
}
```

`splurge` (ς) is shared across education groups; β̄ and ∇ vary by group.

The principle is: **anyone with this file plus a checkout of the listed `git_commit` should be able to reproduce these numbers exactly.** The `code_state` block locks down the code; `model_config` locks down every model assumption; `estimation_config` locks down the optimization machinery; `targets` locks down the empirical inputs (with file hashes, not just paths, so silent edits to the target data files are detectable); `estimation_input_hash` is a single fingerprint derived from all of the above, used as the freshness key for the cache-staleness check (§6.4).

If any of `code_state.git_dirty == true`, `code_state.git_status_summary != ""`, or any other field above is missing, the estimation run still writes the file (so the partial result isn't lost) but tags it `"schema_version": "1-dirty"` and the simulation phase **always** halts with an error when it tries to load a `dirty` file unless `--accept-dirty` is passed explicitly.

### 6.2 Which phases write vs. read

- **Phase 1 (estimation) writes** the canonical parameter file for each interpretation it runs. Estimation explicitly overwrites the existing canonical file. This is the only place the file is written.
- **Phases 2 and 3 (smoke tests and full simulation) read** the canonical file at startup. The simulation **never re-estimates**; it only consumes the parameters.

This split means the typical workflow after a one-time estimation is:

1. `python do_all_v2.py --phase estimation --interpretation both`  *(slow; run once per code-or-target change)*
2. `python do_all_v2.py --phase simulation --interpretation both`  *(faster; can be re-run as often as needed without re-estimating)*

### 6.3 Load-or-halt simulation behavior

At simulation startup, the v2 driver attempts to load `Results_v2_<interp>/estimated_parameters.json`. Behavior:

- **File present and valid:** parameters are loaded and the simulation proceeds.
- **File absent or unreadable:** the driver **halts immediately** with an error message of the form:

```
ERROR: No estimated parameters found for interpretation="<interp>" at
       Code/HA-Models/Target_AggMPCX_LiquWealth/Results_v2_<interp>/estimated_parameters_<interp>.json

To produce these parameters, run the estimation phase first:
       python Estimation_BetaNablaSplurge_v2.py --interpretation <interp>
   or  python do_all_v2.py --phase estimation --interpretation <interp>

Simulation aborted to prevent running with absent or stale parameters.
```

The halt-on-missing rule (rather than silently re-estimating) defends against two failure modes:

1. A simulation silently triggering a fresh estimation the user wasn't expecting (cost: hours of compute, possibly with parameters subtly different from those intended).
2. A simulation silently using stale parameters left over from a previous run that no longer match the current code or target data (cost: hard-to-diagnose result drift).

### 6.4 Validity checks beyond simple presence

Beyond file presence, the simulation also halts with a clear error if any of:

- The `interpretation` field in the file doesn't match the requested interpretation.
- The `estimation_input_hash` doesn't match the current target-data + estimation-config hash (signals that the targets or config have changed since estimation was run, so the cached parameters are stale).
- The JSON schema is malformed or missing required fields.

The hash check is conservative: it forces re-estimation whenever the target data or estimation config change. An explicit `--ignore-stale-hash` flag bypasses it (with a warning printed to stderr) for testing or for cases where the user knows the change is benign.

### 6.5 Reference to the current pipeline's parameter location

The current (non-v2) pipeline writes parameters to `Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt` (and a few sibling files for sensitivity variants). Those are not touched by v2. The v2 pipeline's `Results_v2_<interp>/` directories are siblings; the two never read or write each other's files.

### 6.6 What the existing storage does NOT capture, and why v2 fixes it

The current `Result_AllTarget.txt` storage is *intentionally* much weaker than what v2 will use, and listing the gap explains the v2 schema design:

- **Format:** the existing file is a single line, a Python `repr` of a dict literal, e.g. `{'splurge': 0.2608..., 'beta': 0.9610..., 'nabla': 0.0668...}`. It is read with `eval(contents)` in `load_betanabla_res_txt`. This is unsafe (a tampered file can execute arbitrary code) and schema-free (no validation that the file has the fields the loader expects). v2 uses JSON and validates against the §6.1 schema.
- **Metadata:** the existing file stores **only** the three scalars (splurge, beta, nabla). It records *none* of: the branch / git commit / git-clean status; the HARK / Python / numpy / scipy versions; the date of estimation; the `Parameters.py` settings (CRRA, Rfree, IncUnemp, etc.); the optimization config (method, bounds, tolerances, starting point); the target-data file paths or content hashes; the K/Y target value; the Lorenz percentile targets; the Fagereng-Holm-Natvik MPC series. **Nothing.** Anyone wanting to reproduce the numbers from that file alone has to guess every one of those things from context (or comb through git history to find the matching commit). v2 records all of them in the schema's `code_state`, `model_config`, `estimation_config`, and `targets` blocks.
- **Result-with-context, not just result.** In v2, the parameter file is a *complete reproducibility record*: anyone given the file plus a checkout of the recorded `git_commit` should be able to re-run estimation and get the recorded `results` block back exactly. The existing file does not support this.

This is also the reason the §6.4 staleness check uses a hash over `(code_state ⊕ model_config ⊕ estimation_config ⊕ targets)` rather than just a target-data hash: any change to *any* of those inputs invalidates the cached parameters, and a future v2 simulation should refuse to consume them silently.

## 7. Implementation sequence

### 7.1 Phase 1 — estimation alone (Step 2 equivalent), both flags

Smallest self-contained unit. Validates the K/Y / Lorenz aggregator switching in isolation.

1. Create `Estimation_BetaNablaSplurge_v2.py`.
2. Run it with `interpretation="CDC"`. Compare its output to the existing pipeline's calibration in `Code/HA-Models/Target_AggMPCX_LiquWealth/Results/`. **Must match to machine precision** (or, if rounding/numerical-path differences are unavoidable, to documented tight tolerances).
3. Run it with `interpretation="ESC"`. Compare against Edmund's `maintain_bound_pair_fix_splurge` published numbers (β̄ ≈ 0.9715, ς ≈ 0.2672). Match within ~0.005 on β̄ and ~0.01 on ς confirms correct ESC implementation.

The CDC reproduction in step 2 is the critical validation: it certifies that the new flag-controlled code, when set to "CDC," is identical-in-results to the unchanged reference pipeline. Without that, no other v2 results are trustworthy.

### 7.2 Phase 2 — simulation classes (Step 5 machinery), both flags

1. Create `AggFiscalModel_v2.py` with the conditional `get_poststates` override.
2. Smoke test: instantiate `AggFiscalType_v2(interpretation="CDC")`, solve, simulate 100 periods. Confirm `aNrm` values match what the current `AggFiscalType` produces under the same inputs (within machine precision).
3. Smoke test: instantiate with `interpretation="ESC"`, simulate. Confirm: (a) `cLvl_splurge` still computed identically; (b) `aNrm` evolves via `mNrm − cNrm` (no splurge subtraction); (c) the MC run completes without error.

### 7.3 Phase 3 — full pipeline, both flags

1. Create the `_v2` versions of `Simulate.py`, `AggFiscalMAIN.py`, `Welfare.py`, `Output_Results.py` with the `interpretation` plumbing.
2. Create `do_all_v2.py`.
3. Run the full v2 pipeline in `interpretation="both"` mode. Expected wall-clock: roughly 2× the current pipeline's CDC-only run (~12 h × 2 ≈ 1 day for Baseline with S=32 seeds), since each interpretation runs end-to-end. (Some shared steps — solving the standard CRRA buffer-stock policy — may be cacheable across interpretations; defer that optimization.)

### 7.4 Phase 4 — comparison report

1. Generate `history/20260425_v2_CDC_vs_ESC_comparison.md` with side-by-side tables for:
   - (β̄, ∇, ς) estimates under each interpretation.
   - K/Y, Lorenz percentiles, aggregate MPC — confirming both calibrations hit targeted moments.
   - Multipliers (all three policies, all (Rec, AD) combinations).
   - Policy-activity shares.
   - Welfare-6 cells at S=32 seeds with across-seed SE.
   - Non-targeted wealth moments (bottom decile, top percentile).

2. Confirm the v2-CDC output column matches the original-pipeline-CDC output column to within tolerance (this is the replicability check restated at the simulation level).

3. Flag where CDC and ESC outputs coincide (predicted by target-level equivalence; see [`BUGS_private/HAFiscal_splurge_budget_inconsistency/why_results_match_at_target.md`](../BUGS_private/HAFiscal_splurge_budget_inconsistency/why_results_match_at_target.md)) and where they diverge (should be concentrated in non-targeted tails).

## 8. Validation and sanity checks

- **v2-CDC vs original-CDC must match to machine precision** at the estimation level (Phase 1) and to within MC noise at the simulation level (Phase 3). This is the foundational test — it validates that the v2 codebase, when set to "CDC," is a faithful replication of the current pipeline. If it doesn't match, the v2 work is wrong somewhere, regardless of whether ESC numbers look reasonable.
- **At ς = 0:** v2-CDC and v2-ESC must produce identical results. Trivial sanity check (the `(1−ς)` rescaling is identity at ς = 0).
- **v2-ESC matches Edmund's `maintain_bound_pair_fix_splurge` published numbers** (β̄ ≈ 0.9715, ς ≈ 0.2672) to ~0.005 / ~0.01 tolerance.
- **Welfare-6 at S=32 (each interpretation):** across-seed SE on each cell under 0.5 % (matching the standard the current pipeline holds itself to).
- **Filename-tag guard test passes** (per §5.2): no v2 source file writes a filename without `_CDC` or `_ESC` in it.
- **Halt-on-missing-parameters works** (per §6.3): a smoke-test that deletes the canonical parameter file and tries to start a simulation must produce the documented error message and a non-zero exit code, not silently re-estimate.

## 9. Deliverables

1. The five new `_v2` source files under `FromPandemicCode/` plus `do_all_v2.py` and `Estimation_BetaNablaSplurge_v2.py`.
2. **Canonical parameter files** `Results_v2_CDC/estimated_parameters_CDC.json` and `Results_v2_ESC/estimated_parameters_ESC.json` (per §6 schema) — written once by the estimation phase, read by every subsequent simulation run.
3. v2-CDC simulation outputs in `Tables/Baseline_v2_CDC/` and `Figures/Baseline_v2_CDC/`, every filename containing `_CDC` per §5.2 — matching the original-pipeline outputs.
4. v2-ESC simulation outputs in the parallel `_v2_ESC/` paths, every filename containing `_ESC`.
5. **Two automated guard tests:** the filename-tag scanner (per §5.2 step 2) and the halt-on-missing-parameters smoke test (per §6.3 / §8). Both should run as part of the v2-pipeline sign-off and exit non-zero if violated.
6. Comparison document in `history/20260425_v2_CDC_vs_ESC_comparison.md`, including the v2-CDC-vs-original-CDC reproducibility table.
7. A short memo summarizing which outputs coincide (confirming target-level intuition) and which differ (flagging where tail-sensitivity matters).

## 10. Risks and caveats

- **Flag-handling bugs.** A unified codebase with an `interpretation` switch can quietly mis-route one of the cases. Mitigation: every test runs the pipeline at *both* flag values and compares (a) v2-CDC against original-CDC, (b) v2-ESC against Edmund's published numbers, (c) v2-CDC and v2-ESC against each other under the ς = 0 limit.
- **Subtle import drift.** If a v2 file accidentally imports from the original (non-`_v2`) module (or vice versa), behavior can become entangled. Mitigation: each `_v2` file starts with an explicit import banner; a small test asserts no `_v2` module imports a non-`_v2` model module (utility modules — HARK, numpy, etc. — are exempt).
- **Welfare aggregator stability.** If Edmund's reading of the welfare aggregator changes again, v2 welfare code may need to track it. Current plan: shared `u(cLvl_splurge)` for both flags, matching what he wrote on Apr 23. If a new variant is needed later, add an optional `welfare_aggregator` flag — don't retrofit by editing the original code path.
- **Duplication cost (now smaller than before).** The new design has ~6 v2 files (mostly mirrors of existing ones), but only a handful of methods inside them are flag-dependent (§§3.1–3.3). Vs the prior plan's ESC-only fresh-files approach, this is roughly half the duplication.
- **Shared calibration targets.** Both flags must use the same SCF 2004 K/Y target (6.60) and the same Lorenz percentile targets. Don't duplicate target-data ingestion — the v2 estimation code reads the same target-data files as the original pipeline.

## 11. Timeline estimate

- Phase 1 (estimation, both flags): 0.75 day to write + 4–8 h to run (both calibrations).
- Phase 2 (simulation classes + smoke tests, both flags): 0.75 day.
- Phase 3 (full pipeline, both flags): 0.75 day to wire + ~1 day compute for Baseline at S=32 (both flags).
- Phase 4 (comparison report incl. v2-CDC reproducibility check): 0.5 day.

**Total calendar time:** ~3.5 days of active work plus pipeline compute time in the background. Slightly longer than the prior ESC-only fresh-files version (~3 days) because v2 must also reproduce CDC and the validation step is more involved; offset by less code duplication and a single maintainable next-generation pipeline.

## 12. What this plan supersedes

The earlier (2026-04-23) version of this plan called for fresh `_ESC`-suffixed files producing only the ESC variant. That was structurally simpler but left the project with two divergent codebases (the existing CDC code plus an ESC-only sibling). This revision keeps the no-touch guarantee on the existing code while consolidating future work into a single flag-controlled successor pipeline, which is more maintainable and provides a built-in replicability test (v2-CDC ≡ original-CDC) for free.
