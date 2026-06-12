# Plan: Dual-Measure MC Simulation in HARK

**Date**: 2026-04-02
**Branch**: to be created from `econ-ark/HARK@ConsAggIndMarkovModel`
**Repo**: `/home/shared/github/econ-ark/HARK`
**Goal**: Add paired P/Q (Harmenberg neutral measure) Monte Carlo simulation
to HARK's core agent framework, so a single simulation run produces both
standard (P-measure) and Harmenberg-neutral (Q-measure) results.

---

## Motivation

The Harmenberg (2021) neutral measure provides 3–17× variance reduction
for aggregate consumption in heterogeneous-agent MC simulations by
eliminating permanent-income sampling noise.  Currently, P-MC and Q-MC
must be run as separate simulations (2× cost, unmatched samples).
This plan adds first-class support for running both measures
simultaneously, sharing Markov transitions and mortality draws while
tracking separate (m, pLvl, c) trajectories under each measure.

---

## Architecture Overview

### Current HARK Simulation Pipeline

```
sim_one_period():
  1. get_mortality()          — death/rebirth (shared)
  2. state_prev = state_now   — lag states
  3. get_shocks()             — draw Mrkv, PermShk, TranShk
  4. get_states()→transition()— compute pLvl, mNrm from shocks
  5. get_controls()           — evaluate cFunc(mNrm)
  6. get_poststates()         — compute aNrm = mNrm - cNrm
```

### Proposed Dual-Measure Pipeline

```
sim_one_period():
  1. get_mortality()           — death/rebirth (SHARED between P and Q)
  2. state_prev = state_now    — lag states (P-track)
     state_prev_Q = state_now_Q — lag states (Q-track)
  3. get_shocks()              — draw Mrkv (SHARED), then:
       P-track: PermShk_P, TranShk_P from IncShkDstn
       Q-track: PermShk_Q, TranShk_Q from IncShkDstn_Q
  4. get_states() / transition()
       P-track: pLvl_P, mNrm_P  (standard)
       Q-track: pLvl_Q, mNrm_Q  (parallel, using Q-shocks + Q-lagged aNrm)
  5. get_controls()
       P-track: cNrm_P = cFunc(mNrm_P)
       Q-track: cNrm_Q = cFunc(mNrm_Q)  (same cFunc, different input)
  6. get_poststates()
       P-track: aNrm_P  (standard)
       Q-track: aNrm_Q  (parallel)
```

The consumption function `cFunc` is the same for both measures —
it's determined by the agent's optimization problem, which is
measure-independent.  Only the *simulation dynamics* (shock
magnitudes → state evolution) differ.

---

## What Is Shared vs. Separate

| Component | Shared? | Reason |
|-----------|---------|--------|
| Mrkv transitions | **Yes** | Transition probs are state-dependent, not pLvl-dependent |
| Mortality draws | **Yes** | Death/rebirth rates are pLvl-independent |
| Age tracking | **Yes** | Same agent, same age |
| PermShk magnitude | **No** | Q reweights by ψ/E[ψ], changing which atoms are drawn |
| TranShk magnitude | **No** | Joint (ψ,θ) draw changes; θ marginal same but realizations differ |
| pLvl | **No** | Diverges due to different PermShk histories |
| mNrm, aNrm, cNrm | **No** | Diverges due to different pLvl denominators |
| cFunc | **Yes** | Solution is measure-independent |

### Shock Drawing Strategy

HARK's `DiscreteDistribution.draw_events()` draws uniform random
numbers and maps them to atom indices via CDF inversion:

```python
base_draws = self._rng.uniform(size=N)      # uniform [0,1)
indices = np.cumsum(self.pmv).searchsorted(base_draws)
```

For dual measure, we share the **same base uniform draws** but invert
through **different CDFs**:

```python
# In get_shocks():
base_draws = rng.uniform(size=N)  # draw once

# P-measure: standard CDF
indices_P = np.cumsum(IncShkDstn_P.pmv).searchsorted(base_draws)
PermShk_P = IncShkDstn_P.atoms[0][indices_P] * PermGroFac
TranShk_P = IncShkDstn_P.atoms[1][indices_P]

# Q-measure: Harmenberg-reweighted CDF
indices_Q = np.cumsum(IncShkDstn_Q.pmv).searchsorted(base_draws)
PermShk_Q = IncShkDstn_Q.atoms[0][indices_Q] * PermGroFac
TranShk_Q = IncShkDstn_Q.atoms[1][indices_Q]
```

Since P and Q have the same atoms but different probabilities,
the same uniform draw maps to different (ψ,θ) indices.  This
maximizes correlation between P and Q trajectories: agents who
draw uniforms near the median get similar shocks under both
measures, while agents in the tails diverge.

Note: ψ and θ are independent in HAFiscal's calibration, so the
marginal θ distribution is identical under P and Q.  However,
the *realized* θ for a given agent may differ because different
atom indices are selected.  This is a minor source of P-Q noise
that vanishes as N → ∞.

---

## Implementation Plan

### Phase 0: Branch Setup

1. Create branch `harmenberg-dual-measure` from `ConsAggIndMarkovModel`
   in the HARK repo at `/home/shared/github/econ-ark/HARK`
2. Verify existing tests pass

### Phase 1: Mixin Class (`HARK/dual_measure.py` — new file)

**1.1 `DualMeasureMixin` class**:

```python
class DualMeasureMixin:
    """Mixin that adds Harmenberg neutral-measure (Q) parallel tracking.

    Compose with any IndShockConsumerType subclass:
        class MyDualAgent(DualMeasureMixin, IndShockConsumerType): pass

    When dual_measure=True, sim_one_period() runs the standard P-measure
    pipeline, then a parallel Q-measure state update using Q-shocks
    (same Mrkv/mortality, different PermShk magnitudes).
    """
    dual_measure = False

    def setup_Q_measure(self):
        """Auto-compute IncShkDstn_Q from IncShkDstn via psi/E[psi]."""
        ...
        self.dual_measure = True

    def initialize_sim_Q(self):
        """Allocate Q-state arrays mirroring state_now."""
        self.state_now_Q = {k: np.copy(v) for k, v in self.state_now.items()}
        self.state_prev_Q = {}
        self.shocks_Q = {}
        self.controls_Q = {}
        self.history_Q = {k: np.empty((self.T_sim, self.AgentCount))
                          for k in self.track_vars}

    def sim_one_period(self):
        """Override: run P-pipeline, then Q-pipeline if dual_measure."""
        super().sim_one_period()
        if self.dual_measure:
            self._step_Q_measure()

    def _step_Q_measure(self):
        """Q-measure state evolution for one period."""
        self._lag_Q_states()
        self._draw_Q_shocks()   # reuse base uniforms, Q-CDF
        self._transition_Q()
        self._get_controls_Q()
        self._get_poststates_Q()

    def simulate(self, sim_periods=None):
        """Override: record Q-history alongside P-history."""
        super().simulate(sim_periods)
        # Q-history is recorded inside sim_one_period → _step_Q_measure
```

**1.2 Q-state management**:

- `_lag_Q_states()`: copy `state_now_Q` → `state_prev_Q`
- Death/rebirth: hook into `get_mortality()` to apply same
  `who_dies` mask to Q-states and initialize Q-newborns
- History recording: after each `_step_Q_measure()`, copy
  Q-states into `history_Q[t]`

**1.3 Zero impact on base classes**:

`AgentType`, `IndShockConsumerType`, and `MarkovConsumerType`
are NOT modified.  The mixin overrides `sim_one_period` and
`simulate` via MRO, calling `super()` for the P-pipeline.

### Phase 2: Income Shock Agents (`ConsIndShockModel.py`)

**2.1 `PerfForesightConsumerType` — no Q-measure support**

Permanent income is deterministic, so Harmenberg is not applicable.

**2.2 `IndShockConsumerType`**

**`setup_Q_measure()` (new method)**:

