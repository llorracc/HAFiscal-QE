import numpy as np
import os
import sys
from pathlib import Path
from HARK.distributions import Uniform

# ESC-MOD-PHASE3-read: route the splurge target through the interpretation
# resolver so ESC reads `Result_AllTarget_ESC.txt` (its own Step-1 output)
# instead of CDC's bare `Result_AllTarget.txt`. Falls back to bare file if
# the suffixed variant doesn't exist (legacy compat).
_ha_root = Path(__file__).resolve().parent.parent
if str(_ha_root) not in sys.path:
    sys.path.insert(0, str(_ha_root))
from _interpretation import resolve_path as _resolve_path

# ============================================================================
# CANONICAL SOLUTION-APPROACH DEFAULTS (Plan A, 2026-06-10)
# ----------------------------------------------------------------------------
# Make the *decided* welfare method the DEFAULT, via os.environ.setdefault so
# explicit user/env overrides still win. Validated by the MC-vs-TM-a welfare
# cascade (conclusions_private/2026-06-10_mc_vs_tma_welfare_cascade_HS_Only.md),
# which ran on exactly this config. Decision source:
# conclusions_private/2026-06-10_welfare_method_unified_MC.md.
#
# Escape hatch: HAFISCAL_QE_FIDELITY=1 skips these -> each call site falls back to
# its own legacy default (shuffle OFF, plain 'shuffle' transition, aMax=500), for
# reproducing the published-QE world. EstimParameters is imported by every entry
# point before any of these vars are read at runtime, so setting them here wins.
# ============================================================================
if os.environ.get('HAFISCAL_QE_FIDELITY', '') != '1':
    os.environ.setdefault('HAFISCAL_MC_SHUFFLE', '1')                        # welfare MC: shuffle ON
    os.environ.setdefault('HAFISCAL_SHUFFLE_MRKV_TRANSITION', 'stratified')  # NOT 'shuffle' (the +8.26%-UI footgun)
    os.environ.setdefault('HAFISCAL_SHUFFLE_NEWBORN_FIX', 'transition')
    # aMax=1300 is NOT a magic number: the TM grid must cover the MOST-PATIENT College discount-factor
    # atom (the GIC-cap atom, GPF=theGICfactor=0.9995 under the BUG-053 fix) — the most patient agents
    # save the most, so that atom's ergodic aNrm tail is the binding constraint on aMax. 1300 =
    # production_aMax() = the (1-1e-4) ergodic-aNrm quantile of that cap atom (adaptive_grid_tm.py:165);
    # aMax=500 truncates it (biasing the College high-wealth agents). Re-derive via production_aMax() if
    # the calibration / theGICfactor changes.
    os.environ.setdefault('HAFISCAL_TM_AMAX', '1300')

# Splurge target file: resolve from this module so imports work regardless of process cwd (e.g. pytest from repo root).
_SPLURGE_RESULT = _resolve_path(str(_ha_root / "Target_AggMPCX_LiquWealth" / "Result_AllTarget.txt"))

# MC determinism test mode: reduce agent count for fast single-threaded comparison
# Activated by HAFISCAL_MC_DETERMINISM_TEST=1 env var or --mc-test CLI flag
_MC_DETERMINISM_TEST = (os.environ.get('HAFISCAL_MC_DETERMINISM_TEST', '') == '1'
                        or '--mc-test' in sys.argv)

# Targets in the estimation of the discount factor distributions for each 
# education level. 
# From SCF 2004: [20,40,60,80]-percentiles of the Lorenz curve for liquid wealth
data_LorenzPts_d = np.array([0, 0.01, 0.60, 3.58])    # \
data_LorenzPts_h = np.array([0.06, 0.63, 2.98, 11.6]) # -> units: % 
data_LorenzPts_c = np.array([0.15, 0.92, 3.27, 10.3]) # /
data_LorenzPts = [data_LorenzPts_d, data_LorenzPts_h, data_LorenzPts_c]
data_LorenzPtsAll = np.array([0.03, 0.35, 1.84, 7.42])
# From SCF 2004: Average liquid wealth to permanent income ratio 
data_avgLWPI = np.array([15.7, 47.7, 111])*4 # weighted average of fractions in percent
# From SCF 2004: Total LW over total PI by education group
data_LWoPI = np.array([28.1, 59.6, 162])*4 # units: %
# From SCF 2004: Weighted median of liquid wealth to permanent income ratio
data_medianLWPI = np.array([1.16, 7.55, 28.2])*4 # weighted median of fractions in percent

# Population share of each type
data_EducShares = [0.093, 0.527, 0.38] # Proportion of dropouts, HS grads, college types, SCF 2004 
# Wealth share of each type 
data_WealthShares = np.array([0.008, 0.179, 0.812])*100 # Percentage of total wealth of dropouts, HS grads, college types, SCF 2004 

