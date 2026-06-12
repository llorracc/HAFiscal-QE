# splurge-in-budget TM implementation: a-indexed vs. joint (m, ξ) — careful comparison

**Date:** 2026-04-15
**Purpose:** Careful per-criterion comparison of the two exact approaches to implementing splurge-in-budget in the TM, on speed, code complexity, and expository challenge.
**Related docs:** `plans/20260418-1136h_splurge-in-budget-a-indexed-TM.md` (design rationale §0.3 currently gives a shorter version of this comparison); `plans/20260418-1136h_splurge-in-budget-implementation-sequence.md` (phased implementation).

## Setup — the two approaches precisely

### a-indexed TM

State: $(a, j)$. Transition kernel:

$$T(a \to a' \mid j \to j') = \text{MrkvArray}[j, j'] \cdot \sum_{\xi} P(\xi \mid j') \cdot \mathbf{1}\{a' = g_{j'}(a, \xi)\}$$

with

$$g_{j'}(a, \xi) = (R/\Gamma_{j'})\,a + (1-\varsigma)\bigl[\xi - c^*_{j'}\bigl((R/\Gamma_{j'})\,a + \xi\bigr)\bigr].$$

One sparse matrix per type; $\xi$ is integrated inside the inner construction loop.

### Joint $(m, \xi)$-indexed TM

State: $(m, \xi, j)$. Transition kernel:

$$T((m, \xi, j) \to (m', \xi', j')) = \text{MrkvArray}[j, j'] \cdot P(\xi' \mid j') \cdot \mathbf{1}\{m' = (R/\Gamma_{j'})\,a(m, \xi) + \xi'\}$$

with $a(m, \xi) = m - (1-\varsigma) c^*(m) - \varsigma\,\xi$. The matrix is bigger because the state now includes $\xi$.

### A critical fact worth stating up front

The ergodic under $(m, \xi)$ **does not factor** as $\pi_m(m, j) \cdot P(\xi \mid j)$, because within a cross-section $m$ and $\xi$ are correlated (since $m = (R/\Gamma)\,a_{t-1} + \xi$). So we really do have to carry the full 2D joint. The only way to get a factored representation of the same dynamics is to change the state to $(a, j)$ — which is exactly the a-indexed approach.

---

## 1. Speed — concrete HAFiscal numbers

Baseline parametrization: 21 types, $J \approx 88$ for baseline and up to $\approx 168$ for recession experiments, $N_m = N_a = 100$, $N_\xi = 7$.

### State counts per type (baseline, $J = 88$)

| approach | cells per type |
|---|---:|
| a-indexed | $N_a \cdot J = 100 \cdot 88 = 8{,}800$ |
| $(m, \xi)$ | $N_m \cdot N_\xi \cdot J = 100 \cdot 7 \cdot 88 = 61{,}600$ |

### Sparse nonzeros per type

Each row has approximately $2 \cdot J \cdot N_\xi$ destinations (lottery split × Markov × transitory atoms):

| approach | nnz per type |
|---|---:|
| a-indexed | $\sim 10.8\text{M}$ |
| $(m, \xi)$ | $\sim 76\text{M}$ |

$(m, \xi)$ has **~7× more** nonzeros.

### Memory (CSR, ~12 B/nnz)

- a-indexed: $\sim 130$ MB per type
- $(m, \xi)$: $\sim 912$ MB per type

Both fit easily on a workstation.

### Wall clock (Baseline, end-to-end TM solve)

Dominated by matvec during ergodic power iterations; AD iteration rebuilds the kernel each pass.

| approach | Baseline wall clock |
|---|---:|
| a-indexed | $\approx 1.5$ h |
| $(m, \xi)$ | $\approx 10$ h |
| MC (reference) | $\approx 5$ h |

**This is the decisive comparison.** The whole motivation for having a TM is speed and determinism versus MC. If we pick $(m, \xi)$, the TM becomes **slower than MC** for HAFiscal Baseline, which largely defeats the purpose of having a TM.

Across 8 sensitivity parametrizations (CRRA1, CRRA3, various Rfree, ADElas, etc.), the compounding effect is ~12h (a-indexed) vs. ~80h ($(m, \xi)$) for the sensitivity sweep — roughly 68 hours of wall-clock difference.

---

## 2. Code complexity

Roughly the reverse ordering from speed.

### a-indexed — moderate-to-large refactor

- `dist_mGrid` → `dist_aGrid` throughout `tm_methods.py`.
- cFunc is still evaluated at $m$, but $m$ is computed **inside** the kernel-construction inner loop from $(a, \xi)$, so most code paths pull logic into the loop body.
- **Aggregation rewrites are the biggest pain.** Current-period $C$ and $Y$ require integrating over $(j', \xi')$ next-period atoms, because the ergodic is over $(a, j)$ and current $c$ depends on the arrival $m' = (R/\Gamma)\,a + \xi'$. This inflates the aggregator from a simple sum over $(m, j)$ to a 4-nested loop $(a, j, j', \xi')$.
- Newborn distribution concentrates cleanly at $a = 0$.
- **Test migration:** many existing tests assume m-indexing explicitly (e.g., they check properties of `dist_mGrid`); those need rewriting.

