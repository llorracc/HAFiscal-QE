<!-- Status: DONE (superseded by implementation) -->
# Harmenberg Permanent-Income-Neutral Measure: Theory and Implementation

**Date**: 2026-04-01
**Reference**: Harmenberg (2021), "Aggregating heterogeneous-agent models with permanent income shocks", *Journal of Economic Dynamics and Control*, 129, 104185.
**Context**: Plan for implementing Harmenberg MC in HAFiscal / HARK

---

## Table of Contents

1. [The Aggregation Problem](#1-the-aggregation-problem)
2. [The Standard Monte Carlo Approach](#2-the-standard-monte-carlo-approach)
3. [The Harmenberg Neutral Measure](#3-the-harmenberg-neutral-measure)
4. [Harmenberg Monte Carlo Simulation](#4-harmenberg-monte-carlo-simulation)
5. [Transition Matrix Methods](#5-transition-matrix-methods)
6. [Harmenberg TM: Dimension Reduction](#6-harmenberg-tm-dimension-reduction)
7. [Summary: Four Approaches](#7-summary-four-approaches)
8. [HARK Implementation Status](#8-hark-implementation-status)
9. [Implementation Plan for HAFiscal](#9-implementation-plan-for-hafiscal)

---

## 1. The Aggregation Problem

### 1.1 Setup

Consider a heterogeneous-agent model where agent $i$ at time $t$ has:
- Permanent income $p_{i,t}$ following a geometric random walk
- Normalized market resources $m_{i,t} = \mathbf{m}_{i,t} / p_{i,t}$
- A discrete Markov state $z_{i,t} \in \{0, 1, \ldots, J-1\}$

The agent's problem is **homothetic** in permanent income under CRRA
utility, so the optimal consumption function satisfies:

$$
\mathbf{c}(\mathbf{m}, p, z) = c(m, z) \cdot p
$$

where $c(m, z)$ is the **normalized** consumption function (solved once,
independent of $p$).

### 1.2 Permanent Income Dynamics

Permanent income evolves as:

$$
p_{i,t+1} = \Phi_{z_{t+1}} \cdot \psi_{i,t+1} \cdot p_{i,t}
$$

where $\Phi_z$ is the state-dependent permanent growth factor and $\psi$
is a mean-one permanent shock:

$$
\mathbb{E}_P[\psi] = 1
$$

### 1.3 The Aggregation Challenge

Aggregate consumption at time $t$ is:

$$
\mathbf{C}_t = \int \int \int c(m, z) \cdot p \cdot f_t(m, p, z) \, dm \, dp \, dz
$$

where $f_t(m, p, z)$ is the joint distribution over $(m, p, z)$.

Even though the **solution** is independent of $p$ (thanks to homotheticity),
the **aggregation** requires tracking $p$ because $p$ enters multiplicatively.
The $p$ dimension is a geometric random walk with an unbounded distribution,
making direct numerical integration over $p$ difficult and MC approximation
noisy (a small number of high-$p$ agents dominate the sum).

---

## 2. The Standard Monte Carlo Approach

### 2.1 Algorithm

1. **Solve** the normalized problem to obtain $c(m, z)$
2. **Initialize** $N$ agents with $(m_{i,0}, p_{i,0}, z_{i,0})$
3. **For each period** $t = 0, 1, \ldots, T-1$:
   - Draw shocks $(\psi_{i,t+1}, \theta_{i,t+1})$ from income distribution
   - Draw Markov transitions $z_{i,t+1}$
   - Update permanent income: $p_{i,t+1} = \Phi_{z_{t+1}} \psi_{i,t+1} p_{i,t}$
   - Compute savings: $a_{i,t} = m_{i,t} - c(m_{i,t}, z_{i,t})$
   - Compute next-period resources: $m_{i,t+1} = R_{z_{t+1}} a_{i,t} / (\Phi_{z_{t+1}} \psi_{i,t+1}) + \theta_{i,t+1}$
   - Handle mortality and newborns
4. **Aggregate**: $\hat{\mathbf{C}}_t = \frac{1}{N} \sum_{i=1}^N c(m_{i,t}, z_{i,t}) \cdot p_{i,t}$

### 2.2 Variance Problem

The MC estimator of $\mathbf{C}_t$ has variance:

$$
\text{Var}\left(\hat{\mathbf{C}}_t\right) = \frac{1}{N} \text{Var}\left(c(m, z) \cdot p\right)
$$

Since $p$ is a geometric random walk, $\text{Var}(c \cdot p)$ is dominated by
the variance of $p$ itself. Agents in the tail of the $p$ distribution
contribute disproportionately to the sum, requiring very large $N$ for
accurate aggregates. Typical MC simulations need $N \geq 10{,}000$ agents
(HAFiscal uses 10,000 across 21 types for baseline).

### 2.3 Budget Constraint and Transition Equations

For completeness, the within-period transitions (standard MC, state $z$):

$$
\begin{aligned}
b_{i,t} &= R_z \cdot a_{i,t-1} \\
m_{i,t} &= \frac{b_{i,t}}{\Phi_z \psi_{i,t}} + \theta_{i,t} \\
c_{i,t} &= c(m_{i,t}, z_{i,t}) \\
a_{i,t} &= m_{i,t} - c_{i,t}
\end{aligned}
$$

where $b$ is beginning-of-period bank balances (normalized by previous $p$),
and the division by $\Phi_z \psi$ converts to the new normalization basis
$p_{t} = \Phi_z \psi_t p_{t-1}$.

---

## 3. The Harmenberg Neutral Measure

### 3.1 Permanent-Income-Weighted Distribution

Harmenberg's first insight: define the **permanent-income-weighted
marginal distribution** of normalized resources:

$$
\tilde{\mu}_t(m, z) := \Phi^{-t} \int p \cdot f_t(m, p, z) \, dp
$$

where $\Phi$ is the deterministic growth trend. This object measures
"the total permanent income accruing to agents with normalized resources
$m$ in state $z$." Then aggregate consumption becomes:

$$
\mathbf{C}_t = \Phi^t \int \sum_z c(m, z) \cdot \tilde{\mu}_t(m, z) \, dm
$$

No $p$-integration needed — if we can track $\tilde{\mu}_t$.

### 3.2 The Change of Measure

Harmenberg's second insight: $\tilde{\mu}_t$ evolves under a **tilted**
shock distribution. Define the **permanent-income-neutral measure** $Q$:

$$
q_s = \frac{p_s \cdot \psi_s}{\mathbb{E}_P[\psi]} = p_s \cdot \psi_s
$$

where $p_s$ is the $P$-measure probability of shock realization $s = (\psi_s, \theta_s)$,
and the last equality uses $\mathbb{E}_P[\psi] = 1$.

**Radon-Nikodym derivative**: $dQ/dP|_s = \psi_s$

**Key identity**: For any function $g(m, z)$ of the normalized state:

$$
\mathbb{E}_P[p \cdot g(m, z)] = \mathbb{E}_Q[g(m, z)] \cdot \mathbb{E}_P[p]
$$

This factorization separates the $p$-dependent part (which is just a scalar
$\mathbb{E}_P[p]$, computable analytically) from the $m$-dependent part
(which can be computed under $Q$ without tracking $p$).

### 3.3 Transition Under $Q$

The normalized budget constraint $m_{t+1} = b_t / (\Phi_z \psi_{t+1}) + \theta_{t+1}$
depends on $\psi$. Under $Q$, we draw $\psi$ from the tilted distribution
$\tilde{f}_\psi(\psi) = \psi \cdot f_\psi(\psi)$ — larger permanent shocks
are more likely. The normalized transition kernel $\Lambda(m_{t+1} | m_t, \psi_{t+1})$
remains the same; only the **probabilities** of the shocks change.

The permanent-income-weighted distribution transitions as:

$$
\tilde{\mu}_{t+1}(m') = \int \Lambda(m' | m, \psi) \cdot \tilde{f}_\psi(\psi) \cdot \tilde{\mu}_t(m) \, dm \, d\psi
$$

This is **identical in structure** to the standard transition, with $\tilde{f}_\psi$
replacing $f_\psi$. Therefore:
- The same simulation code works
- The same TM code works
- Only the **shock probabilities** change

### 3.4 Properties of $Q$

Under the neutral measure $Q$:

1. **$\mathbb{E}_Q[\psi] = \mathbb{E}_P[\psi^2] > 1$**: the mean permanent
   shock is no longer 1; it equals the second moment under $P$.

2. **$\mathbb{E}_Q[1/\psi] = 1$**: the mean of the reciprocal is 1.
   This is the "dual" normalization that makes the budget constraint
   $m_{t+1} = b_t/(\Phi\psi) + \theta$ well-behaved under $Q$.

3. **Stationarity condition (GICHrm)**: The permanent-income-weighted
   distribution is stationary iff $\text{GPFac}_{\text{Hrm}} < 1$, where:
   $$
   \text{GPFac}_{\text{Hrm}} = \frac{(\beta R)^{1/\rho}}{\Phi \cdot \exp(\mathbb{E}_P[\psi \log \psi])}
   $$

### 3.5 Analytical $\mathbb{E}_P[p]$

Under mortality rate $\delta$ and growth factor $\Phi$:

$$
\mathbb{E}_P[p] = p_0 \cdot \frac{1}{1 - (1-\delta)\Phi}
$$

where $p_0 = \mathbb{E}[p_{\text{newborn}}]$ is the mean initial permanent income.
More precisely, with state-dependent growth and mortality:

$$
\mathbb{E}_P[p] = \sum_z \pi_z \cdot \frac{\bar{p}_{\text{newborn},z}}{1 - \text{LivPrb}_z \cdot \Phi_z}
$$

This is implemented in HAFiscal's `compute_analytical_mean_pLvl()`.

---

## 4. Harmenberg Monte Carlo Simulation

### 4.1 Algorithm

The Harmenberg MC is **identical to standard MC except**:

1. **Shock drawing**: Replace $P$-measure shock probabilities with $Q$-measure:
   - For the discrete approximation to permanent shocks with atoms
     $\{\psi_k\}$ and probabilities $\{p_k\}$, set:
     $$q_k = p_k \cdot \psi_k \quad (\text{then renormalize if needed})$$
   - Transitory shocks and Markov transitions are **unchanged**

2. **Aggregation**: Replace the standard formula with:
   $$\hat{\mathbf{C}}_t = \left(\frac{1}{N} \sum_{i=1}^N c(\tilde{m}_{i,t}, z_{i,t})\right) \cdot \mathbb{E}_P[p] \cdot N$$
   where $\tilde{m}_{i,t}$ denotes the $Q$-measure simulated normalized
   resources (no $p_{i,t}$ multiplication).

3. **No need to track $p_{i,t}$**: The permanent income level is not
   simulated or stored. $\mathbb{E}_P[p]$ is computed analytically.

### 4.2 HARK Implementation

In HARK, the implementation is remarkably simple:

```python
# Standard MC
agent = IndShockConsumerType(**params)
agent.solve()
agent.initialize_sim()
agent.simulate()

# Harmenberg MC — only two lines different
agent_Q = deepcopy(agent)
agent_Q.neutral_measure = True
agent_Q.update_income_process()  # rebuilds IncShkDstn with tilted probs
agent_Q.initialize_sim()
agent_Q.simulate()
```

The magic happens in `LognormPermIncShk.__init__()`:
```python
if neutral_measure:
    logn_approx.pmv = (logn_approx.atoms * logn_approx.pmv).flatten()
```

This multiplies each shock probability by its permanent shock value,
implementing $q_k = p_k \cdot \psi_k$.

### 4.3 Variance Reduction

Under $Q$, the MC estimator variance becomes:

$$
\text{Var}_Q\left(\hat{\mathbf{C}}_t\right) = \frac{(\mathbb{E}_P[p])^2}{N} \text{Var}_Q(c(m, z))
$$

Since $\text{Var}_Q(c(m, z))$ is bounded (no $p$ multiplication), the variance
reduction is dramatic. The DemARK notebook demonstrates **orders of magnitude**
reduction in aggregate variance for a given agent count:

- Standard MC with 10,000 agents ≈ Harmenberg MC with 100 agents
- This implies a **~100x** effective sample size improvement

### 4.4 What Changes in the Budget Constraint

Under $Q$, agents' permanent income shocks are drawn from
$\tilde{f}_\psi$ rather than $f_\psi$. The budget constraint is:

$$
\tilde{m}_{t+1} = \frac{R_z \tilde{a}_t}{\Phi_z \psi_{t+1}} + \theta_{t+1}
$$

with $\psi_{t+1} \sim Q$ (i.e., drawn with tilted probabilities). The
**savings decision** $\tilde{a}_t = \tilde{m}_t - c(\tilde{m}_t, z_t)$ uses the
**same** consumption function $c(m, z)$ — the policy function is invariant
to the probability measure used for simulation.

### 4.5 What Does NOT Change

- The **solution** (consumption function) is identical
- The **Markov transitions** are identical
- The **transitory shock** distribution is identical
- The **mortality/newborn** process is identical
- The **budget constraint equations** are identical

---

## 5. Transition Matrix Methods

### 5.1 Standard 2D TM (State: $m \times p \times z$)

Discretize the state space on grids:
- $m$-grid: $\{m_1, \ldots, m_M\}$
- $p$-grid: $\{p_1, \ldots, p_K\}$
- Markov states: $\{0, \ldots, J-1\}$

The transition matrix $\mathbf{T}$ has dimension $(M \cdot K \cdot J) \times (M \cdot K \cdot J)$.
Entry $T_{(m',p',j'),(m,p,j)}$ gives the probability of transitioning from
state $(m, p, j)$ to $(m', p', j')$ in one period.

For each source node $(m_i, p_k, j)$:
1. Compute savings: $a_i = m_i - c(m_i, j)$
2. For each destination Markov state $j'$ with probability $\Pi_{j,j'}$:
3. For each shock realization $(\psi_s, \theta_s)$ with probability $w_s$:
   - $m'_s = R_{j'} a_i / (\Phi_{j'} \psi_s) + \theta_s$
   - $p'_s = p_k \cdot \Phi_{j'} \psi_s$
   - Use bilinear "lottery" to place mass on the $(m', p')$ grid

**Pros**: Exact (up to grid discretization), deterministic (no MC noise)
**Cons**: $O(M \cdot K \cdot J)$ state space; the $p$-grid is hard to design
(unbounded support) and makes the matrix large.

### 5.2 Ergodic Distribution

The ergodic distribution $\bar{f}$ satisfies $\mathbf{T} \bar{f} = \bar{f}$.
Find it by power iteration or eigendecomposition. Then:

$$
\mathbf{C} = \sum_j \sum_i \sum_k c(m_i, j) \cdot p_k \cdot \bar{f}(m_i, p_k, j)
$$

This is the "direct level aggregate" approach used in `test_threeway.py`'s
method (b).

---

## 6. Harmenberg TM: Dimension Reduction

### 6.1 Collapsing $p$ to a Single Point

Under the neutral measure, the permanent-income-weighted distribution
$\tilde{\mu}(m, z)$ **does not depend on $p$**. The TM state space
reduces to $m \times z$ only:

- $m$-grid: $\{m_1, \ldots, m_M\}$
- Markov states: $\{0, \ldots, J-1\}$

The TM has dimension $(M \cdot J) \times (M \cdot J)$ — a factor of $K$
smaller than the 2D case.

### 6.2 Neutral-Measure TM Construction

For each source node $(m_i, j)$:
1. Compute savings: $a_i = m_i - c(m_i, j)$, bank balance $b_i = R_j a_i$
2. For each destination state $j'$ with Markov probability $\Pi_{j,j'}$:
3. For each shock $(\psi_s, \theta_s)$ with **$Q$-measure** probability $q_s = w_s \cdot \psi_s$:
   - $m'_s = b_i / (\Phi_{j'} \psi_s) + \theta_s$
   - Use linear "lottery" to place mass on the $m'$-grid

This is exactly `gen_tran_matrix_1D` in HARK's `utilities.py`, which
documents: *"used exclusively when Harmenberg Neutral Measure is applied
and/or if permanent income is not a state variable."*

### 6.3 Aggregation Under the Neutral TM

With ergodic distribution $\tilde{\bar{\mu}}(m, z)$ under $Q$:

$$
\mathbf{C} = \left(\sum_j \sum_i c(m_i, j) \cdot \tilde{\bar{\mu}}(m_i, j)\right) \cdot \mathbb{E}_P[p]
$$

This is method (c) in `test_threeway.py`: "E*[c] · E_analytical[p]".

### 6.4 HARK Implementation

In HARK's `ConsNewKeynesianModel.py`, setting `neutral_measure = True`:
- `define_distribution_grid()` sets `dist_pGrid = [1]` (single point)
- `calc_transition_matrix()` uses `gen_tran_matrix_1D` when `len(dist_pGrid) == 1`

In HAFiscal's `tm_methods.py`:
- `_to_neutral_measure()` reweights `IncShkDstn` probabilities by $\psi$
- `_build_period_tm()` accepts the neutral `IncShkDstn` and builds a 1D TM
- `neutral_measure=True` flag is threaded through all TM functions

---

## 7. Summary: Four Approaches

| | Standard | Harmenberg |
|----------|----------|------------|
| **Monte Carlo** | Track $(m_i, p_i, z_i)$ for $N$ agents. Aggregate: $\hat{C} = \frac{1}{N}\sum c(m_i,z_i) \cdot p_i$. Variance $\propto \text{Var}(cp)/N$. | Track $(\tilde{m}_i, z_i)$ only. Draw $\psi$ from $Q$. Aggregate: $\hat{C} = \frac{1}{N}\sum c(\tilde{m}_i,z_i) \cdot E_P[p]$. Variance $\propto \text{Var}_Q(c)/N$. |
| **Transition Matrix** | State space $m \times p \times z$. TM dimension: $MKJ \times MKJ$. Exact but large. | State space $m \times z$ only. TM dimension: $MJ \times MJ$. $K$-fold reduction. |

### Computational Cost Comparison

| Method | State dimension | Per-step cost | Variance |
|--------|----------------|---------------|----------|
| Standard MC | 3D (m,p,z) | O(N) | High (dominated by p-tail) |
| Harmenberg MC | 2D (m,z) | O(N), but N can be 5-100x smaller | Low (no p-variance) |
| Standard TM | 3D grid | O(M·K·J) per source | Zero (deterministic) |
| Harmenberg TM | 2D grid | O(M·J) per source | Zero (deterministic) |

### Accuracy

All four methods converge to the **same** aggregate in the limit:
- MC methods: as $N \to \infty$
- TM methods: as grid resolution $\to \infty$

The Harmenberg transformation is **exact** (not an approximation) — it changes
the probability measure but not the economic model. Any error is purely from
the discretization or finite-sample approximation, not from the change of measure.

---

## 8. HARK Implementation Status

### 8.1 What Exists in HARK (branch ConsAggIndMarkovModel)

| Component | File | Status |
|-----------|------|--------|
| `neutral_measure` parameter | `ConsIndShockModel.py` defaults | ✅ Present |
| Shock reweighting | `LognormPermIncShk.__init__()` | ✅ Implemented |
| Income process constructors | `IncomeProcesses.py` | ✅ Thread `neutral_measure` |
| Markov income constructor | `IncomeProcesses.py` | ✅ Per-state neutral measure |
| `gen_tran_matrix_1D` | `utilities.py` | ✅ Harmenberg TM helper |
| NK model TM integration | `ConsNewKeynesianModel.py` | ✅ `dist_pGrid=[1]` |
| SSJ / simulator `norm` | `simulator.py`, `SSJutils.py` | ✅ `quasi_run` reweighting |
| GICHrm condition | `ConsIndShockModel.py` | ✅ Diagnostic |
| **MC aggregation adjustment** | — | ❌ **Not built in** |
| **MarkovConsumerType MC** | `ConsMarkovModel.py` | ❌ **Not modified for Harmenberg** |

### 8.2 The Gap: MC Aggregation

HARK's `neutral_measure=True` changes the **shock draws** but does NOT
automatically adjust the **aggregation formula**. After simulation:
- `history['cNrm']` contains $c(\tilde{m}, z)$ under $Q$
- `history['pLvl']` still tracks simulated $p$ (with $Q$-tilted shocks)

To get correct aggregates, the user must:
1. Aggregate $c_{\text{nrm}}$ **without** multiplying by $p$
2. Multiply by $\mathbb{E}_P[p]$ (analytically computed)

The DemARK notebook does this manually but the HARK library does not
provide an automatic aggregation mode. This is the primary gap.

### 8.3 The Gap: MarkovConsumerType

`MarkovConsumerType` inherits `neutral_measure` as a default parameter,
but its income process is often constructed manually (as in HAFiscal's
`AggFiscalType`). The `update_income_process()` path that applies
neutral-measure reweighting is in the **constructors** called by
`IndShockConsumerType`, not by the manual HAFiscal setup.

For HAFiscal's `AggFiscalType` (which uses `construct=False` and builds
`IncShkDstn` manually in `Simulate.py`), the reweighting must be applied
**after** the manual construction, mirroring `_to_neutral_measure()`.

---

## 9. Implementation Plan for HAFiscal

### 9.1 Phase 1: Validate on Simple Model (in HARK context)

Create a notebook demonstrating all four approaches on `IndShockConsumerType`:
1. Standard MC (N=50,000, 200 periods)
2. Harmenberg MC (N=50,000, then N=1,000 showing equivalent accuracy)
3. Standard 2D TM (m×p grid)
4. Harmenberg 1D TM (m grid only)

Compare: steady-state aggregate consumption $\mathbf{C}$, variance of
estimates, computational time.

### 9.2 Phase 2: Extend to MarkovConsumerType

Same four-way comparison but with Markov states (employed/unemployed),
demonstrating that the neutral measure works correctly with state-dependent
income distributions.

### 9.3 Phase 3: Implement in AggFiscalType

#### Step 3a: Create `apply_neutral_measure()` utility

```python
def apply_neutral_measure(IncShkDstn_list):
    """Reweight income distribution probabilities by permanent shock atoms."""
    neutral_list = []
    for dstn in IncShkDstn_list:
        perm_shks = dstn.atoms[0]
        if np.all(perm_shks == 1.0):  # degenerate (unemployed)
            neutral_list.append(dstn)
        else:
            neutral_pmv = dstn.pmv * perm_shks
            neutral_pmv /= neutral_pmv.sum()
            neutral_list.append(
                DiscreteDistribution(neutral_pmv, dstn.atoms)
            )
    return neutral_list
```

#### Step 3b: Modify `Simulate.py` shock construction

After building `IncShkDstn` manually, apply neutral measure:

```python
if sim_method == 'MC_Harmenberg':
    for ThisType in TypeList:
        ThisType.IncShkDstn = [
            apply_neutral_measure(ThisType.IncShkDstn[0])
        ]
        ThisType.IncShkDstn_base = ThisType.IncShkDstn
        # Also reweight recession variants
        ThisType.IncShkDstn_recession = [
            apply_neutral_measure(ThisType.IncShkDstn_recession[0])
        ]
```

#### Step 3c: Modify aggregation in `run_experiment()`

```python
# Current (standard MC):
AggCons = np.sum(cLvl_all_splurge, axis=1)  # sum of c*p across agents

# New (Harmenberg MC):
if self.neutral_measure:
    E_pLvl = sum(compute_analytical_mean_pLvl(a) * a.AgentCount
                 for a in self.agents)
    AggCons_nrm = np.sum(cNrm_all_splurge, axis=1)  # sum of c (no p)
    AggCons = AggCons_nrm * E_pLvl / PopCount
else:
    AggCons = np.sum(cLvl_all_splurge, axis=1)
```

#### Step 3d: Validate

- Run Reduced_Run with standard MC (10K agents, 3 seeds)
- Run Reduced_Run with Harmenberg MC (10K agents, then 2K, 1K)
- Compare multiplier tables: should agree within MC noise
- Measure variance reduction

### 9.4 Phase 4: Production Run

- Full Baseline with Harmenberg MC at reduced agent count
- Compare all tables against existing MC and TM results
- Document speedup and accuracy

---

## Appendix A: Proof of the Key Identity

**Claim**: $\mathbb{E}_P[p \cdot g(m)] = \mathbb{E}_Q[g(m)] \cdot \mathbb{E}_P[p]$

**Proof**: Factor the joint expectation:

$$
\mathbb{E}_P[p \cdot g(m)] = \mathbb{E}_{(m_t, p_t, z_t)}\left[p_t \cdot g(m_t, z_t)\right]
$$

Conditioning on $(a_{t-1}, p_{t-1}, z_{t-1})$ and the Markov transition to $z_t$:

$$
= \mathbb{E}\left[\mathbb{E}\left[p_t g(m_t, z_t) \mid a_{t-1}, p_{t-1}, z_t\right]\right]
$$

Since $p_t = \Phi_{z_t} \psi_t p_{t-1}$ and $m_t = R_{z_t} a_{t-1}/(\Phi_{z_t}\psi_t) + \theta_t$:

$$
= \mathbb{E}\left[p_{t-1} \Phi_{z_t} \sum_s w_s \psi_s g\left(\frac{R_{z_t} a_{t-1}}{\Phi_{z_t}\psi_s} + \theta_s, z_t\right)\right]
$$

Recognizing that $\sum_s w_s \psi_s g(\cdot) = \sum_s q_s g(\cdot) = \mathbb{E}_Q[g(m_t, z_t) \mid a_{t-1}, z_t]$:

$$
= \mathbb{E}\left[p_{t-1} \Phi_{z_t} \cdot \mathbb{E}_Q[g(m_t, z_t) \mid a_{t-1}, z_t]\right]
$$

At the ergodic distribution, if $g$ is independent of $p$ conditional on $m$,
and the neutral measure makes the $m$-distribution stationary:

$$
= \mathbb{E}_P[p] \cdot \mathbb{E}_Q[g(m, z)] \quad \square
$$

---

## Appendix B: Unemployment States and Degenerate Shocks

In HAFiscal, unemployed states have degenerate income distributions:
$\psi = 1$ with probability 1, $\theta = \text{IncUnemp}$ with probability 1.

Under the neutral measure: $q = p \cdot \psi = 1 \cdot 1 = 1$. The
probability is unchanged — degenerate states need no reweighting. This
is correctly handled by checking whether all $\psi$ atoms equal 1.

---

## Appendix C: Splurge Factor

HAFiscal includes a "splurge" factor $\sigma$ where agents consume
$c_{\text{splurge}} = (1-\sigma) c(m,z) p + \sigma \theta p$. Under the
neutral measure:

$$
\mathbb{E}_P[c_{\text{splurge}} \cdot p] = (1-\sigma)\mathbb{E}_Q[c(m,z)] \cdot \mathbb{E}_P[p] + \sigma \mathbb{E}_Q[\theta] \cdot \mathbb{E}_P[p]
$$

The splurge term involves $\theta$ (transitory shock), whose distribution
is unchanged under $Q$. So the formula works: aggregate splurge consumption
is $(1-\sigma)\mathbb{E}_Q[c] \cdot \bar{p} + \sigma \mathbb{E}_Q[\theta] \cdot \bar{p}$.
