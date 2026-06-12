# Plan: Produce a Dolo-Plus / Bellman-DDSL YAML Description of HAFiscal Using Matsya

**Generated**: 2026-06-03
**Reference exemplar**: `/home/shared/github/llorracc/Dupor2023-bn/matsya-exercise/` (worked example from the matsya session run 2026-06-02)
**Assignment template**: `/home/shared/github/llorracc/workspace-course-topics/assignments/matsya-ballpark-dolo-plus-draft.md`
**Course workflow**: `/home/shared/github/llorracc/workspace-course-topics/workflows/use-matsya.md`

---

## 0. Context — what already exists

A first pass through this pipeline has already happened (commit `c6b255b2` "matsya session: critique framework, appendix revisions, GIC fix, splurge bug report"). Surviving artifacts:

| Path | What it is | Status |
|---|---|---|
| `HAFiscal-bellman-for-matsya.md` (328 lines) | Focused mathematical spec of the household Bellman (notation, timing, Markov state, income map, splurge, normalized recursion, perpetual youth, EGM solution method, calibration). Ready for matsya. | **Authoritative** |
| `HAFiscal-doloplus-from-matsya.yaml` (396 lines, mostly matsya prose around an embedded YAML) | Matsya's first-pass dolo-plus YAML attempt. Matsya itself flagged it as PROVISIONAL with "Several features: UNRESOLVED". Wrapped in a markdown narrative rather than a clean standalone YAML. | **Draft / needs replacement** |
| `reproduce/matsya_submit_bellman_spec.py` | One-shot script that submits `HAFiscal-bellman-for-matsya.md` to matsya session `HAFiscal-Latest` | Reusable |
| `reproduce/matsya_submit_upstream_review.py` | Follow-up: asks matsya whether post-spec upstream code changes affect its critique | Reusable |

**The session name in use is `HAFiscal-Latest`** (see `SESSION = "HAFiscal-Latest"` in both scripts). Reuse this session string for **every** `matsya` call below.

**Target shape** (from the Dupor2023-bn exemplar `HouseholdChoice.yaml`): a clean ~80-150 line YAML with:

```yaml
name: hafiscal_household
symbols:
  spaces:        # type definitions
  prestate:      # arrival-perch state
  states:        # decision-perch state (constructed)
  poststates:    # continuation-perch state
  controls:      # decision variables
  exogenous:     # shock distributions
  values:        # V[<], V, V[>], dV[<], dV, dV[>]
  parameters:    # all calibrated scalars
  settings:      # grid sizes etc.
equations:
  arvl_to_dcsn_transition: |
    ...
  dcsn_to_cntn_transition: |
    ...
  cntn_to_dcsn_mover:
    Bellman: |
      V = max_{c, ...}{ u(c, ...) + beta * V[>] }
    MarginalBellman: |
      dV = ...
  dcsn_to_arvl_mover:
    Bellman: |
      V[<] = E_{...}(V)
    ShadowBellman: |
      dV[<] = E_{...}(dV)
calibration:
  ...
```

The HAFiscal version will be more complex than Dupor's (HAFiscal has splurge, perpetual youth, permanent-income normalization, multi-DiscFac heterogeneity), but the **stage decomposition** is the same skeleton.

## 1. Prerequisites (check once)

```bash
# (a) Matsya client installed
which matsya || pip install git+https://github.com/econ-ark/matsya.git

# (b) Token configured (must already be set; if not, see matsya-configure-anthropic-key.md)
test -n "$MATSYA_TOKEN" || cat ~/.config/matsya/config.toml | grep token

# (c) Repo state clean (no uncommitted matsya-related files)
git -C /home/shared/github/llorracc/HAFiscal-Latest status -- '*matsya*' '*doloplus*'

# (d) Session exists on server (warm-up query, no real work)
matsya "Confirm you have my HAFiscal-Latest session loaded with the household Bellman spec from HAFiscal-bellman-for-matsya.md. Reply with the date you first saw it." --session HAFiscal-Latest
```

If step (d) fails or returns "no prior context," re-submit the spec via `python reproduce/matsya_submit_bellman_spec.py`.

## 2. Step-by-step (mirrors the assignment §3 workflow, adapted)

### Step 1 — Reconfirm the source spec

The spec is `HAFiscal-bellman-for-matsya.md`. Read it and decide whether anything has shifted since commit `c6b255b2`:

