s# Runbook: first real anchored run — `./reproduce.sh --comp full --tm-only` on remote

**Date:** 2026-04-25
**Branch:** `feature/reproduce-self-documenting` (the wiring branch; will merge to `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` after this run validates the machinery in production).
**Status:** runbook — execute on remote when ready.
**Plan it implements:** `plans/20260425-1015h_reproduce-self-documenting-runs.md` Phase 6.

## Goal

Produce the first proper reproduction anchor — a commit + tag that captures all the information needed to reproduce the run from a fresh checkout, per the self-documenting-runs design. The vehicle is `./reproduce.sh --comp full --tm-only` (the TM-only Baseline path; ~1–2 hours wall; produces multipliers and IRFs but skips the MC welfare-6 table per the auto-skip in `Output_Results.py`).

This run does *not* produce the MC welfare-6 numbers — that requires `--mc-only` (~6–12 hours) and is a separate anchor for a separate occasion.

## Prerequisites

- Remote machine with more cores than the local laptop (per user's stated preference).
- Same repo cloned, network access to `origin` (GitHub).
- `uv` installed and the venv synced.
- HARK importable from the venv.
- The three input data files present in `Code/HA-Models/Target_AggMPCX_LiquWealth/` (`LiquWealth_Distribution_a.xlsx`, `LiquWealth_Distribution_b.xlsx`, `Data_AggMPC_LotteryWin.xlsx`).

The pre-flight gate verifies all of these and refuses to start if any check fails. Overrides exist (`--accept-dirty`, `--accept-detached`, `--accept-unpushed`) but the goal of *this* run is to clear the gate cleanly so the resulting anchor doesn't carry override flags.

## A. Prepare the remote machine

```bash
# 1. SSH into the remote.
ssh <remote>

# 2. Fetch and check out the feature branch with the wiring.
cd <path-to-HAFiscal-Latest>
git fetch origin
git checkout feature/reproduce-self-documenting
git pull   # confirm at 3e5269d7 or later (the Phase-5 commit)

# 3. Make sure uv env is in sync (HARK + numpy/scipy/etc.).
make sync   # or: uv sync --all-groups
# If broken:  bash reproduce/uv_sync_repair.sh

# 4. Quick sanity check on the wiring: run a NANO smoke first (~10 seconds).
#    Catches any environment issues before committing to the 1–2 hour real run.
./reproduce.sh --comp nano --accept-dirty    # if any local edits exist
# OR (if worktree is clean):
./reproduce.sh --comp nano

# Look for: pre-flight passes; manifest written under reproduce/run-manifests/;
# proposed-commit block printed at the end; exit code 0. Don't commit the nano
# artifacts — clean them up:
rm -f reproduce/run-manifests/comp_nano_*

# 5. Confirm worktree is clean before the real run (the gate refuses otherwise).
git status --porcelain    # should be empty
```

If `git status --porcelain` is **not** empty on the remote, two options:

- **Preferred:** clean it up — `git stash` or commit/discard the unrelated edits. A truly clean run gets `preflight_status: "clean"` rather than `"overridden"` in the manifest. This is what we want for the first anchor.
- **Acceptable:** pass `--accept-dirty` (anchors with overrides are still reproducible — the recipe will require the same override at replay — just less ideal as the first one).

## B. Do the anchored run

Two ways to invoke; pick one.

**(i) Hands-off — auto-commit:**

```bash
./reproduce.sh --comp full --tm-only --auto-commit
```

The `--auto-commit` flag stages the manifest + recipe + pip-freeze + log + output dirs, makes the commit, creates the tag — all automatically. It does **not** push (push remains explicit per the design).

**(ii) Review-then-commit:**

```bash
./reproduce.sh --comp full --tm-only
```

Same outputs. The script prints the proposed-commit block at the end; you inspect the manifest / recipe / commit-msg, then paste the printed `git add ... && git commit -F ... && git tag -a ...` lines.

Either way:

- **Expected wall-clock: ~1–2 hours** (TM + AD iterations on Baseline, 21 types).
- The pre-flight gate runs first; if it fails, the run aborts before any compute.
- **Run inside `tmux` or `nohup ... &`** so you can disconnect from SSH while it runs.

While it runs, monitor:

```bash
# In another shell:
tail -f reproduce/logs/comp_full_<scope>_<timestamp>.log
# Or:
tail -f reproduce/logs/latest.log
```

## C. After the run completes

If you used `--auto-commit`, **skip step C1** (it's already committed and tagged; jump to C2 to push).

### C1. Inspect, then commit + tag (review-then-commit only)

Sanity checks:

```bash
# Manifest fields:
cat reproduce/run-manifests/comp_full_*_tm-only.json | python -m json.tool | less

# Headline numbers landed:
cat Code/HA-Models/FromPandemicCode/Tables/Baseline/Multiplier.tex

# Proposed commit message:
cat reproduce/run-manifests/comp_full_*_tm-only.commit-msg.txt

# Recipe captures the right invocation:
cat reproduce/run-manifests/comp_full_*_tm-only.reproduce-recipe.sh
```

Then run the proposed-commit block printed at the end of the run (or copy from the printed instructions). It looks like:

```bash
git add -f reproduce/run-manifests/comp_full_<UTC>_tm-only.json \
          reproduce/run-manifests/comp_full_<UTC>_tm-only.reproduce-recipe.sh \
          reproduce/run-manifests/comp_full_<UTC>_tm-only_pip_freeze.txt
git add -f reproduce/logs/comp_full_<local-time>.log
git add Code/HA-Models/FromPandemicCode/Tables/Baseline
git add Code/HA-Models/FromPandemicCode/Figures/Baseline
git status                                  # review what's staged
git commit -F reproduce/run-manifests/comp_full_<UTC>_tm-only.commit-msg.txt
git tag -a reproduce-<YYYYMMDD>-comp-full-tm-only \
    -F reproduce/run-manifests/comp_full_<UTC>_tm-only.tag-msg.txt
```

The exact filenames and tag name will be in the printed block — paste verbatim.

### C2. Push commit + tag back to origin

```bash
git push origin feature/reproduce-self-documenting
git push origin reproduce-<YYYYMMDD>-comp-full-tm-only
```

(Two pushes because git won't auto-push tags with branch pushes.)

### C3. Verify from the local machine

```bash
# Back on local:
git fetch origin --tags
git tag -l 'reproduce-*'                           # should list the new tag
git show reproduce-<YYYYMMDD>-comp-full-tm-only --stat
```

## D. After the anchor is in: merge feature branch back

Once the anchor commit + tag look right and pass review:

```bash
# On either machine:
git checkout 0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC
git pull
git merge feature/reproduce-self-documenting
# or rebase if you prefer linear history; either is fine
git push origin 0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC
```

Both the new wiring and the anchor commit (with its tag) are now on the main work branch.

## Things to watch for / known caveats

1. **The first anchor lives on `feature/reproduce-self-documenting`** initially, not on `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`. The merge in §D moves it onto the main branch.
2. **Pre-flight requires the latest commit to be pushed to origin.** Latest is `3e5269d7` (Phase-5 commit) — pushed. If you push more before running, you'll need to fetch on the remote.
3. **TM-only path skips MC welfare-6.** You get `Multiplier.tex` and the IRF/cumulative-multiplier figures; no `welfare6.tex` (skipped by `Output_Results.py` when `cLvl_all_splurge` isn't present). For welfare-6, use `--mc-only` separately.
4. **No per-output-file provenance markers yet.** Plan §6 post-processor was deferred. Outputs are self-locatable via the manifest + commit + tag, but not self-identifying file-by-file. Add later if/when needed (small follow-up).
5. **Failure mode:** any non-zero substep exit code aborts the run. The manifest still gets `finalize`d (with the failed step's exit code) so the partial state is preserved and the failure is documented — just not committable as a successful anchor. The proposed-commit block prints with `exit_code` set, so the user knows not to commit it.
6. **Remote disconnects:** `tmux` / `nohup` is essential — a 1–2 hour run shouldn't be tied to the SSH connection.

## Sign-off criteria for "the anchor is good"

- Run completed with exit code 0 (visible in the manifest's `invocation.exit_code` and the printed end-of-run summary).
- Manifest passes spot-check: `code_state.preflight_status == "clean"` (no overrides), `code_state.git_dirty == false`, `code_state.git_commit` matches `git rev-parse HEAD` on origin.
- `Tables/Baseline/Multiplier.tex` exists, has plausible numbers (multipliers in the 0.8–1.2 range), and matches the values in the commit message.
- The recipe script is executable (`chmod 755` is automatic) and the `exec` line at the bottom is `exec ./reproduce.sh --comp full --tm-only [--auto-commit]`.
- The tag is reachable via `git tag -l 'reproduce-*'` on origin.
- The full chain (manifest → recipe → tag → commit) all live in one git commit and the tag points at it.

## Follow-up after this anchor

The natural next steps once this run validates:

1. **Merge feature branch** back to the main work branch (§D above).
2. **Implement provenance-marker post-processor** (plan §6) so future anchors' output files are individually self-identifying.
3. **Schedule the `--comp full --mc-only` anchor** when there's a 6–12 hour budget — that one captures the welfare-6 numbers.
