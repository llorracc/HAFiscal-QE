#!/usr/bin/env python
"""a-indexed Step-2 (β/∇) estimation — splurge-in-budget / BUG-033 consistent analogue of estim_phase2_tm.py.

Under splurge-in-budget the budget identity is a_t = m_t - c_actual(m_t, xi_t) with
c_actual = (1-varsigma) * cFunc(m_t) + varsigma * xi_t. The m-indexed TM
collapses the ξ-variance (BUG-033); the a-indexed TM preserves it. For
full consistency with Phase 5 (a-indexed baseline production), Step 2
β/∇ should be re-estimated under the same a-indexed convention.

This script is a minimal edit of estim_phase2_tm.py:
  - build_tm_agg_fiscal → build_tm_agg_fiscal_a
  - no (1-Splurge) * aPol adjustment — the a-grid already holds post-
    consumption assets under splurge-in-budget accounting.
  - output to _TM_a.txt

Usage:
    cd Code/HA-Models/FromPandemicCode
    python estim_phase2_tm_a.py                    # all 3 edTypes
    HAFISCAL_EDTYPES=1,2 python estim_phase2_tm_a.py  # subset
"""

import os, sys, time
import numpy as np
from copy import deepcopy
from HARK.distributions import Uniform
from HARK.utilities import get_percentiles, get_lorenz_shares
from HARK.estimation import minimize_nelder_mead

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import EstimParameters as ep
from EstimParameters import (
    init_dropout, init_highschool, init_college, init_ADEconomy, DiscFacDstns,
    DiscFacCount, CRRA, AgentCountTotal, Rfree_base,
    data_LorenzPts, data_medianLWPI, data_EducShares,
    GICmaxBetas, gic_capped_beta, minBeta,
)
from AggFiscalModel import AggFiscalType, AggregateDemandEconomy
from HARK.distributions import DiscreteDistribution
from tm_methods import build_tm_agg_fiscal_a, find_ergodic_distribution

# BUG-051 matched-pair guard: this is a guarded TM-a entry point — require the
# interpretation (CDC vs ESC) to be set EXPLICITLY rather than silently
# defaulting to CDC. Runs at module import, after env + sys.path setup and
# before the heavy economy build below. (importing tm_methods above already
# put the HA-Models dir on sys.path, so _interpretation resolves here.)
# Note: mc_tm_dist_eval.py imports this module with HAFISCAL_EDTYPES='' but it
# always sets HAFISCAL_INTERPRETATION first, so the require check passes there.
from _interpretation import get_interpretation as _get_interp_require
_get_interp_require(require=True)

Splurge = ep.Splurge
UBspell_normal = ep.UBspell_normal
num_types = 3

print(f"a-indexed TM Phase 2 estimation (splurge-in-budget consistent)")
print(f"Splurge={Splurge:.6f}  CRRA={CRRA}  Rfree={Rfree_base[0]}  DiscFacCount={DiscFacCount}")
print(f"AgentCountTotal={AgentCountTotal} (used for agent weighting, not simulation)")

# ---- Build economy (same as estim_phase2_tm.py) ----
t0_setup = time.time()
InfHorizonTypeAgg_d = AggFiscalType(**init_dropout)
InfHorizonTypeAgg_d.cycles = 0
InfHorizonTypeAgg_h = AggFiscalType(**init_highschool)
InfHorizonTypeAgg_h.cycles = 0
InfHorizonTypeAgg_c = AggFiscalType(**init_college)
InfHorizonTypeAgg_c.cycles = 0
AggDemandEcon = AggregateDemandEconomy(**init_ADEconomy)
InfHorizonTypeAgg_d.get_economy_data(AggDemandEcon)
InfHorizonTypeAgg_h.get_economy_data(AggDemandEcon)
InfHorizonTypeAgg_c.get_economy_data(AggDemandEcon)
BaseTypeList = [InfHorizonTypeAgg_d, InfHorizonTypeAgg_h, InfHorizonTypeAgg_c]

IncomeDstn_unemp = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([InfHorizonTypeAgg_d.IncUnemp])])
IncomeDstn_unemp_nobenefits = DiscreteDistribution(
    np.array([1.0]), [np.array([1.0]), np.array([InfHorizonTypeAgg_d.IncUnempNoBenefits])])

