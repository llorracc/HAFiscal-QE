# QE Compliance Specification

**Purpose**: Single Source of Truth for Quantitative Economics submission requirements
**Version**: 2.0
**Last Updated**: 2025-11-25
**Journal**: Quantitative Economics (Econometric Society)

---

## Official Sources

This specification is derived from:

1. **QE LaTeX Templates**
   Source: <https://www.e-publications.org/es/support/>
   Files: qe_template.tex, qe_sample.tex, econsocart.cls

2. **Econometric Society Data Editor Guidelines**
   Main: <https://www.econometricsociety.org/publications/es-data-editor-website/>
   Package: <https://www.econometricsociety.org/publications/es-data-editor-website/package>
   Policy: <https://www.econometricsociety.org/publications/es-data-editor-website/data-and-code-availability-policy>

3. **QE Submission Instructions**
   Source: <https://www.econometricsociety.org/publications/quantitative-economics/submissions/instructions-for-submitting-articles>

4. **QE Replication Policy**
   Source: <https://www.econometricsociety.org/publications/quantitative-economics/submissions/replication-policy>

5. **DCAS Standard v1.0** (endorsed by Econometric Society)
   Data and Code Availability Standard for social sciences

6. **Social Science Data Editors Template**
   Recommended for README files

---

## How to Use This Document

This specification defines ALL requirements for QE journal submission. It serves as the canonical reference for:

1. **Automated checking** (`check-qe-compliance.py`)
2. **AI verification** (QE-COMPLIANCE-REPORT-AND-CHECKLIST-MAKE.md prompt)
3. **Author compliance** (manual review)

### Status Indicators

- ✅ **COMPLIANT**: Requirement met
- ⚠️ **WARNING**: Issue noted but not blocking
- ❌ **NON-COMPLIANT**: Must fix before submission

### Automation Levels

- **🤖 FULL**: Fully automated check
- **🤖 PARTIAL**: Partially automated (existence/format check only)
- **👤 MANUAL**: Requires human/AI review

---

## SECTION A: Manuscript Formatting

### A.1: Document Class
**ID**: `A.1`
**Requirement**: Manuscript uses `\documentclass[qe]{econsocart}`
**Automation**: 🤖 FULL
**Source**: qe_template.tex (lines 1-16)

**Details**:

- Main .tex file must begin with `\documentclass[qe]{econsocart}` (case-insensitive for option)
- Options: `[qe,nameyear,draft]` for initial submission; `[qe,nameyear,final]` for pre-publication
- No other document class commands
- econsocart.cls must be present in submission

**Pass Criteria**:

- ✅ HAFiscal.tex contains `\documentclass[qe]{econsocart}` (or `[QE]`)
- ✅ econsocart.cls exists in repository root

**Fail Criteria**:

- ❌ Uses different document class
- ❌ econsocart.cls missing

**Check Method**:

```python
# Read first 100 lines of HAFiscal.tex
# Search for: \documentclass.*\[.*qe.*\].*\{econsocart\}
# Verify: econsocart.cls exists
```

---

### A.2: Bibliography Style
**ID**: `A.2`
**Requirement**: Uses `\bibliographystyle{qe}` and includes .bbl file
**Automation**: 🤖 FULL
**Source**: qe_template.tex (lines 140-145)

**Details**:

- Must use QE's custom bibliography style (qe.bst)
- Compiled .bbl file MUST be included
- Source .bib file should NOT be included in final submission
- References must be complete with full author names and dates

**Pass Criteria**:

- ✅ HAFiscal.tex contains `\bibliographystyle{qe}`
- ✅ HAFiscal.bbl exists and is non-empty (>10 lines)
- ✅ qe.bst exists in repository
- ⚠️ HAFiscal.bib does NOT exist (warning only, will be excluded by finalize step)

**Fail Criteria**:

- ❌ Wrong bibliography style or missing
- ❌ HAFiscal.bbl missing or empty

**Check Method**:

```python
# Search HAFiscal.tex for: \bibliographystyle{qe}
# Verify HAFiscal.bbl exists and has >10 lines
# Verify qe.bst exists
# Warn if .bib exists
```

---

### A.3: Abstract, Keywords, and JEL Codes
**ID**: `A.3`
**Requirement**: Complete frontmatter with proper abstract, keywords, and JEL codes
**Automation**: 🤖 PARTIAL (existence check only)
**Source**: qe_sample.tex (lines 92-114)

**Details**:

**Abstract Requirements**:

- Maximum 150 words (strictly enforced)
- Clear, descriptive, self-explanatory
- No citations in abstract
- Avoid math formulas as much as possible (no equation references)
- Suitable for abstracting services

**Keyword Requirements**:

- 3-8 keywords recommended
- Keywords should not duplicate title words
- Relevant to paper content

**JEL Code Requirements**:

- Up to 3 JEL codes (not 2-6 as some sources suggest)
- Codes must be specific (e.g., E21, H31) not placeholders (e.g., E.., D..)
- Alphabetical order recommended
- Appropriate for paper content

**Pass Criteria**:

