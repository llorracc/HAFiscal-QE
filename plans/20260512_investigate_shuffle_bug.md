---
date: 2026-05-12
status: PLAN — investigation of suspected bug in shuffle MC implementation (REVISED v3)
keywords: [shuffle, MarkovProcess, ergodic, BUG, investigation, refactor]
---

# Plan: Investigate suspected bug in shuffle MC implementation (v3)

## Background and motivation

The 6-seed paired comparison (HS_Only) and 1-seed Baseline comparison both
show that bug_fix shuffle MC gives systematically biased ui_rec values
relative to non-shuffle MC:
- HS_Only: +3.76% bias (13.7σ)
- Baseline: +6.59% bias (22.7σ; ~2× larger at full scope)

Earlier I diagnosed this as a "structural" interaction between shuffle's
quota mechanism and the Markov chain — i.e., a non-bug. **This was wrong.**

## Findings so far (use these per-capita values, NOT raw counts)

### Finding 1 — Mrkv-state divergence at recession-onset is real and large

Per-capita Mrkv distribution at t=0 of recessionUI scenario (HS_Only seed=0,
N=49000):

| state | shuf % | nshuf % | Δ pp | σ |
|---|---:|---:|---:|---:|
| employed | 91.069% | 90.914% | +0.155 | +0.8σ |
| **u1Q** | **4.969%** | **2.422%** | **+2.547** | **+21.2σ** |
| **u2Q** | **3.159%** | **5.541%** | **-2.382** | **-18.3σ** |
| u3Q | 0.514% | 0.745% | -0.231 | -4.6σ |
| u4Q | 0.188% | 0.241% | -0.053 | -1.8σ |
| noBen | 0.100% | 0.137% | -0.037 | -1.7σ |

Total unemployed % is essentially the same (8.93% shuf vs 9.09% nshuf,
+0.16pp), but the **within-unemployed split is re-balanced** — agents are
shifted from u2Q to u1Q at 21σ significance.

### Finding 2 — Divergence is concentrated at t=0 only

| t | shuf u1Q | nshuf u1Q | Δσ | shuf u2Q | nshuf u2Q | Δσ |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 4.97% | 2.42% | +21.2σ | 3.16% | 5.54% | -18.3σ |
| 1 | 2.84% | 2.84% | 0.0σ | 1.70% | 0.83% | +12.3σ |
| 2 | 2.96% | 2.91% | +0.5σ | 0.95% | 0.97% | -0.4σ |
| 3+ | ~3.0% | ~3.0% | <1σ | ~1.0% | ~1.0% | <1σ |

Base scenario (no recession): shuf and nshuf agree to within ~1σ at all t.
So bug is recession-spike-specific.

### Finding 3 — `MarkovProcess.draw(shuffle=True)` is NOT buggy in isolation

Controlled test (`/tmp/test_markov_shuffle_vs_iid.py`): given identical
initial state distribution (95.5% emp, 3% u1Q, 1% u2Q, 0.3% u3Q, 0.1% u4Q,
0.1% noBen), apply 1 transition under cond_mrkv[macro=3] under shuffle and
iid. Result:

| state | shuf % | iid % | expected % | Δ shuf-iid (pp) | σ |
|---|---:|---:|---:|---:|---:|
| 0 | 91.74% | 91.68% | 91.74% | +0.06 | +0.3σ |
| 1 (u1Q) | 4.89% | 4.93% | 4.89% | -0.04 | -0.3σ |
| 2 (u2Q) | 2.25% | 2.26% | 2.25% | -0.01 | -0.1σ |
| 3-5 | within rounding |

So `MarkovProcess.draw(shuffle=True)` gives the SAME expected counts as iid
(non-shuffle) when starting from the SAME pre-state. **The HARK shuffle
algorithm is correct.**

### Finding 4 — The cond_mrkv at macro=3 (recession) used by both paths

```
[[0.9488 0.0512 0.     0.     0.     0.    ]    # emp →
 [0.25   0.     0.75   0.     0.     0.    ]    # u1Q → emp/u2Q
 [0.25   0.     0.     0.75   0.     0.    ]    # u2Q → emp/u3Q
 [0.25   0.     0.     0.     0.75   0.    ]    # u3Q → emp/u4Q
 [0.25   0.     0.     0.     0.     0.75  ]    # u4Q → emp/noBen
 [0.25   0.     0.     0.     0.     0.75  ]]   # noBen → emp/noBen
```

Note: row 5 (noBen) has the SAME transition as row 4 (u4Q): 0.25 to emp,
0.75 to noBen. So once at noBen, agents stay (until re-employed). And
under bug_fix, u3Q/u4Q are intermediate steps in the chain.

## Implication: the bug is UPSTREAM of the per-step transition

Since `MarkovProcess.draw(shuffle=True)` works correctly in isolation, the
divergence at t=0 must come from differences in **what state the chain
starts from** before the first transition.

### Candidate locations of the bug (now narrowed)

1. **The urate-spike code** (lines 818-829 shuffle, 671-679 non-shuffle):
   visually identical, but uses `self.RNG` which may be in a DIFFERENT state
   between shuffle and non-shuffle paths. Need to verify the RNG state at
   spike time.

