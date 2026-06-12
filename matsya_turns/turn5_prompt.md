Continuing the HAFiscal dolo-plus YAML (ESC Optimizer stage). This turn settles the
JOINT MARKOV state `z` — flattening, the derived (micro/macro/recession) quantities, and
stationary-vs-dated. Prose welcome.

## Ground truth (from Parameters.py:353-434, verified)

- MICRO labor state, `J` values (bug_fix `J=6`): ordered `[E, U1, U2, U3, U4, X]`
  (0=employed; 1..4 = unemployed-with-benefits, quarters since job loss; 5=X exhaustee
  = unemployed no benefits). Built by `small_MrkvArray(E_persist, U_persist, ub=4)`:
  E→E w.p. E_persist else →U1; U_k→E w.p. (1-U_persist) else advance U_k→U_{k+1};
  U4→X or →E; X→X or →E.
- MACRO state, `M` values: (normal, recession) PAIRS per experiment period,
  `M = 2·(num_experiment_periods+1)`. EVEN macro index = normal, ODD = recession.
  Baseline has NO recession dimension: `M=1` (normal only), so `N_z = J = 6`.
  Recession scenarios: `M = 22` or `42`.
- JOINT FLAT state: `z = J·MacroMrkv + MicroMrkv` (HARK `Mrkv = num_base*Macro + Micro`).
  Inversely: `MicroMrkv = z mod J`, `MacroMrkv = z // J`, `RecState = (MacroMrkv mod 2 == 1)`
  (verified vs `get_states`: `MicroMrkvPcvd = Mrkv mod num_base + num_base*(MrkvPcvd // num_base)`).
- The joint `N_z × N_z` transition is `make_hierarchical_mrkv_array(MacroMrkvArray,
  CondMrkvArrays)` — a single flat row-stochastic array.

## What the derived quantities are FOR

- `MicroMrkv` → selects the income value `ŷ(z)` (E: transitory shock; U1..U4: ρ_b
  replacement; X: ρ_nb). In the canonical ConsMarkov pattern this is handled by indexing
  `IncShkDstn[z]` directly on the flat `z`, so no explicit `MicroMrkv` extraction is
  needed.
- `RecState` → gates the AD factor `ADF = Cratio^(RecState·κ)` (next turn). This DOES need
  a per-`z` recession flag.

## Questions (label Q1..Q5 + VERDICT)

Q1. Confirm the canonical flat-Z encoding is a single exogenous Markov declaration
    `z: ["@in Z", "@dist Categorical(MrkvArray[z_prev])"]` over the joint `N_z×N_z` array
    (the `ConsMarkov_stage.yaml:17-19` pattern), with `Z = @def {1,...,N_z}` and the
    hierarchical structure baked into `MrkvArray` (a calibration parameter). Yes/no.

Q2. Does Bellman-DDSL support INLINE integer `mod` and integer-division (`//`) inside a
    transition block — so I could write `MicroMrkv = z mod J`, `MacroMrkv = z // J`,
    `RecState = (MacroMrkv mod 2 == 1)` directly? If YES, cite a KB example using `mod` or
    `//`. If NO (or unsure), confirm the robust approach is PRECOMPUTED LOOKUP PARAMETERS:
    a length-`N_z` integer/boolean vector `RecState_of_z` (and, if needed, `MicroMrkv_of_z`)
    declared in `parameters` and indexed `RecState_of_z[z_d]`. This is a forward dependency
    for next turn's ADF.

Q3. Can the SAME `J=6` (bug_fix) schema cover ALL four policy scenarios (baseline / Check /
    UI-extension / TaxCut) via CALIBRATION ONLY (different `N_z`, `MrkvArray`, `IncShkDstn`,
    `RecState_of_z` per file), with NO structural change to the stage equations? The income-
    encoded UI extension (BUG-043 fix) keeps J=6 fixed and varies only IncShkDstn — confirm
    this is calibration-only.

Q4. Stationary vs dated: spec §7.5 says use the STATIONARY form (single time-invariant
    `MrkvArray`, infinite-horizon fixed point); the recession MIT-shock is an outer wrapper.
    Confirm the YAML stage uses ONE stationary `MrkvArray`, NOT a dated finite-sequence
    backward sweep.

Q5. Closest KB example to a HIERARCHICALLY-FLATTENED Markov state (two chains combined into
    one flat index)? Cite the filepath.

## Deliverable

Verbatim YAML fragments for:
  - `symbols.spaces` (`Z = @def {1,...,N_z}`) and `symbols.exogenous` (the `z` Categorical),
    plus `symbols.prestate`/`states` entries for `z_prev`/`z_d`,
  - `symbols.parameters` declarations for `MrkvArray` (`@in [0,1]^(N_z,N_z)`), `N_z`, and
    `RecState_of_z` (give its type),
  - the `arvl_to_dcsn_transition` line(s) that set `z_d = z` and obtain `RecState`
    (`RecState = RecState_of_z[z_d]` if lookup, or inline if DDSL supports mod///).

End with a VERDICT: flat-Z confirmed (yes/no); inline-mod-or-lookup decision (with the
exact `RecState` line); stationary confirmed (yes/no); policy-unification confirmed (yes/no).
