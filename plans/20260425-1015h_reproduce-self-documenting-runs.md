# Plan: make `./reproduce.sh --comp` runs self-documenting and exactly reproducible

**Date:** 2026-04-25
**Branch target:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`
**Status:** plan — execute after sign-off.

## 1. Goal

After any `./reproduce.sh --comp ...` run, a coauthor (or future Chris) inspecting the resulting commit should be able to reproduce that run *exactly* — same code, same environment, same flags, same input data, same outputs — without having to guess any setting. The current state is the opposite: the user's own question "how were the recent results generated?" required spelunking through commit messages and plan files to recover the command. We fix that going forward.

## 2. Design principles

1. **Pre-flight gate.** The script refuses to start an `--comp` run unless the worktree is in a known-reproducible state (clean, on a tracked-branch commit). Better to fail fast than to produce un-documentable outputs.
2. **Structured machine-readable manifest** (`reproduce/run-manifests/<scope>_<timestamp>.json`) that captures *everything*. Tooling-friendly. The commit message points at it; the manifest itself does the heavy lifting.
3. **Human-readable companion**: a generated `reproduce-recipe.sh` script, ready to run, that re-creates the exact run.
4. **Every output file is self-identifying.** Each generated artifact gets a one-line provenance marker at its start (per §6.5) that records the run's git commit and the reproducing command. A user inspecting `Multiplier.tex` or `welfare6.tex` in isolation — even disconnected from the manifest — can immediately see *which run produced this and how to reproduce it*.
5. **No auto-commit.** The run produces files (manifest, recipe, outputs); the script *proposes* a commit by writing a ready-to-use `git commit -F` invocation to stdout. The user approves and runs it.
6. **Force-track logs and manifests** as part of the proposed commit, even though they're currently gitignored. The `--comp` outputs (Tables/Baseline/, Figures/Baseline/) come along too.
7. **Hash everything that matters.** Input data files (SCF, FHN), output files (.tex, .pdf), and computed parameters (ς, β̄, ∇). The manifest records hashes so a replay can detect drift.
8. **Don't reinvent existing knobs.** `reproduce.sh` already handles logging, scope dispatch, and env-var control of step skipping; the new code adds a layer on top, not a replacement.

## 3. Pre-flight gate (refuse-to-start checks)

Before any `--comp` work begins, `reproduce.sh` runs a `_preflight_for_comp` function that checks:

| Check | Pass condition | If fail |
|---|---|---|
| **Worktree clean** | `git status --porcelain` returns empty | Print message: "Refusing to start: worktree has uncommitted changes. Run `git status` to see them. Pass `--accept-dirty` to override (the manifest will record git-dirty status and a synopsis)." Exit non-zero. |
| **Branch known** | `git rev-parse --abbrev-ref HEAD` returns a real branch name (not `HEAD` from detached state) | Same idiom; `--accept-detached` to override. |
| **HEAD reachable from a remote** | `git for-each-ref --contains HEAD refs/remotes/` returns at least one match | Print warning + suggest `git push`. Allow with `--accept-unpushed` to record "git_unpushed: true". |
| **HARK importable and version known** | `python -c "import HARK; print(HARK.__version__)"` succeeds | Hard fail — reproducibility impossible without recording HARK version. |
| **Required input data present** | `Code/HA-Models/Target_AggMPCX_LiquWealth/{LiquWealth_Distribution_a,LiquWealth_Distribution_b,Data_AggMPC_LotteryWin}.xlsx` all exist | Hard fail. |

When the gate is fully clean, an opening manifest is initialized at `reproduce/run-manifests/<scope>_<timestamp>.json` (see §4) with `"preflight_status": "clean"`. When any check passes only via an `--accept-*` override, the manifest records the override and the gate-violation summary.

## 4. Manifest schema

The manifest is a single JSON file per run. Schema:

```json
{
  "schema_version": "1",

  "invocation": {
    "command_line": "./reproduce.sh --comp full --mc-only",
    "started_at_utc": "2026-04-25T18:30:00Z",
    "ended_at_utc":   "2026-04-25T19:47:00Z",
    "wall_clock_seconds": 4620,
    "exit_code": 0,
    "user": "ccarroll",
    "hostname": "<hostname>",
    "platform": "darwin-arm64",
    "argv": ["./reproduce.sh", "--comp", "full", "--mc-only"],
    "hafiscal_env_vars_at_start": {
      "HAFISCAL_RUN_STEP_1": "false",
      "HAFISCAL_RUN_STEP_2": "false",
      "HAFISCAL_RUN_STEP_3": "false",
      "HAFISCAL_RUN_STEP_4": "false",
      "HAFISCAL_MC_SHUFFLE": null,
      "HAFISCAL_INCOME_SHUFFLE": null,
      "HAFISCAL_SPLURGE_OLD": null,
      "HAFISCAL_SIM_METHOD": null
    }
  },

  "code_state": {
    "branch": "0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC",
    "git_commit": "<sha at run start>",
    "git_dirty": false,
    "git_status_summary": "",
    "git_unpushed_commits": [],
    "preflight_status": "clean",
    "overrides_used": [],

    "hark_version": "0.17.0",
    "hark_install_path": "/...",
    "hark_git_commit": "<sha if installed from git>",
    "python_version": "3.11.x",
    "platform_release": "<uname -r output>"
  },

  "environment_lock": {
    "uv_lockfile_sha256": "<sha256 of uv.lock>",
    "pip_freeze_path": "reproduce/run-manifests/<scope>_<timestamp>_pip_freeze.txt",
    "python_version_file_contents": "3.11"
  },

  "input_data_hashes": {
    "Code/HA-Models/Target_AggMPCX_LiquWealth/LiquWealth_Distribution_a.xlsx": "<sha256>",
    "Code/HA-Models/Target_AggMPCX_LiquWealth/LiquWealth_Distribution_b.xlsx": "<sha256>",
    "Code/HA-Models/Target_AggMPCX_LiquWealth/Data_AggMPC_LotteryWin.xlsx": "<sha256>"
  },

  "calibration_inputs": {
    "Result_AllTarget_path": "Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt",
    "Result_AllTarget_contents_sha256": "<sha256>",
    "Result_AllTarget_parsed": {"splurge": 0.2609, "beta": 0.9611, "nabla": 0.0668}
  },

  "steps_executed": [
    {
      "step": "5a",
      "command": "python AggFiscalMAIN_reduced.py --baseline",
      "started_at_utc": "...",
      "ended_at_utc": "...",
      "wall_clock_seconds": 1080,
      "exit_code": 0
    },
    {
      "step": "5b",
      "command": "python run_welfare6_parallel.py --baseline --out-dir welfare6_scenario_results_Baseline_reproduce --table-dir Tables/Baseline",
      "started_at_utc": "...",
      "ended_at_utc": "...",
      "wall_clock_seconds": 3540,
      "exit_code": 0
    }
  ],

  "outputs": {
    "Tables/Baseline/Multiplier.tex": {"sha256": "<sha>", "bytes": 510, "mtime_utc": "..."},
    "Tables/Baseline/welfare6.tex":   {"sha256": "<sha>", "bytes": 379, "mtime_utc": "..."},
    "Tables/Baseline/welfare6_parallel_summary.json": {"sha256": "<sha>", ...},
    "Figures/Baseline/Cumulative_multipliers.pdf":    {"sha256": "<sha>", ...},
    "...": "every file under Tables/Baseline/ and Figures/Baseline/ that the run produced or modified"
  },

  "log_file": "reproduce/logs/comp_full_20260425-1830.log",

  "comparison_to_anchor": {
    "anchor_tag": "<previous reproduction tag, if any>",
    "outputs_match": null,
    "note": "Filled in by a downstream tool, optional."
  }
}
```

The `_pip_freeze.txt` companion file holds the full pip-freeze output; the manifest records its sha256 so silent edits are detectable.

## 5. The proposed reproduction recipe (companion script)

In addition to the manifest, the run writes `reproduce/run-manifests/<scope>_<timestamp>.reproduce-recipe.sh`:

```sh
#!/usr/bin/env bash
# Auto-generated reproduction recipe.
# This script reproduces the run captured in the matching manifest.