# Parameters concerning the distribution of discount factors
# Initial values for estimation, taken from pandemic paperCondMrkvArrays_base
# Note: only using these values for initialization, they are overwritten by estimation 
num_types = 3
DiscFacMeanD = 0.9647   # Mean intertemporal discount factor for dropout types
DiscFacMeanH = 0.98051  # Mean intertemporal discount factor for high school types
DiscFacMeanC = 0.99160  # Mean intertemporal discount factor for college types

DiscFacInit = [DiscFacMeanD, DiscFacMeanH, DiscFacMeanC]
DiscFacSpreadD = 0.025
DiscFacSpreadH = 0.01676
DiscFacSpreadC = 0.00480  # Half-width of uniform distribution of discount factors

# Define the distribution of the discount factor for each eduation level
DiscFacCount = 7
DiscFacDstnD = Uniform(DiscFacMeanD-DiscFacSpreadD, DiscFacMeanD+DiscFacSpreadD)._approx_equiprobable(DiscFacCount)
DiscFacDstnH = Uniform(DiscFacMeanH-DiscFacSpreadH, DiscFacMeanH+DiscFacSpreadH)._approx_equiprobable(DiscFacCount)
DiscFacDstnC = Uniform(DiscFacMeanC-DiscFacSpreadC, DiscFacMeanC+DiscFacSpreadC)._approx_equiprobable(DiscFacCount)
DiscFacDstns = [DiscFacDstnD, DiscFacDstnH, DiscFacDstnC]

# Parameters concerning Markov transition matrix
#https://www.statista.com/statistics/232942/unemployment-rate-by-level-of-education-in-the-us/
# HAFISCAL_URATE_NORMAL_{D,H,C} env-var overrides for shuffle-friendliness
# diagnostics; see plans/20260504-1700h_phase_F_mfmc_tm_a_control_variate.md
# Phase H-0 and memory project_shuffle_friendly_recalibration.
Urate_normal_d = float(os.environ.get('HAFISCAL_URATE_NORMAL_D', 0.085))
Urate_normal_h = float(os.environ.get('HAFISCAL_URATE_NORMAL_H', 0.044))
Urate_normal_c = float(os.environ.get('HAFISCAL_URATE_NORMAL_C', 0.027))
if any(k in os.environ for k in ('HAFISCAL_URATE_NORMAL_D','HAFISCAL_URATE_NORMAL_H','HAFISCAL_URATE_NORMAL_C')):
    print(f'[urate-override] Urate_normal_d={Urate_normal_d}  Urate_normal_h={Urate_normal_h}  Urate_normal_c={Urate_normal_c}')

Uspell_normal = 1.5          # Average duration of unemployment spell in normal times, in quarters
UBspell_normal = 2           # Average duration of unemployment benefits in normal times, in quarters

# Basic model parameters: CRRA, growth factors, unemployment parameters (for normal times)
CRRA = 2.0                 # Coefficient of relative risk aversion (1, 2 or 3)

with open(_SPLURGE_RESULT, "r", encoding="utf-8") as f:
    dictload = eval(f.read())
Splurge = dictload['splurge'] 
if len(sys.argv) >= 6:
    # Number of arguments indicates that Splurge is set manually 
    Splurge = float(sys.argv[5])

# MC determinism test: override Splurge with a fixed value common to both versions
if _MC_DETERMINISM_TEST:
    # Use the 0.14.1 splurge value as canonical so both versions start identically
    _MC_SPLURGE = float(os.environ.get('HAFISCAL_MC_SPLURGE', '0.2461138828477288'))
    print(f'[MC DETERMINISM TEST] Splurge overridden: {Splurge} -> {_MC_SPLURGE}')
    Splurge = _MC_SPLURGE

# elif len(sys.argv) >= 3:
#     # Number of arguments indicates that CRRA is set manually
#     CRRA = float(sys.argv[2])
#     if (CRRA != 1.0 and CRRA != 2.0 and CRRA != 3.0):
#         print('The Splurge was only estimated for CRRA = 1.0, 2.0 and 3.0')
#     # Read in estimated Splurge --> depends on CRRA: 
#     f = open('../Target_AggMPCX_LiquWealth/Result_CRRA_'+str(CRRA)+'.txt', 'r')
#     dictload = eval(f.read())
#     Splurge = dictload['splurge'] 
    
PopGroFac = 1.0         #1.01**0.25  # Population growth factor
# PermGroFacAgg: aggregate productivity / technological growth factor.
# Set to 1.0 (no aggregate growth) per the QE-era model setup.
# This is the BUG-038 restoration of the QE-era spec; BUG-037's setting
# of PermGroFacAgg = G_pop_avg ≈ 1.00455 was reverted (it was an internally
# consistent model-spec change, not a bug fix; the heavy-tail issue it tried
# to address is fixed at the source by the T_age cap restoration — see
# math doc §25 and `plans/20260430-1807h_qtwisted-capped-cohort-age.md`).
PermGroFacAgg = 1.0     # QE-era setup; aggregate productivity stays constant
IncUnemp = 0.7              # Unemployment benefits replacement rate (proportion of permanent income)
IncUnempNoBenefits = 0.5   # Unemployment income when benefits run out (proportion of permanent income)
if len(sys.argv) >= 5:
    IncUnemp = float(sys.argv[3])
    IncUnempNoBenefits = float(sys.argv[4])