```bash
git -C /home/shared/github/llorracc/HAFiscal-Latest log --oneline -- HAFiscal-bellman-for-matsya.md
# If the file matches c6b255b2 and matsya's session is warm, skip to Step 2.
# If the spec needs updates (e.g., to reflect calibration changes or bug fixes
# in Subfiles/*.tex since c6b255b2), edit HAFiscal-bellman-for-matsya.md FIRST,
# commit, then re-submit:
python reproduce/matsya_submit_bellman_spec.py
```

**Stop here and review** any spec edits before continuing. The whole exercise relies on matsya's input being faithful to the paper.

### Step 2 — Matsya: stage decomposition

Ask matsya to produce a stage decomposition (arrival / decision / continuation), exactly like the Dupor2023-bn `household-bellman-problem.md` example.

```bash
matsya "Based on HAFiscal-bellman-for-matsya.md, break the household problem into stages (arrival, decision, continuation perches). For each perch list: state variables, controls, exogenous draws, transitions in/out. Then produce a stage-flow diagram (ASCII like the Dupor2023 example). Identify where the splurge mechanic fits in the stage flow (does it consume part of m at the decision perch, or modify the budget constraint, or is it a pre-decision deduction from market resources?). Be explicit about what is pre-decision vs post-decision." --session HAFiscal-Latest
```

**Expected output**: A stage decomposition with the splurge placement made unambiguous. If matsya says it needs more info, edit `HAFiscal-bellman-for-matsya.md` to add what it asked for (sourced from the paper, especially `Subfiles/Model.tex`), commit, re-submit, and re-ask.

**Halt criterion**: If matsya cannot locate the splurge in the stage flow on the second attempt, escalate to a manual stage walk-through — write the stage flow yourself first (using §6 of the spec), commit it, then ask matsya to validate.

### Step 3 — Matsya: confirm YAML readiness, then generate the YAML

```bash
matsya "Given the stage decomposition you just produced, do you have enough information to construct a dolo-plus / Bellman-DDSL YAML for the HAFiscal household stage? If yes, produce the YAML in the same format as the canonical buffer_stock and ConsMarkov_mdp examples in your knowledge base. If no, enumerate exactly what additional information you need from HAFiscal-bellman-for-matsya.md or the paper itself." --session HAFiscal-Latest
```

**Expected output**: Either a YAML or a precise list of gaps. If gaps, fix them in the spec, commit, re-submit, repeat.

When the YAML lands, **extract it to a clean file**:

```bash
# Matsya wraps YAML in a markdown response. Extract just the YAML block:
matsya "Repeat your dolo-plus YAML for HAFiscal household as the ENTIRE response, no preamble, no postscript, no commentary, no markdown code fences. Just raw YAML starting with 'name:' on the first line." --session HAFiscal-Latest > HAFiscal-doloplus-draft.yaml

# Sanity check the extraction:
head -3 HAFiscal-doloplus-draft.yaml  # should start with 'name: hafiscal_household'
yq eval . HAFiscal-doloplus-draft.yaml  # should parse without error (requires yq)
```

**Validation gate**: the YAML must:
1. Parse as valid YAML
2. Contain top-level keys `name`, `symbols`, `equations`, `calibration`
3. Have all five perches mentioned (`arvl_to_dcsn_transition`, `cntn_to_dcsn_mover`, `dcsn_to_cntn_transition`, `dcsn_to_arvl_mover`) in `equations:` if a single-stage formulation; or multiple stage blocks if multi-stage
4. Include the splurge mechanic in either the income-map definition or as a pre-decision transition

If any gate fails, return to Step 3.

### Step 4 — Matsya: SMD-style markdown improvement

Ask matsya to clean up `HAFiscal-bellman-for-matsya.md` (or produce a sibling improved file) using the SolvingMicroDSOPs structure as a template:

```bash
matsya "I'd like you to improve HAFiscal-bellman-for-matsya.md using Carroll's SolvingMicroDSOPs lecture notes (especially Sections 12-13 on multiple controls and modular stage architecture) as the structural template. Produce a new markdown organized as: §1 Timing within a period (numbered perches like Dupor2023), §2 Stage flow diagram, §3 State and control spaces (table), §4 Step 1: Arrival → Decision transition, §5 Step 2: The decision problem (Bellman), §6 Step 3: Decision → Continuation transition, §7 Step 4: Continuation → Arrival mover (expectation), §8 Structural summary table (HAFiscal-specific design choices in DDSL terms). Keep all the HAFiscal content (Markov UI states, splurge, perpetual youth, normalization) — just reorganize. Output the FULL markdown, no commentary outside it." --session HAFiscal-Latest > HAFiscal-bellman-smd-organized.md
```