set -euo pipefail

ANCHOR_COMMIT="<git_commit from manifest>"
ANCHOR_BRANCH="0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC"

# 1. Verify worktree clean.
if [[ -n "$(git status --porcelain)" ]]; then
    echo "Worktree dirty; refuse to replay (commit/stash first)." >&2
    exit 1
fi

# 2. Check out the recorded commit.
git fetch origin
git checkout "$ANCHOR_COMMIT"

# 3. Verify environment matches.
expected_hark="0.17.0"
got_hark=$(python -c "import HARK; print(HARK.__version__)")
if [[ "$expected_hark" != "$got_hark" ]]; then
    echo "HARK version mismatch: expected $expected_hark, got $got_hark" >&2
    echo "Re-sync env: bash reproduce/uv_sync_repair.sh" >&2
    exit 1
fi

# 4. Verify input-data hashes match (sample shown; manifest enumerates all).
for entry in \
    "<sha256>:Code/HA-Models/Target_AggMPCX_LiquWealth/LiquWealth_Distribution_a.xlsx" \
    "<sha256>:Code/HA-Models/Target_AggMPCX_LiquWealth/Data_AggMPC_LotteryWin.xlsx"; do
    expected="${entry%%:*}"; path="${entry#*:}"
    got=$(shasum -a 256 "$path" | cut -d' ' -f1)
    if [[ "$expected" != "$got" ]]; then
        echo "Input-data hash mismatch on $path" >&2; exit 1
    fi
