# Shuffle method: second epitaph — limitations by calibration and question type

**Date:** 2026-04-19
**Companion to:** [`20260419_shuffle-vs-mc-comparison.md`](20260419_shuffle-vs-mc-comparison.md) (the first epitaph — measured shuffle vs regular MC at the NM-estimation level and found shuffle marginally slower and not converging under tight tolerance)

The first epitaph said shuffle is *empirically* not faster for HAFiscal's NM estimation. This one makes the deeper point: even if the implementation were perfect, shuffle is *structurally* the wrong tool for HAFiscal, both because of how the model is calibrated and because of what HAFiscal is trying to measure.

## 1. The calibration doesn't play well with shuffle

The shuffle method gives exactly-integer subcounts only when the agent count N is a multiple of every atomic probability's denominator (in lowest terms) — call this quota-exact N. HAFiscal's calibration produces denominators that are large, coprime, and multiplicatively painful.

### 1.1 `Urate_normal = 0.044 = 11/250`

In lowest terms: 11/250. The ergodic employed fraction is therefore `1 − 11/250 = 239/250`. **239 is prime** and shares no factors with any of the other denominators in the system. That alone forces quota-exact N to be a multiple of 250, and forces employed subcounts to multiply through a factor of 239 before any other divisibility kicks in.

### 1.2 `LivPrb = 0.99375 = 1 − 1/160`

If we want death-and-replacement to contribute zero aggregate stochasticity — i.e. exactly N/160 deaths per period — N must be a multiple of 160 = 2⁵ × 5. Because 160 shares only one factor of 2 with the existing Markov denominators, adding death-exactness scales quota-exact N by **16×** (not 160×, but still substantial).

### 1.3 Joint shock atoms: 49

HARK's `IncShkDstnNow.draw(N, shuffle=True)` shuffles over the full 7×7 = 49-atom joint income-shock distribution. For exact marginal shock means among employed agents, `N_emp` must be a multiple of 49. Combined with the 239/250 employed-fraction constraint, this forces N to be a multiple of **250 × 49 = 12,250**.

### 1.4 Combined quota-exact N (HS single-β)

Worst Markov-state denominator: **2250** (from π_noUB = 11/2250). Rolling in the shock and death constraints:

| Regime | Requirement | Quota-exact N |
|---|---|---:|
| Joint shuffle + deterministic death | LCM(2250, 49, 160) | **1,764,000** |
| Joint shuffle + stochastic death | LCM(2250, 49) | **110,250** |
| Marginal shuffle (7) + deterministic death | LCM(2250, 7, 160) | **252,000** |
| Marginal shuffle (7) + stochastic death | LCM(2250, 7) | **15,750** |

For the 7-bin β distribution these multiply by 7 (per bin must separately be quota-exact). For unified (3-group) estimation they multiply further by `1/s_min` (dropout share ≈ 1/10).