2. **The pre-spike state** (= what `self.shocks['Mrkv']` contains before
   the spike): this comes from previous simulation steps. If pre-recession
   warmup uses the SAME RNG draws differently in shuffle vs non-shuffle,
   the pre-spike state differs.

3. **The first transition's input** (the `MicroMrkvNow` at t=0 entry):
   non-shuffle sets `self.MicroMrkvNow = self.shocks['Mrkv'] % J` from
   post-spike state. Shuffle does the same. But if `self.shocks['Mrkv']`
   differs between paths, the input differs.

4. **The initial-pre-warmup state** (= `self.shocks['Mrkv']` BEFORE any
   simulation runs): may be set differently by some initialization code.

## Phase R (REVISED v3) — Find the state-divergence point

Income code refactor is OFF the table — shuffle is a population-wide
operation, non-shuffle is per-agent; they're fundamentally different
abstractions. The controlled test (Finding 3) shows the algorithms produce
the SAME expected per-state counts when called on the SAME input — so the
bug must be in the **input state** at t=0 (= what the chain transitions
FROM), not in the algorithms or the income code.

The user-supplied invariant: at least one of the two paths is correctly
implementing the policy. Find which one and fix the other.

### R.1 — Add diagnostic checkpoints to both code paths (~1 hr)

Instrument `hit_with_recession_shock` and `_hit_with_recession_shock_shuffled`
to write per-capita Mrkv distributions at THREE checkpoints:

1. **CHECKPOINT A**: `self.shocks['Mrkv']` immediately on entry (= pre-spike
   state, inherited from previous simulation step). Save as `self._chkpt_A`.
2. **CHECKPOINT B**: `self.shocks['Mrkv']` after the urate-spike code but
   before the per-period loop (= post-spike, pre-1st-transition). Save as
   `self._chkpt_B`.
3. **CHECKPOINT C**: `self.shock_history['Mrkv'][0]` after the loop's first
   iteration (= post-1st-transition; we already know this differs).

Run both paths with seed=12345 on identical agents. Compare per-capita
distributions at each checkpoint. Identify the FIRST checkpoint where they
differ.

### R.2 — Localize the bug based on which checkpoint diverges first

- **A differs**: the bug is in pre-spike simulation (= the `simulate()` call
  before `hit_with_recession_shock`). The shuffle and non-shuffle have been
  doing different things during pre-recession warmup.
- **B differs (but A matches)**: the bug is in the spike code itself
  (lines 818-829 shuffle vs 671-679 non-shuffle, or the `+= 3*J` macro shift).
- **C differs (but B matches)**: the bug is in the per-period transition
  loop (`get_micro_markv_states_guts` vs `mp.draw(shuffle=True)`). But the
  controlled test (Finding 3) suggests this CANNOT be the cause — unless the
  cond_mrkv being passed differs between paths.

The strongest a priori candidate is **A or B**, since the controlled test
ruled out the algorithm-level difference at C.

### R.3 — Determine the "correct" interpretation

Once we know WHERE the divergence comes from, determine which path matches
the intended policy:
- Compare both paths' CHECKPOINT B distributions to what we'd expect from
  the urate-spike rule: u1Q% increases by ~(Urate_recession - Urate_normal),
  other states unchanged.
- The path that matches this expectation is correct.
- Compare to HAFiscal-QE (published) behavior if the rule is ambiguous.

### R.4 — Implement fix behind feature flag (~1 hr)

Once the root cause is identified, implement a fix:
- Behind `HAFISCAL_SHUFFLE_BUG_FIX={off|on}` (similar to BUG-043 pattern)
- Default `off` for backward-compat
- Add diagnostic test that asserts checkpoint distributions match between
  shuffle and non-shuffle (within sampling noise) under the fix

### R.5 — Validate (~1 hr wall + computation)

- Run HS_Only 6-seed paired comparison under `HAFISCAL_SHUFFLE_BUG_FIX=on`
  → bias on ui_rec should drop to <2σ
- Run Baseline 1-seed comparison → bias should drop similarly
- Verify variance reduction property is preserved (= shuffle still gives
  ~15× variance reduction vs legacy shuffle for non-UI cells)

### R.6 — Documentation and re-evaluation (~1 hr)

- Bug dossier: `BUGS_private/HAFiscal_BUG-044_shuffle_*.md`
- Update memory entries for shuffle (resolution if fixed)
- Retract `BUG-043_shuffle_bias_mechanism_diagnosed.md` — was wrong
- Update morning README's shuffle-bias section

## Total estimated effort

R.1 + R.2 + R.3 = 3 hr (the diagnostic + localization)
R.4-R.6 = 3 hr if a clean fix is found

## Key principle

The user's invariant: **at least one of the two paths must be implementing
the policy correctly** — they can't BOTH be wrong in opposite directions.
The bug is in the STATE that one path passes to the chain, not in the chain
itself. Find the checkpoint where the two paths' input state diverges.

## What I will NOT do autonomously

- Push to git remote
- Modify HARK code (only investigate)
- Implement code changes that aren't behind a feature flag
- Claim the bug is "fixed" without empirical validation showing bias <2σ