done

# 5. Replay the run with the same env vars and command line.
export HAFISCAL_RUN_STEP_1=false
export HAFISCAL_RUN_STEP_2=false
export HAFISCAL_RUN_STEP_3=false
export HAFISCAL_RUN_STEP_4=false
exec ./reproduce.sh --comp full --mc-only
```

Anyone with the manifest + recipe can `bash reproduce/run-manifests/<scope>_<timestamp>.reproduce-recipe.sh` and get the same outputs.

## 6. Per-output-file provenance markers

In addition to the manifest, every output file the run produces or modifies gets a one-line provenance marker injected at the start of the file. The marker is the same minimal information across formats:

```
<COMMENT_PREFIX> Generated by ./reproduce.sh --comp full --mc-only on commit a1b2c3d4 (2026-04-25 18:30 UTC). Manifest: reproduce/run-manifests/comp_full_20260425-1830.json. Replay: bash reproduce/run-manifests/comp_full_20260425-1830.reproduce-recipe.sh
```

A user opening a single output file in isolation (no manifest, no git context) can immediately see (a) which commit was active, (b) what command produced it, and (c) where to find the full provenance and a one-shot replay.

### 6.1 Per-format conventions

Comment syntax varies by format; the post-process applies the right one for each file extension.

| Extension | Comment syntax | Example marker |
|---|---|---|
| `.tex` | `% ...` | `% Generated by ./reproduce.sh --comp full --mc-only on commit a1b2c3d4 ...` |
| `.csv` | `# ...` (data-aware: only if the consuming tool tolerates `#` comments — otherwise put it in a sidecar `.provenance` file) | `# Generated by ./reproduce.sh ...` |
| `.json` | JSON has no comments; inject `"_provenance": "Generated by ..."` as the first key of the top-level object. For lists at top-level, wrap as `{"_provenance": "...", "data": [...]}`. | `{"_provenance": "Generated by ./reproduce.sh ...", "...": ...}` |
| `.svg` | XML comment `<!-- ... -->` immediately after the XML declaration line | `<!-- Generated by ./reproduce.sh ... -->` |
| `.pdf` | Inject as `/Subject` or `/Keywords` PDF metadata via a post-processor (e.g., `qpdf --set-info`/`pikepdf`); also write a `.provenance` sidecar text file alongside | (metadata field; not visible in viewer chrome but `pdfinfo` shows it) |
| `.png` | Embed as a `tEXt` chunk via `pillow` (`PIL.Image.save(..., pnginfo=...)`); also write a `.provenance` sidecar | (tEXt chunk; visible via `exiftool`) |
| `.pickle` | Wrap the pickled object so the top-level dict has a `"_provenance"` key (or write a `.provenance` sidecar — pickle modification is fragile) | `pickle.load(...)["_provenance"]` |
| `.txt` / `.log` | `# ...` at line 1 | `# Generated by ./reproduce.sh ...` |