# -----------------------------------------------------------------------
# Parameters concerning the initial distribution of permanent income
# -----------------------------------------------------------------------
#
# Newborns of group g are drawn from group-specific Lognormal(pLogInitMean_g,
# pLogInitStd_g), calibrated to SCF 2004 quarterly earnings at age 25 by
# education category. These cross-group differentials are an intentional
# calibration target — they encode the SCF earnings premiums by education
# group, which downstream model behavior is calibrated to match.
#
# BUG-038 (2026-04-30) restored this group-specific spec from the BUG-037
# misdiagnosis, which had replaced per-group `pLogInitMean_g` with a common
# `pLogInitMean_avg`. Per user review, that change was an overreach (it
# imposed a "literature-standard" perpetual-youth convention not appropriate
# to HAFiscal's SCF-calibrated heterogeneity). See
# `plans/20260430-1807h_qtwisted-capped-cohort-age.md` §3 for the revert
# rationale.
# -----------------------------------------------------------------------
pLogInitMean_d = np.log(6.2)   # SCF: avg quarterly permanent income at age 25, HS dropout ($1000)
pLogInitMean_h = np.log(11.1)  # SCF: avg quarterly permanent income at age 25, HS graduate ($1000)
pLogInitMean_c = np.log(14.5)  # SCF: avg quarterly permanent income at age 25, college ($1000)
pLogInitStd_d  = 0.32          # SCF: σ of initial log permanent income, HS dropout
pLogInitStd_h  = 0.42          # SCF: σ of initial log permanent income, HS graduate
pLogInitStd_c  = 0.53          # SCF: σ of initial log permanent income, college

# Parameters concerning grid sizes: assets, permanent income shocks, transitory income shocks
aXtraMin = 0.001        # Lowest non-zero end-of-period assets above minimum gridpoint
aXtraMax = 40           # Highest non-zero end-of-period assets above minimum gridpoint
aXtraCount = int(os.environ.get('HAFISCAL_AXTRA_COUNT', 48))         # Base number of end-of-period assets above minimum gridpoints
if 'HAFISCAL_AXTRA_COUNT' in os.environ:
    print(f'[axtra-override] HAFISCAL_AXTRA_COUNT → aXtraCount={aXtraCount}')
aXtraExtra = [0.002,0.003] # Additional gridpoints to "force" into the grid
aXtraNestFac = 3        # Exponential nesting factor for aXtraGrid (how dense is grid near zero)
PermShkCount = 7        # Number of points in equiprobable discrete approximation to permanent shock distribution
TranShkCount = 7        # Number of points in equiprobable discrete approximation to transitory shock distribution


# Size of simulations
AgentCountTotal = 50000 # Total simulated population
T_sim = 80              # Number of quarters to simulate in counterfactuals

if _MC_DETERMINISM_TEST:
    AgentCountTotal = 500  # Reduced for determinism test (fast, ~1-2 min per evaluation)
    print(f'[MC DETERMINISM TEST] AgentCountTotal reduced to {AgentCountTotal}')

# Basic lifecycle length parameters (don't touch these)
T_cycle = 1

# Define grid of aggregate assets to labor
CgridBase = np.array([0.8, 1.0, 1.2])

# BUG-043 fix: extend the micro state space to encode "quarter of unemployment"
# explicitly so UI extension can be implemented as a payout-based policy
# rather than a freeze-window mechanism.
#
# HAFISCAL_UI_STATE_ENCODING:
#   'legacy':            4 micro states {e, u1Q, u2Q, noBen}.
#                        UI extension implemented via transition_ub=False
#                        freeze over a fixed macro-state window. Under-delivers
#                        by 1Q for Case 1 agents (BUG-043). Bit-identical to
#                        the published code; use only when reproducing
#                        pre-2026-05-16 numbers.
#   'bug_fix' (default): 6 micro states {e, u1Q, u2Q, u3Q, u4Q, noBen}.
#                        UI extension implemented via macro-state-conditional
#                        income at u3Q/u4Q (= 0.7 when recession + recessionUI
#                        scenario; 0.5 otherwise). Fixes BUG-043; matches paper
#                        Model.tex line 167-168 ("up to four quarters").
#                        Side benefit: enables shuffle CRN for UI welfare cells.
#                        Cutover 2026-05-16 (see
#                        conclusions_private/2026-05-16_canonical_config_recommendation.md).
# See plans/20260511_BUG-043_fix_state_expansion_plan.md
HAFISCAL_UI_STATE_ENCODING = os.environ.get('HAFISCAL_UI_STATE_ENCODING', 'bug_fix')
assert HAFISCAL_UI_STATE_ENCODING in ('legacy', 'bug_fix'), \
    f"HAFISCAL_UI_STATE_ENCODING must be 'legacy' or 'bug_fix', got {HAFISCAL_UI_STATE_ENCODING!r}"

