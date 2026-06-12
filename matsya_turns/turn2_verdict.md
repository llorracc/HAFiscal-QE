# Turn 2 verdict — Splurge treatment under ESC (bound-pair)

Decision context: user switched CDC→ESC and chose (1) Convention-1 normalization,
(2) splurge FULLY out-of-YAML. So Turn 2 is a confirmation turn, not a budget-encoding
turn. Reviewers reframed accordingly.

| # | Reviewer | Verdict | Reason |
|---|----------|---------|--------|
| 1 | ESC asset-rule correctness | PASS | matsya confirms `a = m - c_opt` (HARK default), no `c_sp` in budget — matches `(eq:budget-ESC)` / `models_CDC_and_ESC.md` §5.2. |
| 2 | ς-absent-from-stage (math) | PASS | Q3 cancellation verified independently: `θ_opt = (1-ς)·ξ·p_tot / [(1-ς)·p_tot] = ξ_tot`. ς survives nowhere in the optimizer stage. |
| 3 | No re-opening locked architecture | PASS | matsya stayed single-stage, four movers, orchestrator-side splurge; did not propose multi-stage or a co-resident sub-agent inside the stage. |
| 4 | OUT-OF-SCOPE preamble completeness | PASS | Block names: Splurger sub-household, `C_tot = c_opt + ς·Y_tot`, `(1-ς)` rescaling, ς calibration-only & absent from stage. All four required items present. |
| 5 | Campbell–Mankiw idiom | PASS | matsya: no DDSL construct for a non-optimizing co-resident; optimizer-stage-only is idiomatic; nearest precedent = Benhabib "canonical stage + orchestrator-side per-agent machinery". |

HALT criteria (original Turn 2): "Encoding C only" / "ADF dropped" — both MOOT under the
out-of-YAML decision (no splurge term to encode; ADF handled in Turn 6 income, not here).

CAVEAT (logged, non-blocking): matsya flagged `ConsMarkov_stage.yaml` as PROVISIONAL —
its KB retrieved only `ConsMarkov_mdp.md`. The canonical exemplar exists locally at
`/home/shared/github/bright-forest/bellman-ddsl/docs/examples/HARK-models-lean-experimental/ConsMarkov_stage.yaml`
(in the "experimental" dir, weakly indexed). Pattern is sound; we drive assembly from
the local file, not matsya's KB retrieval.

RESULT: all reviewers PASS → proceed to Turn 3 (Γ̂^(1-γ) normalization).
