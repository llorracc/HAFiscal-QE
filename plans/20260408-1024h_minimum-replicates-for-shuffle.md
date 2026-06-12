# Plan: minimum replicate size for Markov shuffle in HAFiscal

**Date:** 2026-04-06  
**Problem:** The Markov shuffle (deterministic floor-plus-leftover allocation of agents to destination states) requires enough agents in each source state that `floor(N_j * p_jk)` is at least 1 for every destination state k with nonzero probability. With too few agents, the shuffle falls back to stochastic draws, defeating its purpose.

---

## 1. The constraint

For source state j with N_j agents and transition probabilities p_j0, p_j1, ..., p_j(K-1), the shuffle assigns `floor(N_j * p_jk)` agents to destination k. This gives at least 1 agent to every reachable destination only if:

    N_j >= 1 / min(p_jk for p_jk > 0)

More precisely, the **minimum replicate size** J_min for source state j is:

    J_min(j) = lcm of denominators of p_jk expressed as fractions in lowest terms

For exact frequencies (zero leftover), N_j must be an exact multiple of J_min(j). For approximate frequencies (small leftover), N_j just needs to be "large enough" relative to J_min(j).

## 2. HAFiscal's Markov structure

> **Correction (2026-04-19).** The original §2.1 table and the "J_min ≈ 6 / 1,200 per
> type" figure below used `Rspell` where `Uspell_normal` was meant. `Rspell` is the
> expected **recession** length (macro Markov), not the unemployment spell
> (micro Markov). Separately, §2.3/§2.3.1 gave "1,200 per group" as the minimum
> replicate size for a single-β cohort. That figure represents only
> **J_min coverage** (each micro state has at least J_min agents so the shuffle
> doesn't fall back to stochastic draws). It is **not** quota-exact N, which is
> the stronger condition required for the aggregates (shock means, state counts)
> to be deterministic across periods. §2.4 derives the quota-exact figure.

### 2.1 Micro states (baseline, no recession)

4 micro states per macro state:
- State 0: Employed
- State 1: Unemployed, with benefits, just-entered (one period in this state)
- State 2: Unemployed, with benefits, continuing (UBspell-1 periods)
- State 3: Unemployed, no benefits (exhausted UB)

Relevant parameters (from `Parameters.py` under Baseline, HS):
- `Urate_normal = 0.044 = 11/250` (ergodic unemployment target)
- `Uspell_normal = 1.5` quarters (expected unemployment spell → `U_persist = 1 - 1/Uspell = 1/3`, so `U_exit = 1 - U_persist = 2/3` per quarter)
- `UBspell_normal = 2` (how long benefits last before state 3)
- `Rspell = 6` (**recession** duration — *macro* Markov; not used in the unemployment transitions below)
- `LivPrb = 1 - 1/160 = 0.99375`
- `PermShkCount = TranShkCount = 7` (joint income shock discretization has 49 atoms, each with probability 1/49)

The transition matrix `CondMrkvArrays[macro_state]` is 4×4. At normal times it is:

| From | To | Probability |
|------|-----|------------|
| 0 (emp) → 0 | 1 − 22/717 = 695/717 ≈ 0.9693 |
| 0 (emp) → 1 | 22/717 ≈ 0.0307 |
| 1 (UB) → 0 | 1/Uspell_normal = 2/3 |
| 1 (UB) → 2 | 1 − 1/Uspell_normal = 1/3 |
| 2 (UB) → 0 | 2/3 |
| 2 (UB) → 3 | 1/3 |
| 3 (noUB) → 0 | 2/3 |
| 3 (noUB) → 3 | 1/3 |

The emp→UB1 probability is calibrated so the ergodic employed fraction equals `1 − Urate_normal = 239/250`: setting `π_emp = (1−1/Uspell) / (1/Uspell + p)` = 239/250 with `1/Uspell = 2/3` gives `p = 22/717`.

### 2.2 Ergodic state distribution (rational form)

Solving πP = π with Σπ = 1:

| State | Ergodic fraction | Decimal |
|-------|------------------|--------:|
| 0 (emp) | 239/250 | 0.95600 |
| 1 (UB1) | 11/375 | 0.02933 |
| 2 (UB2) | 11/1125 | 0.00978 |
| 3 (noUB) | 11/2250 | 0.00489 |

The scarcest denominator is **2250** (state 3): for every ergodic state count to be an integer, N must be a multiple of 2250.

### 2.3 The J_min coverage constraint

The shuffle falls back to stochastic draws when a source state has fewer than J_min agents. With `1/Uspell = 2/3`, J_min = 3 per source state (lcm of denominators of {2/3, 1/3}).  The scarcest state is state 3 (ergodic fraction 11/2250 ≈ 0.489%). To have J_min = 3 agents in state 3 every period, we need roughly:

    N_type >= 3 / (11/2250) ≈ 615 agents per type

(The familiar "1,200" figure is the more conservative J_min = Rspell = 6 per state, which overspecifies because it confuses Rspell with Uspell.)

With 3 education groups × 1 β type (Reduced_Run) and education shares (dropout 9.3%, HS 52.7%, college 38.0%), the binding constraint is the **dropout type**:

    N_dropout = N_total × 0.093

For N_dropout ≥ 1,200 (keeping the conservative J_min = 6 for safety): N_total ≥ **12,900**.

With the full 21-type economy (3 educ × 7 β), each β bin within dropout has ~1/7 of the dropout share. For N_per_beta_bin ≥ 1,200: N_total ≥ **90,300**.

These "J_min coverage" figures answer the question *"at what N does the shuffle not fall back to stochastic draws anywhere?"* They do NOT answer *"at what N do shock-means and state counts equal their ergodic values exactly, with no period-to-period variation?"* — that's quota-exact N, derived in §2.4.

### 2.3.1 When per-group estimation is used, the π factor drops out

The N_total figures above (12,900 for Reduced_Run, 90,300 for Baseline) assume a
**single unified simulation** containing all three education groups sharing one
agent pool. The π_min divisor (dropouts = 9.3% of total population; dropouts × one
β bin = 1.3% of total) is what makes those numbers large.

If the estimation pipeline is run **per education group** — e.g., via
`HAFISCAL_EDTYPES=<N>` which runs Nelder-Mead on one group at a time — then the
binding constraint is the **within-group** constraint. Each group's pool itself
must have enough agents in the rarest Markov state × β bin. The π factor drops
out because the group's share within its own pool is 1.0.

    N_per_group >= J_min × n_β / s_min

| Configuration        | n_β | N per group (J_min coverage, conservative) |
|----------------------|----:|-------------------------------------------:|
| Single-β cohort      |   1 |                                      1,200 |
| Full β distribution  |   7 |                                      8,400 |

These per-group figures are still **J_min coverage**, not quota-exact.

**What this means for the existing code.** `HAFISCAL_EDTYPES=<N>` already runs
Nelder-Mead on one education group at a time, but `AgentCountTotal` is still
split across all three groups by their population shares. To harvest the
per-group reduction, `AgentCountTotal` needs to be overridden so the entire
pool belongs to the group being estimated. A family of per-group parametrizations
analogous to the existing `HS_Only` (add `DO_Only`, `COL_Only`) would express
this cleanly: the education shares become `[1, 0, 0]` / `[0, 1, 0]` / `[0, 0, 1]`
in turn, and each run's `AgentCountTotal` targets the per-group minimum directly.

### 2.4 Quota-exact N: the stronger condition

"Quota-exact N" is the smallest N such that **every atomic probability × N is an integer**. At quota-exact N, simulated aggregates over a homogeneous cohort are deterministic across periods up to exactly the sources of randomness we choose not to eliminate (typically death-and-replacement). Requirements:

1. **Markov-state exactness.** N × π_j is integer for each of the four ergodic state fractions (§2.2). Worst denominator: **2250**.
2. **Shock-joint exactness.** With HARK's current `IncShkDstnNow.draw(N_emp, shuffle=True)`, the joint 7×7 income-shock distribution has 49 atoms each with probability 1/49. For every atom to get N_emp/49 agents, N_emp must be divisible by 49. Combined with N × 239/250 = N_emp integer and gcd(239, 49) = gcd(239, 250) = 1, this requires N divisible by 250 × 49 = **12,250**.
3. **Death exactness.** With `LivPrb = 1 − 1/160`, deterministic death count per period requires N divisible by **160**.

For HS single-β, combining these constraints:

| Regime | Requirement | Quota-exact N |
|--------|-------------|--------------:|
| Joint (49-atom) shuffle, **deterministic death** | LCM(2250, 49, 160) | **1,764,000** |
| Joint (49-atom) shuffle, **stochastic death** (claim (c)) | LCM(2250, 49) | **110,250** |
| Marginal-independent (7-atom) shuffle, deterministic death | LCM(2250, 7, 160) | **252,000** |
| Marginal-indep (7-atom) shuffle, **stochastic death** (claim (c)) | LCM(2250, 7) | **15,750** |

Dropping the LivPrb=1/160 constraint scales the figure down by a factor of **16** (not 160, because 2250 already contains one factor of 2 and 160 = 2⁵ × 5). Under the user's intended setup — "only stochasticity from death-and-replacement" — the relevant figures are rows 2 and 4.

**Why 7 vs 49.** HARK's `IncShkDstnNow.draw(N, shuffle=True)` shuffles over the joint 49-atom distribution. Because HARK's mean-one lognormal construction draws PermShk and TranShk independently (no joint correlation), a marginal-independent shuffle (sampling each marginal with `shuffle=True` separately, then pairing) would give the same economics with only the 7-atom divisibility requirement. That change would reduce the quota-exact N by 49/7 = 7×.

**Under the current shuffle machinery (joint), with stochastic death, HS single-β needs N ≈ 110,250 for quota-exact aggregates. Under a hypothetical marginal-independent shuffle, it would need only ≈ 15,750.** Both are far larger than the doc's historical "1,200 / 8,400" figures, which were J_min coverage only.

For a cohort with n_β = 7 bins (full β distribution), each bin independently needs a quota-exact N, so the per-cohort total is **7× the above** (rows 2/4 → 771,750 / 110,250). Per-group estimation (§2.3.1) still removes the π_educ divisor but the per-bin factor of 7 remains.

## 3. Practical approach: what N is "good enough"?

We don't need exact frequencies for every state. The shuffle still helps when:
- The **employed** group (95.6% of agents) has deterministic transitions — this is the largest group and benefits most
- The **unemployed** groups use stochastic fallback — acceptable because their income is deterministic (no perm/tran shocks), so the only noise source is *which specific agents* transition

The practical question: at what N does the shuffle provide meaningful noise reduction for the **policy experiments**?

### 3.1 Proposal: compute J_min per type per state empirically

Write a function that, given the economy's transition matrices and agent counts:
1. For each type i and micro state j, computes the expected N_j in the ergodic
2. Checks whether N_j >= J_min(j) = `ceil(1 / min(p_jk for p_jk > 0))`
3. Reports which (type, state) pairs fall below threshold
4. Computes the minimum N_total that makes all pairs viable

### 3.2 Proposal: adaptive shuffle

Modify `get_micro_markv_states_guts` to use the shuffle for any source state with N_j >= J_min(j), and stochastic fallback only when N_j < J_min(j). This is essentially what the current code does with the `N_j >= J` threshold, but J should be J_min(j), not the number of states.

Current threshold: `N_j >= J` where J = 4 (number of micro states).
Better threshold: `N_j >= ceil(1 / min(p_jk for p_jk > 0))`. For the unemployment rows this is `ceil(Uspell_normal) = 2` (with `1/Uspell = 2/3`, J_min = 3 after lcm); for the emp row the scarcest `p_jk` is 22/717 ≈ 0.031, giving J_min ≈ 33. So the effective threshold varies by state.

### 3.3 Proposal: replicate-based agent count tiers

For each tier in the validation plan, set N_total as a multiple of the minimum viable count:

| Tier | Target | N_total formula | Reduced_Run (3 types) | Full (21 types) |
|------|--------|-----------------|----------------------:|----------------:|
| Smoke | Just run | 100 | 100 | 100 |
| Small | Employed shuffle works | N_dropout ≥ ~J_min / π_state3 | ~1,000 | ~7,000 |
| Medium | All states shuffled for HS+college | HS state 3 ≥ J_min | ~4,000 | ~28,000 |
| Large | All states shuffled for all types | Dropout state 3 ≥ J_min | ~13,000 | ~90,000 |

These tiers target **J_min coverage** (no stochastic fallback). Quota-exact
aggregates (§2.4) require significantly more agents — 110,250 to 1,764,000 for
HS single-β depending on regime.

The `N_total` column is for **unified-population** runs. In the common case where
`HAFISCAL_EDTYPES=<N>` is used to optimize one education group at a time, the
applicable minimum is the per-group figure from §2.3.1 (1,200 for single-β,
8,400 for seven β bins), not the `N_total` here. See §2.3.1 for the reduction.

## 4. Implementation steps

1. **Write `compute_min_agents_for_shuffle(economy)`** — reports per-type, per-state viability
2. **Fix the threshold in `get_micro_markv_states_guts`** — use `ceil(1/min(p))` instead of `J`
3. **Add a report section** to parity validation showing which states use shuffle vs stochastic
4. **Update tier definitions** in the test plan with replicate-aware N_total values
5. **Test**: run UI policy at increasing N to find the N where the multiplier error drops below 5%

## 5. Key insight

The shuffle's benefit is proportional to the fraction of agents it covers. At N=1000 with Reduced_Run:
- Employed (state 0): ~956 agents → shuffle works, covers 95.6% of agents
- Unemployed states: ~44 agents total → mostly stochastic fallback

This means the shuffle IS helping for the dominant channel (employed agents' income shocks and employment transitions), but NOT for the minority channel (unemployment duration transitions). The UI policy's effect operates entirely through the minority channel, which is why it sees no improvement.

For the Check and TaxCut policies, which affect all agents (employed and unemployed), the shuffle provides meaningful noise reduction even at N=1000 — and indeed we see 2-3% errors there vs 47% for UI.
