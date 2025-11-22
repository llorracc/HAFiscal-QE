# QE Compliance Directory

This directory contains official Quantitative Economics (QE) templates and compliance resources.

## Directory Structure

### `check-qe-compliance.py`
Automated compliance checker for QE submissions.

**Usage:**
```bash
cd HAFiscal-QE/qe/compliance
./check-qe-compliance.py ../HAFiscal.tex
```

This script validates:
- Single-file requirement (no `\input` statements except approved ones)
- Required frontmatter sections (title, authors, abstract, keywords)
- Bibliography format
- Appendix structure
- QE-specific formatting requirements

### `templates/`
Official LaTeX templates from VTeX for QE journal submissions.

**Source:** https://vtex-soft.github.io/texsupport.econometricsociety-qe/

**Files:**

1. **`qe_template.tex`** (4.3K)
   - Blank template for article preparation
   - Contains frontmatter structure with `???` placeholders
   - Use this as a reference for proper econsocart syntax

2. **`qe_sample.tex`** (19K)
   - Complete sample article with full content
   - Shows working examples of all LaTeX constructs
   - Useful for understanding complex formatting

3. **`qe_supp_template.tex`** (4.2K)
   - Template for supplementary materials
   - Use if you need to submit appendices or data as supplements

4. **`qe_supp_sample.tex`** (18K)
   - Sample supplementary materials with content
   - Shows how to structure supplements

## How HAFiscal Uses These Templates

- **HAFiscal does NOT directly use these templates**
- `HAFiscal-QE-template.tex` (parent directory) is a customized version
- These files serve as **reference documentation** for QE compliance
- Consult them when questions arise about proper QE/econsocart syntax

## Key Differences: HAFiscal vs Official Templates

### Official Templates:
- Single-file submission (all content in one `.tex`)
- Numeric address labels (`[add1]`, `[add2]`)
- Full author format: `\fnms{First}~\snm{Last}\ead[label=e1]{email}`

### HAFiscal-QE-template.tex:
- Modular structure (content inlined by build scripts)
- Simplified author format (just names, no `\fnms`/`\snm`/`\ead`)
- Conditional `\runtitle`/`\runauthor` for draft mode compatibility

## When to Consult These Templates

1. **Uncertain about econsocart syntax** - Check `qe_sample.tex`
2. **Need to add supplementary materials** - Use `qe_supp_template.tex`
3. **Debugging compilation issues** - Compare with working `qe_sample.tex`
4. **Verifying QE compliance** - Ensure HAFiscal matches official structure

## Download Date

- Downloaded: 2024-11-20
- Repository: vtex-soft/texsupport.econometricsociety-qe (main branch)

## See Also

- `@local/metadata-qe.ltx` - Enhanced metadata template with lessons learned
- `@local/metadata-qe-orig.ltx` - Copy of `qe_template.tex` for comparison
- Official QE support: latex-support@vtex.lt