for ThisType in BaseTypeList:
    ThisType.IncShkDstn = [[ThisType.IncShkDstn[0]] + [IncomeDstn_unemp]*UBspell_normal + [IncomeDstn_unemp_nobenefits]]
    ThisType.IncShkDstn_base = ThisType.IncShkDstn

TypeList = []
n = 0
for e in range(num_types):
    for b in range(DiscFacCount):
        DiscFac = DiscFacDstns[e].atoms[0][b]
        AgentCount = int(np.floor(AgentCountTotal * data_EducShares[e] * DiscFacDstns[e].pmv[b]))
        ThisType = deepcopy(BaseTypeList[e])
        ThisType.AgentCount = AgentCount
        ThisType.DiscFac = DiscFac
        ThisType.seed = n
        TypeList.append(ThisType)
        n += 1

AggDemandEcon.agents = TypeList
AggDemandEcon.solve()
print(f"Economy setup + initial solve: {time.time()-t0_setup:.1f}s")


# ---- a-indexed TM objective function ----

def betas_obj_func_educ_tm_a(beta, spread, GICx, educ_type=2, print_mode=False):
    """a-indexed TM objective: same targets as m-indexed betas_obj_func_educ_tm
    but preserves ξ-variance in the wealth distribution (BUG-033 fix)."""
    dfs = Uniform(beta - spread, beta + spread).discretize(DiscFacCount)
    for thedf in range(DiscFacCount):
        if dfs.atoms[0][thedf] > gic_capped_beta(educ_type, np.exp(GICx) / (1 + np.exp(GICx))):
            dfs.atoms[0][thedf] = gic_capped_beta(educ_type, np.exp(GICx) / (1 + np.exp(GICx)))
        elif dfs.atoms[0][thedf] < minBeta:
            dfs.atoms[0][thedf] = minBeta

    TypeListNewEduc = []
    for b_idx in range(DiscFacCount):
        AgentCount = int(np.floor(AgentCountTotal * data_EducShares[educ_type] * dfs.pmv[b_idx]))
        ThisType = deepcopy(BaseTypeList[educ_type])
        ThisType.AgentCount = AgentCount
        ThisType.DiscFac = dfs.atoms[0][b_idx]
        TypeListNewEduc.append(ThisType)

    TypeListAll = AggDemandEcon.agents
    TypeListAll[educ_type * DiscFacCount:(educ_type + 1) * DiscFacCount] = TypeListNewEduc
    AggDemandEcon.agents = TypeListAll
    AggDemandEcon.solve()

    # Build a-indexed TM + ergodic for this edType's 7 agents
    total_weight = sum(t.AgentCount for t in TypeListNewEduc)
    a_vals_list = []
    w_vals_list = []

    # Interpretation single source (CDC vs ESC): drives BOTH the TM kernel asset
    # rule (passed to build_tm_agg_fiscal_a) and the (1-ς) household correction
    # below. Read from get_interpretation() so the TM-a kernel is always matched
    # to the agent/calibration regime, never a stale hardcoded 'CDC'. BUG-051.
    _tm_interp = get_interpretation()

    for agent in TypeListNewEduc:
        agent_w = agent.AgentCount / total_weight if total_weight > 0 else 1.0 / DiscFacCount
        # aCount=200 (was 100) per tm_methods.py:4434 comment: aCount=100 produces
        # ~30% K/Y bias from upper-grid tail truncation when β·Rfree is near GIC
        # (which is exactly the high-β atoms in our distributions). aCount=200
        # drops the bias to <0.1% and is the new default for build_tm_agg_fiscal_a.
        # This was the source of the apparent "TM-a vs MC methodology gap" on
        # HS medianLWPI (-30.8% in the 2026-05-03 ESC TM-a run); not a
        # normalized-vs-level issue but a grid-resolution issue.
        # aCount=200 is the production grid (see comment above). interpretation
        # from the single source (BUG-051) so the TM-a kernel matches the
        # agent/calibration regime.
        # HAFISCAL_TM_ACOUNT (2026-06-10): distribution-grid override. The dist grid is ~1% of
        # the per-eval cost (the 7 solves dominate and are aCount-independent), and the pooled
        # group MEDIAN — a calibration target — carries a ~1.5% quantization bias at aCount=200
        # that converges by ~1600 (jitter 1.49% -> 0.06% vs an N=6400 reference; driven by the
        # two GIC-cap atoms' fat tails). Finer dist grid = nearly-free accuracy on the median
        # target; Lorenz targets are grid-robust either way.
        _tm_aCount = int(os.environ.get('HAFISCAL_TM_ACOUNT', '200'))
        tm_data = build_tm_agg_fiscal_a(agent, aCount=_tm_aCount, interpretation=_tm_interp)
        ergodic = find_ergodic_distribution(tm_data['TranMatrix'])

        dist_aGrid = tm_data['dist_aGrid']
        J = agent.MrkvArray[0].shape[0]
        A = len(dist_aGrid)

        # Ergodic layout per build_tm_agg_fiscal_a docstring:
        # [j=0, a=0..A-1, j=1, a=0..A-1, ...] — reshape to (J, A).
        erg = np.asarray(ergodic).reshape(J, A)

        for j in range(J):
            dstn_j = erg[j, :]
            mask = dstn_j > 1e-15
            if np.any(mask):
                # dist_aGrid holds the kernel asset state: under CDC this IS the
                # household a_tot; under ESC it is the per-Optimizer a_opt, and the
                # household correction a_tot = (1-ς)·a_opt is applied to a_array
                # after the loop (eq:conv1-ESC; tm_methods.py:4898). BUG-051.
                aNrm_vals = dist_aGrid[mask]
                weights = dstn_j[mask] * agent_w
                a_vals_list.append(aNrm_vals)
                w_vals_list.append(weights)

    a_array = np.concatenate(a_vals_list)
    w_array = np.concatenate(w_vals_list)
    w_array /= np.sum(w_array)

    # ESC household correction (eq:conv1-ESC; tm_methods.py:4898): the kernel grid
    # is the per-Optimizer a_opt; household liquid wealth a_tot = (1-ς)·a_opt. (CDC's
    # grid is already a_tot.) Scales medianLWPI by (1-ς); leaves the scale-invariant
    # Lorenz shares unchanged. Omitting it overstates ESC LW/PI by 1/(1-ς) — the
    # spurious 21-62% "MC-vs-TM gap" diagnosed 2026-06-05 (BUG-051).
    if _tm_interp == 'ESC':
        a_array = a_array * (1.0 - Splurge)

    medianLWPI = 100.0 * get_percentiles(a_array, weights=w_array, percentiles=[0.5])
    LorenzPts = 100.0 * get_lorenz_shares(a_array, weights=w_array,
                                           percentiles=[0.2, 0.4, 0.6, 0.8])

    sumSquares = np.sum((medianLWPI - data_medianLWPI[educ_type]) ** 2)
    sumSquares += np.sum((np.array(LorenzPts) - data_LorenzPts[educ_type]) ** 2)
    distance = np.sqrt(sumSquares)

    if print_mode:
        print(f"  beta={beta:.4f} nabla={spread:.4f} GICx={GICx:.4f}")
        print(f"  medianLWPI: model={medianLWPI[0]:.2f}  data={data_medianLWPI[educ_type]:.2f}")
        print(f"  Lorenz: model=[{', '.join(f'{x:.2f}' for x in LorenzPts)}]  "
              f"data=[{', '.join(f'{x:.2f}' for x in data_LorenzPts[educ_type])}]")
        print(f"  distance={distance:.6f}")

    return distance


