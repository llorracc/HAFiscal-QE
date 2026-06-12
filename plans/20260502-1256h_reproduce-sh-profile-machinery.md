---
date: 2026-05-02
status: draft
keywords: [reproduce.sh, profiles, qe-fidelity, tm-throughout, production-fast, methodological-configuration, HAFISCAL_INTERPRETATION, HAFISCAL_GICX_MODE]
related_bugs: [BUG-039, BUG-034]
related_plans: [20260502-1145h_fix-BUG-039-GICx-NM-options.md]
---

# `reproduce.sh --profile NAME` machinery: 5 named methodological profiles

## Background

The HAFiscal codebase now supports many distinct methodological combinations
(MC vs TM-a, CDC vs ESC interpretation, multiple GICx modes after BUG-039,
warm-start vs heuristic NM starts, etc.). A user invoking
`./reproduce.sh --comp full` today gets one specific combination of all
these choices — the current default — but cannot easily request a
DIFFERENT coherent combination without juggling individual env vars.

This plan introduces `--profile NAME` to `reproduce.sh`, with five named
profiles bundling the choices into clear objectives. Users select a
profile rather than setting env vars manually.

## Relationship to the BUG-039 plan

This plan was originally Phase H of the BUG-039 plan
(`plans/20260502-1145h_fix-BUG-039-GICx-NM-options.md`). It's been
extracted into a standalone plan because:

- The `--profile NAME` machinery is a logically distinct piece of work
  (UX/dispatch in a shell script, not a code change to the optimizer)
- Two of the five profiles use BUG-039 features (`HAFISCAL_GICX_MODE`,
  `HAFISCAL_NM_START_FROM_SAVED`, `HAFISCAL_WRAPPER_MULTISTART_POINTS`),
  but three do not — the `qe_fidelity`, `production_current`, and
  `mc_throughout_validation` profiles can be implemented without any
  BUG-039 work. So this plan can land partially even before BUG-039
  Phases A/E/F.
- Logical scoping: reviewers should evaluate this plan separately from
  the BUG-039 estimation-internals work.

**Dependency**: profiles `production_fast` and `tm_throughout_fast`
require BUG-039 Phases A and (optionally) E and F to be landed. If those
aren't landed yet, this plan can either:
- Defer adding those two profiles to a follow-up commit
- Or include them as "stubs" that fail with a clear "BUG-039 not yet
  landed" error message

## Goal

Users can run:
```bash
./reproduce.sh --comp full --profile qe_fidelity
./reproduce.sh --comp full --profile production_fast
./reproduce.sh --comp mini --profile tm_throughout_fast
```
…and get a coherent, well-defined set of methodological choices applied
to the existing scope-flagged pipeline.

## Out of scope

- Don't change any non-shell code (the profiles just set env vars that
  existing code already reads)
- Don't add NEW dimensions of methodological choice — only bundle the
  ones that already exist
- Don't change the existing `--comp` scope flag, `--mc-only`/`--tm-only`
  flags, or any other existing semantics
- Don't validate methodology in this plan (each profile's smoke test
  just confirms the dispatch works; cross-profile validation is its
  own work)

## Constraints

- Profiles are opt-in via explicit `--profile NAME` flag; no profile
  becomes default
- Backwards-compat: invocations without `--profile` behave exactly as
  today
- Fail fast on unknown profile names (with the list of valid profiles)
- Profile env-var settings are logged at script start so users can see
  what was configured
- Profiles compose with all existing scope flags (`--comp nano/micro/mini/min/full/max`)
  and modifiers (`--mc-only`/`--tm-only` if not already implied by profile)

## Cataloguing all available dimensions of choice

