# Plan: HAFiscal pLvl normalization mixin

**Date:** April 5, 2026  
**Depends on:** HARK `PermanentIncomeNormalizationMixin` (implemented on `harmenberg-dual-measure`)

---

## Goal

Create a HAFiscal-specific override of `_analytical_log_pLvl_moments` that accounts for:
1. **State-dependent PermGroFac** — employed agents grow at G_emp ≈ 1.005, unemployed at G_unemp = 1.0
2. **Unemployment-adjusted shock variance** — unemployed periods accumulate no permanent shock (BUG-019)
3. **The ergodic unemployment rate** from the TM (not just the calibrated `Urate_normal`)

Then compose it with `AggFiscalType` and `DualAggFiscalType` so the Gatekeeper can test with all three variance-reduction techniques enabled.

---

## What exists in HARK

```python
# HARK/simulation/normalization.py
class PermanentIncomeNormalizationMixin:
    normalize_pLvl = False
    
    def _analytical_log_pLvl_moments(self, age_k):
        """Default: scalar PermGroFac, PermShkDstn variance, eff_periods = max(k-1, 0)."""
        ...
    
    def post_sim_normalize_pLvl(self):
        """Affine rescaling in log-space per age cohort."""
        ...
    
    def sim_one_period(self):
        """super().sim_one_period() then post_sim_normalize_pLvl()."""
        ...
```

The default `_analytical_log_pLvl_moments` uses scalar `PermGroFac[0]` and `PermShkDstn[0]` — correct for `IndShockConsumerType` but not for Markov models with state-dependent growth.

## What exists in HAFiscal

```python
# income_process_sst.py:
effective_pLvl_growth(agent, u)           # → (1-u)*G_emp + u*G_unemp
effective_perm_shock_variance_periods(k, agent, u)  # → (1-u)*k
effective_perm_shock_periods_for_t_age(t_age, agent, u)  # → (1-u)*max(t_age-1, 0)

# tm_methods.py:
_get_perm_shock_var(agent)                # → Var[log ψ] from employed IncShkDstn
```

These already encode the unemployment-adjusted formulas validated to +0.14% accuracy.

---

## Implementation

### New file: `Code/HA-Models/FromPandemicCode/hafiscal_normalization.py`

```python
"""
HAFiscal-specific pLvl normalization mixin.

Overrides _analytical_log_pLvl_moments to account for state-dependent
PermGroFac and unemployment-adjusted shock variance (BUG-019 formula).
"""

import numpy as np
from HARK.simulation.normalization import PermanentIncomeNormalizationMixin
from income_process_sst import effective_pLvl_growth, effective_perm_shock_periods_for_t_age
from tm_methods import _get_perm_shock_var


class HAFiscalNormalizationMixin(PermanentIncomeNormalizationMixin):
    """
    Per-cohort pLvl normalization for HAFiscal's Markov employment model.
    
    Overrides _analytical_log_pLvl_moments to use:
    - effective_pLvl_growth: g = (1-u)*G_emp + u*G_unemp
    - effective_perm_shock_periods_for_t_age: (1-u)*max(t_age-1, 0)
    - _get_perm_shock_var: Var[log ψ] from the employed IncShkDstn
    
    The unemployment rate u defaults to Urate_normal but can be
    overridden by setting _normalization_u_rate (e.g., from the TM
    ergodic u_ergodic).
    """
    
    def _analytical_log_pLvl_moments(self, age_k):
        u = getattr(self, '_normalization_u_rate',
                    getattr(self, 'Urate_normal', 0.0))
        
        g_eff = effective_pLvl_growth(self, u)
        log_g = np.log(g_eff)
        
        sigma_psi_sq = _get_perm_shock_var(self)
        
        eff_periods = float(effective_perm_shock_periods_for_t_age(
            np.array([age_k]), self, u)[0])
        
        pLogInitMean = getattr(self, 'pLogInitMean',
                              getattr(self, 'pLvlInitMean', 0.0))
        pLogInitStd = getattr(self, 'pLogInitStd',
                             getattr(self, 'pLvlInitStd', 0.0))
        
        mu_k = pLogInitMean + age_k * log_g - eff_periods * sigma_psi_sq / 2
        sigma_k = np.sqrt(pLogInitStd**2 + eff_periods * sigma_psi_sq)
        
        return mu_k, sigma_k
```

### Composing with AggFiscalType

In `AggFiscalModel.py` or in the test/simulation setup:

```python
from hafiscal_normalization import HAFiscalNormalizationMixin

class NormalizedAggFiscalType(HAFiscalNormalizationMixin, AggFiscalType):
    pass

class NormalizedDualAggFiscalType(HAFiscalNormalizationMixin, DualAggFiscalType):
    pass
```

MRO ensures `sim_one_period` calls:
1. `PermanentIncomeNormalizationMixin.sim_one_period` (which calls `super().sim_one_period()` then `post_sim_normalize_pLvl()`)
2. `super()` resolves to `DualAggFiscalType.sim_one_period` (or `AggFiscalType.sim_one_period`)

The normalization runs AFTER the standard P-pipeline (and Q-pipeline if dual). For the Q-track, `post_sim_normalize_pLvl` adjusts `state_now['pLvl']` (P-track). A Q-track version would need a separate `post_sim_normalize_pLvl_Q` — defer this to a follow-up since the P-track normalization is the higher-value item.

### Enabling in the Gatekeeper

In `verify_four_methods_agreement.py :: _build_single_type_economy`, when constructing agents:

```python
agent_cls = NormalizedDualAggFiscalType  # instead of DualAggFiscalType
# After construction:
agent.income_shuffle = True
agent.markov_shuffle = True
agent.normalize_pLvl = True
```

Or pass these as parameters to `compare_four_methods` and let it set them.

---

## What changes in existing files

| File | Change |
|------|--------|
| **New:** `hafiscal_normalization.py` | `HAFiscalNormalizationMixin` with SST-based `_analytical_log_pLvl_moments` |
| `AggFiscalModel.py` | Add `NormalizedAggFiscalType` and `NormalizedDualAggFiscalType` class definitions (2 lines each) |
| `verify_four_methods_agreement.py` | Accept `variance_reduction=True` param; use normalized agent class and set shuffle flags |
| `Gatekeeper_Asymptotic_Equality.ipynb` | Add `variance_reduction=True` to `GATEKEEPER_PARAMS` |

---

## Testing

1. **Unit test:** `NormalizedAggFiscalType` with `normalize_pLvl=True`, run 50 periods. For each age cohort: `|mean(log_p) - mu_k| < 1e-10` and `|std(log_p) - sigma_k| < 1e-10`.

2. **Variance reduction test:** Run Gatekeeper at N=20k with and without variance reduction. Verify:
   - AggCons SD drops ~70%
   - E[u'] SD drops ~25%
   - No bias increase (tail means within 0.5%)

3. **Convergence sweep:** N ∈ {5k, 10k, 20k, 40k}. Verify TM-MC gaps shrink faster with variance reduction enabled.

---

## Q-track normalization (deferred)

The P-track normalization adjusts `state_now['pLvl']`. The Q-track has its own `state_now_Q['pLvl']` which evolves under Q dynamics (faster growth). A full solution would:

1. Override `_analytical_log_pLvl_moments` with Q-measure parameters (g_Q, sigma_psi_sq_Q)
2. Add `post_sim_normalize_pLvl_Q` that adjusts `state_now_Q['pLvl']`
3. Call it after the Q-pipeline in `sim_one_period`

This is straightforward but adds complexity. Since the P-track normalization is the high-value item (it's what the paper's results depend on), defer Q-track normalization until the P-track is validated.
