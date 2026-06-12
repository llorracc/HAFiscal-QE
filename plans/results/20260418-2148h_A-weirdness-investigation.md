# Investigation of "A weirdness" — why `return_parameters()` fires 800+ times in step 2

**Date:** 2026-04-18
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC_matsya_explore-further-speedups`
**Context:** Background task "A" (HS full NM, `HAFISCAL_EDTYPES=1 python EstimAggFiscalMAIN.py`) ran 108 min and wrote 2759 lines of stdout, 800+ of them repeated prints of the INITIAL DiscFacDstns values from `Parameters.py:315`. We wanted to know what was calling `return_parameters()` so many times.

## Finding

A stack trace at `Parameters.py:315` during an off-mode NM run revealed the call path:

```
loky worker _bootstrap
  → _ForkingPickler.loads (unpickling queue item)
  → importlib.exec_module
  → AggFiscalModel.py:62: return_parameters(OutputFor='_Model.py')
  → Parameters.py:315: print('EducationGroup: ', e, ', betaDistr :', ...)
```

**Every time joblib's loky backend spawns a new worker process, that fresh worker imports `AggFiscalModel.py`, which at its module-top (line 62) calls `return_parameters()` to fetch six Markov-array builder functions. The full `return_parameters()` body runs — including the DiscFacDstns loop that produces the verbose print.**

## Cost

Measured on this machine:

| Call | Wall |
|---|---:|
| `return_parameters(OutputFor='_Model.py')` cold (fresh Python process) | **1151 ms** |
| Same, warm (second call in same process) | ~20 ms |

Parameters.py has essentially no module-level code (just `def return_parameters()`); the 1.15 s cold cost is dominated by imports inside the function body (scipy.stats, HARK distributions, HARK Markov-array helpers).

## Print-count data ⇒ worker-respawn rate

From the validator logs (prints per NM iteration across modes):

| Run | Prints | NM iters | Prints/iter |
|---|---:|---:|---:|
| off ed=0 N=30 | 225 | 30 | **7.5** |
| off ed=1 N=5 | 50 | 5 | **10** |
| off ed=2 N=10 | 30 | 10 | **3** |
| on ed=0 N=30 | 22 | 30 | 0.73 (all init) |
| on ed=1 N=5 | 22 | 5 | 4.4 (all init) |
| on ed=2 N=10 | 22 | 10 | 2.2 (all init) |

**The deepcopy-per-NM-iter path triggers 3-10× more worker respawns per NM iter than the in-place path.** Each respawn pays ~1.15 s of fresh-process import overhead. The in-place path's 22 prints are all from the initial pool creation; subsequent iterations reuse the same workers (0 respawns on top of the initial 22).

The exact mechanism by which `deepcopy(BaseTypeList[educ_type])` causes loky to respawn workers is not fully nailed down — likely candidates are (a) memory pressure from the per-iter deepcopy causing loky to cycle workers, (b) pickle complexity of the deepcopied agent triggering different worker-pool policy, or (c) something in HARK's `multi_thread_commands` that reuses workers differently when inputs contain fresh objects. Investigation could pursue this but the practical fix is already in hand (HAFISCAL_NM_IN_PLACE=1 avoids the deepcopy).

## Net wall-time impact

| Scenario | Spawns × 1.15 s | Run wall | % overhead |
|---|---:|---:|---:|
| A (off, HS full NM) | 828 × 1.15 s ≈ 16 min | 108 min | **~14 %** |
| off DO N=30 | 225 × 1.15 s ≈ 4 min | 27 min | **~16 %** |
| on DO N=30 | 22 × 1.15 s ≈ 25 s | 20 min | ~2 % |

So a large fraction of the 1.27–1.35× speedup we measured from `HAFISCAL_NM_IN_PLACE=1` comes from avoiding these worker respawns, not from solver warm-start per se. That's a useful refinement of the Phase 1.2 story.

## Residual speedup opportunity

Even in the on-mode path, 22 worker-spawn events at the start of each run cost ~25 s of cold-import overhead. On a short run that's non-trivial.

Three candidate fixes ordered by ROI:

1. **Test `HAFISCAL_SERIAL=1`.** `multi_thread_commands_fake` is the serial path; using it eliminates joblib workers entirely. Whether this is a net win depends on whether per-agent simulation is longer than the worker-spawn amortized cost. 30-min experiment to measure, zero code change.
2. **Tune loky worker persistence.** `LOKY_IDLE_WORKER_TIMEOUT`, `LOKY_MAX_CPU_COUNT`, etc. let us keep workers alive longer. May eliminate the 22 prints in on-mode by preventing the pool from cycling. Cheap to test.
3. **Move `AggFiscalModel.py:62` to a lazy accessor.** Every worker would still import AggFiscalModel, but the expensive `return_parameters` call would happen only when the builder functions are actually used. Requires patching the 21 references in AggFiscalModel. Invasive. Probably not worth doing until we confirm #1 or #2 isn't enough.

## Decision

Leave this on the backlog for the next speedup-exploration session. The Phase 1.2 speedup is already committed and default-on. The Phase 1.2 story is sharpened — the speedup is partly from warm-start, partly from avoiding worker-pool thrash — but that refinement doesn't change the decision to land it.

## Diagnostic artifacts (not committed)

- Stack-trace patch to Parameters.py:315: reverted.
- `HAFISCAL_TRACE_RETURN_PARAMS=1` env-var gate: reverted.