```python
def setup_Q_measure(self):
    """Compute Q-measure IncShkDstn from P-measure IncShkDstn.
    Q reweights employed permanent shock probs by ψ/E[ψ].
    """
    self.IncShkDstn_Q = []
    for period_dstns in self.IncShkDstn:
        Q_dstns = []
        for dstn in period_dstns:
            perm_atoms = dstn.atoms[0]
            E_perm = np.dot(dstn.pmv, perm_atoms)
            if E_perm > 0 and np.std(perm_atoms) > 1e-10:
                Q_pmv = dstn.pmv * perm_atoms / E_perm
                Q_pmv /= Q_pmv.sum()
                Q_dstns.append(DiscreteDistribution(Q_pmv, dstn.atoms))
            else:
                # Degenerate (unemployed) — unchanged
                Q_dstns.append(dstn)
        self.IncShkDstn_Q.append(Q_dstns)
```

**`get_shocks()` override**:

After drawing P-shocks normally, if `dual_measure`, use the
same base uniform draws to draw Q-shocks from `IncShkDstn_Q`.

Implementation detail: save `self._base_draws` during the P-draw,
then reuse for Q-CDF inversion.  This requires a small
refactor of the draw logic to expose the uniform random numbers.

**`_transition_Q()` override**:

```python
def _transition_Q(self):
    pLvl_Q = self.state_prev_Q['pLvl'] * self.shocks_Q['PermShk']
    Rport = self.get_Rport()
    bNrm_Q = Rport * self.state_prev_Q['aNrm'] / pLvl_Q
    mNrm_Q = bNrm_Q + self.shocks_Q['TranShk']
    self.state_now_Q['pLvl'] = pLvl_Q
    self.state_now_Q['mNrm'] = mNrm_Q
```

**`_get_controls_Q()` override**:

```python
def _get_controls_Q(self):
    # Same cFunc, different mNrm input
    cNrm_Q = self.solution[t].cFunc(self.state_now_Q['mNrm'])
    self.controls_Q['cNrm'] = cNrm_Q
```

**`_get_poststates_Q()` override**:

```python
def _get_poststates_Q(self):
    self.state_now_Q['aNrm'] = self.state_now_Q['mNrm'] - self.controls_Q['cNrm']
```

### Phase 3: Markov Agents (follow-up PR)

**3.1 `DualMeasureMarkovMixin`** (or extend `DualMeasureMixin`):

```python
class DualMeasureMarkov(DualMeasureMixin, MarkovConsumerType):
    pass
```

**`_draw_Q_shocks()` override**:

- `get_markov_states()` already called in P-pipeline (shared Mrkv)
- Q-shocks drawn from `IncShkDstn_Q[t][Mrkv]` using same base uniforms
- Both tracks use the same `Mrkv` state for indexing

**`_get_controls_Q()` override**:

```python
# Index cFunc by shared Mrkv state, evaluate at Q-mNrm
cNrm_Q = solution[t].cFunc[Mrkv_j](state_now_Q['mNrm'])
```

This phase is deferred to a second PR to keep the first PR small.

### Phase 4: Death/Rebirth Synchronization

When an agent dies and is reborn:
- P-measure: newborn gets fresh `pLvl_init`, `aNrm = 0`, etc.
- Q-measure: newborn gets the SAME `aNrm = 0` (normalized) but
  the pLvl_Q should start from the same initial draw as pLvl_P.

In `get_mortality()`, when `dual_measure`:
- Apply the same `who_dies` mask to Q-states
- Copy the same newborn `pLvl_init` to both `state_now` and `state_now_Q`
- Copy the same newborn `aNrm` and `Mrkv` to both tracks

### Phase 5: Aggregation Utilities

**5.1 `compute_pLvl_factor()` (new utility function)**

```python
def compute_pLvl_factor(agent, macro_path, act_T):
    """Compute analytical pLvl_factor(t) from the AR(1) recurrence.
    See math-derive-harm §15.
    """
    G = agent.PermGroFac[0][0]
    # ... (delta_eff, g_base_pLvl from agent params)
    F = np.ones(act_T)
    for t in range(1, act_T):
        u_t = ...  # from macro_path or agent history
        g_rec = (1 - u_t) * G + u_t
        F[t] = (1 - delta) * g_rec * F[t-1] + (1 - (1 - delta) * g_base)
    return F
```

**5.2 `aggregate_Q()` (new utility function)**