**Sanity check**: outline the result and compare to `Dupor2023-bn/matsya-exercise/household-bellman-problem.md`'s outline:

```bash
grep -nE '^#' HAFiscal-bellman-smd-organized.md
grep -nE '^#' /home/shared/github/llorracc/Dupor2023-bn/matsya-exercise/household-bellman-problem.md
```

They should have a similar shape (1 Timing → 2 Diagram → 3 State table → 4 Arrival→Decision → 5 Bellman → 6 Decision→Continuation → 7 Continuation→Arrival → 8 Summary).

### Step 5 — Critique pass (specific to HAFiscal's complexity)

HAFiscal has three features that the prior matsya pass flagged as "UNRESOLVED." Ask matsya specifically about each, one per turn:

```bash
# 5a. Splurge
matsya "In the YAML you produced, exactly where does the splurge appear? The splurge is a mechanical (non-optimized) consumption component that depends on current income but does NOT enter utility. In dolo-plus DDSL, what is the cleanest way to express a mechanical consumption-flow that affects the budget constraint but is not a control? Is there a 'definitions' or 'auxiliary' block I should use?" --session HAFiscal-Latest

# 5b. Permanent-income normalization (Γ̂^(1-γ) factor)
matsya "The HAFiscal Bellman uses permanent-income normalization: V(m, p, z) = p^(1-γ) v̌(m̌, z). The continuation value in normalized space picks up a Γ̂^(1-γ) factor. In dolo-plus, is there a canonical way to express this homogeneity-of-degree-(1-γ) trick, or does the YAML simply embed the factor directly in the cntn_to_dcsn_mover Bellman line?" --session HAFiscal-Latest

# 5c. Perpetual youth
matsya "HAFiscal uses perpetual-youth mortality: with probability D the agent dies and is replaced. The effective per-period discount is β*(1-D). In dolo-plus, do I encode this as (a) a modified beta in the calibration, (b) a Markov state with absorbing death, or (c) something else? What's the cleanest pattern that matches DDSL conventions?" --session HAFiscal-Latest
```

For each, edit the YAML (`HAFiscal-doloplus-draft.yaml`) to apply matsya's recommendation. Commit each fix as a separate logical step so the diff is reviewable.

### Step 6 — Manual verification against the paper

Compare matsya's outputs against the actual paper (`HAFiscal.tex` + `Subfiles/Model.tex`):

- Does the YAML's income map match `Subfiles/Model.tex`'s `Subsection 2.2: Income Process`?
- Does the Markov transition matrix in the YAML match `Subfiles/Model.tex`'s definition of π_eu, π_ue, UI exhaustion?
- Are the calibrated values in the YAML's `calibration:` block consistent with `Code/HA-Models/FromPandemicCode/Parameters.py`?
- Is the perpetual-youth mortality consistent with `T_age=200` + LivPrb in Parameters.py?

Write a one-paragraph verification note like the Dupor2023-bn pattern, e.g. `HAFiscal-doloplus-verification.md`, listing what was accepted / edited / rejected from matsya's output.

### Step 7 — Optional: ask matsya to write out the math from the YAML

This is the "YAML → math" round-trip the assignment recommends as a quality check:

```bash
matsya "From the dolo-plus YAML for HAFiscal you produced, write out the math (full Bellman equation, transitions, expectation, marginal value) in LaTeX/markdown notation. Use the SolvingMicroDSOPs notation conventions. The output should be a self-contained document that someone could read in isolation without referring back to the YAML." --session HAFiscal-Latest > HAFiscal-bellman-from-yaml.md
```

Then **diff this against `HAFiscal-bellman-for-matsya.md`** to check for round-trip drift. Discrepancies indicate either (a) the YAML lost information or (b) the spec had ambiguity that matsya resolved one way and now hard-codes the other way. Either case is informative.

## 3. Deliverables (commit + PR pattern)

A clean branch + commit + PR per the assignment's §Deliverable section:

| File | Status | Notes |
|---|---|---|
| `HAFiscal-bellman-for-matsya.md` | EXISTS, may be UPDATED in Step 1 | The authoritative paper-derived spec |
| `HAFiscal-bellman-smd-organized.md` | NEW from Step 4 | SMD-structured version |
| `HAFiscal-doloplus-draft.yaml` | NEW from Step 3 | Clean standalone YAML |
| `HAFiscal-bellman-from-yaml.md` | OPTIONAL, NEW from Step 7 | YAML → math round-trip |
| `HAFiscal-doloplus-verification.md` | NEW from Step 6 | One paragraph: accepted/edited/rejected |
| `HAFiscal-doloplus-from-matsya.yaml` | EXISTING DRAFT | Move to `archived_matsya_drafts/c6b255b2_doloplus.yaml` or delete; flag in PR |

