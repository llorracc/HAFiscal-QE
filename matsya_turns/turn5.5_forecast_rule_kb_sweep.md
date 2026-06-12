# Turn 5.5 — KB sweep for forecast-rule / Krusell-Smith precedent

Grep over `/home/shared/github/bright-forest/bellman-ddsl` for
`krusell.smith | aggregate_consistency | forecast_rule | ALM | aggregate law of motion`.

RESULT: matches appear ONLY in theory/literature/presentation/roadmap files
(`AI/context/mdp.tex`, `shanker-thesis/chap{2,3,4}.tex`, Dyn-X presentations,
`AI/claude.md`, `07-execution-pipeline.md`). **ZERO matches in any `docs/examples/`
canonical stage YAML.**

DECISION (confirms locked architecture #2): there is NO canonical dolo-plus example of an
in-YAML forecast rule / aggregate_consistency block. Therefore:
  - Keep `Cratio_d` as a continuous STATE (option a), `CRule` as a parameter, AD fixed
    point EXTERNAL (orchestrator). Do NOT add an `aggregate_consistency`/`forecast_rule`
    block to the YAML.
  - Do NOT downgrade Cratio to a time-varying exogenous parameter (option b) — the 2D
    cFunc(m, Cratio) fidelity is required and there's no canonical block to host the rule
    anyway.

This is honestly a DDSL extension (Cratio-state + CRule-parameter + external loop); flag
as such in the final YAML header.