```python
def aggregate_Q(agent, E_pLvl, pLvl_factor):
    """Compute Q-measure aggregate consumption from history_Q.
    C(t) = E_pLvl * F(t) * sum_i f_Q(m_i(t))
    where f_Q = cLvl_splurge / pLvl_Q
    """
    ...
```

**5.3 Stimulus check with Q-MC**

For non-p-linear policies (e.g. means-tested transfers), the
dual-measure framework enables a hybrid:
- Use P-measure `pLvl_P` for the means-test / phase-out calculation
- Use Q-measure `mNrm_Q` for the consumption function evaluation
- Aggregate using pLvl_factor × f_Q with the correct check amount

This is possible because both P and Q tracks are available
simultaneously for each agent.

---

## API Design

### User-Facing API

```python
agent = IndShockConsumerType(**params)
agent.solve()

# Enable dual measure
agent.dual_measure = True
agent.setup_Q_measure()  # computes IncShkDstn_Q from IncShkDstn

# Simulate — both measures computed in one pass
agent.initialize_sim()
agent.simulate()

# Access results
P_consumption = agent.history['cNrm']   # standard P-measure
Q_consumption = agent.history_Q['cNrm'] # Harmenberg Q-measure
P_pLvl = agent.history['pLvl']
Q_pLvl = agent.history_Q['pLvl']

# Q-aggregate consumption (scalar pLvl_factor approach)
E_pLvl = compute_analytical_mean_pLvl(agent)
pLvl_factor = compute_pLvl_factor(agent, macro_path)
C_Q = E_pLvl * pLvl_factor * np.sum(Q_consumption / Q_pLvl, axis=1)
```

### Backward Compatibility

- `dual_measure = False` by default → zero behavioral change
- No new required arguments to any existing method
- `history` dict unchanged; `history_Q` is additive
- Existing tests must continue to pass unmodified

---

## Performance Considerations

| Metric | Current (2 separate runs) | Dual-measure (1 run) |
|--------|--------------------------|---------------------|
| Shock draws | 2N draws | N draws + N CDF inversions |
| State updates | 2 × (pLvl, mNrm, cNrm, aNrm) | 2 × (pLvl, mNrm, cNrm, aNrm) |
| cFunc evaluations | 2N | 2N |
| Memory | 2 × full agent copies | 1 agent + Q-state arrays |
| Mrkv draws | 2N | N |
| deepcopy cost | full economy copy | none |

**Net speedup**: ~1.5–1.8× (most time is in cFunc evaluation,
which must happen twice regardless; savings come from eliminating
deepcopy, redundant Mrkv draws, and reduced memory pressure).

The main memory overhead is the Q-state arrays (4 arrays ×
N_agents × float64 ≈ 6 MB per 200K agents — negligible).

---

## Testing Strategy

### Unit Tests

1. **Q = P when PermShk is degenerate**: If σ_ψ = 0, then
   `IncShkDstn_Q = IncShkDstn_P`, and `history_Q` should
   match `history` exactly.

2. **Q-ergodic mean matches TM**: After long burn-in, the MC
   sample mean `(1/N) Σ f(m_Q_i)` should match the TM Q-ergodic
   `Σ_k c(m_k) π_Q(m_k)` to within sampling error.

3. **Shared Mrkv**: Verify that `history['Mrkv']` and
   `history_Q['Mrkv']` are identical arrays.

4. **Shared mortality**: Verify same agents die at same times
   in both tracks.

5. **pLvl divergence**: After many periods, `Var(pLvl_Q)` should
   be smaller than `Var(pLvl_P)` (Q concentrates the distribution).

### Integration Tests (HAFiscal)

6. **Differenced policy effects**: Q-MC UI extension and Tax cut
   NPVs match P-MC within 2% (same as current separate-run results).

7. **Stimulus check hybrid**: Using P-pLvl for phase-out with
   Q-mNrm for consumption, check NPV matches P-MC within 5%.

8. **Variance reduction**: Q-MC SE / P-MC SE < 0.5 for raw
   experiment NPVs.

---

## File Change Summary

### PR 1: IndShockConsumerType dual-measure

