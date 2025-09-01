# Transform HAFiscal to Quantitative Economics Format

This prompt guides the transformation of HAFiscal LaTeX documents to meet Quantitative Economics submission requirements.

## Overview

The transformation is **downstream-only** - we read from HAFiscal sources and create new QE-formatted files without modifying the originals.

## Source Analysis Phase

1. **Examine HAFiscal.tex structure**
   - Document class and options
   - Package usage
   - Author information format
   - Section organization
   - Use of \subfile{} commands
   - Bibliography setup

2. **Inventory content types**
   - Main manuscript sections
   - Online appendix materials
   - Tables and figures
   - Supplementary proofs
   - Data/code documentation

## Transformation Steps

### 1. Document Class Conversion

**From:**
```latex
\documentclass[???]{???}  % Current HAFiscal class
```

**To:**
```latex
\documentclass[qe,nameyear,draft]{econsocart}
```

### 2. Author Information Restructuring

**From HAFiscal format to QE format:**
```latex
\begin{aug}
\author[add1]{\fnms{First~M.}~\snm{Last}\ead[label=e1]{email@domain.edu}}
% Additional authors...
\end{aug}

\address[add1]{%
\orgdiv{Department of Economics},
\orgname{University Name}}
```

### 3. File Consolidation

**Convert multi-file structure:**
- Replace `\subfile{Subfiles/Introduction.tex}` with actual content
- Inline all section files into single document
- Maintain logical flow and numbering

### 4. Bibliography Transformation

**Apply QE style:**
```latex
\bibliographystyle{qe}
\bibliography{HAFiscal-QE}  % Consolidated bibliography
```

### 5. Content Separation

**Main manuscript includes:**
- Core theoretical content
- Primary empirical results
- Essential tables/figures
- Main conclusions

**Supplementary materials include:**
- Additional proofs
- Robustness checks
- Extended data descriptions
- Computational appendices

### 6. Package Compatibility

**Review and adjust:**
- Remove incompatible packages
- Add QE-required packages (hyperref with blue links)
- Resolve any conflicts

### 7. Figure/Table Handling

**Ensure:**
- All paths are relative to single document
- Proper float placement
- QE-compliant captions
- No missing references

## Validation Checklist

- [ ] Document compiles with QE class
- [ ] All authors have email addresses
- [ ] Bibliography uses qe.bst style
- [ ] No undefined references
- [ ] Single .tex file (no \input commands)
- [ ] Supplementary materials separated
- [ ] PDF generates without errors

## Common Issues and Solutions

### Issue: Package conflicts
**Solution:** Create compatibility layer or find QE-approved alternatives

### Issue: Complex subfigures
**Solution:** Simplify using standard figure environments

### Issue: Custom commands
**Solution:** Define in preamble within \startlocaldefs...\endlocaldefs

### Issue: Non-standard citations
**Solution:** Convert to natbib-compatible format

## Automation Targets

Future scripts should handle:
1. Automatic content extraction from subfiles
2. Author information parsing and reformatting
3. Bibliography entry validation
4. Package compatibility checking
5. Reference resolution verification

## Testing Protocol

1. Run transformation
2. Compile with QE class
3. Check all warnings/errors
4. Verify output matches original content
5. Validate against QE requirements 