# Policy_ExtraBenefitQuarters: how many EXTRA quarters of UI benefits the
# extension policy provides on top of UBspell_normal. Per paper Model.tex
# line 167 ("extended from two quarters to four quarters"): 2 extra.
Policy_ExtraBenefitQuarters = 2

if HAFISCAL_UI_STATE_ENCODING == 'bug_fix':
    # Expanded state space: encode each quarter of unemployment as its own
    # micro state up to UBspell_normal + Policy_ExtraBenefitQuarters.
    # E.g., with UBspell_normal=2 and Policy_ExtraBenefitQuarters=2: 4 benefit-
    # eligible states (u1Q, u2Q, u3Q, u4Q) + employed + noBen = 6 micro states.
    num_base_MrkvStates = 2 + UBspell_normal + Policy_ExtraBenefitQuarters
else:
    # Legacy 4-state encoding: 2 benefit-eligible states + employed + noBen.
    num_base_MrkvStates = 2 + UBspell_normal

# Inform user of encoding choice (cheap, helpful for log reading)
if HAFISCAL_UI_STATE_ENCODING == 'bug_fix':
    print(f'[BUG-043 fix] HAFISCAL_UI_STATE_ENCODING=bug_fix → '
          f'num_base_MrkvStates={num_base_MrkvStates} '
          f'(legacy would be {2 + UBspell_normal})')

num_experiment_periods = 20

def small_MrkvArray(e,u,ub,transition_ub=True):
    small_MrkvArray = np.zeros((ub+2, ub+2))
    small_MrkvArray[0,0] = e
    small_MrkvArray[0,1] = 1-e
    for i in np.array(range(ub))+1:
        if transition_ub:
            small_MrkvArray[i,i+1] = u
        else:
            small_MrkvArray[i,i] = u
        small_MrkvArray[i,0] = 1-u
    small_MrkvArray[ub+1,ub+1] = u
    small_MrkvArray[ub+1,0] = 1-u
    return small_MrkvArray 

def make_cond_mrkv_arrays_base(Urate_normal, Uspell_normal, UBspell_normal):
    U_persist_normal = 1.-1./Uspell_normal
    E_persist_normal = 1.-Urate_normal*(1.-U_persist_normal)/(1.-Urate_normal)
    MrkvArray_normal         = small_MrkvArray(E_persist_normal,    U_persist_normal,    UBspell_normal)
    CondMrkvArrays = [MrkvArray_normal]
    return CondMrkvArrays

def make_full_mrkv_array(MacroMrkvArray, CondMrkvArrays):
    for i in range(MacroMrkvArray.shape[0]):
        this_row = MacroMrkvArray[i,0]*CondMrkvArrays[0]
        for j in range(MacroMrkvArray.shape[0]-1):
            this_row = np.concatenate((this_row, MacroMrkvArray[i,j+1]*CondMrkvArrays[j+1]),axis=1)
        if i==0:
            FullMrkv = this_row
        else:
            FullMrkv = np.concatenate((FullMrkv, this_row), axis=0)
    return [FullMrkv]

MacroMrkvArray_base = np.array([[1.0]])
CondMrkvArrays_base_d = make_cond_mrkv_arrays_base(Urate_normal_d, Uspell_normal, UBspell_normal)
MrkvArray_base_d = make_full_mrkv_array(MacroMrkvArray_base, CondMrkvArrays_base_d)
CondMrkvArrays_base_h = make_cond_mrkv_arrays_base(Urate_normal_h, Uspell_normal, UBspell_normal)
MrkvArray_base_h = make_full_mrkv_array(MacroMrkvArray_base, CondMrkvArrays_base_h)
CondMrkvArrays_base_c = make_cond_mrkv_arrays_base(Urate_normal_c, Uspell_normal, UBspell_normal)
MrkvArray_base_c = make_full_mrkv_array(MacroMrkvArray_base, CondMrkvArrays_base_c)

# Define permanent income growth rates
PermGroFac_base =   [1.0]
PermGroFac_base_d = [1.0 + 0.01421/4]  # From Pandemic paper: avg growth rates during
PermGroFac_base_h = [1.0 + 0.01812/4]  # working life for each education group
PermGroFac_base_c = [1.0 + 0.01958/4]

