# Quantitative Economics Submission Requirements

Based on the official QE LaTeX templates from the Econometric Society.

## Key Requirements

### 1. Document Class
- Must use `\documentclass[qe,nameyear,draft]{econsocart}` for submissions
- Change to `[final]` option for prepublication
- Uses custom `econsocart.cls` and `econsocart.cfg` files

### 2. Required Files
- `econsocart.cls` - Main class file (DO NOT MODIFY)
- `econsocart.cfg` - Configuration file (DO NOT MODIFY)
- `qe.bst` - Bibliography style file for BibTeX

### 3. Document Structure

#### Front Matter
- Title and running title
- Author information with:
  - Full names (first names with spaces between initials)
  - Affiliations (organization division and name)
  - Email addresses (MANDATORY for each author)
- Funding/acknowledgments section
- Abstract
- Keywords (general)
- JEL Classification codes (alphabetical order)

#### Main Content
- Standard sections
- Equations can be numbered by section (optional)
- Theorem environments follow standard LaTeX styles

#### Bibliography
- Must use `qe.bst` style file
- References must be complete with:
  - Full first and last names
  - Complete publication dates
  - All required fields

### 4. Supplementary Materials
- Use separate template `qe_supp_template.tex`
- Must be clearly distinguished from main manuscript
- Same class file but different structure

### 5. Submission Format
- PDF format only for upload
- Single `.tex` file (no \input{} commands)
- Include all necessary files (.aux, .bbl if applicable)

### 6. Special Notes
- At least one author must be a member of the Econometric Society
- Electronic publication only as of 2024
- Hyperref package with blue links is standard

## Transformation Requirements from HAFiscal

### 1. Class File Change
- From: HAFiscal's current document class
- To: `\documentclass[qe,nameyear,draft]{econsocart}`

### 2. Author Information Restructuring
- Extract and reformat author details
- Add mandatory email addresses
- Properly format affiliations

### 3. Bibliography Conversion
- Apply `qe.bst` style
- Ensure all entries have complete information
- Convert to QE citation format

### 4. Document Restructuring
- Separate main content from supplementary materials
- Adjust theorem environments if needed
- Remove any incompatible packages or commands

### 5. File Organization
- Consolidate into single `.tex` file (removing \subfile{} structure)
- Separate supplementary materials
- Ensure all figures/tables are properly included 