### 6.2 Implementation: post-process at end of run

The marker injection happens once, at the end of the run, in a single helper (`reproduce/inject_provenance.py`). The post-processor walks every file listed in the manifest's `outputs` block, opens it according to its extension, and prepends/embeds the marker. Doing this once at the end avoids touching every writer call site in the codebase.

**Idempotency:** the helper checks whether the marker is already present (string match on `Generated by ./reproduce.sh`) and skips if so; this matters when an output file is regenerated by a subsequent run.

**Hashing order matters.** The output-file hashes recorded in the manifest's `outputs` block are computed *after* marker injection (otherwise the on-disk file's hash would not match what the manifest claims). Replay scripts that hash for verification therefore hash the marker-included file.

**Files for which marker injection is unsafe** (e.g., binaries the consuming tooling would mis-parse if metadata is added) — the post-processor skips them and writes a `.provenance` sidecar instead. The manifest records which files got an in-file marker vs a sidecar.

## 7. Storage layout


Add a new tracked directory at the repo root:

```
reproduce/
├── logs/                          # existing; .log files gitignored
├── run-manifests/                 # NEW — tracked
│   ├── .gitignore                 # excludes *.commit-msg.txt and *.tag-msg.txt
│   ├── comp_full_20260425-1830.json
│   ├── comp_full_20260425-1830.reproduce-recipe.sh
│   ├── comp_full_20260425-1830_pip_freeze.txt
│   ├── comp_full_20260425-1830.commit-msg.txt    # generated, gitignored (scratch for `git commit -F`)
│   └── comp_full_20260425-1830.tag-msg.txt       # generated, gitignored (scratch for `git tag -a -F`)
└── (existing dispatcher scripts)
```

Key choices:

- **Manifest, recipe, and pip-freeze are tracked.** They're small (a few KB each), make the run discoverable, and get carried along by `git log`.
- **Logs are also tracked**, but only as part of the proposed commit (force-add). Otherwise `*.log` stays in `.gitignore`. This means logs accumulate only for runs the user actually commits, not every casual invocation.
- **The commit-message and tag-message scratch files** (`.commit-msg.txt`, `.tag-msg.txt`) are generated by the script but `.gitignore`d — they exist only to be passed to `git commit -F` and `git tag -a -F`. The substantive content they contain is also embedded in the manifest, so excluding them from the repo loses nothing.

## 8. Post-flight: proposing the commit

When the run completes (whether successfully or with an error), the script writes the manifest, recipe, and pip-freeze, then prints a clearly-marked block to stdout:

