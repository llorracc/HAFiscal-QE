# Plan 1: Ladder presets, single-grid defaults, and documentation

**Status:** Draft (implementation not started)  
**Scope:** Items **A**, **B**, and **C** from the asymptotic-equality driver review (preset levels, CLI defaults, docs).  
**Out of scope:** Baseline-work caching / refactor — see `asymptotic-equality-driver-baseline-cache-refactor.md` (Plan 2).

**Recommended implementation order:** **B → A → C** (defaults and behavior first, then explicit `--ladder` wiring, then user-facing documentation).

---

## B — Change default `--mc` / `--tm` behavior (first)

**Problem:** Phases such as `baseline`, `norec-check`, `norec-ui`, and `norec-taxcut` default to **multiple** TM grids (and sometimes multiple MC tiers), which triggers a **TM sweep** every run. That is appropriate for convergence studies, not for routine smoke / fixed-scale parity runs.

**Goal:** When the user does **not** pass `--mc` or `--tm`, the driver should default to **one** MC label and **one** TM label per phase (no implicit multi-grid sweep).

**Tasks**

1. Inventory every phase runner in `Code/HA-Models/FromPandemicCode/test_asymptotic_equality_revised.py` that sets `mc_configs = [...]` or `tm_configs = [...]` when `None`.
2. Replace multi-entry defaults with a **single** pair consistent with “reduced but meaningful” parity (exact labels to align with `MC_CONFIGS` / `TM_CONFIGS` in the same file — e.g. one `MC-med`-class + one `TM-fine`-class, or tie to Plan A’s table).
3. Preserve **sweep semantics** when the user passes **more than one** `--mc` or `--tm` argument (explicit opt-in).
4. Add a one-line log at phase start: `MC configs: …`, `TM configs: …` so logs show whether a sweep ran.

**Acceptance**

- `uv run python test_asymptotic_equality_revised.py --phase norec-taxcut` (no `--mc`/`--tm`) runs **one** TM grid and **one** MC tier unless overridden.
- Passing `--tm TM-coarse TM-default` still runs a **two-grid** sweep (current loop behavior when `len(tm_configs) > 1`).

---

## A — Preset ladder levels (`--ladder` / `--scale`) (second)

**Problem:** Operators want a named **tiny / small / medium / large** scale without memorizing which `MC-*` and `TM-*` labels match.

**Goal:** A single CLI flag selects **one** `(MC label, TM label)` pair used whenever `--mc` / `--tm` are omitted.

**Tasks**

1. Add a table near `MC_CONFIGS` / `TM_CONFIGS`, e.g. `LADDER_LEVEL` (names provisional):

   | Level   | MC config   | TM config   |
   |---------|-------------|------------|
   | `tiny`  | `MC-tiny`   | `TM-coarse` |
   | `small` | `MC-small`| `TM-default` |
   | `medium`| `MC-med`  | `TM-fine` |
   | `large` | `MC-large`| `TM-xfine` |

   Adjust to project conventions (`plans/20260329-1853h_tm_scaleup_plan.md`, Gatekeeper grids).

2. Add argument, e.g. `--ladder {tiny,small,medium,large}` (alias `--scale` if desired).

3. In `main()`, **after** parsing: if `--ladder` is set and `--mc` / `--tm` are **absent**, set `args.mc` and `args.tm` to the one-element lists from the table. If `--ladder` conflicts with explicit `--mc`/`--tm`, define precedence (recommended: **explicit `--mc`/`--tm` win**; document).

4. Optionally map `Parametrization` (`Smoke_Test`, `Reduced_Run`, …) to a default `--ladder` when neither `--ladder` nor `--mc`/`--tm` are given — only if it stays predictable; otherwise skip and document.

**Acceptance**

- `uv run python test_asymptotic_equality_revised.py --phase baseline --ladder tiny` uses exactly **one** MC and **one** TM from the table.
- Explicit `--mc MC-med --tm TM-fine` ignores `--ladder` for those dimensions (per chosen precedence rules).

---

## C — Documentation (third)

**Goal:** Explain default behavior, `--ladder`, sweep opt-in, and why **baseline vs policy** requires two solves in this model (separate from “TM vs MC must agree”). **Also:** eliminate ambiguous **“TM”** labels so TM-P vs TM-Q is always explicit in console output and in step reports.

**Tasks**

1. **Driver docstring / module header** in `test_asymptotic_equality_revised.py`: `--ladder`, default single-grid behavior, multi-`--tm` = sweep.

2. **`plans/20260404-1746h_asymptotic-equality-test-plan_revised.md`** (short subsection or pointer): reference this plan and the two-solve rationale (point to `AggFiscalModel.switch_shock_type`: `base` vs `TaxCut` / `UI` / `Check` use different `MrkvArray` / `IncShkDstn` — different Bellman problems; multiplier needs baseline path vs policy path).

3. Optional: one paragraph in `CLAUDE.md` or `AGENTS.md` under the test driver — “run parity with `--ladder tiny`”.

4. **Explicit TM measure labeling (required):** Audit **every** `print_table` title, column header, and `print(...)` line in `test_asymptotic_equality_revised.py` (and any helper it calls) that refers to TM results. Replace generic **“TM”**, **“TM ref”**, or grid-only labels (**“TM-50”**) where they denote a **measure-specific** object with explicit **TM-Q** or **TM-P**:
   - Economy-level aggregates from `run_experiment_tm(..., neutral_measure=True)` → **TM-Q** in the label (e.g. `TM-Q (mCount=50)` or `TM-Q ref`).
   - Per-type ergodic moments from `compute_baseline_tm_data(..., neutral_measure=False)` → **TM-P** in the label.
   - Where both appear in one phase, print a **one-line legend** if needed: *“TM-Q: neutral measure (p-linear aggregates); TM-P: physical measure (P-ergodic moments vs MC-P).”*
5. **Same rule** for `verify_four_methods_agreement.py` and the **Gatekeeper** / **Harness** notebooks: table headers and summary markdown must say **TM-P** / **TM-Q** / **MC-P** / **MC-Q** where applicable—not bare “TM”.

6. **Cross-reference:** §2.1 of `plans/20260404-1746h_asymptotic-equality-test-plan_revised.md` now requires explicit TM-P/TM-Q labels in step reports; implementation of tasks 4–5 satisfies that requirement for automated outputs.

**Acceptance**

- A new reader can discover **why** two solves appear and how to run **without** TM sweep.
- Grep for ambiguous patterns (e.g. `"TM ref"` without Q/P in user-facing strings in the driver) returns **no** false-generic labels, or each occurrence is documented as intentionally generic (rare).

---

## Rollout / risk

- **Risk:** CI or local scripts rely on old multi-default sweeps. Mitigation: grep for `test_asymptotic_equality_revised` in CI; changelog in commit message; optional temporary `--sweep-defaults` escape hatch (only if needed).

---

## Dependencies

- None (Plan 2 is independent).