# BUG-038 (2026-04-30): PermGroFacAgg stays at 1.0 per the QE-era setup
# (assigned at line ~99 above). The BUG-037 override that set it to
# G_pop_avg ≈ 1.00455 was reverted because (a) per user review, the
# heavy-tail issue it tried to address is more cleanly fixed by the
# T_age cap restoration in BUG-038, and (b) PermGroFacAgg = 1 is the
# QE paper's setup — minimum disruption from that baseline.
# See `plans/20260430-1807h_qtwisted-capped-cohort-age.md` §3 and
# `BUGS_private/HAFiscal_BUG-038_T_age_cap_removal.md`.

# SST (income process): see income_process_sst.py and history/20260403-sst-permgrofac-income-process-plan.md
from income_process_sst import build_PermGroFac_micro

# --- Unemployment income process flags (SST) ---
# Paper default: unemployed agents have no pLvl growth (PermGroFac_unemp=1),
# no stochastic permanent shocks, and no stochastic transitory shocks.
# Income during unemployment is deterministic: pLvl * IncUnemp.
#
# Rationale for turning off shocks: with ~4.4% unemployment, only ~44 out of
# 1000 agents are unemployed.  Stochastic draws for 44 agents produce sampling
# noise that overwhelms the small signal from their income differences.
# Deterministic unemployment income eliminates this noise source.
#
# For debugging: set unemp_pLvl_grows_like_employed=True to give unemployed
# agents the same PermGroFac as employed (but still no stochastic shocks).
# When True, PermGroFac_unemp is set to the employed rate per education group
# in the build_PermGroFac_micro calls below.
# HAFISCAL_PLVL_GROWS_DURING_UNEMP (default 'off') controls whether unemployed
# agents accumulate the productivity-growth factor G during unemployment spells.
#   'off' (default, QE-published convention): unemployed agents have pLvl FROZEN
#         (no G, no ψ shock under perm_shocks_during_unemp=False). MC and TM-a
#         agree at this convention. Matches what the published QE numbers
#         actually compute.
#   'on'  (Harmenberg-factorizable convention): unemployed agents grow at G
#         (still ψ=1 under perm_shocks=False). Required for pLvl ⊥ state, the
#         Harmenberg analytical factorization that allows TM-a to use the
#         analytical p formula. MC and TM-a both apply G uniformly.
#
# Both conventions are internally consistent. The MC-vs-TM-a residual
# diagnosed 2026-05-05 was caused by the two methods silently using
# DIFFERENT conventions: MC was 'off' (PermShk=1.0 for unemp drops G), TM-a
# was 'on' (PermGroFac uniform across states). This env var unifies both.
_pgu_env = os.environ.get('HAFISCAL_PLVL_GROWS_DURING_UNEMP', 'off').strip().lower()
unemp_pLvl_grows_like_employed = _pgu_env in ('on', '1', 'true', 'yes')
PermGroFac_unemp = 1.0  # Used when unemp_pLvl_grows_like_employed is False
if 'HAFISCAL_PLVL_GROWS_DURING_UNEMP' in os.environ:
    print(f'[plvl-grows-during-unemp] HAFISCAL_PLVL_GROWS_DURING_UNEMP={_pgu_env!r} '
          f'→ unemp_pLvl_grows_like_employed = {unemp_pLvl_grows_like_employed}')
# perm_shocks_during_unemployment: profile-dependent. Set explicitly by reproduce.sh
# profiles via HAFISCAL_PERM_DURING_UNEMP={on,off}. Default ON (Harmenberg-style:
# unemployed agents draw the same PermShk as employed, enabling pLvl ⊥ state
# factorization). The qe_fidelity profile sets OFF to match the published
# HAFiscal-QE assumption (PermShk=1 while unemployed).
_psdu_env = os.environ.get('HAFISCAL_PERM_DURING_UNEMP', '').strip().lower()
if _psdu_env in ('on', '1', 'true', 'yes'):
    perm_shocks_during_unemployment = True
elif _psdu_env in ('off', '0', 'false', 'no'):
    perm_shocks_during_unemployment = False
elif _psdu_env == '':
    perm_shocks_during_unemployment = True   # silent default = Harmenberg-style
else:
    raise ValueError(
        f"HAFISCAL_PERM_DURING_UNEMP={_psdu_env!r} is not a recognized value. "
        f"Use 'on'/'off' (or 1/0, true/false, yes/no)."
    )
tran_shocks_during_unemployment = False  # Paper: no stochastic TranShk while unemployed

# # Define the permanent and transitory shocks 
# TranShkStd = [0.1]
# PermShkStd = [0.05]
# Variances from Sticky expectations paper: 
TranShkStd = [np.sqrt(0.12)]
PermShkStd = [np.sqrt(0.003)]

Rfree_base = [1.01]             #Baseline
if len(sys.argv) >= 2:
    Rfree_base = [float(sys.argv[1])]
LivPrb_base = [1.0-1/160.0]     # 40 years (160 quarters) working life 

