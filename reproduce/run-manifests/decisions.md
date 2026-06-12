# Autonomous decisions during implementation

A running log of decisions I made without explicit user input during the implementation of `plans/20260425-1015h_reproduce-self-documenting-runs.md`. The user authorized this in their 2026-04-25 reply: *"Proceed as far as you can without my input, but record any decisions you make that you might normally have insisted upon input from me on."*

User can review and override any of these.

> **As of 2026-04-25**, decisions in this log not annotated otherwise are still current as written. Items that have since been superseded, completed, or corrected carry an explicit `**Status (2026-04-25):**` annotation.

## Phase 0 (setup)

- **Branch base:** branched `feature/reproduce-self-documenting` from the working branch HEAD (`cf521dfc` — the v2-pipeline plan commit). Alternative was to branch from the `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` branch tip; they're the same commit at this moment, so choice is moot.

## Phase 1 (pre-flight gate)

- **All checks run before aborting.** Rather than fail-fast at the first failed check, the gate runs every check and reports all problems in one block before exiting. UX win: a single failed run tells the user the complete punch list.
- **No override for input-data presence.** Per plan §3, the input data files are paper-essential; missing them is a hard fail with no `--accept-missing-inputs` knob. (Override would be tantamount to running with non-paper inputs, which defeats the purpose.)
- **No override for HARK importability.** Same reasoning: reproducibility requires *some* HARK version recorded; if HARK can't be imported, there's no version to record.
- **`HAFISCAL_PREFLIGHT_*` env vars** are the bridge from gate to (Phase-2) manifest builder. Captured: `_OVERRIDES`, `_BRANCH`, `_HEAD_SHA`, `_DIRTY`. The `PREFLIGHT_OVERRIDES` bash array is serialized to a space-separated string for export (bash arrays don't export cleanly to subprocesses).
    - **Status (2026-04-25 correction):** Separator changed from space to ";" to safely handle entries with internal spaces (Phase 5 bug fix; see "Bug found and fixed during smoke test" entry in Phase 5).
- **Helper function naming:** `_preflight_for_comp` (underscore-prefixed for "internal" convention used elsewhere in the script). Companion `_preflight_record_override` does the array append.
- **Emoji prefixes** in log output match existing script conventions (✅ ⚠️ ❌). The big "================================================================" boxed-error pattern is also borrowed from existing usage (cf. lines 257–270 of the Windows-environment block).
- **HARK version on this machine is 0.17.1**, not the 0.17.0 used in plan example schemas — the plan examples are illustrative; the manifest will record whatever `HARK.__version__` reports at run time.

## Phase 2 (manifest builder)

- **Subcommand split:** `init`, `step`, `record-output`, `finalize`. Each subcommand reads/writes the manifest JSON file in place. Bash invokes Python via subprocess at the corresponding hooks (init at start; step after each substep; record-output after the run produces files; finalize at end). Alternative (single CLI with `--mode`) was less discoverable.
- **Schema version is "1"** as a string (not an int), which lets us add a `"1-dirty"` variant later for runs cleared via `--accept-*` overrides without bumping major version. Plan §6.1 of the v2-pipeline plan uses the same convention.
- **HARK source SHA:** captured via `git rev-parse HEAD` run from `dirname(HARK.__file__).parent` — this works when HARK is installed editable from a git clone (the typical uv setup on this branch), and silently returns None otherwise. The version string (`HARK.__version__`) is the primary record; the SHA is supplementary.
- **`uv pip freeze` first, `pip freeze` fallback.** Per user decision #3. The sidecar file's header comment records which one was actually used so a future replay knows.
- **Result_AllTarget.txt parsing** uses `ast.literal_eval` rather than `eval()` — safe (won't execute arbitrary code) and equivalent for the dict-literal format the existing code uses.
- **Dotfiles skipped** when walking output dirs (any path component starting with `.`). Otherwise `__pycache__/` and `.DS_Store` would dominate the manifest's outputs block.
- **Path recording is repo-relative when possible, absolute otherwise.** For pip-freeze sidecars and output files inside the repo, repo-relative; for arbitrary user-specified paths (e.g., a manifest in `/tmp/` during testing), absolute. Production paths are always inside the repo.
- **HAFISCAL env-var snapshot** is fixed to a 9-entry list. If new HAFISCAL_* vars appear later (e.g., in the v2 pipeline), the list will need updating; not a clean abstraction but explicit.
- **Modifier flags** (mc-only, tm-only, etc.) come in as a comma-separated string `--modifiers mc-only,tm-only` rather than `--modifier` (singular, repeated). Easier for the bash caller to construct.
- **Smoke test** (init → step → record-output → finalize against existing Tables/Baseline/): all 4 subcommands worked, 10 output files hashed, manifest schema populated. One bug found and fixed during the smoke test (path-rel computation assumed manifest inside repo).

## Phase 3 (recipe / commit-msg / tag generators)

- **Tag base format:** `reproduce-<YYYYMMDD>-comp-<scope>[-<modifier>]`. The `-comp-` part is hard-coded (all `--comp` runs use it); if `--data` or `--docs` ever get the same treatment, those would use `-data-` / `-docs-` separately.
- **Tag-date source:** UTC date from the manifest's run-start `started_at_utc` field (YYYYMMDD). This matches the date the run *began* even if it crossed midnight while running. Per plan §8.
- **Collision-resolution scope:** local tags PLUS remote tags fetched via `git ls-remote --tags origin`. The remote check requires network; if offline, `_existing_tag_names` returns whatever's available locally. Risk: a same-day re-run on a different machine could collide on the remote. Mitigation: the tag-name generator runs at commit-prep time (Phase 4 wiring), and `git push` will refuse to push an already-existing tag.
- **Recipe script discipline:** `set -euo pipefail` + `exec` for the final command (so exit code propagates cleanly). Each verification step (clean worktree, HARK version, input-data hashes) prints expected-vs-got on failure and exits non-zero.
- **HARK version check:** strict string equality (`expected == got`). If you bump HARK, you'd need to either re-run estimation under the new version (anchor moves) or accept that older recipes won't replay against the newer HARK.
- **Env-var replay:** only re-export `HAFISCAL_*` vars that were set at original invocation (None values skipped). Used Python `repr()` for quoting safety in the bash export line — handles spaces / special chars.
- **Commit-msg "key outputs":** picks up to 8 priority files (Multiplier.tex, welfare6.tex, welfare6_parallel_summary.json first; then other Tables/Baseline/*.tex). Full list lives in the manifest. SHAs truncated to 12 hex chars for readability.
- **Commit-msg path display:** uses `manifest_path.parent.name + '/' + manifest_path.stem + '.reproduce-recipe.sh'` so a user reading the commit log sees `bash run-manifests/<file>.reproduce-recipe.sh` (relative to repo root). For test paths outside the repo (e.g., `/tmp/`), the display uses the parent's name (`tmp/`), which is cosmetically off but harmless and only happens in dev/test.
- **`tag-name` subcommand returns just the name on stdout** (not log noise), so bash callers can capture it cleanly with `TAG=$(python build_manifest.py tag-name --manifest ...)`.

## Phase 4 (wiring)

- **`ORIGINAL_ARGV`** captured at the very top of `reproduce.sh`, *before* any arg parsing modifies `$@`. This is what the manifest's `command_line` field records.
- **State carried via globals** (`MANIFEST_PATH`, `MANIFEST_STEM`) rather than bash function returns; simpler than passing the manifest path to every helper invocation.
- **`DEFAULT_OUTPUT_ROOTS` bash array** names the output dirs to hash by default (`Tables/Baseline`, `Figures/Baseline`). Per-subcommand wiring can override by passing explicit args to `_manifest_record_outputs`.
- **Helper functions are no-ops if `MANIFEST_PATH` is unset.** Defensive: a subcommand that doesn't call `_manifest_init` first won't crash if it accidentally calls one of the other helpers.
- **`--auto-commit` does staging + commit + tag** (per user decision 3) but **does NOT push** — push remains the user's explicit step. Logged hint at end: `git push origin <branch> && git push origin <tag>`.
- **Print-proposal block** uses a heredoc with all suggested git commands, ready to copy-paste. Includes a hint at the end: "Or re-run with --auto-commit to do the staging + commit + tag automatically."
- **Only `reproduce_nano_results` wired in this commit.** Other entry points (`reproduce_full_mc_only_results`, `reproduce_full_tm_only_results`, `reproduce_all_computational_results`, `reproduce_micro_results`, `reproduce_mini_results`, `reproduce_minimal_results`, `reproduce_TM_and_MC_results`) need the same pattern; deferred to follow-up.
    - **Status (2026-04-25):** Implemented. All eight computational entry points are now manifest-wired (reproduce.sh:1395–1843); each calls _manifest_init, _manifest_step, _manifest_record_outputs, and _manifest_finalize_and_propose in the correct sequence.
- **Provenance-marker post-processor** (per plan §6) not yet implemented; deferred.
    - **Status (2026-04-25):** Still deferred. Outputs are recorded in the manifest but do not yet have embedded provenance metadata.
- **Smoke test (Phase 5)** not yet run; would require either pushing the feature branch or `--accept-unpushed`. Deferred to follow-up turn — user may want to be involved given the multi-hour Phase 6 will follow on a remote.
    - **Status (2026-04-25):** Completed (see Phase 5 section below).

## Phase 5 (smoke test)

- **Test command:** `./reproduce.sh --comp nano --accept-dirty` (the working tree has 240+ unrelated incidental modifications from outside this session, so `--accept-dirty` is required for any test run during development; the manifest correctly records the override).
- **Branch state:** feature branch was pushed before the test so the unpushed-check passed without needing `--accept-unpushed`.
- **Test results:**
    - Pre-flight gate ran cleanly (with the dirty override) and reported the punch list properly.
    - Sub-script `./reproduce/reproduce_computed_nano.sh` ran in 4 seconds, exit code 0.
    - Manifest, recipe, commit-msg, tag-msg all written to `reproduce/run-manifests/`.
    - Pip-freeze sidecar captured (`uv pip freeze` succeeded).
    - 65 output files hashed across `Tables/Baseline/` and `Figures/Baseline/`.
    - Tag-name resolved cleanly: `reproduce-20260425-comp-nano` (no collision).
    - Total wall: 11 seconds (4s nano + ~7s manifest overhead).
- **Bug found and fixed during smoke test:** `HAFISCAL_PREFLIGHT_OVERRIDES` env var bridge from bash → Python was using space as separator, but individual override entries contain spaces internally (e.g., `"git_dirty:user-accepted via --accept-dirty"`). Result: the Python parser was breaking each entry into multiple fragments. Switched to `;` separator on both sides; entries with spaces now round-trip correctly. Verified by re-running the smoke test.
- **Decisions made during the smoke test:**
    - **Manifest stem uses UTC timestamp** (e.g., `comp_nano_20260425-1546.json`); the log file uses local time (e.g., `comp_nano_20260425-1146.log`). Same moment, different timezone reference. Not a bug, but the stem and the log filename don't share the timestamp string. Could unify to UTC throughout in a follow-up if user wants consistency.
    - **Recipe script verifies HARK version exactly** — passes for the same machine; would correctly fail with a clear message if HARK version were bumped. The failure message points at `reproduce/uv_sync_repair.sh`.
- **Provenance markers (plan §6) NOT yet implemented.** The smoke test's outputs (`Tables/Baseline/*.tex`, `Figures/Baseline/*.{pdf,png}`) currently do NOT have the per-output-file `% Generated by ...` markers. This was a Phase-4 sub-task that's been deferred. Recommended follow-up: add `reproduce/inject_provenance.py` that walks the manifest's `outputs` block and injects markers per-format (per plan §6.1 conventions, with `.provenance` sidecars for `.pdf` / `.png` per user decision 6).
