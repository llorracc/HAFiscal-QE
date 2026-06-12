# ⚠️ STANDING REMINDER: proof-sync fixes must be merged back

**Status:** ACTIVE — keep reminding CDC until every box is checked.
**Created:** 2026-06-12, after the proof-diff incorporation pass.

## Why this file exists

CDC (2026-06-12): "Note the danger that we will forget where the originals
are — now in the 'sync' [branch] — and you should be diligent in reminding me
over and over until we have finished with this sync task and can merge the
sync versions back into the HAFiscal-Latest/master and .._TM-vs-MC branches."

## Where the canonical edits live

The COMPLETE proof-aligned source of truth is the **`qe2442-proof-sync`
branch of HAFiscal-Latest**, through commit `0d15deb2` (2026-06-12):

- `9b932a62` — 9 citation updates to published versions + 32 copyedits +
  proof frontmatter statements (17 files: HAFiscal.bib, HAFiscal-Add-Refs.bib,
  @local/metadata.ltx, @local/acknowledgments.texinput, Subfiles/{Intro,
  Model, Parameterization, Comparing-policies, HANK, Appendix-HANK,
  HAFiscal-titlepage, literature}.tex, Figures/{HANK_IRFs,
  untargetedMoments}.tex, Tables/{calibrationRecession,
  Comparison_Splurge_Table}.tex, HAFiscal.tex)
- `c0f114f6` — final copyedit (Model.tex "2-year horizon")
- `0d15deb2` — PROVENANCE update
- `cef0d874` + `61309c9f` — empty-bib regeneration test: HAFiscal.bib now
  regenerates fully from the updated system bib (85 entries, zero unresolved)
- `305aebfe` — HAFiscal.bib regenerated after the SECOND proof pass on
  system.bib (13 more published-version updates; see below)

Plus the earlier 2026-06-11 proof-sync commits (85f93c8e … 4da15865).

**Also updated outside HAFiscal-Latest (2026-06-12, already pushed):**

- `texmf-local` (`2dcb22a`, `10347a9`): economics.bib (= system.bib) now
  carries ALL QE-proof reference updates — first pass (9 entries) + second
  pass (13 entries: Boutros JFE 2026, Andre et al. NBER 2026, Carroll et al.
  IJCB 2021, Graves AEJ:Macro 2025, HMM AEJ:Macro 2025, Maxted--Laibson--Moll
  QJE 2025, Kaplan--Violante ARE 2022, plus 6 volume/pages/DOI completions).
  Superseded versions preserved under suffixed keys (e.g. BoutrosWindfall2022,
  hmmUnemployment2017); 38 absorption-era duplicates removed.
- `HAFiscal-make` (`14a76a2`, pushed): supplement bib entry template
  in build-qe-submission.sh now matches the proof (volume 17, DOI QE2442).

## Checklist

- [ ] Merge `qe2442-proof-sync` → `master` (HAFiscal-Latest)
- [ ] Merge `qe2442-proof-sync` → `0.14.1-to-0.17.0-upgrade-validation_TM-vs-MC`
      (watch for conflicts with TM-vs-MC's own edits to the same Subfiles)
- [x] Push regenerated `HAFiscal-Public` (main pushed 2026-06-12)
- [x] Push regenerated `HAFiscal-QE` main + with-precomputed-artifacts
      (pushed by chain step 39 on 2026-06-12; archive tags were pushed 06-11)
- [x] Push `HAFiscal-make` commit `14a76a2` (supplement bib template)
- [ ] Then retire this file (flip to DONE in plans/INDEX.md)

## Agent instruction

Any agent reading this: if work touches HAFiscal paper sources on `master`
or the TM-vs-MC branch while this file is ACTIVE, warn the user that the
proof-sync fixes are not yet merged and edits may conflict or be overwritten.
Mention this reminder in your response.