# ---- Run estimation ----

_edtypes_env = os.environ.get('HAFISCAL_EDTYPES', '0,1,2')
edtypes_to_run = [int(s) for s in _edtypes_env.split(',') if s.strip()]
print(f"\nEdTypes to estimate: {edtypes_to_run}")

res_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Results')
df_base = f"DiscFacEstim_CRRA_{CRRA}_R_{Rfree_base[0]}"
if ep.IncUnemp != 0.7 or ep.IncUnempNoBenefits != 0.5:
    df_base += "_altBenefits"
if Splurge == 0:
    df_base += "_Splurge0"

# ESC-MOD-PHASE3-write: cross-interpretation registry isolation. CDC keeps
# legacy unsuffixed names; ESC tags every output with _ESC.
# Used in two ways below:
#   (a) `_INTERP_SUFFIX` appended to all `_TM_a.txt` writes (so ESC writes
#       to `..._TM_a_ESC.txt` instead of overwriting CDC's `..._TM_a.txt`)
#   (b) Warm-start source path tagged the same way (so ESC warm-starts from
#       its own prior ESC saved cal, not CDC's; missing file → cold start)
import sys as _sys_es
_ha_root_es = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _ha_root_es not in _sys_es.path:
    _sys_es.path.insert(0, _ha_root_es)
