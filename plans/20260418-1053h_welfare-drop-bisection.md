# Welfare-6 drop bisection: locate the commit(s) responsible for QE 2.13 → current 1.39

## Context

Welfare-6 (UI, Rec=1, AD=1) moved from **2.13 (QE published)** to **1.39 (current Phase 6-prime)** — a ~35% drop. Single-channel isolation tests attribute:

- BUG-031 asset-update alone: ~1.7 %
- (β, ∇) re-estimation (m-TM → a-TM): ~2 %
- ς re-estimation (0.2461 → 0.2609): ~0.3 %
- **Sum of isolated channels: ~4 %**

Commit `2680b3a0` (2026-04-13) ran Baseline welfare6 at T_age=200, lagged AD-timing, **pre-splurge-in-budget**, and already had UI Rec=1 AD=1 = **1.41** — i.e. the bulk of the QE-to-current gap was established *before* any of the splurge work, during the HARK 0.14.1 → 0.17.0 upgrade era. See `plans/20260418-1053h_welfare-drop-fork-investigation-breadcrumb.md`.

The bisection locates the commit(s) that introduced the welfare drop, enabling a clean attribution narrative for the online appendix / erratum.

## Checkpoints

Each checkpoint is run at Reduced_Run scope (3 types × 7 β atoms, 5 min MC) to get a fast signature. Primary readout: W_6(UI, Rec=1, AD=1).

| # | Commit | Date | State | Env | Expected UI W_6 |
|---|---|---|---|---|---|
| 0 | `01fc50f8` | 2026-01-20 | QE publish (HARK 0.14.1) | py310 + HARK 0.14.1 | **2.13** (ground truth) |
| 1 | `2db82a86` | — | Migrate to HARK 0.17.0 | py311 + HARK 0.17 | ? — isolates HARK upgrade |
| 2 | `a2a50c24` | — | HARK 0.17 + API compat | py311 + HARK 0.17 | ? |
| 3 | `5b9c02f3` | — | 0.14.1 ↔ 0.17.0 equivalence confirmed | py311 | ? — should match #2 |
| 4 | `c45cd8e9` | — | AggFiscal → AggIndMrkvConsumerType Markov refactor | py311 | ? — isolates Markov restructuring |
| 5 | `58444c83` | — | Phase 1 TM fix + BUG-014 + mCount=100 | py311 | ? |
| 6 | `2680b3a0` | 2026-04-13 | Baseline welfare6 at T_age=200 lagged pre-splurge-in-budget | py311 | ~1.41 (Baseline; Reduced_Run ≈) |
| 7 | HEAD | 2026-04-18 | current Phase 6-prime | py311 | ~1.42 (Reduced_Run; Baseline 1.39) |

## Env constraints

- **Checkpoint 0 (QE publish)** is on HARK 0.14.1 which requires Python 3.10. This is a separate venv setup — not automated in v1 of the bisection runner. Skip unless/until a py310 + HARK 0.14.1 env is established.
- **Checkpoints 1–7** should all run on the current py311 + HARK 0.17 toolchain, pending resolution of any ephemeral incompatibilities (API churn during the upgrade).

## Infrastructure

- `Code/HA-Models/FromPandemicCode/bisect_welfare.sh` — orchestrator. Takes a list of commit SHAs. For each:
  1. `git worktree add ../bisect-<sha> <sha>`
  2. Copy the current `mc_welfare_diagnostic.py` + `analyze_splurge_isolation.py` (ς-isolation form) into the worktree (so the diagnostic exists even at old commits where it hadn't been written yet).
  3. From the worktree, run the diagnostic → produces `/tmp/welfare_diag/bisect/<sha>.npz`.
  4. Extract W_6 for UI Rec=1 AD=1 and append to `/tmp/welfare_diag/bisect/summary.tsv`.
  5. `git worktree remove ../bisect-<sha>`.
- Per-checkpoint expected wall time: ~5 min MC + ~30 s analysis = ~5.5 min.
- Total: 5 checkpoints × 5.5 min ≈ 30 min.

## Decision tree

Once summary.tsv populates:

- If W_6 drops sharply at one specific checkpoint (e.g., #1 or #4), that commit is the primary culprit — continue bisecting within its range if needed.
- If W_6 drifts monotonically across several checkpoints, the drop is an accumulation of smaller changes — report the attribution by phase (HARK upgrade / Markov refactor / TM work / splurge work) with percentage contributions.
- If W_6 is already ≈1.4 at checkpoint #1 (post-HARK-upgrade), the HARK 0.14.1 → 0.17.0 upgrade itself is the dominant driver and deserves a forensic investigation inside HARK.
- If W_6 is still ≈2.0 at checkpoint #4 but drops at #5, it's the BUG-014 / Phase 1 TM era.

## Output

`/tmp/welfare_diag/bisect/summary.tsv` with columns: commit, date, one_line_msg, UI_W6_rec1_ad1, UI_M_10y, Check_W6_rec1_ad1, Check_M_10y.

A short addendum to `plans/20260418-1053h_welfare-drop-fork-investigation-breadcrumb.md` reporting the attribution once the bisection completes.
