# Plan: functional codebase improvements after documentation cleanup

**Date:** 2026-04-25
**Status:** STALLED (never executed; its doc-cleanup prerequisites were superseded by the 2026-06-11 doc-rationalization family — see plans/INDEX.md)
**Scope:** Behavioral and structural codebase improvements
**Prerequisite:** `plans/20260425-1301h_documentation-only-reproduction-cleanup.md` has already been executed

## 1. Goal

Improve the maintainability, safety, and reproducibility of the HAFiscal computational codebase after the documentation has been corrected to describe the current reproduction contract.

This plan assumes the documentation now accurately states:

- what `./reproduce.sh --comp full` runs;
- how `--comp max`, `--comp full --tm-only`, `--comp full --mc-only`, and `--comp TM-and-MC` differ;
- which outputs are valid under each mode;
- where paper-facing artifacts are generated;
- which timings are expected under cold, hot, and variant runs.

The purpose of this plan is to make the code conform to that documented contract and reduce the risk of partial, stale, or misconfigured reproduction runs.

## 2. Non-goals

- Do not rewrite the economics or intentionally change numerical results.
- Do not use this plan to repair README drift; that is assumed complete.
- Do not rename public paper-facing outputs until downstream LaTeX and release scripts have compatibility shims.
- Do not make packaging changes and numerical algorithm changes in the same commit.
- Do not remove historical scripts until their role has been classified by the completed documentation pass.

## 3. Phase 1: make the current pipeline fail safely

### 3.1 Refactor `do_all.py` to checked subprocess calls

Problem: `Code/HA-Models/do_all.py` is the default full-run orchestrator, but most steps use `os.chdir` and `os.system`. Many commands do not check failure. Step 5 records return codes but does not fail the whole step if a subcommand fails.

Implementation:

- Replace repeated `os.chdir` patterns with absolute `Path` objects rooted at `Code/HA-Models`.
- Replace `os.system(...)` with `subprocess.run([...], cwd=..., check=True)`.
- Use `sys.executable` rather than bare `python`.
- Preserve the current sequence and default step flags.
- Fail immediately when any required subcommand exits nonzero.
- Keep existing progress logging calls, but record each subcommand, cwd, duration, and return code.

Validation:

- Run a cheap smoke path if available, such as a step disabled run or a smoke-test parametrization.
- Intentionally call a nonexistent script in a temporary branch or local patch to confirm failure propagation, then revert that local test change.
- Confirm no default command names or arguments changed.

Estimate: 2-4 days.

### 3.2 Add per-step manifest records

Problem: `reproduce.sh` currently records the default full run as one shell command. That is useful, but not enough to diagnose which paper step generated or failed a result.

Implementation:

- Extend the manifest interface so `do_all.py` or the shell wrapper can record Step 1, Step 2, Step 4, Step 5a, and Step 5b separately.
- Include command, cwd, start time, end time, exit code, and declared output roots for each step.
- Preserve the outer manifest file naming and preflight behavior.

Validation:

- Run a fast scope such as nano or a smoke equivalent and confirm manifest JSON remains valid.
- Confirm full-run manifest schema is backward-compatible or versioned.

Estimate: 1-3 days after `do_all.py` subprocess refactor.

## 4. Phase 2: make persisted inputs safe and explicit

### 4.1 Replace `eval` loaders with safe parsing

Problem: `Parameters.py` and `EstimParameters.py` load parameter/result text by calling `eval`. This is unsafe and makes the file format implicit.

Implementation:

- Replace `eval` with `ast.literal_eval` for existing Python-literal files.
- Add small loader functions with clear names, such as `load_python_literal_dict` and `load_discfac_estimates`.
- Validate expected keys and types after parsing.
- Preserve compatibility with existing files such as `Result_AllTarget.txt` and `DiscFacEstim_*.txt`.

Validation:

- Unit test the current splurge and discount-factor files.
- Test malformed input produces a clear exception rather than silent defaults.
- Confirm `return_parameters("Baseline")` returns the same key values before and after the change.

Estimate: 0.5-1 day.

### 4.2 Introduce a versioned structured format

Problem: Python-literal `.txt` files are not a robust long-term persistence format.

Implementation:

- Define JSON or TOML schemas for splurge estimates and discount-factor estimates.
- Write compatibility loaders that read old `.txt` files and new structured files.
- Add writer functions for new outputs while preserving old outputs until downstream consumers are migrated.
- Include schema version, producing script, timestamp, parametrization, and source data references.

Validation:

- Round-trip current estimate files through the new format.
- Compare parsed values against legacy parsing.
- Confirm old committed files still load.

Estimate: 2-5 days for loaders and writers; longer if every historical artifact is migrated.

## 5. Phase 3: define a real configuration contract

### 5.1 Centralize run configuration

Problem: Run behavior is controlled by a mixture of environment variables, CLI flags, `Parametrization` strings, import-time `sys.argv`, and hard-coded defaults.

Implementation:

- Define a `RunConfig` dataclass or equivalent small configuration object.
- Document and implement precedence: defaults, parametrization, config file, environment, CLI.
- Start with `do_all.py`, `AggFiscalMAIN_reduced.py`, `Parameters.py`, and `EstimParameters.py`.
- Avoid a large migration at first. Provide adapter functions that let legacy functions receive the values they currently expect.

Validation:

- Tests for precedence among defaults, env vars, and CLI flags.
- Tests for `Baseline`, `Reduced_Run`, `Splurge0`, TM, MC, and smoke modes.
- Confirm existing command lines still work.

Estimate: 4-8 days for the first useful contract; 2-4 weeks to remove most legacy assumptions.

