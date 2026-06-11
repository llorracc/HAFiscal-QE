# Plan: regenerate Public + QE from a proof-synced branch of HAFiscal-Latest

**Date:** 2026-06-10 · **Status:** PROPOSED — not executed · **Build via:** `HAFiscal-make`.

---

## 0. Objective

Produce `HAFiscal-Public` and `HAFiscal-QE` whose content is **compatible with the QE
typeset draft** (`qe2442.tex`; source = the Apr‑29 `HAFiscal.zip`), by making the
edits in **`HAFiscal-Latest/Subfiles/*.tex` + `HAFiscal.bib`** that ultimately get
bundled into the flattened `HAFiscal-QE/HAFiscal.tex`. Do this on a **dedicated,
correspondingly‑named branch** in all three repos, **preserving the prior states as
archival**. The clean, proof‑driven pass — excluding the TM‑vs‑MC validation work
and the welfare‑number recomputation.

**In scope:** (A) add missing `campbell1989consumption` to the bib · (B) appendix
terminology → proof · (C) back‑port the copyeditor's cosmetic edits · (D) confirm
the two footnotes (already on master) survive the build · (E) build + verify Public/QE
match the proof · **(F) branching/archival/provenance (NEW — see §2).**

**Excluded:** welfare numbers (do NOT touch — residual: master note `2.15/1.83` vs
table/proof `2.13/1.82` vs TM‑vs‑MC `2.20/1.81`) · TM‑vs‑MC content changes (recomputed
numbers, splurge `0.246`→`0.25`, splurge footnote) · TM‑vs‑MC pure typos (parked in §4).

---

## 1. Architecture facts that constrain the work

1. **The build reads the main `HAFiscal-Latest` checkout** (scripts use
   `../HAFiscal-Latest`, no branch arg) ⇒ the proof‑synced branch must be the
   **checked‑out branch in the main `HAFiscal-Latest` working tree** for the build.
2. Entry: `cd HAFiscal-make && ./makeEverything.sh` → Latest→Public
   (`make-repo-Latest-to-Public.sh`, **forces Public to `main`**) → Public→QE
   (`make-repo-Public-to-QE.sh` step 31 flattens `Subfiles/` into one `HAFiscal.tex`;
   targets QE `main` + `with-precomputed-artifacts`). ⇒ **the build overwrites
   Public@`main` and QE@`main`/`wpa`** — so prior states must be archived first (§2).
3. **Bib source of truth = `HAFiscal.bib`**; `HAFiscal_paperpile.bib` + (empty)
   `HAFiscal-Add-Refs.bib` are excluded from Public/QE ⇒ **new refs go in `HAFiscal.bib`.**
4. **No hand‑edited flat file** — QE regenerates the single `HAFiscal.tex` by flattening
   `Subfiles/`, so every edit lands in `Subfiles/*.tex` + `HAFiscal.bib`.

---

## 2. Branching, archival & provenance (NEW)

**Principle.** Every coherent paper generation is a triple **Latest → Public → QE**.
Record each with a **shared branch name across all three repos**, and **never clobber
a prior published/submitted generation** — keep prior states as `archive/…` branches.

**Release label for this generation:** **`qe2442-proof-sync`** *(proposed — confirm; a
date form like `2026-06_qe-proof` also works; could align with the earlier
`with-QE-final-diffs` naming).*

| Repo | Preserve as archival (before build) | New generation lands on |
|---|---|---|
| **HAFiscal-Latest** | `master` and `…TM-vs-MC` left untouched (inherently preserved) | new branch **`qe2442-proof-sync`** off `master` — all §3 edits here; checked out for the build |
| **HAFiscal-Public** | branch current `main` (2026‑01‑11) → **`archive/public_20260111`** | **`qe2442-proof-sync`** (matches Latest) |
| **HAFiscal-QE** | branch current `main` + `with-precomputed-artifacts` (2026‑04‑28) → **`archive/qe_20260428_submitted`** (+`_wpa`) | **`qe2442-proof-sync`** (+ its `wpa` variant) |

**Provenance marker.** The matching branch name is the primary marker. In addition,
record in the Latest `qe2442-proof-sync` branch (final commit message and/or a small
`PROVENANCE.md`) the exact Public/QE branch + commit SHAs this source generated, and
that it syncs to the VTeX proof `qe2442.tex`. Result: `Latest@qe2442-proof-sync →
Public@qe2442-proof-sync → QE@qe2442-proof-sync` is an explicit, traceable, coherent set.

