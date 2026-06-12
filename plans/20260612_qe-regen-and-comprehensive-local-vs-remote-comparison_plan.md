# Plan: regenerate the QE repo and comprehensively compare local vs remote

**Date:** 2026-06-12 · **Status:** DONE — executed 2026-06-12. **Verdict: PASS** — regenerated QE reproduces the remote with zero text/table/figure/bib differences (all drift = timestamps + documented process noise). Report: `conclusions_private/20260612_qe-regen-local-vs-remote-comprehensive-diff.md`. §2 decisions approved 2026-06-12 (D1=qe2442-proof-sync, D2=origin pushed generation + submitted-tags appendix). One pipeline fix landed: HAFiscal-make `7a0503c` (bib append vs READ-ONLY PROTECTION).
**Goal:** rerun the whole Latest→Public→QE generation chain (restoring the
tables/figures/bib/data artifacts in the locally generated `HAFiscal-QE/`),
then rerun the comprehensive test that the **text** AND the
**tables/figures/etc** are the same between the freshly generated **local**
QE repo and the **remote** (GitHub) QE repo.

**Companions:**
- `plans/20260610_master-QE-proof-compatibility_plan.md` — the original
  generation run (overnight 2026-06-10/11) whose output this plan re-verifies.
- `plans/20260611_qe-baseline-freeze-and-candidate-lock_plan.md` (DONE) — the
  freeze that makes this re-verification meaningful: HAFiscal-Latest
  (TM-vs-MC) now carries the QE-published numbers, locked.
- Comparison methodology reused from
  `conclusions_private/20260611_qe-vs-repo-numeric-diff.md` (value-only
  numeric diffs + pixel-level figure compares + inventory).

---

## 1. Facts that constrain the work (verified 2026-06-12)

