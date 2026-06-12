# Plan: audit that the generated QE version incorporates ALL the proof's diffs

**Date:** 2026-06-12 · **Status:** DONE — audit executed 2026-06-12; verdict
NO (33 copyedits + 9 citation updates + 4 frontmatter statements not
incorporated). P5 fixes then EXECUTED same day on `qe2442-proof-sync`
(commits 9b932a62, c0f114f6, 0d15deb2), chain rebuilt, re-audit clean.
Report: `conclusions_private/20260612_proof-diff-incorporation-audit.md`.
⚠️ Merge-back to master/TM-vs-MC still pending:
`plans/20260612_proof-sync-merge-back_TODO.md`.
**Question being answered (CDC, 2026-06-12):** does the *current generated*
QE version (`HAFiscal-QE` local `main` = remote `qe2442-proof-sync`, verified
identical 2026-06-12) incorporate **every** change that the QE proof
identified — not just the ~128 copyedits that were back-ported, but all of
them? Flagged example: `percent` → `\%` appears fixed in some places but not
others.

## 1. Reference and method

- **Ground truth = the proof source `qe2442.tex`** (VTeX SkyLaTeX bundle,
  `/tmp/skylatex_src/`, mtime 2026-06-09 — to be preserved durably in
  Phase 0). The corrected-proof PDF (`qe2442_corrected_53pp.pdf`) is no
  longer on disk; it was rendered from this source, so the source IS the
  proof's text. (If CDC still has the PDF in email/Downloads, a rendered
  `pdftotext` cross-check can be appended later — not blocking.)
- **Object under test = the flattened `HAFiscal.tex`** of the regenerated QE
  repo (byte-identical to the GitHub remote per
  `conclusions_private/20260612_qe-regen-local-vs-remote-comprehensive-diff.md`).
- **Method:** normalize both files (strip LaTeX comments, collapse
  whitespace), word-level diff, then classify **every hunk** into:
  - **(a) documented deliberate exclusion** — per `PROVENANCE.md` on
    `qe2442-proof-sync`: VTeX production scaffolding (styledata/vmkcol, JATS
    bibliography, `\-` hyphenation hints, control-space/layout internals,
    flattened EPS figures), the proof's unbalanced-quote erratum (we keep
    balanced quotes), and the parked TM-vs-MC typo list (master plan §4).
  - **(b) production-mechanical equivalence** — same rendered text, different
    LaTeX mechanism (e.g. sub-labeled two-panel figure vs hardcoded `}a`).
  - **(c) UNINCORPORATED proof change** — a wording/punctuation/number/style
    edit present in the proof but absent from our version. **These are the
    failures the audit exists to find.**
- **Special focus:** a per-occurrence table of every `percent`/`\%` usage in
  both files, since CDC flagged it.

## 2. Phases

- **P0 — preserve the reference.** Copy `qe2442.tex` (+ bundle manifest)
  from volatile `/tmp` into `Private/Submissions/QE/proof-source/`.
- **P1 — extract + normalize** both texts (comments stripped, whitespace
  collapsed, body only — from `\begin{document}`).
- **P2 — word-level diff** → machine-readable hunk inventory.
- **P3 — classify** each hunk by the (a)/(b)/(c) rules; everything not
  auto-classified gets individual review.
- **P4 — report**:
  `conclusions_private/20260612_proof-diff-incorporation-audit.md` — verdict,
  per-hunk classification table, the percent/\% occurrence table, and (if
  any) the list of category-(c) misses.
- **P5 (gated) — fixes.** If category-(c) items exist: present to CDC; on
  approval, apply to `Subfiles/*.tex` on `qe2442-proof-sync`, rebuild via the
  chain, re-run this audit to zero, and re-run the local-vs-remote
  comparison.

## 3. Acceptance

- Every word-level hunk between `qe2442.tex` and our flattened QE
  `HAFiscal.tex` is classified (a)/(b)/(c) — none unexplained.
- Either zero category-(c) items, or a CDC-approved fix list driving them to
  zero.
- The percent/\% question answered per-occurrence.