# Calculate max beta values for each education group where GIC holds with equality.
#
# Imposes the Risk-Modified Growth Impatience Condition with mortality
# (GIC-Mod-with-Liv) from Carroll's BufferStockTheory paper:
#
#     L · Þ · E[1/ψ] / Γ < 1   where Þ = (Rβ)^(1/ρ)
#
# Solving for β:  β_max = (Γ / (L · E[1/ψ]))^ρ / R
#
# Γ is the **agent's per-period perceived deterministic growth of pLvl**,
# which equals the cohort-specific labor-income growth `PermGroFac_base_g`
# (NOT multiplied by `PermGroFacAgg`). PermGroFacAgg is an aggregate-
# bookkeeping factor that affects the LEVEL at which newborns enter
# (`pLvl_init = Lognormal(... + log(PlvlAgg^t), ...)`) but does NOT enter
# survivors' per-period pLvl evolution: `pLvl_{t+1} = G_g · ψ · pLvl_t`.
# Therefore the agent's normalized-asset chain (aNrm = a/p) depends on G_g
# alone, and the GIC formula must use Γ = G_g.
#
# (An earlier version of this formula multiplied G_g by PermGroFacAgg —
# silently a no-op while PermGroFacAgg = 1, but became spuriously
# loosening when PermGroFacAgg was set to G_pop_avg ≈ 1.005 per BUG-037.
# Corrected here to use G_g alone; see BUG-037 §1.7 for the agent-side
# derivation.)
#
# For lognormal ψ with E[ψ]=1 and var(log ψ)=σ²:  E[1/ψ] = exp(σ²).
#
# This is the BST-textbook condition that is necessary and sufficient for a
# *stationary distribution of normalized assets* to exist in a population
# with mortality + birth. Both growth (numerator) and mortality (denominator)
# loosen the bound; permanent-shock variance partially offsets by tightening.
#
# Replaces an earlier ad-hoc formula (1-L) + Γ^ρ/R which combined
# mortality and the regular GICRaw additively without coupling to shock
# variance and ignored aggregate productivity growth.
Ex_inv_PermShk = np.exp(PermShkStd[0]**2)  # E[1/ψ] for lognormal with E[ψ]=1
_GICMod_denom = LivPrb_base[0] * Ex_inv_PermShk
GICmaxBetas = np.array([
    (PermGroFac_base_d[0] / _GICMod_denom)**CRRA / Rfree_base[0],
    (PermGroFac_base_h[0] / _GICMod_denom)**CRRA / Rfree_base[0],
    (PermGroFac_base_c[0] / _GICMod_denom)**CRRA / Rfree_base[0],
])
# GIC margin: the most-patient (cap) atom's Growth Patience Factor ceiling. Imposed on the GPF
# (BUG-053), so gic_capped_beta(e, theGICfactor) = GICmaxBetas[e]*theGICfactor**CRRA puts the cap
# atom at GPF = theGICfactor. Set to 0.9995 (2026-06-09): the BUG-053 fix correctly moved the cap
# from beta-shave to GPF-shave, but at GPF=0.999 the cap is LOAD-BEARING for College (its
# wealth-concentration fit needs a near-GIC-boundary most-patient atom) — College TM-a distance
# ~5.75 at GPF=0.999 vs ~4.3 at GPF=0.9995. GPF=0.9995 (cap beta = GICmax*0.9995**2 = 1.005375 for
# College) restores the good fit AND coincides with the cap the old beta-shave bug effectively
# produced (GICmax*0.999 = 1.005369, GPF 0.99949), so multipliers stay ~unchanged vs the published
# world while the mechanism is now correct. theGICfactor is the GIC margin choice, not a bug knob.
theGICfactor = 0.9995
minBeta = 0.01

def gic_capped_beta(educ_type, shave):
    """Maximum discount factor (beta) for an education group, capped so the most-patient
    atom's GROWTH PATIENCE FACTOR (GPF) does not exceed `shave`.

    WHAT WE IMPOSE, AND WHY (BUG-053)
    ---------------------------------
    The object that must stay below 1 for a stationary wealth-to-permanent-income ratio is
    the GPF (the Growth Impatience Condition: GPF < 1), NOT beta itself. So the calibration
    ceiling belongs on the GPF: we want the most-patient atom to sit at GPF = `shave`
    (e.g. 0.999) -- a hair inside the growth-impatience boundary GPF = 1.

    `GICmaxBetas[educ_type]` is the beta at which GPF = 1 exactly (the GIC-Mod-with-Liv cap,
    (Gamma / (L * E[1/psi]))**CRRA / R). Since GPF is proportional to beta**(1/CRRA), the
    beta whose GPF equals `shave` is

        beta_cap = GICmaxBetas[educ_type] * shave**CRRA          # GPF(beta_cap) == shave

    THE FIX (default): exponent CRRA -> `shave` is a ceiling on the GPF. With shave=0.999,
    CRRA=2 the cap atom lands at GPF = 0.999, beta ~= GICmax*0.998.

    THE BUG IT REPLACES: the old code multiplied the cap by `shave` directly
    (GICmaxBetas * shave -- a ceiling on BETA), which yields GPF = shave**(1/CRRA) -- e.g.
    0.999 -> 0.9995. That left the most-patient atom *closer* to the GIC boundary than the
    nominal 0.999, with a correspondingly fatter ergodic wealth tail, slower consumption
    solve, and wider asset grid.

    PAPER TRAIL: HAFISCAL_GIC_SHAVE_ON_GPF defaults to '1' (GPF-shave, the fix). Set it to
    '0' to reproduce the old beta-shave behavior (GPF = shave**(1/CRRA)) for the
    QE-divergence ledger / before-after comparison. Changing the cap moves the calibration,
    so the (beta, nabla) atoms should be RE-ESTIMATED under the fix (gated; see BUG-053).
    """
    import os as _os
    # exponent CRRA  -> `shave` is a ceiling on the GPF (the fix);
    # exponent 1.0   -> `shave` is a ceiling on beta (the BUG-053 behavior, reproducible).
    _exp = CRRA if _os.environ.get('HAFISCAL_GIC_SHAVE_ON_GPF', '1') != '0' else 1.0
    return GICmaxBetas[educ_type] * shave ** _exp