```
====================================================================================
REPRODUCTION COMMIT — proposed (NOT auto-committed)
====================================================================================

Manifest:        reproduce/run-manifests/comp_full_20260425-1830.json
Recipe script:   reproduce/run-manifests/comp_full_20260425-1830.reproduce-recipe.sh
Pip freeze:      reproduce/run-manifests/comp_full_20260425-1830_pip_freeze.txt
Log:             reproduce/logs/comp_full_20260425-1830.log

To stage, commit, and tag this run, review then run:

    git add -f reproduce/run-manifests/comp_full_20260425-1830.{json,reproduce-recipe.sh,_pip_freeze.txt}
    git add -f reproduce/logs/comp_full_20260425-1830.log
    git add Code/HA-Models/FromPandemicCode/Tables/Baseline/
    git add Code/HA-Models/FromPandemicCode/Figures/Baseline/
    git status                                  # review what's staged
    git commit -F reproduce/run-manifests/comp_full_20260425-1830.commit-msg.txt
    git tag -a reproduce-20260425-comp-full-mc-only \
        -F reproduce/run-manifests/comp_full_20260425-1830.tag-msg.txt
    # Optional: git push origin <branch> && git push origin reproduce-20260425-comp-full-mc-only

The proposed commit message file says, in part:

  reproduce: ./reproduce.sh --comp full --mc-only run on 2026-04-25 18:30 UTC
            (commit <sha>; HARK 0.17.0; clean worktree)

  Wall: 1h 17min. Step 5a (TM multipliers): 18min. Step 5b (MC welfare-6,
  parallel): 59min.

  Splurge ς = 0.2609; β̄ = 0.9611; ∇ = 0.0668 (from Result_AllTarget.txt
  sha256 <hash>).

  Outputs:
    Tables/Baseline/Multiplier.tex   sha256 <hash>
    Tables/Baseline/welfare6.tex     sha256 <hash>
    ... (full list in manifest)

  To replay exactly:
    bash reproduce/run-manifests/comp_full_20260425-1830.reproduce-recipe.sh

  Tagged as: reproduce-20260425-comp-full-mc-only
  Full manifest: reproduce/run-manifests/comp_full_20260425-1830.json
====================================================================================
```

The user pastes the `git add ... && git commit ... && git tag ...` lines (or runs them in sequence after staging) and is done. No surprise commits or pushes.

**Tag naming:** `reproduce-<YYYYMMDD>-<scope>[-<modifier>]`. The script generates the tag name from the run's UTC date and the `--comp <scope>` plus any modifier flags (`--mc-only`, `--tm-only`). Collisions are resolved by appending `-2`, `-3`, etc. (e.g., a same-day re-run with the same flags becomes `reproduce-20260425-comp-full-mc-only-2`).

**`--auto-commit` flag.** When set on the `reproduce.sh` invocation (default off), the script does the staging + commit + tag itself after the run completes successfully. It still does not push — pushing remains the user's explicit step.

## 9. Implementation phases

1. **Phase 1 — pre-flight gate (small, can ship alone).** Add `_preflight_for_comp` to `reproduce.sh`. Refuse on dirty/detached/missing-input. Add `--accept-dirty`, `--accept-detached`, `--accept-unpushed` overrides. ~150 lines of bash. No manifest yet.
2. **Phase 2 — manifest + pip-freeze.** Add a Python helper `reproduce/build_manifest.py` that builds the JSON from the bash-collected variables. `reproduce.sh` invokes it at start (initial manifest), at every step (append step records), and at end (finalize). Records env, code state, input-data hashes, output-file hashes, exit codes. Recipe-script generator is a small Jinja-style template (could just be heredocs). ~300 lines of Python, ~50 of bash glue.
3. **Phase 3 — recipe script + commit-message + tag generators.** Same helper, additional methods. The commit-msg and tag-msg templates are fixed strings with substitutions; the tag-name generator constructs `reproduce-<YYYYMMDD>-<scope>[-<modifier>][-N]` with collision-resolution against existing local + remote tags. ~150 lines.
4. **Phase 4 — wiring into the real entry points.** Each substep in `reproduce.sh` (`_run_comp_full_mc_only`, `_run_comp_full_tm_only`, `_run_comp_<scope>`) gets a `_record_step` call. Per-step wall-clock and exit-code recording. ~50 lines.
5. **Phase 5 — testing.** Run a `--comp nano` (the smallest scope) end-to-end. Verify: manifest has all required fields, recipe script actually replays, output hashes match between back-to-back runs, pre-flight gate refuses to run on dirty worktree.
6. **Phase 6 — first real anchored run.** Once Phases 1–5 are signed off, do an `--comp full --mc-only` on the current HEAD, commit the manifest+recipe+log+outputs as proposed, and tag (e.g., `reproduce-2026-04-25-comp-full-mc-only`). This becomes the first proper reproduction anchor.

