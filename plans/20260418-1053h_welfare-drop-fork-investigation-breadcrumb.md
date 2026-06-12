# Welfare-drop investigation — fork breadcrumb

**Created:** 2026-04-18
**Fork:** `llorracc/HAFiscal-welfare-drop-investigation` (private)
**Base commit:** `01fc50f8` (QE publish, pristine HARK 0.14.1)
**Branch on fork:** `welfare-drop-investigation`

## Why a fork?

The investigation requires:
- Setting up a Python 3.10 + HARK 0.14.1 environment parallel to the 0.17.0 env in this repo
- Backporting current-code speedups (fork-based parallelization, mc_welfare_diagnostic.py) to the 0.14.1 codebase
- Iterating on hypotheses without touching this repo's active work

Doing this in-place here would interleave with ongoing work on the splurge / TM_a investigation. The fork isolates the welfare-drop investigation until it produces a conclusion.

## What it is investigating

The bisection we ran at Reduced_Run scope (`plans/20260418-1053h_welfare-drop-bisection.md`; raw outputs in `/tmp/welfare_diag/bisect/summary.tsv`) tentatively attributes ~59 % of the QE-to-HEAD welfare-6 drop to "the HARK 0.14.1 → 0.17.0 upgrade itself." The claim rests on Reduced_Run runs at six post-upgrade checkpoints showing UI W_6 ≈ 1.72 (post-upgrade) versus the known QE Baseline value of 2.13 (inferred ≈ 2.19 at Reduced_Run scope). But:

1. The QE-era code was never run at Reduced_Run scope directly. The 2.19 Reduced_Run number is extrapolated.
2. The "equivalence" commit (`5b9c02f3`, 2026-03-21) verified **0.14.1 + BoroCnstNat fix ≡ 0.17.0**, not **pristine 0.14.1 ≡ 0.17.0**. The latter — which is what the QE paper numbers actually came from — was never established.
3. Earlier informal testing suggested the BoroCnstNat fix alone does not meaningfully change welfare numbers. This needs to be confirmed properly.

The fork's job is to pin down what, if anything, inside the HARK 0.14.1 → 0.17.0 transition produces the ~0.41 drop in UI W_6 — or to show that the drop is scope-dependent and does not appear at Reduced_Run scope at all.

## Plan summary

See the fork's `plan/welfare-drop-fork-handoff.md` for the full plan. In brief:

1. **Port speedups to 0.14.1** (fork-based per-duration parallelization; mc_welfare_diagnostic.py). Goal: Reduced_Run MC welfare6 in ~15 min on 0.14.1 code.
2. **Verify each port is behavior-preserving** by comparing Reduced_Run output before/after the port on the same 0.14.1 base.
3. **Anchor test:** run pristine 0.14.1 Reduced_Run welfare6. Confirms the Reduced_Run extrapolation of QE's 2.13 and provides the anchor for subsequent patch comparisons.
4. **BoroCnstNat test:** apply only the BoroCnstNat fix (BUG-001) to pristine 0.14.1. Compare ΔW_6 against anchor. Expected (per user recollection): negligible effect.
5. **If BoroCnstNat is small (expected):** extend the comparison to other 0.14.1→0.17.0 delta candidates — newborn PermShk (BUG-003), ergodic age init (BUG-004), KinkedR grid (BUG-002) — each as a minimal patch on pristine 0.14.1.
6. **If no single patch explains the drop:** the gap is either scope-dependent (Reduced_Run does not show it; need 21-type Baseline) or comes from multiple interacting changes. Plan Phase B accordingly.

## What gets committed where

- **All investigation code, diagnostic outputs, and findings live on the fork's `welfare-drop-investigation` branch.**
- **This repo (`HAFiscal-Latest`) is not touched by the fork during the investigation.** No PRs back to this repo mid-investigation.

## Reintegration plan

When the investigation concludes, the findings are merged back to this repo as follows:

1. **A single write-up document** is cherry-picked from the fork into `BUGS_private/HAFiscal_splurge_budget_inconsistency/welfare-drop-root-cause.md` (or similar name), summarizing:
   - Which HARK/HAFiscal change(s) drove the ~0.41 W_6 drop, with quantitative attribution per patch
   - Whether the effect is scope-dependent (Reduced_Run vs Baseline)
   - Implications for the paper's erratum/appendix framing
2. **This breadcrumb file** is revised in place with the finalized attribution numbers, replacing the current "HARK upgrade ~59 %" tentative claim with the patch-level breakdown.
3. **`BUGS_private/HARK+HAFiscal_TM_vs_MC_bug_index.md`** gets a new entry (or amendments to BUG-001/002/003/004) flagging the welfare-6 impact of each HARK-level fix, if any.
4. **No code from the 0.14.1 codebase is backported to this repo.** The 0.14.1 modifications exist solely to measure behavior; they are not part of the path forward.
5. **After reintegration:** `gh repo delete llorracc/HAFiscal-welfare-drop-investigation` (optionally via `gh repo archive` first if we want to preserve the history externally).

This breadcrumb file itself stays in `plan/` as the durable record of why the fork existed and where the answers went.

## How to pick up from here

A fresh Claude Code session (on any machine) can work on the investigation by:

```bash
git clone git@github.com:llorracc/HAFiscal-welfare-drop-investigation.git
cd HAFiscal-welfare-drop-investigation
git checkout welfare-drop-investigation
cat plan/welfare-drop-fork-handoff.md    # full briefing
```

The handoff doc on the fork contains the detailed task list, env-setup recipe, and verification protocol.