| File | Changes |
|------|---------|
| `HARK/dual_measure.py` (new) | `DualMeasureMixin` class with all Q-state management, `setup_Q_measure()`, `_step_Q_measure()`, `_transition_Q`, `_get_controls_Q`, `_get_poststates_Q`, Q-history recording |
| `HARK/ConsumptionSaving/ConsIndShockModel.py` | Small refactor of `get_shocks()` to expose base uniform draws (store as `self._base_shock_draws`) so the mixin can reuse them for Q-CDF inversion |
| `HARK/utilities.py` | Add `make_Q_measure_dstn()` utility |
| `tests/test_dual_measure.py` (new) | Unit tests for dual-measure simulation |

### PR 2: MarkovConsumerType dual-measure (follow-up)

| File | Changes |
|------|---------|
| `HARK/dual_measure.py` | Extend mixin or add `DualMeasureMarkovMixin` for Mrkv-indexed cFunc and shared Mrkv draws |
| `HARK/ConsumptionSaving/ConsMarkovModel.py` | Small refactor of `get_shocks()` to expose base draws per Mrkv state |
| `HARK/dual_measure_agg.py` (new) | `compute_pLvl_factor()`, `aggregate_Q()` utilities for aggregate consumption |
| `tests/test_dual_measure_markov.py` (new) | Markov-specific tests |

---

## Phased Delivery

### PR 1: IndShockConsumerType dual-measure

| Phase | Scope | Est. effort |
|-------|-------|-------------|
| 0 | Branch from `ConsAggIndMarkovModel`, verify tests | 0.5 day |
| 1 | `DualMeasureMixin` core (Q-state mgmt, history, death/rebirth sync) | 1.5 days |
| 2 | IndShock-specific Q-methods (shocks, transition, controls, poststates) | 1 day |
| 3 | Refactor `IndShockConsumerType.get_shocks()` to expose base uniforms | 0.5 day |
| 4 | Unit tests | 1 day |
| **PR 1 total** | | **~4.5 days** |

### PR 2: MarkovConsumerType dual-measure + HAFiscal integration

| Phase | Scope | Est. effort |
|-------|-------|-------------|
| 5 | Markov Q-methods (Mrkv-indexed cFunc, shared Mrkv draws) | 1 day |
| 6 | Aggregation utilities (pLvl_factor, aggregate_Q) | 0.5 day |
| 7 | HAFiscal integration (replace two-run approach) | 1 day |
| 8 | Integration tests | 0.5 day |
| **PR 2 total** | | **~3 days** |

| **Grand total** | | **~7.5 days** |

---

## Design Decisions (Resolved)

1. **`IncShkDstn_Q` computation**: Auto-compute only via
   `setup_Q_measure()` using the standard ψ/E[ψ] reweighting.
   No user-supplied override — keeps the API simple and covers
   all known use cases.

2. **Naming convention**: `history_Q`, `state_now_Q`, `shocks_Q`,
   `controls_Q` — concise, matches the mathematical P/Q notation.

3. **Architecture**: **Mixin class** (`DualMeasureMixin`) that can
   be composed with any agent type.  Usage:
   ```python
   class DualMeasureIndShock(DualMeasureMixin, IndShockConsumerType):
       pass
   ```
   This keeps the base classes clean and avoids adding complexity to
   `AgentType`.  The mixin provides `_step_Q_measure()`,
   `setup_Q_measure()`, Q-state management, and Q-history recording.
   Subclass-specific methods (`_transition_Q`, `_get_controls_Q`,
   `_get_poststates_Q`) are defined on the mixin with implementations
   appropriate for each consumption model.

4. **Scope of initial PR**: `IndShockConsumerType` only (Phase 1–2).
   `MarkovConsumerType` follows in a second PR (Phase 3).
   This keeps the first PR small and reviewable.

5. **Branch base**: `ConsAggIndMarkovModel` — what HAFiscal depends
   on today.  Minimizes integration friction.

6. **`read_shocks` / `shock_history`**: The existing mechanism should
   be extended to store both P and Q shock histories when
   `dual_measure=True`.  This is a Phase 2 concern.
