We are constructing a dolo-plus / Bellman-DDSL YAML for the HAFiscal household problem
whose focused spec you parsed earlier in THIS session. This turn settles the SPLURGE
treatment. Prose alongside any YAML is welcome.

IMPORTANT INTERPRETATION CHANGE vs the spec you were given. The spec in this session
(`HAFiscal-bellman-for-matsya.md`, §6 and §7.2, "Version A") models the splurge as a
BUDGET DEDUCTION: `a = m - c_sp - c_opt`. That is the "CDC" (single-household bargain)
reading. We are NOT using it. We are using the **ESC / "bound-pair" (Campbell–Mankiw)**
reading, in which the splurge does NOT enter the optimizer's budget at all. Please
OVERRIDE spec §6/§7.2 accordingly for everything below.

## The ESC (bound-pair) interpretation

The household is two ACTUALLY-DISTINCT sub-households sharing one permanent-income
label `p_tot`:

- OPTIMIZER sub-household, mass `(1-ς)`: receives income share `(1-ς)·Y_tot`, holds the
  ENTIRETY of household assets, and solves a STANDARD CRRA buffer-stock problem over its
  own resources. Its asset rule is the textbook `a = m - c_opt` (HARK default
  `aNrm = mNrm - cNrm`). NO splurge term in its budget or Euler.
- SPLURGER sub-household, mass `ς`: receives income share `ς·Y_tot`, holds ZERO assets,
  and consumes her entire income `c_spl = ς·Y_tot`. This is a separate ledger that NEVER
  touches the Optimizer's assets.

Total household consumption `C_tot = c_opt + ς·Y_tot` is an observable used ONLY by the
(out-of-scope) welfare aggregator.

## Two decisions already made (do NOT re-open)

1. NORMALIZATION = "Convention 1": the YAML stage represents the OPTIMIZER sub-household,
   normalized by its OWN permanent income `p_opt = (1-ς)·p_tot`. A convenient consequence
   (the `(1-ς)` cancels): the Optimizer's normalized transitory shock equals the
   household's `ξ_tot`, so the stage's transitory shock symbol `theta` is just `ξ_tot`.
   Household-total assets/consumption are recovered OUTSIDE the YAML via the `(1-ς)`
   factor. This matches HARK's running ESC code (`aNrm = a_tot/(1-ς)`).
2. The SPLURGE IS FULLY OUT-OF-YAML. The Splurger sub-household and `C_tot = c_opt+ς·Y_tot`
   are computed by the Python orchestrator (exactly like welfare). The YAML household
   stage is therefore the PURE canonical buffer-stock for the Optimizer, with ZERO
   splurge reference in any equation. `ς` appears only as a documented OUT-OF-SCOPE
   preamble comment.

## Locked stage architecture (background)

SINGLE stage `hafiscal_household`, modeled on canonical `ConsMarkov_stage.yaml`, four
perch movers (`arvl_to_dcsn_transition`, `dcsn_to_cntn_transition`, `cntn_to_dcsn_mover`,
`dcsn_to_arvl_mover`). Continuous state `m_check`; flat joint Markov state `z`; single
control `c_opt`; shocks `psi`, `theta`; CRRA reward over `c_opt` only; `Γ̂^(1-γ)` factor
inside the expectation; effective discount `β·LivPrb`. (AD coupling via `ADF`, the joint
Markov flattening, and the Cratio state come in later turns — not this one.)

## Questions (label answers Q1..Q4 + a VERDICT block)

Q1. Under the ESC bound-pair reading, is the correct DDSL encoding simply the canonical
    single-stage buffer-stock (the `ConsMarkov_stage.yaml` pattern with `a = m - c_opt`),
    with the Splurger sub-household and `C_tot` handled entirely OUTSIDE the YAML? I.e.,
    confirm there is NO splurge term anywhere in the stage equations. If you disagree,
    say exactly why.

Q2. Is a Campbell–Mankiw "rule-of-thumb + optimizer" split idiomatically represented in
    Bellman-DDSL as TWO separate agents/stages (only the optimizer's stage written here)
    rather than one stage carrying both consumptions? Is there any DDSL construct for a
    second, non-optimizing sub-agent, or is keeping it orchestrator-side the right call?

Q3. Given normalization Convention 1 (stage normalized by `p_opt`, so the stage's `theta`
    already equals `ξ_tot`), is there ANY residual place in the OPTIMIZER stage where the
    splurge parameter `ς` must appear? I believe the answer is no — confirm or correct.

Q4. Closest KB example to a pure buffer-stock stage whose "second consumer" (a fixed
    rule-of-thumb spender) is handled outside the optimized stage? Cite the KB filepath.

## Deliverable

(a) A one-line VERDICT: does the ESC reading reduce the household stage to the pure
    canonical buffer-stock with zero splurge reference (yes/no), and is `ς` absent from
    all stage equations (yes/no)?
(b) Draft the 2–4 line OUT-OF-SCOPE preamble COMMENT block (YAML `#` comments) that should
    sit atop the final YAML documenting the splurge as orchestrator-side: name the
    Splurger sub-household, `C_tot = c_opt + ς·Y_tot`, the `(1-ς)` household-total
    rescaling, and that `ς` (ESC value ≈ 0.2672) is calibration-only and absent from the
    stage.
