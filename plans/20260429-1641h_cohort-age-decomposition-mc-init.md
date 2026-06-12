# Implementation plan: cohort-age decomposition for MC initialization

**Author:** Claude Opus (max effort)
**Date:** 2026-04-29
**Status:** awaiting user approval before execution
**Source-of-truth math doc:** `history/20260331-mathematical-derivations-harmenberg.md` §24
**Predecessor work:** `tm_methods.compute_doob_pi_q_a` (commit `3325ada9`), `init_mc_from_doob_a` (commit `f87151c0`)
**Empirical baseline to beat:** `harmenberg_doob_drift_test.py` — current 1-moment lognormal init produces $\mathbb{E}_Q[a]$ drift up to ~5% (HS β=0.91) and ~20% (CO β=0.988) over 200 periods.

---

## 0. Self-contained problem statement

The HAFiscal Monte Carlo simulator runs under the **physical (P-)measure**: each agent is one physical person whose state $(p_t, a_t, j_t)$ evolves under P-dynamics. Its joint stationary distribution is $\mu_P(p, a, j)$.

For an MC simulation of length $T$ to have **stationary sample moments at every time** $t \in \{0, 1, \ldots, T\}$, the initial state of the $N$ agents must be drawn from $\mu_P$ exactly. Otherwise the chain "relaxes" toward $\mu_P$ during forward simulation, producing observable drift in time-$t$ moments. The relaxation timescale is $\sim 1/(1 - L \cdot G \cdot \mathbb{E}[\psi])$ at moderate $\beta$ and grows large as $\beta \to \beta_{\text{GIC}}$.

The TM-a kernel gives us $\pi_P(a, j)$ exactly. The **conditional** $\mu_P(p \mid a, j)$ is what we need to specify. Doob's machinery (Fix 4, §21.6) gives $w(x) = v_1(x) = \mathbb{E}_P[p \mid x]$; the moment ladder $v_k(x) = \mathbb{E}_P[p^k \mid x]$ extends to higher conditional moments. But these are **age-integrated** — averaged over all survivor ages of agents currently at $x$.

The model structure tells us $\mu_P(p \mid x)$ is in fact a **mixture over cohort ages**: each survivor has been alive some random number of periods $K$, and within each $K = k$ slice, $p$ has a known closed-form distribution. Collapsing the mixture into a single lognormal sacrifices information that the model gives us essentially for free. **This plan implements the cohort-age-decomposed init that uses the model's mixture structure explicitly.**

---

## 1. Theoretical foundations (self-contained from math doc §24)

### 1.1 The cohort-age random variable

For agent $i$ at time $t$, define $K_t^{(i)} \in \{0, 1, 2, \ldots\}$ as the number of full periods elapsed since that agent's most recent birth. $K = 0$ means newborn this period; $K = k$ means survived $k$ periods since birth.

### 1.2 TM-P decomposition into birth and survival kernels

The transition matrix built by `_build_period_tm_a` decomposes as:

$$T_P[x \to x'] = \underbrace{(1 - L_j) \cdot \pi_N(x')}_{\text{birth contribution}} + \underbrace{T_S[x \to x']}_{\text{survival kernel}}$$

where:
- $T_S[x \to x'] = L_j \cdot \sum_{j', s} \text{Mrkv}[j, j'] \cdot \text{shk}_s \cdot \text{lottery}_{x \to x'}(j', s)$ is the survival-only kernel (carrying the $L_j$ factor — column-sum is $L_j$, sub-stochastic).
- $\pi_N(x') = \mathbb{1}\{a' = 0\} \cdot \pi_{\text{Markov-ergodic}}(j')$ is the newborn distribution per `_make_newborn_dist_a`.

### 1.3 Cohort-conditional state distribution

Define $\pi^{(k)}(x) := P(X_t = x \mid K_t = k)$. The forward propagation recursion is:

$$\pi^{(k+1)}(x') = \frac{1}{L^{(k)}} \sum_x T_S[x \to x'] \cdot \pi^{(k)}(x), \qquad L^{(k)} := \sum_x L_{j(x)} \cdot \pi^{(k)}(x)$$

with initial condition $\pi^{(0)}(x) = \pi_N(x)$. The normalization $L^{(k)}$ is the cohort-$k$ aggregate survival probability; in the constant-$L$ case $L^{(k)} \equiv L$ and the recursion is $\pi^{(k+1)} = T_S \cdot \pi^{(k)} / L$.

### 1.4 Cohort-conditional moment recursions

Define cohort-conditional $p$-moments $M_k^{(\ell)}(x) := \mathbb{E}_P[p_t^k \mid X_t = x, K_t = \ell]$, and the corresponding occupation function $g_k^{(\ell)}(x) := M_k^{(\ell)}(x) \cdot \pi^{(\ell)}(x)$. Forward recursion:

$$g_k^{(\ell+1)}(x') = \frac{1}{L^{(\ell)}} \sum_x T_{S, p^k}[x \to x'] \cdot g_k^{(\ell)}(x)$$

with initial condition $g_k^{(0)}(x) = \mathbb{E}[p_{\text{init}}^k] \cdot \pi_N(x)$.

The **k-th moment p-weighted survival kernel** (defined in math doc §23.7 / §21.6):

$$T_{S, p^k}[x \to x'] = L_j \sum_{j', s} \text{Mrkv}[j, j'] \cdot \text{shk}_s \cdot G_{j'}^k \, \psi_s^k \cdot \text{lottery}_{x \to x'}(j', s)$$

— same loop as $T_S$ but with each shock realization weighted by $G_{j'}^k \, \psi_s^k$.

For the lognormal newborn $p_{\text{init}} \sim \text{Lognormal}(\mu_{\text{init}}, \sigma_{\text{init}})$ with `pLvlInitMean = μ_init`, `pLvlInitStd = σ_init` from `agent`:

$$\mathbb{E}[p_{\text{init}}^k] = \exp\!\left(k \, \mu_{\text{init}} + \tfrac{1}{2} k^2 \, \sigma_{\text{init}}^2\right)$$

Recovering moments: $M_k^{(\ell)}(x) = g_k^{(\ell)}(x) / \pi^{(\ell)}(x)$ where $\pi^{(\ell)}(x) > 0$.

### 1.5 Within-cohort lognormality (Proposition)

Conditional on cohort age $K = k$ and the j-path $(j_0, j_1, \ldots, j_k)$ that the agent traversed:

$$\log p_t \mid (K = k, j\text{-path}) \sim \mathcal{N}\!\left(\mu_{\text{init}} + \sum_{s=1}^k \log G_{j_s} + \sum_{s=1}^k \mathbb{E}[\log \psi \mid j_s], \quad \sigma_{\text{init}}^2 + \sum_{s=1}^k \text{Var}(\log \psi \mid j_s)\right)$$

**Proof:** $p_t = p_{\text{init}} \cdot \prod_{s=1}^k G_{j_s} \cdot \psi_s$ so $\log p_t = \log p_{\text{init}} + \sum \log G_{j_s} + \sum \log \psi_s$. The shocks are independent across periods. If the underlying continuous $\log \psi$ is normal, this sum is normal exactly. $\square$

**Caveat (discretization):** HAFiscal uses 7-point Hermite-Gaussian quadrature for $\psi$ in **employed** states. The discrete sum-of-7-atoms is not exactly Gaussian, but matches the first 13 moments. Our **moment recursions are exact at the 7-point discretization level**; the lognormal-fit at the per-cell density level for sampling is the only approximation.

**Important: degenerate shocks for unemployed states.** In HAFiscal as currently implemented, the **three unemployed states** (`j ∈ {1, 2, 3}`) have **degenerate income shock distributions**:

```python
IncShkDstn_unemp = DiscreteDistribution(
    np.array([1.0]),                          # single shock atom, prob 1
    [np.array([1.0]),                         # ψ ≡ 1 (no permanent shock)
     np.array([BaseType.IncUnemp])])          # ξ = IncUnemp (constant)
```

So unemployed agents draw **neither** a stochastic permanent shock $\psi$ **nor** a stochastic transitory shock $\xi$ — both are degenerate at fixed values. This has two consequences for the cohort-age formulas:

1. **For unemployed periods $j_s \in \{1, 2, 3\}$**: $\psi = 1$ implies $\log \psi = 0$ deterministically, so both $\mathbb{E}[\log \psi \mid j_s] = 0$ and $\text{Var}(\log \psi \mid j_s) = 0$. The sums in the within-cohort lognormality formula contribute nothing from those periods. **The formula is correct as written and naturally accommodates this case** — the proposition holds with a Dirac-point contribution at $\log \psi = 0$ at unemployed periods.

2. **For the moment recursion kernels $T_{S, p^k}$**: each unemployed-state shock loop iterates exactly once with $\psi^k = 1^k = 1$ (no contribution to the per-period log-p increment). The recursion handles this automatically; no special-case code is needed.

3. **For the transitory income $\xi$**: $\xi$ doesn't enter the $p$-evolution, only the $a$-evolution (via cash-on-hand $m$). So degenerate $\xi$ for unemployed has no impact on the cohort-conditional $p$-moments. It does affect the cohort-conditional $\pi^{(k)}(x)$ marginal (since unemployed agents have predictable $a$-evolution per period), but $\pi^{(k)}$ is computed via $T_S$ directly so this is also handled automatically.

**Optional counterfactual mode (CONFIG: `unemp_shocks='degenerate' | 'employed'`):** for testing/validation purposes, we may want to compare cohort-init behavior under (a) the production HAFiscal convention (degenerate unemployed shocks, default `'degenerate'`) versus (b) a counterfactual where unemployed agents draw the same $(\psi, \xi)$ shocks as employed agents (`'employed'`). The latter is purely diagnostic — it changes the model — but provides a sanity check that the cohort-age framework doesn't depend on the degenerate-shock structure for its correctness. **This will be added as an opt-in flag to `compute_cohort_age_decomposition_a`; default behavior matches production.** Implementation: when `unemp_shocks='employed'`, override `IncShkDstn_list[j]` for `j ∈ {1,2,3}` to copy `IncShkDstn_list[0]` before building the survival kernels. **Do not change production behavior.**

### 1.6 Geometric cohort weight distribution (constant-L case)

$$P(K_t = k) = (1 - L) \cdot L^k$$

**Derivation:** Per period, fraction $(1-L)$ dies and is replaced by newborns. So the population fraction at age $k$ is $(1-L) \cdot L^k$ (born $k$ periods ago, survived $k$ subsequent periods up to and including the current period — actually born in period $t-k$ and survived $k$ periods so far means we have age $k$ in period $t$, which has weight `birth-rate × survival^k`).

Sum check: $\sum_{k=0}^\infty (1-L) L^k = (1-L) / (1-L) = 1$. ✓

For state-dependent $L_j$, the cohort weights become path-dependent and require iterative computation:

$$P(K_t = k+1) = L^{(k)} \cdot P(K_t = k) \quad\text{with}\quad P(K_t = 0) = \bar{\delta}$$

where $\bar{\delta} = \sum_x \pi_P(x) (1 - L_{j(x)})$ is the aggregate death rate (= birth rate in stationarity).

### 1.7 Stationarity cross-checks (mandatory validity tests)

The cohort decomposition produces the same $\pi_P$ and $v_k$ via geometric aggregation:

$$\pi_P(x) = \sum_{k=0}^\infty (1 - L) L^k \cdot \pi^{(k)}(x)$$

$$v_k(x) \cdot \pi_P(x) = \sum_{\ell=0}^\infty (1 - L) L^\ell \cdot g_k^{(\ell)}(x) =: f_k(x)$$

The first must match `find_ergodic_distribution(T_P)` to within truncation error; the second must match Doob's `compute_doob_pi_q_a`-derived `f` (i.e., `w * pi_P`) for $k=1$ and the v_2 system for $k=2$. **These cross-checks are blocking** — implementation is rejected until both pass.

**Truncation:** Replace $\sum_{k=0}^\infty$ with $\sum_{k=0}^{K_{\max}}$. Tail mass is $L^{K_{\max}+1}$. For $L = 0.99$ tolerance $10^{-3}$: $K_{\max} \geq \log(10^{-3}) / \log(0.99) \approx 687$. For $10^{-5}$: $\approx 1146$. Default $K_{\max} = 2000$ for safety.

### 1.8 The MC initialization scheme

For each MC agent $i \in \{1, \ldots, N\}$:

**Step 1 — Cohort age:** $K_i \sim \text{Geometric}(1 - L)$, truncated at $K_{\max}$.

**Step 2 — Conditional state:** $X_i = (a_i, j_i) \sim \pi^{(K_i)}(\cdot)$ — sample from the cohort-conditional $(a, j)$-marginal.

**Step 3 — Conditional p:** $p_i \sim \text{Lognormal}(\mu_{X_i}^{(K_i)}, \sigma_{X_i}^{(K_i)})$ where the parameters are matched to the cohort-and-cell first two moments via:

$$\sigma_x^{(\ell)} = \sqrt{\log\!\left(1 + \frac{V_x^{(\ell)}}{(M_1^{(\ell)}(x))^2}\right)}, \qquad \mu_x^{(\ell)} = \log M_1^{(\ell)}(x) - \tfrac{1}{2} (\sigma_x^{(\ell)})^2$$

with $V_x^{(\ell)} = M_2^{(\ell)}(x) - (M_1^{(\ell)}(x))^2$ the cohort-and-cell variance.

---

## 2. Implementation tasks (in dependency order)

### Task 2.1 — Add `_build_p2_weighted_survival_kernel_a`

**Where:** `Code/HA-Models/FromPandemicCode/tm_methods.py`, immediately after `_build_p_weighted_survival_kernel_a` (line ~2940).

**Signature:** identical to `_build_p_weighted_survival_kernel_a` but with `G_jp**2 * psi_s**2` replacing `G_jp * psi_s` at the shock-weighting step. Returns a sub-stochastic `scipy.sparse.csc_matrix`.

**Implementation strategy:** copy `_build_p_weighted_survival_kernel_a` verbatim, change one line:
```python
# OLD: wt = markov_prob * LivPrb_j * shk_tile * G_jp * psi_tile
# NEW: wt = markov_prob * LivPrb_j * shk_tile * (G_jp**2) * (psi_tile**2)
```

**Validation:** unit test in `harmenberg_cohort_unit_test.py` checks that aggregating $T_{S, p^2}$ over destinations gives the expected per-source $L_j \cdot G_{j'}^2 \cdot \mathbb{E}[\psi^2]$ structure. (Specifically: sum of column should equal $L_j \cdot \sum_{j'} \text{Mrkv}[j, j'] \cdot G_{j'}^2 \cdot \mathbb{E}_{j'}[\psi^2]$.)

**Cost:** one matrix build, $O(\text{nnz}(T_S))$ ≈ tens of thousands of operations. Sub-millisecond.

**Refactor opportunity (deferred):** could parameterize `_build_p_weighted_survival_kernel_a` to accept a `k` argument (the moment power), with `k=1` and `k=2` both supported by the same code. Defer to Task 2.5 once the dedicated `_build_p2` version is verified.

### Task 2.2 — Add `_build_survival_only_kernel_a`

**Where:** `Code/HA-Models/FromPandemicCode/tm_methods.py`, near `_build_p_weighted_survival_kernel_a`.

**Purpose:** produces $T_S$ — the survival-only kernel used in $(eq:cohort\text{-fwd-prop})$. This is `_build_p_weighted_survival_kernel_a` with $G^k \psi^k$ replaced by $1$ (no extra weighting). Equivalently: it's the survival portion of `_build_period_tm_a` excluding the birth contribution.

**Implementation strategy:** copy `_build_p_weighted_survival_kernel_a`, remove the `G_jp` and `psi_tile` factors at the shock-weighting step:
```python
# OLD: wt = markov_prob * LivPrb_j * shk_tile * G_jp * psi_tile
# NEW: wt = markov_prob * LivPrb_j * shk_tile
```

**Validation:** unit test checks (a) column sums equal $L_j$ (sub-stochastic with deficit equal to mortality rate); (b) $T_S + (1 - L_j) \pi_N \mathbb{1}^\top$ reconstructs $T_P$ from `_build_period_tm_a` to machine precision (this is $(eq:TM\text{-P-decomp})$).

### Task 2.3 — Add `compute_cohort_age_decomposition_a`

**Where:** `Code/HA-Models/FromPandemicCode/tm_methods.py`, after `compute_doob_pi_q_a`.

**Signature:**
```python
def compute_cohort_age_decomposition_a(
    agent, tm_data,
    K_max=2000,
    k_moments=(1, 2),
    interpretation='CDC',
    verify_against_doob=True):
    """
    Compute cohort-age-conditional state distribution and p-moments
    via forward propagation from newborn injection.

    Returns dict:
      'pi_k':       (K_max+1, A*J) — π^{(ℓ)}(x) for ℓ=0..K_max
      'g1_k':       (K_max+1, A*J) — g_1^{(ℓ)}(x) (M_1 occupation function)
      'g2_k':       (K_max+1, A*J) — g_2^{(ℓ)}(x) (M_2 occupation function)
      'cohort_wt':  (K_max+1,) — geometric weights P(K=ℓ)
      'L_avg':      (K_max+1,) — per-cohort survival rate L^{(ℓ)}
      'pi_P_aggregated': (A*J,) — Σ_ℓ cohort_wt[ℓ] * pi_k[ℓ] (cross-check)
      'f1_aggregated':   (A*J,) — Σ_ℓ cohort_wt[ℓ] * g1_k[ℓ] (cross-check)
      'f2_aggregated':   (A*J,) — Σ_ℓ cohort_wt[ℓ] * g2_k[ℓ] (cross-check)
    """
```

**Algorithm (per math doc §24.4):**
```
1. Build T_S via _build_survival_only_kernel_a
2. Build T_S_p via _build_p_weighted_survival_kernel_a (k=1)
3. Build T_S_p2 via _build_p2_weighted_survival_kernel_a (k=2)
4. Read pLvlInitMean, pLvlInitStd from agent (per AggFiscalModel.py:482-489
   convention; checking both 0.14.1 and 0.17.0 attribute names)
5. Compute E_p_init_1 = exp(μ_init + 0.5*σ_init²)
   Compute E_p_init_2 = exp(2*μ_init + 2*σ_init²)
6. Build π_N via _make_newborn_dist_a(dist_aGrid, markov_ergodic)
7. Initialize: pi_k[0] = π_N
                g1_k[0] = E_p_init_1 * π_N
                g2_k[0] = E_p_init_2 * π_N
8. For ℓ = 0 to K_max-1:
     L_ℓ = sum_x LivPrb[j(x)] * pi_k[ℓ][x]
     pi_k[ℓ+1] = (T_S @ pi_k[ℓ]) / L_ℓ
     g1_k[ℓ+1] = (T_S_p @ g1_k[ℓ]) / L_ℓ
     g2_k[ℓ+1] = (T_S_p2 @ g2_k[ℓ]) / L_ℓ
     L_avg[ℓ] = L_ℓ
9. Compute geometric weights:
     cohort_wt[ℓ] = (1 - L_ℓ_avg) * L_ℓ_avg^ℓ  (for constant L)
     OR (state-dependent): iterative per §24.6 generalization
10. Aggregate:
     pi_P_aggregated = Σ_ℓ cohort_wt[ℓ] * pi_k[ℓ]
     f1_aggregated = Σ_ℓ cohort_wt[ℓ] * g1_k[ℓ]
     f2_aggregated = Σ_ℓ cohort_wt[ℓ] * g2_k[ℓ]
11. If verify_against_doob:
     pi_P_doob = find_ergodic_distribution(T_P)  # T_P from caller's tm_data
     doob_out = compute_doob_pi_q_a(agent, tm_data, pi_P_doob, ...)
     w_doob = doob_out['w']
     f1_doob = w_doob * pi_P_doob   # Doob's E[p · 1{X=x}]
     assert max|pi_P_aggregated - pi_P_doob| < tol  # tol = max(L^{K_max+1}, 1e-10)
     assert max|f1_aggregated - f1_doob| < tol
     # f2 has no direct Doob counterpart (would need new v2 solve);
     # for v2 cross-check: implement compute_doob_v2_a as a side helper
12. Return dict.
```

**Cost:** $3 \cdot (K_{\max} + 1)$ sparse matvecs, each $O(\text{nnz}(T_S))$ ≈ tens of thousands. For $K_{\max} = 2000$ and `nnz(T_S) ≈ 30,000`: ~$1.8 \times 10^8$ flops, sub-second.

**Memory:** 3 arrays of size $(K_{\max}+1) \times A \cdot J$. For $K_{\max} = 2000$, $A \cdot J = 800$: 6.4M entries × 3 = ~150 MB at float64. Fine for production. Could compress (downsample cohort ages, store float32) if needed for very large grids.

### Task 2.4 — Add `compute_doob_v2_a`

**Where:** `Code/HA-Models/FromPandemicCode/tm_methods.py`, after `compute_doob_pi_q_a`.

**Purpose:** companion to `compute_doob_pi_q_a` that computes the second-moment Doob system $(I - T_{S, p^2}) f_2 = \bar{\delta} \cdot \pi_N$. Returns $f_2$, $v_2 = f_2 / \pi_P$, and conditional variance $V(x) = v_2(x) - w(x)^2$.

**Signature:**
```python
def compute_doob_v2_a(agent, tm_data, ergodic_P, doob_out=None, ...):
    """
    Compute conditional second moment v_2(x) = E_P[p² | x] via the same
    sparse linear system structure as compute_doob_pi_q_a, with G²ψ²
    weighting in T_S,p² instead of Gψ in T_S,p.

    Returns: {'f_2', 'v_2', 'conditional_variance', 'T_S_p2'}
    """
```

**Need this for:** (a) the cross-check in Task 2.3 step 11; (b) extending `init_mc_from_doob_a` with 2-moment lognormal fit (§23.7 alternative).

**Cost:** one sparse linear solve, comparable to existing Doob solve. ~10ms for our grids.

### Task 2.5 — Add `init_mc_from_cohort_age_decomposition`

**Where:** `Code/HA-Models/FromPandemicCode/tm_methods.py`, after `init_mc_from_doob_a`.

**Signature:**
```python
def init_mc_from_cohort_age_decomposition(
    agent, cohort_dec, dist_aGrid, N, seed):
    """
    Initialize MC agent state from the cohort-age decomposition output.

    Three-step sampling per math doc §24.8:
      1. K_i ~ Geometric(1-L), truncated at K_max
      2. (a_i, j_i) ~ π^{(K_i)}(.)
      3. p_i ~ Lognormal(μ_{X_i}^{(K_i)}, σ_{X_i}^{(K_i)})
         with parameters from (eq:cohort-lognormal-fit)

    Sets agent.state_now['aNrm'], 'pLvl', 'MrkvNowPcvd', 't_age'.
    """
```

**Algorithm:**
```
1. K_max = cohort_dec['pi_k'].shape[0] - 1
2. Sample cohort ages: K_arr = rng.geometric(...); clip to K_max
3. For each unique k in K_arr:
     Sample N_k = count of agents with K==k
     Sample (a_idx, j) from pi_k[k] for those N_k agents
     Compute per-cell M_1, M_2 from g1_k[k], g2_k[k], pi_k[k]
     Compute σ_x, μ_x via (eq:cohort-lognormal-fit)
     Sample p_i ~ Lognormal(μ_x, σ_x) for each agent
4. Set agent.state_now['aNrm'] = dist_aGrid[a_idx]
5. Set agent.state_now['MrkvNowPcvd'] = j
6. Set agent.state_now['pLvl'] = p_i
7. Set agent.t_age = K_arr (so HARK's tracking knows the cohort age)
```

**Concern:** setting `agent.t_age` may interact with HARK's internal mortality tracking. Need to verify that simulating forward from this t_age state does not double-count mortality (i.e., HARK shouldn't immediately kill agents with very high t_age unless that's the intended Bewley-style behavior). Likely OK because HARK applies LivPrb each period regardless of t_age.

### Task 2.6 — Extend `harmenberg_doob_drift_test.py` with cohort-init variant

**Where:** `Code/HA-Models/FromPandemicCode/harmenberg_doob_drift_test.py`.

**Add a 5th config-axis:** `init_method ∈ {'doob_1moment', 'doob_2moment', 'cohort_age'}`.

For each (β, interpretation, init_method), run drift sweep over $t \in \{0, 10, 25, 50, 100, 200\}$. Report drift in $\mathbb{E}_P[a]$, $\mathbb{E}_Q[a]$, $\mathbb{E}_P[p]$, state-fractions.

**Pass criteria:**
- E_P[a] drift: same ≤ 0.5% as current 1-moment init (this is the (a,j)-marginal, which is correct under any init that uses TM-P)
- E_Q[a] drift, HS β=0.91: should shrink from current ~5% to within MC noise (~0.5%)
- E_Q[a] drift, CO β=0.988: should shrink from current ~20% to substantially less (target: ≤ 5%); residual is from j-path heterogeneity within cohort and constrained-survivor mixture (§23.8)

### Task 2.7 — Numerical-validity tests as unit tests

**Where:** `Code/HA-Models/FromPandemicCode/test_cohort_age_decomposition.py` (new file).

Tests to implement (per math doc §24.12):

| Test | Equation | Pass criterion |
|---|---|---|
| `test_TM_P_decomp` | $(eq:TM\text{-P-decomp})$ | $T_S + (1 - L_j) \pi_N \mathbb{1}^\top = T_P$, max abs error < 1e-12 |
| `test_pi_k_normalization` | $(eq:cohort\text{-cond-dist})$ | $\sum_x \pi^{(\ell)}(x) = 1$ for every $\ell$, abs error < 1e-12 |
| `test_pi_P_aggregation` | $(eq:cohort\text{-aggregate-marginal})$ | $\sum_\ell (1-L) L^\ell \pi^{(\ell)} = \pi_P^{TM}$, max abs error < $L^{K_{\max}+1} + 10^{-10}$ |
| `test_v1_aggregation` | $(eq:cohort\text{-aggregate-moment})$ for $k=1$ | $\sum_\ell (1-L) L^\ell g_1^{(\ell)} = w \cdot \pi_P$ (Doob), error tolerance same as above |
| `test_v2_aggregation` | $(eq:cohort\text{-aggregate-moment})$ for $k=2$ | $\sum_\ell (1-L) L^\ell g_2^{(\ell)} = v_2 \cdot \pi_P$ (Doob v2 helper), error tolerance same |
| `test_within_cohort_lognormal` | $(eq:within\text{-cohort-lognormal})$ | Run MC, partition by t_age=k, fit lognormal to within-cohort log p, compare to analytical $\mu, \sigma$ from recursion. Tolerance: relative error < 5% (limited by MC sampling at large k) |
| `test_cohort_weight_geom` | $(eq:cohort\text{-weight-geom})$ | Run MC, tabulate t_age distribution, compare to $(1-L)L^k$. Tolerance: relative error < 1% |

Each test has clear pass/fail. Run via `pytest Code/HA-Models/FromPandemicCode/test_cohort_age_decomposition.py`.

### Task 2.8 — Documentation updates

- **`tm_methods.py` docstrings:** thorough docstring on each new function pointing to math doc §24 sections.
- **Math cheat-sheet (`BUGS_private/HAFiscal_splurge_budget_inconsistency/math_cheatsheet_tm_a_p_vs_q.md`):** add code-site references for each §24 equation now that they're implemented.
- **Conclusions log:** new entry summarizing the empirical drift improvement (or non-improvement) from cohort-init vs single-lognormal init, with numbers from Task 2.6.

---

## 3. Cascade-gated execution order

Per the user's standing preference for cascade-gating (memory `feedback_cascade_gating.md`):

**Tier 0 (~10 min, sub-second compute):**
- Task 2.1 + 2.2: build the two new survival kernels
- Run unit tests: `test_TM_P_decomp`, kernel structural tests
- **HALT if structural tests fail.**

**Tier 1 (~30 min, sub-second compute):**
- Task 2.3 + 2.4: cohort decomposition + Doob v_2 helper
- Run cross-check tests: `test_pi_k_normalization`, `test_pi_P_aggregation`, `test_v1_aggregation`, `test_v2_aggregation`
- **HALT if any aggregation cross-check fails to within $L^{K_{\max}+1}$ tolerance.**

**Tier 2 (~30 min, ~1 min compute):**
- Task 2.5: `init_mc_from_cohort_age_decomposition`
- Run within-cohort lognormality sanity test on a single config (HS β=0.91, N=200k)
- **HALT if observed within-cohort log-p mean/variance disagree with analytical by > 5% at small ages.**

**Tier 3 (~30 min, ~10 min compute):**
- Task 2.6: extend drift test, run on 4 baseline configs (HS×CDC, HS×ESC, CO×CDC, CO×ESC)
- **PASS criterion:** cohort-init E_Q[a] drift < doob_1moment drift in all 4 configs; ideally cohort-init drift falls within MC noise (~0.5%) for HS, < 5% for CO.

**Tier 4 (deferred, ~1 hour each):**
- Task 2.7 full pytest suite
- Task 2.8 documentation updates
- Conclusions log entry

---

## 4. Risk assessment and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Truncation tail $L^{K_{\max}+1}$ at $L=0.99$, $K_{\max}=2000$ is $\approx 10^{-9}$ — negligible. At $L=0.9905$ same $K_{\max}$ gives $\approx 10^{-8}$. Fine. | Low | Low | Already accounted for; tolerance is $L^{K_{\max}+1}$ |
| State-dependent $L_j$ would break the closed-form geometric. HAFiscal uses constant $L_j$ per cohort (mortality rate doesn't depend on employment), so this should be fine. **Verify this assumption** during Task 2.3. | Low | Medium | Inspect `agent.LivPrb`; if state-dependent, extend per §24.6 generalization |
| Within-cohort j-path heterogeneity makes the per-cohort lognormal fit imperfect. This is a residual error, not a defect. | Medium | Low | Documented limitation (§24.9 of math doc); acceptable |
| `agent.t_age` interaction with HARK forward simulation. If HARK uses t_age in any mortality decision, our cohort-init might cause erratic forward dynamics. | Low | High | Inspect `AggFiscalModel.sim_one_period` and HARK base; verify forward sim treats t_age as informational only. Add unit test that runs MC with cohort-init for 5 periods and confirms no agent dies prematurely. |
| Memory at large $K_{\max}$. 150 MB at $K_{\max}=2000$, A·J=800 is fine. Larger grids could push this. | Low | Low | Float32 fallback or downsample cohort ages if needed |
| Numerical underflow in $L^{K_{\max}}$ when computing geometric weights at very large $K_{\max}$. With $L \in (0.99, 1)$ this is fine; at $K_{\max}=10000$ and $L=0.99$, $L^{K_{\max}} \approx 4 \times 10^{-44}$ — still representable in float64. | Low | Low | Cap $K_{\max}$ at 5000 |
| Doob v_2 cross-check requires implementing `compute_doob_v2_a` as a prerequisite. Order of Task 2.4 vs 2.3 matters. | Medium | Low | Plan order is correct: Task 2.4 in Tier 1 alongside Task 2.3 |

---

## 5. Success criteria

**Tier 0–2 (math correctness):**
- All unit tests in Task 2.7 pass at the specified tolerances.
- Aggregation cross-checks against TM-P ergodic and Doob $w$ pass to within $L^{K_{\max}+1} + 10^{-10}$.
- Within-cohort lognormality sanity test confirms model-implied $\mu_x^{(k)}$, $\sigma_x^{(k)}$ match MC empirical to within MC noise.

**Tier 3 (drift improvement):**
- Cohort-init E_Q[a] drift < doob_1moment E_Q[a] drift in all 4 configs (HS×{CDC,ESC}, CO×{CDC,ESC}).
- For HS β=0.91: cohort-init E_Q[a] drift within MC noise floor (≤ 0.5% over 200 periods).
- For CO β=0.988: cohort-init E_Q[a] drift substantially reduced (≤ 5% — target; baseline is ~20%).
- E_P[a] drift unchanged (≤ 0.5%, already correct under TM-P-faithful init).

**Tier 4 (publishable contribution? optional):**
- Empirical investigation of Carroll's Ω_cov conjecture using the cohort-age framework — defer; not part of this implementation plan.

---

## 6. Out-of-scope (intentionally deferred)

- **Carroll Ω_cov conjecture investigation** (math doc §24.13): requires a separate analytical effort; not bundled.
- **Higher than v_2 in Doob ladder** (math doc §23.7): not needed for cohort-init; cohort-faithful init already captures the mixture structure that v_3+ would address differently.
- **3-parameter family per cohort** (e.g., gen-gamma instead of lognormal): extension if drift remains material; not in scope unless Tier 3 fails.
- **Refactoring `_build_p_weighted_survival_kernel_a` and `_build_p2_weighted_survival_kernel_a` into a shared `_build_pk_weighted_survival_kernel_a(k=...)`** function: cosmetic; defer until both versions are debugged.
- **Production wiring in `compute_baseline_tm_data`:** the cohort-init helper is for diagnostic/research; doesn't need to be in the production Step 5 path. If we eventually want to use it for production MC, add a separate sub-plan.

---

## 7. Estimated total effort

**Coding:** ~6 hours focused work (3 new functions, 1 extension, 1 test file, 1 drift-test extension)

**Compute:** ~30 minutes total (Tier 3 drift test is the bottleneck at ~10 min)

**Documentation:** ~2 hours (cheat-sheet updates, conclusions log)

**Total wall-clock:** assuming sequential cascade-gated execution with HALT on failure, estimated 1 working day to complete Tier 0–3.

---

## 8. Approval gates

This plan should not begin execution until the user explicitly approves. Specifically:

- **Approval to proceed past Tier 0:** confirms the kernel-structure approach matches user's intent.
- **Approval to proceed past Tier 1:** confirms aggregation cross-checks are the right validity gate.
- **Approval to proceed past Tier 2:** confirms the `init_mc_from_cohort_age_decomposition` API is acceptable.
- **Approval to proceed past Tier 3:** confirms the empirical drift-reduction is sufficient to call this complete.

If any tier fails, default action is HALT and report to user. No autonomous fixing without explicit go-ahead.

---

## 9. Branch / merge workflow

Per user instruction (2026-04-29):

1. **Pre-implementation: push current branch.** All preparatory work (math doc §14.0, §23, §24, the four cascade-gate scripts, the production a-indexed Doob Step 5 outputs, the GIC tightening, this plan itself) must first be committed and pushed on the current branch `bug034-035-cdc-consistency-cleanup` to `origin`.

2. **Create implementation branch.** Branch off `bug034-035-cdc-consistency-cleanup` as:
   ```
   git checkout -b cohort-age-mc-init bug034-035-cdc-consistency-cleanup
   git push -u origin cohort-age-mc-init
   ```

3. **Build new machinery on the implementation branch.** All code changes for Tasks 2.1–2.8 happen on `cohort-age-mc-init`. Tier-by-tier commits with cascade-gate HALTs as specified in §3.

4. **Per-tier merge gate.** After each successful tier, push the implementation branch. Do **not** merge back to `bug034-035-cdc-consistency-cleanup` mid-implementation — wait until Tier 3 (drift improvement) passes its success criteria.

5. **Final merge plan.** When all tiers pass:
   - Run a final integration check on `cohort-age-mc-init`: confirm full pytest suite passes; confirm the existing Doob and TM-P production paths are still bit-identical (no regressions).
   - Open a merge candidate / wait for user approval.
   - On approval, fast-forward merge `cohort-age-mc-init` into `bug034-035-cdc-consistency-cleanup` (or rebase + merge as the user prefers).
   - Push the merged `bug034-035-cdc-consistency-cleanup`.
   - Optionally retain the `cohort-age-mc-init` branch as a checkpoint, or delete after merge.

6. **Failure-mode plan.** If Tier 3 fails to meet the drift-reduction success criteria after reasonable diagnostic effort, the implementation branch can be retained as a documented "tried this and it didn't help" artifact without merging back. The math doc §24 derivation stands either way (the math is correct; the implementation may or may not help in practice).