**Build‑mechanic procedure** (because the build targets `main`/`wpa`):
1. Archive the current `main`/`wpa` in Public & QE (branches above).
2. Run the build (writes to `main`/`wpa`).
3. Create the `qe2442-proof-sync` branch in Public & QE at the freshly‑built commit.
4. **DECISION:** should `main` then *advance* to the new generation, or stay **pinned**
   to the published/submitted version with new generations only on labeled branches?
   (Affects whether GitHub's default view shows the new or the published version.)

---

## 3. Part 1 — the clean pass (execute on approval)

### Step 1 — Branch setup
- Confirm `…TM-vs-MC` is committed/pushed (it is). Create `qe2442-proof-sync` off
  `master` in HAFiscal-Latest and check it out in the main working tree for editing+build.
- Verify the two footnotes are present: `Subfiles/Model.tex:28` (Campbell–Mankiw),
  `Subfiles/Comparing-policies.tex:145` (CRRA welfare).

### Step 2 — Bibliography fix (A)
- Add to **`HAFiscal.bib`** the entry the Model.tex footnote cites (undefined on master ⇒ `?`):
  ```bibtex
  @incollection{campbell1989consumption,
    author    = {John Y. Campbell and N. Gregory Mankiw},
    title     = {Consumption, Income, and Interest Rates: Reinterpreting the Time Series Evidence},
    booktitle = {NBER Macroeconomics Annual 1989, Volume 4},
    editor    = {Olivier Jean Blanchard and Stanley Fischer},
    pages     = {185--246}, year = {1989}, publisher = {MIT Press},
    address   = {Cambridge, MA}, series = {NBER Macroeconomics Annual}, volume = {4}
  }
  ```
- Mirror into Paperpile / `HAFiscal-Add-Refs.bib` for source hygiene (only `HAFiscal.bib`
  reaches the build). Other proof refs already present — no action.

### Step 3 — Appendix terminology (B)
- Proof mixes "Supplemental Appendix" ×4 / "Online Appendix" ×3 ⇒ map **per occurrence**.
- Known spot `Subfiles/literature.tex:98`; audit titles, `HAFiscal.tex` root
  appendix‑handling/`hiddencontent`, `Appendix-NoSplurge.tex`; align each to the proof.

### Step 4 — Cosmetic copyedits (C)
- Derive from the proof‑vs‑sent diff (`qe2442.tex` vs `HAFiscal.zip/HAFiscal.tex`):
  numbers/percent → numerals/% (`50 percent`→`50%`, `five`→`5`, …), British→American
  spelling (`modelling`→`modeling`), section titles → sentence case, minor punctuation.
- Apply to `Subfiles/` via a **reviewable, anchored script** (dry‑run report; present
  curated list for sign‑off first). No §4‑typos, no welfare/results numbers.

### Step 5 — Build & verify (E)
- With `qe2442-proof-sync` checked out: `cd HAFiscal-make && ./makeEverything.sh --dry-run`,
  then real (`--omit-QE` first to validate Public, then full).
- Verify: PDFs build; both footnotes render; `campbell1989consumption` resolves (no `?`);
  terminology + cosmetics applied.
- **Acceptance check:** diff regenerated QE `HAFiscal.tex` vs `qe2442.tex` — only
  differences should be the parked typos (§4), the welfare numbers, and VTeX scaffolding.

### Step 6 — Land the generation + provenance (per §2)
- Archive current Public `main` and QE `main`/`wpa` (the `archive/…` branches).
- Create `qe2442-proof-sync` branches in Public & QE at the built commits.
- Write the provenance marker (Latest commit msg / `PROVENANCE.md`) recording the
  generated Public/QE SHAs and the `qe2442.tex` source.
- Restore `…TM-vs-MC` as the working checkout in HAFiscal-Latest.

---

## 4. Held‑off to‑do — TM‑vs‑MC pure typos (DO NOT apply in Part 1)

| Typo (master) | → | Location |
|---|---|---|
| `mulitiplier`→`multiplier` | | `Comparing-policies.tex:109` |
| `slighlty`→`slightly` | | `Comparing-policies.tex:227`; `Appendix-NoSplurge.tex:100` |
| `sustantial`→`substantial` | | `literature.tex:45` |
| `asses`→`assess` | | `Appendix-NoSplurge.tex:36` |
| `Lorentz`→`Lorenz` | | `Appendix-NoSplurge.tex:56` |

(Not typos, hence excluded entirely: splurge `0.246`→`0.25`, the added splurge footnote,
the `2.20/1.81` recomputation.)

---

## 5. Open items / decisions
1. **Release label** — confirm `qe2442-proof-sync` (vs a date form / `with-QE-final-diffs`).
2. **`main` policy** — after build, does Public/QE `main` advance to the new generation,
   or stay pinned to the published/submitted version (new gens only on labeled branches)? (§2.4)
3. **Latest base** — confirm the proof‑synced branch is cut from `master` (so `master`
   stays as the pre‑sync archive), as assumed here. (If "current branch" meant
   `…TM-vs-MC`, adjust — but that branch predates/diverges from the published paper.)
4. Welfare‑note residual (`2.15/1.83` vs proof `2.13/1.82`) left as‑is — confirm acceptable.

## 6. Done‑when
- `qe2442-proof-sync` (Latest) compiles with `campbell1989consumption` resolved.
- `makeEverything.sh` builds Public + QE cleanly onto matching `qe2442-proof-sync` branches.
- Prior Public/QE states preserved as `archive/…`.
- Regenerated QE `HAFiscal.tex` ≈ `qe2442.tex` modulo the documented exclusions.