for e in range(num_types):
    for thedf in range(DiscFacCount):
        if DiscFacDstns[e].atoms[0][thedf] > gic_capped_beta(e, theGICfactor):
            DiscFacDstns[e].atoms[0][thedf] = gic_capped_beta(e, theGICfactor)
        elif DiscFacDstns[e].atoms[0][thedf] < minBeta:
            DiscFacDstns[e].atoms[0][thedf] = minBeta

# find intial distribution of states for each education type
vals_d, vecs_d = np.linalg.eig(np.transpose(MrkvArray_base_d[0])) 
vals_d = vals_d.real
vecs_d = vecs_d.real
dist_d = np.abs(np.abs(vals_d) - 1.)
idx_d = np.argmin(dist_d)
init_mrkv_dist_d = vecs_d[:,idx_d].astype(float)/np.sum(vecs_d[:,idx_d].astype(float))

vals_h, vecs_h = np.linalg.eig(np.transpose(MrkvArray_base_h[0])) 
dist_h = np.abs(np.abs(vals_h) - 1.)
idx_h = np.argmin(dist_h)
# Use np.real() to extract real part, avoiding ComplexWarning for negligible imaginary components
init_mrkv_dist_h = np.real(vecs_h[:,idx_h])/np.sum(np.real(vecs_h[:,idx_h]))

vals_c, vecs_c = np.linalg.eig(np.transpose(MrkvArray_base_c[0])) 
dist_c = np.abs(np.abs(vals_c) - 1.)
idx_c = np.argmin(dist_c)
# Use np.real() to extract real part, avoiding ComplexWarning for negligible imaginary components
init_mrkv_dist_c = np.real(vecs_c[:,idx_c])/np.sum(np.real(vecs_c[:,idx_c]))

# Define a parameter dictionary for dropout type
init_dropout = {"cycles": 0, # This will be overwritten at type construction
                "T_cycle": T_cycle,
                'T_sim': 400, #Simulate up to age 400
                'T_age': 200,  # BUG-038: QE-era cap restored (50 years). See math doc §25.
                'AgentCount': 10000,
                "PermGroFacAgg": PermGroFacAgg,
                "PopGroFac": PopGroFac,
                "CRRA": CRRA,
                "DiscFac": 0.98, # This will be overwritten at type construction
                "Rfree_base" : Rfree_base,
                "PermGroFac_base": PermGroFac_base_d,
                "LivPrb_base": LivPrb_base,
                "Rfree" : np.array(num_base_MrkvStates*Rfree_base),
                "PermGroFac": [np.array(build_PermGroFac_micro(PermGroFac_base_d[0], num_base_MrkvStates, PermGroFac_base_d[0] if unemp_pLvl_grows_like_employed else PermGroFac_unemp))],
                "LivPrb": [np.array(LivPrb_base*num_base_MrkvStates)],
                "MrkvArray_base" : MrkvArray_base_d, 
                "MacroMrkvArray_base" : MacroMrkvArray_base,
                "CondMrkvArrays_base" : CondMrkvArrays_base_d,
                "MrkvArray" : MrkvArray_base_d, 
                "MacroMrkvArray" : MacroMrkvArray_base,
                "CondMrkvArrays" : CondMrkvArrays_base_d,
                "BoroCnstArt": 0.0,
                "PermShkStd": PermShkStd,
                "PermShkCount": PermShkCount,
                "TranShkStd": TranShkStd,
                "TranShkCount": TranShkCount,
                "UnempPrb": 0.0, # Unemployment is modeled as a Markov state
                "IncUnemp": IncUnemp,
                "IncUnempNoBenefits": IncUnempNoBenefits,
                "aXtraMin": aXtraMin,
                "aXtraMax": aXtraMax,
                "aXtraCount": aXtraCount,
                "aXtraExtra": aXtraExtra,
                "aXtraNestFac": aXtraNestFac,
                "CubicBool": False,
                "vFuncBool": False,
                'kLogInitMean': np.log(0.00001), # Initial assets are zero
                'kLogInitStd': 0.0,
                'pLogInitMean': pLogInitMean_d,  # SCF: avg quarterly perm income at age 25 (per group)
                'pLogInitStd': pLogInitStd_d,       # σ_g kept group-specific (within-group dispersion)
                "MrkvPrbsInit" : np.array(list(init_mrkv_dist_d)),
                'Urate_normal' : Urate_normal_d,
                'Uspell_normal' : Uspell_normal,
                'UBspell_normal' : UBspell_normal,
                'num_base_MrkvStates' : num_base_MrkvStates,
                'PermGroFac_unemp': PermGroFac_unemp,
                'perm_shocks_during_unemployment': perm_shocks_during_unemployment,
                'tran_shocks_during_unemployment': tran_shocks_during_unemployment,
                'num_experiment_periods' : num_experiment_periods,
                'UpdatePrb' : 1.0,
                'Splurge' : Splurge,
                'track_vars' : [],
                'EducType': 0
                }