- ✅ Abstract exists in `\begin{abstract}...\end{abstract}`
- ✅ Abstract ≤150 words
- ✅ JEL codes exist in `\begin{keyword}[class=JEL]...\end{keyword}`
- ✅ Keywords exist in `\begin{keyword}...\end{keyword}`
- 👤 JEL codes are specific (not placeholders)
- 👤 JEL codes are appropriate for paper content (≤3)
- 👤 Keywords are relevant and don't duplicate title (3-8 recommended)
- 👤 No citations or heavy math in abstract

**Fail Criteria**:

- ❌ Missing abstract, JEL codes, or keywords
- ❌ Abstract >150 words
- ⚠️ Placeholder JEL codes (E.., D..)
- ⚠️ Keywords duplicate title words

**Check Method**:

```python
# Search titlepage for \begin{abstract}, \jelclass{}, \keywords{}
# Count abstract words
# Verify non-empty content
# MANUAL: AI checks for placeholder codes and keyword quality
```

---

### A.4: Title, Running Title, and Authors
**ID**: `A.4`
**Requirement**: Complete title page with all author information
**Automation**: 🤖 PARTIAL
**Source**: qe_template.tex (lines 67-100), qe_sample.tex (lines 54-90)

**Details**:

**Title Requirements**:

- Clear, descriptive title
- Running title (shortened version for headers)

**Author Requirements**:

- All author names with first names and surnames
- Email mandatory for each author (not just one contact email)
- Complete affiliations for all authors
- Funding acknowledgments (if applicable)
- **PROHIBITION**: Do not thank handling co-editor anonymously or by name

**Pass Criteria**:

- ✅ `\title{...}` exists and is non-empty
- ✅ `\runtitle{...}` exists (running head title)
- ✅ Each `\author[...]{\fnms{...}~\snm{...}\ead[label=...]{...}}` has email
- ✅ All `\address[...]` blocks complete
- 👤 No co-editor acknowledgment (anonymous or by name)

**Fail Criteria**:

- ❌ Missing title or running title
- ❌ Any author missing email
- ⚠️ Co-editor thanked (violates submission rules)

**Check Method**:

```python
# Verify \title and \runtitle exist
# Count \author commands and \ead commands (should match)
# MANUAL: AI checks for co-editor acknowledgment in \begin{funding}
```

---

### A.5: Manuscript Layout
**ID**: `A.5`
**Requirement**: Proper manuscript formatting for readability
**Automation**: 👤 MANUAL (PDF visual inspection)
**Source**: QE submission instructions

**Details**:

- Minimum 12-point font size throughout entire manuscript
- 1.5 or double spacing required (applied to all content including references and appendices)
- Minimum 1.25-inch margins on all sides
- Maximum 32 lines per page
- Numbered pages required
- Figures and tables placed on relevant pages (not collected at end)
- References appear after any appendices at document's end

**Pass Criteria**:

- 👤 Font ≥12pt throughout
- 👤 Spacing ≥1.5 throughout
- 👤 Margins ≥1.25 inches
- 👤 ≤32 lines per page
- 👤 Pages numbered
- 👤 Figures/tables inline (not at end)

**Fail Criteria**:

- ⚠️ Layout doesn't meet specifications (affects readability for reviewers)

**Note**: These requirements apply to PDF submission. LaTeX class file (econsocart) handles most formatting automatically.

---

### A.6: Figures and Tables
**ID**: `A.6`
**Requirement**: All figures and tables exist with proper structure
**Automation**: 🤖 PARTIAL (existence only)
**Source**: Best practices

**Details**:

- Figures should exist as LaTeX files (Figures/*.tex) or graphics files
- Each figure should have a caption
- Each table should have a caption
- Figures and tables referenced in main text
- Image files in appropriate directory

**Pass Criteria**:

- ✅ Figures/ directory exists with .tex or image files
- 👤 All figures have captions
- 👤 All tables have captions
- 👤 All figures/tables referenced in text
- 👤 Image files exist for all \includegraphics commands

**Fail Criteria**:

- ⚠️ Missing image files
- ⚠️ Unreferenced figures/tables

**Check Method**:

```python
# Count .tex files in Figures/
# Verify image files exist
# MANUAL: AI checks captions and references
```

---

## SECTION B: Replication Package Structure

### B.1: README Documentation
**ID**: `B.1`
**Requirement**: Comprehensive README in PDF format with all required sections
**Automation**: 🤖 PARTIAL (existence and length)
**Source**: ES Data Editor guidelines, Social Science Data Editors template (recommended)

**Details**:

**Format**: README must be in **PDF format** (README.pdf)
Note: README.md (markdown) is acceptable for development but must be converted to PDF for submission.

**Minimum Length**: ≥100 lines of substantive content (when in markdown source; PDF should be comprehensive)

**Required Sections** (per ES Data Editor guidelines):

1. **Data Availability Statement**
   - Access procedures for all data
   - Costs (if any)
   - Data version details
   - Restrictions or confidentiality notes

2. **Package Contents Description**
   - File-to-source connections (which file generates which output)
   - Directory structure explanation
   - File naming conventions

3. **Code Execution Instructions**
   - Master script to run (e.g., reproduce.sh)
   - Order of execution if manual steps needed
   - Expected outputs

4. **Computational Requirements**
   - Software versions (exact versions, e.g., Python 3.9.1, Stata 17)
   - Hardware requirements
   - Runtime estimates (especially if >1 hour)
   - Operating system tested on

5. **Output Mapping**
   - Table/figure output mapping (which script generates Table 1, Figure 2, etc.)
   - Location of output files

6. **Data Citations** (dedicated references section)
   - All data sources cited in bibliographic format
   - Following journal format for indexing
   - Both in paper and in README references section

7. **Installation Instructions**
   - How to set up computational environment
   - Package/library installation steps

8. **Directory Structure**
   - Tree or description of organization

9. **System Requirements**
   - Minimum specifications
   - Tested platforms

10. **Known Issues** (if applicable)
    - Any limitations or edge cases

**Social Science Data Editors Template**: Strongly recommended
Note: Link not provided in sources but mentioned in guidelines

**Pass Criteria**:

- ✅ README.pdf exists (or README.md as source)
- ✅ ≥100 lines (markdown) or comprehensive PDF
- 👤 All required sections present
- 👤 Instructions are clear and complete
- 👤 Data Availability Statement included
- 👤 Data citations in dedicated references section

**Fail Criteria**:

- ❌ README missing
- ❌ <100 lines markdown or insufficient PDF detail
- ❌ Missing required sections (especially Data Availability Statement)

**Check Method**:

```python
# Verify README.pdf or README.md exists
# Count non-empty lines (if markdown)
# MANUAL: AI checks for required sections and clarity
```

---

### B.2: Reproduction Script
**ID**: `B.2`
**Requirement**: Master reproduction script exists and is executable
**Automation**: 🤖 FULL
**Source**: ES Data Editor best practices

**Details**:

**Script Requirements**:

- Must provide reproduce.sh (preferred) or reproduce.py
- Script must be executable (chmod +x)
- Should be master script calling all subsidiary scripts
- Should regenerate all computational results

**Best Practices** (from ES Data Editor guidelines):

- **Master files**: Create master files calling all subsidiary scripts in order
- **Meaningful names**: Use "Main" or "Master" in primary file names
- **Relative paths**: Use relative paths or global variables (not hardcoded absolute paths)
- **Cross-platform**: Forward slashes for directory separation (even on Windows)
- **Tested**: Test code from replication folder on multiple machines
- **Log files**: Include log files documenting execution results

**For Compiled Languages**:

- Include make files reproducing compilation steps
- Document compiler options
- Provide explicit instructions if specialized software lacks script capabilities

**Pass Criteria**:

- ✅ reproduce.sh OR reproduce.py exists
- ✅ File is executable (has +x permission)
- 👤 Script is master orchestrator (calls subsidiary scripts)
- 👤 Uses relative paths
- 👤 Cross-platform compatible (forward slashes)
- 👤 Generates log files

**Fail Criteria**:

- ❌ No reproduction script found
- ⚠️ Uses hardcoded absolute paths
- ⚠️ Not tested on multiple platforms

**Check Method**:

```python
# Check for reproduce.sh or reproduce.py
# Verify file permissions include execute
# MANUAL: AI checks for relative paths and master script structure
```

---

### B.3: Raw Data Files
**ID**: `B.3`
**Requirement**: Raw data included in proper format with complete documentation
**Automation**: 🤖 PARTIAL (warns if no data found)
**Source**: ES Data and Code Availability Policy

**Details**:

**Data Inclusion Requirements**:

- **Primary and secondary data** must be included unless exemptions granted
- **Raw data** (not just processed data) required
- If data cannot be included: provide access instructions in README

**Data Format Requirements** (critical):

- **Mandatory**: Plain ASCII formats like **CSV** (comma-separated values)
- **Non-proprietary copies required**: Even if you use Stata/Excel/MATLAB
- **Proprietary formats**: May supplement but **cannot replace** CSV versions
- Acceptable plain text formats: CSV, TXT, TSV, JSON

**Metadata Requirements**:

- "Description of variables and their allowed values"
- Must be publicly accessible through:
  - Variable labels in data files
  - Codebooks (separate documentation files)
  - README documentation

**Data Citation Requirements**:

- All data sources **must be cited** in:
  - Paper/appendices
  - **Dedicated references section in README.pdf**
- Citations must follow journal format for bibliometric indexing
- Include: author, title, publisher, year, access date, DOI/URL

**Project-Specific: SCF Data on Artifacts Branch**:

- **Special requirement from data editor**: Survey of Consumer Finances (SCF) data must be on **artifacts branch**, NOT main branch
- Main branch should include download/access script
- Rationale: Large data files should not bloat main repository
- See reproduce/reproduce_data_moments.sh for implementation

**Pass Criteria**:

- ✅ Data files found in common locations (Data/, data/, Code/Empirical/Data/), OR
- ✅ CSV/plain text versions of all data, OR
- 👤 README documents data access (if no data files in repo)
- 👤 Metadata/codebook for all variables
- 👤 Data citations in README references section
- 👤 SCF data on artifacts branch (project-specific)

**Fail Criteria**:

- ❌ Proprietary format without CSV equivalent
- ❌ No data files and no README data access section
- ⚠️ No variable documentation (codebook/labels)
- ⚠️ Data not cited in README references

**Check Method**:

```python
# Search for data files in: Data/, data/, Code/*/
# Count .dta, .csv, .xlsx, .txt files
# Check for .csv versions of proprietary formats
# Warn if only proprietary formats found
# Check for artifacts branch with git show-ref
# MANUAL: AI checks README for data access instructions and citations
```

---

### B.4: Data Transformation Code
**ID**: `B.4`
**Requirement**: All data cleaning and transformation code included
**Automation**: 🤖 PARTIAL
**Source**: ES Data and Code Availability Policy

**Details**:

**Requirements**:

- **All data transformation programs must be included**
- Clear separation of data cleaning and analysis code recommended
- Hierarchical organization for version control
- Code must be in **source format** (not compiled binaries only)
- Generates analysis datasets from raw data

**Organization Best Practices**:

- Separate directory for data cleaning (e.g., Data/cleaning/)
- Clear naming: 01_clean_data.py, 02_merge_datasets.py, etc.
- Document any manual data preparation steps in README

**Pass Criteria**:

- ✅ Data transformation scripts exist (in Code/, scripts/, or similar)
- 👤 Clear separation from analysis code
- 👤 README documents data transformation workflow
- 👤 Generates intermediate datasets if needed

**Fail Criteria**:

- ⚠️ No data transformation code found but processed data used
- ⚠️ Compiled binaries only (no source)

**Check Method**:

```python
# Search for scripts with "clean", "transform", "prepare" in name
# Check for data processing directories
# MANUAL: AI verifies transformation workflow documented
```

---

### B.5: Analysis Code
**ID**: `B.5`
**Requirement**: Code reproduces all computational exhibits in paper
**Automation**: 👤 MANUAL (requires execution)
**Source**: ES Data and Code Availability Policy

**Details**:

**Requirements**:

- Analysis code must **reproduce all computational exhibits** in the paper
- Must generate outputs matching manuscript exhibits
- Well-organized with logical structure
- Meaningful file/function names
- Comments explain non-obvious logic
- No hardcoded paths (use relative paths or globals)
- Parameters documented

**Code Quality Standards**:

- Logical organization
- Descriptive names
- Adequate comments
- Portable (works on different machines)
- Version-controlled friendly structure

**Pass Criteria**:

- 👤 Code structure is clear and logical
- 👤 All figures/tables can be generated
- 👤 Documentation is adequate
- 👤 No hardcoded paths
- 👤 Results match paper

**Fail Criteria**:

- ❌ Code cannot generate paper results
- ⚠️ Hardcoded paths
- ⚠️ Poor organization or documentation

**Check Method**:

- MANUAL: AI samples code files and reviews structure
- MANUAL: Test execution reproduces results

```

---

### B.6: Restricted Data Procedures
**ID**: `B.6`
**Requirement**: Proper handling of confidential or restricted-access data
**Automation**: 👤 MANUAL
**Source**: ES Data and Code Availability Policy

**Details**:

**When Data Cannot Be Publicly Shared**:
The journal acknowledges practical difficulties with proprietary or restricted-access datasets.

**Required Procedures**:

1. **Exemption Documentation**:
   - Clear explanation in README of why data cannot be shared
   - Confidentiality agreements, ethical restrictions, or proprietary licenses

2. **Temporary ES Access** (if possible):
   - Provide Data Editor temporary access for reproducibility verification
   - Specify access duration and conditions

3. **Synthetic Datasets** (if temporary access not possible):
   - Create synthetic or simulated datasets matching structure
   - Document how synthetic data relates to real data
   - Code should run on synthetic data to verify correctness

4. **Access Instructions in README**:
   - Detailed instructions for others to obtain data
   - Application procedures
   - Expected timeline for access
   - Costs (if any)
   - Contact information for data provider

**Pass Criteria**:
- 👤 Exemption clearly documented in README
- 👤 Temporary access provided to Data Editor, OR
- 👤 Synthetic dataset included with documentation
- 👤 Access instructions complete and current

**Fail Criteria**:
- ❌ Restricted data with no exemption documentation
- ❌ No access instructions or synthetic alternative

**Note**: This requirement only applies when data cannot be publicly shared.

---

### B.7: Analysis Datasets
**ID**: `B.7`
**Requirement**: Include analysis datasets if not regenerable within reasonable time
**Automation**: 👤 MANUAL
**Source**: ES Data Editor guidelines

**Details**:

**When to Include**:
- If data transformation takes >1 hour to run
- If raw data is extremely large (>1GB)
- If transformation requires specialized software or computing resources

**When Not Needed**:
- If transformation is fast (<1 hour)
- If raw data is manageable size
- If README provides clear instructions

**Format**:
- Same format requirements as raw data (CSV preferred)
- Clearly labeled as "analysis" or "processed" data
- README documents which analysis datasets are pre-generated

**Pass Criteria**:
- ✅ Analysis datasets included when regeneration time >1 hour, OR
- ✅ Transformation is fast enough to regenerate

**Fail Criteria**:
- ⚠️ No analysis datasets but transformation takes >1 hour

---

### B.8: Software Dependencies
**ID**: `B.8`
**Requirement**: Complete specification of software environment
**Automation**: 🤖 FULL
**Source**: ES Data Editor guidelines

**Details**:

**Dependency File Requirements**:
- Document all software dependencies
- Specify **exact versions** (especially for reproducibility-critical packages)
- Common formats:
  - environment.yml (Conda)
  - requirements.txt (pip)
  - pyproject.toml (Poetry/UV)
  - Pipfile (pipenv)
  - Makefile (for compiled languages)

**Computational Requirements in README**:
- Software versions (exact versions, e.g., Python 3.9.1, not just "Python 3")
- Hardware requirements (RAM, CPU cores if parallel)
- Operating system tested on
- Runtime estimates

**Pass Criteria**:
- ✅ At least one dependency file exists (environment.yml, requirements.txt, pyproject.toml, or Pipfile)
- 👤 Exact versions specified for key packages
- 👤 README documents software requirements

**Fail Criteria**:
- ⚠️ No dependency files found (warning only)
- ⚠️ Version ranges instead of exact versions for critical packages

**Check Method**:
```python
# Check for: environment.yml, requirements.txt, pyproject.toml, Pipfile
# Count how many exist
# MANUAL: AI verifies exact versions specified
```

---

### B.9: Open License
**ID**: `B.9`
**Requirement**: LICENSE file with license permitting unrestricted replication use
**Automation**: 🤖 FULL
**Source**: ES Data Editor guidelines

**Details**:

- Must include LICENSE file in repository root
- License must permit **unrestricted replication use**
- Common acceptable licenses:
  - Apache 2.0
  - MIT
  - CC BY 4.0
  - BSD 3-Clause
- QE requires open access to replication materials

**Pass Criteria**:

- ✅ LICENSE file exists (LICENSE, LICENSE.md, or LICENSE.txt)
- 👤 License permits unrestricted replication use

**Fail Criteria**:

- ❌ LICENSE file missing

**Check Method**:

```python
# Check for LICENSE, LICENSE.md, LICENSE.txt
# Verify file is non-empty
# MANUAL: AI verifies license type permits replication
```

**Note**: After journal acceptance, authors add LICENSE. For initial submission, this may be non-compliant.

---

### B.10: Zenodo DOI
**ID**: `B.10`
**Requirement**: Zenodo DOI for replication package (post-acceptance)
**Automation**: 🤖 PARTIAL (searches for DOI pattern)
**Source**: ES Data Editor guidelines, Zenodo ES community

**Details**:

- Upload replication package to **Econometric Society Journals' Community at Zenodo**
- Zenodo community: <https://zenodo.org/communities/es-replication-repository>
- Obtain DOI (format: 10.5281/zenodo.XXXXX)
- Cite DOI in README and titlepage

**Metadata Requirements for Zenodo**:

- Full manuscript citation
- Author names and affiliations
- Publication year
- Journal name (Quantitative Economics)
- DOI of published paper (after publication)

**Pass Criteria**:

- ✅ DOI found in README or titlepage (post-acceptance)
- 👤 Deposited at ES Zenodo community

**Fail Criteria**:

- ❌ DOI not found (non-compliant post-acceptance only)

**Check Method**:

```python
# Search README and titlepage for: 10.5281/zenodo
# This is EXPECTED to fail for initial submission
```

**Note**: Required **after acceptance**, not for initial submission. Expect non-compliant status initially.

---

## SECTION C: Submission Quality (Manual/AI Checks)

### C.1: Code Organization
**ID**: `C.1`
**Requirement**: Well-organized, portable, commented code
**Automation**: 👤 MANUAL
**Source**: ES Data Editor best practices

**Details**:

**Organization**:

- Code files organized logically (by analysis stage, by output type, etc.)
- Clear directory structure
- Meaningful file/function names
- README documents code structure

**Portability Requirements**:

- **No hardcoded absolute paths** (use relative paths or globals)
- **Forward slashes** for directory separation (even on Windows: `path/to/file`)
- **Relative paths** from repository root or configurable base path
- **Tested on multiple machines/OSes** before submission

**Documentation**:

- Comments explain non-obvious logic
- Function/class documentation
- Parameters documented
- Data structures explained

**Pass Criteria**:

- 👤 Code structure is clear and logical
- 👤 No hardcoded absolute paths
- 👤 Uses forward slashes for paths
- 👤 Documentation is adequate
- 👤 Portable across platforms

**Fail Criteria**:

- ⚠️ Hardcoded paths
- ⚠️ Platform-specific code without alternatives
- ⚠️ Poor organization or insufficient comments

**Check Method**:

- AI samples code files and reviews structure
- AI searches for hardcoded paths (e.g., C:\, /Users/, /home/)
- AI checks for platform-specific code

---

### C.2: Results Linkage
**ID**: `C.2`
**Requirement**: Clear connection between code and paper results
**Automation**: 👤 MANUAL
**Source**: Best practices

**Details**:

- Each figure can be traced to generating code
- Each table can be traced to generating code
- README documents output mapping (Table 1 → script.py line 42, etc.)
- Results match paper (verified by reproducibility check)

**Output Mapping Best Practices**:

- README section listing each exhibit with generating code
- Comments in code identifying which exhibit is produced
- Output files named consistently (e.g., table1.tex, figure2.pdf)

**Pass Criteria**:

- 👤 Figure/table generation is clearly documented
- 👤 README explains how results link to code
- 👤 Output mapping provided

**Fail Criteria**:

- ⚠️ Cannot trace exhibits to code
- ⚠️ No output mapping in README

**Check Method**:

- AI reviews README for output mapping section
- AI checks if code structure makes linkage clear

---

### C.3: Co-editor Acknowledgment Prohibition
**ID**: `C.3`
**Requirement**: Do not thank handling co-editor in submission
**Automation**: 👤 MANUAL
**Source**: qe_sample.tex (line 84 note)

**Details**:

**Prohibition**:

- Do not thank the handling co-editor **anonymously or by name**
- Not in funding/acknowledgments section
- Not elsewhere in the paper
- This is explicitly noted in QE sample template

**Rationale**:

- Maintains anonymity of editorial process
- Prevents identification of handling editor during review

**After Acceptance**:

- Co-editor name will be inserted by journal in final version
- Authors do not need to add this

**Pass Criteria**:

- 👤 No co-editor acknowledgment found in paper

**Fail Criteria**:

- ❌ Co-editor thanked (violates submission rules)

**Check Method**:

- AI searches `\begin{funding}` and acknowledgments for co-editor mentions
- AI looks for phrases like "handling editor", "co-editor", "editorial guidance"

---

### C.4: Supplementary Appendices
**ID**: `C.4`
**Requirement**: Supplementary appendices properly formatted and limited
**Automation**: 🤖 PARTIAL
**Source**: QE submission instructions

**Details**:

**Requirements**:

- Supplementary appendices clearly labeled
- **Maximum 25 pages** for supplemental material
- Separate from main text if very long
- Properly formatted with appendix environment

**Format**:

- Use `\begin{appendix}` environment
- Single appendix: `\section*{Appendix}` (no title needed if just one)
- Multiple appendices: `\section{Appendix A}`, `\section{Appendix B}`, etc.

**Pass Criteria**:

- ✅ Appendix files found in Subfiles/ (if separate), OR
- ✅ Appendix in main document, OR
- ✅ No appendices (acceptable)
- 👤 Supplemental appendices ≤25 pages (if separate)

**Fail Criteria**:

- ⚠️ Supplemental appendices >25 pages

**Check Method**:

```python
# Search Subfiles/ for Appendix-*.tex or supplement-*.tex
# Count and report if found
# MANUAL: AI checks page count if separate
```

---

## SECTION D: Submission Packaging

### D.1: Package Format
**ID**: `D.1`
**Requirement**: Proper packaging of submission materials
**Automation**: 👤 MANUAL (pre-submission)
**Source**: ES Data Editor package guidelines

**Details**:

**Zip File Requirements**:

- Submit as **single zip file** containing all replication materials
- Paper and online appendices **separate** (outside the replication zip)
- For confidential data: **separate clearly labeled zip file**
- Maximum file size: **100MB per file** (up to 3 files allowed)

**What Goes in Replication Zip**:

- All code files
- All data files (or data access documentation)
- README.pdf
- LICENSE file
- Dependency specifications (environment.yml, requirements.txt, etc.)
- reproduce.sh or reproduce.py
- Any makefiles or build scripts

**What Goes Outside Replication Zip**:

- Main paper PDF
- Online appendices PDF
- Cover letters

**Submission via Editorial Express**:

- Identifying information (Title, Journal, MS number, RP number)
- Manuscript and approved appendices (PDF)
- Completed and signed checklist
- Cover letter to handling editor
- Cover letter to data editor
- Replication package zip file(s)

**Pass Criteria**:

- 👤 Replication materials in single zip
- 👤 Paper separate from replication package
- 👤 Each zip file ≤100MB

**Fail Criteria**:

- ⚠️ Zip file >100MB (requires splitting or hosting elsewhere)

---

### D.2: DCAS Standard Compliance
**ID**: `D.2`
**Requirement**: Package meets DCAS v1.0 standard
**Automation**: 👤 MANUAL
**Source**: Econometric Society endorsement of DCAS

**Details**:

**DCAS (Data and Code Availability Standard)**:

- Version 1.0 endorsed by Econometric Society journals
- Comprehensive checklist for replication packages
- Covers data availability, code quality, documentation

**Use as Checklist**:

- Review package against DCAS requirements
- Ensure all applicable items addressed
- Document any exemptions in README

**Pass Criteria**:

- 👤 Package meets DCAS v1.0 requirements (as applicable)

**Note**: DCAS provides more detailed checklist than this spec for certain items.

---

## Compliance Summary Format

The compliance checker outputs JSON with this structure:

```json
{
  "metadata": {
    "generated": "2025-11-25T10:00:00Z",
    "qe_root": "/path/to/HAFiscal-QE",
    "checker_version": "2.0",
    "spec_version": "2.0"
  },
  "results": [
    {
      "requirement_id": "A.1",
      "requirement": "Document class uses econsocart",
      "status": "compliant",
      "evidence": ["HAFiscal.tex line 14: \\documentclass[qe]{econsocart}"],
      "files_checked": ["/path/to/HAFiscal.tex"],
      "recommendation": "None required",
      "source": "qe_template.tex"
    },
    {
      "requirement_id": "B.3",
      "requirement": "Raw data in CSV format",
      "status": "warning",
      "evidence": ["Found .dta files but no .csv equivalents"],
      "files_checked": ["/path/to/Data/"],
      "recommendation": "Provide CSV versions of data files per ES Data Editor policy",
      "source": "ES Data and Code Availability Policy"
    }
  ]
}
```

---

## Expected Non-Compliance (Initial Submission)

These requirements are **expected to fail** on initial submission:

1. **B.9 (LICENSE)**: Added after acceptance
2. **B.10 (Zenodo DOI)**: Created after acceptance

All other requirements should be **compliant** before submission.

---

## AI Verification Prompt

To verify compliance using AI, use this prompt structure:

```
Review the QE submission at [PATH] against QE-COMPLIANCE-SPEC.md v2.0.

For each requirement:
1. Run automated check (if available)
2. Review evidence
3. Perform manual verification (where needed)
4. Check source citations
5. Report: COMPLIANT / WARNING / NON-COMPLIANT

Focus on manual checks (marked 👤 MANUAL) that automation cannot verify.

Pay special attention to:
- Data format requirements (CSV versions)
- README completeness (Data Availability Statement, citations)
- Cross-platform portability (relative paths, forward slashes)
- Co-editor acknowledgment prohibition
- SCF data on artifacts branch (project-specific)

Generate detailed report with:
- Requirement ID
- Status (✅ ⚠️ ❌)
- Evidence
- Source reference
- Recommendations (if non-compliant)
```

---

## Requirement Summary Table

| ID | Requirement | Automation | Critical | Source |
|----|-------------|------------|----------|--------|
| **Section A: Manuscript** |
| A.1 | Document class | 🤖 FULL | ✅ Yes | Template |
| A.2 | Bibliography style | 🤖 FULL | ✅ Yes | Template |
| A.3 | Abstract/JEL/Keywords | 🤖 PARTIAL | ✅ Yes | Template |
| A.4 | Title/Authors/Running title | 🤖 PARTIAL | ✅ Yes | Template |
| A.5 | Manuscript layout | 👤 MANUAL | ⚠️ Recommended | Instructions |
| A.6 | Figures and tables | 🤖 PARTIAL | ⚠️ Verify captions | Best practices |
| **Section B: Replication Package** |
| B.1 | README.pdf documentation | 🤖 PARTIAL | ✅ Yes | ES Data Editor |
| B.2 | Reproduction script | 🤖 FULL | ✅ Yes | ES Data Editor |
| B.3 | Raw data (CSV format) | 🤖 PARTIAL | ✅ Yes | ES Policy |
| B.4 | Data transformation code | 🤖 PARTIAL | ✅ Yes | ES Policy |
| B.5 | Analysis code | 👤 MANUAL | ✅ Yes | ES Policy |
| B.6 | Restricted data procedures | 👤 MANUAL | ⚠️ If applicable | ES Policy |
| B.7 | Analysis datasets | 👤 MANUAL | ⚠️ If needed | ES Data Editor |
| B.8 | Software dependencies | 🤖 FULL | ⚠️ Recommended | ES Data Editor |
| B.9 | LICENSE | 🤖 FULL | ⚠️ Post-acceptance | ES Data Editor |
| B.10 | Zenodo DOI | 🤖 PARTIAL | ⚠️ Post-acceptance | ES Data Editor |
| **Section C: Quality** |
| C.1 | Code organization & portability | 👤 MANUAL | ⚠️ Review needed | ES Best Practices |
| C.2 | Results linkage | 👤 MANUAL | ⚠️ Review needed | Best practices |
| C.3 | Co-editor prohibition | 👤 MANUAL | ✅ Yes | Template note |
| C.4 | Supplemental appendices | 🤖 PARTIAL | ⚠️ If applicable | Instructions |
| **Section D: Packaging** |
| D.1 | Package format | 👤 MANUAL | ✅ Yes | ES Data Editor |
| D.2 | DCAS compliance | 👤 MANUAL | ⚠️ Recommended | ES endorsement |

**Legend**:

- ✅ Yes = Must be compliant before submission
- ⚠️ = Review recommended but not always blocking
- Post-acceptance = Expected to fail initially

---

## Updates and Maintenance

This specification should be updated when:

- QE journal changes requirements
- Econometric Society updates Data Editor guidelines
- Automated checker adds new validations
- User feedback identifies gaps
- Template files are updated

**Version History**:

- **2.0** (2025-11-25): Comprehensive update based on full review of official sources
  - Added source URLs for all requirements
  - Fixed README.pdf vs README.md clarification
  - Added data format requirements (CSV mandatory)
  - Added raw data requirement
  - Added SCF artifacts branch requirement (project-specific)
  - Corrected abstract/JEL/keyword counts per template
  - Added co-editor acknowledgment prohibition
  - Added running title requirement
  - Added manuscript layout requirements
  - Added data transformation code section
  - Added restricted data procedures
  - Added analysis datasets clarification
  - Expanded code organization with portability requirements
  - Added submission packaging section
  - Added DCAS standard reference
  - Added master script best practices
  - Added log file documentation requirement
  - Added Social Science Data Editors template recommendation
  - 26 total requirements (up from 16 in v1.0)

- **1.0** (2025-11-22): Initial specification consolidating SUBMISSION-REQUIREMENTS.md and COMPLIANCE-CHECKLIST.md

---

**Specification Completeness**: This v2.0 specification captures all known requirements from official QE and Econometric Society sources as of 2025-11-25.

**Maintenance Contact**: HAFiscal project team
**Last Verified Against Official Sources**: 2025-11-25

## Decision Letter Notes (MS 2442)

In addition to the standing requirements drawn from official QE and Econometric Society sources, the handling editor's conditional-acceptance email for MS 2442 (archived as `QE-COMPLIANCE-email.eml` in this directory) specifies **procedural instructions** for the final submission and replication check. These notes summarize those instructions and link them to the requirements already encoded above.

**Source Document**:

- Conditional-acceptance email from Morten Ravn (Subject: "QE: decision on MS 2442"), saved as `QE-COMPLIANCE-email.eml` in `qe/compliance/`.

**Procedural Requirements from the Decision Letter**:

1. **Data Editor Workflow**
   - Authors must treat the replication package as a **new submission to the Data Editor**, using the ES Data Editor Editorial Express site:
     - `https://editorialexpress.com/ESData`
   - The decision letter explicitly points to the following steps (all of which are already covered by the official-source URLs at the top of this SPEC):
     1. Review the **Data and Code Availability Policy**  
        - `https://www.econometricsociety.org/publications/es-data-editor-website/data-and-code-availability-policy`
     2. Follow the **package preparation steps**  
        - `https://www.econometricsociety.org/publications/es-data-editor-website/package`
     3. Complete the **Data Editor checklist** (PDF)  
        - `https://www.econometricsociety.org/uploads/reports/ES_Data_Editor_Website/Checklist.pdf`
     4. Submit the replication package and associated documents to the Data Editor as a **new submission** in Editorial Express (resubmission there is used only for replication-check revisions).

2. **Items to Submit as Separate Files to the Data Editor**
   The letter requires the following to be submitted as **separate files** (procedural packaging around the requirements in Sections A–D above):
   - Replication files for review (the replication package described in Sections B and D of this SPEC).  
     - If the package is too large to upload, authors must email the Data Editor (`dataeditor@econometricsociety.org`) for alternate instructions.
   - Cover letter to the Data Editor outlining any exemptions or special instructions (e.g., restricted data handling per B.6).
   - Completed **Data Editor checklist** (based on the Checklist.pdf referenced above).
   - Final manuscript (HAFiscal.pdf built with `\documentclass[qe]{econsocart}`).
   - Any approved online appendices (supplements).
   - Cover letter to the handling editor if there were last minor revisions.

3. **Deadlines and Extensions**
   - **Data submission deadline**: Data files and replication materials should be submitted to the Data Editor **within one month** of the decision.
   - **Extensions**:
     - For data/editorial logistics: contact the Director of Publications at `qe@econometricsociety.org`.
     - The offer to revise/conditionally accept is normally valid for **12 months** from the decision date; extensions to this window are at the handling editor's discretion and must be requested within the 12‑month period.

4. **Cases Without Replication Files**
   - If there are **no replication files**, the final revision may be submitted at the QE submissions page:  
     - `https://www.econometricsociety.org/publications/quantitative-economics/submissions`
   - For HAFiscal, this path is **not applicable** because a full replication package is provided (Sections B and D).

5. **Supplementary Appendices Formatting**
   - The letter clarifies production practices for supplemental appendices:
     - QE **no longer typesets supplemental appendices**.
     - Supplements must be **standalone** in both:
       - Their **production files** (LaTeX sources), and
       - Their **PDFs**.
     - Supplements must use the **QE journal style** from:
       - `https://www.e-publications.org/es/support/`
     - Supplements should be **referenced and cited in the main text** (not treated as previously circulated working-paper appendices).
   - These points are complementary to:
     - **C.4: Supplementary Appendices** (page limits, labeling, use of appendix environments).
     - **A.1–A.6** (use of `econsocart` and QE templates for both main paper and supplements).

6. **Transfer Back to Handling Editor**
   - After the Data Editor verifies the replication package and declares it acceptable, all final materials are transferred back to the handling editor for final approval and acceptance.
   - This step does not introduce new technical requirements beyond those already encoded in Sections A–D, but clarifies the **sequence**: replication-check completion **precedes** the editor's final acceptance.

7. **Access and Download Limits for Decision-Letter Attachments**
   - The decision letter also mentions time‑limited access and a maximum number of downloads for the decision attachments (e.g., 25 downloads, expiry date).  
   - These are **operational constraints of Editorial Express**, not standing QE replication requirements, and therefore are **not encoded** as compliance items in this SPEC.

Taken together, `QE-COMPLIANCE-email.eml` provides **procedural context** and confirms that the requirements listed in this SPEC (drawn from the URLs referenced in the email) are the basis for the Data Editor's replication review. This section is intended to document that linkage, not to introduce additional technical requirements beyond those already enumerated in Sections A–D.