PR description must include:
- Matsya session name: `HAFiscal-Latest`
- Date range of matsya calls
- The verification paragraph (or pointer to the file)

## 4. Failure modes + recovery

| Failure | Likely cause | Recovery |
|---|---|---|
| `matsya` returns 504 timeout on a large prompt | Prompt too long for one turn | Break into smaller prompts; re-submit; if session-context confusion, start a fresh `--session HAFiscal-Latest-v2` |
| Matsya says "I don't have HAFiscal-bellman-for-matsya.md in context" | Session forgot or never had the spec | Re-run `python reproduce/matsya_submit_bellman_spec.py` to re-submit |
| YAML doesn't parse | Matsya inserted prose into the YAML block | Re-ask with the "raw YAML, no commentary" wording from Step 3 |
| Splurge / normalization / perpetual-youth feature has no clean DDSL pattern | Genuine DDSL gap | Add an inline YAML comment flagging it; document in the verification paragraph; consider opening an issue against `econ-ark/Matsya` for DDSL extension |
| The YAML differs structurally from Dupor2023-bn's `HouseholdChoice.yaml` | Either HAFiscal genuinely needs different structure, or matsya regressed | Diff the two files; ask matsya explicitly to use Dupor's pattern as a template |

## 5. Open questions for the user

1. **Does the existing `HAFiscal-doloplus-from-matsya.yaml` need to be preserved as-is (archived) or can it be overwritten?** The new clean YAML should be a separate file (`HAFiscal-doloplus-draft.yaml`) — but I want to confirm whether the legacy file has any independent value.

2. **Single-stage or multi-stage YAML?** HAFiscal's household problem fits a single decision perch (joint consumption + saving, no separate labor-supply stage). But the recession dynamics could be framed as multi-stage (normal stage / recession-entry stage / recession stage / recovery stage). Does the user want the simpler single-stage version, or should we attempt multi-stage to capture the AD-coupled recession structure?

3. **Should the matsya output include the AD aggregate state Z and Cratio fixed-point?** This is partial-equilibrium-of-the-household given Z, or general-equilibrium with Z endogenous. The Dupor exemplar is partial-equilibrium (w, r, D, T are exogenous to the household). Recommend doing partial-equilibrium first (cleaner YAML), with the AD outer loop documented separately.

4. **Calibration values in the YAML — Baseline or which sensitivity?** The Dupor exemplar has illustrative defaults (β=0.96 etc.) that don't match any specific paper run. HAFiscal has multiple parametrizations (Baseline, HS_Only, CRRA1, ...). Recommend defaulting to Baseline values (β-grid from `Results/`, urate from Parameters.py).

## 6. Estimated effort

| Step | Wall time | Notes |
|---|---|---|
| Step 1 — spec review | 10-30 min | Mostly reading; resubmit only if changed |
| Step 2 — stage decomposition | 5-20 min | One matsya turn + possibly one edit-resubmit cycle |
| Step 3 — YAML generation | 10-30 min | Two matsya turns (one to confirm readiness, one to generate); extraction is mechanical |
| Step 4 — SMD-style markdown | 5-15 min | One matsya turn (longer prompt, longer response — may bump 504 timeout, see §4) |
| Step 5 — critique passes | 10-30 min | Three short matsya turns + corresponding YAML edits |
| Step 6 — manual verification | 30-90 min | Reading paper sections + cross-checking parameters |
| Step 7 — round-trip (optional) | 10-20 min | One matsya turn + diff |
| **Total** | **~1.5-4 hours** | Dominated by Step 6 (manual paper reading), not matsya wait time |

Matsya per-query wall is "tens of seconds to a few minutes" per the assignment notes — substantial pause expected on each turn.

---

## To execute this plan

Future-me (or you) can invoke it with:

> *"execute the plan in plan_hafiscal_dolo_plus_via_matsya.md"*

The plan is self-contained: paths are absolute, the matsya session name is fixed (`HAFiscal-Latest`), commands are copy-pasteable, validation gates are concrete, and the deliverables list is enumerated. Each step has a halt criterion so a failure surfaces a specific question to escalate rather than silently producing wrong YAML.
