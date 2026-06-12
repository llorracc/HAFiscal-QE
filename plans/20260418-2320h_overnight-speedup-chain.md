# Overnight speedup experiments — 2026-04-18 night → 2026-04-19 morning

**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_matsya_explore-further-speedups`
**User returns:** ~8 am 2026-04-19
**Deliverable:** `plans/results/20260419-0056h_overnight-digest.md` + PushNotification on completion.

## Guardrails

- No merges. No pushes to master. No destructive git ops.
- Every experiment gated by env var so defaults are unchanged.
- Numerical equivalence (max |Δβ|, max |Δdistance|) verified before timing is reported.
- If any leg fails or produces an implausible result, log + skip to next leg.

## Chain

1. **Finish step-2 measurement `bjhi79cuh`** (in flight, HS full NM, HAFISCAL_NM_IN_PLACE=1, no maxfun cap). Wall should tell us whether the do_all.py "48 h" nominal is real or stale.
2. **Serial-vs-parallel test (`HAFISCAL_SERIAL=1`).** Run HS full NM with HAFISCAL_SERIAL=1 (routes through `multi_thread_commands_fake` — no joblib workers). Compare wall to (1). Hypothesis: small enough per-agent work that avoiding joblib spawn overhead wins.
3. **Loky pool persistence tuning.** Set `LOKY_IDLE_WORKER_TIMEOUT=3600` (default 300 s) and re-run HS full NM. Should eliminate the ~25 s cold-import cost per worker respawn in the in-place path. Compare to (1).
4. **Step 4 (HANK/SAM) profile.** Run `python HA-Fiscal-HANK-SAM.py` under the profile harness. Nominal 13 h. Gives Phase 3 baseline.
5. **Digest + notification.** Write `plans/results/20260419-0056h_overnight-digest.md` and call `PushNotification` at ~7:30 am.

## Sequencing

Runs strictly serial to avoid CPU contention. Wakeups used to advance the chain. If the chain exhausts well before 7 am, idle; if an item is still running at 7 am, notify with partial results.
