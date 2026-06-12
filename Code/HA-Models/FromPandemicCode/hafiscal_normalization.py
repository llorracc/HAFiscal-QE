"""
HAFiscal-specific pLvl normalization mixin.

Provides mean-only per-period log(pLvl) normalization for HAFiscal's
Markov employment model, in which each agent's permanent-income growth
factor depends on the realized Markov state (employed vs various
unemployment states).

Why a HAFiscal-specific override is required
--------------------------------------------
HARK's upstream ``PermanentIncomeNormalizationMixin`` assumes a
non-Markov model where every agent grows by the same scalar
``PermGroFac[0]`` each period. For Markov agents, ``self.PermGroFac[0]``
is a *vector* of growth factors (one per Markov state), so the
upstream's

    log_G = np.log(self.PermGroFac[0])
    mu_k  = self.pLogInitMean + age_k * log_G - eff_periods * sigma_psi_sq / 2

makes ``mu_k`` a vector and the subsequent ``log_p[mask] = mu_k``
assignment fails with a shape mismatch.

Two HAFiscal-specific corrections are needed:

1. **Mean (mu_k):** use the SST population-weighted growth
   ``g_eff = (1-u) * G_emp + u * G_unemp`` instead of the per-state
   PermGroFac vector. This is the long-run (Lyapunov) mean log-growth
   for an agent moving on the Markov chain at stationary distribution.

2. **Variance (sigma_k):** the upstream formula
   ``sigma_k = sqrt(pLogInitStd^2 + eff_periods * sigma_psi_sq)``
   counts only the permanent-shock variance and IGNORES the
   cross-sectional variance from heterogeneous Markov paths
   (employed vs unemployed histories produce different pLvl trajectories).
   For HAFiscal Markov agents this would underestimate the analytical
   variance and the mixin would rescale the cross-section to a value
   that is too small. Distorting the wealth heterogeneity could change
   policy responses in ways that defeat the purpose of variance
   reduction.

Decision: do MEAN-ONLY normalization. Shift each age cohort's log-pLvl
distribution so its cross-sectional mean matches the analytical Markov
mean, while leaving the cross-sectional spread unchanged. This fixes
the level drift identified in
``runs/phase_a2_baseline_drift_findings.md`` (TM produces a constant
194,557 baseline; MC drifts upward to ~204,000) without distorting
the variance.

Usage::

    from hafiscal_normalization import HAFiscalNormalizationMixin
    from AggFiscalModel import AggFiscalType, DualAggFiscalType

    class NormalizedAggFiscalType(HAFiscalNormalizationMixin, AggFiscalType):
        pass

    class NormalizedDualAggFiscalType(HAFiscalNormalizationMixin, DualAggFiscalType):
        pass

    agent = NormalizedDualAggFiscalType(normalize_pLvl=True, ...)
"""

import numpy as np

from HARK.simulation.normalization import PermanentIncomeNormalizationMixin
from income_process_sst import effective_pLvl_growth


class HAFiscalNormalizationMixin(PermanentIncomeNormalizationMixin):
    """Mean-only per-period log(pLvl) normalization for HAFiscal Markov agents.

    Overrides:

    * ``_get_effective_PermGroFac`` — returns the SST population-weighted
      scalar growth ``(1-u) * G_emp + u * G_unemp``.

    * ``post_sim_normalize_pLvl`` — replaces the upstream mean+variance
      rescaling with a mean-only shift. For each age-k cohort with at
      least ``HAFISCAL_NORM_MIN_NK`` agents (default 5), shifts
      ``log(pLvl)`` so the cohort cross-sectional mean matches
      ``mu_k = pLogInitMean + age_k * log(g_eff)``. The cohort spread
      is preserved.
    """

    def _get_effective_PermGroFac(self):
        u = getattr(self, '_normalization_u_rate',
                    getattr(self, 'Urate_normal', 0.0))
        return float(effective_pLvl_growth(self, u))

    def _hafiscal_target_E_pLvl(self):
        """Target population mean of pLvl, taken from TM's analytical
        ergodic computation in tm_methods.compute_analytical_mean_pLvl.

        This is the most reliable target source: rather than re-deriving
        the Markov-aware mean log(pLvl) inline (which is brittle to get
        right for the Jensen / state-variance interactions), we use the
        same function TM itself uses to compute E[pLvl] under the
        stationary cross-section. By construction, normalizing MC's
        empirical E[pLvl] to this target makes MC's aggregate income
        match TM's analytical baseline.

        Cached on the agent as ``_hafiscal_target_E_pLvl_cached`` so the
        TM function is only called once per agent.
        """
        cached = getattr(self, '_hafiscal_target_E_pLvl_cached', None)
        if cached is not None:
            return cached
        try:
            from tm_methods import compute_analytical_mean_pLvl
            u = getattr(self, '_normalization_u_rate',
                        getattr(self, 'Urate_normal', 0.0))
            target = float(compute_analytical_mean_pLvl(self, unemployment_rate=u))
        except Exception:
            target = None
        self._hafiscal_target_E_pLvl_cached = target
        return target

    def post_sim_normalize_pLvl(self):
        """Direct empirical retargeting of pLvl to TM's analytical mean.

        Approach: at the start of each simulated period, compute the
        empirical population mean of pLvl. Compare to the analytical
        target from ``tm_methods.compute_analytical_mean_pLvl``
        (cached). Shift every agent's ``log(pLvl)`` by the constant
        ``log(target) - log(empirical)``, which makes the new empirical
        mean exactly equal to the target.

        Why a uniform shift rather than per-cohort: the right per-cohort
        analytical mean for HAFiscal Markov agents would require a
        Markov-aware derivation that interacts with the state transition
        matrix and per-state shock variance. A uniform shift uses TM's
        already-correct analytical aggregate as the source of truth and
        sidesteps the entire derivation, at the cost of leaving the
        within-cohort age distribution of pLvl unchanged. For
        aggregate-level outputs (which is what the multipliers care
        about) this is the right trade.

        Adjusts ``mNrm`` and ``bNrm`` to preserve the underlying levels
        ``mLvl = mNrm * pLvl`` and ``bLvl = bNrm * pLvl`` after the pLvl
        update.

        Skipped if ``self.normalize_pLvl`` is False or the target is
        unavailable.
        """
        if not getattr(self, "normalize_pLvl", False):
            return

        target_E_pLvl = self._hafiscal_target_E_pLvl()
        if target_E_pLvl is None or target_E_pLvl <= 0:
            return

        pLvl = np.asarray(self.state_now["pLvl"])
        empirical_E_pLvl = float(np.mean(np.maximum(pLvl, 1e-16)))
        if empirical_E_pLvl <= 0:
            return

        # Single uniform multiplicative correction in level space
        # (equivalent to a uniform additive shift in log space).
        scale = target_E_pLvl / empirical_E_pLvl
        if not np.isfinite(scale) or scale <= 0:
            return

        pLvl_old = pLvl.copy()
        self.state_now["pLvl"][:] = pLvl * scale

        # Preserve mLvl and bLvl: varLvl = varNrm * pLvl, so varNrm
        # must scale by the inverse ratio of new pLvl to old pLvl.
        inv_ratio = pLvl_old / np.maximum(self.state_now["pLvl"], 1e-16)
        for var in ("mNrm", "bNrm"):
            if var in self.state_now and isinstance(self.state_now[var], np.ndarray):
                self.state_now[var] *= inv_ratio