adj_highschool = {
    "PermGroFac_base": PermGroFac_base_h,
    "PermGroFac": [np.array(build_PermGroFac_micro(PermGroFac_base_h[0], num_base_MrkvStates, PermGroFac_base_h[0] if unemp_pLvl_grows_like_employed else PermGroFac_unemp))],
    "MrkvArray_base" : MrkvArray_base_h, 
    "CondMrkvArrays_base" : CondMrkvArrays_base_h,
    "MrkvArray" : MrkvArray_base_h, 
    "CondMrkvArrays" : CondMrkvArrays_base_h,
    'pLogInitMean': pLogInitMean_h,  # SCF: avg quarterly perm income at age 25 (per group)
    'pLogInitStd': pLogInitStd_h,       # σ_g kept group-specific
    "MrkvPrbsInit" : np.array(list(init_mrkv_dist_h)),
    'Urate_normal' : Urate_normal_h,
    'EducType' : 1}
init_highschool = init_dropout.copy()
init_highschool.update(adj_highschool)

adj_college = {
    "PermGroFac_base": PermGroFac_base_c,
    "PermGroFac": [np.array(build_PermGroFac_micro(PermGroFac_base_c[0], num_base_MrkvStates, PermGroFac_base_c[0] if unemp_pLvl_grows_like_employed else PermGroFac_unemp))],
    "MrkvArray_base" : MrkvArray_base_c, 
    "CondMrkvArrays_base" : CondMrkvArrays_base_c,
    "MrkvArray" : MrkvArray_base_c, 
    "CondMrkvArrays" : CondMrkvArrays_base_c,
    'pLogInitMean': pLogInitMean_c,  # SCF: avg quarterly perm income at age 25 (per group)
    'pLogInitStd': pLogInitStd_c,       # σ_g kept group-specific
    "MrkvPrbsInit" : np.array(list(init_mrkv_dist_c)),
    'Urate_normal' : Urate_normal_c,
    'EducType' : 2}
init_college = init_dropout.copy()
init_college.update(adj_college)

# Define a dictionary to represent the baseline scenario
base_dict = {'shock_type' : "base",
             'UpdatePrb' : 1.0,
             'Splurge' : Splurge
             }

frictionless_changes = {
             'UpdatePrb' : 1.0
             }

# Parameters for AggregateDemandEconomy economy
intercept_prev = np.ones((num_base_MrkvStates,num_base_MrkvStates ))    # Intercept of aggregate savings function
slope_prev = np.zeros((num_base_MrkvStates,num_base_MrkvStates ))       # Slope of aggregate savings function
ADelasticity = 0.30                                                     # Elasticity of productivity to consumption

num_max_iterations_solvingAD = 30
convergence_tol_solvingAD = 1E-6
Cfunc_iter_stepsize       = 1

# Make a dictionary to specify a Cobb-Douglas economy
init_ADEconomy = {'intercept_prev': intercept_prev,
                     'slope_prev': slope_prev,
                     'ADelasticity' : 0.0,
                     'demand_ADelasticity' : ADelasticity,
                     'Cfunc_iter_stepsize' : Cfunc_iter_stepsize,
                     'MrkvArray' : MrkvArray_base_h,
                     'num_base_MrkvStates' : num_base_MrkvStates,
                'PermGroFac_unemp': PermGroFac_unemp,
                'perm_shocks_during_unemployment': perm_shocks_during_unemployment,
                'tran_shocks_during_unemployment': tran_shocks_during_unemployment,
                     "MrkvArray_base" : MrkvArray_base_h, 
                     'CgridBase' : CgridBase,
                     'EconomyMrkvNow_init': 0,
                     'act_T' : 400
                     }