from _interpretation import interp_suffix as _interp_suffix, get_interpretation
_INTERP_SUFFIX = _interp_suffix()  # '' for CDC, '_ESC' for ESC

educ_names = ['Dropout', 'Highschool', 'College']

# Default starting points (always position 0 in init_vals_grid below; this
# preserves backward compatibility — HAFISCAL_NUM_STARTS=1 reproduces the
# pre-BUG-036 single-start estimation exactly).
init_vals_default = {0: [0.75, 0.3, 6], 1: [0.93, 0.07, 5], 2: [0.98, 0.015, 6]}

# Multi-start grids per BUG-036: the dropout cohort's Nelder-Mead surface is
# multimodal; single-start lands in a 47×-worse local basin. Multi-start
# reliably finds the global minimum. HS and college have narrower distributions
# and are less basin-trap-prone but get a couple of extra starts as cheap
# insurance.
init_vals_grid = {
    0: [  # Dropout — high-∇, multimodal (BUG-036)
        [0.75, 0.30, 6.0],   # script default
        [0.70, 0.34, 6.0],   # near-ESC anchor
        [0.65, 0.40, 5.0],   # low-β / wide-∇ probe (best basin in BUG-036 diag)
        [0.80, 0.20, 6.5],   # high-β / narrow-∇ probe
    ],
    1: [  # Highschool — narrow ∇
        [0.93, 0.07, 5.0],   # script default
        [0.90, 0.11, 4.5],   # post-fix-CDC-like
        [0.95, 0.05, 5.5],   # tighter
    ],
    2: [  # College — very narrow ∇
        [0.98, 0.015, 6.0],  # script default
        [0.97, 0.030, 7.0],  # mild perturbation
    ],
}

NUM_STARTS = int(os.environ.get('HAFISCAL_NUM_STARTS', '1'))
print(f"\nMulti-start: HAFISCAL_NUM_STARTS={NUM_STARTS}  "
      f"(1 = backward-compat single-start; >1 = run multiple starts and pick best)")

# Multi-cohort runs share a single consolidated _TM_a[_ESC].txt; truncate
# once so per-cohort writes can append in order (then footer appends too).
if len(edtypes_to_run) > 1:
    open(os.path.join(res_dir, df_base + "_TM_a" + _INTERP_SUFFIX + ".txt"), 'w').close()