| Dimension | Current values | Env var or flag |
|---|---|---|
| Step 1 (splurge) method | MC | (no toggle yet — TM-a Step-1 not implemented) |
| Step 2 (β/∇) method | MC (production) or TM-a (`estim_phase2_tm_a.py`) | future: `HAFISCAL_STEP2_METHOD = mc \| tm_a` |
| Step 2 GICx mode (BUG-039) | legacy / hardcoded / twophase | `HAFISCAL_GICX_MODE` |
| Step 2 NM starting points | heuristic defaults / warm-start from saved | `HAFISCAL_NM_START_FROM_SAVED` |
| Step 2 multistart parallelism | sequential / parallel | `HAFISCAL_WRAPPER_MULTISTART_POINTS` |
| Step 2 NM tolerance | 1e-2 (current default) / tighter (e.g., 1e-4 for QE-fidelity) | `HAFISCAL_NM_XATOL` |
| Step 5 method | TM-a (default) / MC | `--tm-only` / `--mc-only` flags in `reproduce.sh` |
| Step 5 q_method | doob / cohort / bst | `q_method` parameter (in code, not env-var-exposed yet) |
| Interpretation | CDC (default) / ESC | `HAFISCAL_INTERPRETATION` |
| Run scope | nano / micro / mini / min / TM-and-MC / full / max | `--comp` scope flag |
| Splurge robustness | normal (Splurge ≈ 0.26) / Splurge=0 | `Splurge0` parametrization |
| T_age cap | 200 (post-BUG-038 default) / None | (not env-var-toggled) |

## Profiles

### Profile 1: `qe_fidelity` — reproduce HAFiscal-QE methodology with current code

Goal: re-do the original HAFiscal-QE estimation as faithfully as the
current code permits. Use MC throughout, ESC interpretation, legacy GICx.

```bash
HAFISCAL_INTERPRETATION=ESC
HAFISCAL_GICX_MODE=legacy        # 3-D NM with GICx as free param (QE original)
HAFISCAL_NM_START_FROM_SAVED=0   # heuristic defaults (no warm-start)
HAFISCAL_NM_XATOL=1e-4           # QE-original tighter tolerance
extra_flags="--mc-only"          # Step 5 in MC
```

Wall time: ~12-24 hours (MC throughout, tight NM tolerance, no speedups).

Caveats: even under this profile, the result may differ from original
HAFiscal-QE because non-toggleable code paths have shifted (HARK 0.17.x
semantics differ from 0.14.1; see the `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`
branch lineage; subsequent BUG-031/032/033/034/036/038 fixes are in
the code regardless of this profile). Deeper fidelity would require
checking out the legacy HARK 0.14.1 + legacy code at QE submission
vintage. The `qe_fidelity` profile gets us as close as configurable.

### Profile 2: `production_current` — what's currently default; baseline for comparison

Goal: snapshot of what `./reproduce.sh --comp full` does TODAY without
any profile flag. Useful for A/B comparison vs other profiles.

```bash
HAFISCAL_INTERPRETATION=CDC
HAFISCAL_GICX_MODE=legacy
HAFISCAL_NM_START_FROM_SAVED=0
HAFISCAL_NM_XATOL=1e-2
# Step 5 in TM-a (current default; no flag needed)
```

Wall time: ~6-12 hours (current observed).

### Profile 3: `production_fast` — same methodology as current + BUG-039 + speedups

Goal: same answers as `production_current` but with the speedups
landed in the BUG-039 plan (hardcoded GICx, warm-start, parallel
multistart).

```bash
HAFISCAL_INTERPRETATION=CDC
HAFISCAL_GICX_MODE=hardcoded     # BUG-039 fix (Phase A)
HAFISCAL_NM_START_FROM_SAVED=1   # BUG-039 Phase E
HAFISCAL_WRAPPER_MULTISTART_POINTS=1  # BUG-039 Phase F
HAFISCAL_NM_XATOL=1e-2
# Step 5 in TM-a (default)
```

Wall time: ~3-6 hours (about 50% of `production_current`).

Acceptance: `production_fast` and `production_current` should produce
the same converged (β, ∇) within NM tolerance. If not, BUG-039 fix or
the other speedups have a problem.

**Dependency**: requires BUG-039 Phases A, E, F to be landed.

### Profile 4: `tm_throughout_fast` — TM-a everywhere, maximum speed

Goal: minimize wall time using TM-a throughout (including Step 2
estimation), accepting the level-vs-normalized methodology trade-off
discussed in `2026-05-02_tm-vs-mc-methodology-distinction-for-step-2-fit.md`.