**Total implementation:** ~650 lines across bash + Python, ~2 days of development plus the actual full run. The `--auto-commit` path adds ~50 lines on top (Phase 4 / Phase 5).

## 10. Validation tests

- **Replay test:** run twice in a row with no code changes; the recipe script from run 1 must reproduce run 2's outputs to the byte (hash-equal). This catches non-determinism.
- **Dirty-refusal test:** create a trivial uncommitted edit, run `./reproduce.sh --comp nano` — must refuse with the documented message.
- **Override test:** same with `--accept-dirty`; must run, and the manifest must record `git_dirty: true` plus the diff synopsis.
- **Stale-input test:** edit `Data_AggMPC_LotteryWin.xlsx` between two runs; the recipe script from run 1 (hash check in step 4) must refuse to replay run 2.
- **Schema validation:** the manifest JSON must validate against a JSON-schema file checked into `reproduce/run-manifests/manifest.schema.json`.

## 11. Risks and trade-offs

| Concern | Note |
|---|---|
| **Log file size.** | A `--comp full` log can be megabytes. Force-tracking adds bulk to the repo over time. **Mitigation:** the gitignore stays `*.log`; only logs from runs the user explicitly commits are tracked. Casual invocations don't accumulate. |
| **Commit message bloat.** | If the user uses the proposed full message, it's ~30 lines. That's fine (well under common message-length norms). |
| **Pre-flight false positives.** | The dirty check might trip up users mid-development. **Mitigation:** the `--accept-dirty` override exists; the manifest records the override so reviewers can see it was deliberate. |
| **Output-file hashing of large pickle outputs.** | Step 5b writes large pickles in `welfare6_scenario_results_*/`. Hashing them all could take seconds. **Mitigation:** restrict output hashing to the `Tables/Baseline/` and `Figures/Baseline/` files (the actual paper outputs); the working-set pickles are intermediate and need not be tracked or hashed. |
| **Non-determinism in MC at exact-hash level.** | If random seeds aren't fully pinned, two runs might produce slightly different welfare6.tex bytes (e.g., trailing whitespace, float formatting). **Mitigation:** the welfare6_mc pipeline already uses CRN with explicit seeds; any drift is a real bug worth catching. The replay test in §9 surfaces it. |
| **What about reproduction across machines?** | Hashes will match only on the same OS/arch and the same numerical libraries. **Mitigation:** the manifest records `platform`; replay on a different platform will produce slightly different floats, which is not the manifest's fault. The recipe script can include an `--allow-platform-drift` flag. |
| **HARK installed via uv git ref.** | If `HARK` is installed from a git URL (per `pyproject.toml`), record both its `__version__` and the git SHA. The current uv setup pins a SHA in `uv.lock`; the manifest captures that. |

## 12. Optional stretch goals (defer)

- **Comparison report.** A separate tool reads two manifests and diffs them — output-hash deltas, env deltas, parameter deltas. Useful for "what changed between this run and the anchor run?"
- **Manifest-driven CI.** Periodic CI that re-runs the recipe of the most recent committed manifest and verifies the outputs still match. Catches regressions.
- **Across-anchor browsing.** A small static HTML index of all committed manifests (date, scope, command, output hashes), generated from the JSON files. Helps discover what runs exist.

## 13. Variations on the user's proposed mechanism

The user's proposal is essentially: *clean worktree → record commit at start → propose commit at end with reproduction recipe in the message and the log force-added.* This plan keeps that core but adds:

