# HAFiscal Document Structure Analysis

## Document Overview

### Main Document: HAFiscal.tex
- **Document Class**: `econark` with options `[titlepage, headings=optiontotocandhead]`
- **Build Modes**: Supports LONG and SHORT modes via `\BuildMode` parameter
- **Bibliography Style**: `econark` 
- **Bibliography File**: `HAFiscal.bib` (42KB, 1172 lines)

### Existing QE Version: HAFiscal-QE.tex
- Already exists with basic QE structure
- Uses `\documentclass[qe,draft]{econsocart}`
- Has author information partially formatted for QE
- Contains placeholder sections for content insertion

## Document Structure

### Main Content Sections (from Subfiles.texinput)
1. `Subfiles/Intro.tex` - Introduction
2. `Subfiles/literature.tex` - Literature Review
3. `Subfiles/Model.tex` - Model
4. `Subfiles/Parameterization.tex` - Parameterization
5. `Subfiles/Comparing-policies.tex` - Comparing Policies
6. `Subfiles/HANK.tex` - HANK Model
7. `Subfiles/Conclusion.tex` - Conclusion

### Appendices
1. `Subfiles/Appendix-NoSplurge.tex` - OFFLINE appendix (always included)
2. `Subfiles/Appendix-HANK.tex` - ONLINE appendix (conditional inclusion)

### Special Features
- Uses `\subfile{}` commands for modular structure
- Supports online appendix handling with stub/full modes
- Has custom local definitions in `@local/local.sty`

## Key Packages Used (from @local/local.sty)

### Essential Packages
- `hyperref` - Links and references
- `natbib` with `[authoryear]` option - Citations
- `subfiles` - Modular document structure
- `graphicx` - Graphics
- `booktabs` - Professional tables
- `dcolumn` - Decimal alignment in tables
- `xcolor` - Color support
- `amsmath`, `amssymb`, `amsfonts` - Mathematics
- `subcaption` - Subfigures

### Layout/Formatting
- `setspace` - Spacing control
- `enumitem` - List formatting
- `sectsty` - Section styling
- `afterpage`, `placeins` - Float control

### Custom Features
- Custom appendix commands from `@local/appendix-commands`
- Color commands: `\myred`, `\myblue`
- Decimal column type: `d`

## Author Information (from HAFiscal-QE.tex)

1. Christopher D. Carroll - Johns Hopkins University (ccarroll@jhu.edu)
2. Edmund Crawley - Federal Reserve Board (edmund.s.crawley@frb.gov)
3. William Du - Johns Hopkins University (wdu9@jhu.edu)
4. Ivan Frankovic - Deutsche Bundesbank (ivan.frankovic@bundesbank.de)
5. Håkon Tretvoll - Statistics Norway and HOFIMAR, BI Norwegian Business School (hakon.tretvoll@ssb.no)

## Title Information
- **Full Title**: "Welfare and Spending Effects of Consumption Stimulus Policies"
- **Running Title**: Same as full title

## Abstract
Available in HAFiscal-Abstract.txt (702 bytes)

## Transformation Requirements

### 1. File Consolidation
- Extract content from all subfiles
- Merge into single .tex file
- Remove `\subfile{}` commands
- Maintain section order and numbering

### 2. Package Compatibility
- **Keep**: hyperref, booktabs, dcolumn, xcolor, amsmath, subcaption
- **Remove**: subfiles, econark-specific packages
- **Add**: QE-required hyperref settings (blue links)

### 3. Bibliography Conversion
- Convert from `econark` style to `qe` style
- Use `qe.bst` file
- Ensure all entries have complete information

### 4. Content Separation
- **Main manuscript**: All sections 1-7
- **Main appendix**: Appendix-NoSplurge (essential content)
- **Supplementary**: Appendix-HANK (online only)

### 5. Special Handling
- Convert custom commands to QE-compatible format
- Adapt appendix stub mechanism for QE
- Handle conditional content (SHORT/LONG modes)

## Next Steps

1. Create script to extract content from subfiles
2. Build consolidation tool
3. Test compilation with QE class
4. Verify all references and citations
5. Generate submission-ready PDFs 