1. **Current remote state.** `HAFiscal-QE` on GitHub: `origin/main` =
   `origin/qe2442-proof-sync` = `5aa25fb` ("Watermark images with
   PREGENERATED label"), whose parent `13d9428` **removed the precomputed
   artifacts** from `main` (\*.bib, generated \*.txt, \*.obj, non-source
   \*.dta, root PDFs — kept: HAFiscal.bbl, rscfp2004.dta, README.pdf, qe/
   PDFs, image PDFs). `origin/with-precomputed-artifacts` =
   `origin/qe2442-proof-sync-wpa` = `b3b3566` ("Add compiled PDFs and
   bibliography") — the full-artifact variant. The 2026-04-28 submitted
   state is preserved as tags `archive-qe_2026-04-28_submitted{,_wpa}`.
2. **Local QE state.** Identical commits to remote (it IS the pushed
   2026-06-11 generation), with 3 dirty files (`.zenodo.json`,
   `CITATION.cff`, `Subfiles/HAFiscal-titlepage.tex` — build-time stamps).
   The repo is an **ephemeral build artifact**: `make-repo-Public-to-QE.sh`
   wipes `.git/` and recreates orphan branches each run. Durable archival =
   the GitHub remote (per `PROVENANCE.md` on `qe2442-proof-sync`).
3. **Build mechanics.** `cd HAFiscal-make && ./makeEverything.sh` reads the
   **checked-out branch of `../HAFiscal-Latest`** (no branch argument),
   forces Public to `main`, then regenerates QE `main` + `wpa` (step 31
   flattens `Subfiles/` into one `HAFiscal.tex`). The 2026-06-11 run used
   `SKIP_PUSH=1 SKIP_DOCKER=1`; HAFiscal-make is now at `6ce4dfc` (3 commits
   past the `1b98e19` used then — all build-script fixes, no content).
4. **Source branch mismatch.** The Latest working tree is checked out on
   `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC` (with the QE-freeze
   commits `12f06cc3…6ec03021`). The previous generation was built from
   `qe2442-proof-sync` (= `origin/qe2442-proof-sync`, `b7cca49e`), which is
   **NOT an ancestor** of TM-vs-MC: the proof copyedits/bib/terminology live
   only there. Building from TM-vs-MC would therefore differ from the remote
   in *prose* by exactly those copyedits, even though the frozen
   tables/figures now match.
5. **No Python pipeline rerun is needed.** "The whole generation chain"
   here = the **HAFiscal-make chain**. The tables/figures/intermediates
   that land in QE are *tracked files in HAFiscal-Latest* carried over by
   rsync — they are not recomputed at build time. (A do_all.py rerun would
   anyway now produce gitignored `_candidate` files, untouched by the
   build.) Runtime is LaTeX-bound: ~1–3 h locally, not 4–5 days.

---

## 2. Decisions (CDC gate — recommendations marked)

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | **Source branch for the regeneration** | (a) `qe2442-proof-sync` — reproduces the documented generation; the apples-to-apples reproducibility test. (b) TM-vs-MC — tests the freshly frozen branch, but prose will differ from remote by the proof copyedits (a noisy compare). | **(a)**. Run (b) later as a separate "freeze fidelity" comparison if desired, with the copyedit delta documented as expected. |
| D2 | **Comparison target ("the remote")** | (a) `origin/qe2442-proof-sync` + `…-wpa` (the pushed 2026-06-11 generation — strict reproducibility). (b) tags `archive-qe_2026-04-28_submitted{,_wpa}` (what QE was actually sent — but differs by the documented proof-sync deltas). | **(a) as the pass/fail comparison**; (b) as an informational appendix with the known deltas from `PROVENANCE.md` listed as expected. |
| D3 | **Push policy** | Never push from this run; local regeneration only. | **No push** (`SKIP_PUSH=1`). The remote stays the canonical state we compare against. |
| D4 | **Local QE dirty files** | The 3 dirty stamp files get wiped by the rebuild. | Accept; snapshot them to `/tmp` first for the record. |

---

## 3. Phase R — regeneration

R0. **Preflight snapshot + safety.**
   - `git -C HAFiscal-QE diff > /tmp/qe_dirty_pre_regen.patch` (D4 record).
   - Verify the four remote refs/tags exist on GitHub (`git ls-remote`) —
     they are the durable baseline; the local QE `.git` is about to be wiped.
   - Confirm `HAFiscal-Latest` TM-vs-MC tree is clean enough to leave
     (commit or stash strays; the freeze work is already committed).

R1. **Check out the source branch in the main Latest working tree** (per D1):
   `git -C HAFiscal-Latest checkout qe2442-proof-sync` (local = origin,
   `b7cca49e`, verified). Expect heavy working-tree churn on the network
   volume; gitignored `_candidate`/build files may linger — harmless (rsync
   excludes cover build dirs; verify no `*_candidate.*` lands in Public/QE
   in R3).

R2. **Run the chain** (HAFiscal-make @ current `6ce4dfc`):
   ```bash
   cd /Volumes/Sync/GitHub/llorracc/HAFiscal-make
   SKIP_PUSH=1 SKIP_DOCKER=1 ./makeEverything.sh 2>&1 | tee /tmp/makeEverything_20260612.log
   ```
   (If the full driver stalls, fall back to the 2026-06-11 recipe: run
   `make-repo-Latest-to-Public.sh` then `SKIP_PUSH=1 SKIP_DOCKER=1
   ./make-repo-Public-to-QE.sh`.)

R3. **Post-build sanity.** Local QE has fresh orphan `main` + `wpa`
   branches; artifacts restored on `wpa` (\*.bib, generated \*.txt, \*.obj,
   compiled PDFs) and the main-branch artifact-strip applied; QE
   `HAFiscal.pdf` builds; no `_candidate` files leaked into Public/QE.

R4. **Restore the working checkout:**
   `git -C HAFiscal-Latest checkout 0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`
   and re-verify the lock: `make test-locked` (45 frozen files intact).

---

## 4. Phase C — the comprehensive local-vs-remote comparison

Set up a pristine copy of the remote (the local `.git` was recreated by the
build, so fetch fresh): `git clone --no-checkout git@github.com:llorracc/HAFiscal-QE.git /tmp/qe_remote`
and `git -C /tmp/qe_remote worktree add` one tree per ref under comparison
(D2: `qe2442-proof-sync`, `qe2442-proof-sync-wpa`; appendix: the two
`archive-qe_2026-04-28_submitted*` tags).

Compare **local regenerated** vs **remote**, branch-pair by branch-pair
(`main`↔`qe2442-proof-sync`, `wpa`↔`qe2442-proof-sync-wpa`), in five layers:

| Layer | What | Method | Pass condition |
|---|---|---|---|
| C1 Inventory | every tracked path | `git ls-files` set-diff per branch | identical file sets |
| C2 Text (source) | flattened `HAFiscal.tex`, `Subfiles/`, `qe/` cover docs | `diff` (whitespace-normalized); timestamp/stamp lines (titlepage date, `.zenodo.json`, `CITATION.cff`) whitelisted | no diffs outside the whitelist |
| C3 Text (rendered) | `HAFiscal.pdf` (wpa) + qe/ submission PDFs | `pdftotext -layout` both, diff page-by-page | zero text-layer differences |
| C4 Tables | every generated `.tex`/`.ltx` table (Tables/, Code/.../Tables/, tabular/) | value-only extraction (`grep -oE '[0-9]+\.?[0-9]*'`) + full-text diff | zero numeric differences |
| C5 Figures | every figure PDF (+ png/svg siblings on wpa) | byte `cmp`; on mismatch `pdftoppm -r 150` render + pixel compare | byte-identical, or pixel-identical with metadata-only byte drift (documented) |

Plus a bibliography check (C2b): `HAFiscal.bbl` and the QE-repo bib —
entry-set equality (the 2026-06-11 run verified cited 84 = bib 84).

**Expected/acceptable noise (declare up front, fail anything else):**
- PDF `CreationDate`/`ModDate`/`ID` metadata (pixel-identical renders).
- Build-stamp lines (titlepage date, `.zenodo.json`/`CITATION.cff` version
  stamps) — exactly the 3 files dirty in the pre-regen local tree.
- Nothing else: tables and figures must be value- and pixel-identical, since
  the build copies them from the same tracked sources that produced the
  remote.

**Deliverable:**
`conclusions_private/20260612_qe-regen-local-vs-remote-comprehensive-diff.md`
— per-layer results, every difference listed and classified
(expected-noise / needs-explanation / FAIL), with the D2(b) appendix vs the
2026-04-28 submitted tags noting the `PROVENANCE.md`-documented deltas.

---

## 5. Acceptance criteria

1. Regeneration completes from `qe2442-proof-sync` with `SKIP_PUSH=1`; local
   QE `main`+`wpa` rebuilt; artifacts restored on `wpa`.
2. Layers C1–C5 pass per the noise whitelist for both branch pairs — i.e.
   the chain **reproduces the remote QE content**: same text, same table
   values, same figure pixels.
3. Latest working tree back on TM-vs-MC; `make test-locked` green.
4. The comparison report is written and this plan is flipped DONE (with a
   one-line result in `plans/INDEX.md`).

## 6. Risks / notes

- **Ephemeral local QE `.git`:** wiped by the build — all comparison
  baselines must come from the GitHub remote (hence the `/tmp/qe_remote`
  clone), never from the pre-build local clone.
- **Branch switching** of the main Latest working tree is required (build
  has no branch argument). The freeze hook/manifest live on TM-vs-MC and are
  untouched by building from `qe2442-proof-sync` (the build makes no Latest
  commits). R4 restores the checkout and re-verifies the lock.
- **Network-volume slowness** (/Volumes/Sync): the rsync+LaTeX chain took
  several hours overnight on 2026-06-11; budget the same.
- If C2/C3 turn up real text drift, or C4/C5 numeric/pixel drift, STOP and
  report — that would mean the generation chain no longer reproduces the
  canonical QE state, and fixing it is a separate, gated task.
