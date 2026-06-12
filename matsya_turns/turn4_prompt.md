Continuing the HAFiscal dolo-plus YAML (ESC bound-pair Optimizer stage). This turn
settles MORTALITY / perpetual youth — the effective discount and the out-of-scope
handling of forced death + newborn re-injection. Prose welcome.

## Facts

- Perpetual-youth mortality: per-period survival `LivPrb = 1 - D`, with `D ≈ 1/160`
  (~40-year working life). Mortality is the SAME across all employment/Markov states
  (NOT z-dependent), so `LivPrb` is a SCALAR parameter here (unlike ConsMarkov's
  `LivPrb[z_d]`).
- Spec §7.2 line 210 folds mortality into the effective discount `β_i·(1-D) = β_i·LivPrb`
  in the decision Bellman. HARK applies it as `EndOfPrdvP *= LivPrb` (AggFiscalModel.py:1857).
- The canonical exemplars write it directly in the backward builder:
  `V = max_c{ u(c) + beta * LivPrb * V[>] }`  (ConsIndShock:64, ConsMarkov:76).
- Per the locked architecture, T_age=200 forced death and newborn-pool re-injection are
  handled ENTIRELY by the simulation orchestrator and are OUT of the YAML. Only the
  `β·LivPrb` effective discount stays IN the stage. (The Bellman fixed point does not
  need the death/rebirth mass-balance — that affects the forward stationary distribution
  only.)

## Questions (label Q1..Q4 + VERDICT)

Q1. Confirm the canonical encoding of the effective discount is `beta * LivPrb` inline in
    the `cntn_to_dcsn_mover.Bellman` max (and in the `InvEuler`: `c = (beta*LivPrb*dV[>])^(-1/rho)`),
    with `LivPrb` a SCALAR parameter (= 1-D), NOT a separate `D` parameter and NOT
    z-indexed. Equivalent to `β·(1-D)`.

Q2. Is there ANY canonical Bellman-DDSL syntax for (a) T_age-style forced death at a
    maximum age, or (b) newborn-pool re-injection / birth-death mass balance? If yes, cite
    the exact KB filepath. If no canonical construct exists, confirm these belong in the
    orchestrator and are documented as OUT-OF-SCOPE in the YAML preamble.

Q3. For documenting orchestrator-handled items, is a leading `#`-comment preamble block
    the idiomatic choice, or does dolo-plus support a dedicated structured key (e.g.
    `out_of_scope:` / `notes:`) in the stage? Which do you recommend?

Q4. One comment line per out-of-scope item, or a single consolidated block? (Stylistic —
    give your recommendation for a clean final file.)

## Deliverable

(a) Verbatim YAML fragment for the `cntn_to_dcsn_mover` block (Bellman + InvEuler +
    ShadowBellman `dV = c^(-rho)`), showing `beta * LivPrb` with scalar `LivPrb`.
(b) Draft the OUT-OF-SCOPE preamble comment lines enumerating the four locked external
    items: (i) AD outer Cratio fixed point, (ii) 21-cohort beta×education sweep,
    (iii) T_age=200 forced death, (iv) newborn-pool re-injection. (This complements the
    splurge OUT-OF-SCOPE note from Turn 2.)

End with a VERDICT: the exact discount expression, the LivPrb typing (scalar), and
whether any T_age/newborn DDSL construct exists (yes+cite / no).
