# Plan: document where the CDC interpretation is implemented in the codebase

**Date:** 2026-04-25
**Status:** Planned
**Branch:** `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` (the live CDC implementation)
**Predecessor:** `BUGS_private/HAFiscal_splurge_budget_inconsistency/models_CDC_and_ESC.md` (canonical CDC↔ESC side-by-side)

## 1. Goal

Before any code work that re-introduces the ESC / Campbell–Mankiw bound-pair interpretation as a runnable option, produce a **complete, line-anchored inventory of every place in the current codebase where the CDC / household-bargain interpretation is implemented**. The deliverable is twofold:

- **A central map document** (in `plans/`, not `BUGS_private/`, because not every change is necessarily a bug — some are interpretive substitutions that an ESC-faithful version would resolve differently) listing every CDC location with file path, line number, what was changed, what the ESC version was, and the rationale source.
- **In-code markers** at each location, of a stable greppable form (e.g., `# CDC-MOD-BUG031:` plus a short tag) so a future reader who lands in the code can find the anchor without already knowing the map exists.

When the team subsequently builds a code path that can run *either* CDC or ESC (or both, side-by-side), every CDC-direction substitution will be a known, named seam — not something that has to be rediscovered from `git log` or coauthor memory.

## 2. Reference ESC baseline