```bash
HAFISCAL_INTERPRETATION=CDC
HAFISCAL_STEP2_METHOD=tm_a       # NEW: dispatch to estim_phase2_tm_a.py
HAFISCAL_GICX_MODE=hardcoded
HAFISCAL_NM_START_FROM_SAVED=1
HAFISCAL_WRAPPER_MULTISTART_POINTS=1
HAFISCAL_NM_XATOL=1e-2
# Step 5 in TM-a (default)
```

Wall time: ~1-2 hours (TM-a is much faster per NM eval than MC).

Caveat: the TM-a Step-2 fits normalized-Lorenz against level-Lorenz
data target — see the methodology conclusion log. For HS the resulting
(β, ∇) is within ~0.5% / ~0.8% of MC; for D and C the difference is
larger (~5% / ~13-17%). Acceptable for fast-turnaround / exploratory
work; not for paper-canonical reporting.

**Dependency**: requires BUG-039 Phases A, E, F + introducing
`HAFISCAL_STEP2_METHOD` dispatch (small new piece of code, beyond
BUG-039).

### Profile 5: `mc_throughout_validation` — MC everywhere for methodology cross-check

Goal: validate `production_current`/`production_fast` by running the
canonical MC pipeline end-to-end (Step 5 in MC instead of TM-a).
Compare Step-5 multipliers MC vs TM-a to bound the methodology gap.

```bash
HAFISCAL_INTERPRETATION=CDC
HAFISCAL_GICX_MODE=legacy
HAFISCAL_NM_START_FROM_SAVED=0
HAFISCAL_NM_XATOL=1e-2
extra_flags="--mc-only"          # Step 5 in MC
```

Wall time: ~6-12 hours.

## Approach

### Phase 1: Add `--profile NAME` dispatch to reproduce.sh (~1.5 hr)

Edit `reproduce.sh` option parser (around line 2432-2566):

```bash
--profile)
    shift
    PROFILE="$1"
    case "$PROFILE" in
        qe_fidelity)
            export HAFISCAL_INTERPRETATION=ESC
            export HAFISCAL_GICX_MODE=legacy
            export HAFISCAL_NM_START_FROM_SAVED=0
            export HAFISCAL_NM_XATOL=1e-4
            extra_flags+=" --mc-only"
            ;;
        production_current)
            export HAFISCAL_INTERPRETATION=CDC
            export HAFISCAL_GICX_MODE=legacy
            export HAFISCAL_NM_START_FROM_SAVED=0
            export HAFISCAL_NM_XATOL=1e-2
            ;;
        production_fast)
            export HAFISCAL_INTERPRETATION=CDC
            export HAFISCAL_GICX_MODE=hardcoded
            export HAFISCAL_NM_START_FROM_SAVED=1
            export HAFISCAL_WRAPPER_MULTISTART_POINTS=1
            export HAFISCAL_NM_XATOL=1e-2
            ;;
        tm_throughout_fast)
            export HAFISCAL_INTERPRETATION=CDC
            export HAFISCAL_STEP2_METHOD=tm_a
            export HAFISCAL_GICX_MODE=hardcoded
            export HAFISCAL_NM_START_FROM_SAVED=1
            export HAFISCAL_WRAPPER_MULTISTART_POINTS=1
            export HAFISCAL_NM_XATOL=1e-2
            ;;
        mc_throughout_validation)
            export HAFISCAL_INTERPRETATION=CDC
            export HAFISCAL_GICX_MODE=legacy
            export HAFISCAL_NM_START_FROM_SAVED=0
            export HAFISCAL_NM_XATOL=1e-2
            extra_flags+=" --mc-only"
            ;;
        *)
            echo "Unknown profile: $PROFILE"
            echo "Valid profiles: qe_fidelity, production_current, production_fast, tm_throughout_fast, mc_throughout_validation"
            exit 1
            ;;
    esac
    log INFO "Profile: $PROFILE — env vars exported, extra_flags='$extra_flags'"
    ;;
```

Update `show_help()` (around line 1004-1100) with a `PROFILES` section
listing all 5 profiles, their objectives, dependency notes, and
approximate wall times.

Update `reproduce_full_*_results()` functions to use the `extra_flags`
variable so that flags from a profile compose with the existing scope
(e.g., `--comp full --profile mc_throughout_validation` should run the
full-scope MC-only pipeline).