- **A structured manifest file** alongside the commit message — easier to grep/diff/programmatically inspect than a free-form message.
- **Per-output-file provenance markers** (per §6) — every generated `.tex`, `.json`, `.svg`, etc. carries a one-line marker at its start identifying the run's commit and the reproducing command. Per the user's clarification: a coauthor inspecting an isolated output file (no manifest, no git context) immediately sees who made it and how to remake it.
- **A ready-to-execute recipe script** — the user (or a CI system) can replay with one shell invocation.
- **Input-data hashing** — catches silent edits to the SCF / FHN target files.
- **Output-file hashing** — fingerprints what was produced; replay can verify.
- **Pre-flight gate that refuses to start** rather than running first and recording state — more disciplined: no chance of producing un-documentable outputs.
- **Override flags with explicit recording** (`--accept-dirty`, etc.) — preserves the strict default while leaving room for legitimate exceptions.

Everything else (commit-msg recipe, force-add log) is preserved as-is.

## 14. Resolved decisions (2026-04-25)

### 14.1 Plan-design decisions (settled before implementation)

1. **Dirty worktree:** default is **hard refuse**. `--accept-dirty` override available; the manifest records the override and a diff synopsis when used.
2. **Tracking logs in git:** **force-add into the proposed commit** — only logs from runs the user actually commits get tracked; casual invocations don't accumulate.
3. **Auto-commit option:** **include from day one** as `--auto-commit` (default off). When set, the run does the staging + commit + tag itself; no push (still user-controlled).
4. **Manifest location:** **`reproduce/run-manifests/`** — co-located with the rest of the replay machinery under `reproduce/`.
5. **Tag policy:** **every committed reproduction also gets a git tag** of the form `reproduce-<YYYYMMDD>-<scope>[-<modifier>]` (e.g., `reproduce-20260425-comp-full-mc-only`). Tags are reachable from the command line via `git tag -l 'reproduce-*'`. The proposed commit script (§8) emits both the `git commit -F ...` and the `git tag -a ...` invocations.

### 14.2 Implementation decisions (settled at start of execution)

1. **Branch:** implementation work happens on **`feature/reproduce-self-documenting`**, branched off the working branch. Merges back when complete and tested.
2. **Submodule cleanliness in pre-flight:** **do not insist on submodule cleanliness.** But **do** record the version of HARK being used as part of the environment-lock block (`code_state.hark_version`, `code_state.hark_install_path`, `code_state.hark_git_commit` if installed from git, plus the fully-resolved entry from `uv pip freeze`).
3. **Environment lock command:** **`uv pip freeze`** — captured to a sidecar `.txt` and hashed in the manifest.
4. **Input-data-hashing boundary:** **broad** — hash the three target-data `.xlsx` files in `Code/HA-Models/Target_AggMPCX_LiquWealth/`, the existing calibration output `Code/HA-Models/Target_AggMPCX_LiquWealth/Result_AllTarget.txt` (which is an *input* to Step 5 even though it's an output of Step 2), and any other data files Step 5 reads at startup.
5. **JSON output wrapping:** **second-then-third progression with no schema-breaking wrap.** When the existing top-level structure is a dict, add `"_provenance"` as a sibling top-level key (non-breaking). When the top-level is a list (or any non-dict), do not modify the file — write a `.provenance` sidecar instead.
6. **PDF / PNG provenance markers:** **`.provenance` sidecar only.** No metadata injection. The user's concern is that `pikepdf`/`PIL` metadata writes might trip up LaTeX (which embeds PDFs and reads PNGs as images); the conservative path is to leave the binary intact and place the marker in a sibling `<filename>.provenance` text file.
7. **Replay-test tolerance:** allow **within-numerical-tolerance differences with a tolerance of 3 significant digits** for floats in JSON / TeX outputs across back-to-back runs. Byte-equality is no longer required; the comparator parses numerics out of `.tex` / `.json` and compares them at 3-sig-fig precision.
8. **Phase 6 (first real anchored run):** **deferred** — user will run on a remote with more cores. Phases 1–5 proceed without it.

### 14.3 Decisions made autonomously during implementation

These are recorded as I make them in [`reproduce/run-manifests/decisions.md`](../reproduce/run-manifests/decisions.md). User can review and override at any point.