### $(m, \xi)$-indexed — smaller refactor, accepts state-space bloat

- Add $\xi$ as a second state coordinate; `dist_mGrid` becomes `dist_mxi_Grid` or a pair of aligned arrays.
- cFunc evaluation unchanged — $c^*(m, j)$ with $m$ directly from state.
- **Aggregation is trivial:** $C = \sum_{m, \xi, j} \pi(m, \xi, j) \cdot c_\text{actual}(m, j, \xi)$, direct sum over the ergodic. No next-period integration needed.
- Check/TaxCut shift still enters $m$, inside the existing pattern.
- Newborn injection: mass at $(m_0(\xi), \xi)$ for each $\xi$ atom; slightly more bookkeeping than a-indexed's single point but still mechanical.
- **Test migration:** existing tests mostly continue to work if we marginalize $\xi$ out at the aggregation layer. Much less rewriting.

### Precedent in the codebase

There's already some 2D TM machinery in the codebase (the Check bucket × Markov state structure, for example), which makes $(m, \xi)$ less of a conceptual jump. a-indexed is a novel structure relative to what's there now.

### Rough effort estimate

- a-indexed refactor: ~2-3 days of focused coding
- $(m, \xi)$ refactor: ~1-2 days

---

## 3. Expository challenge

This is where $(m, \xi)$ has its clearest edge, though the magnitude depends on audience.

### For coauthors

$(m, \xi)$ is a direct extension of the existing framework: *"splurge-in-budget makes $m$ not sufficient, so we add $\xi$ as a second state coordinate."* That's a one-sentence setup. a-indexed requires explaining why we change the state variable altogether, which is a deeper conceptual move even though it's the cleaner mathematical formulation once you see it.

### For the paper / appendix

Most papers don't go into TM state-indexing details — the method section cites HARK and describes dynamics, not grid choices. Either approach is a line or two of prose. The expository cost of a-indexed only bites in internal discussion and in code review.

### For future maintainers of the codebase

$(m, \xi)$ preserves more of the existing mental model. a-indexed forces whoever reads the code after us to do the state-variable translation in their head.

**Verdict on exposition:** $(m, \xi)$ wins a modest-to-substantial edge, depending on how much weight is placed on future-maintainer legibility.

---

## 4. Scorecard

| Criterion | Winner | Margin |
|---|---|---|
| **Speed** | a-indexed | decisive (~7×; crosses the MC line) |
| **Code complexity** | $(m, \xi)$ | modest (maybe 1-1.5 days saved) |
| **Expository challenge** | $(m, \xi)$ | modest for coauthors + maintainers; negligible for the paper |

---

## 5. Decision (2026-04-15)

**Chosen approach: a-indexed TM. No $(m, \xi)$ stepping stone.**

The speed advantage of a-indexed is large enough to override the code and expository advantages of $(m, \xi)$ — for HAFiscal specifically, where the TM exists precisely to be fast. A 10h TM run defeats the purpose of having a TM when MC takes 5h. Across the sensitivity sweep the difference compounds to roughly 68h saved.

### Why no hybrid $(m, \xi) \to$ a-indexed path

Earlier drafts of this comparison suggested implementing $(m, \xi)$ first as a validation stepping-stone, then migrating to a-indexed. **Rejected.** If the endpoint is a-indexed anyway, the $(m, \xi)$ intermediate is wasted effort — work that is discarded rather than built upon. The stepping-stone framing would only be justified if the $(m, \xi)$ code could be kept in production for some purpose, which it cannot (it's strictly slower than a-indexed and solves the same problem).

### Ground truth for correctness during development

**MC is the ground truth.** The MC path under splurge-in-budget is already correct (`AggFiscalType.get_poststates` uses realized `self.shocks['TranShk']` per agent), so it serves as the unbiased reference against which the a-indexed TM is developed and verified.

**During development, comparisons must be narrow and fast.** Running full MC at 5h per check would be prohibitive. Instead, use targeted asymptotic-style tests drawn from the asymptotic-equality test-plan series in `plans/20260403-1253h_asymptotic-equality-test-plan.md` and `Code/HA-Models/Gatekeeper_Asymptotic_Equality.ipynb`:

- start from the smallest scenario where the math can discriminate (typically 1-type, short-horizon, small grid);
- verify TM_a ergodic moments match MC moments to expected precision at increasing scales;
- at each scale, run in minutes, not hours.

The asymptotic-plan harness was built for exactly this purpose (originally for the 0.14.1-to-0.17.0 TM-vs-MC validation); reusing its structure keeps Phase 3 development iteration fast enough to be practical.

### Bookkeeping follow-up

The a-indexed TM refactor itself is now Phase 3 of the implementation sequence; it should be filed as its own BUG-NNN when that phase begins, per the process requirement in `plans/20260418-1136h_splurge-in-budget-implementation-sequence.md`. Currently it is tracked only by these plan documents.