**The pragmatic N values we actually run — ≈ 5,200 HS agents Baseline cohort-weighted, or 1,200–8,400 per group in the per-group regime — are 1–3 orders of magnitude below quota-exact** under even the friendliest regime. At those sizes the shuffle eliminates the stochastic fallback in Markov state coverage (that's what "J_min coverage" means in [`minimum-replicates-for-shuffle.md`](../minimum-replicates-for-shuffle.md)) but it does NOT produce deterministic state counts. The aggregates still fluctuate period-to-period at ≈ √N rate.

If we wanted the genuine article — deterministic aggregates up to death-and-replacement — we'd need to run at least 110,250 agents per single-β cohort, or 15,750 if HARK's shuffle were reworked marginal-independent. Both are ~20–200× our current working sizes.

## 2. Shuffle doesn't help with rare events — and HAFiscal is about rare events

Even in an alternate universe where quota-exact N were cheap and we ran everything at 1.7M agents, shuffle still wouldn't help HAFiscal answer its core questions. Shuffle stabilizes **aggregate first moments over the ergodic distribution**. HAFiscal asks what happens in the tail.

### 2.1 Example: the UI-extension question

The marginal effect of a UI extension is paid to agents in the **no-UB** state — state 3, those who have exhausted regular unemployment benefits. Ergodic frequency: 11/2250 ≈ **0.489%**.

Agents with *longer* no-UB histories are relevant too — the consumption path of someone whose benefits ran out several quarters ago is economically different from someone who just lost them. The probability of being in an unemployment state continuously for k consecutive periods is approximately `Urate × (1 − 1/Uspell)^(k−1) = 0.044 × (1/3)^(k−1)`:

| History | Probability | Expected N at 5,200 HS agents |
|---|---:|---:|
| Unemployed, current period | 0.044 | ~229 |
| Continuously unemployed for 2 periods | 0.044 × 1/3 ≈ 0.0147 | ~76 |
| 3 periods | 0.044 × 1/9 ≈ 0.00489 | ~25 |
| 4 periods | 0.044 × 1/27 ≈ 0.00163 | ~8 |
| 5 periods | 0.044 × 1/81 ≈ 0.00054 | ~3 |
| 6 periods | 0.044 × 1/243 ≈ 0.00018 | ~1 |

### 2.2 What shuffle does and doesn't do for these events

**What shuffle does:** at quota-exact N, the ergodic *count* of agents in each current state is a deterministic constant across periods.

**What shuffle does not do:**

1. **It doesn't change *who* transitions.** At the boundary between "shuffle" (deterministic count) and "whose outcome changes" (stochastic identity), shuffle still assigns individual agents to transitions. The identity is what determines the subsequent consumption / wealth path. Two agents who just exhausted benefits in the same period still have different wealth because their prior earnings and consumption histories are different, and shuffle doesn't touch those.

2. **It doesn't help with multi-period-history rare states.** P(continuously unemployed for 6 periods) = 0.00018 isn't a "current state" — it's a product of independent single-period stochastic transitions. The count of agents with that specific history in period t depends on the full stochastic dynamics. Shuffle cannot make this deterministic without also prescribing the full panel history, which would defeat the purpose of a stochastic simulation.

3. **It doesn't reduce the standard error of rare-state statistics.** The precision of a welfare statistic restricted to agents in a rare state scales as 1/√N_rare. Shuffle holds N_rare constant across periods; it doesn't change its equilibrium magnitude, and it doesn't enlarge the rare subsample.

4. **It doesn't affect cross-sectional wealth dispersion *within* a rare state.** Two agents in state 3 at period t arrived there via two different histories of income shocks, consumption choices, wealth accumulation. Shuffle doesn't alter that heterogeneity.

### 2.3 What you actually need for precision on rare-event welfare

If the object of inference is `E[welfare change | agent in state 3]` or `E[welfare change | agent has been in state 3 for 3+ periods]`, the sampling SE scales as `σ_within / √N_rare`. To halve the SE you need 4× more agents in the rare state.

There are essentially three ways to get that precision:

- **Brute scale.** Run 10× or 100× more agents. Expensive; also hits quota-exact N limits above.
- **Importance sampling.** Oversample histories that pass through the rare states, reweight in the welfare integral. Not implemented in the shuffle framework.
- **Analytical integration.** Use the transition-matrix (TM) method to compute the welfare integral over the ergodic density directly. HAFiscal is already developing this path; it's strictly orthogonal to shuffle.

None of these is shuffle. Shuffle addresses a different problem — first-moment precision on common states — and addresses it well for quantities the research doesn't particularly care about (mean income of the employed is close to 1.000 under any reasonable N).

## 3. Summary verdict

Two independent reasons shuffle is not the right variance-reduction lever for HAFiscal:

1. **Calibration-structural.** Urate = 11/250 brings in a factor of 239, LivPrb = 1/160 brings in 16, joint shocks bring in 49. Quota-exact N for HS single-β is 110,250 at best and 1,764,000 at worst — far beyond production scales.
2. **Question-structural.** HAFiscal measures welfare effects of policies that operate through rare states and multi-period histories. Shuffle stabilizes aggregate counts of current states at the ergodic distribution; that has no impact on the precision of tail-restricted welfare statistics, which is what drives HAFiscal's scientific conclusions.

**Recommendation:**

- Keep the `HAFISCAL_MC_SHUFFLE=1` / `HAFISCAL_INCOME_SHUFFLE=1` opt-in env vars for users who specifically want the small first-moment precision benefit and understand the limits.
- Do not wire `markov_shuffle` into burn-in, do not push toward quota-exact N, do not make shuffle the default for step-2 NM estimation.
- Variance-reduction effort on this branch should focus on TM methods (already underway) and, if needed later, importance-sampling schemes targeted specifically at rare-state welfare integrals. Neither uses the shuffle framework.

Shuffle is a legitimate tool for models calibrated to friendly rational denominators whose scientific questions are about means of common states. HAFiscal is neither.
