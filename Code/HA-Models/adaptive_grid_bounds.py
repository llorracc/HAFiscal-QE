"""adaptive_grid_bounds.py — optional single global aNrm grid from MC support.

NOTE (2026-06-09, BUG-053): SUPERSEDED for the production aMax by the TM-ergodic
adaptive_grid_tm.production_aMax() (college GIC-cap-atom (1-1e-4) ergodic quantile
-> aMax=1300, the HAFISCAL_TM_AMAX canonical default); kept as the optional
MC-support workflow.

An OPTIONAL extra step off the gridpoint-distribution workflow (the MC simulations
that produce aNrm panels). Generalizes the earlier one-sided college-max boundary to
a TWO-SIDED, single grid shared across ALL cohorts and education groups:

    aNrmMin = lowest aNrm in the MOST IMPATIENT cohort's MC  (lowest beta, ALL groups)
    aNrmMax = highest aNrm in the MOST PATIENT COLLEGE cohort's MC (highest beta college)
    aNrmMin_below = aNrmMin / 10        (below_factor=10)
    aNrmMax_above = aNrmMax * 2         (above_factor=2)
    single grid   = [aNrmMin_below, aNrmMax_above]  for EVERY cohort/group

Cohorts (as of the pre-BUG-053 CDC calibration, Results/DiscFacEstim_CRRA_2.0_R_1.01.txt,
2026-06-08):
    most impatient = Dropout, atom d=0, beta = 0.317   -> aNrmMin
    most patient   = College, atom d=6, beta = 1.016   -> aNrmMax  (~867 observed)
Under the current production calibration (ESC TM-a, BUG-053 re-estimation 2026-06-09:
D beta=0.7384/nabla=0.3037, C beta=0.9920/nabla=0.0233) the extremes are Dropout atom
d=0 beta~0.478 and the College top atom GIC-capped at beta~1.0054 (GPF=theGICfactor=0.9995).

Why a single shared grid (not per-cohort): the grid must COVER the most-patient
agents or the upper edge truncates (the legacy aMax=500 default — pre-2026-06-09;
the canonical production default is now HAFISCAL_TM_AMAX=1300, see EstimParameters.py —
already truncated the college most-patient at aNrm~867); one shared grid keeps the cross-cohort welfare
aggregation consistent. The impatient cohorts' near-0 resolution comes from the
exp-spacing (dense near 0) plus aCount. The aMin/10 keeps the lower edge just below
the lowest observed aNrm (it lands ~0 when the impatient cohort has constrained or
newborn agents at aNrm~=0 -- the procedure handles either case).

WORKFLOW (the optional extra step)
  1. Run the two extreme cohorts' MC (the gridpoint-distribution step):
       # most impatient (Dropout only, via per-cohort agent-count override):
       HAFISCAL_AGENTCOUNT_D=10000 HAFISCAL_AGENTCOUNT_H=0 HAFISCAL_AGENTCOUNT_C=0 \
         python FromPandemicCode/welfare6_scenario.py --scenario base \
         --parametrization Baseline --out-dir Results/tmp/impatientmin
         # repeat --scenario recession and recessionCheck
       # most patient college:
       python FromPandemicCode/welfare6_scenario.py --scenario base \
         --parametrization College_Only --out-dir Results/tmp/collegemax
         # repeat --scenario recession and recessionCheck
  2. Compute the single global grid (this module):
       python adaptive_grid_bounds.py \
         --impatient-dir Results/tmp/impatientmin --college-dir Results/tmp/collegemax
  3. Export the printed bounds and run the TM solve; build_tm_agg_fiscal_a reads
     HAFISCAL_TM_AMIN / HAFISCAL_TM_AMAX and uses the SAME grid for every cohort/group:
       export HAFISCAL_TM_AMIN=<aNrmMin/10>  HAFISCAL_TM_AMAX=<aNrmMax*2>
"""
import os
import pickle

import numpy as np


def _panel_minmax(panel_dir, scenarios=("base", "recession", "recessionCheck")):
    """(min, max, scenarios_found) of aNrm over the scenario panels in panel_dir."""
    lo, hi, found = np.inf, -np.inf, []
    for s in scenarios:
        p = os.path.join(panel_dir, f"{s}.pkl")
        if not os.path.exists(p):
            continue
        with open(p, "rb") as f:
            d = pickle.load(f)
        aN = np.asarray(d["aNrm_all_bs"])
        lo = min(lo, float(aN.min()))
        hi = max(hi, float(aN.max()))
        found.append(s)
    if not found:
        raise FileNotFoundError(f"no scenario panels ({scenarios}) in {panel_dir}")
    return lo, hi, found


def global_aNrm_bounds(impatient_min, patient_college_max,
                       below_factor=10.0, above_factor=2.0):
    """The single global grid bounds.

    aNrmMin_below = aNrmMin / below_factor ; aNrmMax_above = aNrmMax * above_factor.
    """
    return impatient_min / below_factor, patient_college_max * above_factor


def bounds_from_dirs(impatient_dir, college_dir,
                     scenarios=("base", "recession", "recessionCheck"),
                     below_factor=10.0, above_factor=2.0):
    """Optional extra step: single global [aMin, aMax] from the two extreme cohorts'
    MC panels. impatient_dir = most-impatient (Dropout) MC; college_dir = most-patient
    college MC."""
    imin, imax, ifound = _panel_minmax(impatient_dir, scenarios)
    cmin, cmax, cfound = _panel_minmax(college_dir, scenarios)
    a_min, a_max = global_aNrm_bounds(imin, cmax, below_factor, above_factor)
    return {
        "aNrmMin": imin, "aNrmMax": cmax,
        "aMin": a_min, "aMax": a_max,
        "below_factor": below_factor, "above_factor": above_factor,
        "impatient_scenarios": ifound, "college_scenarios": cfound,
        "impatient_max_seen": imax, "college_min_seen": cmin,
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="Single global aNrm grid from the MC support of the two extreme cohorts.")
    ap.add_argument("--impatient-dir", default="Results/tmp/impatientmin",
                    help="MC panel dir for the most-impatient (Dropout) cohort")
    ap.add_argument("--college-dir", default="Results/tmp/collegemax",
                    help="MC panel dir for the most-patient college cohort")
    ap.add_argument("--below-factor", type=float, default=10.0)
    ap.add_argument("--above-factor", type=float, default=2.0)
    a = ap.parse_args()
    r = bounds_from_dirs(a.impatient_dir, a.college_dir,
                         below_factor=a.below_factor, above_factor=a.above_factor)
    print(f"aNrmMin (most impatient, {'+'.join(r['impatient_scenarios'])}) = {r['aNrmMin']:.6g}")
    print(f"aNrmMax (most patient college, {'+'.join(r['college_scenarios'])}) = {r['aNrmMax']:.6g}")
    print(f"single global grid: [{r['aMin']:.6g}, {r['aMax']:.6g}]"
          f"  (aNrmMin/{r['below_factor']:.0f}, aNrmMax*{r['above_factor']:.0f})")
    print("\n# export for the TM solve (SAME grid, all cohorts/groups):")
    print(f"export HAFISCAL_TM_AMIN={r['aMin']:.6g} HAFISCAL_TM_AMAX={r['aMax']:.6g}")