**Decision:** the ESC baseline for the diff is `origin/maintain_bound_pair_fix_splurge` (Edmund's HARK-0.17-compatible bound-pair-faithful patches). That branch is the canonical "what would ESC look like in the current HARK?" reference, and is what `models_CDC_and_ESC.md` already cites as the ESC code reference.

**Why not `master` (HARK 0.14.1)?** That's the historical pre-anything-changed code, but it (a) has the splurge-budget identity violation under either reading and (b) predates other 0.14.1→0.17.0 fixes that are independent of CDC↔ESC. Diff'ing against it would conflate three unrelated layers of change (HARK upgrade, bug fixes, CDC interpretation).

## 3. Discovery method — three independent passes

The point of multiple passes is cross-validation: anything that shows up in only one pass is worth treating with extra suspicion (likely either missed by the others or an artifact of how that pass works).

### 3.1 Diff pass

```bash
git diff origin/maintain_bound_pair_fix_splurge...0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC \
   -- Code/HA-Models/ \
   | <filter>
```

Filter to non-trivial code changes — drop pure import-shuffle, version-pin, comment-only, whitespace-only diffs. Group remaining hunks by file. Each non-trivial hunk is a candidate CDC anchor.

Caveat: the `_TM-vs-MC` branch also contains independent work that's not interpretation-related (TM-method refactors, validation harnesses, multi-seed shuffle infrastructure, etc.). The diff pass needs a per-hunk classification step — not every hunk is a CDC↔ESC substitution.

### 3.2 BUGS dossier pass

The bugs that were filed during the splurge-in-budget work are the most authoritative description of *intent* behind each change:

- `BUGS_private/HAFiscal_BUG-031_splurge_not_in_budget.md` — the asset-update fix (the central CDC-vs-ESC interpretive choice that started this).
- `BUGS_private/HAFiscal_BUG-032_lottery_splurge_formula.md` — the lottery $\varsigma$ re-estimation under the splurge-on-total-income MPC formula.
- `BUGS_private/HAFiscal_BUG-033_tm_a_indexed_refactor.md` — the a-indexed TM refactor, motivated by the CDC-direction asset interpretation.

Each dossier names the file:line of its patches. Walk all three; the union of cited locations is the BUGS-pass candidate list.

### 3.3 Doc cross-reference pass

`models_CDC_and_ESC.md` §4.3 has a **CDC code-mapping table** listing six locations that are part of the CDC implementation:

| Code variable | CDC interpretation |
|---|---|
| `pLvl`, `TranShk * AggDemandFac`, `mNrm = bNrm + ...`, `cNrm = cFunc(mNrm)` | (interpretation labels — not patches) |
| `cLvl_splurge = (1-Splurge)*cNrm*pLvl + Splurge*pLvl*TranShk*AggDemandFac` | (the consumption formula) |
| `get_poststates` override: `aNrm = mNrm - cLvl_splurge/pLvl` | (the asset-update patch — CDC's central change) |
| K/Y aggregator `Σ aLvl / Σ (pLvl·TranShk)` | (no `(1-ς)` correction → CDC reading) |

The table is illustrative, not exhaustive. Cross-check it against the §4.3 description and against the discovery passes above; flag any mismatches.

## 4. Annotation scheme

### 4.1 In-code markers

Each CDC-anchor location gets a comment line above the patch, of the form:

```python
# CDC-MOD-<BUG-NN>: <one-line summary>. ESC version: <what ESC does>. See plans/<map-doc>.md and BUGS_private/HAFiscal_BUG-<NN>_*.md.
```

Examples:

```python
# CDC-MOD-BUG031: Asset update under household-bargain reading subtracts realized weighted consumption. ESC version: a = m - cFunc(m) (per-Optimizer book). See plans/<map>.md.
self.state_now['aNrm'] = self.state_now['mNrm'] - self.state_now['cLvl_splurge'] / self.state_now['pLvl']
```

Properties:
- **Stable, greppable token** (`CDC-MOD-`) so the full set of anchors can be enumerated by `grep -rn CDC-MOD- Code/`.
- **BUG number** in the token so each anchor is tied to its dossier.
- **One-line summary** so a reader skimming gets the gist without leaving the file.
- **ESC pointer** so the future "make this configurable" work knows what the alternative is.
- **Doc references** so the deeper rationale is one click away.

### 4.2 Marker classification (interpretive vs bug-fix)

For each anchor, the map document should classify the change as:

- **Interpretive (I):** an ESC-faithful version would do something different here. The CDC version is one of two valid choices.
- **Bug fix (B):** the change would persist under any interpretation; it fixes an unambiguous error in the original code.
- **Interpretive AND bug fix (I+B):** the original code was wrong under both readings; CDC and ESC would each fix it differently.

The classification matters for the future configurable-version work: **(I)** anchors need a runtime switch; **(B)** anchors stay as-is; **(I+B)** need a runtime switch with both alternatives implemented.

This classification is the place where most of the careful judgment is needed. It can be left blank initially (`?`) and filled in iteratively as the team discusses each anchor.

## 5. Initial inventory of files likely to have CDC anchors

(Not a final list — to be expanded during discovery.)

| File | Expected CDC modifications |
|---|---|
| `Code/HA-Models/FromPandemicCode/AggFiscalModel.py` | `get_poststates` override (asset-update); K/Y aggregator (level-summed without `(1-ς)`); possibly `cLvl_splurge` formula source-of-truth |
| `Code/HA-Models/FromPandemicCode/tm_methods.py` | a-indexed TM kernel (BUG-033); TM-side equivalent of the asset-update change; Cratio path under CDC |
| `Code/HA-Models/FromPandemicCode/Parameters.py` | Pointer to `Result_AllTarget*.txt` and `DiscFacEstim_*.txt` files (these are CDC-calibrated; ESC has its own set) |
| `Code/HA-Models/Target_AggMPCX_LiquWealth/Estimation_BetaNablaSplurge.py` | Lottery $\varsigma$ estimation under splurge-on-total-income MPC formula (BUG-032) |
| `Code/HA-Models/FromPandemicCode/Welfare.py` | **Verify** that the welfare aggregator is identical to ESC's per `models_CDC_and_ESC.md` §3 (both use `u(c_total)`); if so, no anchor needed here |
| `Code/HA-Models/FromPandemicCode/EstimAggFiscalMAIN.py` | Step-2 $(\beta, \nabla)$ estimation against CDC moments — uses CDC $\varsigma$ and the CDC asset update |
| `Code/HA-Models/Results/DiscFacEstim_CRRA_2.0_R_1.01.txt` and similar | Output artifact — CDC calibration triple. Not a code anchor but cited by Parameters.py; the map should note these files exist as "CDC-calibrated" |
| Possibly `do_all.py`, `Output_Results.py` | Less likely — these orchestrate, they don't implement the interpretation directly. To be confirmed by the diff pass. |

## 6. Deliverable order

1. **Map document scaffolding** — empty table with columns (file, line, summary, ESC version, classification, BUG dossier ref). Establishes format before content.
2. **Discovery pass 1: BUGS dossier walk** — fastest, most authoritative source of intent; populates the high-confidence rows of the map first.
3. **Discovery pass 2: code-mapping table from `models_CDC_and_ESC.md`** — fills in any rows BUGS missed.
4. **Discovery pass 3: full diff pass** — catches anchors not yet in the bug dossiers (most likely candidates: changes made informally during validation work, or made under the umbrella of one BUG but touching files the dossier didn't enumerate).
5. **Reconcile** — three lists from three passes; the union is the candidate inventory; flag anything that appears in only one pass.
6. **Insert in-code markers** at every anchor — from the reconciled inventory.
7. **Validation pass** — `grep -rn CDC-MOD- Code/` should produce a count matching the map document's row count.

## 7. Validation

For each anchor in the final map:

- The cited file:line should contain the documented patch.
- The patch should be reproducible from the linked BUG dossier (or, if no BUG, from a `git log` entry that explains the change).
- A "round-trip" sanity check: someone reverting all `CDC-MOD-` patches in the codebase (treating each marker as an "uninstall" instruction) should produce a state that approximately matches `origin/maintain_bound_pair_fix_splurge` (modulo independent HARK-upgrade fixes and modulo any CDC interpretive choices that were already in `master`).

The round-trip check is the strongest test of completeness — if it passes, the anchor inventory is exhaustive within the scope of CDC↔ESC differences.

## 8. Out of scope (to keep this plan focused)

- **The actual configurable code path** that runs both CDC and ESC: that's a downstream plan, enabled by this one. This plan only documents the substitution points; it doesn't implement the switch.
- **ESC-side validation** (proving Edmund's branch is internally consistent): orthogonal; this plan takes the ESC baseline as a given reference.
- **Independent HARK 0.14.1 → 0.17.0 differences** unrelated to interpretation: out of scope. The ESC baseline already includes the HARK upgrade, so those changes are common to both branches and don't appear in the diff.
- **Per-output-file artifact provenance** (which Tables/* and Figures/* came from a CDC vs ESC run): orthogonal; the plan covers code anchors, not output anchors.

## 9. Open questions to resolve before execution

- **Map document filename and location.** Suggested: `plans/<date>h_cdc-implementation-map.md` (alongside this plan). Alternative: split into `plans/<date>h_cdc-implementation-map_code.md` (anchors) and `plans/<date>h_cdc-implementation-map_calibration.md` (the CDC-calibrated `.txt` artifacts), if the calibration-file inventory is substantial enough to warrant its own doc.
- **Classification (I / B / I+B) of each anchor.** This is the place that needs the most coauthor input. The plan can deliver a populated map with `?` in the classification column, leaving the substantive judgment to a follow-up review pass.
- **Scope of the "Code/" prefix.** The plan as written covers `Code/HA-Models/FromPandemicCode/` and `Code/HA-Models/Target_AggMPCX_LiquWealth/` (the simulation + estimation). Should it also cover `Code/Empirical/` (data prep) and `Code/HA-Models/do_all.py` orchestration? Suspect yes for completeness; can be deferred.

## 10. Estimated effort

- **Discovery passes (1-2-3 above):** 2-4 hours of focused work; bottleneck is the diff pass review, not the BUGS pass.
- **Map document drafting:** 1-2 hours once the inventory is reconciled.
- **In-code marker insertion:** 30-60 min (mostly mechanical once the map exists).
- **Classification (I / B / I+B) discussion with coauthors:** open-ended; could be a single meeting or could require iterative back-and-forth. The plan delivers the inventory; the classification is a separate review activity.

Total agent time before classification: ~half a day. Total wall-time including coauthor classification: depends on coauthor availability.