### Phase 2: Per-profile nano-smoke validation (~1 hr total)

For each profile, run `./reproduce.sh --comp nano --profile NAME` to
confirm the env-var dispatch works (nano scope is fast, just checks
that the pipeline launches with the right env vars set).

Acceptance:
- All 5 profiles complete `--comp nano` without error
- The logged "Profile: X — env vars exported" line shows correct settings
- For profiles with dependencies on BUG-039 (3 and 4), if BUG-039 isn't
  landed yet, the profile should fail with a clear message ("Profile
  production_fast requires BUG-039 Phase A; please land BUG-039 first
  or use a different profile")

### Phase 3: Documentation (~30 min)

Add a section to README.md describing the profile system at a high level:
- "What's a profile and when to use one"
- The 5 profiles' objectives + wall times
- Pointer to this plan for details

Update `reproduce/README.md` with the same info from a script-internals
perspective.

## Sequencing

Phase 1 (dispatch) → Phase 2 (validation) → Phase 3 (docs).

If BUG-039 Phases A, E, F aren't yet landed, we can either:
- (a) Land Phase 1 with profiles 3 and 4 stubbed-out
- (b) Wait for BUG-039 to land first, then do Phase 1 with all 5 profiles

Recommendation: (a). Profiles 1, 2, 5 don't depend on BUG-039 and are
useful immediately. Profiles 3, 4 can be added in a follow-up commit
once BUG-039 lands.

## Estimated total: ~3 hours focused work + ~1 hour validation

## Commit strategy

Two commits:

1. `reproduce.sh: add --profile NAME with profiles 1, 2, 5` (no
   BUG-039 dependency)
2. `reproduce.sh: add profiles 3 (production_fast) and 4
   (tm_throughout_fast)` (after BUG-039 lands)

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| `extra_flags` interaction with existing flags is fragile | Med | Test each profile against each `--comp` scope; document any incompatibilities |
| Profile name collision with future flag names | Low | Profile names are `snake_case`, flags are `--kebab-case` — no syntactic overlap |
| User runs profile without realizing the wall-time implications | Med | log INFO at start with explicit "this profile is expected to take ~Xh" message |
| `qe_fidelity` profile claims to match QE but doesn't (due to non-toggleable code drift) | High | Documented explicitly in profile description AND in show_help; flag this as a known limitation |
| Profile sets an env var that conflicts with one the user already exported | Med | Document that `--profile` env vars OVERRIDE pre-existing ones; alternatively warn if pre-existing ones are detected |

## What this plan does NOT do

- Doesn't validate methodology of any profile (each profile's smoke
  test only confirms the pipeline launches; comparing across profiles
  is its own work)
- Doesn't introduce new methodological options — only bundles existing ones
- Doesn't change the default behavior of `reproduce.sh` (profiles are
  opt-in)
- Doesn't make any HAFISCAL_* env var the default — all defaults stay
  as today

## Future profile additions (suggested for later, not in this plan)

- `splurge0_robustness` — `Splurge=0` for the Online Appendix robustness check
- `crra1` / `crra3` — alternative CRRA values for sensitivity analysis
- `lower_ub_no_b` — alternative unemployment benefit structure
- `recovery_horizon` — alternative recession-recovery horizons
- `cohort_qmethod` — explicit profile for q_method='cohort' (currently
  the default; might want an explicit one for documentation)

## References

- BUG-039 plan: `plans/20260502-1145h_fix-BUG-039-GICx-NM-options.md`
  (this plan was originally Phase H of that one)
- BUG-039 dossier: `BUGS_private/HAFiscal_BUG-039_GICx_unconditionally_optimized.md`
- TM-vs-MC methodology note (relevant to `tm_throughout_fast` caveat):
  `conclusions_private/2026-05-02_tm-vs-mc-methodology-distinction-for-step-2-fit.md`
- Saved-cal staleness diagnosis (relevant to all profiles' Step-2 outputs):
  `conclusions_private/2026-05-01_saved-step2-cal-stale-due-to-bug-034.md`
- Current `reproduce.sh`: `reproduce.sh` (3297 lines)
- Current help text site: `reproduce.sh:995-1103`
- Current option-parsing site: `reproduce.sh:2432-2566`