### 5.2 Remove import-time dependence on mutable process state

Problem: `EstimParameters.py` reads `sys.argv` and files at import time. Some tests also mutate `sys.argv` and `cwd` at module scope.

Implementation:

- Move import-time parameter calculation behind explicit functions.
- Add fixtures or context managers for any remaining tests that must patch `sys.argv`.
- Make file paths relative to module location or an explicit repo root, not the caller's current working directory.

Validation:

- Import `Parameters.py` and `EstimParameters.py` from repo root and from `FromPandemicCode` without changing cwd.
- Run the fast pytest subset after migration.

Estimate: 3-7 days after the first `RunConfig` pass.

## 6. Phase 4: implement output ownership and provenance

### 6.1 Convert the documentation artifact map into a checked registry

Prerequisite: the documentation-only plan has produced a paper artifact map.

Implementation:

- Convert the markdown artifact map into a machine-readable registry, such as `reproduce/artifacts.yaml` or `README/artifacts.json`.
- For each artifact, record paper label, path, generator, valid modes, required inputs, and whether it is paper-facing or intermediate.
- Use the registry to drive manifest output-root selection where practical.

Validation:

- A lightweight check confirms every registered generator path exists.
- A lightweight check confirms every paper-facing artifact path either exists or is explicitly generated by a documented step.
- The manifest records all registered paper-facing outputs for the selected scope.

Estimate: 3-7 days.

### 6.2 Add provenance sidecars or inline markers

Problem: Generated outputs are not all self-identifying. A table or figure may not say which command, commit, HARK version, and input hashes produced it.

Implementation:

- For `.tex` outputs, add safe generated-by comments.
- For binary outputs such as PDFs and PNGs, write sidecar `.provenance` files.
- Include manifest path, command, commit SHA, HARK version, key input hashes, and timestamp.
- Make marker injection idempotent.

Validation:

- Run a smoke command and confirm markers are created or updated only for generated outputs.
- Confirm LaTeX still compiles with `.tex` comments.

Estimate: 1-2 weeks.

### 6.3 Clarify binary artifact extensions

Problem: `OtherFunctions.py` writes pickle files with `.csv` extensions. This is misleading and makes artifact handling harder.

Implementation:

- Add new helpers that write `.pkl` files.
- Keep read compatibility for existing `.csv` pickle files.
- Migrate new outputs gradually by writing both formats or by adding compatibility aliases.
- Do not break committed paper-facing artifacts without downstream audit.

Validation:

- Confirm `Output_Results.py` and related loaders can read both old and new paths.
- Confirm the artifact registry marks file format accurately.

Estimate: 3-7 days for compatibility layer; 1-2 weeks if broad migration is attempted.

## 7. Phase 5: separate tests, diagnostics, and experiments

Problem: `Code/HA-Models/FromPandemicCode` mixes production modules, tests, diagnostics, phase scripts, historical validation, and one-off experiments.

Implementation:

- Classify files into:
  - production modules and entry points;
  - pytest regression tests;
  - validation harnesses;
  - diagnostics;
  - historical experiments.
- Move only low-risk tests first, or create wrapper test files in a new `tests/` directory while leaving source files in place.
- Add fixtures for cwd, `sys.argv`, temp output directories, and environment variables.
- Mark long-running validation tests separately from default pytest.

Validation:

- `pytest` default collection should run only fast, deterministic tests.
- Long-running validation tests should be selectable by marker or explicit path.
- Existing diagnostic scripts should remain discoverable through docs, not accidental pytest collection.

Estimate: 3-7 days for first cleanup; 2-4 weeks for robust reproduction coverage.

## 8. Phase 6: package reusable model code

Problem: The code relies heavily on running scripts from particular directories and manipulating `sys.path`.

Implementation:

- Create an importable package boundary for reusable logic, for example `hafiscal/`.
- Move reusable model, parameter, simulation, and output functions behind package modules.
- Keep legacy script entry points as thin wrappers during transition.
- Prefer `python -m hafiscal.scripts.<name>` or console scripts for new entry points.

Validation:

- Import package modules from repo root without cwd hacks.
- Existing shell commands still work through wrappers.
- Fast tests use package imports rather than path mutation.

Estimate: 2-4 weeks.

## 9. Recommended Ordering

1. Refactor `do_all.py` to checked subprocess calls.
2. Replace unsafe `eval` with safe literal parsing.
3. Add per-step manifest records.
4. Introduce the first `RunConfig` contract.
5. Convert the documentation artifact map into a checked registry.
6. Add provenance markers and broaden manifest output coverage.
7. Separate tests and diagnostics.
8. Package reusable modules.

This order keeps early changes behavior-preserving and lets the completed documentation cleanup serve as the contract for later refactors.

## 10. Estimated Total Effort

Minimum safety pass: 1-2 weeks.

Strong maintainability pass with configuration contract, artifact registry, and test separation: 4-8 weeks.

Full modernization with packaging and provenance maturity: 2-3 months, best done incrementally.

## 11. Risks

- Even behavior-preserving refactors may perturb long-running numerical workflows if cwd, environment, or output paths change. Keep changes small and validate with cheap smoke runs first.
- Existing paper and QE paths may depend on historical names such as `Baseline`, `CRRA2`, and `.csv` pickle files. Add compatibility before renaming.
- Configuration centralization can become a rewrite if attempted all at once. Start with adapters and clear precedence tests.
- A full reproduction is too expensive for every refactor. Build a ladder of validation: import tests, nano/smoke, TM-only, MC deterministic, then full run only at release checkpoints.