for edType in edtypes_to_run:
    print(f"\n{'='*60}")
    print(f"Estimating {educ_names[edType]} (edType={edType}) via a-indexed TM")
    print(f"{'='*60}")

    # BUG-039 dispatch: HAFISCAL_GICX_MODE = legacy | hardcoded | twophase.
    # See BUGS_private/HAFiscal_BUG-039_GICx_unconditionally_optimized.md
    # and plans/20260502-1145h_fix-BUG-039-GICx-NM-options.md.
    #   hardcoded: 2-D NM (β, ∇); cap pinned at module-load theGICfactor (=0.9995 as of BUG-053,
    #              2026-06-09 — see EstimParameters.py; was 0.999 when this block was written). (DEFAULT post-Phase G)
    #   legacy:    3-D NM (β, ∇, GICx); GICx is a free fit knob. Pre-Phase G default; opt-in for verification.
    #   twophase:  2-D first; if cap binds at converged (β, ∇), refine with 3-D NM.
    # Default flipped 2026-05-03 per Phase G: Phase F evidence (GICx 10× spread with
    # negligible (β,∇) impact) confirms cap is non-load-bearing for all 3 cohorts.
    from EstimParameters import theGICfactor as _theGICfactor
    _GICX_MODE = os.environ.get('HAFISCAL_GICX_MODE', 'hardcoded')
    _GICx_for_factor_0999 = float(np.log(_theGICfactor / (1 - _theGICfactor)))
    if _GICX_MODE not in ('legacy', 'hardcoded', 'twophase'):
        raise ValueError(f"HAFISCAL_GICX_MODE must be 'legacy', 'hardcoded', or 'twophase'; got {_GICX_MODE!r}")
    print(f"[BUG-039] HAFISCAL_GICX_MODE = {_GICX_MODE}")
    if _GICX_MODE == 'hardcoded':
        print(f"[BUG-039 hardcoded] GICx pinned at logit(theGICfactor={_theGICfactor}) = {_GICx_for_factor_0999:.4f}; NM is 2-D (β, ∇)")
        f_temp = lambda x, et=edType: betas_obj_func_educ_tm_a(x[0], x[1], _GICx_for_factor_0999, educ_type=et)
    elif _GICX_MODE == 'twophase':
        print(f"[BUG-039 twophase] phase 1 = 2-D with GICx pinned; phase 2 fires per-start if cap binds")
        f_temp = lambda x, et=edType: betas_obj_func_educ_tm_a(x[0], x[1], _GICx_for_factor_0999, educ_type=et)
    else:  # 'legacy'
        f_temp = lambda x, et=edType: betas_obj_func_educ_tm_a(x[0], x[1], x[2], educ_type=et)

    starts = (init_vals_grid[edType][:NUM_STARTS] if NUM_STARTS > 1
              else [init_vals_default[edType]])

    # BUG-039 Phase E: HAFISCAL_NM_START_FROM_SAVED=1 prepends saved values
    # from DiscFacEstim_*.txt as an additional starting point.
    # Default flipped 2026-05-03 per Phase G: Phase E validated round-trip
    # preservation, so warm-start is on by default. Set =0 to opt out.
    if os.environ.get('HAFISCAL_NM_START_FROM_SAVED', '1') == '1':
        # Read warm-start from the canonical MC saved cal of THIS interpretation.
        # ESC reads `..._ESC.txt`; CDC reads `....txt`. Missing file → cold start.
        # Registry-aware (Phase 3 of registry plan): prefer the registry's
        # saved step2_cal for the matching configuration; fall back to the
        # suffix-named file if no registry entry exists.
        _saved_path = os.path.join(res_dir, df_base + _INTERP_SUFFIX + '.txt')
        try:
            import sys as _sys_reg_ws
            _ha_root_reg_ws = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            if _ha_root_reg_ws not in _sys_reg_ws.path:
                _sys_reg_ws.path.insert(0, _ha_root_reg_ws)
            import _registry as _reg_ws
            _reg_path = _reg_ws.find_warm_start_cal()
            if _reg_path is not None and _reg_path.exists():
                _saved_path = str(_reg_path)
                print(f"[BUG-039 Phase E + registry] warm-start source: {_reg_path}")
        except Exception as _ws_err:
            print(f"[BUG-039 Phase E] registry lookup failed ({_ws_err!r}); using suffix-named file")
        try:
            _saved_text = open(_saved_path).read()
            import re as _re
            _row_pattern = _re.compile(
                r"'EducationGroup':\s*" + str(edType) +
                r".*?'beta':\s*([\d.eE+-]+).*?'nabla':\s*([\d.eE+-]+).*?'GICx':\s*([\d.eE+-]+)"
            )
            _m = _row_pattern.search(_saved_text)
            if _m:
                _saved_start = [float(_m.group(1)), float(_m.group(2)), float(_m.group(3))]
                if NUM_STARTS == 1:
                    # Single-start mode + warm-start: REPLACE default with saved
                    starts = [_saved_start]
                    print(f"[BUG-039 Phase E] HAFISCAL_NM_START_FROM_SAVED=1: replaced single-start "
                          f"default with saved start β={_saved_start[0]:.4f}, ∇={_saved_start[1]:.4f}, "
                          f"GICx={_saved_start[2]:.4f} (from {os.path.basename(_saved_path)})")
                else:
                    # Multi-start: prepend saved + cap at NUM_STARTS
                    starts.insert(0, _saved_start)
                    starts = starts[:NUM_STARTS]
                    print(f"[BUG-039 Phase E] HAFISCAL_NM_START_FROM_SAVED=1: prepended saved start "
                          f"β={_saved_start[0]:.4f}, ∇={_saved_start[1]:.4f}, GICx={_saved_start[2]:.4f} "
                          f"(from {os.path.basename(_saved_path)}; capped to {NUM_STARTS} starts)")
            else:
                print(f"[BUG-039 Phase E] HAFISCAL_NM_START_FROM_SAVED=1 set but no edType={edType} row in {_saved_path}; using legacy starts only")
        except (FileNotFoundError, IOError):
            print(f"[BUG-039 Phase E] HAFISCAL_NM_START_FROM_SAVED=1 set but {_saved_path} not readable; using legacy starts only")

    # BUG-039: for 2-D modes, drop GICx from each starting point.
    if _GICX_MODE in ('hardcoded', 'twophase'):
        starts = [list(s)[:2] for s in starts]
    best_params, best_dist, best_idx = None, np.inf, None
    all_results = []

    # [2026-06-09] live NM progress. HARK's verbose only triggers scipy's final
    # disp summary (no per-iter trace) and exposes no callback, so wrap the
    # objective to log every Nth eval. NM has no fixed total — gauge progress
    # from the objective plateauing + the eval rate. Default on;
    # HAFISCAL_NM_LOG_EVERY=0 disables, any int sets the stride.
    _nm_log_every = int(os.environ.get('HAFISCAL_NM_LOG_EVERY', '5'))

    def _nm_progress(f, tag=''):
        if _nm_log_every <= 0:
            return f
        st = {'n': 0, 'best': float('inf'), 't0': time.time()}

        def g(x):
            v = float(f(x))
            st['n'] += 1
            st['best'] = min(st['best'], v)
            if st['n'] == 1 or st['n'] % _nm_log_every == 0:
                dt = max(time.time() - st['t0'], 1e-9)
                xs = ', '.join(f"{xi:.5f}" for xi in x)
                print(f"  [NM{tag} eval {st['n']}] obj={v:.5g} best={st['best']:.5g} "
                      f"x=[{xs}] ({dt:.0f}s, {st['n']/dt:.2f}/s)", flush=True)
            return v
        return g

    for k, x0 in enumerate(starts):
        if NUM_STARTS > 1:
            print(f"\n  --- Start {k+1}/{len(starts)}: x0={x0} ---")
        t0 = time.time()
        opt = minimize_nelder_mead(_nm_progress(f_temp, f" e{edType}"), x0, verbose=(NUM_STARTS == 1))
        # BUG-039: assemble full (β, ∇, GICx) from the (possibly 2-D) NM result
        if _GICX_MODE == 'hardcoded':
            opt = np.array([opt[0], opt[1], _GICx_for_factor_0999])
        elif _GICX_MODE == 'twophase':
            beta_p, spread_p = float(opt[0]), float(opt[1])
            dfs_p = Uniform(beta_p - spread_p, beta_p + spread_p).discretize(DiscFacCount)
            cap_p = gic_capped_beta(edType, _theGICfactor)
            if max(dfs_p.atoms[0]) > cap_p:
                print(f"  [BUG-039 twophase] cap binding at converged (β={beta_p:.4f}, ∇={spread_p:.4f}); running phase 2 (3-D)")
                f_3d = lambda x, et=edType: betas_obj_func_educ_tm_a(x[0], x[1], x[2], educ_type=et)
                opt = minimize_nelder_mead(f_3d, [beta_p, spread_p, _GICx_for_factor_0999], verbose=(NUM_STARTS == 1))
            else:
                print(f"  [BUG-039 twophase] cap non-binding at converged (β={beta_p:.4f}, ∇={spread_p:.4f}); skipping phase 2")
                opt = np.array([beta_p, spread_p, _GICx_for_factor_0999])
        elapsed = time.time() - t0
        dist = betas_obj_func_educ_tm_a(opt[0], opt[1], opt[2], educ_type=edType)
        all_results.append((k, x0, opt.tolist(), dist, elapsed))
        if NUM_STARTS > 1:
            print(f"    β={opt[0]:.4f} ∇={opt[1]:.4f} GICx={opt[2]:.3f} "
                  f"| distance={dist:.4f} | {elapsed/60:.1f} min")
        if dist < best_dist:
            best_dist = dist
            best_params = opt
            best_idx = k

    if NUM_STARTS > 1:
        print(f"\n  Best basin: start #{best_idx+1} (distance {best_dist:.4f})")
        dist_range = max(r[3] for r in all_results) - min(r[3] for r in all_results)
        print(f"  Distance range across {NUM_STARTS} starts: {dist_range:.4f}")
        if dist_range > 0.1:
            print(f"  ⚠ STRONG basin variation (range > 0.1) — confirms BUG-036 risk for this cohort")

    GICfactor = np.exp(best_params[2]) / (1 + np.exp(best_params[2]))
    print(f"\nFinished {educ_names[edType]}")
    print(f"  Beta={best_params[0]:.4f}  Nabla={best_params[1]:.4f}  GIC factor={GICfactor:.4f}")

    # Print the NEWLY-ESTIMATED discretized + GIC-clipped betaDistr (the distribution just
    # constructed at this optimum), labelled so it is unambiguously the new one — the load-time
    # betaDistr print in Parameters.py shows the STALE on-disk calibration during re-estimation
    # and is suppressed via HAFISCAL_QUIET_BETADISTR (BUG-053 followup, 2026-06-09).
    _gicfac_new = float(np.exp(best_params[2]) / (1 + np.exp(best_params[2])))
    _cap_new = gic_capped_beta(edType, _gicfac_new)
    _atoms_new = np.clip(
        Uniform(best_params[0] - best_params[1], best_params[0] + best_params[1]).discretize(DiscFacCount).atoms[0],
        minBeta, _cap_new)
    _n_at_cap_new = int(np.sum(_atoms_new >= _cap_new - 1e-12))
    print(f"  [newly estimated: EducationGroup {edType}] betaDistr : {np.round(_atoms_new, 4).tolist()}"
          f"  [GIC cap={_cap_new:.5f} (GPF={_gicfac_new:.5f}); {_n_at_cap_new}/{DiscFacCount} at cap]")

    betas_obj_func_educ_tm_a(best_params[0], best_params[1], best_params[2],
                             educ_type=edType, print_mode=True)

    suffix = f"_edType{edType}" if len(edtypes_to_run) == 1 else ""
    out_path = os.path.join(res_dir, df_base + suffix + "_TM_a" + _INTERP_SUFFIX + ".txt")
    mode = 'w' if suffix else 'a'
    with open(out_path, mode) as f:
        # float() the np.array entries: under numpy>=2 (numpy.float64) repr() would emit
        # "np.float64(...)" which ast.literal_eval (run_phase2_parallel.py merge,
        # adaptive_grid_tm._read_estim_record) cannot parse. Bare floats are numpy-version
        # independent and match the existing/QE-lineage calibration files. (BUG-053 audit.)
        f.write(repr({'EducationGroup': edType, 'beta': float(best_params[0]),
                       'nabla': float(best_params[1]), 'GICx': float(best_params[2])}) + '\n')
    print(f"  Wrote {out_path}")

# Footer
if len(edtypes_to_run) == 3:
    out_path = os.path.join(res_dir, df_base + "_TM_a" + _INTERP_SUFFIX + ".txt")
    with open(out_path, 'a') as f:
        f.write(f"\nParameters: R = {round(Rfree_base[0],2)}, CRRA = {round(CRRA,2)}, "
                f"IncUnemp = {round(ep.IncUnemp,2)}, IncUnempNoBenefits = {round(ep.IncUnempNoBenefits,2)}, "
                f"Splurge = {Splurge}\n")

print(f"\nDone.")
